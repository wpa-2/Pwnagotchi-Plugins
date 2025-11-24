import json
import logging
import os
import time
import threading
import queue
from datetime import timedelta
from typing import Any, Dict, List, Optional

import requests
from requests import RequestException

import pwnagotchi.plugins as plugins
from pwnagotchi.agent import Agent
from pwnagotchi.voice import Voice

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
LOG_DIR = "/etc/pwnagotchi/log"
LOG_FILE = os.path.join(LOG_DIR, "discord_plugin.log")
CACHE_FILE = "/home/pi/handshakes/discord_wigle_cache.json"
SCREENSHOT_FILE = "/var/tmp/pwnagotchi/discord_status.png"

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
os.makedirs(os.path.dirname(SCREENSHOT_FILE), exist_ok=True)

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
    __description__ = 'Sends handshakes (pcap), status (screen capture), and stats to Discord. Threaded & Queued.'

    def __init__(self):
        super().__init__()
        self.webhook_url: Optional[str] = None
        self.api_key: Optional[str] = None
        self.status_interval_minutes: int = 60  # Default to hourly updates
        
        self.http_session = requests.Session()
        self.wigle_cache: Dict[str, Dict[str, str]] = {}
        
        # Deduplication
        self.recent_handshakes = set()
        self.recent_handshakes_limit = 200

        # Threading & Queue
        self._event_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread = None

        # Session Data
        self.session_handshakes = 0
        self.start_time = time.time()
        self.last_status_time = time.time()
        self.session_id = os.urandom(4).hex()
        
        # Reference to agent for screen capture
        self._agent = None

    def on_loaded(self):
        logger.info("Discord plugin loaded.")
        self.webhook_url = self.options.get("webhook_url", None)
        self.api_key = self.options.get("wigle_api_key", None)
        self.status_interval_minutes = self.options.get("status_interval", 60)

        self._load_wigle_cache()

        if not self.webhook_url:
            logger.error("Discord plugin: Missing webhook_url.")
            return

        # Start the background worker
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info(f"Discord plugin: Worker thread started. Session ID: {self.session_id}")

    def on_unload(self, ui):
        logger.info("Discord plugin: Unloading.")
        self._save_wigle_cache()
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

    # ------------------------------------------------------------------------
    # Event Triggers
    # ------------------------------------------------------------------------

    def on_ready(self, agent: Agent):
        self._agent = agent
        self.start_time = time.time()
        self.last_status_time = time.time()
        logger.info("Discord plugin: Pwnagotchi is ready.")
        
        unit_name = self._get_unit_name(agent)

        self.queue_notification(
            content="🟢 **Pwnagotchi is Online!**",
            embed={
                'title': f"{unit_name} is Ready",
                'description': f"Unit is ready and sniffing.\n**Plugin Session ID:** `{self.session_id}`",
                'color': 5763719  # Green
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

    def on_session_stop(self, agent: Agent, session: Any):
        logger.info("Discord plugin: Session stop detected.")
        # Trigger a final status update with screenshot
        self._capture_and_queue_status(agent, final=True)
        self._save_wigle_cache()

    # ------------------------------------------------------------------------
    # Worker Logic (The Brain)
    # ------------------------------------------------------------------------

    def _worker_loop(self):
        while not self._stop_event.is_set():
            # 1. Check for Queue Items
            try:
                event = self._event_queue.get(timeout=1.0)
            except queue.Empty:
                event = None

            if event:
                try:
                    if event.get('type') == 'handshake':
                        self._process_handshake(event)
                    elif event.get('type') == 'notification':
                        self._send_discord_payload(
                            event['content'], 
                            event.get('embeds'), 
                            event.get('file_path')
                        )
                    elif event.get('type') == 'status_update':
                         self._process_status_update(event)
                    
                    time.sleep(2) # Rate limit protection
                except Exception as e:
                    logger.error(f"Discord plugin: Error processing event: {e}")
                finally:
                    self._event_queue.task_done()

            # 2. Check for Heartbeat (Periodic Status)
            if self.status_interval_minutes > 0 and self._agent:
                if (time.time() - self.last_status_time) > (self.status_interval_minutes * 60):
                    logger.info("Discord plugin: Triggering scheduled status update.")
                    self._capture_and_queue_status(self._agent)
                    self.last_status_time = time.time()

    # ------------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------------

    def queue_notification(self, content: str, embed: Optional[Dict] = None):
        self._event_queue.put({
            'type': 'notification',
            'content': content,
            'embeds': [embed] if embed else []
        })

    def _get_unit_name(self, agent):
        try:
            return agent.config()['main']['name']
        except:
            return "Pwnagotchi"

    def _capture_and_queue_status(self, agent, final=False):
        """Captures screen and queues a status update event."""
        try:
            # Capture Screen
            if agent.view():
                agent.view().image().save(SCREENSHOT_FILE, 'png')
            
            # Queue the event
            self._event_queue.put({
                'type': 'status_update',
                'agent_info': {
                    'name': self._get_unit_name(agent),
                    'uptime': str(timedelta(seconds=int(time.time() - self.start_time))),
                    'session_handshakes': self.session_handshakes,
                },
                'final': final
            })
        except Exception as e:
            logger.error(f"Error capturing status: {e}")

    # ------------------------------------------------------------------------
    # Processors
    # ------------------------------------------------------------------------

    def _process_status_update(self, event):
        """Builds the stats embed and attaches the screenshot."""
        info = event['agent_info']
        is_final = event['final']
        
        # Use Pwnagotchi Voice for the flavor text
        # We need to mock a 'session' object if we want accurate voice lines, 
        # or we can just use the generic voice generation.
        # For simplicity, we'll try to get the 'best' voice line.
        try:
            if self._agent:
                voice_msg = Voice(lang=self._agent.config()['main']['lang']).on_last_session_tweet(self._agent.last_session)
            else:
                voice_msg = "Beep Boop."
        except:
            voice_msg = "Status Report:"

        embed = {
            'title': f"📊 Status of {info['name']}",
            'description': f"{voice_msg}\n\n**Uptime:** {info['uptime']}",
            'color': 15548997 if is_final else 3447003, # Red if stop, Blue if status
            'fields': [
                {'name': '🤝 Handshakes', 'value': str(info['session_handshakes']), 'inline': True},
                {'name': '🆔 Session ID', 'value': self.session_id, 'inline': True}
            ],
            'image': {'url': 'attachment://discord_status.png'},
            'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        content = "💤 **Session Ending**" if is_final else "ℹ️ **Status Update**"
        
        self._send_discord_payload(
            content=content,
            embeds=[embed],
            file_path=SCREENSHOT_FILE
        )

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
            'color': 16776960
        }

        self._send_discord_payload(
            content=f"🤝 New handshake from {ap.get('hostname', 'Unknown')}",
            embeds=[embed],
            file_path=filename
        )

    # ------------------------------------------------------------------------
    # Networking
    # ------------------------------------------------------------------------

    def _send_discord_payload(self, content: str, embeds: List[Dict], file_path: Optional[str] = None):
        if not self.webhook_url: return

        payload_dict = {"content": content, "embeds": embeds}

        try:
            if file_path and os.path.exists(file_path):
                # Multipart upload (JSON + File)
                with open(file_path, 'rb') as f:
                    filename = os.path.basename(file_path)
                    files = {'file': (filename, f, 'application/octet-stream')}
                    data = {'payload_json': json.dumps(payload_dict)}
                    self.http_session.post(self.webhook_url, files=files, data=data, timeout=30)
            else:
                # Standard JSON
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
