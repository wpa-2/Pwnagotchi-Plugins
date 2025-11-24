# 🚀 Pwnagotchi Power-Up Plugins

A curated collection of powerful plugins designed to enhance your Pwnagotchi experience. These tools add functionality ranging from remote command execution and automated backups to rich Discord notifications and VPN connectivity. Supercharge your Pwnagotchi and make it an even more formidable (and convenient) Wi-Fi companion!

---

## 📋 Quick Menu

| Plugin | Description | Setup Guide |
| :--- | :--- | :--- |
| **🛡️ AutoBackup** | **v2.0** - Automated backups with retention policy (garbage collection). | [Scroll Down](#-autobackup-your-digital-guardian) |
| **🔒 Pwny-WG** | Connect to home **WireGuard VPN** and sync handshakes automatically via SSH. | [View Guide](./Pwny-WG/README.md) |
| **🦎 Pwny-Tailscale** | Easy **Tailscale** integration for remote access without port forwarding. | [View Guide](./Pwny-Tailscale/README.md) |
| **📡 Tele_Pi** | Telegram control and notifications for your Pwnagotchi. | [View Guide](./Tele_Pi/README.md) |
| **🔔 Discord** | Get instant notifications about your Pwnagotchi's conquests via Discord. | [Scroll Down](#-discord-your-pwnage-newsfeed) |
| **🌐 web2ssh** | A lightweight web interface for executing shell commands from your browser. | [Scroll Down](#-web2ssh-command-center-in-your-browser) |
| **📍 WigleLocator** | Automatically queries WiGLE to find GPS coordinates for handshakes. | [Scroll Down](#-wiglelocator-pinpoint-your-pwns) |

---

## 🔌 Universal Installation

1.  **Download:** Click on the `.py` file you want (e.g., `wireguard.py`, `auto_backup.py`) from the file list above.
2.  **Install:** Move the file to your Pwnagotchi's custom plugin directory: `/usr/local/share/pwnagotchi/custom-plugins/`.
3.  **Configure:** Edit your `/etc/pwnagotchi/config.toml` file to include the settings listed below.
4.  **Activate:** Restart your Pwnagotchi:
    ```bash
    sudo systemctl restart pwnagotchi
    ```

---

## 🛡️ AutoBackup: Your Digital Guardian
*(Updated to v2.0 - Now with Garbage Collection!)*

The **AutoBackup** plugin automatically creates compressed `.tar.gz` backups of your specified files whenever an internet connection is available. It features a smart retention policy to delete old backups so your SD card never fills up.

### ⚙️ Configuration
```toml
[main.plugins.auto_backup]
enabled = true
interval = "daily" # Options: "hourly", "daily", or minutes (e.g., "60")
max_tries = 0
backup_location = "/home/pi/backups/"
max_backups_to_keep = 5 # Keeps the 5 newest files, deletes the rest
files = [
 "/root/settings.yaml",
 "/root/client_secrets.json",
 "/root/.ssh",
 "/home/pi/handshakes",
 "/etc/pwnagotchi/config.toml",
 "/usr/local/share/pwnagotchi/custom-plugins"
]
exclude = [
  "*.tmp",
  "*.bak",
  "/etc/pwnagotchi/logs/*"
]
```

### 🚀 Restore Command
To restore files after a fresh flash:
```bash
sudo tar xzf /home/pi/backups/YOUR_BACKUP_FILENAME.tar.gz -C /
```

---

## 🔔 Discord: Your Pwnage Newsfeed

Get instant, beautifully formatted notifications about your Pwnagotchi's conquests sent directly to your Discord channel! This plugin leverages the WiGLE API to enrich handshake alerts with GPS coordinates.

### ⚙️ Configuration
```toml
[main.plugins.discord]
enabled = true
webhook_url = "YOUR_DISCORD_WEBHOOK_URL"
wigle_api_key = "ENCODED_API_KEY"
```

---

## 🌐 web2ssh: Command Center in Your Browser

Control your Pwnagotchi from anywhere on your network! **web2ssh** provides a lightweight, password-protected web interface for executing shell commands directly from your browser.

**Requirement:** You must install Flask first:
```bash
sudo apt update && sudo apt install python3-flask
```

### ⚙️ Configuration
```toml
[main.plugins.web2ssh]
enabled = true
username = "admin"
password = "changeme"
port = 8082
```

### 🖼️ In Action

![WEB-SSH Command Executor](https://github.com/user-attachments/assets/9d3829ea-a64b-4892-ace7-5c88159ebe57)
*The main command input screen with convenient shortcuts.*

![Command Output](https://github.com/user-attachments/assets/82084845-8e6a-40be-bd2d-47398b5887ea)
*The clean output view after executing a command.*

---

## 📍 WigleLocator: Pinpoint Your Pwns

The **WigleLocator** plugin automatically queries the WiGLE database to find the geographic coordinates for every access point you capture a handshake from.

### ⚙️ Configuration
```toml
[main.plugins.wiglelocator]
enabled = true
api_key = "ENCODED_API_KEY"
```
