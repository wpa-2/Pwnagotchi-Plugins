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
    __version__ = '2.0'
    __license__ = 'GPL3'
    __description__ = 'Backs up files and cleans up old backups to save space.'

    def __init__(self):
        self.ready = False
        self.tries = 0
        self.last_not_due_logged = 0
        self.status_file = '/root/.auto-backup'
        self.status = StatusFile(self.status_file)
        self.lock = threading.Lock()

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
            
        self.ready = True
        logging.info("AUTO-BACKUP: Plugin loaded.")

    def get_interval_seconds(self):
        interval = self.options['interval']
        if isinstance(interval, str):
            if interval.lower() == "daily":
                return 24 * 60 * 60
            elif interval.lower() == "hourly":
                return 60 * 60
            else:
                try:
                    return float(interval) * 60
                except ValueError:
                    return 24 * 60 * 60
        elif isinstance(interval, (int, float)):
            return float(interval) * 60
        return 24 * 60 * 60

    def is_backup_due(self):
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
            max_keep = self.options['max_backups_to_keep']
            pwnagotchi_name = socket.gethostname() # or get from config if available

            # Find all tar.gz files in the backup directory
            # We filter by name to make sure we don't delete other stuff
            search_pattern = os.path.join(backup_dir, f"*-backup-*.tar.gz")
            files = glob.glob(search_pattern)
            
            # Sort files by creation time (Oldest first)
            files.sort(key=os.path.getmtime)
            
            # Calculate how many to delete
            if len(files) > max_keep:
                num_to_delete = len(files) - max_keep
                logging.info(f"AUTO-BACKUP: Cleaning up {num_to_delete} old backups...")
                
                for i in range(num_to_delete):
                    try:
                        os.remove(files[i])
                        logging.debug(f"AUTO-BACKUP: Deleted old file {files[i]}")
                    except OSError as e:
                        logging.error(f"AUTO-BACKUP: Failed to delete {files[i]}: {e}")
                        
        except Exception as e:
            logging.error(f"AUTO-BACKUP: Cleanup error: {e}")

    def _run_backup_thread(self, agent, existing_files):
        with self.lock:
            global_config = getattr(agent, 'config', None)
            if callable(global_config):
                global_config = global_config()
            if global_config is None:
                global_config = {}
            
            pwnagotchi_name = global_config.get('main', {}).get('name', socket.gethostname())
            backup_location = self.options['backup_location']
            
            if not os.path.exists(backup_location):
                try:
                    os.makedirs(backup_location)
                except OSError:
                    return

            # Add timestamp to filename so they don't overwrite each other
            timestamp = time.strftime("%Y%m%d%H%M%S")
            backup_file = os.path.join(backup_location, f"{pwnagotchi_name}-backup-{timestamp}.tar.gz")

            display = agent.view()
            try:
                logging.info("AUTO-BACKUP: Starting backup process...")
                display.set('status', 'Backing up...')
                display.update()

                command_list = list(self.options['commands'])
                command_list.append(backup_file)

                for pattern in self.options.get('exclude', []):
                    command_list.append(f"--exclude={pattern}")
                
                command_list.extend(existing_files)
                
                process = subprocess.Popen(
                    command_list,
                    shell=False,
                    stdin=None,
                    stdout=open("/dev/null", "w"),
                    stderr=subprocess.PIPE
                )
                _, stderr_output = process.communicate()

                if process.returncode > 0:
                    raise OSError(f"Command failed: {stderr_output.decode('utf-8').strip()}")

                logging.info(f"AUTO-BACKUP: Backup successful: {backup_file}")
                
                # RUN CLEANUP AFTER SUCCESS
                self._cleanup_old_backups()
                
                display.set('status', 'Backup done!')
                display.update()
                self.status.update()
                self.tries = 0

            except Exception as e:
                self.tries += 1
                logging.error(f"AUTO-BACKUP: Backup error: {e}")
                display.set('status', 'Backup failed!')
                display.update()

    def on_internet_available(self, agent):
        if not self.ready: return
        if self.options['max_tries'] and self.tries >= self.options['max_tries']: return

        if not self.is_backup_due():
            now = time.time()
            if now - self.last_not_due_logged > 3600:
                logging.debug("AUTO-BACKUP: Backup not due yet.")
                self.last_not_due_logged = now
            return

        existing_files = list(filter(os.path.exists, self.options['files']))
        if not existing_files: return

        if self.lock.locked(): return

        backup_thread = threading.Thread(target=self._run_backup_thread, args=(agent, existing_files))
        backup_thread.start()
