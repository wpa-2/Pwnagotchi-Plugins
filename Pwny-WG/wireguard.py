import logging
import os
import subprocess
import time
import threading

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

class WireGuard(plugins.Plugin):
    __author__ = 'WPA2'
    __version__ = '1.5'
    __license__ = 'GPL3'
    __description__ = 'Connects to WireGuard and syncs handshakes via custom SSH port.'

    def __init__(self):
        self.ready = False
        self.status = "Init"
        self.wg_config_path = "/tmp/wg0.conf"
        self.last_sync_time = 0
        self.sync_interval = 600
        self.initial_boot = True
        self.lock = threading.Lock()

    def on_loaded(self):
        required_ops = ['private_key', 'address', 'peer_public_key', 'peer_endpoint', 'handshake_dir', 'server_user']
        missing = [op for op in required_ops if op not in self.options]
        
        if missing:
            logging.error(f"[WireGuard] Missing config: {', '.join(missing)}")
            return

        if not os.path.exists('/usr/bin/rsync'):
            logging.error("[WireGuard] rsync is not installed. Run: sudo apt-get install rsync")
            return

        self.options.setdefault('startup_delay_secs', 60)
        self.options.setdefault('server_port', 22)
        
        self.ready = True
        logging.info("[WireGuard] Plugin loaded and ready.")

    def on_ui_setup(self, ui):
        self.ui = ui
        try:
            ui.add_element('wg_status', LabeledValue(
                color=BLACK,
                label='WG:',
                value=self.status,
                position=(ui.width() // 2 - 25, 0),
                label_font=fonts.Small,
                text_font=fonts.Small
            ))
        except Exception as e:
            logging.error(f"[WireGuard] UI Setup Error: {e}")

    def update_status(self, text):
        self.status = text
        if hasattr(self, 'ui'):
            try:
                self.ui.set('wg_status', text)
            except Exception:
                pass

    def _cleanup_interface(self):
        subprocess.run(["wg-quick", "down", self.wg_config_path], 
                       stdout=subprocess.DEVNULL, 
                       stderr=subprocess.DEVNULL)
        subprocess.run(["ip", "link", "delete", "dev", "wg0"], 
                       stdout=subprocess.DEVNULL, 
                       stderr=subprocess.DEVNULL)

    def _connect(self):
        if self.lock.locked():
            return

        logging.info("[WireGuard] Attempting to connect...")
        self.update_status("Conn...")

        self._cleanup_interface()

        server_vpn_ip = ".".join(self.options['address'].split('.')[:3]) + ".1"

        conf = f"""[Interface]
PrivateKey = {self.options['private_key']}
Address = {self.options['address']}
"""
        if 'dns' in self.options:
            conf += f"DNS = {self.options['dns']}\n"
        
        conf += f"""
[Peer]
PublicKey = {self.options['peer_public_key']}
Endpoint = {self.options['peer_endpoint']}
AllowedIPs = {server_vpn_ip}/32
PersistentKeepalive = 25
"""
        if 'preshared_key' in self.options:
            conf += f"PresharedKey = {self.options['preshared_key']}\n"

        try:
            with open(self.wg_config_path, "w") as f:
                f.write(conf)
            os.chmod(self.wg_config_path, 0o600)

            process = subprocess.run(
                ["wg-quick", "up", self.wg_config_path],
                capture_output=True,
                text=True
            )

            if process.returncode == 0:
                self.update_status("Up")
                logging.info("[WireGuard] Connection established.")
                return True
            else:
                self.update_status("Err")
                clean_err = process.stderr.replace('\n', ' ')
                logging.error(f"[WireGuard] Connect fail: {clean_err}")
                return False

        except Exception as e:
            self.update_status("Err")
            logging.error(f"[WireGuard] Critical Error: {e}")
            return False

    def _sync_handshakes(self):
        with self.lock:
            logging.info("[WireGuard] Starting handshake sync...")
            
            source_dir = '/home/pi/handshakes/'
            remote_dir = self.options['handshake_dir']
            server_user = self.options['server_user']
            server_vpn_ip = ".".join(self.options['address'].split('.')[:3]) + ".1"
            ssh_port = self.options['server_port']
            
            if not os.path.exists(source_dir):
                return

            # Explicitly force id_ed25519 key
            ssh_cmd = f"ssh -p {ssh_port} -i /root/.ssh/id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10"
            
            command = [
                "rsync", "-avz", "--stats", "--timeout=20",
                "-e", ssh_cmd,
                source_dir,
                f"{server_user}@{server_vpn_ip}:{remote_dir}"
            ]

            try:
                result = subprocess.run(command, capture_output=True, text=True)
                
                if result.returncode == 0:
                    new_files = 0
                    for line in result.stdout.splitlines():
                        if "Number of created files:" in line:
                            try:
                                parts = line.split(":")
                                if len(parts) > 1:
                                    new_files = int(parts[1].strip().split()[0])
                            except: pass
                    
                    msg = f"Sync: {new_files}"
                    self.update_status(msg)
                    if new_files > 0:
                        logging.info(f"[WireGuard] Transferred {new_files} handshakes.")
                    
                    threading.Timer(10.0, self.update_status, ["Up"]).start()
                else:
                    logging.error(f"[WireGuard] Sync Error: {result.stderr}")
                    if "Connection refused" in result.stderr or "unreachable" in result.stderr:
                         logging.warning("[WireGuard] Connection appears dead. Resetting...")
                         self.update_status("Down")
                         self._cleanup_interface()

            except Exception as e:
                logging.error(f"[WireGuard] Sync Exception: {e}")
            
            finally:
                self.last_sync_time = time.time()

    def on_internet_available(self, agent):
        if not self.ready:
            return

        if self.initial_boot:
            delay = self.options['startup_delay_secs']
            logging.debug(f"[WireGuard] Waiting {delay}s startup delay...")
            time.sleep(delay)
            self.initial_boot = False
        
        # FIX: Only connect if we are definitely DOWN, ERROR, or Initializing
        # Do NOT connect if we are "Up" or currently "Sync: X"
        if self.status in ["Init", "Down", "Err"]:
            self._connect()
        
        # Trigger sync if Up OR currently Syncing (to allow retries if logic permits)
        elif self.status == "Up" or self.status.startswith("Sync"):
            if self.lock.locked():
                return 

            now = time.time()
            if now - self.last_sync_time > self.sync_interval:
                threading.Thread(target=self._sync_handshakes).start()

    def on_unload(self, ui):
        logging.info("[WireGuard] Unloading...")
        self._cleanup_interface()
        if os.path.exists(self.wg_config_path):
            try:
                os.remove(self.wg_config_path)
            except: pass
        try:
            ui.remove_element('wg_status')
        except: pass
