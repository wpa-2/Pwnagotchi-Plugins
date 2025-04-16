# Pwnagotchi Configuration Guide 🚀

Welcome to the **Pwnagotchi Configuration Guide**! This `README.md` explains every option in the Pwnagotchi configuration file (`/etc/pwnagotchi/config.toml`). Whether you're a newbie or a pro, this guide makes it easy to customize your AI-powered Wi-Fi hacking buddy. 😎

> **New to Pwnagotchi?** Pwnagotchi is a DIY device that learns to capture Wi-Fi handshakes. This file controls its behavior, plugins, and display. Let’s dive in! 🛠️

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
|---------|-------------|---------|---------|
| **name** | Your Pwnagotchi’s name, shown on the screen and for identification. | `pwnagotchi` | `name = "MyPwnagotchi"` |
| **lang** | Language for the interface (e.g., `en` for English, `es` for Spanish). | `en` | `lang = "es"` |
| **iface** | Wi-Fi interface for monitoring traffic (must be in monitor mode). | `wlan0mon` | `iface = "wlan1mon"` |
| **mon_start_cmd** | Command to start monitor mode on the interface. | `/usr/bin/monstart` | `/usr/local/bin/start_monitor.sh` |
| **mon_stop_cmd** | Command to stop monitor mode. | `/usr/bin/monstop` | `/usr/local/bin/stop_monitor.sh` |
| **mon_max_blind_epochs** | Max cycles without detecting networks before restarting. | `5` | `10` |
| **no_restart** | Set to `true` to prevent automatic restarts. | `false` | `true` |
| **whitelist** | List of SSIDs or MAC addresses to skip (no hacking). | `[]` | `["MyHomeWiFi", "00:11:22:33:44:55"]` |
| **confd** | Directory for additional config files to merge. | `/etc/pwnagotchi/conf.d/` | `/etc/pwnagotchi/custom/` |
| **custom_plugin_repos** | URLs for custom plugin repositories. | `[]` | `["https://github.com/user/repo/archive/main.zip"]` |
| **custom_plugins** | Directory for locally stored custom plugins. | `/usr/local/share/pwnagotchi/custom-plugins/` | `/home/pi/plugins/` |

> **💡 Tip**: Use `whitelist` to protect your home Wi-Fi from accidental attacks! Add your network’s SSID or router’s MAC address.

---

## Plugins

Plugins add superpowers to your Pwnagotchi! 🦸 The `[main.plugins.*]` sections control these extras. Each plugin has an `enabled` setting (`true`/`false`) and specific options.

### 🔧 Auto-Tune
Optimizes Wi-Fi channel hopping.
- **enabled**: Turn on/off. Default: `true`.

### 💾 Auto Backup
Backs up important files automatically.
- **enabled**: Turn on/off. Default: `false`.
- **interval**: How often to back up (`hourly`, `daily`, or minutes). Default: `daily`.
- **max_tries**: Max retries for failed backups (0 = unlimited). Default: `0`.
- **backup_location**: Where to save backups. Default: `/home/pi/`.
- **files**: Files/folders to back up. Example: `["/root/settings.yaml", "/home/pi/handshakes"]`.
- **exclude**: Files/folders to skip. Example: `["/etc/pwnagotchi/logs/*"]`.
- **commands**: Backup commands (e.g., `tar` for zipping). Example: `["tar cf {backup_file} {files}"]`.

> **⚠️ Warning**: Set `backup_location` to a safe directory to avoid overwriting files!

### 🔄 Auto-Update
Keeps Pwnagotchi and plugins up to date.
- **enabled**: Turn on/off. Default: `true`.
- **install**: Auto-install updates if `true`. Default: `true`.
- **interval**: Days between update checks. Default: `1`.
- **token**: GitHub token for API access (needs `public_repo` scope). Default: `""`.

### 📱 Bluetooth Tethering
Shares internet via Bluetooth.
- **enabled**: Turn on/off. Default: `false`.
- **phone-name**: Phone’s Bluetooth name. Default: `""`.
- **mac**: Phone’s Bluetooth MAC address. Default: `""`.
- **phone**: Phone type (`android` or `ios`). Default: `""`.
- **ip**: Tethering IP address. Default: `192.168.44.2` (Android) or `172.20.10.2` (iOS).
- **dns**: DNS servers (space-separated). Default: `8.8.8.8 1.1.1.1`.

