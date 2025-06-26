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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pwnagotchi.ui.agent import Session


class Discord(plugins.Plugin):
    """
    Discord plugin for Pwnagotchi.
    Sends handshakes and session summaries to Discord with location data from WiGLE.
    """

    __author__ = "WPA2"
    __version__ = '2.3.0'
    __license__ = 'GPL3'
    __description__ = 'Sends Pwnagotchi handshakes and session summaries to Discord, with location data from WiGLE.'

    def __init__(self):
        super().__init__()
        self.webhook_url: Optional[str] = None
        self.session_notified: bool = True  # Start as True to avoid sending summary on first load
        self.api_key: Optional[str] = None
        self.http_session = requests.Session()
        self.wigle_cache = {}  # Simple dictionary cache for BSSID lookups

    def on_loaded(self):
        logging.info('Discord plugin loaded.')
        self.webhook_url = self.options.get('webhook_url', None)
        self.api_key = self.options.get('wigle_api_key', None)

        self.log_config_status(self.webhook_url, "Webhook URL")
        self.log_config_status(self.api_key, "WiGLE API key")

        if not self.webhook_url:
            logging.error("Discord plugin: Webhook URL not provided. Plugin will be disabled.")
        if not self.api_key:
            logging.error("Discord plugin: WiGLE API key not provided. Location services will be disabled.")
            
    def on_session_start(self, agent: Agent, session: "Session") -> None:
        self.session_notified = False

    def log_config_status(self, key: Optional[str], name: str) -> None:
        if not key:
            logging.error(f"Discord plugin: {name} not provided in config.")
        else:
            logging.info(f"Discord plugin: {name} set.")

    def send_discord_notification(
        self,
        content: str,
        embed_data: Optional[List[Dict[str, Any]]] = None,
        files: Optional[Dict[str, Any]] = None
    ) -> None:
        if not self.webhook_url:
            logging.error("Discord plugin: Webhook URL not set. Cannot send notification.")
            return

        data = {"content": content, "embeds": embed_data or []}
        max_retries = 3
        backoff_factor = 2

        for attempt in range(max_retries):
            try:
                if files:
                    payload = {"payload_json": json.dumps(data)}
                    response = self.http_session.post(self.webhook_url, data=payload, files=files, timeout=10)
                else:
                    headers = {'Content-Type': 'application/json'}
                    response = self.http_session.post(self.webhook_url, json=data, headers=headers, timeout=10)

                if response.status_code in [200, 204]:
                    logging.info('Discord plugin: Notification sent successfully.')
                    return
                elif response.status_code == 429:
                    retry_after = response.json().get('retry_after', 1)
                    logging.warning(f"Discord plugin: Rate limited. Retrying after {retry_after} seconds.")
                    time.sleep(retry_after)
                else:
                    logging.error(f"Discord plugin: Failed to send notification. Status: {response.status_code} - {response.text}")
                    return
            except RequestException as e:
                logging.exception(f"Discord plugin: Error sending notification on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    sleep_time = backoff_factor ** attempt
                    logging.info(f"Discord plugin: Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logging.error("Discord plugin: Max retries reached. Giving up.")
    
    def _get_location_from_wigle(self, bssid: Optional[str]) -> Optional[Dict[str, Any]]:
        if not bssid:
            logging.warning("[Discord plugin] Missing BSSID. Skipping location retrieval.")
            return None
        if not self.api_key:
            return None

        if bssid in self.wigle_cache:
            logging.info(f"[Discord plugin] Using cached location for BSSID {bssid}")
            return self.wigle_cache[bssid]

        headers = {'Authorization': f'Basic {self.api_key}'}
        params = {'netid': bssid}
        max_retries = 3

        for attempt in range(max_retries):
            try:
                response = self.http_session.get('https://api.wigle.net/api/v2/network/detail', headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success') and data.get('results'):
                        result = data['results'][0]
                        location = {'lat': result.get('trilat'), 'lon': result.get('trilong')}
                        if location['lat'] and location['lon']:
                            self.wigle_cache[bssid] = location
                            return location
                    self.wigle_cache[bssid] = None # Cache failure to avoid retrying
                    return None
                elif response.status_code == 429:
                    retry_after = response.json().get('retry_after', 10)
                    logging.warning(f"WiGLE API rate limited. Retrying after {retry_after} seconds.")
                    time.sleep(retry_after)
                else:
                    logging.error(f"[Discord plugin] WiGLE API returned status {response.status_code} for BSSID {bssid}")
                    return None
            except RequestException as e:
                logging.error(f'[Discord plugin] Network error fetching WiGLE data for BSSID {bssid}: {e}')
                if attempt < max_retries - 1:
                    time.sleep(backoff_factor ** attempt)
                else:
                    logging.error("[Discord plugin] Max retries reached for WiGLE API.")
        return None

    def on_handshake(
        self,
        agent: Agent,
        filename: str,
        access_point: Dict[str, Any],
        client_station: Dict[str, Any]
    ) -> None:
        logging.info(f"Discord plugin: Handshake captured for {access_point.get('hostname', 'Unknown')}")
        bssid = access_point.get("mac")
        location = self._get_location_from_wigle(bssid)

        if location and location.get('lat') and location.get('lon'):
            lat, lon = location['lat'], location['lon']
            location_info = (f"Latitude: {lat}, Longitude: {lon}\n"
                             f"[View on Map](https://www.google.com/maps/search/?api=1&query={lat},{lon})")
        else:
            location_info = "Location not available."

        embed_data = [{
            'title': '🔐 New Handshake Captured!',
            'description': f"**Access Point:** {access_point.get('hostname', 'Unknown')} (`{bssid}`)",
            'fields': [
                {'name': 'Client Station', 'value': f"`{client_station.get('mac', 'Unknown')}`", 'inline': True},
                {'name': 'Handshake File', 'value': os.path.basename(filename), 'inline': True},
                {'name': '📍 Location', 'value': location_info, 'inline': False},
            ],
            'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            'color': 0x00FF00 # Green for success
        }]
        self.send_discord_notification(f"🤝 New handshake from {access_point.get('hostname', 'Unknown')}", embed_data=embed_data)

    def on_session_stop(self, agent: Agent, session: "Session") -> None:
        if self.session_notified or not self.webhook_url:
            return

        logging.info("Discord plugin: Session stopped. Sending summary.")
        summary_embed = {
            'title': '📊 Session Summary',
            'description': f"Pwnagotchi session on **{pwnagotchi.name()}** has ended.",
            'fields': [
                {'name': '🏁 Session Duration', 'value': str(session['duration']), 'inline': True},
                {'name': '🤝 Handshakes', 'value': str(session['handshakes']), 'inline': True},
                {'name': '💪 Peers', 'value': str(session['peers']), 'inline': True},
            ],
            'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            'color': 0xFFC300 # Gold
        }
        self.send_discord_notification(
            content=f"Pwnagotchi **{pwnagotchi.name()}** is going to sleep.",
            embed_data=[summary_embed]
        )
        self.session_notified = True

    def on_unload(self, ui: "Session") -> None:
        # A failsafe to send the summary if the plugin is unloaded manually
        self.on_session_stop(None, ui.get_session())