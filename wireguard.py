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
    __version__ = '1.9'
    __license__ = 'GPL3'
    __description__ = 'VPN Sync: Full backup on first run, then incremental only.'

    def __init__(self):
        self.ready = False
        self.status = "Init"
        self.wg_config_path = "/tmp/wg0.conf"
        self.last_sync_time = 0
        self.sync_interval = 600
        self.initial_boot = True
        self.lock = threading.Lock()
        # This file acts as the "Bookmark". We only sync files newer than this file.
        self.marker_file = "/root/.wg_last_sync_marker"

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
        
        # Calculate server VPN IP (assume .1 if not specified)
        if 'server_vpn_ip' not in self.options:
            try:
                ip_part = self.options['address'].split('/')[0]
                base_ip = ".".join(ip_part.split('.')[:3]) + ".1"
                self.options['server_vpn_ip'] = base_ip
            except:
                self.options['server_vpn_ip'] = "10.0.0.1" 

        # --- CHECKPOINT LOGIC ---
        # If marker doesn't exist, this is a fresh install.
        if not os.path.exists(self.marker_file):
            try:
                # Create the file
                with open(self.marker_file, 'a'):
                    pass
                # Set timestamp to Epoch (1970). 
                # This ensures the "find -newer" command catches ALL historical files on the first run.
                os.utime(self.marker_file, (0, 0))
                logging.info("[WireGuard] First run detected. Full sync scheduled.")
            except Exception as e:
                logging.error(f"[WireGuard] Marker creation failed: {e}")
        # ------------------------

        self.ready = True
        logging.info("[WireGuard] Plugin loaded. Checkpoint system active.")

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
        try:
            subprocess.run(["wg-quick", "down", self.wg_config_path], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            subprocess.run(["ip", "link", "delete", "dev", "wg0"], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
        except:
            pass

    def _connect(self):
        if self.lock.locked():
            return

        logging.info("[WireGuard] Attempting to connect...")
        self.update_status("Conn...")

        self._cleanup_interface()

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
AllowedIPs = {self.options['server_vpn_ip']}/32
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

    def _get_ssh_key_path(self):
        if os.path.exists("/root/.ssh/id_ed25519"):
            return "/root/.ssh/id_ed25519"
        elif os.path.exists("/root/.ssh/id_rsa"):
            return "/root/.ssh/id_rsa"
        return None

    def _sync_handshakes(self):
        with self.lock:
            source_dir = '/home/pi/handshakes/'
            if not os.path.exists(source_dir):
                source_dir = '/root/handshakes/'
            
            remote_dir = self.options['handshake_dir']
            server_user = self.options['server_user']
            server_ip = self.options['server_vpn_ip']
            ssh_port = self.options['server_port']
            
            if not os.path.exists(source_dir):
                return

            key_path = self._get_ssh_key_path()
            if not key_path:
                self.update_status("KeyErr")
                return

            # --- GAPLESS SYNC LOGIC ---
            # 1. We create a list of files that are NEWER than our marker file.
            file_list_path = "/tmp/wg_sync_list.txt"
            
            # Use 'find' with -newer. This is instant.
            # It finds everything captured since the last successful sync.
            try:
                with open(file_list_path, "w") as f:
                    subprocess.run(
                        ["find", source_dir, "-type", "f", "-newer", self.marker_file, "-printf", "%P\\n"], 
                        stdout=f
                    )
                
                # If nothing new, we are done. Fast exit.
                if os.path.getsize(file_list_path) == 0:
                    self.last_sync_time = time.time()
                    return 
                    
            except Exception as e:
                logging.error(f"[WireGuard] List Gen Error: {e}")
                return
            # --- END LOGIC ---

            logging.info("[WireGuard] Syncing new handshakes...")
            ssh_cmd = f"ssh -p {ssh_port} -i {key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10"
            
            command = [
                "rsync", "-avz", "--timeout=30",
                "--files-from=" + file_list_path,
                "-e", ssh_cmd,
                source_dir,
                f"{server_user}@{server_ip}:{remote_dir}"
            ]

            try:
                result = subprocess.run(command, capture_output=True, text=True)
                
                if result.returncode == 0:
                    # SUCCESS: Update the marker to NOW so we don't sync these files again
                    os.utime(self.marker_file, None)
                    
                    try:
                        with open(file_list_path, 'r') as f:
                            count = sum(1 for _ in f)
                        msg = f"Sync: {count}"
                    except:
                        msg = "Sync: OK"

                    self.update_status(msg)
                    if count > 0:
                        logging.info(f"[WireGuard] Synced {count} new handshakes.")
                    
                    threading.Timer(10.0, self.update_status, ["Up"]).start()
                else:
                    if result.returncode not in [23, 24]:
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
        
        if self.status in ["Init", "Down", "Err"]:
            self._connect()
        
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
