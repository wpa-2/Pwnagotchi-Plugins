import pwnagotchi.plugins as plugins
from pwnagotchi.utils import StatusFile
import logging
import os
import subprocess
import time
import socket
import threading
import glob

class AutoBackup(plugins.Plugin):
    __author__ = 'WPA2'
    __version__ = '2.2'
    __license__ = 'GPL3'
    __description__ = 'Backs up Pwnagotchi configuration and data, keeping recent backups.'

    # Hardcoded defaults for Pwnagotchi
    DEFAULT_FILES = [
        "/root/settings.yaml",
        "/root/client_secrets.json",
        "/root/.api-report.json",
        "/root/.ssh",
        "/root/.bashrc",
        "/root/.profile",
        "/root/peers",
        "/etc/pwnagotchi/",
        "/usr/local/share/pwnagotchi/custom-plugins",
        "/etc/ssh/",
        "/home/pi/handshakes/",
        "/home/pi/.bashrc",
        "/home/pi/.profile",
        "/home/pi/.wpa_sec_uploads",
    ]
    
    DEFAULT_INTERVAL_SECONDS = 60 * 60  # 60 minutes
    DEFAULT_MAX_BACKUPS = 3
    DEFAULT_EXCLUDE = [
        "/etc/pwnagotchi/logs/*",
        "*.bak",
        "*.tmp",
    ]

    def __init__(self):
        self.ready = False
        self.tries = 0
        self.last_not_due_logged = 0
        self.status_file = '/root/.auto-backup'
        self.status = StatusFile(self.status_file)
        self.lock = threading.Lock()
        self.backup_in_progress = False
        self.hostname = socket.gethostname()

    def on_loaded(self):
        """Validate only required option: backup_location"""
        if 'backup_location' not in self.options or self.options['backup_location'] is None:
            logging.error("AUTO-BACKUP: Option 'backup_location' is not set.")
            return

        self.hostname = socket.gethostname()
        
        # Read config with internal defaults - DO NOT modify self.options
        self.files = self.options.get('files', self.DEFAULT_FILES)
        self.interval_seconds = self.options.get('interval_seconds', self.DEFAULT_INTERVAL_SECONDS)
        self.max_backups = self.options.get('max_backups_to_keep', self.DEFAULT_MAX_BACKUPS)
        self.exclude = self.options.get('exclude', self.DEFAULT_EXCLUDE)
        self.include = self.options.get('include', [])
        
        # Handle commands: if old format, use correct default internally
        commands = self.options.get('commands', ["tar", "czf"])
        if isinstance(commands, str) or (isinstance(commands, list) and len(commands) == 1 and isinstance(commands[0], str) and '{' in str(commands)):
            logging.warning("AUTO-BACKUP: Old command format detected in config, using default: tar czf")
            self.commands = ["tar", "czf"]
        elif not commands:
            self.commands = ["tar", "czf"]
        else:
            self.commands = commands
        
        # Validate include paths if specified
        if self.include:
            if not isinstance(self.include, list):
                self.include = [self.include]
            
            for path in self.include:
                if not os.path.exists(path):
                    logging.warning(f"AUTO-BACKUP: include path '{path}' does not exist, will skip if still missing at backup time")
            
        self.ready = True
        include_msg = f", includes: {len(self.include)} additional path(s)" if self.include else ""
        logging.info(f"AUTO-BACKUP: Plugin loaded for host '{self.hostname}'. Interval: 60min, Backups kept: {self.max_backups}{include_msg}")

    def is_backup_due(self):
        """Check if backup is due based on interval."""
        try:
            last_backup = os.path.getmtime(self.status_file)
        except OSError:
            return True
        return (time.time() - last_backup) >= self.interval_seconds

    def _cleanup_old_backups(self):
        """Deletes the oldest backups if we exceed the limit."""
        try:
            backup_dir = self.options['backup_location']
            max_keep = self.max_backups
            
            # Filter by this device's hostname
            search_pattern = os.path.join(backup_dir, f"{self.hostname}-backup-*.tar.gz")
            files = glob.glob(search_pattern)
            
            if not files:
                logging.debug("AUTO-BACKUP: No backup files found for cleanup")
                return
            
            # Sort files by modification time (oldest first)
            files.sort(key=os.path.getmtime)
            
            # Calculate how many to delete
            if len(files) > max_keep:
                num_to_delete = len(files) - max_keep
                logging.info(f"AUTO-BACKUP: Found {len(files)} backups, keeping {max_keep}, deleting {num_to_delete} old backup(s)...")
                
                for old_file in files[:num_to_delete]:
                    try:
                        os.remove(old_file)
                        logging.info(f"AUTO-BACKUP: Deleted: {os.path.basename(old_file)}")
                    except OSError as e:
                        logging.error(f"AUTO-BACKUP: Failed to delete {old_file}: {e}")
                        
        except Exception as e:
            logging.error(f"AUTO-BACKUP: Cleanup error: {e}")

    def _run_backup_thread(self, agent, existing_files):
        """Execute backup in separate thread."""
        try:
            with self.lock:
                # Get pwnagotchi name from config if available, fallback to hostname
                global_config = getattr(agent, 'config', None)
                if callable(global_config):
                    global_config = global_config()
                if global_config is None:
                    global_config = {}
                
                pwnagotchi_name = global_config.get('main', {}).get('name', self.hostname)
                backup_location = self.options['backup_location']
                
                # Create backup directory if it doesn't exist
                if not os.path.exists(backup_location):
                    try:
                        os.makedirs(backup_location)
                        logging.info(f"AUTO-BACKUP: Created backup directory: {backup_location}")
                    except OSError as e:
                        logging.error(f"AUTO-BACKUP: Failed to create backup directory: {e}")
                        return

                # Add timestamp to filename
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                backup_file = os.path.join(backup_location, f"{pwnagotchi_name}-backup-{timestamp}.tar.gz")

                display = agent.view()
                
                logging.info(f"AUTO-BACKUP: Starting backup to {backup_file}...")
                display.set('status', 'Backing up...')
                display.update()

                # Build command
                command_list = list(self.commands)
                command_list.append(backup_file)

                # Add exclusions
                for pattern in self.exclude:
                    command_list.append(f"--exclude={pattern}")
                
                # Add files to backup
                command_list.extend(existing_files)
                
                # Execute backup command
                process = subprocess.Popen(
                    command_list,
                    shell=False,
                    stdin=None,
                    stdout=open("/dev/null", "w"),
                    stderr=subprocess.PIPE
                )
                _, stderr_output = process.communicate()

                if process.returncode != 0:
                    raise OSError(f"Backup command failed with code {process.returncode}: {stderr_output.decode('utf-8').strip()}")

                logging.info(f"AUTO-BACKUP: Backup successful: {backup_file}")
                
                # Run cleanup after successful backup
                self._cleanup_old_backups()
                
                display.set('status', 'Backup done!')
                display.update()
                
                # Update status file timestamp
                self.status.update()
                
                # Reset try counter on success
                self.tries = 0

        except Exception as e:
            self.tries += 1
            logging.error(f"AUTO-BACKUP: Backup error (attempt {self.tries}): {e}")
            try:
                display.set('status', 'Backup failed!')
                display.update()
            except:
                pass
        finally:
            self.backup_in_progress = False

    def on_internet_available(self, agent):
        """Triggered when internet becomes available."""
        if not self.ready:
            return
        
        if self.tries >= 3:  # Hardcoded max_tries
            logging.debug(f"AUTO-BACKUP: Max tries (3) exceeded, skipping backup")
            return

        if not self.is_backup_due():
            now = time.time()
            # Log status once per hour to avoid spam
            if now - self.last_not_due_logged > 3600:
                try:
                    last_backup = os.path.getmtime(self.status_file)
                    next_backup = self.interval_seconds - (now - last_backup)
                    logging.debug(f"AUTO-BACKUP: Backup not due yet. Next backup in ~{int(next_backup/3600)}h {int((next_backup%3600)/60)}m")
                except:
                    pass
                self.last_not_due_logged = now
            return

        # Check if files exist
        existing_files = list(filter(os.path.exists, self.files))
        
        # Add include paths if specified
        if self.include:
            for path in self.include:
                if os.path.exists(path):
                    existing_files.append(path)
                    logging.debug(f"AUTO-BACKUP: Added include path: {path}")
                else:
                    logging.debug(f"AUTO-BACKUP: Include path does not exist, skipping: {path}")
        
        if not existing_files:
            logging.warning("AUTO-BACKUP: No files to backup exist")
            return

        # Prevent multiple simultaneous backups
        if self.backup_in_progress or self.lock.locked():
            logging.debug("AUTO-BACKUP: Backup already in progress, skipping")
            return

        self.backup_in_progress = True
        
        # Start backup in daemon thread
        backup_thread = threading.Thread(
            target=self._run_backup_thread, 
            args=(agent, existing_files),
            daemon=True,
            name="AutoBackupThread"
        )
        backup_thread.start()
        logging.debug("AUTO-BACKUP: Backup thread started")
