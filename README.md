# 🚀 Pwnagotchi Power-Up Plugins

A curated collection of powerful plugins designed to enhance your Pwnagotchi experience. These tools add functionality ranging from remote command execution and automated backups to rich Discord notifications and VPN connectivity. 

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow?style=flat&logo=buy-me-a-coffee)](https://buymeacoffee.com/wpa2)

---

## 🔌 Universal Installation

1.  **Download:** Click on the `.py` file you want (e.g., `wireguard.py`, `discord.py`) from the file list above.
2.  **Install:** Move the file to your Pwnagotchi's custom plugin directory: `/usr/local/share/pwnagotchi/custom-plugins/`.
3.  **Configure:** Edit your `/etc/pwnagotchi/config.toml` file to include the settings listed below.
4.  **Activate:** Restart your Pwnagotchi:
    `sudo systemctl restart pwnagotchi`

---

## 📂 The Plugin Collection

| Plugin | Description | Setup Guide |
| :--- | :--- | :--- |
| **🛡️ AutoBackup** | **v2.0** - Automated backups with retention policy (garbage collection). | [Scroll Down](#autobackup) |
| **💾 GitHub_Backups** | Automated Git backup script for syncing configs to GitHub/Gitea. | [View Guide](./GitHub_Backups/README.md) |
| **🔔 Discord** | **v3.0.1** - Uploads **.pcap files**, maps locations, and tracks sessions. | [Scroll Down](#discord) |
| **🔒 Pwny-WG** | Connect to home **WireGuard VPN** and sync handshakes via SSH. | [View Guide](./Pwny-WG/README.md) |
| **🦎 Pwny-Tailscale** | Easy **Tailscale** integration for remote access without port forwarding. | [View Guide](./Pwny-Tailscale/README.md) |
| **📡 TelePwn** | **v2.0** - Advanced Telegram control and notifications for Pwnagotchi. | [View Guide](./TelePwn/README.md) |
| **🌐 web2ssh** | Lightweight web interface for executing shell commands from a browser. | [Scroll Down](#web2ssh) |
| **📍 WigleLocator** | **v2.2** - Queries WiGLE for GPS coordinates and provides live maps. | [Scroll Down](#wiglelocator) |

---

<a name="autobackup"></a>
## 🛡️ AutoBackup: Your Digital Guardian
*(Updated to v2.0 - Now with Garbage Collection!)*

The **AutoBackup** plugin automatically creates compressed `.tar.gz` backups of your specified files whenever an internet connection is available.

### ⚙️ Configuration Example:
    [main.plugins.auto_backup]
    enabled = true
    backup_location = "/home/pi/backups"

---

<a name="discord"></a>
## 🔔 Discord: The Ultimate Exfiltration Tool

Get instant, beautifully formatted notifications about your Pwnagotchi's conquests via Discord.

### ⚙️ Configuration Example:
```
[main.plugins.discord]
enabled = true
webhook_url = "YOUR_DISCORD_WEBHOOK_URL"
wigle_api_key = "ENCODED_API_KEY"
```
---

<a name="web2ssh"></a>
## 🌐 web2ssh: Command Center in Your Browser

Control your Pwnagotchi from anywhere on your network! **web2ssh** provides a lightweight, password-protected web interface.

### 🖼️ In Action
![WEB-SSH](https://github.com/user-attachments/assets/9d3829ea-a64b-4892-ace7-5c88159ebe57)

---

<a name="wiglelocator"></a>
## 📍 WigleLocator: Pinpoint Your Pwns (v2.2)

The **WigleLocator** plugin automatically queries the WiGLE database to find the geographic coordinates for every access point you capture.

### ⚙️ Configuration Example:
    [main.plugins.wiglelocator]
    enabled = true
    api_key = "ENCODED_API_KEY"
