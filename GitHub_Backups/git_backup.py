import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import logging
import os
import shutil
import subprocess
from datetime import datetime
import socket
import fnmatch
import json


class git_backup(plugins.Plugin):
    __author__ = 'WPA2'
    __version__ = '2.1.0'
    __license__ = 'GPL3'
    __description__ = 'Simple Git backup for Pwnagotchi - mirrors files to GitHub with auto-restore script'

    # ===== HARDCODED DEFAULTS =====
    DEFAULT_FILES = [
        "/etc/pwnagotchi/",
        "/usr/local/share/pwnagotchi/custom-plugins",
        "/home/pi/handshakes",
        "/root/peers",
        "/root/.api-report.json",
        "/home/pi/.wpa_sec_uploads",
        "/root/.ssh",
        "/etc/ssh/",
        "/root/.bashrc",
        "/root/.profile",
        "/home/pi/.bashrc",
        "/home/pi/.profile",
    ]

    EXCLUDES = [
        "*/logs/*",
        "*.pyc",
        "*__pycache__*",
        "*.tmp",
        "*.bak",
        "*.log",
    ]

    BACKUP_DIR = "/home/pi/git-backup-repo"
    STATUS_FILE = "/root/.git-backup-status.json"

    def __init__(self):
        self.ready = False
        self.ui_status = "---"

    def _load_status(self):
        """Load status from JSON file"""
        try:
            if os.path.exists(self.STATUS_FILE):
                with open(self.STATUS_FILE, 'r') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return {}

    def _save_status(self, data):
        """Save status to JSON file"""
        try:
            with open(self.STATUS_FILE, 'w') as f:
                json.dump(data, f)
        except IOError as e:
            logging.warning(f"[git-backup] Could not save status: {e}")

    def on_loaded(self):
        logging.info("[git-backup] Loading plugin...")

        # Validate required config
        if 'github_repo' not in self.options:
            logging.error("[git-backup] 'github_repo' not set in config.toml - plugin disabled")
            logging.error("[git-backup] Add: main.plugins.git_backup.github_repo = \"git@github.com:USER/REPO.git\"")
            return

        # Load options with defaults
        self.github_repo = self.options['github_repo']
        self.interval = self.options.get('interval', 2) * 3600  # hours -> seconds (default 2 hours)
        self.extra_files = self.options.get('extra_files', [])
        self.ssh_key = self.options.get('ssh_key', '/home/pi/.ssh/id_rsa')

        # Validate SSH key exists
        if not os.path.exists(self.ssh_key):
            logging.error(f"[git-backup] SSH key not found: {self.ssh_key}")
            logging.error("[git-backup] Generate one with: ssh-keygen -t ed25519 -f /home/pi/.ssh/id_rsa")
            return

        self.ready = True
        logging.info(f"[git-backup] Ready - interval: {self.options.get('interval', 2)}h, repo: {self.github_repo}")

    def on_ui_setup(self, ui):
        with ui._lock:
            ui.add_element('git_backup', LabeledValue(
                color=BLACK,
                label='B',
                value='---',
                position=(ui.width() - 35, 0),
                label_font=fonts.Small,
                text_font=fonts.Small
            ))

    def on_ui_update(self, ui):
        with ui._lock:
            ui.set('git_backup', self.ui_status)

    def on_internet_available(self, agent):
        if not self.ready:
            return

        # Check cooldown
        status = self._load_status()
        last_backup = status.get('last_backup')
        if last_backup:
            try:
                last_time = datetime.fromisoformat(last_backup)
                elapsed = (datetime.now() - last_time).total_seconds()
                if elapsed < self.interval:
                    hours_left = (self.interval - elapsed) / 3600
                    logging.debug(f"[git-backup] Cooldown: {hours_left:.1f}h remaining")
                    return
            except ValueError:
                pass  # Invalid date, proceed with backup

        logging.info("[git-backup] Internet available, starting backup...")
        self._perform_backup()

    def _git_env(self):
        """Environment variables for git with SSH key"""
        env = os.environ.copy()
        env['GIT_SSH_COMMAND'] = f'ssh -i {self.ssh_key} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
        return env

    def _run_git(self, args, check=True):
        """Run a git command in the backup directory"""
        result = subprocess.run(
            ['git'] + args,
            cwd=self.BACKUP_DIR,
            env=self._git_env(),
            capture_output=True,
            text=True
        )
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, args, result.stdout, result.stderr)
        return result

    def _init_repo(self):
        """Initialize the local git repo (one-way push only)"""
        git_dir = os.path.join(self.BACKUP_DIR, '.git')

        # Already initialized
        if os.path.isdir(git_dir):
            logging.debug("[git-backup] Repo already exists")
            return True

        logging.info("[git-backup] Initializing repository...")

        try:
            # Clean slate
            if os.path.exists(self.BACKUP_DIR):
                shutil.rmtree(self.BACKUP_DIR)

            # Init fresh - one way push, never clone
            os.makedirs(self.BACKUP_DIR, exist_ok=True)
            
            subprocess.run(['git', 'init'], cwd=self.BACKUP_DIR, check=True, capture_output=True)
            subprocess.run(['git', 'remote', 'add', 'origin', self.github_repo], cwd=self.BACKUP_DIR, check=True, capture_output=True)
            subprocess.run(['git', 'checkout', '-b', 'main'], cwd=self.BACKUP_DIR, check=True, capture_output=True)
            
            self._configure_git_user()

            logging.info("[git-backup] Initialized new repository")
            return True

        except Exception as e:
            logging.error(f"[git-backup] Failed to initialize repo: {e}")
            return False

    def _configure_git_user(self):
        """Set git user config for commits"""
        hostname = socket.gethostname()
        self._run_git(['config', 'user.email', f'{hostname}@pwnagotchi.local'], check=False)
        self._run_git(['config', 'user.name', f'Pwnagotchi ({hostname})'], check=False)
        # Fix ownership warning (plugin runs as root)
        subprocess.run(['git', 'config', '--global', '--add', 'safe.directory', self.BACKUP_DIR], 
                      capture_output=True, check=False)

    def _should_exclude(self, filepath):
        """Check if file matches any exclusion pattern"""
        for pattern in self.EXCLUDES:
            if fnmatch.fnmatch(filepath, pattern):
                return True
            if fnmatch.fnmatch(os.path.basename(filepath), pattern):
                return True
        return False

    def _copy_files(self):
        """Copy backup files to repo directory, mirroring structure"""
        all_files = self.DEFAULT_FILES + self.extra_files
        copied_count = 0
        errors = []

        for src_path in all_files:
            if not os.path.exists(src_path):
                logging.debug(f"[git-backup] Skipping (not found): {src_path}")
                continue

            try:
                if os.path.isfile(src_path):
                    copied_count += self._copy_single_file(src_path)
                    logging.debug(f"[git-backup] Copied file: {src_path}")

                elif os.path.isdir(src_path):
                    dir_count = self._copy_directory(src_path)
                    copied_count += dir_count
                    if dir_count > 0:
                        logging.info(f"[git-backup] Copied {dir_count} changed files from {src_path}")

            except Exception as e:
                errors.append(f"{src_path}: {e}")
                logging.warning(f"[git-backup] Error copying {src_path}: {e}")

        if errors:
            logging.warning(f"[git-backup] {len(errors)} files had errors")

        return copied_count

    def _copy_single_file(self, src_path):
        """Copy a single file to backup directory if changed"""
        if self._should_exclude(src_path):
            return 0

        # Mirror the path structure: /etc/pwnagotchi/config.toml -> repo/etc/pwnagotchi/config.toml
        rel_path = src_path.lstrip('/')
        dest_path = os.path.join(self.BACKUP_DIR, rel_path)

        # Skip if destination exists and is same or newer (unchanged)
        if os.path.exists(dest_path):
            src_mtime = os.path.getmtime(src_path)
            dest_mtime = os.path.getmtime(dest_path)
            src_size = os.path.getsize(src_path)
            dest_size = os.path.getsize(dest_path)
            
            # Skip if same size and dest is same age or newer
            if src_size == dest_size and dest_mtime >= src_mtime:
                return 0

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(src_path, dest_path)
        return 1

    def _copy_directory(self, src_dir):
        """Recursively copy a directory to backup"""
        copied = 0

        for root, dirs, files in os.walk(src_dir):
            # Filter out excluded directories in-place
            dirs[:] = [d for d in dirs if not self._should_exclude(os.path.join(root, d))]

            for filename in files:
                src_file = os.path.join(root, filename)
                if not self._should_exclude(src_file):
                    try:
                        copied += self._copy_single_file(src_file)
                    except (PermissionError, OSError) as e:
                        logging.debug(f"[git-backup] Could not copy {src_file}: {e}")

        return copied

    def _generate_restore_script(self):
        """Generate restore.sh for easy recovery"""
        hostname = socket.gethostname()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

        script_content = f'''#!/bin/bash
# ============================================
# Pwnagotchi Restore Script
# Generated: {timestamp}
# Source: {hostname}
# ============================================
#
# Usage:
#   git clone git@github.com:YOUR/REPO.git
#   cd REPO
#   sudo ./restore.sh
#

set -e

RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${{RED}}Error: Please run as root${{NC}}"
    echo "Usage: sudo ./restore.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo " Pwnagotchi Restore"
echo " From backup: {hostname}"
echo "========================================"
echo ""

read -p "This will overwrite existing files. Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Stopping pwnagotchi service..."
systemctl stop pwnagotchi 2>/dev/null || true

echo ""
echo "Restoring files..."

# Restore all backed-up directories
for dir in etc home root usr; do
    if [ -d "$SCRIPT_DIR/$dir" ]; then
        echo -e "  ${{YELLOW}}Processing /$dir...${{NC}}"
        cp -r "$SCRIPT_DIR/$dir"/* "/$dir/" 2>/dev/null || true
    fi
done

echo ""
echo "Fixing permissions..."

# SSH permissions (critical!)
if [ -d /root/.ssh ]; then
    chown -R root:root /root/.ssh
    chmod 700 /root/.ssh
    chmod 600 /root/.ssh/* 2>/dev/null || true
    echo -e "  ${{GREEN}}✓${{NC}} /root/.ssh"
fi

if [ -d /etc/ssh ]; then
    chown -R root:root /etc/ssh
    chmod 644 /etc/ssh/*.pub 2>/dev/null || true
    chmod 600 /etc/ssh/ssh_host_*_key 2>/dev/null || true
    echo -e "  ${{GREEN}}✓${{NC}} /etc/ssh"
fi

# Pi home directory
if [ -d /home/pi ]; then
    chown -R pi:pi /home/pi 2>/dev/null || true
    echo -e "  ${{GREEN}}✓${{NC}} /home/pi"
fi

echo ""
echo -e "${{GREEN}}========================================"
echo " Restore complete!"
echo "========================================${{NC}}"
echo ""
echo "Next steps:"
echo "  1. Review /etc/pwnagotchi/config.toml"
echo "  2. sudo systemctl start pwnagotchi"
echo ""
'''

        script_path = os.path.join(self.BACKUP_DIR, 'restore.sh')
        with open(script_path, 'w') as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)

    def _generate_readme(self):
        """Generate a README for the backup repo"""
        hostname = socket.gethostname()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        readme = f'''# Pwnagotchi Backup - {hostname}

Last backup: {timestamp}

## Quick Restore

```bash
git clone git@github.com:YOUR/REPO.git pwnagotchi-backup
cd pwnagotchi-backup
sudo ./restore.sh
```

## Manual Restore

Files are stored in their original directory structure. Copy what you need:

```bash
# Example: restore just handshakes
sudo cp -r home/pi/handshakes /home/pi/

# Example: restore config
sudo cp -r etc/pwnagotchi /etc/
```

## What's Backed Up

- `/etc/pwnagotchi/` - Main config
- `/usr/local/share/pwnagotchi/custom-plugins` - Custom plugins
- `/home/pi/handshakes` - Captured handshakes
- `/root/peers` - Peer data
- `/root/.ssh` & `/etc/ssh` - SSH keys
- Shell profiles

---
*Generated by [git-backup](https://github.com/wpa-2/pwnagotchi-plugins) plugin*
'''
        
        readme_path = os.path.join(self.BACKUP_DIR, 'README.md')
        with open(readme_path, 'w') as f:
            f.write(readme)

    def _git_commit_and_push(self):
        """Stage, commit, and push changes"""
        hostname = socket.gethostname()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

        try:
            # Stage all changes
            self._run_git(['add', '-A'])

            # Check if there's anything to commit
            result = self._run_git(['status', '--porcelain'], check=False)
            if not result.stdout.strip():
                logging.info("[git-backup] No changes to commit")
                return True

            # Commit
            commit_msg = f"Backup {hostname} - {timestamp}"
            self._run_git(['commit', '-m', commit_msg])

            # Force push (one-way backup, always overwrite remote)
            self._run_git(['push', '--force', '-u', 'origin', 'main'])

            logging.info("[git-backup] Push successful")
            return True

        except subprocess.CalledProcessError as e:
            err_msg = e.stderr if e.stderr else str(e)
            logging.error(f"[git-backup] Git operation failed: {err_msg}")
            return False

    def _perform_backup(self):
        """Main backup routine"""
        self.ui_status = "..."

        try:
            # Step 1: Initialize repo if needed
            if not self._init_repo():
                self.ui_status = "ERR"
                return

            # Step 2: Copy files to repo (only changed files)
            count = self._copy_files()
            if count > 0:
                logging.info(f"[git-backup] {count} files changed/added")
            else:
                logging.info(f"[git-backup] No file changes detected")

            # Step 3: Generate helper files
            self._generate_restore_script()
            self._generate_readme()

            # Step 4: Commit and push
            if self._git_commit_and_push():
                # Success - update status
                self._save_status({'last_backup': datetime.now().isoformat()})
                self.ui_status = datetime.now().strftime('%H:%M')
                logging.info("[git-backup] Backup complete!")
            else:
                self.ui_status = "ERR"
                logging.error("[git-backup] Backup failed during git push")

        except Exception as e:
            self.ui_status = "ERR"
            logging.error(f"[git-backup] Backup failed: {e}")

    def _time_ago(self, dt):
        """Convert datetime to human readable time ago string"""
        now = datetime.now()
        diff = now - dt
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return 'just now'
        elif seconds < 3600:
            mins = int(seconds // 60)
            return f'{mins} minute{"s" if mins != 1 else ""} ago'
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f'{hours} hour{"s" if hours != 1 else ""} ago'
        elif seconds < 604800:
            days = int(seconds // 86400)
            return f'{days} day{"s" if days != 1 else ""} ago'
        else:
            weeks = int(seconds // 604800)
            return f'{weeks} week{"s" if weeks != 1 else ""} ago'

    def on_webhook(self, path, request):
        """Allow manual backup trigger via webhook"""
        status = self._load_status()
        last_raw = status.get('last_backup', None)
        
        # Format the timestamp nicely
        if last_raw:
            try:
                last_dt = datetime.fromisoformat(last_raw)
                last = last_dt.strftime('%d %b %Y at %H:%M')
                time_ago = self._time_ago(last_dt)
            except:
                last = 'Unknown'
                time_ago = ''
        else:
            last = 'Never'
            time_ago = ''
        
        # Check if backup was just triggered
        message = ''
        if request.args.get('backup') == '1':
            if self.ready:
                self._perform_backup()
                status = self._load_status()
                last_raw = status.get('last_backup', None)
                if last_raw:
                    try:
                        last_dt = datetime.fromisoformat(last_raw)
                        last = last_dt.strftime('%d %b %Y at %H:%M')
                        time_ago = 'just now'
                    except:
                        pass
                message = '<div class="success">✓ Backup complete!</div>'
            else:
                message = '<div class="error">✗ Plugin not ready - check logs</div>'
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Git Backup</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            color: #fff;
        }}
        .container {{
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            max-width: 400px;
            width: 100%;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .header h1 {{
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 5px;
        }}
        .header .icon {{
            font-size: 48px;
            margin-bottom: 15px;
        }}
        .status-card {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 25px;
            text-align: center;
        }}
        .status-label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: rgba(255, 255, 255, 0.5);
            margin-bottom: 8px;
        }}
        .status-value {{
            font-size: 20px;
            font-weight: 500;
        }}
        .status-ago {{
            font-size: 13px;
            color: rgba(255, 255, 255, 0.4);
            margin-top: 5px;
        }}
        .backup-btn {{
            display: block;
            width: 100%;
            padding: 16px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
            border: none;
            cursor: pointer;
        }}
        .backup-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        }}
        .backup-btn:active {{
            transform: translateY(0);
        }}
        .backup-btn.loading {{
            pointer-events: none;
            opacity: 0.8;
        }}
        .spinner {{
            display: inline-block;
            width: 18px;
            height: 18px;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 0.8s linear infinite;
            margin-right: 8px;
            vertical-align: middle;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        .success {{
            background: rgba(46, 213, 115, 0.15);
            border: 1px solid rgba(46, 213, 115, 0.3);
            color: #2ed573;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
            font-weight: 500;
        }}
        .error {{
            background: rgba(255, 71, 87, 0.15);
            border: 1px solid rgba(255, 71, 87, 0.3);
            color: #ff4757;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
            font-weight: 500;
        }}
        .footer {{
            text-align: center;
            margin-top: 25px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.3);
        }}
        .footer a {{
            color: rgba(255, 255, 255, 0.4);
            text-decoration: none;
            transition: color 0.2s;
        }}
        .footer a:hover {{
            color: rgba(255, 255, 255, 0.7);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="icon">📦</div>
            <h1>Git Backup</h1>
        </div>
        {message}
        <div class="status-card">
            <div class="status-label">Last Backup</div>
            <div class="status-value">{last}</div>
            <div class="status-ago">{time_ago}</div>
        </div>
        <a href="?backup=1" class="backup-btn" id="backupBtn" onclick="startBackup(event)">Backup Now</a>
        <div class="footer">
            <a href="https://github.com/wpa-2/pwnagotchi-plugins" target="_blank">Pwnagotchi Git Backup v2.1.0</a>
        </div>
    </div>
    <script>
        function startBackup(e) {{
            var btn = document.getElementById('backupBtn');
            btn.classList.add('loading');
            btn.innerHTML = '<span class="spinner"></span>Backing up...';
        }}
    </script>
</body>
</html>'''
        return html
