# Pwnagotchi Tailscale Plugin

This plugin allows your Pwnagotchi to automatically connect to your Tailscale network using an authentication key. Once connected, it enables secure remote access (SSH, Web UI) and periodically synchronizes the `handshakes` directory to a server on your Tailnet using `rsync` over SSH.

The plugin provides on-screen status updates for the Tailscale connection and sync activity.

## Table of Contents
1.  [Prerequisites](#prerequisites)
2.  [Step 1: Server Setup](#step-1-server-setup)
3.  [Step 2: Pwnagotchi Setup](#step-2-pwnagotchi-setup)
4.  [Step 3: Get a Tailscale Auth Key](#step-3-get-a-tailscale-auth-key)
5.  [Step 4: Plugin Installation](#step-4-plugin-installation)
6.  [Step 5: Pwnagotchi Configuration](#step-5-pwnagotchi-configuration)
7.  [Step 6: Enable Handshake Sync (SSH Key Setup)](#step-6-enable-handshake-sync-ssh-key-setup)
8.  [Step 7: Final Restart and Verification](#step-7-final-restart-and-verification)
9.  [Status Indicators](#status-indicators)
10. [Troubleshooting](#troubleshooting)

---

### Prerequisites

* A Pwnagotchi device with network access for the initial setup.
* A free [Tailscale](https://tailscale.com/) account.
* A server or PC on your Tailscale network to receive the handshake files. This server must have an SSH server running.

---

### Step 1: Server Setup

1.  **Install Tailscale on your Server:** Follow the official instructions to install Tailscale on the machine that will receive the handshakes.
2.  **Log In and Find its IP:** Run `sudo tailscale up` on your server to connect it to your network. Then, run `tailscale ip -4` or visit the [Tailscale Admin Console](https://login.tailscale.com/admin/machines) to find the machine's **Tailscale IP address** (e.g., `100.X.X.X`). You will need this for the configuration.
3.  **Create the destination directory:** On your server, create the directory where handshakes will be stored:
    ```bash
    mkdir -p /path/to/remote/handshakes/
    ```

---

### Step 2: Pwnagotchi Setup

Log into your Pwnagotchi via SSH or a direct connection.

1.  **Install `rsync` and `curl`:**
    ```bash
    sudo apt-get update
    sudo apt-get install -y rsync curl
    ```

2.  **Install Tailscale:**
    ```bash
    curl -fsSL https://tailscale.com/install.sh | sh
    ```
    **Important:** You do **not** need to run `sudo tailscale up` manually. The plugin will handle authentication using an auth key.

---

### Step 3: Get a Tailscale Auth Key

The plugin will use an auth key to add your Pwnagotchi to your Tailnet automatically.

1.  Go to the [**Keys** page](https://login.tailscale.com/admin/settings/keys) in the Tailscale admin console.
2.  Click **Generate auth key**.
3.  **Recommended Settings:**
    * **Reusable:** No (for better security, generate a new key if you need to re-authenticate).
    * **Ephemeral:** Yes (the Pwnagotchi will be removed from your Tailnet if it's disconnected for a period of time, preventing clutter).
    * **Tags:** Optional (e.g., `tag:pwnagotchi`).
4.  Click **Generate key** and copy the key (it looks like `tskey-auth-k123...`). You will not be able to see it again.

---

### Step 4: Plugin Installation

1.  Download the plugin directly to the Pwnagotchi's custom plugins directory:
    ```bash
    sudo wget -O /usr/local/share/pwnagotchi/custom-plugins/tailscale.py https://raw.githubusercontent.com/wpa-2/Pwnagotchi-Plugins/refs/heads/main/tailscale.py
    ```

---

### Step 5: Pwnagotchi Configuration

1.  Open the main Pwnagotchi config file:
    ```bash
    sudo nano /etc/pwnagotchi/config.toml
    ```

2.  Add the following configuration block, filling in your specific details.
```toml
[main.plugins.tailscale]
enabled = true
auth_key = "tskey-auth-YOUR-KEY-HERE"
server_tailscale_ip = "100.X.X.X" # Your server's Tailscale IP
server_user = "your-server-user"  # The SSH username on your server
handshake_dir = "/path/to/remote/handshakes/" # Destination folder on your server

# Optional settings (defaults shown):
hostname = "pwnagotchi" # Custom device name in Tailnet
sync_interval_secs = 600 # How often to sync handshakes (10 minutes)
source_handshake_path = "/home/pi/handshakes/" # Local handshake directory (NOTE: trailing slash required)
```

**Configuration Notes:**
* **Required fields:** `auth_key`, `server_tailscale_ip`, `server_user`, `handshake_dir`
* **Optional fields:** All others have sensible defaults
* **Trailing Slash:** The `source_handshake_path` **must** end with a `/` for rsync to work correctly
* **Sync Interval:** Value is in seconds. 600 = 10 minutes, 300 = 5 minutes, etc.

---

### Step 6: Enable Handshake Sync (SSH Key Setup)

For the plugin to automatically sync handshakes with `rsync`, you need to set up passwordless SSH authentication. **This plugin uses a dedicated SSH key** (`id_rsa_tailscale`) to avoid conflicts with other plugins like WireGuard that may use their own SSH keys.

1.  **On the Pwnagotchi**, generate a dedicated SSH key for Tailscale sync. Press Enter at all prompts to accept defaults.
    ```bash
    sudo ssh-keygen -t rsa -b 4096 -f /root/.ssh/id_rsa_tailscale -N ""
    ```

2.  **On the Pwnagotchi**, display the new public key and copy the entire output.
    ```bash
    sudo cat /root/.ssh/id_rsa_tailscale.pub
    ```

3.  **On your Server**, add the Pwnagotchi's public key to the `authorized_keys` file for the user you specified in `server_user`.
    ```bash
    # Replace 'your-server-user' with the actual username if different
    echo "PASTE_PWNAGOTCHI_PUBLIC_KEY_HERE" >> /home/your-server-user/.ssh/authorized_keys
    
    # Ensure correct permissions
    chmod 700 /home/your-server-user/.ssh
    chmod 600 /home/your-server-user/.ssh/authorized_keys
    ```

4.  **Test the SSH connection** with the dedicated key:
    ```bash
    sudo ssh -i /root/.ssh/id_rsa_tailscale your-server-user@100.X.X.X
    ```
    You should connect without a password prompt. Type `exit` to disconnect.
    **Note:** Replace `100.X.X.X` with your server's Tailscale IP and `your-server-user` with your actual username.

---

### Step 7: Final Restart and Verification

1.  **On the Pwnagotchi**, restart the service to load all new configurations.
    ```bash
    sudo systemctl restart pwnagotchi
    ```

2.  **Verify:**
    * Watch the Pwnagotchi's screen. You should see the status change from `TS: Starting` → `TS: Conn...` → `TS: Up`.
    * Check your [Tailscale Admin Console](https://login.tailscale.com/admin/machines). The Pwnagotchi should appear as a new device.
    * After a sync interval (default 10 minutes), the status will briefly show `TS: Sync:X`, where X is the number of new handshake files transferred.
    * From your server or any other device on your Tailnet, you should be able to SSH into the Pwnagotchi using its hostname: `ssh pi@pwnagotchi`.

3.  **Check the logs** for detailed information:
    ```bash
    sudo journalctl -u pwnagotchi -f | grep Tailscale
    ```

---

### Status Indicators

The plugin displays a status indicator on the Pwnagotchi screen with the label `TS:`. Here's what each status means:

| Status | Meaning |
|--------|---------|
| `Starting` | Plugin is initializing |
| `Conn...` | Attempting to connect to Tailscale |
| `Up` | Successfully connected to Tailscale network |
| `Sync...` | Currently syncing handshakes to server |
| `Sync:X` | Successfully synced X new files (displayed briefly) |
| `Sync:99+` | Successfully synced 99+ files (displayed briefly) |
| `SyncErr` | Handshake sync failed (check logs) |
| `Error` | Connection attempt failed (retrying) |
| `Failed` | Connection failed after all retries |

---

### Troubleshooting

#### Plugin doesn't load
* Check the Pwnagotchi logs: `sudo journalctl -u pwnagotchi -f | grep Tailscale`
* Look for errors about missing config options
* Verify `rsync` and `tailscale` are installed: `which rsync` and `which tailscale`
* Ensure the plugin file has correct permissions: `sudo chmod 644 /usr/local/share/pwnagotchi/custom-plugins/tailscale.py`

#### Connection Fails or Status shows "Failed"
* Verify your `auth_key` is correct and has not expired
* If you used a non-reusable key, generate a new one
* Check if Tailscale is running: `sudo tailscale status`
* Manually test connection: `sudo tailscale up --authkey=YOUR-KEY-HERE --hostname=pwnagotchi`
* Check logs for specific error messages

#### Sync Fails or Status shows "SyncErr"
* **Test rsync manually** with the dedicated key:
  ```bash
  sudo rsync -avz -e "ssh -i /root/.ssh/id_rsa_tailscale" /home/pi/handshakes/ your-server-user@100.X.X.X:/path/to/remote/handshakes/
  ```
* **Common issues:**
  * SSH key not properly configured (see Step 6)
  * Incorrect server IP address
  * Wrong username or destination path
  * Missing trailing slash on `source_handshake_path`
  * Dedicated key file doesn't exist: `ls -la /root/.ssh/id_rsa_tailscale*`
* **Verify SSH key** is working:
  ```bash
  sudo ssh -i /root/.ssh/id_rsa_tailscale your-server-user@100.X.X.X
  ```
  Should connect without password prompt.
* **Check server permissions:**
  ```bash
  # On the server:
  chmod 700 ~/.ssh
  chmod 600 ~/.ssh/authorized_keys
  ```

#### Plugin loops on "Conn..." (v1.0.0 only)
* This was a bug in v1.0.0 where the plugin incorrectly validated Tailscale connection status
* **Solution:** Update to v1.0.1 or later
* The fix changed validation from looking for "Logged in as" to checking exit codes

#### Handshakes not appearing on server
* Verify the Pwnagotchi is actually capturing handshakes: `ls -la /home/pi/handshakes/`
* Check that the destination directory exists on the server
* Verify you've waited at least one sync interval (default 10 minutes)
* Check the logs for sync activity: `sudo journalctl -u pwnagotchi | grep "Sync complete"`
