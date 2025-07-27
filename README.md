# 🚀 Pwnagotchi Power-Up Plugins

A curated collection of powerful plugins designed to enhance your Pwnagotchi experience. These tools add functionality ranging from remote command execution and automated backups to rich Discord notifications with GPS data. Supercharge your Pwnagotchi and make it an even more formidable (and convenient) Wi-Fi companion!

---

## 📋 Table of Contents

- [🛡️ **AutoBackup**](#️-autobackup-your-digital-guardian)
- [🔔 **Discord**](#-discord-your-pwnage-newsfeed)
- [🌐 **web2ssh**](#-web2ssh-command-center-in-your-browser)
- [📍 **WigleLocator**](#-wiglelocator-pinpoint-your-pwns)

---

## 🔌 Universal Installation

1.  Download the plugin files (e.g., `auto_backup.py`, `discord.py`, etc.).
2.  Move the plugin files to your Pwnagotchi's custom plugin directory: `/usr/local/share/pwnagotchi/custom-plugins/`.
3.  Edit your `/etc/pwnagotchi/config.toml` file to include the configuration for each plugin you wish to enable. See the specific instructions for each plugin below.
4.  Restart your Pwnagotchi to apply the changes.

---

## 🛡️ AutoBackup: Your Digital Guardian

Keep your handshakes, settings, and other critical files safe! The **AutoBackup** plugin automatically creates compressed `.tar.gz` backups of your specified files and directories whenever an internet connection is available.

### Why It's Awesome:
-   **🛡️ Automatic & Secure**: Set it and forget it. Backups run automatically when online, creating compressed and safe archives.
-   **🕒 Flexible Intervals**: Configure backups to run hourly, daily, or at any custom minute interval.
-   **🧠 Smart & Efficient**: Only backs up files that actually exist and allows you to exclude unnecessary data like logs and temp files.

### ⚙️ Configuration

Pwnagotchi's `config.toml` supports two configuration formats. The modern "New Style" is recommended, but the "Old Style" also works.

#### New Style (Recommended)
```toml
[main.plugins.auto_backup]
enabled = true
interval = "60"
max_tries = 0
backup_location = "/home/pi/"
files = [
 "/root/settings.yaml",
 "/root/client_secrets.json",
 "/root/.api-report.json",
 "/root/.ssh",
 "/root/.bashrc",
 "/root/.profile",
 "/home/pi/handshakes",
 "/root/peers",
 "/etc/pwnagotchi/",
 "/usr/local/share/pwnagotchi/custom-plugins",
 "/etc/ssh/",
 "/home/pi/.bashrc",
 "/home/pi/.profile",
 "/home/pi/.wpa_sec_uploads"
]
exclude = [
  "/etc/pwnagotchi/logs/*",
  "*.bak",
  "*.tmp",
]
```

#### Old Style
```toml
main.plugins.auto_backup.enabled = true
main.plugins.auto_backup.interval = "60"
main.plugins.auto_backup.max_tries = 3
main.plugins.auto_backup.backup_location = "/home/pi/"
main.plugins.auto_backup.files = [
 "/root/settings.yaml",
 "/root/client_secrets.json",
 "/root/.api-report.json",
 "/root/.ssh",
 "/root/.bashrc",
 "/root/.profile",
 "/home/pi/handshakes",
 "/root/peers",
 "/etc/pwnagotchi/",
 "/usr/local/share/pwnagotchi/custom-plugins",
 "/etc/ssh/",
 "/home/pi/.bashrc",
 "/home/pi/.profile",
 "/home/pi/.wpa_sec_uploads",
]
main.plugins.auto_backup.exclude = [
 "/etc/pwnagotchi/logs/*",
 "*.bak",
 "*.tmp",
]
```

### 🚀 Restore Command

After a fresh flash, you can easily restore your files with this command:

```bash
sudo tar xzf /home/pi/NAME-backup.tar.gz -C /
```

---

## 🔔 Discord: Your Pwnage Newsfeed

Get instant, beautifully formatted notifications about your Pwnagotchi's conquests sent directly to your Discord channel! This plugin leverages the WiGLE API to enrich handshake alerts with GPS coordinates.

### Why It's Awesome:
-   **🛰️ GPS-Enriched Alerts**: Automatically fetches and includes the latitude and longitude of the access point using WiGLE.
-   **🧠 Smart Caching**: Reduces redundant API calls by keeping a local cache of WiGLE lookups, saving data and time.
-   **💬 Instant Notifications**: Get notified in real-time on your Discord server the moment a new handshake is captured.

### ⚙️ Configuration

Add this to your `/etc/pwnagotchi/config.toml`:

```toml
[main.plugins.discord]
enabled = true
webhook_url = "YOUR_DISCORD_CHANNEL_WEB_HOOK_URL"
wigle_api_key = "ENCODED FOR USE API KEY "
```
```Old Stle
main.plugins.discord.enabled = true
main.plugins.discord.webhook_url = ""
main.plugins.discord.wigle_api_key = ""
```

---

## 🌐 web2ssh: Command Center in Your Browser

Control your Pwnagotchi from anywhere on your network! **web2ssh** provides a lightweight, password-protected web interface for executing shell commands directly from your browser. No need to `ssh` in for a quick reboot or to check a file.

### Why It's Awesome:
-   **🖥️ Browser-Based Control**: Execute any shell command from a simple web page.
-   **👆 One-Click Shortcuts**: Pre-configured buttons for common actions like `reboot`, `shutdown`, `ping`, and more.
-   **🔒 Secure Access**: Protected by basic authentication to keep your device secure.
-   **📱 Mobile Friendly**: A clean, responsive UI that works on both desktop and mobile browsers.

### 🚨 Special Dependency

This plugin requires **Flask**. You must install it on your Pwnagotchi by running:
```bash
sudo apt update
sudo apt install python3-flask
```

### ⚙️ Configuration

Add this to your `/etc/pwnagotchi/config.toml`:

```toml
[main.plugins.web2ssh]
enabled = true
username = "changeme"
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

Know where you've been. The **WigleLocator** plugin automatically queries the WiGLE database to find the geographic coordinates for every access point you capture a handshake from. This data is then saved to a local text file.

### Why It's Awesome:
-   **🗺️ Automatic Geolocation**: Fetches location data (latitude and longitude) for each handshake.
-   **✍️ Local Data Storage**: Saves location information in a simple `.txt` file named after the network's ESSID.
-   **📺 On-Screen Display**: Shows the found coordinates directly on your Pwnagotchi's display.

### ⚙️ Configuration

Add this to your `/etc/pwnagotchi/config.toml`:

```toml
[main.plugins.wiglelocator]
enabled = true
api_key = "ENCODED FOR USE API KEY "
