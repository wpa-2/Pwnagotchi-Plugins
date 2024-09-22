import logging
import requests
import os
import json
import pwnagotchi
import pwnagotchi.plugins as plugins

class Discord(plugins.Plugin):
    __author__ = "WPA2"
    __version__ = '2.1.0'
    __license__ = 'GPL3'
    __description__ = 'Sends Pwnagotchi handshakes and session summaries to Discord.'

    def __init__(self):
        self.webhook_url = None
        self.api_key = None
        self.session_notified = False
        self.no_handshake_logged = False  # Track no handshake notifications

    def on_loaded(self):
        logging.info('Discord plugin loaded.')
        self.webhook_url = self.options.get('webhook_url', None)
        self.api_key = self.options.get('wigle_api_key', None)
        if not self.webhook_url:
            logging.error("Discord plugin: Webhook URL not provided in config.")
        else:
            logging.info("Discord plugin: Webhook URL set.")

    def send_discord_notification(self, content, embed_data=None, files=None):
        if not self.webhook_url:
            logging.error("Discord plugin: Webhook URL not set. Cannot send notification.")
            return

        data = {
            "content": content,
            "embeds": embed_data or []
        }

        try:
            if files:
                response = requests.post(self.webhook_url, data={"payload_json": json.dumps(data)}, files=files)
            else:
                response = requests.post(self.webhook_url, json=data)

            if response.status_code in [200, 204]:
                logging.info('Discord plugin: Notification sent successfully.')
            else:
                logging.error(f"Discord plugin: Failed to send notification. Response: {response.status_code} - {response.text}")
        except Exception as e:
            logging.exception(f"Discord plugin: Error sending notification: {str(e)}")

    def on_config_changed(self, config):
        self.api_key = config.get('main', {}).get('plugins', {}).get('wiglelocator', {}).get('api_key', None)
        if not self.api_key:
            logging.error('[Discord] WiGLE API key not found in config.toml!')

    def on_handshake(self, agent, filename, access_point, client_station):
        logging.info(f"[Discord] Handshake event captured. Access Point: {access_point['hostname']}, Client Station: {client_station['mac']}")
        
        bssid = access_point["mac"]
        essid = access_point["hostname"]

        # Fetch the AP location from WiGLE
        location = self._get_location_from_wigle(bssid)

        if location:
            location_link = f"https://www.google.com/maps?q={location['lat']},{location['lon']}"
            embed_data = [
                {
                    'title': 'New Handshake Captured!',
                    'description': (
                        f'Access Point: **{access_point["hostname"]}**\n'
                        f'Client Station: **{client_station["mac"]}**\n'
                        f'Location:\n'
                        f'Latitude: {location["lat"]}, Longitude: {location["lon"]}\n'
                        f'[View Location]({location_link})'
                    ),
                    'fields': [
                        {'name': 'Handshake File', 'value': filename, 'inline': False},
                    ]
                }
            ]
        else:
            logging.warning(f'[Discord] No location found for BSSID: {bssid}. Sending notification without location.')
            embed_data = [
                {
                    'title': 'New Handshake Captured!',
                    'description': (
                        f'Access Point: **{access_point["hostname"]}**\n'
                        f'Client Station: **{client_station["mac"]}**\n'
                        'Location: Not available\n'
                    ),
                    'fields': [
                        {'name': 'Handshake File', 'value': filename, 'inline': False},
                    ]
                }
            ]

        self.send_discord_notification(
            f"🤝 New handshake from {access_point['hostname']}",
            embed_data=embed_data
        )

    def _get_location_from_wigle(self, bssid):
        headers = {
            'Authorization': 'Basic ' + self.api_key
        }
        params = {
            'netid': bssid,
        }

        response = requests.get('https://api.wigle.net/api/v2/network/detail', headers=headers, params=params)
        logging.info(f"[Discord] WiGLE API request for BSSID {bssid}, response code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            if data['success'] and data['results']:
                result = data['results'][0]
                return {
                    'lat': result.get('trilat', 'N/A'),
                    'lon': result.get('trilong', 'N/A')
                }
            else:
                logging.warning(f'[Discord] No location data found for BSSID: {bssid}')
        else:
            logging.error(f'[Discord] Error fetching WiGLE data: {response.status_code}')
        return None

    def on_internet_available(self, agent):
        last_session = agent.last_session
        if last_session.handshakes > 0 and not self.session_notified:
            logging.info("Discord plugin: Internet available, sending session summary.")
            self.session_notified = True

            embed_data = [
                {
                    'title': 'Pwnagotchi Session Summary',
                    'description': 'Here are the stats from the last session:',
                    'fields': [
                        {'name': 'Duration', 'value': last_session.duration, 'inline': True},
                        {'name': 'Epochs', 'value': str(last_session.epochs), 'inline': True},
                        {'name': 'Average Reward', 'value': f"{last_session.avg_reward:.2f}", 'inline': True},
                        {'name': 'Deauths', 'value': str(last_session.deauthed), 'inline': True},
                        {'name': 'Associations', 'value': str(last_session.associated), 'inline': True},
                        {'name': 'Handshakes', 'value': str(last_session.handshakes), 'inline': True},
                    ]
                }
            ]

            self.send_discord_notification("📊 Session Summary", embed_data=embed_data)

    def on_session_stop(self, agent, session):
        logging.info("Session stopped. Resetting notification flags.")
        self.session_notified = False
        self.no_handshake_logged = False  # Reset for next session
