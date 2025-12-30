import json
import logging
import os
import time
import threading
import queue
import atexit
from collections import deque
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests
from requests import RequestException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import pwnagotchi.plugins as plugins
from pwnagotchi.agent import Agent

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
LOG_DIR = "/etc/pwnagotchi/log"
LOG_FILE = os.path.join(LOG_DIR, "discord_plugin.log")
CACHE_FILE = "/home/pi/handshakes/discord_wigle_cache.json"

# Timeouts
DISCORD_TIMEOUT = 30
DISCORD_QUICK_TIMEOUT = 10
WIGLE_TIMEOUT = 10

# Rate limiting
MAX_QUEUE_SIZE = 1000
WORKER_SLEEP_INTERVAL = 2.0

# Cache settings
CACHE_EXPIRY_DAYS = 30

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


# ----------------------------------------------------------------------------
# Data Classes
# ----------------------------------------------------------------------------
@dataclass
class CachedLocation:
    """Cached WiGLE location with timestamp"""
    lat: str
    lon: str
    timestamp: float
    
    def is_expired(self, expiry_days: int = CACHE_EXPIRY_DAYS) -> bool:
        """Check if cache entry has expired"""
        age_days = (time.time() - self.timestamp) / 86400
        return age_days > expiry_days
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'lat': self.lat,
            'lon': self.lon,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CachedLocation':
        return cls(
            lat=data['lat'],
            lon=data['lon'],
            timestamp=data.get('timestamp', time.time())
        )


