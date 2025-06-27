import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests
from requests import RequestException

import pwnagotchi
import pwnagotchi.plugins as plugins
from pwnagotchi.agent import Agent

# If TYPE_CHECKING is needed, uncomment:
# from typing import TYPE_CHECKING
# if TYPE_CHECKING:
#     from pwnagotchi.ui.agent import Session

# ----------------------------------------------------------------------------
# File/directory constants for logs and cache
# ----------------------------------------------------------------------------
LOG_DIR = "/etc/pwnagotchi/log"
LOG_FILE = os.path.join(LOG_DIR, "discord_plugin.log")

# The updated location for the WiGLE cache
CACHE_FILE = "/home/pi/handshakes/discord_wigle_cache.json"

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)

# ----------------------------------------------------------------------------
# Setup dedicated logger for this plugin
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
    """
    Discord plugin for Pwnagotchi.
    Sends handshakes and session summaries to Discord with location data from WiGLE.
    Persists a local cache of WiGLE lookups in /home/pi/handshakes/discord_wigle_cache.json.
    """

    __author__ = "WPA2"
    __version__ = '2.3.0'
    __license__ = 'GPL3'
    __description__ = (
        'Sends Pwnagotchi handshakes and session summaries to Discord, '
        'with location data from WiGLE. Persists a local cache of WiGLE lookups.'
    )

    def __init__(self):
        super().__init__()
        self.webhook_url: Optional[str] = None
        self.session_notified: bool = False
        self.api_key: Optional[str] = None
        self.http_session = requests.Session()
        self.wigle_cache: Dict[str, Dict[str, str]] = {}  # {bssid: {"lat": ..., "lon": ...}}

        # Track recently processed handshakes to detect duplicates
        self.recent_handshakes = set()
        self.recent_handshakes_limit = 200

    def on_loaded(self):
        logger.info("Discord plugin loaded.")
        self.webhook_url = self.options.get("webhook_url", None)
        self.api_key = self.options.get("wigle_api_key", None)

        self.log_config_status(self.webhook_url, "Webhook URL")
        self.log_config_status(self.api_key, "WiGLE API key")

        # Load existing WiGLE cache from disk
        self._load_wigle_cache()

        if not self.webhook_url or not self.api_key:
            logger.error(
                "Discord plugin: Missing essential configurations (webhook_url or wigle_api_key). "
                "Plugin may not function correctly."
            )

    def on_unload(self, ui):
        """
        Called when the plugin is unloaded. We'll save our WiGLE cache here.
        """
        logger.info("Discord plugin: on_unload called. Saving WiGLE cache to disk.")
        self._save_wigle_cache()

    def log_config_status(self, key: Optional[str], name: str) -> None:
        if not key:
            logger.error(f"Discord plugin: {name} not provided in config.")
        else:
            logger.info(f"Discord plugin: {name} set.")

    def send_discord_notification(
        self,
        content: str,
        embed_data: Optional[List[Dict[str, Any]]] = None,
        files: Optional[Dict[str, Any]] = None
    ) -> None:
        if not self.webhook_url:
            logger.error("Discord plugin: Webhook URL not set. Cannot send notification.")
            return

        data = {
            "content": content,
            "embeds": embed_data or []
        }

        max_retries = 3
        backoff_factor = 2
        for attempt in range(1, max_retries + 1):
            try:
                if files:
                    payload = {"payload_json": json.dumps(data)}
                    response = self.http_session.post(
                        self.webhook_url,
                        data=payload,
                        files=files,
                        timeout=10
                    )
                else:
                    headers = {'Content-Type': 'application/json'}
                    response = self.http_session.post(
                        self.webhook_url,
                        json=data,
                        headers=headers,
                        timeout=10
                    )

                # Check response
                if response.status_code in [200, 204]:
                    logger.info('Discord plugin: Notification sent successfully.')
                    break
                elif response.status_code == 429:
                    retry_after = response.json().get('retry_after', 1)
                    logger.warning(
                        f"Discord plugin: Rate limited by Discord. Response 429. "
                        f"Retrying after {retry_after} seconds."
                    )
                    time.sleep(retry_after)
                else:
                    logger.error(
                        f"Discord plugin: Failed to send notification. "
                        f"Response: {response.status_code} - {response.text}"
                    )
                    break
            except RequestException as e:
                logger.exception(
                    f"Discord plugin: Error sending notification on attempt {attempt}: {e}"
                )
                if attempt < max_retries:
                    sleep_time = backoff_factor ** attempt
                    logger.info(f"Discord plugin: Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error("Discord plugin: Max retries reached. Giving up.")

    def _get_location_from_wigle(self, bssid: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Retrieves location data from WiGLE for a given BSSID. Uses a persistent (disk-based) cache
        to avoid repeated lookups across reboots. If bssid is found in self.wigle_cache, returns it
        immediately. Otherwise, queries WiGLE, stores the new data, and returns it.
        """
        if not bssid:
            logger.warning("[Discord plugin] Missing BSSID. Skipping location retrieval.")
            return None

        # Normalize BSSID (lowercase)
        normalized_bssid = bssid.lower()

        # Check the in-memory cache
        if normalized_bssid in self.wigle_cache:
            logger.debug(f"[Discord plugin] Using cached location for BSSID {normalized_bssid}")
            return self.wigle_cache[normalized_bssid]

        if not self.api_key:
            logger.error("Discord plugin: WiGLE API key not set. Cannot fetch new location data.")
            return None

        logger.debug(f"[Discord plugin] No cache entry for {normalized_bssid}; fetching from WiGLE...")
        headers = {'Authorization': f'Basic {self.api_key}'}
        params = {'netid': normalized_bssid}

        try:
            response = self.http_session.get(
                'https://api.wigle.net/api/v2/network/detail',
                headers=headers,
                params=params,
                timeout=10
            )
            logger.debug(f"[Discord plugin] WiGLE API request for {normalized_bssid}, "
                         f"response code: {response.status_code}")

            if response.status_code == 429:
                retry_after = response.json().get('retry_after', 10)
                logger.warning(
                    f"[Discord plugin] WiGLE rate-limited the request. Retrying after {retry_after} seconds."
                )
                time.sleep(retry_after)
                # Recursively retry once (mind infinite loops in real usage)
                return self._get_location_from_wigle(bssid)

            if response.status_code == 200:
                data = response.json()
                logger.debug(f"[Discord plugin] WiGLE response data: {data}")

                if data.get('success') and data.get('results'):
                    result = data['results'][0]
                    location = {
                        'lat': result.get('trilat', 'N/A'),
                        'lon': result.get('trilong', 'N/A')
                    }
                    self.wigle_cache[normalized_bssid] = location
                    logger.debug(
                        f"[Discord plugin] Caching location for {normalized_bssid}: {location}"
                    )

                    # Save updated cache to disk immediately
                    self._save_wigle_cache()

                    return location
                else:
                    logger.warning(
                        f'[Discord plugin] No location data found for {normalized_bssid}. '
                        f"Response success={data.get('success')}, results={data.get('results')}"
                    )
            else:
                logger.error(
                    f"[Discord plugin] WiGLE lookup failed for {normalized_bssid}. "
                    f"HTTP {response.status_code}, text: {response.text}"
                )
        except RequestException as e:
            logger.error(f'[Discord plugin] Network error fetching WiGLE data for {normalized_bssid}: {e}')

        return None

    def on_handshake(
        self,
        agent: Agent,
        filename: str,
        access_point: Dict[str, Any],
        client_station: Dict[str, Any]
    ) -> None:
        """
        Triggered whenever Pwnagotchi captures a new handshake.
        """
        logger.info("Discord plugin: Handshake captured, preparing to send to Discord.")

        # Build a unique key to detect duplicates (in this session)
        bssid = access_point.get("mac", "00:00:00:00:00:00")
        client_mac = client_station.get("mac", "00:00:00:00:00:00")
        handshake_key = (filename, bssid.lower(), client_mac.lower())

        if handshake_key in self.recent_handshakes:
            logger.warning(
                f"Discord plugin: Duplicate handshake event detected for {handshake_key}. "
                f"Skipping second notification."
            )
            return
        else:
            self.recent_handshakes.add(handshake_key)
            # Trim if set gets too large
            if len(self.recent_handshakes) > self.recent_handshakes_limit:
                self.recent_handshakes.pop()

        # Look up location data
        location = self._get_location_from_wigle(bssid)

        # Build the location info text
        if location:
            location_info = (
                f"Latitude: {location['lat']}, Longitude: {location['lon']}\n"
                f"[View on Map](https://www.google.com/maps/search/?api=1&query={location['lat']},{location['lon']})"
            )
        else:
            location_info = "Location not available."

        # Build embed data
        embed_data = [
            {
                'title': '🔐 New Handshake Captured!',
                'description': (
                    f"**Access Point:** {access_point.get('hostname', 'Unknown')}\n"
                    f"**Client Station:** {client_station.get('mac', 'Unknown')}"
                ),
                'fields': [
                    {'name': '🗂 Handshake File', 'value': filename, 'inline': False},
                    {'name': '📍 Location', 'value': location_info, 'inline': False},
                ],
                'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        ]

        # Send notification to Discord
        logger.debug(f"Discord plugin: Sending handshake notification with embed data: {embed_data}")
        self.send_discord_notification(
            f"🤝 New handshake from {access_point.get('hostname', 'Unknown')}",
            embed_data=embed_data
        )

    def on_session_stop(self, agent: Agent, session: Any) -> None:
        """
        Triggered when a Pwnagotchi session stops.
        """
        logger.info("Discord plugin: Session stopped. Resetting notification flags and handshake cache.")
        self.session_notified = False
        self.recent_handshakes.clear()

        # Optionally save the cache again
        self._save_wigle_cache()

    # ------------------------------------------------------------------------
    # Helpers for loading/saving the WiGLE cache to/from disk
    # ------------------------------------------------------------------------
    def _load_wigle_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    self.wigle_cache = json.load(f)
                logger.info(
                    f"Discord plugin: Loaded WiGLE cache from {CACHE_FILE}, "
                    f"{len(self.wigle_cache)} entries."
                )
            except Exception as e:
                logger.error(
                    f"Discord plugin: Error reading WiGLE cache from {CACHE_FILE}: {e}"
                )
        else:
            logger.info(
                f"Discord plugin: No existing WiGLE cache file at {CACHE_FILE}; starting fresh."
            )

    def _save_wigle_cache(self):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(self.wigle_cache, f)
            logger.info(
                f"Discord plugin: Saved WiGLE cache to {CACHE_FILE}, "
                f"{len(self.wigle_cache)} entries."
            )
        except Exception as e:
            logger.error(f"Discord plugin: Error saving WiGLE cache to {CACHE_FILE}: {e}")