### 🛠️ Fix Services
Ensures critical services are running.
- **enabled**: Turn on/off. Default: `true`.

### ⚡ Cache
Speeds up performance with caching.
- **enabled**: Turn on/off. Default: `true`.

### ☁️ Google Drive Sync
Syncs backups to Google Drive.
- **enabled**: Turn on/off. Default: `false`.
- **backupfiles**: Files to sync. Default: `[""]`.
- **backup_folder**: Google Drive folder. Default: `PwnagotchiBackups`.
- **interval**: Sync frequency (hours). Default: `1`.

### 🕹️ GPIO Buttons
Uses GPIO buttons for interaction.
- **enabled**: Turn on/off. Default: `false`.

### 🌍 GPS
Tracks location with a GPS module.
- **enabled**: Turn on/off. Default: `false`.
- **speed**: GPS baud rate. Default: `19200`.
- **device**: GPS device path or GPSD server. Default: `/dev/ttyUSB0` or `localhost:2947`.

### 📡 GPS Listener
Listens for GPS data.
- **enabled**: Turn on/off. Default: `false`.

### 🌐 Grid
Connects to the Pwnagotchi community grid.
- **enabled**: Turn on/off. Default: `true`.
- **report**: Share captured handshakes with the grid. Default: `true`.

### 📜 Logtail
Shows recent logs on the screen.
- **enabled**: Turn on/off. Default: `false`.
- **max-lines**: Max log lines to display. Default: `10000`.

### 🌡️ Memory/Temperature
Displays memory and temperature stats.
- **enabled**: Turn on/off. Default: `false`.
- **scale**: Temperature unit (`celsius` or `fahrenheit`). Default: `celsius`.
- **orientation**: Display layout (`horizontal` or `vertical`). Default: `horizontal`.

### 🔗 OHC API
Connects to an external API (specific setups).
- **enabled**: Turn on/off. Default: `false`.
- **api_key**: API key for authentication. Default: `sk_your_api_key_here`.
- **receive_email**: Get email notifications (`yes` or `no`). Default: `yes`.

### 🤖 PwnDroid
Shows GPS coordinates/altitude on the screen.
- **enabled**: Turn on/off. Default: `false`.
- **display**: Show coordinates. Default: `false`.
- **display_altitude**: Show altitude. Default: `false`.

### 🔋 PiSugarX
Manages PiSugar battery modules.
- **enabled**: Turn on/off. Default: `false`.
- **rotation**: Rotate display output. Default: `false`.
- **default_display**: Display mode (`percentage` or other). Default: `percentage`.
- **lowpower_shutdown**: Shut down on low battery. Default: `true`.
- **lowpower_shutdown_level**: Battery % for shutdown. Default: `10`.
- **max_charge_voltage_protection**: Limit charge to ~80% for battery health. Default: `false`.

### 🔓 PwnCrack
Cracks captured handshakes automatically.
- **enabled**: Turn on/off. Default: `false`.
- **key**: API key for cracking service. Default: `""`.

### 📊 Session Stats
Tracks session data.
- **enabled**: Turn on/off. Default: `false`.
- **save_directory**: Where to save session data. Default: `/var/tmp/pwnagotchi/sessions/`.

### 🔋 UPS Hat C
Manages UPS Hat C battery module.
- **enabled**: Turn on/off. Default: `false`.
- **label_on**: Show `BAT` label or just %. Default: `true`.
- **shutdown**: Battery % for shutdown. Default: `5`.
- **bat_x_coord**: X-coordinate for battery display. Default: `140`.
- **bat_y_coord**: Y-coordinate for battery display. Default: `0`.

### 🔋 UPS Lite
Manages UPS Lite battery module.
- **enabled**: Turn on/off. Default: `false`.
- **shutdown**: Battery % for shutdown. Default: `2`.

