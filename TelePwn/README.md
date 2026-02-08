# 🚀 TelePwn - Control Your Pwnagotchi via Telegram

[![Buy Me a Coffee](https://img.shields.io/badge/☕-Buy%20Me%20a%20Coffee-yellow)](https://buymeacoffee.com/wpa2)
[![Telegram Chat](https://img.shields.io/badge/Join-Telegram-blue.svg)](https://t.me/yourtelegramchannel)
[![Version](https://img.shields.io/badge/Version-2025-green.svg)](https://github.com/wpa-2/Pwnagotchi-Plugins)

**TelePwn** is a powerful Pwnagotchi plugin that brings your device to your fingertips through a Telegram bot.  
Remotely manage your Pwnagotchi, monitor stats, capture handshakes, schedule tasks, and integrate with external services — all from your phone or computer.

Whether you're tweaking plugins or checking logs, **TelePwn** makes it simple, fast, and secure.

---

## 🌟 Why Use TelePwn?

- 🛰️ **Remote Control**: Reboot, shutdown, or toggle plugins from anywhere.
- 📊 **Real-Time Insights**: Get screenshots, system stats, and handshake counts instantly.
- 🔄 **Automation**: Schedule backups or reboots to keep your Pwnagotchi humming.
- 🌐 **Integration**: Send alerts to Discord or APIs using webhooks.
- 🤖 **User-Friendly**: Intuitive Telegram menus guide you through every action.

---

## 🎥 See It in Action

![TelePwn Telegram Menu](images/a.png)

---

## ⚡ Installation

Get TelePwn up and running in minutes with our automated install script.

### Step 1: SSH into Your Pwnagotchi

```bash
ssh pi@<pwnagotchi-ip>
```
_Replace `<pwnagotchi-ip>` with your Pwnagotchi’s IP (e.g., `10.0.0.2`)._  
_Default credentials: `pi` / `raspberry` (change your password!)._

---

### Step 2: Run the Install Script

```bash
wget https://raw.githubusercontent.com/wpa-2/TelePwn/refs/heads/main/install_telepwn.sh
chmod +x install_telepwn.sh
sudo ./install_telepwn.sh
```

The script automatically:
- Installs dependencies (python-telegram-bot, requests, psutil, schedule)
- Downloads the TelePwn plugin
- Prompts you for bot token and chat ID
- Updates `/etc/pwnagotchi/config.toml`
- Restarts the Pwnagotchi daemon

---

### Step 3: Set Up Your Telegram Bot

- Create a bot with [@BotFather](https://t.me/BotFather):
  - Send `/newbot` and follow prompts.
  - Copy your bot token.

- Get your Chat ID with [@userinfobot](https://t.me/userinfobot):
  - Start a chat and grab your numeric ID.

---

### Step 4: Test It

Open Telegram ➔ Message your bot `/start` ➔ Tap the **Menu** button! 🎯

---

## 🛠️ Commands

### 📜 Menu and Core

| Command | Description |
|:--------|:------------|
| `/start` | Open main menu |
| `/reboot` | Reboot device (manual or auto mode) |
| `/shutdown` | Safe shutdown |
| `/uptime` | Show device uptime |
| `/logs` | Show last 50 log lines |
| `/clear` | Clear the display |
| `/kill` | Kill the daemon & reload plugins |

---

### 📡 Handshakes and Files

| Command | Description |
|:--------|:------------|
| `/handshakes` | Show number of captured handshakes |
| `/screenshot` | Send current screen as an image |
| `/backup` | Backup key files and send |
| `/files list` | List handshake files |
| `/files download <filename>` | Download a handshake file |
| `/files upload` | Upload a handshake file (pcap/pcapng) |

---

### ⚙️ Plugins and Daemon

| Command | Description |
|:--------|:------------|
| `/plugins` | List available plugins |
| `/toggle <plugin_name>` | Enable/disable a plugin |
| `/restart_manual` | Restart daemon into manual mode |
| `/restart_auto` | Restart daemon into auto mode |

---

### 🌐 Pwngrid Actions

| Command | Description |
|:--------|:------------|
| `/pwngrid send <id> <message>` | Send message to Pwngrid peer |
| `/pwngrid clear` | Clear Pwngrid inbox |
| `/inbox` | View Pwngrid messages |

---

### 🔥 Webhooks

TelePwn supports creating powerful webhooks that trigger actions remotely.

**Supported types:**
- 📣 `notify` - Send a message back to Telegram
- 🛠️ `shell` - Run a shell command on the Pwnagotchi
- 🌍 `http` - Send an HTTP request (e.g., Discord webhook)
- 🔀 `plugin_toggle` - Enable/disable a plugin

---

### ➡️ Set a Webhook

```bash
/setwebhook <action> <url> [type] [request/command]
```

| Parameter | Meaning |
|:----------|:--------|
| `action` | Name for the webhook |
| `url` | Target URL (use `none` for shell/plugin_toggle) |
| `type` | `notify`, `shell`, `http`, or `plugin_toggle` |
| `request/command` | Extra command or request body if needed |

---

### 🧪 Examples

**Simple notification:**
```bash
/setwebhook alert none notify
```

**Send to Discord:**
```bash
/setwebhook discord_alert https://discord.com/api/webhooks/<id>/<token> http POST {"content":"Handshake captured!"}
```

**Rotate the screen (without restarting full system!):**
```bash
/setwebhook rotate_screen none shell sudo sed -i '/ui\.display\.rotation/c\ui.display.rotation = {degrees}' /etc/pwnagotchi/config.toml && sudo killall -USR1 pwnagotchi
```
_Trigger it with:_
```bash
/webhook rotate_screen degrees=180
```

**Toggle a plugin (e.g., memtemp):**
```bash
/setwebhook toggle_memtemp none plugin_toggle
```
_Trigger it with:_
```bash
/webhook toggle_memtemp memtemp
```

---

### ➡️ Trigger a Webhook

```bash
/webhook <action> [extra]
```

| Example | Meaning |
|:--------|:--------|
| `/webhook alert` | Send a notification |
| `/webhook temp 41.2` | Post temp to HTTP API |
| `/webhook rotate_screen degrees=90` | Rotate screen 90 degrees |
| `/webhook toggle_memtemp memtemp` | Toggle the memtemp plugin |

---

### 📝 Notes

- For `shell` webhooks, variables like `{degrees}` can be passed as `key=value`.
- Webhooks are stored at `/etc/pwnagotchi/telepwn_webhooks.toml`.
- Edit or delete webhooks manually if needed.

---

---
> 📚 **Need more help?**  
> Check out the [TelePwn Webhooks Help Guide](webhooks.md) for easy examples and a cheat sheet!
---

### 📈 System Stats

| Command | Description |
|:--------|:------------|
| `/stats` | Show CPU usage, RAM usage, and temperature |

---

### 🧠 Schedule Tasks

| Command | Description |
|:--------|:------------|
| `/schedule add <action> <interval_hours>` | Add a scheduled task |
| `/schedule list` | List scheduled tasks |
| `/schedule remove <task_id>` | Remove a scheduled task |

Example:  
```bash
/schedule add reboot 24
```
_(Reboots every 24 hours)_

---

## 🧰 Troubleshooting

- Bot not responding?
  ```bash
  sudo journalctl -u pwnagotchi | grep telepwn
  ```

- Commands fail?
  ```bash
  sudo tail -n 50 /etc/pwnagotchi/log/pwnagotchi.log
  ```

- Webhooks not firing?
  ```bash
  sudo grep webhook /etc/pwnagotchi/log/pwnagotchi.log
  ```

- Confirm plugin is enabled:
  ```text
  main.plugins.telepwn.enabled = true
  ```
  in your `/etc/pwnagotchi/config.toml`

---

## 🤝 Contributing

- Fork this repo.
- Add cool features or fixes.
- Submit pull requests.
- Help us make Pwnagotchi smarter!

---
