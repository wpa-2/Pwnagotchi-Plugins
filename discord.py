import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from requests import RequestException

import pwnagotchi
import pwnagotchi.plugins as plugins
from pwnagotchi.agent import Agent
from typing import TYPE_CHECKING

# This is a standard way to get type hints for the Session object without causing import errors
if TYPE_CHECKING:
    from pwnagotchi.ui.agent import Session


class Discord(plugins.Plugin):
    """
    Discord plugin for Pwnagotchi.
    Sends handshake notifications to Discord with location data from WiGLE.
    """

    __author__ = "WPA2"
    __version__ = '2.2.4'
    __license__ = 'GPL3'
    __description__ = 'Sends Pwnagotchi handshakes to Discord, with location data from WiGLE.'

    def __init__(self):
        super().__init__()
        self.webhook_url: Optional[str] = None
        self.api_key: Optional[str] = None
        self.http_session = requests.Session()
        self.wigle_cache = {}

    def on_loaded(self):
        logging.info('Discord plugin loaded.')
        self.webhook_url = self.options.get('webhook_url')
        self.api_key = self.options.get('wigle_api_key')

        if self.webhook_url:
            logging.info("Discord plugin: Webhook URL set.")
        else:
            logging.error("Discord plugin: Webhook URL not provided. Plugin will not be able to send messages.")

        if self.api_key:
            logging.info("Discord plugin: WiGLE API key set.")
        else:
            logging.warning("Discord plugin: WiGLE API key not provided. Location services will be disabled.")

    def send_discord_notification(self, content: str, embed_data: Optional[List[Dict[str, Any]]] = None) -> None:
        if not self.webhook_url:
            return

        data = {"content": content, "embeds": embed_data or []}
        try:
            response = self.http_session.post(self.webhook_url, json=data, timeout=15)
            if response.status_code in [200, 204]:
                logging.info('Discord plugin: Notification sent successfully.')
            else:
                logging.error(f"Discord plugin: Failed to send notification. Status: {response.status_code} - {response.text}")
        except RequestException as e:
            logging.error(f"Discord plugin: Error sending notification: {e}")

    def _get_location_from_wigle(self, bssid: Optional[str]) -> Optional[Dict[str, Any]]:
        if not bssid or not self.api_key: return None
        if bssid in self.wigle_cache: return self.wigle_cache[bssid]

        try:
            response = self.http_session.get(f'https://api.wigle.net/api/v2/network/detail?netid={bssid}', headers={'Authorization': f'Basic {self.api_key}'}, timeout=10)
            if response.status_code == 200 and response.json().get('success'):
                results = response.json().get('results', [])
                if results:
                    result = results[0]
                    location = {'lat': result.get('trilat'), 'lon': result.get('trilong')}
                    if location['lat'] and location['lon']:
                        self.wigle_cache[bssid] = location
                        return location
            self.wigle_cache[bssid] = None
        except Exception as e:
            logging.error(f'[Discord plugin] Error fetching WiGLE data: {e}')
        return None

    def on_handshake(self, agent: Agent, filename: str, access_point: Dict[str, Any], client_station: Dict[str, Any]) -> None:
        bssid = access_point.get("mac")
        location = self._get_location_from_wigle(bssid)
        location_info = f"[{location['lat']}, {location['lon']}](https://www.google.com/maps/search/?api=1&query={location['lat']},{location['lon']})" if location else "Location not available."

        embed_data = [{
            'title': '🔐 New Handshake Captured!',
            'description': f"**Access Point:** {access_point.get('hostname', 'Unknown')} (`{bssid}`)",
            'fields': [
                {'name': 'Client Station', 'value': f"`{client_station.get('mac', 'Unknown')}`", 'inline': True},
                {'name': 'Handshake File', 'value': f"`{os.path.basename(filename)}`", 'inline': True},
                {'name': '📍 Location', 'value': location_info, 'inline': False},
            ],
            'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            'color': 0x00FF00
        }]
        self.send_discord_notification(f"🤝 New handshake from {access_point.get('hostname', 'Unknown')}", embed_data=embed_data)