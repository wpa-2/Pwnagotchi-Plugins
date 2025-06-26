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

# This is a standard way to get type hints for the Session object without causing import errors
if TYPE_CHECKING:
    from pwnagotchi.ui.agent import Session


class Discord(plugins.Plugin):
    """
    Discord plugin for Pwnagotchi.
    Sends handshakes to Discord and a summary of the *previous* session on startup.
    """

    __author__ = "WPA2 & User Collaboration"
    __version__ = '3.2.0'
    __license__ = 'GPL3'
    __description__ = 'Sends handshakes to Discord and a summary of the previous session on startup.'

    def __init__(self):
        super().__init__()
        self.webhook_url: Optional[str] = None
        self.api_key: Optional[str] = None
        self.http_session = requests.Session()
        self.wigle_cache = {}
        # Path to a file to track which sessions have been reported
        self.reported_session_file = '/var/tmp/pwnagotchi_discord_plugin.sent'

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

    def on_ready(self, agent: Agent):
        """
        Hook is called when the Pwnagotchi is ready and has loaded its data.
        We use this to send the summary of the *last* session.
        """
        logging.info("Discord plugin: Pwnagotchi is ready. Checking for last session summary to send.")

        last_session = agent.last_session

        # CORRECTED CHECK: Ensure the session object exists and ran for a meaningful amount of time.
        if not last_session or last_session.duration < 1:
            logging.info("Discord plugin: No valid previous session data found to summarize.")
            return

        # Use the session's end time as its unique identifier.
        session_unique_id = last_session.ended_at.isoformat() if last_session.ended_at else None
        if not session_unique_id:
            logging.warning("Discord plugin: Last session has no end time, cannot determine uniqueness.")
            return

        # Check if we have already reported this session
        try:
            with open(self.reported_session_file, 'r') as f:
                last_reported_id = f.read().strip()
            if last_reported_id == session_unique_id:
                logging.info(f"Discord plugin: Summary for session ending at {session_unique_id} has already been sent.")
                return
        except FileNotFoundError:
            pass # File doesn't exist, so we've never sent a summary before.
        except Exception as e:
            logging.error(f"Discord plugin: Error reading reported session file: {e}")

        logging.info(f"Discord plugin: Sending summary for previous session ending at {session_unique_id}")

        summary_embed = {
            'title': '📊 Previous Session Summary',
            'description': f"Report from **{pwnagotchi.name()}**'s last session.",
            'fields': [
                {'name': '🏁 Duration', 'value': str(last_session.duration), 'inline': True},
                {'name': '🤝 Handshakes', 'value': str(last_session.handshakes), 'inline': True},
                {'name': '💪 Peers', 'value': str(last_session.peers), 'inline': True},
            ],
            'timestamp': last_session.ended_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            'color': 0xFFC300 # Gold
        }
        self.send_discord_notification(
            content=f"Pwnagotchi **{pwnagotchi.name()}** has booted up.",
            embed_data=[summary_embed]
        )

        # After sending, save the session's unique ID to the file to prevent re-sending
        try:
            with open(self.reported_session_file, 'w') as f:
                f.write(session_unique_id)
        except Exception as e:
            logging.error(f"Discord plugin: Error writing to reported session file: {e}")

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