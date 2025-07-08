# Pwnagotchi Configuration Guide 🚀

Welcome to the ultimate **Pwnagotchi Configuration Guide**! This `README.md` explains every option in the `config.toml` file, helping you customize your AI-powered Wi-Fi buddy. 😎

> Pwnagotchi is a DIY A2C-based AI that learns from its surrounding Wi-Fi environment to capture WPA2 handshakes. This file is its brain—let's dive in! 🛠️

---

### 📍 Where is the Configuration File?
Before you start, you need to find and edit the main configuration file. It's located at:
```
/etc/pwnagotchi/config.toml
```
You'll need `sudo` privileges to edit it (e.g., `sudo nano /etc/pwnagotchi/config.toml`).

---

## 📋 Table of Contents
- [Main Configuration](#main-configuration)
- [Plugins](#plugins)
- [Logging](#logging)
- [Personality](#personality)
- [User Interface](#user-interface)
- [Bettercap](#bettercap)
- [Filesystem Memory](#filesystem-memory)
- [Tips for Beginners](#tips-for-beginners)

---

## Main Configuration

The `[main]` section sets up the core of your Pwnagotchi. Think of it as the brain’s basic settings. 🧠

| Setting | Description | Default | Example |
|---|---|---|---|
| `name` | Your Pwnagotchi’s name, shown on the screen and used for identification. | `pwnagotchi` | `name = "MyPwnagotchi"` |
| `lang` | Language for the interface (e.g., `en`, `es`). | `en` | `lang = "es"` |
| `iface` | **Monitor mode interface**. This is *not* your physical Wi-Fi card (`wlan0`), but the virtual interface used for monitoring (`wlan0mon`). | `wlan0mon` | `iface = "wlan1mon"` |
| `mon_start_cmd` | Command to put the Wi-Fi card into monitor mode. | `/usr/bin/monstart` | `/usr/local/bin/start_monitor.sh` |
| `mon_stop_cmd` | Command to stop monitor mode. | `/usr/bin/monstop` | `/usr/local/bin/stop_monitor.sh` |
| `no_restart` | Set to `true` to prevent Pwnagotchi from automatically restarting on errors. | `false` | `no_restart = true` |
| `whitelist` | List of SSIDs or BSSIDs (MAC addresses) to ignore. | `[]` | `whitelist = ["MyHomeWiFi", "00:11:22:33:44:55"]` |
| `custom_plugins` | Directory for locally stored custom plugins. | `/usr/local/share/pwnagotchi/custom-plugins/` | `custom_plugins = "/home/pi/my_plugins/"` |

> 💡 **Tip:** Always `whitelist` your home and office Wi-Fi networks to prevent accidentally capturing your own handshakes!

---

## Plugins

Plugins add superpowers to your Pwnagotchi! 🦸 Each plugin under `[main.plugins.*]` has an `enabled = true/false` setting and its own options.

### General & System Plugins
| Plugin | Description |
|---|---|
| `auto-tune` | **(Recommended)** Automatically optimizes Wi-Fi channel hopping for better performance. Default: `enabled = true`. |
| `auto-update` | Keeps Pwnagotchi and plugins up to date from their Git repositories. Set an `interval` in days. Default: `enabled = true`. |
| `webcfg` | **(Recommended)** Provides a web interface to view status and configure your Pwnagotchi from a browser. Default: `enabled = true`. |
| `fix_services` | ⚠️ **For built-in Wi-Fi cards only.** Ensures critical services are running correctly. Default: `enabled = true`. |

### Data Backup & Cracking Plugins
| Plugin | Description |
|---|---|
| `auto_backup` | Automatically backs up important files. Set an `interval`, `backup_location`, and a list of `files` to save. |
| `gdrivesync` | Syncs backups to a `backup_folder` in Google Drive. Requires setup. |
| `pwncrack` | Automatically sends handshakes to an online cracking service. Requires an `api_key`. |
| `wpa-sec` | Uploads handshakes to wpa-sec.stanev.org for cracking and community sharing. Requires an `api_key`. |
| `wigle` | Uploads Wi-Fi network data to Wigle.net. Requires a Wigle `api_key`. |
| `session-stats` | Tracks session data like handshakes captured and time elapsed. |

> ⚠️ **Warning**: The `pwncrack`, `wpa-sec`, and `wigle` plugins share your data with third-party services. Understand their terms of service before enabling.

### Hardware & Connectivity Plugins
| Plugin | Description |
|---|---|
| `bt-tether` | Shares internet from a phone via Bluetooth. Requires configuring your phone's `mac` address and `name`. |
| `gps` | Tracks location with a GPS module. Set the `device` path (e.g., `/dev/ttyUSB0`) or `gpsd` server (`localhost:2947`). |
| `gpio_buttons` | Allows you to use physical GPIO buttons to interact with the Pwnagotchi. |
| `grid` | Connects to the Pwnagotchi community grid to share data and see nearby peers. Default: `enabled = true`. |

### Battery Management Plugins
| Plugin | Description |
|---|---|
| `pisugar` | Manages PiSugar battery modules. Set a `lowpower_shutdown_level` to safely power off. |
| `ups_hat_c` | Manages Waveshare UPS Hat (C) battery module. |
| `ups_lite` | Manages UPS-Lite battery module. |

### UI & Display Plugins
| Plugin | Description |
|---|---|
| `logtail` | Shows recent log entries on the Pwnagotchi's screen. |
| `memtemp` | Displays CPU temperature and memory usage stats on the screen. |
| `pwndroid` | Displays GPS coordinates and altitude on the screen when paired with the PwnDroid app. |
| `webgpsmap` | Shows GPS data on a map in the web UI. |

---

## Logging

The `[main.log]` section controls where logs are stored and how they are rotated.

| Setting | Description | Default |
|---|---|---|
| `path` | Location for the main log file. | `"/var/log/pwnagotchi.log"` |
| `path-debug` | Location for the more verbose debug log. | `"/tmp/pwnagotchi-debug.log"` |
| `rotation` | **(Recommended)** `enabled = true` prevents logs from filling your SD card. Set a max `size` (e.g., `10M`). | `enabled = true` |

---

## Personality

The `[personality]` section defines your Pwnagotchi’s "mood" and hacking tactics. 😈

| Setting | Description | Default |
|---|---|---|
| `deauth` | `true` allows performing deauth attacks to capture handshakes. | `true` |
| `associate` | `true` allows connecting to access points to gather data. | `true` |
| `channels` | Wi-Fi channels to scan (e.g., `[1, 6, 11]`). Empty `[]` means all channels. | `[]` |
| `min_rssi` | Minimum signal strength (dBm) required to interact with a network. `-200` means no limit. A realistic value is `-75`. | `-200` |
| `bond_encounters_factor`| How quickly your Pwnagotchi "bonds" with other units it encounters. | `20000` |
| `bored_num_epochs` | Number of cycles without activity before getting "bored." | `15` |
| `sad_num_epochs` | Number of cycles without activity before getting "sad." | `25` |

> 😺 **Fun Fact**: Pwnagotchi changes moods (and face expressions) based on its activity. Tweak these settings to make it more aggressive or passive!

---

## User Interface

The `[ui]` section controls what you see on the screen and in the web browser.

| Setting | Description | Default |
|---|---|---|
| `invert` | `true` for white background, `false` for black. | `false` |
| `font.name` | Display font (e.g., `DejaVuSansMono`). | `DejaVuSansMono` |
| `faces` | Customize the ASCII art for different moods. | `(various)` |
| `web.enabled` | `true` to enable the web UI. | `true` |
| `web.address` | Listening address. `0.0.0.0` is recommended for general access. | `::` |
| `web.port` | Web server port. | `8080` |
| `display.enabled` | **(Required for screens)** `true` to activate the physical display. | `false` |
| `display.type` | The model of your e-ink screen (e.g., `waveshare_v3`, `inkyphat`). | `waveshare_v2` |
| `display.rotation`| Screen rotation in degrees (`0`, `90`, `180`, `270`). | `180` |

> 🖼️ **Display Tip**: To use a screen, you *must* set `ui.display.enabled = true` and `ui.display.type` to match your hardware. Check the official Pwnagotchi docs for a list of supported display types!

---

## Bettercap

The `[bettercap]` section configures Bettercap, the underlying packet sniffing tool.

| Setting | Description | Default |
|---|---|---|
| `handshakes` | Directory where captured handshake `.pcap` files are stored. | `"/home/pi/handshakes"` |
| `silence` | Bettercap events to hide from the log to reduce noise (e.g., `wifi.ap.new`, `wifi.client.probe`). | `(various)` |

---

## Filesystem Memory

The `[fs.memory]` section helps reduce SD card wear by using RAM for temporary files. This is a key feature for longevity!

| Setting | Description | Benefit |
|---|---|---|
| `log.enabled` | `true` to store logs in RAM instead of directly on the SD card. | Reduces constant write cycles. |
| `data.enabled`| `true` to store temporary data (like session info) in RAM. | Extends the life of your SD card. |

---

## Tips for Beginners

<details>
<summary>🆕 **New to Pwnagotchi? Click here for quick tips!**</summary>

- **Start Simple**: At first, only enable a few plugins like `auto-tune` and `webcfg`.
- **Use the Web UI**: Set `ui.web.enabled = true` and visit `http://<pwnagotchi-ip>:8080` in your browser (the default IP over USB is often `10.0.0.2`).
- **Check the Logs**: If something isn't working, check the log file at `/var/log/pwnagotchi.log` for clues.
- **Join the Community**: Visit the official [pwnagotchi.ai](https://pwnagotchi.ai/) website, Discord, or community forums for help and ideas.

</details>

---

## Contributing
Got ideas to improve this guide? Please submit a pull request or open an issue!

## License
This project is licensed under the MIT License. See the `LICENSE` file for details.

---

Happy hacking with your Pwnagotchi! 🎉
