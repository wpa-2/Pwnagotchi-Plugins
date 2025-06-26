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
    __version__ = '2.4.0'
    __license__ = 'GPL3'
    __description__ = 'Sends Pwnagotchi handshakes and session summaries to Discord, with location data from WiGLE.'

    def __init__(self):
        super().__init__()
        self.webhook_url: Optional[str] = None
        self.api_key: Optional[str] = None
        self.http_session = requests.Session()
        self.wigle_cache = {}
        # Use a flag to ensure the final summary is sent only once
        self.summary_sent = False
        # Store session data when the session stops, to be used on unload
        self.final_session_data = None

    def on_loaded(self):
        logging.info('Discord plugin loaded.')
        self.webhook_url = self.options.get('webhook_url')
        self.api_key = self.options.get('wigle_api_key')

        if self.webhook_url:
            logging.info("Discord plugin: Webhook URL set.")
        else:
            logging.error("Discord plugin: Webhook URL not provided. Plugin will be disabled.")
        
        if self.api_key:
            logging.info("Discord plugin: WiGLE API key set.")
        else:
            logging.warning("Discord plugin: WiGLE API key not provided. Location services will be disabled.")

    def send_discord_notification(
        self,
        content: str,
        embed_data: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        if not self.webhook_url:
            # We log this in on_loaded, so no need to spam logs here.
            return

        data = {"content": content, "embeds": embed_data or []}
        try:
            # For shutdown, we don't have time for complex retries. Send and hope for the best.
            response = self.http_session.post(self.webhook_url, json=data, timeout=10)
            if response.status_code in [200, 204]:
                logging.info('Discord plugin: Notification sent successfully.')
            else:
                logging.error(f"Discord plugin: Failed to send notification. Status: {response.status_code} - {response.text}")
        except RequestException as e:
            logging.error(f"Discord plugin: Error sending notification: {e}")

    def _get_location_from_wigle(self, bssid: Optional[str]) -> Optional[Dict[str, Any]]:
        # This function remains the same as the previous working version.
        if not bssid or not self.api_key:
            return None
        if bssid in self.wigle_cache:
            return self.wigle_cache[bssid]

        headers = {'Authorization': f'Basic {self.api_key}'}
        params = {'netid': bssid}
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
            self.wigle_cache[bssid] = None
        except RequestException as e:
            logging.error(f'[Discord plugin] Network error fetching WiGLE data: {e}')
        return None

    def on_handshake(self, agent: Agent, filename: str, access_point: Dict[str, Any], client_station: Dict[str, Any]) -> None:
        bssid = access_point.get("mac")
        location = self._get_location_from_wigle(bssid)

        if location:
            lat, lon = location['lat'], location['lon']
            location_info = f"[{lat}, {lon}](https://www.google.com/maps/search/?api=1&query={lat},{lon})"
        else:
            location_info = "Location not available."

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

    def on_session_stop(self, agent: Agent, session: "Session") -> None:
        # This hook is called when a pwnagotchi session ends.
        # We just store the data here. The sending is done in on_unload.
        logging.info("Discord plugin: Session stopped. Storing final session data for summary.")
        self.final_session_data = session

    def on_unload(self, ui: "Session") -> None:
        # This hook is called when the plugin is about to be unloaded (e.g., on shutdown)
        logging.info("Discord plugin: Unload sequence initiated.")
        if self.summary_sent:
            return

        session_to_send = self.final_session_data or ui.get_session()
        
        if session_to_send:
            logging.info("Discord plugin: Sending session summary on unload.")
            summary_embed = {
                'title': '📊 Session Summary',
                'description': f"Pwnagotchi session on **{pwnagotchi.name()}** has ended.",
                'fields': [
                    {'name': '🏁 Session Duration', 'value': str(session_to_send.get('duration', 'N/A')), 'inline': True},
                    {'name': '🤝 Handshakes', 'value': str(session_to_send.get('handshakes', 'N/A')), 'inline': True},
                    {'name': '💪 Peers', 'value': str(session_to_send.get('peers', 'N/A')), 'inline': True},
                ],
                'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                'color': 0xFFC300
            }
            self.send_discord_notification(
                content=f"Pwnagotchi **{pwnagotchi.name()}** is going to sleep.",
                embed_data=[summary_embed]
            )
            self.summary_sent = True