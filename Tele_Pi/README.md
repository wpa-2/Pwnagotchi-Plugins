# Pi Manager Bot for Telegram 🤖

A powerful, asynchronous Telegram bot designed to securely monitor and manage a Linux-based system (like a Raspberry Pi) from anywhere.

![Bot Screenshot](https://placehold.co/600x400/1e1e2e/d4d4d4?text=Bot+Interface+Screenshot)

This bot provides a convenient menu-driven interface to run system commands, check network status, get system metrics, and use various utilities, all from the comfort of your Telegram chat.

---

## ✨ Features

The bot's commands are neatly organized into three categories for ease of use.

### ⚙️ System Management
- **System Updates:** Update and upgrade system packages with `apt`.
- **Power Control:** Safely reboot or shut down the system.
- **Resource Monitoring:**
    - Check disk usage (`df -h`).
    - View free memory (`free -m`).
    - Get current CPU temperature.
    - List all running processes (`ps -ef`).
    - List systemd services.
- **Automated Alerts:** Set up recurring jobs to monitor CPU temperature and RAM usage, receiving alerts if they exceed predefined thresholds.
- **Status Overview:** Get a quick, clean summary of the system's vital signs (CPU temp, RAM/disk usage, uptime).

### 🌐 Network Tools
- **IP Information:** Display local and external IP addresses.
- **Network Scanning:** Scan for available Wi-Fi networks using `nmcli`.
- **Connectivity Check:** Ping any remote host to check for connectivity.
- **Detailed Stats:** Show detailed statistics for network interfaces.

### 🛠️ Utilities
- **Speed Test:** Run an internet speed test using `speedtest-cli`.
- **System Uptime:** Check how long the system has been running.
- **Weather Forecast:** Get the current weather for any city using the OpenWeatherMap API.
- **Random Joke:** Fetch a random programming joke to lighten the mood.

---

## 🚀 Setup and Installation

Follow these steps to get your bot up and running.

### 1. Prerequisites
- **Python 3.8+**
- The `python3-venv` package. Install it with: `sudo apt install python3-venv`
- A **Telegram Bot Token**. Get one from [@BotFather](https://t.me/BotFather) on Telegram.
- An **OpenWeatherMap API Key**. Get a free key from [OpenWeatherMap](https://openweathermap.org/appid).
- Your **Telegram User ID**. Get it from a bot like [@userinfobot](https://t.me/userinfobot).

### 2. Clone the Repository
```bash
git clone <your-repository-url>
cd <your-repository-directory>
```

### 3. Create and Activate a Virtual Environment
Using a virtual environment is the recommended way to manage Python packages and avoid conflicts with system packages.

> **Important Note on Permissions:** If you are installing in a system-owned directory like `/opt`, you may encounter permission errors. To fix this, first assign ownership of the directory to your user. **Run this command before creating the virtual environment:**
> ```bash
> # Replace /opt with your chosen directory if different
> sudo chown -R $(whoami) /opt
> ```

Now, create and activate the virtual environment:
```bash
# Create the virtual environment (do NOT use sudo)
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate
```
*Your terminal prompt should now be prefixed with `(.venv)`.*

### 4. Install Dependencies
With the virtual environment active, install the required Python libraries.
```bash
pip install -r requirements.txt
```
*(If you don't have a `requirements.txt` file, create one with the following content:)*
```
python-telegram-bot==21.2
psutil
requests
```
*Once done, you can leave the virtual environment for now by typing `deactivate`.*

### 5. Configure Passwordless Sudo (Recommended)
For commands like `/reboot`, `/shutdown`, and `/update` to work seamlessly, you need to grant passwordless `sudo` permissions for those specific commands to the user running the script.

1.  Open the `sudoers` file for editing by running:
    ```bash
    sudo visudo
    ```
2.  Add the following lines at the end of the file, replacing `your_username` with your actual Linux username:
    ```
    # Allow the bot user to run specific commands without a password
    your_username ALL=(ALL) NOPASSWD: /usr/bin/reboot
    your_username ALL=(ALL) NOPASSWD: /usr/bin/shutdown
    your_username ALL=(ALL) NOPASSWD: /usr/bin/apt update
    your_username ALL=(ALL) NOPASSWD: /usr/bin/apt upgrade -y
    ```
3.  Save and exit the editor.

---

## ⚙️ Running the Bot

You can run the bot manually for testing or set it up as a `systemd` service to run automatically on boot.

### Manually (for Testing)
1.  Activate the virtual environment:
    ```bash
    source .venv/bin/activate
    ```
2.  Set your environment variables:
    ```bash
    export TELEGRAM_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
    export WEATHER_API_KEY="YOUR_OPENWEATHERMAP_API_KEY"
    export ALLOWED_USER_ID="YOUR_TELEGRAM_USER_ID"
    ```
3.  Run the script:
    ```bash
    python3 pi_bot.py
    ```

### As a Systemd Service (Recommended for Production)

This method will ensure your bot starts automatically on boot and restarts if it crashes.

**Step 1: Create an Environment File for Secrets**

Create a file to hold your secret keys. This is more secure and works reliably with `systemd`.

```bash
# Create and open the file
nano /opt/telegram_bot.env
```

Add your secrets to this file in the following format ( **do not use `export` or quotes**):
```
TELEGRAM_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
WEATHER_API_KEY=YOUR_OPENWEATHERMAP_API_KEY
ALLOWED_USER_ID=YOUR_TELEGRAM_USER_ID
```
Save the file (`Ctrl+O`, `Enter`) and exit (`Ctrl+X`). Secure it so only the owner can read it:
```bash
chmod 600 /opt/telegram_bot.env
```

**Step 2: Create the Systemd Service File**

Create a new service file for your bot:
```bash
sudo nano /etc/systemd/system/telegram-bot.service
```

Paste the following configuration into the file. **Make sure to replace `your_username` with your actual Linux username** (e.g., `pi`, `wpa2`).

```ini
[Unit]
Description=My Telegram Pi Manager Bot
After=network.target

[Service]
User=your_username
Group=your_username
WorkingDirectory=/opt
EnvironmentFile=/opt/telegram_bot.env
ExecStart=/opt/.venv/bin/python3 /opt/pi_bot.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```
Save and exit the editor.

**Step 3: Enable and Start the Service**

Now, tell `systemd` to reload, enable, and start your new service.
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot.service
sudo systemctl start telegram-bot.service
```

**Step 4: Check the Status**

You can check if the service is running correctly:
```bash
sudo systemctl status telegram-bot.service
```
To see the live logs from your bot, use:
```bash
sudo journalctl -u telegram-bot.service -f
```

---

## 📖 Command Reference

| Command                  | Description                                      | Arguments         |
| ------------------------ | ------------------------------------------------ | ----------------- |
| **System** |                                                  |                   |
| `/update`                | Updates and upgrades system packages.            | None              |
| `/reboot`                | Reboots the system.                              | None              |
| `/shutdown`              | Shuts down the system.                           | None              |
| `/disk_usage`            | Shows file system disk space usage.              | None              |
| `/free_memory`           | Shows system memory usage.                       | None              |
| `/show_processes`        | Lists all currently running processes.           | None              |
| `/show_system_services`  | Lists all systemd services.                      | None              |
| `/start_monitoring`      | Starts monitoring CPU temperature.               | None              |
| `/stop_monitoring`       | Stops monitoring CPU temperature.                | None              |
| `/start_monitoring_ram`  | Starts monitoring RAM usage.                     | None              |
| `/stop_monitoring_ram`   | Stops monitoring RAM usage.                      | None              |
| `/temp`                  | Shows the current CPU temperature.               | None              |
| `/status`                | Shows a brief overview of system status.         | None              |
| **Network** |                                                  |                   |
| `/ip`                    | Shows all IP addresses for all interfaces.       | None              |
| `/external_ip`           | Gets the public-facing IP address.               | None              |
| `/wifi`                  | Scans for and lists available WiFi networks.     | None              |
| `/ping`                  | Pings a remote host to check connectivity.       | `<hostname/IP>`   |
| `/show_network_info`     | Shows detailed network interface statistics.     | None              |
| **Utility** |                                                  |                   |
| `/speedtest`             | Runs an internet speed test.                     | None              |
| `/uptime`                | Shows how long the system has been running.      | None              |
| `/weather`               | Gets the current weather for a specified city.   | `<city name>`     |
| `/joke`                  | Tells a random programming joke.                 | None              |

---

## 🔒 Security
- **User Restriction:** Access is strictly limited to the `ALLOWED_USER_ID`.
- **Secure Key Storage:** API keys and tokens are managed via an environment file with restricted permissions.
- **Safe Subprocess Calls:** All external commands are run using `asyncio.create_subprocess_exec` with arguments passed as a list (`shell=False`), preventing shell injection vulnerabilities.

---

## 🤝 Contributing
Contributions are welcome! If you have ideas for new features or improvements, feel free to fork the repository, make your changes, and submit a pull request.

---

## 📄 License
This project is licensed under the MIT License. See the `LICENSE` file for details.