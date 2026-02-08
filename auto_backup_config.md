# auto_backup.py

Automated backup plugin for Pwnagotchi that runs on a schedule and preserves your device configuration, settings, and captures.

## What Gets Backed Up (By Default)

- Pwnagotchi settings and config
- SSH keys and authorized hosts
- Client secrets
- Handshake captures
- Custom plugins
- Installed Python packages
- Web UI data

Backups run every 60 minutes, keep the 3 most recent, and skip logs/temp files automatically.

## Configuration

**Minimal (just enable it):**
```toml
[main.plugins.auto_backup]
enabled = true
backup_location = "/home/pi/backups"
```

**Add custom directories:**
```toml
[main.plugins.auto_backup]
enabled = true
backup_location = "/home/pi/backups"
include = ["/home/pi/my_custom_data"]
```

**Add multiple paths:**
```toml
[main.plugins.auto_backup]
enabled = true
backup_location = "/home/pi/backups"
include = [
  "/home/pi/my_custom_data",
  "/opt/important_app",
  "/etc/myapp/config.json",
]
```

## Installation

```bash
sudo wget -O /usr/local/share/pwnagotchi/custom-plugins/auto_backup.py / 
https://raw.githubusercontent.com/wpa-2/Pwnagotchi-Plugins/refs/heads/main/auto_backup.py
```

## How It Works

- Creates compressed `.tar.gz` files with hostname + timestamp
- Rotates backups automatically (keeps 3 most recent)
- Stores metadata to avoid unnecessary backups
- Runs in the background via Pwnagotchi's scheduler

---

If this plugin saves you time, [consider buying me a coffee](https://buymeacoffee.com/wpa2) ☕



To restore after flashing 
```
sudo tar xzf /home/pi/NAME-backup.tar.gz -C /
```