# ----------------------------------------------------------------------------
# Discord Plugin
# ----------------------------------------------------------------------------
class Discord(plugins.Plugin):
    __author__ = "WPA2"
    __version__ = '3.0.1'
    __license__ = 'GPL3'
    __description__ = 'Enhanced Discord integration: sends handshakes with location data and session reports'

    def __init__(self):
        super().__init__()
        self.webhook_url: Optional[str] = None
        self.api_key: Optional[str] = None
        
        # HTTP Session with retry logic
        self.http_session = self._create_http_session()
        
        # WiGLE cache with expiry
        self.wigle_cache: Dict[str, CachedLocation] = {}
        self.cache_lock = threading.Lock()
        
        # Deduplication using deque (FIFO, not random removal)
        self.recent_handshakes: deque = deque(maxlen=200)
        self.handshake_lock = threading.Lock()

        # Threading & Queue with size limit
        self._event_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._cleanup_done = False

        # Session Stats (Thread-safe)
        self.session_lock = threading.Lock()
        self.session_handshakes = 0
        self.start_time = time.time()
        self.session_id = os.urandom(4).hex()
        
        # Periodic cache saving
        self._cache_save_timer: Optional[threading.Timer] = None
        self._cache_dirty = False
        
        # Register cleanup handler
        atexit.register(self._on_exit_cleanup)

    def _create_http_session(self) -> requests.Session:
        """Create HTTP session with retry logic"""
        session = requests.Session()
        
        # Retry strategy: 3 retries with exponential backoff
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session

    # ------------------------------------------------------------------------
    # Lifecycle Methods
    # ------------------------------------------------------------------------

    def on_loaded(self):
        """Called when plugin is loaded"""
        logger.info("Discord plugin loaded (v%s).", self.__version__)
        
        self.webhook_url = self.options.get("webhook_url", None)
        self.api_key = self.options.get("wigle_api_key", None)

        self._load_wigle_cache()

        if not self.webhook_url:
            logger.error("Discord plugin: Missing webhook_url in configuration.")
            return
        
        if not self.api_key:
            logger.warning("Discord plugin: Missing wigle_api_key - location lookups disabled.")

        # Start the background worker
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="DiscordWorker")
        self._worker_thread.start()
        
        # Start periodic cache saver
        self._schedule_cache_save()
        
        logger.info(f"Discord plugin: Worker thread started. Session ID: {self.session_id}")

    def on_unload(self, ui):
        """Called when plugin is unloaded"""
        logger.info("Discord plugin: Unloading...")
        self._on_exit_cleanup()

    def _on_exit_cleanup(self):
        """Cleanup resources - idempotent"""
        if self._cleanup_done:
            return
        
        self._cleanup_done = True
        logger.info("Discord plugin: Cleaning up...")
        
        # Cancel cache save timer
        if self._cache_save_timer:
            self._cache_save_timer.cancel()
        
        # Save cache one last time
        self._save_wigle_cache()
        
        # Stop worker thread gracefully
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            logger.debug("Waiting for worker thread to finish...")
            self._worker_thread.join(timeout=5.0)
            if self._worker_thread.is_alive():
                logger.warning("Worker thread did not finish in time")
        
        # Close HTTP session
        try:
            self.http_session.close()
        except Exception as e:
            logger.error(f"Error closing HTTP session: {e}")
        
        logger.info("Discord plugin: Cleanup complete.")

    # ------------------------------------------------------------------------
    # Event Handlers
    # ------------------------------------------------------------------------

    def on_ready(self, agent: Agent):
        """Called when Pwnagotchi is ready"""
        self.start_time = time.time()
        logger.info("Discord plugin: Pwnagotchi is ready.")
        
        # Get unit name safely
        unit_name = self._get_unit_name(agent)

        # Send online notification
        self._queue_notification(
            content="🟢 **Pwnagotchi is Online!**",
            embed={
                'title': f"{unit_name} is Ready",
                'description': f"Unit is ready and sniffing.\n**Plugin Session ID:** `{self.session_id}`",
                'color': 5763719,  # Green
                'timestamp': self._get_iso_timestamp()
            }
        )

        # Report previous session stats if available
        self._report_previous_session(agent, unit_name)

    def on_handshake(self, agent: Agent, filename: str, access_point: Dict[str, Any], 
                     client_station: Dict[str, Any]):
        """Called when a handshake is captured"""
        bssid = access_point.get("mac", "00:00:00:00:00:00")
        client_mac = client_station.get("mac", "00:00:00:00:00:00")
        handshake_key = (filename, bssid.lower(), client_mac.lower())

        # Thread-safe deduplication check
        with self.handshake_lock:
            if handshake_key in self.recent_handshakes:
                logger.debug(f"Duplicate handshake ignored: {filename}")
                return
            
            self.recent_handshakes.append(handshake_key)

        # Thread-safe counter increment
        with self.session_lock:
            self.session_handshakes += 1
            current_count = self.session_handshakes

        logger.info(f"New handshake captured: {filename} (Total: {current_count})")

        # Queue the handshake for processing
        try:
            self._event_queue.put_nowait({
                'type': 'handshake',
                'filename': filename,
                'access_point': access_point,
                'client_station': client_station,
                'session_count': current_count
            })
        except queue.Full:
            logger.error("Event queue is full! Dropping handshake notification.")

    # ------------------------------------------------------------------------
    # Worker Thread Logic
    # ------------------------------------------------------------------------

    def _worker_loop(self):
        """Main worker thread loop - processes queued events"""
        logger.debug("Worker thread started")
        
        while not self._stop_event.is_set():
            try:
                # Use shorter timeout when stopping to process remaining items quickly
                timeout = 0.1 if self._stop_event.is_set() else 1.0
                event = self._event_queue.get(timeout=timeout)
            except queue.Empty:
                continue

            try:
                event_type = event.get('type')
                
                if event_type == 'handshake':
                    self._process_handshake(event)
                elif event_type == 'notification':
                    self._send_discord_payload(
                        event['content'], 
                        event.get('embeds', [])
                    )
                else:
                    logger.warning(f"Unknown event type: {event_type}")
                
                # Rate limiting: sleep between Discord API calls
                if not self._stop_event.is_set():
                    time.sleep(WORKER_SLEEP_INTERVAL)
                    
            except Exception as e:
                logger.error(f"Error processing event: {e}", exc_info=True)
            finally:
                self._event_queue.task_done()
        
        # Process remaining items in queue during shutdown
        logger.debug("Processing remaining queue items...")
        while not self._event_queue.empty():
            try:
                event = self._event_queue.get_nowait()
                event_type = event.get('type')
                
                if event_type == 'handshake':
                    self._process_handshake(event)
                elif event_type == 'notification':
                    self._send_discord_payload(
                        event['content'], 
                        event.get('embeds', [])
                    )
                
                self._event_queue.task_done()
            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Error in shutdown processing: {e}")
        
        logger.debug("Worker thread finished")

    def _queue_notification(self, content: str, embed: Optional[Dict] = None):
        """Queue a simple notification to be sent to Discord"""
        try:
            payload = {
                'type': 'notification',
                'content': content,
                'embeds': [embed] if embed else []
            }
            self._event_queue.put_nowait(payload)
        except queue.Full:
            logger.error("Event queue is full! Dropping notification.")

    def _process_handshake(self, event: Dict[str, Any]):
        """Process a handshake event and send to Discord"""
        filename = event['filename']
        ap = event['access_point']
        client = event['client_station']
        session_count = event.get('session_count', 0)
        
        bssid = ap.get("mac", "Unknown")
        ap_name = ap.get('hostname', 'Unknown')
        client_mac = client.get('mac', 'Unknown')

        logger.info(f"Processing handshake for Discord: {ap_name} [{bssid}] -> {client_mac}")

        # Get location from WiGLE
        location = self._get_location_from_wigle(bssid)
        if location:
            loc_str = (
                f"**Lat:** {location.lat}, **Lon:** {location.lon}\n"
                f"[🗺️ View on Google Maps]"
                f"(https://www.google.com/maps/search/?api=1&query={location.lat},{location.lon})"
            )
        else:
            loc_str = "Location not available (not in WiGLE database)"

        # Build Discord embed
        embed = {
            'title': '🔐 New Handshake Captured!',
            'description': f"**Access Point:** {ap_name}\n**BSSID:** `{bssid}`",
            'fields': [
                {
                    'name': '📱 Client Station',
                    'value': f"`{client_mac}`",
                    'inline': True
                },
                {
                    'name': '📊 Channel',
                    'value': str(ap.get('channel', 'Unknown')),
                    'inline': True
                },
                {
                    'name': '🗂️ Handshake File',
                    'value': f"`{os.path.basename(filename)}`",
                    'inline': False
                },
                {
                    'name': '📍 Location',
                    'value': loc_str,
                    'inline': False
                },
            ],
            'footer': {
                'text': f"Session: {session_count} handshakes | ID: {self.session_id}"
            },
            'timestamp': self._get_iso_timestamp(),
            'color': 16776960  # Gold/Yellow
        }

        # Send to Discord with file attachment
        self._send_discord_payload(
            content=f"🤝 New handshake from **{ap_name}**",
            embeds=[embed],
            file_path=filename
        )

    # ------------------------------------------------------------------------
    # Discord API Methods
    # ------------------------------------------------------------------------

    def _send_discord_payload(self, content: str, embeds: List[Dict], 
                             file_path: Optional[str] = None):
        """Send payload to Discord webhook with optional file attachment"""
        if not self.webhook_url:
            logger.warning("No webhook URL configured, skipping Discord message")
            return

        payload_dict = {
            "content": content,
            "embeds": embeds
        }

        try:
            if file_path and os.path.exists(file_path):
                # Send with file attachment
                self._send_with_file(payload_dict, file_path)
            else:
                # Send JSON only
                self._send_json_only(payload_dict)
                
        except RequestException as e:
            logger.error(f"Discord API request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending to Discord: {e}", exc_info=True)

    def _send_with_file(self, payload_dict: Dict, file_path: str):
        """Send Discord message with file attachment"""
        try:
            filename = os.path.basename(file_path)
            logger.info(f"Sending Discord notification with file attachment: {filename}")
            
            with open(file_path, 'rb') as f:
                files = {
                    'file': (filename, f, 'application/octet-stream')
                }
                data = {
                    'payload_json': json.dumps(payload_dict)
                }
                
                response = self.http_session.post(
                    self.webhook_url,
                    files=files,
                    data=data,
                    timeout=DISCORD_TIMEOUT
                )
                
                self._handle_discord_response(response, with_file=True)
                
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            # Send without file
            self._send_json_only(payload_dict)
        except IOError as e:
            logger.error(f"Error reading file {file_path}: {e}")
            self._send_json_only(payload_dict)

    def _send_json_only(self, payload_dict: Dict):
        """Send Discord message without file attachment"""
        logger.info("Sending Discord notification (JSON only)")
        
        response = self.http_session.post(
            self.webhook_url,
            json=payload_dict,
            headers={'Content-Type': 'application/json'},
            timeout=DISCORD_QUICK_TIMEOUT
        )
        
        self._handle_discord_response(response, with_file=False)

    def _handle_discord_response(self, response: requests.Response, with_file: bool = False):
        """Handle Discord API response and log appropriately"""
        attachment_info = " (with file)" if with_file else ""
        
        if response.status_code == 204:
            # Success (no content)
            logger.info(f"✓ Discord notification sent successfully{attachment_info}")
        elif response.status_code == 200:
            # Success (with content)
            logger.info(f"✓ Discord notification sent successfully{attachment_info}")
        elif response.status_code == 429:
            # Rate limited
            try:
                data = response.json()
                retry_after = data.get('retry_after', 'unknown')
                logger.warning(f"Discord rate limit hit. Retry after: {retry_after}s")
            except:
                logger.warning("Discord rate limit hit (couldn't parse retry info)")
        else:
            # Other error
            logger.error(f"Discord API error: {response.status_code} - {response.text}")

    # ------------------------------------------------------------------------
    # WiGLE API Methods
    # ------------------------------------------------------------------------

    def _get_location_from_wigle(self, bssid: str) -> Optional[CachedLocation]:
        """Get location from WiGLE API with caching"""
        if not bssid:
            return None
        
        normalized_bssid = bssid.lower()

        # Check cache first (thread-safe)
        with self.cache_lock:
            if normalized_bssid in self.wigle_cache:
                cached = self.wigle_cache[normalized_bssid]
                
                # Check if expired
                if not cached.is_expired():
                    logger.debug(f"WiGLE cache hit for {normalized_bssid}")
                    return cached
                else:
                    logger.debug(f"WiGLE cache expired for {normalized_bssid}")
                    del self.wigle_cache[normalized_bssid]

        # API key required for lookup
        if not self.api_key:
            return None

        # Query WiGLE API
        logger.debug(f"Querying WiGLE API for {normalized_bssid}")
        location = self._query_wigle_api(normalized_bssid)
        
        if location:
            # Cache the result (thread-safe)
            with self.cache_lock:
                self.wigle_cache[normalized_bssid] = location
                self._cache_dirty = True
        
        return location

    def _query_wigle_api(self, bssid: str) -> Optional[CachedLocation]:
        """Query WiGLE API for network location"""
        headers = {'Authorization': f'Basic {self.api_key}'}
        params = {'netid': bssid}
        
        try:
            response = self.http_session.get(
                'https://api.wigle.net/api/v2/network/detail',
                headers=headers,
                params=params,
                timeout=WIGLE_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success') and data.get('results'):
                    result = data['results'][0]
                    lat = result.get('trilat', 'N/A')
                    lon = result.get('trilong', 'N/A')
                    
                    if lat != 'N/A' and lon != 'N/A':
                        logger.debug(f"WiGLE lookup successful for {bssid}")
                        return CachedLocation(
                            lat=str(lat),
                            lon=str(lon),
                            timestamp=time.time()
                        )
                    else:
                        logger.debug(f"WiGLE returned invalid coordinates for {bssid}")
                else:
                    logger.debug(f"WiGLE API returned no results for {bssid}")
            elif response.status_code == 404:
                logger.debug(f"BSSID {bssid} not found in WiGLE database")
            else:
                logger.warning(f"WiGLE API error: {response.status_code}")
                
        except RequestException as e:
            logger.error(f"WiGLE API request failed: {e}")
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error parsing WiGLE response: {e}")
        
        return None

    # ------------------------------------------------------------------------
    # Cache Management
    # ------------------------------------------------------------------------

    def _load_wigle_cache(self):
        """Load WiGLE cache from disk"""
        if not os.path.exists(CACHE_FILE):
            logger.debug("No existing cache file found")
            return
        
        try:
            with open(CACHE_FILE, "r") as f:
                raw_cache = json.load(f)
            
            # Convert to CachedLocation objects
            loaded_count = 0
            expired_count = 0
            
            with self.cache_lock:
                for bssid, data in raw_cache.items():
                    try:
                        cached_loc = CachedLocation.from_dict(data)
                        
                        # Skip expired entries
                        if cached_loc.is_expired():
                            expired_count += 1
                            continue
                        
                        self.wigle_cache[bssid] = cached_loc
                        loaded_count += 1
                        
                    except (KeyError, TypeError, ValueError) as e:
                        logger.warning(f"Skipping invalid cache entry for {bssid}: {e}")
            
            logger.info(f"Loaded {loaded_count} WiGLE cache entries ({expired_count} expired)")
            
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error loading cache file: {e}")
            self.wigle_cache = {}

    def _save_wigle_cache(self):
        """Save WiGLE cache to disk"""
        if not self._cache_dirty:
            logger.debug("Cache not dirty, skipping save")
            return
        
        try:
            with self.cache_lock:
                # Convert to serializable dict
                raw_cache = {
                    bssid: loc.to_dict()
                    for bssid, loc in self.wigle_cache.items()
                    if not loc.is_expired()  # Don't save expired entries
                }
                
                self._cache_dirty = False
            
            # Write to disk
            with open(CACHE_FILE, "w") as f:
                json.dump(raw_cache, f, indent=2)
            
            logger.info(f"Saved {len(raw_cache)} WiGLE cache entries")
            
        except (IOError, TypeError) as e:
            logger.error(f"Error saving cache file: {e}")

    def _schedule_cache_save(self):
        """Schedule periodic cache saves (every 5 minutes)"""
        if self._stop_event.is_set():
            return
        
        self._save_wigle_cache()
        
        # Schedule next save
        self._cache_save_timer = threading.Timer(300.0, self._schedule_cache_save)
        self._cache_save_timer.daemon = True
        self._cache_save_timer.start()

    # ------------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------------

    def _get_unit_name(self, agent: Agent) -> str:
        """Safely get unit name from agent config"""
        try:
            config = agent.config()
            return config['main']['name']
        except (KeyError, AttributeError, TypeError):
            return "Pwnagotchi"

    def _report_previous_session(self, agent: Agent, unit_name: str):
        """Report stats from previous session if available"""
        if not hasattr(agent, 'last_session') or not agent.last_session:
            return
        
        last = agent.last_session
        
        # Check if session had meaningful duration
        duration_str = str(getattr(last, 'duration', '0:00:00'))
        if duration_str == "0:00:00":
            logger.debug("Previous session had no duration, skipping report")
            return
        
        # Gather stats
        handshakes = getattr(last, 'handshakes', 0)
        epochs = getattr(last, 'epochs', 0)
        deauths = getattr(last, 'deauths', 0)
        
        logger.info(f"Reporting previous session: {handshakes} handshakes in {duration_str}")
        
        # Build embed
        fields = [
            {'name': '🤝 Handshakes', 'value': str(handshakes), 'inline': True},
            {'name': '⏱️ Duration', 'value': duration_str, 'inline': True},
            {'name': '🔄 Epochs', 'value': str(epochs), 'inline': True},
        ]
        
        if deauths > 0:
            fields.append({'name': '💥 Deauths', 'value': str(deauths), 'inline': True})
        
        self._queue_notification(
            content="📋 **Previous Session Report**",
            embed={
                'title': f'{unit_name} - Session Summary',
                'description': 'Statistics from the last session before restart/mode switch',
                'fields': fields,
                'color': 12370112,  # Orange
                'timestamp': self._get_iso_timestamp()
            }
        )

    @staticmethod
    def _get_iso_timestamp() -> str:
        """Get current timestamp in ISO 8601 format for Discord embeds"""
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