### 🌐 Web Configuration
Provides a web interface for settings.
- **enabled**: Turn on/off. Default: `true`.

### 🗺️ Web GPS Map
Shows GPS data on a web map.
- **enabled**: Turn on/off. Default: `false`.

### 📍 Wigle
Uploads Wi-Fi data to Wigle.net.
- **enabled**: Turn on/off. Default: `false`.
- **api_key**: Wigle API key. Default: `""`.
- **cvs_dir**: Directory for CSV files. Default: `/tmp`.
- **donate**: Share data with Wigle. Default: `false`.
- **timeout**: Upload timeout (seconds). Default: `30`.
- **position**: Display position `[x, y]`. Default: `[7, 85]`.

### 🔐 WPA-Sec
Uploads handshakes to wpa-sec.stanev.org for cracking.
- **enabled**: Turn on/off. Default: `false`.
- **api_key**: WPA-Sec API key. Default: `""`.
- **api_url**: WPA-Sec API endpoint. Default: `https://wpa-sec.stanev.org`.
- **download_results**: Download cracking results. Default: `false`.
- **show_pwd**: Show cracked passwords. Default: `false`.

> **🎉 Pro Tip**: Enable plugins like `auto-update` and `webcfg` to keep your Pwnagotchi fresh and easy to manage via a browser!

---

## Logging

The `[main.log]` section controls where logs are stored.

| Setting | Description | Default |
|---------|-------------|---------|
| **path** | Main log file location. | `/etc/pwnagotchi/log/pwnagotchi.log` |
| **path-debug** | Debug log file location. | `/etc/pwnagotchi/log/pwnagotchi-debug.log` |

### 🔄 Log Rotation
Prevents logs from eating up disk space.
- **enabled**: Turn on/off. Default: `true`.
- **size**: Max log size before rotation (e.g., `10M` = 10MB). Default: `10M`.

---

## Personality

The `[personality]` section defines how Pwnagotchi behaves and interacts with Wi-Fi networks. It’s like setting its mood and tactics! 😈

| Setting | Description | Default |
|---------|-------------|---------|
| **advertise** | Advertise as an access point. | `true` |
| **deauth** | Perform deauth attacks to capture handshakes. | `true` |
| **associate** | Connect to nearby access points. | `true` |
| **channels** | Wi-Fi channels to scan (empty = all). | `[]` |
| **min_rssi** | Min signal strength (dBm) for networks. | `-200` |
| **ap_ttl** | Time-to-live (seconds) for access point ads. | `120` |
| **sta_ttl** | Time-to-live (seconds) for client connections. | `300` |
| **recon_time** | Recon scan duration (seconds). | `30` |
| **max_inactive_scale** | Multiplier for inactive network detection. | `2` |
| **recon_inactive_multiplier** | Multiplier for inactive recon. | `2` |
| **hop_recon_time** | Channel hop duration (seconds). | `10` |
| **min_recon_time** | Min recon duration (seconds). | `5` |
| **max_interactions** | Max interactions per network per cycle. | `3` |
| **max_misses_for_recon** | Max missed scans before network is inactive. | `5` |
| **excited_num_epochs** | Cycles before leaving "excited" state. | `10` |
| **bored_num_epochs** | Cycles before entering "bored" state. | `15` |
| **sad_num_epochs** | Cycles before entering "sad" state. | `25` |
| **bond_encounters_factor** | Bonding factor with other Pwnagotchis. | `20000` |
| **throttle_a** | Throttling for association (0.0-1.0). | `0.4` |
| **throttle_d** | Throttling for deauth (0.0-1.0). | `0.9` |

> **😺 Fun Fact**: Pwnagotchi changes moods (excited, bored, sad) based on its activity. Tweak these settings to make it more aggressive or chill!

---

## User Interface

The `[ui]` section controls the screen and web interface. Make your Pwnagotchi look cool! 😎

| Setting | Description | Default |
|---------|-------------|---------|
| **invert** | Set to `true` for white background, `false` for black. | `false` |
| **cursor** | Show/hide cursor on screen. | `true` |
| **fps** | Frames per second for display (0.0 = default). | `0.0` |

