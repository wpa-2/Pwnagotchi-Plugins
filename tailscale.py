import logging
import os
import subprocess
import time

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

class Tailscale(plugins.Plugin):
    __author__ = 'WPA2'
    __version__ = '1.0.2'
    __license__ = 'GPL3'
    __description__ = 'A configurable plugin to connect to a Tailscale network and sync handshakes.'

    def __init__(self):
        self.ready = False
        self.status = "Starting"

    def on_loaded(self):
        logging.info("[Tailscale] Plugin loaded.")
        
        # Set default options if they're not in config.toml
        self.options.setdefault('sync_interval_secs', 600)
        self.options.setdefault('source_handshake_path', '/home/pi/handshakes/')
        self.options.setdefault('hostname', 'pwnagotchi')

        # Validate that all required options are present
        required = ['auth_key', 'server_tailscale_ip', 'server_user', 'handshake_dir']
        missing = [key for key in required if key not in self.options]
        if missing:
            logging.error(f"[Tailscale] Missing required config options: {', '.join(missing)}")
            return
        
        # Validate hostname (DNS label format for Tailscale)
        hostname = self.options['hostname']
        import re
        if not re.match(r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$', hostname):
            logging.warning(f"[Tailscale] Hostname '{hostname}' may not be valid. Use lowercase letters, numbers, and hyphens only.")
            logging.warning("[Tailscale] Valid examples: 'pwnagotchi', 'pwn-01', 'my-device'")
            # Continue anyway - let Tailscale reject it if invalid
            
        if not os.path.exists('/usr/bin/tailscale') or not os.path.exists('/usr/bin/rsync'):
            logging.error("[Tailscale] tailscale or rsync is not installed.")
            return
            
        self.ready = True
        self.last_sync_time = 0

    def on_ui_setup(self, ui):
        self.ui = ui
        self.ui.add_element('ts_status', LabeledValue(
            color=BLACK,
            label='TS:',
            value=self.status,
            position=(175, 76),
            label_font=fonts.Small,
            text_font=fonts.Small
        ))

    def _update_status(self, new_status, temporary=False, duration=15):
        """Helper method to update the UI status."""
        original_status = self.status
        self.status = new_status
        
        # Only update UI if it's been initialized
        if hasattr(self, 'ui') and self.ui:
            try:
                self.ui.set('ts_status', self.status)
                self.ui.update()
            except Exception as e:
                logging.debug(f"[Tailscale] UI update failed: {e}")
        
        if temporary:
            time.sleep(duration)
            # Only revert if the status hasn't changed to something else in the meantime
            if self.status == new_status:
                self.status = original_status
                if hasattr(self, 'ui') and self.ui:
                    try:
                        self.ui.set('ts_status', self.status)
                        self.ui.update()
                    except Exception as e:
                        logging.debug(f"[Tailscale] UI update failed: {e}")

    def _connect(self):
        max_retries = 3
        retry_delay = 15
        
        for attempt in range(max_retries):
            logging.info(f"[Tailscale] Attempting to connect (Attempt {attempt + 1}/{max_retries})...")
            self._update_status("Conn...")

            try:
                # Check current Tailscale status
                status_result = subprocess.run(["tailscale", "status"], capture_output=True, text=True)
                # A successful status command (exit code 0) with output means we're connected
                if status_result.returncode == 0 and status_result.stdout.strip():
                    self._update_status("Up")
                    logging.info("[Tailscale] Already connected to Tailscale.")
                    return True

                # Attempt to connect
                connect_command = [
                    "tailscale", "up",
                    f"--authkey={self.options['auth_key']}",
                    f"--hostname={self.options['hostname']}",
                    "--accept-dns=false"  # Prevent DNS conflicts with Pwnagotchi's network setup
                ]
                subprocess.run(connect_command, check=True, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                
                # Verify connection
                time.sleep(5) # Give Tailscale a moment to establish the connection
                status_check = subprocess.run(["tailscale", "status"], capture_output=True, text=True)
                # Check if status command succeeded and has output (indicating we're connected)
                if status_check.returncode == 0 and status_check.stdout.strip():
                    self._update_status("Up")
                    logging.info("[Tailscale] Connection established.")
                    return True
                else:
                    raise subprocess.CalledProcessError(1, "tailscale up", stderr="Failed to verify connection.")

            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.strip() if e.stderr else 'Unknown error'
                logging.error(f"[Tailscale] Connection failed: {error_msg}")
                self._update_status("Error")
                time.sleep(retry_delay)

        logging.error("[Tailscale] Failed to establish connection after multiple retries.")
        self._update_status("Failed")
        return False

    def _sync_handshakes(self):
        logging.info("[Tailscale] Starting handshake sync...")
        self._update_status("Sync...")
        
        source_dir = self.options['source_handshake_path']
        remote_dir = self.options['handshake_dir']
        server_user = self.options['server_user']
        server_ip = self.options['server_tailscale_ip']
        
        # Use dedicated SSH key to avoid conflicts with other plugins (e.g., WireGuard)
        command = [
            "rsync", "-avz", "--stats", "-e", 
            "ssh -i /root/.ssh/id_rsa_tailscale -o StrictHostKeyChecking=no -o BatchMode=yes -o UserKnownHostsFile=/dev/null",
            source_dir, f"{server_user}@{server_ip}:{remote_dir}"
        ]

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            new_files = 0
            for line in result.stdout.splitlines():
                if "Number of created files:" in line:
                    new_files = int(line.split(":")[1].strip().split(" ")[0])
                    break
            
            logging.info(f"[Tailscale] Sync complete. Transferred {new_files} new files.")
            # Keep status concise for small displays
            if new_files > 99:
                self._update_status("Sync:99+", temporary=True)
            else:
                self._update_status(f"Sync:{new_files}", temporary=True)
            self.last_sync_time = time.time()

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logging.error(f"[Tailscale] Handshake sync failed: {e}")
            if hasattr(e, 'stderr') and e.stderr:
                logging.error(f"[Tailscale] Stderr: {e.stderr.strip()}")
            self._update_status("SyncErr", temporary=True)

    def on_internet_available(self, agent):
        if not self.ready:
            return
        
        if self.status not in ["Up", "Conn..."]:
            self._connect()
        
        if self.status == "Up":
            now = time.time()
            if now - self.last_sync_time > self.options['sync_interval_secs']:
                self._sync_handshakes()

    def on_unload(self, ui):
        logging.info("[Tailscale] Unloading plugin.")
        # We might not want to disconnect from Tailscale on unload, 
        # as it could be used by other services. This can be enabled if desired.
        # logging.info("[Tailscale] Disconnecting from Tailscale.")
        # try:
        #     subprocess.run(["tailscale", "down"], check=True, capture_output=True)
        # except (subprocess.CalledProcessError, FileNotFoundError):
        #     pass
        
        with ui._lock:
            try:
                ui.remove_element('ts_status')
            except KeyError:
                pass
