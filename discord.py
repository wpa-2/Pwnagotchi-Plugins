import logging
import requests
import json
import os
import pwnagotchi
import pwnagotchi.plugins as plugins

class Discord(plugins.Plugin):
    __author__ = "WPA2"
    __version__ = '2.2.0'
    __license__ = 'GPL3'
    __description__ = 'Sends Pwnagotchi handshakes and session summaries to Discord, with location data from WiGLE.'

    def __init__(self):
        self.webhook_url = None
        self.session_notified = False
        self.api_key = None  # WiGLE API key

    def on_loaded(self):
        logging.info('Discord plugin loaded.')
        self.webhook_url = self.options.get('webhook_url', None)
        self.api_key = self.options.get('wigle_api_key', None)

        if not self.webhook_url:
            logging.error("Discord plugin: Webhook URL not provided in config.")
        else:
            logging.info("Discord plugin: Webhook URL set.")

        if not self.api_key:
            logging.error("Discord plugin: WiGLE API key not provided in config.")
        else:
            logging.info("Discord plugin: WiGLE API key set.")

    def send_discord_notification(self, content, embed_data=None, files=None):
        """Send a notification to the configured Discord webhook."""
        if not self.webhook_url:
            logging.error("Discord plugin: Webhook URL not set. Cannot send notification.")
            return

        data = {
            "content": content,
            "embeds": embed_data or []
        }

        try:
            if files:
                response = requests.post(
                    self.webhook_url,
                    data={"payload_json": json.dumps(data)},
                    files=files
                )
            else:
                response = requests.post(self.webhook_url, json=data)

            if response.status_code in [200, 204]:
                logging.info("Discord plugin: Notification sent successfully.")
            else:
                logging.error(f"Discord plugin: Failed to send notification. "
                              f"Response: {response.status_code} - {response.text}")
        except Exception as e:
            logging.exception(f"Discord plugin: Error sending notification: {str(e)}")

    def on_handshake(self, agent, filename, access_point, client_station):
        """Called when a handshake is captured."""
        logging.info("Discord plugin: Handshake captured.")

        # Fetch the location from WiGLE
        location = self._get_location_from_wigle(access_point["mac"])

        # Build a user-friendly location value for the embed
        if location:
            lat = location['lat']
            lon = location['lon']
            location_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            location_value = (
                f"Latitude: {lat}, Longitude: {lon}\n"
                f"[View Location]({location_link})"
            )
        else:
            location_value = f"ESSID or BSSID {access_point['mac']} not known to the Wigle database."

        embed_data = [
            {
                'title': 'New Handshake Captured!',
                'description': (
                    f"Access Point: **{access_point['hostname']}**\n"
                    f"Client Station: **{client_station['mac']}**"
                ),
                'fields': [
                    {
                        'name': 'Handshake File',
                        'value': filename,
                        'inline': False
                    },
                    {
                        'name': 'Location',
                        'value': location_value,
                        'inline': False
                    }
                ]
            }
        ]

        self.send_discord_notification(
            content=f"🤝 New handshake from {access_point['hostname']}",
            embed_data=embed_data
        )

    def _get_location_from_wigle(self, bssid):
        """Query WiGLE for approximate location data based on the BSSID."""
        headers = {
            'Authorization': 'Basic ' + self.api_key
        }
        params = {
            'netid': bssid
        }

        response = requests.get('https://api.wigle.net/api/v2/network/detail', headers=headers, params=params)
        logging.info(f"[Discord plugin] WiGLE API request for BSSID {bssid}, response code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            if data['success'] and data['results']:
                result = data['results'][0]
                trilat = result.get('trilat', 'N/A')
                trilong = result.get('trilong', 'N/A')
                logging.info(f"[Discord plugin] WiGLE API result: Lat={trilat}, Long={trilong}")
                return {
                    'lat': trilat,
                    'lon': trilong
                }
            else:
                logging.warning(f"[Discord plugin] No location data found for BSSID: {bssid}")
        elif response.status_code == 401:
            logging.info(f"[Discord plugin] WiGLE returned 401 for BSSID {bssid}. Treating as no location data.")
        else:
            logging.error(f"[Discord plugin] Error fetching WiGLE data: {response.status_code}")

        return None

    def on_internet_available(self, agent):
        """Called once an Internet connection is available."""
        if self.session_notified:
            return  # Avoid sending multiple session summaries

        last_session = agent.last_session
        logging.info(f"Last session details: Handshakes: {last_session.handshakes}, "
                     f"Duration: {last_session.duration}, Epochs: {last_session.epochs}")

        if last_session.handshakes > 0:
            logging.info("Discord plugin: Internet available, sending session summary.")
            self.session_notified = True  # Prevent future notifications

            # Capture display image
            display = agent.view()
            picture_path = '/root/pwnagotchi.png'
            display.update(force=True)
            display.image().save(picture_path, 'png')

            # Prepare session summary embed
            embed_data = [
                {
                    'title': 'Pwnagotchi Session Summary',
                    'description': 'Here are the stats from the last session:',
                    'fields': [
                        {'name': 'Duration',       'value': last_session.duration,               'inline': True},
                        {'name': 'Epochs',         'value': str(last_session.epochs),           'inline': True},
                        {'name': 'Average Reward', 'value': f"{last_session.avg_reward:.2f}",    'inline': True},
                        {'name': 'Deauths',        'value': str(last_session.deauthed),         'inline': True},
                        {'name': 'Associations',   'value': str(last_session.associated),       'inline': True},
                        {'name': 'Handshakes',     'value': str(last_session.handshakes),       'inline': True},
                    ],
                    'image': {'url': 'attachment://pwnagotchi.png'}
                }
            ]

            # Send session summary + screenshot
            try:
                with open(picture_path, 'rb') as image_file:
                    files = {'pwnagotchi.png': image_file}
                    self.send_discord_notification(
                        content="📊 Session Summary",
                        embed_data=embed_data,
                        files=files
                    )
            except Exception as e:
                logging.exception(f"Discord plugin: Error sending session summary: {str(e)}")
        else:
            logging.info("Discord plugin: No handshakes in last session; not sending summary.")
            # You can set self.session_notified = True to avoid repeated logs if you wish
            self.session_notified = True

    def on_session_stop(self, agent, session):
        """Called when a session ends."""
        logging.info("Session stopped. Resetting notification flags.")
        self.session_notified = False
