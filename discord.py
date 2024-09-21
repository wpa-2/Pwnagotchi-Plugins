import logging
import requests
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
        self.session_notified = False

    def on_loaded(self):
        logging.info('Discord plugin loaded.')
        self.webhook_url = self.options.get('webhook_url', None)
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

    def on_handshake(self, agent, filename, access_point, client_station):
        logging.info("Discord plugin: Handshake captured.")
        embed_data = [
            {
                'title': 'New Handshake Captured!',
                'description': (
                    f"Access Point: **{access_point['hostname']}**\n"
                    f"Client Station: **{client_station['mac']}**"
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

    def on_internet_available(self, agent):
        if self.session_notified:
            return

        last_session = agent.last_session
        logging.info(f"Last session details: Handshakes: {last_session.handshakes}, Duration: {last_session.duration}, Epochs: {last_session.epochs}")

        if last_session.handshakes > 0:
            logging.info("Discord plugin: Internet available, sending session summary.")
            self.session_notified = True  # Prevent future notifications until reset

            # Capture display image
            display = agent.view()
            picture_path = '/root/pwnagotchi.png'
            display.update(force=True)
            display.image().save(picture_path, 'png')

            # Prepare session summary
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
                    ],
                    'image': {'url': 'attachment://pwnagotchi.png'}
                }
            ]

            # Send session summary with screenshot
            try:
                with open(picture_path, 'rb') as image_file:
                    files = {'pwnagotchi.png': image_file}
                    self.send_discord_notification(
                        "📊 Session Summary",
                        embed_data=embed_data,
                        files=files
                    )
            except Exception as e:
                logging.exception(f"Discord plugin: Error sending session summary: {str(e)}")
        else:
            logging.info("Discord plugin: No handshakes in last session; not sending summary.")

    def on_session_stop(self, agent, session):
        logging.info("Session stopped. Resetting notification flag.")
        self.session_notified = False
