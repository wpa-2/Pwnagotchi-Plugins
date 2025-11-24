import json
import logging
import os
import time
import threading
import queue
import atexit
from typing import Any, Dict, List, Optional

import requests
from requests import RequestException

import pwnagotchi.plugins as plugins
from pwnagotchi.agent import Agent

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
LOG_DIR = "/etc/pwnagotchi/log"
LOG_FILE = os.path.join(LOG_DIR, "discord_plugin.log")
CACHE_FILE = "/home/pi/handshakes/discord_wigle_cache.json"

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)

# ----------------------------------------------------------------------------
# Logging Setup
# ----------------------------------------------------------------------------
logger = logging.getLogger("pwnagotchi.plugins.discord")
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


class Discord(plugins.Plugin):
    __author__ = "WPA2"
    __version__ = '2.6.0'
    __license__ = 'GPL3'
    __description__ = 'Sends Pwnagotchi handshakes (w/ pcap) and reports Last Session stats on boot/mode switch.'

    def __init__(self):
        super().__init__()
        self.webhook_url: Optional[str] = None
        self.api_key: Optional[str] = None
        self.http_session = requests.Session()
        self.wigle_cache: Dict[str, Dict[str, str]] = {}
        
        # Deduplication
        self.recent_handshakes = set()
        self.recent_handshakes_limit = 200

        # Threading & Queue
        self._event_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread = None

        # Session Stats (Current)
        self.session_handshakes = 0
        self.start_time = time.time()
        self.session_id = os.urandom(4).hex()
        
        # Register the safety net for Hard Shutdowns (Poweroff/Systemctl Stop)
        atexit.register(self._on_exit_cleanup)

    def on_loaded(self):
        logger.info("Discord plugin loaded.")
        self.webhook_url = self.options.get("webhook_url", None)
        self.api_key = self.options.get("wigle_api_key", None)

        self._load_wigle_cache()

        if not self.webhook_url or not self.api_key:
            logger.error("Discord plugin: Missing webhook_url or wigle_api_key.")
            return

        # Start the background worker
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info(f"Discord plugin: Worker thread started. Session ID: {self.session_id}")

    def on_unload(self, ui):
        self._on_exit_cleanup()

    def _on_exit_cleanup(self):
        if self._stop_event.is_set(): return

        logger.info("Discord plugin: Cleaning up...")
        self._save_wigle_cache()
        
        # Stop thread
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)

    # ------------------------------------------------------------------------
    # Event Triggers
    # ------------------------------------------------------------------------

    def on_ready(self, agent: Agent):
        self.start_time = time.time()
        logger.info("Discord plugin: Pwnagotchi is ready.")
        
        try:
            unit_name = agent.config()['main']['name']
        except:
            unit_name = "Pwnagotchi"

        # 1. Send Online Message
        self.queue_notification(
            content="🟢 **Pwnagotchi is Online!**",
            embed={
                'title': f"{unit_name} is Ready",
                'description': f"Unit is ready and sniffing.\n**Plugin Session ID:** `{self.session_id}`",
                'color': 5763719  # Green
            }
        )

        # 2. Report PREVIOUS Session Stats (The Persistence Fix)
        # This catches the stats from the session that just ended (Manual Switch / Reboot)
        if hasattr(agent, 'last_session') and agent.last_session:
            last = agent.last_session
            # Only report if it actually lasted some time to avoid empty spam on fresh flashes
            if hasattr(last, 'duration') and str(last.duration) != "0:00:00":
                logger.info(f"Discord plugin: Found last session stats. Duration: {last.duration}")
                
                # Attempt to get handshake count safely
                hs_count = getattr(last, 'handshakes', 0)
                
                self.queue_notification(
                    content="📋 **Previous Session Report**",
                    embed={
                        'title': 'Session Summary',
                        'description': (f"**Handshakes:** {hs_count}\n"
                                        f"**Duration:** {last.duration}\n"
                                        f"**Epochs:** {getattr(last, 'epochs', 0)}"),
                        'color': 12370112 # Orange/Grey
                    }
                )

    def on_handshake(self, agent: Agent, filename: str, access_point: Dict[str, Any], client_station: Dict[str, Any]):
        bssid = access_point.get("mac", "00:00:00:00:00:00")
        client_mac = client_station.get("mac", "00:00:00:00:00:00")
        handshake_key = (filename, bssid.lower(), client_mac.lower())

        if handshake_key in self.recent_handshakes:
            return 
        
        self.recent_handshakes.add(handshake_key)
        if len(self.recent_handshakes) > self.recent_handshakes_limit:
            self.recent_handshakes.pop()

        self.session_handshakes += 1

        self._event_queue.put({
            'type': 'handshake',
            'filename': filename,
            'access_point': access_point,
            'client_station': client_station
        })

    # ------------------------------------------------------------------------
    # Worker Logic
    # ------------------------------------------------------------------------

    def _worker_loop(self):
        while not self._stop_event.is_set() or not self._event_queue.empty():
            try:
                timeout = 1.0 if not self._stop_event.is_set() else 0.1
                event = self._event_queue.get(timeout=timeout)
            except queue.Empty:
                if self._stop_event.is_set(): break
                continue

            try:
                if event.get('type') == 'handshake':
                    self._process_handshake(event)
                elif event.get('type') == 'notification':
                    self._send_discord_payload(event['content'], event.get('embeds'))
                
                if not self._stop_event.is_set():
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"Discord plugin: Error in worker loop: {e}")
            finally:
                self._event_queue.task_done()

    def queue_notification(self, content: str, embed: Optional[Dict] = None):
        payload = {
            'type': 'notification',
            'content': content,
            'embeds': [embed] if embed else []
        }
        self._event_queue.put(payload)

    def _process_handshake(self, event):
        filename = event['filename']
        ap = event['access_point']
        client = event['client_station']
        bssid = ap.get("mac", "")

        location = self._get_location_from_wigle(bssid)
        if location:
            loc_str = (f"Latitude: {location['lat']}, Longitude: {location['lon']}\n"
                       f"[View on Map](https://www.google.com/maps/search/?api=1&query={location['lat']},{location['lon']})")
        else:
            loc_str = "Location not available."

        embed = {
            'title': '🔐 New Handshake Captured!',
            'description': (f"**Access Point:** {ap.get('hostname', 'Unknown')}\n"
                            f"**Client Station:** {client.get('mac', 'Unknown')}"),
            'fields': [
                {'name': '🗂 Handshake File', 'value': os.path.basename(filename), 'inline': False},
                {'name': '📍 Location', 'value': loc_str, 'inline': False},
            ],
            'footer': {'text': f"Total Session Handshakes: {self.session_handshakes} | ID: {self.session_id}"},
            'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            'color': 16776960 # Yellow
        }

        self._send_discord_payload(
            content=f"🤝 New handshake from {ap.get('hostname', 'Unknown')}",
            embeds=[embed],
            file_path=filename
        )

    # ------------------------------------------------------------------------
    # Discord Sender
    # ------------------------------------------------------------------------

    def _send_discord_payload(self, content: str, embeds: List[Dict], file_path: Optional[str] = None):
        if not self.webhook_url: return

        payload_dict = {"content": content, "embeds": embeds}

        try:
            if file_path and os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
                    data = {'payload_json': json.dumps(payload_dict)}
                    self.http_session.post(self.webhook_url, files=files, data=data, timeout=30)
            else:
                self.http_session.post(self.webhook_url, json=payload_dict, 
                                     headers={'Content-Type': 'application/json'}, timeout=10)
        except Exception as e:
            logger.error(f"Discord plugin: Send error: {e}")

    # ------------------------------------------------------------------------
    # WiGLE Logic
    # ------------------------------------------------------------------------

    def _get_location_from_wigle(self, bssid: str) -> Optional[Dict[str, Any]]:
        if not bssid: return None
        normalized = bssid.lower()

        if normalized in self.wigle_cache:
            return self.wigle_cache[normalized]

        if not self.api_key: return None

        headers = {'Authorization': f'Basic {self.api_key}'}
        params = {'netid': normalized}
        try:
            res = self.http_session.get('https://api.wigle.net/api/v2/network/detail', 
                                      headers=headers, params=params, timeout=10)
            
            if res.status_code == 200:
                data = res.json()
                if data.get('success') and data.get('results'):
                    r = data['results'][0]
                    loc = {'lat': r.get('trilat', 'N/A'), 'lon': r.get('trilong', 'N/A')}
                    self.wigle_cache[normalized] = loc
                    return loc
        except Exception as e:
            logger.error(f"WiGLE lookup failed: {e}")
        return None

    def _load_wigle_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    self.wigle_cache = json.load(f)
            except:
                self.wigle_cache = {}

    def _save_wigle_cache(self):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(self.wigle_cache, f)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