### 🖌️ Font
Customizes the display font.
- **name**: Font name (e.g., `DejaVuSansMono`, `fonts-japanese-gothic` for Japanese). Default: `DejaVuSansMono`.
- **size_offset**: Adjusts font size. Default: `0`.

### 😸 Faces
Sets ASCII art for Pwnagotchi’s emotions.
- **look_r**, **look_l**, etc.: ASCII for states like `happy`, `sad`. Example: `happy = "(•‿‿•)"`.
- **png**: Use PNG images instead of ASCII. Default: `false`.
- **position_x**, **position_y**: Face display coordinates. Default: `0`, `34`.

### 🌐 Web Interface
Controls the browser-based UI.
- **enabled**: Turn on/off. Default: `true`.
- **address**: Listening address (`::` for IPv4/IPv6, `0.0.0.0` for IPv4). Default: `::`.
- **auth**: Require login. Default: `false`.
- **username**, **password**: Web login credentials (if `auth = true`). Default: `changeme`.
- **origin**: Allowed web request origin. Default: `""`.
- **port**: Web server port. Default: `8080`.
- **on_frame**: Command to run per frame update. Default: `""`.

### 📺 Display
Configures the physical screen.
- **enabled**: Turn on/off. Default: `false`.
- **rotation**: Screen rotation (degrees). Default: `180`.
- **type**: Display type (e.g., `waveshare_4`). Default: `waveshare_4`.

> **🖼️ Display Tip**: Enable `ui.display` and set `type` to match your screen (e.g., Waveshare). Check the Pwnagotchi docs for supported displays!

---

## Bettercap

The `[bettercap]` section configures Bettercap, the tool Pwnagotchi uses for Wi-Fi hacking.

| Setting | Description | Default |
|---------|-------------|---------|
| **handshakes** | Directory for captured handshake files. | `/home/pi/handshakes` |
| **silence** | Bettercap events to hide from logs. | `["wifi.ap.new", "wifi.client.probe", ...]` |

---

## Filesystem Memory

The `[fs.memory]` section uses RAM for logs and temporary data to reduce SD card wear.

### 📝 Log Mount
Stores logs in RAM.
- **enabled**: Turn on/off. Default: `true`.
- **mount**: Log mount point. Default: `/etc/pwnagotchi/log/`.
- **size**: Filesystem size (e.g., `50M`). Default: `50M`.
- **sync**: Sync to disk interval (seconds). Default: `60`.
- **zram**: Use zram compression. Default: `true`.
- **rsync**: Sync to disk with rsync. Default: `true`.

### 📦 Data Mount
Stores temporary data in RAM.
- **enabled**: Turn on/off. Default: `true`.
- **mount**: Data mount point. Default: `/var/tmp/pwnagotchi`.
- **size**: Filesystem size. Default: `10M`.
- **sync**: Sync interval (seconds). Default: `3600`.
- **zram**: Use zram compression. Default: `true`.
- **rsync**: Sync to disk with rsync. Default: `true`.

---

## Tips for Beginners

<details>
<summary>🆕 New to Pwnagotchi? Click here for quick tips!</summary>

- **Start Simple**: Enable only a few plugins like `auto-tune`, `auto-update`, and `webcfg` to get started.
- **Protect Your Network**: Add your home Wi-Fi to `whitelist` to avoid accidental attacks.
- **Use the Web Interface**: Set `ui.web.enabled = true` and visit `http://<pwnagotchi-ip>:8080` to configure via browser.
- **Check Logs**: If something goes wrong, look at `/etc/pwnagotchi/log/pwnagotchi.log` for clues.
- **Backup Regularly**: Enable `auto_backup` to save your settings and handshakes.
- **Join the Community**: Visit [pwnagotchi.org](https://pwnagotchi.org/) or X for tips and plugin ideas!

</details>

---

## Contributing
Got ideas to improve this guide? Submit a pull request or issue on GitHub! For Pwnagotchi questions, check the [official docs](https://pwnagotchi.ai/) or community forums.

## License
This project is licensed under the MIT License. See the `LICENSE` file for details.

---

Happy hacking with your Pwnagotchi! 🎉
