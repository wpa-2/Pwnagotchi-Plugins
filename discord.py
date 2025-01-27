import json
import logging
import os
import tempfile
import time
from typing import Any, Dict, List, Optional

import requests
from requests import RequestException

import pwnagotchi
import pwnagotchi.plugins as plugins
from pwnagotchi.agent import Agent  # Correctly import Agent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pwnagotchi.ui.agent import Session  # Import Session only for type checking if it exists


class Discord(plugins.Plugin):
    """
    Discord plugin for Pwnagotchi.
    Sends handshakes and session summaries to Discord with location data from WiGLE.
    """

    __author__ = "WPA2"
    __version__ = '2.2.2'
    __license__ = 'GPL3'
    __description__ = 'Sends Pwnagotchi handshakes and session summaries to Discord, with location data from WiGLE.'

    def __init__(self):
        super().__init__()  # Initialize the base Plugin class
        self.webhook_url: Optional[str] = None
        self.session_notified: bool = False
        self.api_key: Optional[str] = None  # WiGLE API key
        self.http_session = requests.Session()  # Initialize a session

    def on_loaded(self):
        """
        Triggered when the plugin is loaded.
        Initializes configuration options and validates essential settings.
        """
        logging.info('Discord plugin loaded.')
        self.webhook_url = self.options.get('webhook_url', None)
        self.api_key = self.options.get('wigle_api_key', None)

        self.log_config_status(self.webhook_url, "Webhook URL")
        self.log_config_status(self.api_key, "WiGLE API key")

        if not self.webhook_url or not self.api_key:
            logging.error("Discord plugin: Missing essential configurations. Plugin will not function correctly.")

    def log_config_status(self, key: Optional[str], name: str) -> None:
        """
        Logs the status of a configuration option.

        :param key: The configuration value to check.
        :param name: The name of the configuration option.
        """
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
        """
        Sends a notification to Discord via the configured webhook.

        :param content: The main content of the message.
        :param embed_data: A list of embed objects for rich formatting.
        :param files: A dictionary of files to send with the message.
        """
        if not self.webhook_url:
            logging.error("Discord plugin: Webhook URL not set. Cannot send notification.")
            return

        data = {
            "content": content,
            "embeds": embed_data or []
        }

        headers = {'Content-Type': 'application/json'}

        max_retries = 3
        backoff_factor = 2
        for attempt in range(1, max_retries + 1):
            try:
                if files:
                    # When sending files, payload_json should be sent as data
                    response = self.http_session.post(
                        self.webhook_url,
                        data={"payload_json": json.dumps(data)},
                        files=files,
                        headers=headers,
                        timeout=10
                    )
                else:
                    response = self.http_session.post(
                        self.webhook_url,
                        json=data,
                        headers=headers,
                        timeout=10
                    )

                if response.status_code in [200, 204]:
                    logging.info('Discord plugin: Notification sent successfully.')
                    break
                elif response.status_code == 429:
                    retry_after = response.json().get('retry_after', 1)
                    logging.warning(f"Discord plugin: Rate limited. Retrying after {retry_after} seconds.")
                    time.sleep(retry_after)
                else:
                    logging.error(
                        f"Discord plugin: Failed to send notification. Response: {response.status_code} - {response.text}"
                    )
                    break
            except RequestException as e:
                logging.exception(f"Discord plugin: Error sending notification on attempt {attempt}: {e}")
                if attempt < max_retries:
                    sleep_time = backoff_factor ** attempt
                    logging.info(f"Discord plugin: Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logging.error("Discord plugin: Max retries reached. Giving up.")

    def on_handshake(
        self,
        agent: Agent,
        filename: str,
        access_point: Dict[str, Any],
        client_station: Dict[str, Any]
    ) -> None:
        """
        Triggered when a new handshake is captured.
        Sends a Discord notification with handshake details and location.

        :param agent: The Pwnagotchi agent.
        :param filename: The filename of the captured handshake.
        :param access_point: Information about the access point.
        :param client_station: Information about the client station.
        """
        logging.info("Discord plugin: Handshake captured.")

        # Fetch the location
        bssid = access_point.get("mac")
        location = self._get_location_from_wigle(bssid)
        if location and 'lat' in location and 'lon' in location:
            location_link = f"https://www.google.com/maps/search/?api=1&query={location['lat']},{location['lon']}"
            location_info = f"Latitude: {location['lat']}, Longitude: {location['lon']}\n[View on Map]({location_link})"
        else:
            location_info = "Location not available."

            if bssid:
                logging.warning(f"[Discord plugin] No location data found for BSSID: {bssid}.")
            else:
                logging.warning("[Discord plugin] Missing BSSID. Cannot retrieve location data.")

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
        self.send_discord_notification(
            f"🤝 New handshake from {access_point.get('hostname', 'Unknown')}",
            embed_data=embed_data
        )

    def _get_location_from_wigle(self, bssid: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Fetches the geographical location of a BSSID from the WiGLE API.

        :param bssid: The BSSID (MAC address) of the access point.
        :return: A dictionary with 'lat' and 'lon' if found, else None.
        """
        if not bssid:
            logging.warning("[Discord plugin] Missing BSSID. Skipping location retrieval.")
            return None

        headers = {
            'Authorization': f'Basic {self.api_key}'
        }
        params = {
            'netid': bssid,
        }

        try:
            response = self.http_session.get(
                'https://api.wigle.net/api/v2/network/detail',
                headers=headers,
                params=params,
                timeout=10  # Set a timeout for the request
            )
            logging.info(f"[Discord plugin] WiGLE API request for BSSID {bssid}, response code: {response.status_code}")
        except RequestException as e:
            logging.error(f'[Discord plugin] Network error while fetching WiGLE data for BSSID {bssid}: {e}')
            return None

        if response.status_code == 200:
            try:
                data = response.json()
            except json.JSONDecodeError:
                logging.error('[Discord plugin] Failed to decode WiGLE API response as JSON.')
                return None

            if data.get('success') and data.get('results'):
                result = data['results'][0]
                trilat = result.get('trilat', 'N/A')
                trilong = result.get('trilong', 'N/A')
                logging.info(f"[Discord plugin] WiGLE API result for BSSID {bssid}: Lat={trilat}, Long={trilong}")

                return {
                    'lat': trilat,
                    'lon': trilong
                }
            else:
                logging.warning(f'[Discord plugin] No location data found for BSSID: {bssid}.')
        else:
            logging.error(f'[Discord plugin] Error fetching WiGLE data for BSSID {bssid}: {response.status_code} - {response.text}')
        return None

    def on_internet_available(self, agent: Agent) -> None:
        """
        Triggered when the internet becomes available.
        Sends a session summary to Discord if not already sent.

        :param agent: The Pwnagotchi agent.
        """
        if self.session_notified:
            return

        last_session = agent.last_session
        logging.info(
            f"Last session details: Handshakes: {last_session.handshakes}, "
            f"Duration: {last_session.duration}, Epochs: {last_session.epochs}"
        )

        if last_session.handshakes > 0:
            logging.info("Discord plugin: Internet available, sending session summary.")
            self.session_notified = True  # Prevent future notifications until reset

            # Capture display image using a temporary file
            try:
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_image:
                    display = agent.view()
                    display.update(force=True)
                    display.image().save(temp_image.name, 'png')
                    picture_path = temp_image.name

                # Prepare session summary
                embed_data = [
                    {
                        'title': '📊 Pwnagotchi Session Summary',
                        'description': 'Here are the stats from the last session:',
                        'fields': [
                            {'name': '⏱ Duration', 'value': last_session.duration, 'inline': True},
                            {'name': '🔢 Epochs', 'value': str(last_session.epochs), 'inline': True},
                            {'name': '⭐ Average Reward', 'value': f"{last_session.avg_reward:.2f}", 'inline': True},
                            {'name': '🚫 Deauths', 'value': str(last_session.deauthed), 'inline': True},
                            {'name': '🔗 Associations', 'value': str(last_session.associated), 'inline': True},
                            {'name': '🔐 Handshakes', 'value': str(last_session.handshakes), 'inline': True},
                        ],
                        'image': {'url': 'attachment://pwnagotchi.png'},
                        'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    }
                ]

                # Send session summary with screenshot
                with open(picture_path, 'rb') as image_file:
                    files = {'pwnagotchi.png': image_file}
                    self.send_discord_notification(
                        "📈 Session Summary",
                        embed_data=embed_data,
                        files=files
                    )
            except Exception as e:
                logging.exception(f"Discord plugin: Error sending session summary: {e}")
            finally:
                if 'picture_path' in locals() and os.path.exists(picture_path):
                    try:
                        os.remove(picture_path)
                        logging.info("Discord plugin: Temporary image file removed.")
                    except OSError as e:
                        logging.error(f"Discord plugin: Error removing temporary image file: {e}")
        else:
            logging.info("Discord plugin: No handshakes in last session; not sending summary.")
            self.session_notified = True  # Prevent repeated logging

    def on_session_stop(self, agent: Agent, session: Any) -> None:
        """
        Triggered when a session stops.
        Resets notification flags.

        :param agent: The Pwnagotchi agent.
        :param session: The session that has stopped.
        """
        logging.info("Session stopped. Resetting notification flags.")
        self.session_notified = False
