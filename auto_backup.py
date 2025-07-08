import pwnagotchi.plugins as plugins
from pwnagotchi.utils import StatusFile
import logging
import os
import subprocess
import time
import socket

class AutoBackup(plugins.Plugin):
    __author__ = 'WPA2'
    __version__ = '1.2.1'
    __license__ = 'GPL3'
    __description__ = 'Backs up files when internet is available. Creates compressed, safe backups.'

    def __init__(self):
        self.ready = False
        self.tries = 0
        self.last_not_due_logged = 0
        self.status_file = '/root/.auto-backup'
        self.status = StatusFile(self.status_file)

    def on_loaded(self):
        required_options = ['files', 'interval', 'backup_location', 'max_tries']
        for opt in required_options:
            if opt not in self.options or self.options[opt] is None:
                logging.error(f"AUTO-BACKUP: Option '{opt}' is not set.")
                return

        if 'commands' not in self.options or not self.options['commands']:
            self.options['commands'] = ["tar", "czf"]
            
        self.ready = True
        logging.info("AUTO-BACKUP: Plugin loaded.")

    def get_interval_seconds(self):
        """Converts the interval option from minutes/hours/days into seconds."""
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
                    logging.error("AUTO-BACKUP: Invalid interval format. Defaulting to daily.")
                    return 24 * 60 * 60
        elif isinstance(interval, (int, float)):
            return float(interval) * 60
        else:
            logging.error("AUTO-BACKUP: Unrecognized interval type. Defaulting to daily.")
            return 24 * 60 * 60

    def is_backup_due(self):
        """Determines if enough time has passed since the last backup."""
        interval_sec = self.get_interval_seconds()
        try:
            last_backup = os.path.getmtime(self.status_file)
        except OSError:
            return True
        return (time.time() - last_backup) >= interval_sec

    def on_internet_available(self, agent):
        if not self.ready:
            return

        if self.options['max_tries'] and self.tries >= self.options['max_tries']:
            logging.info("AUTO-BACKUP: Max tries reached, skipping backup.")
            return

        if not self.is_backup_due():
            now = time.time()
            if now - self.last_not_due_logged > 600:
                logging.info("AUTO-BACKUP: Backup not due yet.")
                self.last_not_due_logged = now
            return

        existing_files = list(filter(os.path.exists, self.options['files']))
        if not existing_files:
            logging.warning("AUTO-BACKUP: No files specified in config were found to back up.")
            return

        global_config = getattr(agent, 'config', None)
        if callable(global_config):
            global_config = global_config()
        if global_config is None:
            global_config = {}
        
        pwnagotchi_name = global_config.get('main', {}).get('name', socket.gethostname())
        
        backup_location = self.options['backup_location']
        backup_file = os.path.join(backup_location, f"{pwnagotchi_name}-backup.tar.gz")

        display = agent.view()
        try:
            logging.info("AUTO-BACKUP: Starting backup process...")
            display.set('status', 'Backing up ...')
            display.update()

            command_list = list(self.options['commands'])
            command_list.append(backup_file)

            for pattern in self.options.get('exclude', []):
                command_list.append(f"--exclude={pattern}")
            
            command_list.extend(existing_files)
            
            logging.info(f"AUTO-BACKUP: Running command: {' '.join(command_list)}")

            process = subprocess.Popen(
                command_list,
                shell=False,
                stdin=None,
                stdout=open("/dev/null", "w"),
                stderr=subprocess.PIPE
            )
            _, stderr_output = process.communicate()

            if process.returncode > 0:
                error_message = stderr_output.decode('utf-8').strip()
                raise OSError(f"Command failed with code {process.returncode}: {error_message}")

            logging.info(f"AUTO-BACKUP: Backup successful: {backup_file}")
            display.set('status', 'Backup done!')
            display.update()
            self.status.update()
            self.tries = 0

        except (OSError, subprocess.SubprocessError) as e:
            self.tries += 1
            logging.error(f"AUTO-BACKUP: Backup error: {e}")
            display.set('status', 'Backup failed!')
            display.update()
