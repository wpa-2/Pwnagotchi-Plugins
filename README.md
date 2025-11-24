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

1.  Download the plugin files from their respective folders.
2.  Move the plugin files to your Pwnagotchi's custom plugin directory: `/usr/local/share/pwnagotchi/custom-plugins/`.
3.  Edit your `/etc/pwnagotchi/config.toml` file to include the configuration for each plugin you wish to enable.
4.  Restart your Pwnagotchi to apply the changes:
    ```bash
    sudo systemctl restart pwnagotchi
    ```

---

## 🛡️ AutoBackup: Your Digital Guardian
*(Updated to v2.0 - Now with Garbage Collection!)*

Keep your handshakes, settings, and other critical files safe! The **AutoBackup** plugin automatically creates compressed `.tar.gz` backups of your specified files whenever an internet connection is available.

### Why It's Awesome:
-   **🛡️ Automatic & Secure**: Backups run automatically when online.
-   **🧹 Smart Retention**: **(New in v2.0)** Automatically deletes old backups to prevent your SD card from filling up.
-   **🧠 Efficient**: Only backs up files that actually exist and allows exclusions.

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
 "/root/.api-report.json",
 "/root/.ssh",
 "/root/.bashrc",
 "/root/.profile",
 "/home/pi/handshakes",
 "/root/peers",
 "/etc/pwnagotchi/config.toml",
 "/usr/local/share/pwnagotchi/custom-plugins",
 "/etc/ssh/",
 "/home/pi/.bashrc",
 "/home/pi/.profile",
 "/home/pi/.wpa_sec_uploads"
]
exclude = [
  "/etc/pwnagotchi/logs/*",
  "*.bak",
  "*.tmp"
]
```

### 🚀 Restore Command
After a fresh flash, you can easily restore your files with this command:
```bash
sudo tar xzf /home/pi/backups/YOUR_BACKUP_FILENAME.tar.gz -C /
```

---

## 🔔 Discord: Your Pwnage Newsfeed

Get instant, beautifully formatted notifications about your Pwnagotchi's conquests sent directly to your Discord channel! This plugin leverages the WiGLE API to enrich handshake alerts with GPS coordinates.

### Why It's Awesome:
-   **🛰️ GPS-Enriched Alerts**: Automatically fetches latitude and longitude using WiGLE.
-   **🧠 Smart Caching**: Reduces redundant API calls.
-   **💬 Instant Notifications**: Get notified in real-time on your Discord server.

### ⚙️ Configuration
```toml
[main.plugins.discord]
enabled = true
webhook_url = "YOUR_DISCORD_CHANNEL_WEB_HOOK_URL"
wigle_api_key = "ENCODED_WIGLE_API_KEY"
```

---

## 🌐 web2ssh: Command Center in Your Browser

Control your Pwnagotchi from anywhere on your network! **web2ssh** provides a lightweight, password-protected web interface for executing shell commands directly from your browser. No need to `ssh` in for a quick reboot.

### Why It's Awesome:
-   **🖥️ Browser-Based Control**: Execute shell commands from a simple web page.
-   **👆 One-Click Shortcuts**: Buttons for `reboot`, `shutdown`, `ping`, etc.
-   **🔒 Secure Access**: Protected by basic authentication.
-   **📱 Mobile Friendly**: Works great on phones.

### 🚨 Special Dependency
This plugin requires **Flask**. Install it by running:
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

Know where you've been. The **WigleLocator** plugin automatically queries the WiGLE database to find the geographic coordinates for every access point you capture a handshake from.

### Why It's Awesome:
-   **🗺️ Automatic Geolocation**: Fetches location data for each handshake.
-   **✍️ Local Data Storage**: Saves location information in a simple `.txt` file.
-   **📺 On-Screen Display**: Shows the found coordinates directly on your Pwnagotchi's display.

### ⚙️ Configuration
```toml
[main.plugins.wiglelocator]
enabled = true
api_key = "ENCODED_WIGLE_API_KEY"
```
