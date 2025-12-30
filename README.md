# 🚀 Pwnagotchi Power-Up Plugins

A curated collection of powerful plugins designed to enhance your Pwnagotchi experience. These tools add functionality ranging from remote command execution and automated backups to rich Discord notifications and VPN connectivity. Supercharge your Pwnagotchi and make it an even more formidable (and convenient) Wi-Fi companion!

---

## 🔌 Universal Installation

1.  **Download:** Click on the `.py` file you want (e.g., `wireguard.py`, `discord.py`) from the file list above.
2.  **Install:** Move the file to your Pwnagotchi's custom plugin directory: `/usr/local/share/pwnagotchi/custom-plugins/`.
3.  **Configure:** Edit your `/etc/pwnagotchi/config.toml` file to include the settings listed below.
4.  **Activate:** Restart your Pwnagotchi:
    ```bash
    sudo systemctl restart pwnagotchi
    ```

---

## 📂 The Plugin Collection

| Plugin | Description | Setup Guide |
| :--- | :--- | :--- |
| **🛡️ AutoBackup** | **v2.0** - Automated backups with retention policy (garbage collection). | [Scroll Down](#autobackup) |
| **🔔 Discord** | **v2.5.0** - Uploads **.pcap files**, maps locations, and tracks sessions without lag. | [Scroll Down](#discord) |
| **🔒 Pwny-WG** | Connect to home **WireGuard VPN** and sync handshakes automatically via SSH. | [View Guide](./Pwny-WG/README.md) |
| **🦎 Pwny-Tailscale** | Easy **Tailscale** integration for remote access without port forwarding. | [View Guide](./Pwny-Tailscale/README.md) |
| **📡 Tele_Pi** | Telegram control and notifications for your Pwnagotchi. | [View Guide](./Tele_Pi/README.md) |
| **🌐 web2ssh** | A lightweight web interface for executing shell commands from your browser. | [Scroll Down](#web2ssh) |
| **📍 WigleLocator** | Automatically queries WiGLE to find GPS coordinates for handshakes. | [Scroll Down](#wiglelocator) |

---

<a name="autobackup"></a>
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

<a name="discord"></a>
## 🔔 Discord: The Ultimate Exfiltration Tool
*(Updated to v3.0.1 - Production Ready)*

Get instant, beautifully formatted notifications about your Pwnagotchi's conquests via Discord.

**Key Features:**
* **📁 Automatic Exfiltration:** Uploads captured `.pcap` files directly to Discord. Download and crack handshakes immediately—no SSH required.
* **⚡ Zero-Lag Queue:** Threaded background worker prevents freezing or slowdown during captures. Perfect for high-speed scanning.
* **📍 Intelligence:** Enriches alerts with direct Google Maps links via WiGLE geolocation.
* **📊 Session Tracking:** Reports uptime, handshake counts, and stats on boot/shutdown.
* **🔄 Auto-Retry:** Network failures? Automatic retry with exponential backoff (3 attempts).
* **🛡️ Thread-Safe:** Rock-solid concurrency for rapid-fire handshake captures.

### ⚙️ Configuration
```toml
main.plugins.discord.enabled = true
main.plugins.discord.webhook_url = "YOUR_DISCORD_WEBHOOK_URL"
main.plugins.discord.wigle_api_key = "ENCODED_API_KEY"
```
*Note: `wigle_api_key` must be Base64 encoded: `echo -n "Username:Token" | base64`*


---

<a name="web2ssh"></a>
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

---
<a name="wiglelocator"></a>
## 📍 WigleLocator: Pinpoint Your Pwns

# WigleLocator: Pinpoint Your Pwns (v2.2)

The **WigleLocator** plugin automatically queries the WiGLE database to find the geographic coordinates for every access point you capture a handshake from.

**New in v2.2:**
* **🛡️ WiGLE-Compliant Rate Limiting:** Properly respects 429 responses with automatic 24-hour cooldowns to prevent API abuse
* **📊 Live Status Dashboard:** Interactive modal showing real-time stats (queue size, daily requests, cooldown status)
* **🔄 Auto-Refresh:** Stats update every 30 seconds with manual refresh option
* **⚡ Conservative Processing:** Enforces 2-second intervals between requests, processes max 20 items per batch every 10 minutes
* **🔒 CSRF Protection:** Secure token-based authentication for administrative actions
* **💾 Smart Caching:** Prevents memory bloat with 10,000 entry limit and automatic trimming
* **🗑️ One-Click Reset:** Flush queue and reset rate limits via web interface

**Features from v2.0:**
* **Async Processing:** No UI freezing - lookups happen in background threads
* **Offline Queueing:** Captures handshakes offline and processes when internet available
* **Interactive Map:** View located networks at `http://pwnagotchi.local:8080/plugins/wiglelocator/`
* **Multi-Format Export:** Download KML (Google Earth), CSV (Excel), and JSON directly from web UI

*(Note: The Discord plugin v2.5.0 now handles its own lookups, but this plugin is useful if you want to save GPS data locally, generate maps, or use Google Earth without Discord.)*

### ⚙️ Configuration

Add your WiGLE API key to `/etc/pwnagotchi/config.toml`:
```toml
main.plugins.wiglelocator.enabled = true
main.plugins.wiglelocator.api_key = "ENCODED_API_KEY"
```

### 📊 Monitoring

Access the web interface at `http://pwnagotchi.local:8080/plugins/wiglelocator/` to:
- View all located networks on an interactive Leaflet map
- Check real-time status (queue size, daily API usage, cooldown timer)
- Download data in KML, CSV, or JSON formats
- Flush queue and reset rate limits if needed

The plugin automatically enforces WiGLE's rate limits to ensure compliance and prevent API suspension.
Add your WiGLE API key to `/etc/pwnagotchi/config.toml`.

```toml
main.plugins.wiglelocator.enabled = true
main.plugins.wiglelocator.api_key = "ENCODED_API_KEY"
# OR
[main.plugins.wiglelocator]
enabled = true
api_key = "ENCODED_API_KEY"
```
