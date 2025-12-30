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
    __version__ = '2.1'
    __license__ = 'GPL3'
    __description__ = 'Backs up files and cleans up old backups to save space.'

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
        required_options = ['files', 'interval', 'backup_location', 'max_tries']
        for opt in required_options:
            if opt not in self.options or self.options[opt] is None:
                logging.error(f"AUTO-BACKUP: Option '{opt}' is not set.")
                return

        if 'commands' not in self.options or not self.options['commands']:
            self.options['commands'] = ["tar", "czf"]
            
        # Default to keeping 10 backups if not specified
        self.options.setdefault('max_backups_to_keep', 10)
        
        # Get hostname for backup filenames
        self.hostname = socket.gethostname()
            
        self.ready = True
        logging.info(f"AUTO-BACKUP: Plugin loaded for host '{self.hostname}'.")

    def get_interval_seconds(self):
        """Convert interval configuration to seconds."""
        interval = self.options['interval']
        if isinstance(interval, str):
            interval_lower = interval.lower()
            if interval_lower == "daily":
                return 24 * 60 * 60
            elif interval_lower == "hourly":
                return 60 * 60
            else:
                try:
                    return float(interval) * 60
                except ValueError:
                    logging.warning(f"AUTO-BACKUP: Invalid interval '{interval}', defaulting to daily")
                    return 24 * 60 * 60
        elif isinstance(interval, (int, float)):
            return float(interval) * 60
        return 24 * 60 * 60

    def is_backup_due(self):
        """Check if backup is due based on interval."""
        interval_sec = self.get_interval_seconds()
        try:
            last_backup = os.path.getmtime(self.status_file)
        except OSError:
            return True
        return (time.time() - last_backup) >= interval_sec

    def _cleanup_old_backups(self):
        """Deletes the oldest backups if we exceed the limit."""
        try:
            backup_dir = self.options['backup_location']
            max_keep = self.options.get('max_backups_to_keep', 10)
            
            if max_keep <= 0:
                logging.warning("AUTO-BACKUP: max_backups_to_keep is 0 or negative, skipping cleanup")
                return

            # Filter by this device's hostname to avoid deleting other backups
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
                        logging.info(f"AUTO-BACKUP: Deleted old backup: {os.path.basename(old_file)}")
                    except OSError as e:
                        logging.error(f"AUTO-BACKUP: Failed to delete {old_file}: {e}")
            else:
                logging.debug(f"AUTO-BACKUP: {len(files)} backups found, within limit of {max_keep}")
                        
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

                # Add timestamp to filename to prevent overwrites
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                backup_file = os.path.join(backup_location, f"{pwnagotchi_name}-backup-{timestamp}.tar.gz")

                display = agent.view()
                
                logging.info(f"AUTO-BACKUP: Starting backup process to {backup_file}...")
                display.set('status', 'Backing up...')
                display.update()

                # Build command
                command_list = list(self.options['commands'])
                command_list.append(backup_file)

                # Add exclusions
                for pattern in self.options.get('exclude', []):
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
            # Always clear the in-progress flag
            self.backup_in_progress = False

    def on_internet_available(self, agent):
        """Triggered when internet becomes available."""
        # Check if plugin is ready
        if not self.ready:
            return
        
        # Check if max tries exceeded
        if self.options['max_tries'] and self.tries >= self.options['max_tries']:
            logging.debug(f"AUTO-BACKUP: Max tries ({self.options['max_tries']}) exceeded, skipping backup")
            return

        # Check if backup is due
        if not self.is_backup_due():
            now = time.time()
            # Log status once per hour to avoid spam
            if now - self.last_not_due_logged > 3600:
                next_backup = self.get_interval_seconds() - (now - os.path.getmtime(self.status_file))
                logging.debug(f"AUTO-BACKUP: Backup not due yet. Next backup in ~{int(next_backup/3600)} hours")
                self.last_not_due_logged = now
            return

        # Check if files exist
        existing_files = list(filter(os.path.exists, self.options['files']))
        if not existing_files:
            logging.warning("AUTO-BACKUP: No files to backup exist")
            return

        # Prevent multiple simultaneous backups
        if self.backup_in_progress:
            logging.debug("AUTO-BACKUP: Backup already in progress, skipping")
            return
        
        # Check if lock is already held (extra safety)
        if self.lock.locked():
            logging.debug("AUTO-BACKUP: Lock already held, skipping")
            return

        # Set flag before starting thread to prevent race condition
        self.backup_in_progress = True
        
        # Start backup in daemon thread so it doesn't prevent shutdown
        backup_thread = threading.Thread(
            target=self._run_backup_thread, 
            args=(agent, existing_files),
            daemon=True,
            name="AutoBackupThread"
        )
        backup_thread.start()
        logging.debug("AUTO-BACKUP: Backup thread started")
