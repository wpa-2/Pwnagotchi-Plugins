import logging
import os
import subprocess
import time
import threading
from typing import Optional

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK


class WireGuard(plugins.Plugin):
    __author__ = 'WPA2'
    __version__ = '2.2'
    __license__ = 'GPL3'
    __description__ = 'VPN Sync: Full backup on first run, then incremental only. (Enhanced Edition - Fixed)'

    def __init__(self):
        self.ready = False
        self.status = "Init"
        self.wg_config_path = "/tmp/wg0.conf"
        self.last_sync_time = 0
        self.sync_interval = 600  # Default: 10 minutes
        self.boot_time = time.time()  # Track when plugin initialized
        self.connection_attempted = False
        self.lock = threading.Lock()
        self.marker_file = "/root/.wg_last_sync_marker"
        self.temp_file_list = "/tmp/wg_sync_list.txt"
        self.status_timer = None
        self.shutdown_requested = False
        
        # Statistics
        self.total_synced = 0
        self.today_synced = 0
        self.today_date = None
        self.connection_uptime_start = 0
        self.last_successful_sync = 0
        self.last_sync_count = 0
        self.connection_attempts = 0
        self.failed_attempts = 0
        
        # Health monitoring
        self.health_check_interval = 120  # 2 minutes
        self.last_health_check = 0
        self.consecutive_health_failures = 0

    def on_loaded(self):
        """Initialize plugin with comprehensive config validation."""
        required_opts = ['private_key', 'address', 'peer_public_key', 'peer_endpoint', 
                        'handshake_dir', 'server_user']
        missing = [op for op in required_opts if op not in self.options]
        
        if missing:
            logging.error(f"[WireGuard] Missing required config: {', '.join(missing)}")
            return

        # Validate dependencies
        if not self._check_dependencies():
            return

        # Set defaults
        self.options.setdefault('startup_delay_secs', 60)
        self.options.setdefault('server_port', 22)
        self.options.setdefault('dns', '9.9.9.9')
        self.options.setdefault('sync_interval', 600)
        self.options.setdefault('connection_timeout', 10)
        self.options.setdefault('max_retries', 5)
        self.options.setdefault('bwlimit', 0)  # KB/s, None = unlimited
        self.options.setdefault('compress_level', 6)
        self.options.setdefault('persistent_keepalive', 25)
        self.options.setdefault('health_check_enabled', True)
        
        self.sync_interval = self.options['sync_interval']
        
        # Validate and calculate server VPN IP
        if not self._validate_and_setup_network():
            return

        # Initialize marker file with proper error handling
        if not self._initialize_marker_file():
            logging.error("[WireGuard] Failed to initialize checkpoint system. Plugin disabled.")
            return

        # Setup known_hosts for secure SSH
        self._setup_ssh_security()

        self.ready = True
        logging.info(f"[WireGuard] Plugin v{self.__version__} loaded. Checkpoint system active.")
        logging.info(f"[WireGuard] Config: Sync interval={self.sync_interval}s, Compression={self.options['compress_level']}")

    def _check_dependencies(self) -> bool:
        """Verify all required system tools are installed."""
        required_tools = {
            'rsync': 'sudo apt-get install rsync',
            'wg': 'sudo apt-get install wireguard wireguard-tools',
            'wg-quick': 'sudo apt-get install wireguard wireguard-tools',
        }
        
        missing = []
        for tool, install_cmd in required_tools.items():
            if not self._command_exists(tool):
                logging.error(f"[WireGuard] Missing: {tool}. Install: {install_cmd}")
                missing.append(tool)
        
        return len(missing) == 0

    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH."""
        try:
            subprocess.run(['which', command], capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def _validate_and_setup_network(self) -> bool:
        """Validate network configuration and calculate server IP."""
        try:
            # Validate client address format
            address = self.options['address']
            if '/' not in address:
                logging.error(f"[WireGuard] Invalid address format: {address}. Expected CIDR notation (e.g., 10.0.0.5/24)")
                return False
            
            # Calculate server VPN IP if not specified
            if 'server_vpn_ip' not in self.options:
                ip_part = address.split('/')[0]
                octets = ip_part.split('.')
                
                if len(octets) != 4:
                    logging.error(f"[WireGuard] Invalid IP address: {ip_part}")
                    return False
                
                # Assume server is .1
                base_ip = ".".join(octets[:3]) + ".1"
                self.options['server_vpn_ip'] = base_ip
                logging.info(f"[WireGuard] Auto-detected server IP: {base_ip}")
            
            # Validate endpoint format
            endpoint = self.options['peer_endpoint']
            if ':' not in endpoint:
                logging.error(f"[WireGuard] Invalid endpoint format: {endpoint}. Expected HOST:PORT")
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"[WireGuard] Network validation failed: {e}")
            return False

    def _initialize_marker_file(self) -> bool:
        """Initialize checkpoint marker file with proper error handling."""
        try:
            if not os.path.exists(self.marker_file):
                # Create the file
                with open(self.marker_file, 'a'):
                    pass
                
                # Set timestamp to Epoch (1970) for full initial sync
                os.utime(self.marker_file, (0, 0))
                logging.info("[WireGuard] First run detected. Full sync scheduled.")
            else:
                logging.info("[WireGuard] Checkpoint marker found. Incremental sync mode.")
            
            # Verify we can read/write the marker
            if not os.access(self.marker_file, os.R_OK | os.W_OK):
                logging.error(f"[WireGuard] Cannot read/write marker file: {self.marker_file}")
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"[WireGuard] Marker initialization failed: {e}")
            return False

    def _setup_ssh_security(self):
        """Setup SSH known_hosts for secure connections."""
        try:
            known_hosts = "/root/.ssh/known_hosts"
            os.makedirs("/root/.ssh", mode=0o700, exist_ok=True)
            
            # Create known_hosts if it doesn't exist
            if not os.path.exists(known_hosts):
                open(known_hosts, 'a').close()
                os.chmod(known_hosts, 0o600)
                logging.info("[WireGuard] Created SSH known_hosts file")
                
        except Exception as e:
            logging.warning(f"[WireGuard] SSH security setup failed: {e}")

    def on_ui_setup(self, ui):
        """Setup UI elements."""
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

    def update_status(self, text: str):
        """Update status display with thread safety."""
        self.status = text
        
        # Cancel any pending status update timer
        if self.status_timer and self.status_timer.is_alive():
            self.status_timer.cancel()
        
        if hasattr(self, 'ui'):
            try:
                self.ui.set('wg_status', text)
            except Exception:
                pass

    def _cleanup_interface(self):
        """Clean up WireGuard interface and temp files."""
        try:
            subprocess.run(["wg-quick", "down", self.wg_config_path], 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL,
                          timeout=5)
        except:
            pass
        
        try:
            subprocess.run(["ip", "link", "delete", "dev", "wg0"], 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL,
                          timeout=5)
        except:
            pass
        
        # Clean up temp files
        self._cleanup_temp_files()

    def _cleanup_temp_files(self):
        """Remove temporary files created during sync."""
        temp_files = [self.temp_file_list, self.wg_config_path]
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception as e:
                    logging.debug(f"[WireGuard] Could not remove {temp_file}: {e}")

    def _verify_connection(self) -> bool:
        """Verify VPN connection is actually working."""
        try:
            server_ip = self.options['server_vpn_ip']
            result = subprocess.run(
                ["ping", "-c", "2", "-W", "3", server_ip],
                capture_output=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logging.debug(f"[WireGuard] Connection verified (ping to {server_ip})")
                return True
            else:
                logging.warning(f"[WireGuard] Ping to {server_ip} failed")
                return False
                
        except Exception as e:
            logging.error(f"[WireGuard] Connection verification failed: {e}")
            return False

    def _connect(self, retry_count: int = 0) -> bool:
        """
        Establish WireGuard connection with retry logic and verification.
        
        Args:
            retry_count: Current retry attempt number
            
        Returns:
            True if connection successful, False otherwise
        """
        if self.lock.locked():
            logging.debug("[WireGuard] Connection attempt skipped (sync in progress)")
            return False

        max_retries = self.options['max_retries']
        if retry_count >= max_retries:
            logging.error(f"[WireGuard] Max retries ({max_retries}) reached. Giving up.")
            self.update_status("Failed")
            return False

        if retry_count > 0:
            # Exponential backoff: 2^retry seconds (2, 4, 8, 16, 32...)
            backoff = min(2 ** retry_count, 60)
            logging.info(f"[WireGuard] Retry {retry_count}/{max_retries} after {backoff}s...")
            self.update_status(f"Retry:{retry_count}")
            time.sleep(backoff)

        self.connection_attempts += 1
        logging.info(f"[WireGuard] Connection attempt {self.connection_attempts}...")
        self.update_status("Conn...")

        # Clean up any existing interface
        self._cleanup_interface()

        # Build configuration
        conf = self._build_wireguard_config()

        try:
            # Write config
            with open(self.wg_config_path, "w") as f:
                f.write(conf)
            os.chmod(self.wg_config_path, 0o600)

            # Bring up interface
            process = subprocess.run(
                ["wg-quick", "up", self.wg_config_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if process.returncode != 0:
                self.failed_attempts += 1
                clean_err = process.stderr.replace('\n', ' ')
                logging.error(f"[WireGuard] wg-quick failed: {clean_err}")
                
                # Retry on DNS errors
                if "Temporary failure in name resolution" in process.stderr or \
                   "Name or service not known" in process.stderr:
                    logging.info("[WireGuard] DNS error detected, retrying...")
                    return self._connect(retry_count + 1)
                
                self.update_status("Err")
                return False

            # Verify connection actually works
            if not self._verify_connection():
                logging.warning("[WireGuard] Interface up but connection verification failed")
                self._cleanup_interface()
                return self._connect(retry_count + 1)

            # Success!
            self.connection_uptime_start = time.time()
            self.consecutive_health_failures = 0
            self.update_status("Up")
            logging.info("[WireGuard] Connection established and verified.")
            
            # Log statistics
            stats = f"Stats: {self.connection_attempts} attempts, {self.failed_attempts} failures, {self.total_synced} synced"
            logging.info(f"[WireGuard] {stats}")
            
            return True

        except subprocess.TimeoutExpired:
            logging.error("[WireGuard] Connection timeout")
            self._cleanup_interface()
            return self._connect(retry_count + 1)
            
        except Exception as e:
            self.failed_attempts += 1
            self.update_status("Err")
            logging.error(f"[WireGuard] Critical error: {e}")
            return self._connect(retry_count + 1)

    def _build_wireguard_config(self) -> str:
        """Build WireGuard configuration file content."""
        conf = f"""[Interface]
