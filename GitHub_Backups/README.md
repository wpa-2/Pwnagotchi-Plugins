# Git Backup Plugin for Pwnagotchi

Simple, reliable backup of your Pwnagotchi to GitHub. Files are mirrored in their original directory structure so you can browse them directly on GitHub and restore with a single command.

## Features

- **Automatic backups** - Triggers when internet is available, with configurable cooldown
- **Incremental backups** - Only copies changed files (handles 50k+ handshakes efficiently)
- **Manual backup** - One-click backup via web UI
- **Browsable backups** - Files stored in original structure, viewable on GitHub
- **Git history** - See exactly what changed between backups
- **Auto-generated restore script** - One command recovery
- **One-way sync** - Always force pushes, no merge conflicts ever
- **Display status** - Shows last backup time on Pwnagotchi screen
- **Minimal config** - Just add your GitHub repo URL

## What Gets Backed Up

| Path | Contents |
|------|----------|
| `/etc/pwnagotchi/` | Main config and plugin configs |
| `/usr/local/share/pwnagotchi/custom-plugins` | Your custom plugins |
| `/home/pi/handshakes` | Captured handshakes |
| `/root/peers` | Peer data |
| `/root/.api-report.json` | API reporting data |
| `/home/pi/.wpa_sec_uploads` | WPA-sec upload tracking |
| `/root/.ssh` | Root SSH keys |
| `/etc/ssh/` | Host SSH keys |
| `/root/.bashrc`, `/root/.profile` | Root shell config |
| `/home/pi/.bashrc`, `/home/pi/.profile` | Pi user shell config |

**Excluded automatically:** `*/logs/*`, `*.pyc`, `*__pycache__*`, `*.tmp`, `*.bak`, `*.log`

---

## Installation

### Step 1: Generate SSH Key

On your Pwnagotchi, generate an SSH key for GitHub authentication:

```bash
ssh-keygen -t ed25519 -f /home/pi/.ssh/id_rsa -N ""
```

This creates:
- `/home/pi/.ssh/id_rsa` - Private key (stays on Pwnagotchi)
- `/home/pi/.ssh/id_rsa.pub` - Public key (add to GitHub)

### Step 2: Add Key to GitHub

Display your public key:

```bash
cat /home/pi/.ssh/id_rsa.pub
```

Copy the entire output (starts with `ssh-ed25519`), then:

1. Go to **GitHub.com** → **Settings** → **SSH and GPG keys**
2. Click **New SSH key**
3. Give it a title (e.g., "Pwnagotchi Backup")
4. Paste the public key
5. Click **Add SSH key**

### Step 3: Test SSH Connection

```bash
ssh -T git@github.com
```

You should see:
```
Hi username! You've successfully authenticated, but GitHub does not provide shell access.
```

**Troubleshooting:** If you get "Permission denied", check:
- Key was copied correctly (no extra spaces/newlines)
- Key is added to the correct GitHub account
- No SSH config overriding the key path (check `/home/pi/.ssh/config`)

### Step 4: Create Private Repository

1. Go to **GitHub.com** → **New repository**
2. Name it (e.g., `pwnagotchi-backup`)
3. Select **Private**
4. **Don't** initialize with README (leave empty)
5. Click **Create repository**

Copy the SSH URL: `git@github.com:YOUR_USERNAME/pwnagotchi-backup.git`

### Step 5: Install Plugin

```bash
sudo wget -O /usr/local/share/pwnagotchi/custom-plugins/git_backup.py \
  https://raw.githubusercontent.com/wpa-2/pwnagotchi-plugins/main/git_backup.py
```

### Step 6: Configure

Edit your config:

```bash
sudo nano /etc/pwnagotchi/config.toml
```

Add (minimum required):

```toml
[main.plugins.git_backup]
enabled = true
github_repo = "git@github.com:myuser/pwnagotchi-backup.git"
```

### Step 7: Restart & Verify

```bash
sudo systemctl restart pwnagotchi
```

Check logs:

```bash
pwnlog | grep git-backup
```

You should see:
```
[git-backup] Loading plugin...
[git-backup] Ready - interval: 4h, repo: git@github.com:...
```

---

## Configuration Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `enabled` | Yes | `false` | Enable the plugin |
| `github_repo` | **Yes** | - | SSH URL of your GitHub repo |
| `interval` | No | `4` | Hours between automatic backups |
| `ssh_key` | No | `/home/pi/.ssh/id_rsa` | Path to SSH private key |
| `extra_files` | No | `[]` | Additional files/directories to backup |

### Minimal Config

```toml
[main.plugins.git_backup]
enabled = true
github_repo = "git@github.com:myuser/pwnagotchi-backup.git"
```

### Full Config Example

```toml
[main.plugins.git_backup]
enabled = true
github_repo = "git@github.com:myuser/pwnagotchi-backup.git"
interval = 6
ssh_key = "/home/pi/.ssh/id_rsa"
extra_files = [
    "/root/my-custom-script.sh",
    "/home/pi/my-data/",
    "/etc/my-custom-config.conf",
]
```

---

## Usage

### Automatic Backups

Backups trigger automatically when:
1. Internet becomes available (via `on_internet_available` hook)
2. Enough time has passed since last backup (based on `interval`)

### Manual Backup via Web UI

Visit:
```
http://<pwnagotchi-ip>:8080/plugins/git_backup/
```

Click **"Backup Now"** to trigger immediately (ignores cooldown).

### Manual Backup via Command Line

```bash
curl "http://localhost:8080/plugins/git_backup/?backup=1"
```

### Display Status

The plugin shows backup status on the Pwnagotchi display:

| Display | Meaning |
|---------|---------|
| `---` | No backup yet |
| `HH:MM` | Time of last successful backup |
| `...` | Backup in progress |
| `ERR` | Last backup failed (check logs) |

---

## Restoring from Backup

### Quick Restore (Full)

On a fresh Pwnagotchi or after SD card failure:

```bash
# Clone your backup repo
git clone git@github.com:YOUR_USERNAME/YOUR_REPO.git pwnagotchi-restore
cd pwnagotchi-restore

# Run the auto-generated restore script
sudo ./restore.sh
```

The restore script will:
1. Stop pwnagotchi service
2. Copy all files to their original locations
3. Fix SSH permissions
4. Prompt you to restart

### Manual Restore (Selective)

Files are stored in their original directory structure. Copy only what you need:

```bash
# Clone the repo
git clone git@github.com:YOUR_USERNAME/YOUR_REPO.git pwnagotchi-restore
cd pwnagotchi-restore

# Restore just handshakes
sudo cp -r home/pi/handshakes/* /home/pi/handshakes/

# Restore just config
sudo cp -r etc/pwnagotchi/* /etc/pwnagotchi/

# Restore just custom plugins
sudo cp -r usr/local/share/pwnagotchi/custom-plugins/* /usr/local/share/pwnagotchi/custom-plugins/

# Restore SSH keys (fix permissions after!)
sudo cp -r root/.ssh/* /root/.ssh/
sudo chmod 700 /root/.ssh
sudo chmod 600 /root/.ssh/*
```

### Restore via GitHub Web

You can also download individual files directly from GitHub's web interface - useful for quickly grabbing a config file or checking a setting.

---

## Troubleshooting

### "SSH key not found"

```bash
# Check key exists
ls -la /home/pi/.ssh/id_rsa

# If missing, generate it
ssh-keygen -t ed25519 -f /home/pi/.ssh/id_rsa -N ""

# Fix permissions
chmod 700 /home/pi/.ssh
chmod 600 /home/pi/.ssh/id_rsa
chmod 644 /home/pi/.ssh/id_rsa.pub
```

### "Permission denied (publickey)"

```bash
# Test connection with verbose output
ssh -vT git@github.com
```

Check:
- Public key is added to GitHub
- No SSH config overriding key path: `cat /home/pi/.ssh/config`
- Correct key is being used (look for "Offering public key" in verbose output)

### "Repository not found"

- Verify repo exists on GitHub
- Check spelling in config
- Ensure SSH key has access (is added to correct GitHub account)

### Backup not running automatically

```bash
# Check plugin is loaded
pwnlog | grep git-backup

# Check cooldown status
cat /root/.git-backup-status.json

# Force a backup via web UI
curl "http://localhost:8080/plugins/git_backup/?backup=1"
```

### "Plugin not ready"

Check logs for the specific error:

```bash
pwnlog | grep git-backup
```

Common causes:
- `github_repo` not set in config
- SSH key doesn't exist
- Syntax error in config.toml

### Git push errors

```bash
# Check git status manually
cd /home/pi/git-backup-repo
git status
git remote -v

# Try manual push
GIT_SSH_COMMAND='ssh -i /home/pi/.ssh/id_rsa' git push origin main
```

---

## How It Works

1. **Trigger**: `on_internet_available` hook fires when Pwnagotchi connects to internet
2. **Cooldown check**: Skip if last backup was less than `interval` hours ago
3. **Initialize repo**: Create local git repo (one-time, never clones from remote)
4. **Incremental copy**: Only copy files that have changed (checks mtime + size)
5. **Generate helpers**: Create `restore.sh` and `README.md` in repo
6. **Commit & push**: Stage changes, commit with timestamp, force push to GitHub
7. **Update status**: Save timestamp, update display

**One-way sync**: The plugin always force pushes to GitHub. Your Pwnagotchi is the source of truth - remote changes are overwritten. This eliminates merge conflicts and keeps things simple.

**Incremental backups**: After the first backup, only changed files are copied. A collection of 50k+ handshakes will backup in seconds if nothing changed.

Files are copied (not moved), so your Pwnagotchi keeps working normally. The local repo at `/home/pi/git-backup-repo/` is just a staging area.

---

## Performance

| Scenario | Time |
|----------|------|
| First backup (empty repo) | Depends on size (737MB ≈ 2 mins) |
| No changes | ~3 seconds |
| 10 new handshakes | ~5 seconds |
| Config change only | ~3 seconds |

The plugin checks file modification time and size before copying. Only changed files are processed, making subsequent backups fast even with large handshake collections.

---

## Security Notes

- **Use a private repository** - Your backups contain SSH keys and config files
- **SSH keys in backup** - The backup includes `/root/.ssh` which may contain keys for other systems. Consider if this is appropriate for your setup.
- **GitHub access** - Anyone with access to your GitHub account can see your backups

---

## Uninstalling

```bash
# Remove plugin
sudo rm /usr/local/share/pwnagotchi/custom-plugins/git_backup.py

# Remove local repo (optional)
sudo rm -rf /home/pi/git-backup-repo

# Remove status file (optional)
sudo rm /root/.git-backup-status.json

# Remove config lines from config.toml
sudo nano /etc/pwnagotchi/config.toml
# Delete the main.plugins.git_backup.* lines

# Restart
sudo systemctl restart pwnagotchi
```

---

## License

GPL3

## Author

WPA2

## Links

- [Pwnagotchi](https://pwnagotchi.ai/)
- [Plugin Repository](https://github.com/wpa-2/pwnagotchi-plugins)
- [Buy me a Coffee](https://github.com/wpa-2/pwnagotchi-plugins)