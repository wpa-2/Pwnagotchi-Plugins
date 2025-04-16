# Pwnagotchi Configuration Guide

This document provides a detailed explanation of the configuration options for a Pwnagotchi, a DIY, AI-powered Wi-Fi hacking tool. The configuration file is typically located at `/etc/pwnagotchi/config.toml` and controls various aspects of the device's behavior, plugins, and user interface. Below, each section and option is described to help you customize your Pwnagotchi effectively.

---

## Table of Contents
1. [Main Configuration (`[main]`)](#main-configuration)
2. [Plugins (`[main.plugins.*]`)](#plugins)
3. [Logging (`[main.log]`)](#logging)
4. [Personality (`[personality]`)](#personality)
5. [User Interface (`[ui]`)](#user-interface)
6. [Bettercap (`[bettercap]`)](#bettercap)
7. [Filesystem Memory (`[fs.memory]`)](#filesystem-memory)

---

## Main Configuration

The `[main]` section defines core settings for the Pwnagotchi.

- **name** (`string`): The name of your Pwnagotchi, displayed on the UI and used for identification.
  - Default: `"pwnagotchi"`
  - Example: `name = "MyPwnagotchi"`

- **lang** (`string`): The language for the Pwnagotchi interface.
  - Default: `"en"` (English)
  - Example: `lang = "es"` (Spanish)

- **iface** (`string`): The network interface used for monitoring Wi-Fi traffic.
  - Default: `"wlan0mon"`
  - Ensure the interface is in monitor mode.

- **mon_start_cmd** (`string`): Command to start monitor mode on the specified interface.
  - Default: `"/usr/bin/monstart"`
  - Example: `mon_start_cmd = "/usr/local/bin/start_monitor.sh"`

- **mon_stop_cmd** (`string`): Command to stop monitor mode.
  - Default: `"/usr/bin/monstop"`

- **mon_max_blind_epochs** (`integer`): Maximum number of epochs (cycles) the Pwnagotchi will operate without detecting networks before restarting.
  - Default: `5`

- **no_restart** (`boolean`): If `true`, prevents the Pwnagotchi from restarting automatically under certain conditions.
  - Default: `false`

- **whitelist** (`list`): List of SSIDs or MAC addresses to exclude from deauthentication or hacking attempts.
  - Example: `whitelist = ["MyHomeWiFi", "00:11:22:33:44:55"]`

- **confd** (`string`): Directory containing additional configuration files to merge with the main config.
  - Default: `"/etc/pwnagotchi/conf.d/"`

- **custom_plugin_repos** (`list`): URLs to custom plugin repositories for downloading additional plugins.
  - Example: `custom_plugin_repos = ["https://github.com/user/repo/archive/main.zip"]`

- **custom_plugins** (`string`): Directory where custom plugins are stored locally.
  - Default: `"/usr/local/share/pwnagotchi/custom-plugins/"`

---

## Plugins

The `[main.plugins.*]` sections configure various plugins to extend Pwnagotchi's functionality. Each plugin has an `enabled` flag and additional settings.

### Auto-Tune (`[main.plugins.auto-tune]`)
Optimizes Wi-Fi channel hopping for better performance.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `true`

### Auto Backup (`[main.plugins.auto_backup]`)
Automates backups of specified files.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **interval** (`string` or `integer`): Backup frequency (`"hourly"`, `"daily"`, or minutes).
  - Default: `"daily"`
- **max_tries** (`integer`): Maximum retry attempts for failed backups.
  - Default: `0` (unlimited)
- **backup_location** (`string`): Directory to store backups.
  - Default: `"/home/pi/"`
- **files** (`list`): Files/directories to back up.
  - Example: `files = ["/root/settings.yaml", "/home/pi/handshakes"]`
- **exclude** (`list`): Files/directories to exclude from backups.
  - Example: `exclude = ["/etc/pwnagotchi/logs/*"]`
- **commands** (`list`): Commands to execute for backup (e.g., `tar` for archiving).
  - Example: `commands = ["tar cf {backup_file} {files}"]`

### Auto-Update (`[main.plugins.auto-update]`)
Automatically updates Pwnagotchi software and plugins.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `true`
- **install** (`boolean`): If `true`, automatically installs updates.
  - Default: `true`
- **interval** (`integer`): Update check frequency (in days).
  - Default: `1`
- **token** (`string`): GitHub personal access token for API access (scope: `public_repo`).
  - Default: `""` (empty)

### Bluetooth Tethering (`[main.plugins.bt-tether]`)
Enables internet tethering via Bluetooth.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **phone-name** (`string`): Name of the phone as displayed in Bluetooth settings.
  - Default: `""`
- **mac** (`string`): Bluetooth MAC address of the phone.
  - Default: `""`
- **phone** (`string`): Phone type (`"android"` or `"ios"`).
  - Default: `""`
- **ip** (`string`): IP address for tethering.
  - Default: `"192.168.44.2"` (Android) or `"172.20.10.2"` (iOS)
- **dns** (`string`): DNS servers to use.
  - Default: `"8.8.8.8 1.1.1.1"` (Google DNS)

### Fix Services (`[main.plugins.fix_services]`)
Ensures critical services are running.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `true`

### Cache (`[main.plugins.cache]`)
Caches data to improve performance.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `true`

### Google Drive Sync (`[main.plugins.gdrivesync]`)
Syncs backups to Google Drive.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **backupfiles** (`list`): Files to sync.
  - Default: `[""]`
- **backup_folder** (`string`): Google Drive folder for backups.
  - Default: `"PwnagotchiBackups"`
- **interval** (`integer`): Sync frequency (in hours).
  - Default: `1`

### GPIO Buttons (`[main.plugins.gpio_buttons]`)
Enables GPIO-connected buttons for interaction.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`

### GPS (`[main.plugins.gps]`)
Provides GPS functionality for location tracking.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **speed** (`integer`): Baud rate for GPS device.
  - Default: `19200`
- **device** (`string`): GPS device path or GPSD server.
  - Default: `"/dev/ttyUSB0"` or `"localhost:2947"` for GPSD

### GPS Listener (`[main.plugins.gps_listener]`)
Listens for GPS data.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`

### Grid (`[main.plugins.grid]`)
Interacts with the Pwnagotchi community grid.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `true`
- **report** (`boolean`): If `true`, reports captured handshakes to the grid.
  - Default: `true`

### Logtail (`[main.plugins.logtail]`)
Displays recent log entries on the Pwnagotchi screen.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **max-lines** (`integer`): Maximum number of log lines to display.
  - Default: `10000`

### Memory/Temperature (`[main.plugins.memtemp]`)
Displays system memory and temperature.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **scale** (`string`): Temperature scale (`"celsius"` or `"fahrenheit"`).
  - Default: `"celsius"`
- **orientation** (`string`): Display orientation (`"horizontal"` or `"vertical"`).
  - Default: `"horizontal"`

### OHC API (`[main.plugins.ohcapi]`)
Integrates with an external API (specific to certain setups).
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **api_key** (`string`): API key for authentication.
  - Default: `"sk_your_api_key_here"`
- **receive_email** (`string`): Whether to receive email notifications (`"yes"` or `"no"`).
  - Default: `"yes"`

### PwnDroid (`[main.plugins.pwndroid]`)
Displays GPS coordinates or altitude on the screen.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **display** (`boolean`): Show coordinates on the display.
  - Default: `false`
- **display_altitude** (`boolean`): Show altitude on the display.
  - Default: `false`

### PiSugarX (`[main.plugins.pisugarx]`)
Manages PiSugar battery modules.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **rotation** (`boolean`): Rotate display output.
  - Default: `false`
- **default_display** (`string`): Display mode (`"percentage"` or other).
  - Default: `"percentage"`
- **lowpower_shutdown** (`boolean`): Shut down when battery is low.
  - Default: `true`
- **lowpower_shutdown_level** (`integer`): Battery percentage for shutdown.
  - Default: `10`
- **max_charge_voltage_protection** (`boolean`): Limits battery charge to ~80% to extend lifespan.
  - Default: `false`

### PwnCrack (`[main.plugins.pwncrack]`)
Automates cracking of captured handshakes.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **key** (`string`): API key for cracking service.
  - Default: `""`

### Session Stats (`[main.plugins.session-stats]`)
Tracks session statistics.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **save_directory** (`string`): Directory to save session data.
  - Default: `"/var/tmp/pwnagotchi/sessions/"`

### UPS Hat C (`[main.plugins.ups_hat_c]`)
Manages UPS Hat C battery module.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **label_on** (`boolean`): Show "BAT" label or just percentage.
  - Default: `true`
- **shutdown** (`integer`): Battery percentage for shutdown.
  - Default: `5`
- **bat_x_coord** (`integer`): X-coordinate for battery display.
  - Default: `140`
- **bat_y_coord** (`integer`): Y-coordinate for battery display.
  - Default: `0`

### UPS Lite (`[main.plugins.ups_lite]`)
Manages UPS Lite battery module.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **shutdown** (`integer`): Battery percentage for shutdown.
  - Default: `2`

### Web Configuration (`[main.plugins.webcfg]`)
Provides a web interface for configuration.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `true`

### Web GPS Map (`[main.plugins.webgpsmap]`)
Displays GPS data on a web-based map.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`

### Wigle (`[main.plugins.wigle]`)
Uploads Wi-Fi data to Wigle.net.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **api_key** (`string`): Wigle API key.
  - Default: `""`
- **cvs_dir** (`string`): Directory for CSV output.
  - Default: `"/tmp"`
- **donate** (`boolean`): Donate data to Wigle.
  - Default: `false`
- **timeout** (`integer`): Upload timeout (seconds).
  - Default: `30`
- **position** (`list`): Display position for Wigle data `[x, y]`.
  - Default: `[7, 85]`

### WPA-Sec (`[main.plugins.wpa-sec]`)
Uploads handshakes to wpa-sec.stanev.org for cracking.
- **enabled** (`boolean`): Enable/disable the plugin.
  - Default: `false`
- **api_key** (`string`): WPA-Sec API key.
  - Default: `""`
- **api_url** (`string`): WPA-Sec API endpoint.
  - Default: `"https://wpa-sec.stanev.org"`
- **download_results** (`boolean`): Download cracking results.
  - Default: `false`
- **show_pwd** (`boolean`): Display cracked passwords.
  - Default: `false`

---

## Logging

The `[main.log]` section configures logging behavior.

- **path** (`string`): Path to the main log file.
  - Default: `"/etc/pwnagotchi/log/pwnagotchi.log"`
- **path-debug** (`string`): Path to the debug log file.
  - Default: `"/etc/pwnagotchi/log/pwnagotchi-debug.log"`

### Log Rotation (`[main.log.rotation]`)
Manages log file rotation to prevent excessive disk usage.
- **enabled** (`boolean`): Enable/disable log rotation.
  - Default: `true`
- **size** (`string`): Maximum log file size before rotation (e.g., `"10M"` for 10MB).
  - Default: `"10M"`

---

## Personality

The `[personality]` section controls the Pwnagotchi's AI behavior and Wi-Fi interaction settings.

- **advertise** (`boolean`): If `true`, advertises the Pwnagotchi as an access point.
  - Default: `true`
- **deauth** (`boolean`): If `true`, performs deauthentication attacks to capture handshakes.
  - Default: `true`
- **associate** (`boolean`): If `true`, associates with nearby access points.
  - Default: `true`
- **channels** (`list`): Wi-Fi channels to scan (empty for all).
  - Default: `[]`
- **min_rssi** (`integer`): Minimum signal strength (dBm) for networks to consider.
  - Default: `-200`
- **ap_ttl** (`integer`): Time-to-live (seconds) for access point advertisements.
  - Default: `120`
- **sta_ttl** (`integer`): Time-to-live (seconds) for station (client) connections.
  - Default: `300`
- **recon_time** (`integer`): Time (seconds) for reconnaissance scans.
  - Default: `30`
- **max_inactive_scale** (`integer`): Multiplier for inactive network detection.
  - Default: `2`
- **recon_inactive_multiplier** (`integer`): Multiplier for inactive reconnaissance.
  - Default: `2`
- **hop_recon_time** (`integer`): Time (seconds) for channel hopping during recon.
  - Default: `10`
- **min_recon_time** (`integer`): Minimum time (seconds) for reconnaissance.
  - Default: `5`
- **max_interactions** (`integer`): Maximum interactions per network per epoch.
  - Default: `3`
- **max_misses_for_recon** (`integer`): Maximum missed scans before considering a network inactive.
  - Default: `5`
- **excited_num_epochs** (`integer`): Epochs before transitioning from "excited" state.
  - Default: `10`
- **bored_num_epochs** (`integer`): Epochs before transitioning to "bored" state.
  - Default: `15`
- **sad_num_epochs** (`integer`): Epochs before transitioning to "sad" state.
  - Default: `25`
- **bond_encounters_factor** (`integer`): Factor for calculating bonding with other Pwnagotchis.
  - Default: `20000`
- **throttle_a** (`float`): Throttling factor for association.
  - Default: `0.4`
- **throttle_d** (`float`): Throttling factor for deauthentication.
  - Default: `0.9`

---

## User Interface

The `[ui]` section configures the Pwnagotchi's display and web interface.

- **invert** (`boolean`): If `true`, inverts the display (white background, black text).
  - Default: `false` (black background)
- **cursor** (`boolean`): Show/hide the cursor on the display.
  - Default: `true`
- **fps** (`float`): Frames per second for display updates (0.0 for default).
  - Default: `0.0`

### Font (`[ui.font]`)
Configures the display font.
- **name** (`string`): Font name (e.g., `"DejaVuSansMono"`, `"fonts-japanese-gothic"` for Japanese).
  - Default: `"DejaVuSansMono"`
- **size_offset** (`integer`): Adjustment to font size.
  - Default: `0`

### Faces (`[ui.faces]`)
Defines ASCII art for Pwnagotchi's emotional states.
- **look_r**, **look_l**, etc. (`string`): ASCII art for various states (e.g., happy, sad).
  - Example: `happy = "(•‿‿•)"`
- **png** (`boolean`): If `true`, uses PNG images instead of ASCII.
  - Default: `false`
- **position_x**, **position_y** (`integer`): Coordinates for face display.
  - Default: `position_x = 0`, `position_y = 34`

### Web Interface (`[ui.web]`)
Configures the web-based UI.
- **enabled** (`boolean`): Enable/disable the web interface.
  - Default: `true`
- **address** (`string`): Listening address (`"::"` for IPv4/IPv6, `"0.0.0.0"` for IPv4 only).
  - Default: `"::"`
- **auth** (`boolean`): Enable/disable authentication.
  - Default: `false`
- **username**, **password** (`string`): Credentials for web access (if `auth = true`).
  - Default: `"changeme"`
- **origin** (`string`): Allowed origin for web requests.
  - Default: `""`
- **port** (`integer`): Web server port.
  - Default: `8080`
- **on_frame** (`string`): Command to run on each frame update.
  - Default: `""`

### Display (`[ui.display]`)
Configures the physical display.
- **enabled** (`boolean`): Enable/disable the display.
  - Default: `false`
- **rotation** (`integer`): Display rotation (degrees).
  - Default: `180`
- **type** (`string`): Display type (e.g., `"waveshare_4"`).
  - Default: `"waveshare_4"`

---

## Bettercap

The `[bettercap]` section configures the Bettercap framework, which Pwnagotchi uses for Wi-Fi hacking.

- **handshakes** (`string`): Directory to store captured handshake files.
  - Default: `"/home/pi/handshakes"`
- **silence** (`list`): Bettercap events to suppress in logs.
  - Example: `silence = ["wifi.ap.new", "wifi.client.probe"]`

---

## Filesystem Memory

The `[fs.memory]` section configures in-memory filesystems for logs and temporary data.

### Log Mount (`[fs.memory.mounts.log]`)
Mounts logs to a RAM-based filesystem.
- **enabled** (`boolean`): Enable/disable the mount.
  - Default: `true`
- **mount** (`string`): Mount point for logs.
  - Default: `"/etc/pwnagotchi/log/"`
- **size** (`string`): Size of the filesystem (e.g., `"50M"`).
  - Default: `"50M"`
- **sync** (`integer`): Sync interval (seconds) to disk.
  - Default: `60`
- **zram** (`boolean`): Use zram for compression.
  - Default: `true`
- **rsync** (`boolean`): Sync to disk using rsync.
  - Default: `true`

### Data Mount (`[fs.memory.mounts.data]`)
Mounts temporary data to a RAM-based filesystem.
- **enabled** (`boolean`): Enable/disable the mount.
  - Default: `true`
- **mount** (`string`): Mount point for data.
  - Default: `"/var/tmp/pwnagotchi"`
- **size** (`string`): Size of the filesystem.
  - Default: `"10M"`
- **sync** (`integer`): Sync interval (seconds).
  - Default: `3600`
- **zram** (`boolean`): Use zram for compression.
  - Default: `true`
- **rsync** (`boolean`): Sync to disk using rsync.
  - Default: `true`

---

## Contributing
Feel free to contribute to this documentation by submitting pull requests or issues on the GitHub repository. For Pwnagotchi-specific questions, refer to the official [Pwnagotchi documentation](https://pwnagotchi.ai/) or community forums.

## License
This project is licensed under the MIT License. See the `LICENSE` file for details.