PrivateKey = {self.options['private_key']}
Address = {self.options['address']}
DNS = {self.options['dns']}

[Peer]
PublicKey = {self.options['peer_public_key']}
Endpoint = {self.options['peer_endpoint']}
AllowedIPs = {self.options['server_vpn_ip']}/32
PersistentKeepalive = {self.options['persistent_keepalive']}
"""
        if 'preshared_key' in self.options:
            conf += f"PresharedKey = {self.options['preshared_key']}\n"
            
        return conf

    def _get_ssh_key_path(self) -> Optional[str]:
        """Find SSH private key, preferring ed25519."""
        key_paths = [
            "/root/.ssh/id_ed25519",
            "/root/.ssh/id_rsa",
            "/root/.ssh/id_ecdsa"
        ]
        
        for key_path in key_paths:
            if os.path.exists(key_path):
                return key_path
        
        logging.error("[WireGuard] No SSH key found. Run: sudo ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N \"\"")
        return None

    def _build_file_list(self) -> tuple[bool, int]:
        """
        Build list of files to sync using checkpoint marker.
        
        Returns:
            Tuple of (success: bool, file_count: int)
        """
        source_dir = self._get_source_directory()
        if not source_dir:
            return False, 0

        try:
            # Use find with -newer to get only files modified since last sync
            # Filter for common handshake file extensions to avoid syncing junk
            with open(self.temp_file_list, "w") as f:
                result = subprocess.run(
                    [
                        "find", source_dir,
                        "-type", "f",
                        "-newer", self.marker_file,
                        "(", "-name", "*.pcap", "-o", "-name", "*.cap", "-o", "-name", "*.hccapx", ")",
                        "-printf", "%P\\n"
                    ],
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30
                )
            
            if result.returncode != 0:
                logging.error(f"[WireGuard] File list generation failed: {result.stderr}")
                return False, 0
            
            # Count files
            file_count = 0
            if os.path.exists(self.temp_file_list):
                with open(self.temp_file_list, 'r') as f:
                    file_count = sum(1 for line in f if line.strip())
            
            return True, file_count
            
        except subprocess.TimeoutExpired:
            logging.error("[WireGuard] File list generation timed out")
            return False, 0
        except Exception as e:
            logging.error(f"[WireGuard] File list error: {e}")
            return False, 0

    def _get_source_directory(self) -> Optional[str]:
        """Find handshake source directory."""
        possible_dirs = [
            '/home/pi/handshakes/',
            '/root/handshakes/',
            '/home/pi/handshakes',  # without trailing slash
            '/root/handshakes'
        ]
        
        for directory in possible_dirs:
            if os.path.exists(directory) and os.path.isdir(directory):
                return directory.rstrip('/') + '/'  # Ensure trailing slash
        
        logging.error("[WireGuard] No handshake directory found")
        return None

    def _sync_handshakes(self):
        """
        Sync new handshakes to server with improved error handling.
        Uses checkpoint system for gapless, efficient transfers.
        """
        # Acquire lock with timeout to avoid deadlock
        acquired = self.lock.acquire(timeout=5)
        if not acquired:
            logging.warning("[WireGuard] Could not acquire sync lock (timeout)")
            return

        try:
            source_dir = self._get_source_directory()
            if not source_dir:
                return

            # Build list of new files
            success, file_count = self._build_file_list()
            if not success:
                return
            
            # Fast exit if nothing to sync
            if file_count == 0:
                self.last_sync_time = time.time()
                logging.debug("[WireGuard] No new handshakes to sync")
                return

            logging.info(f"[WireGuard] Syncing {file_count} new handshakes...")
            self.update_status(f"Sync:{file_count}")

            # Get SSH key
            key_path = self._get_ssh_key_path()
            if not key_path:
                self.update_status("KeyErr")
                return

            # Build rsync command
            server_user = self.options['server_user']
            server_ip = self.options['server_vpn_ip']
            ssh_port = self.options['server_port']
            remote_dir = self.options['handshake_dir']
            timeout = self.options['connection_timeout']

            # SSH command with better security
            ssh_cmd = (
                f"ssh -p {ssh_port} "
                f"-i {key_path} "
                f"-o ConnectTimeout={timeout} "
                f"-o ServerAliveInterval=10 "
                f"-o ServerAliveCountMax=3 "
                f"-o StrictHostKeyChecking=accept-new "  # Better than 'no'
                f"-o Compression=yes"
            )

            # Build rsync command
            rsync_cmd = [
                "rsync",
                "-avz",
                f"--timeout={timeout * 2}",
                f"--compress-level={self.options['compress_level']}",
                f"--files-from={self.temp_file_list}",
                "-e", ssh_cmd
            ]
            
            # Add bandwidth limit if specified
            if self.options['bwlimit']:
                rsync_cmd.append(f"--bwlimit={self.options['bwlimit']}")
            
            rsync_cmd.extend([
                source_dir,
                f"{server_user}@{server_ip}:{remote_dir}"
            ])

            # Execute sync
            result = subprocess.run(
                rsync_cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute max
            )

            if result.returncode == 0:
                # Success! Update marker timestamp to now
                os.utime(self.marker_file, None)
                
                # Update statistics with daily counter
                from datetime import datetime
                now = datetime.now()
                today = now.strftime('%Y-%m-%d')
                
                # Reset daily counter if it's a new day
                if self.today_date != today:
                    self.today_synced = 0
                    self.today_date = today
                
                self.today_synced += file_count
                self.total_synced += file_count
                self.last_successful_sync = time.time()
                self.last_sync_time = time.time()
                self.last_sync_count = file_count
                
                msg = f"Sync:{file_count}"
                self.update_status(msg)
                logging.info(f"[WireGuard] Successfully synced {file_count} files. Today: {self.today_synced}, Total: {self.total_synced}")
                
                # Reset to "Up" after 10 seconds
                self.status_timer = threading.Timer(10.0, self.update_status, ["Up"])
                self.status_timer.start()
                
            else:
                # Partial success or failure
                if result.returncode in [23, 24]:
                    # Code 23: Partial transfer, some files transferred
                    # Code 24: Source files vanished (not critical)
                    logging.warning(f"[WireGuard] Partial sync (code {result.returncode})")
                    # Still update marker for files that did transfer
                    os.utime(self.marker_file, None)
                    self.last_sync_time = time.time()
                else:
                    logging.error(f"[WireGuard] Sync failed (code {result.returncode}): {result.stderr}")
                
                # Check for connection issues
                if any(err in result.stderr.lower() for err in 
                       ["connection refused", "unreachable", "no route", "timeout"]):
                    logging.warning("[WireGuard] Connection appears dead. Triggering reconnection...")
                    self.update_status("Down")
                    self._cleanup_interface()
                    # Will reconnect on next internet_available call

        except subprocess.TimeoutExpired:
            logging.error("[WireGuard] Sync timed out (>5min)")
            
        except Exception as e:
            logging.error(f"[WireGuard] Sync exception: {e}")
            
        finally:
            self.last_sync_time = time.time()
            self._cleanup_temp_files()
            self.lock.release()

    def _health_check(self):
        """Perform periodic health check on VPN connection."""
        if not self.options.get('health_check_enabled', True):
            return
        
        now = time.time()
        if now - self.last_health_check < self.health_check_interval:
            return
        
        self.last_health_check = now
        
        # Don't health check if sync is running
        if self.lock.locked():
            return
        
        if self.status == "Up":
            if not self._verify_connection():
                self.consecutive_health_failures += 1
                logging.warning(f"[WireGuard] Health check failed ({self.consecutive_health_failures}/3)")
                
                if self.consecutive_health_failures >= 3:
                    logging.error("[WireGuard] Multiple health check failures. Reconnecting...")
                    self.update_status("Down")
                    self._cleanup_interface()
                    self.consecutive_health_failures = 0
            else:
                self.consecutive_health_failures = 0
                logging.debug("[WireGuard] Health check passed")

    def on_internet_available(self, agent):
        """Called when internet becomes available."""
        if not self.ready or self.shutdown_requested:
            return

        # Check if we need to wait for startup delay (non-blocking)
        if not self.connection_attempted:
            startup_delay = self.options['startup_delay_secs']
            elapsed = time.time() - self.boot_time
            
            if elapsed < startup_delay:
                remaining = int(startup_delay - elapsed)
                if remaining > 0:
                    self.update_status(f"Wait:{remaining}s")
                    logging.debug(f"[WireGuard] Waiting {remaining}s more before connecting")
                    return
            
            # Enough time has passed, attempt connection
            logging.info(f"[WireGuard] Startup delay complete, connecting...")
            self.connection_attempted = True
        
        # Connect if not connected
        if self.status in ["Init", "Down", "Err", "Failed"] or self.status.startswith("Wait:"):
            self._connect()
        
        # Sync if connected
        elif self.status in ["Up"] or self.status.startswith("Sync"):
            # Don't start new sync if one is running
            if self.lock.locked():
                return
            
            # Periodic health check
            self._health_check()
            
            # Check if it's time to sync
            now = time.time()
            if now - self.last_sync_time >= self.sync_interval:
                threading.Thread(
                    target=self._sync_handshakes,
                    name="WireGuard-Sync",
                    daemon=True
                ).start()

    def on_webhook(self, path, request):
        """Handle web UI requests for WireGuard statistics."""
        from datetime import datetime
        
        # Get WireGuard interface stats
        wg_info = self._get_wireguard_stats()
        
        # Calculate connection uptime
        uptime_str = "Not connected"
        if self.connection_uptime_start > 0 and self.status == "Up":
            uptime_seconds = int(time.time() - self.connection_uptime_start)
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            seconds = uptime_seconds % 60
            uptime_str = f"{hours}h {minutes}m {seconds}s"
        
        # Format last sync time
        last_sync_str = "Never"
        if self.last_successful_sync > 0:
            last_sync_dt = datetime.fromtimestamp(self.last_successful_sync)
            last_sync_str = last_sync_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Calculate next sync
        next_sync_str = "Unknown"
        if self.last_sync_time > 0 and self.status == "Up":
            next_sync_seconds = int(self.sync_interval - (time.time() - self.last_sync_time))
            if next_sync_seconds > 0:
                next_sync_str = f"{next_sync_seconds // 60}m {next_sync_seconds % 60}s"
            else:
                next_sync_str = "Due now"
        
        # Connection status
        is_connected = self.status == "Up"
        status_class = 'status-connected' if is_connected else 'status-disconnected'
        
        # Health status
        health_status = "Healthy"
        health_class = "status-connected"
        if self.consecutive_health_failures > 0:
            health_status = f"Degraded ({self.consecutive_health_failures}/3 failures)"
            health_class = "status-warning"
        elif not is_connected:
            health_status = "Disconnected"
            health_class = "status-disconnected"
        
        # Generate HTML
        html = f"""
        <html>
        <head>
            <title>WireGuard Statistics</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <meta http-equiv="refresh" content="30">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #1a1a1a;
                    color: #e0e0e0;
                    padding: 20px;
                    margin: 0;
                }}
                .container {{
                    max-width: 700px;
                    margin: 0 auto;
                }}
                h1 {{
                    color: #FF6B35;
                    border-bottom: 2px solid #FF6B35;
                    padding-bottom: 10px;
                }}
                .stat-box {{
                    background-color: #2a2a2a;
                    border-left: 4px solid #FF6B35;
                    padding: 15px;
                    margin: 15px 0;
                    border-radius: 4px;
                }}
                .stat-label {{
                    color: #888;
                    font-size: 12px;
                    text-transform: uppercase;
                    margin-bottom: 5px;
                }}
                .stat-value {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #FF6B35;
                }}
                .status-connected {{
                    color: #4CAF50;
                }}
                .status-disconnected {{
                    color: #f44336;
                }}
                .status-warning {{
                    color: #ff9800;
                }}
                .info-row {{
                    display: flex;
                    justify-content: space-between;
                    margin: 8px 0;
                    padding: 8px;
                    background-color: #333;
                    border-radius: 3px;
                }}
                .info-label {{
                    color: #888;
                }}
                .info-value {{
                    color: #e0e0e0;
                    font-weight: bold;
                }}
                .refresh-note {{
                    text-align: center;
                    color: #666;
                    font-size: 12px;
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔒 WireGuard Statistics</h1>
                
                <div class="stat-box">
                    <div class="stat-label">Today's Synced Handshakes</div>
                    <div class="stat-value">{self.today_synced}</div>
                </div>
                
                <div class="stat-box">
                    <div class="stat-label">Total Synced (This Session)</div>
                    <div class="stat-value">{self.total_synced}</div>
                </div>
                
                <div class="stat-box">
                    <div class="stat-label">Connection Status</div>
                    <div class="info-row">
                        <span class="info-label">Status:</span>
                        <span class="info-value {status_class}">
                            {self.status}
                        </span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Health:</span>
                        <span class="info-value {health_class}">{health_status}</span>
                    </div>
                    {f'''
                    <div class="info-row">
                        <span class="info-label">VPN IP:</span>
                        <span class="info-value">{self.options.get('address', 'unknown').split('/')[0]}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Uptime:</span>
                        <span class="info-value">{uptime_str}</span>
                    </div>
                    ''' if is_connected else ''}
                </div>
                
                {f'''
                <div class="stat-box">
                    <div class="stat-label">WireGuard Interface</div>
                    <div class="info-row">
                        <span class="info-label">Interface:</span>
                        <span class="info-value">{wg_info.get('interface', 'wg0')}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Endpoint:</span>
                        <span class="info-value">{wg_info.get('endpoint', 'unknown')}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Last Handshake:</span>
                        <span class="info-value">{wg_info.get('last_handshake', 'Never')}</span>
                    </div>
                    {f'''
                    <div class="info-row">
                        <span class="info-label">Transfer (RX/TX):</span>
                        <span class="info-value">{wg_info.get('transfer', 'unknown')}</span>
                    </div>
                    ''' if wg_info.get('transfer') else ''}
                </div>
                ''' if is_connected else ''}
                
                <div class="stat-box">
                    <div class="stat-label">Sync Information</div>
                    <div class="info-row">
                        <span class="info-label">Last Sync:</span>
                        <span class="info-value">{last_sync_str}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Last Count:</span>
                        <span class="info-value">{self.last_sync_count} files</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Next Sync:</span>
                        <span class="info-value">{next_sync_str}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Sync Interval:</span>
                        <span class="info-value">{self.sync_interval // 60} minutes</span>
                    </div>
                </div>
                
                <div class="stat-box">
                    <div class="stat-label">Connection Statistics</div>
                    <div class="info-row">
                        <span class="info-label">Total Attempts:</span>
                        <span class="info-value">{self.connection_attempts}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Failed Attempts:</span>
                        <span class="info-value">{self.failed_attempts}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Success Rate:</span>
                        <span class="info-value">
                            {f"{((self.connection_attempts - self.failed_attempts) / self.connection_attempts * 100):.1f}%" if self.connection_attempts > 0 else "N/A"}
                        </span>
                    </div>
                </div>
                
                <div class="stat-box">
                    <div class="stat-label">Server Configuration</div>
                    <div class="info-row">
                        <span class="info-label">Server VPN IP:</span>
                        <span class="info-value">{self.options['server_vpn_ip']}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">SSH Port:</span>
                        <span class="info-value">{self.options['server_port']}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Remote Path:</span>
                        <span class="info-value">{self.options['handshake_dir']}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Compression:</span>
                        <span class="info-value">Level {self.options['compress_level']}</span>
                    </div>
                    {f'''
                    <div class="info-row">
                        <span class="info-label">Bandwidth Limit:</span>
                        <span class="info-value">{self.options['bwlimit']} KB/s</span>
                    </div>
                    ''' if self.options.get('bwlimit', 0) > 0 else ''}
                </div>
                
                <div class="refresh-note">
                    Page auto-refreshes every 30 seconds
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def _get_wireguard_stats(self) -> dict:
        """Get WireGuard interface statistics using wg command."""
        stats = {
            'interface': 'wg0',
            'endpoint': self.options.get('peer_endpoint', 'unknown'),
            'last_handshake': 'Never',
            'transfer': None
        }
        
        try:
            result = subprocess.run(
                ["wg", "show", "wg0"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout
                
                # Parse last handshake time
                for line in output.split('\n'):
                    if 'latest handshake:' in line:
                        handshake_str = line.split('latest handshake:')[1].strip()
                        stats['last_handshake'] = handshake_str
                    elif 'transfer:' in line:
                        transfer_str = line.split('transfer:')[1].strip()
                        stats['transfer'] = transfer_str
                        
        except Exception as e:
            logging.debug(f"[WireGuard] Could not get interface stats: {e}")
        
        return stats

    def on_unload(self, ui):
        """Graceful shutdown with cleanup."""
        logging.info("[WireGuard] Shutting down...")
        self.shutdown_requested = True
        
        # Cancel pending timers
        if self.status_timer and self.status_timer.is_alive():
            self.status_timer.cancel()
        
        # Wait for active sync to complete (max 10 seconds)
        if self.lock.locked():
            logging.info("[WireGuard] Waiting for active sync to complete...")
            deadline = time.time() + 10
            while self.lock.locked() and time.time() < deadline:
                time.sleep(0.5)
        
        # Cleanup
        self._cleanup_interface()
        
        # Log final statistics
        if self.connection_uptime_start > 0:
            uptime = int(time.time() - self.connection_uptime_start)
            logging.info(f"[WireGuard] Session stats: {self.total_synced} synced, {uptime}s uptime")
        
        # Remove UI element
        try:
            ui.remove_element('wg_status')
        except:
            pass
        
        logging.info("[WireGuard] Shutdown complete.")
