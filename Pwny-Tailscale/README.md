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
9.  [Troubleshooting](#troubleshooting)

---

### Prerequisites

* A Pwnagotchi device with network access for the initial setup.
* A free [Tailscale](https://tailscale.com/) account.
* A server or PC on your Tailscale network to receive the handshake files. This server must have an SSH server running.

---

### Step 1: Server Setup

1.  **Install Tailscale on your Server:** Follow the official instructions to install Tailscale on the machine that will receive the handshakes.
2.  **Log In and Find its IP:** Run `sudo tailscale up` on your server to connect it to your network. Then, run `tailscale ip -4` or visit the [Tailscale Admin Console](https://login.tailscale.com/admin/machines) to find the machine's **Tailscale IP address** (e.g., `100.X.X.X`). You will need this for the configuration.

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
    curl -fsSL [https://tailscale.com/install.sh](https://tailscale.com/install.sh) | sh
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

1.  Place the `tailscale.py` script into the Pwnagotchi's custom plugins directory.
    ```bash
    # Make sure the directory exists
    sudo mkdir -p /usr/local/share/pwnagotchi/custom-plugins/
    
    # Move the plugin file (adjust the source path if needed)
    sudo mv /path/to/your/tailscale.py /usr/local/share/pwnagotchi/custom-plugins/
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
hostname = "pwnagotchi" # Custom device name in Tailnet
    ```

---

### Step 6: Enable Handshake Sync (SSH Key Setup)

For the plugin to automatically sync handshakes with `rsync`, the Pwnagotchi's `root` user needs an SSH key that your server trusts. This allows for passwordless login.

1.  **On the Pwnagotchi**, generate an SSH key for the `root` user. Press Enter at all prompts to accept the defaults.
    ```bash
    sudo ssh-keygen -t rsa -b 4096
    ```

2.  **On the Pwnagotchi**, display the new public key and copy the entire output.
    ```bash
    sudo cat /root/.ssh/id_rsa.pub
    ```

3.  **On your Server**, add the Pwnagotchi's public key to the `authorized_keys` file for the user you specified in `server_user`.
    ```bash
    # Replace 'your-server-user' with the actual username if different
    echo "PASTE_PWNAGOTCHI_PUBLIC_KEY_HERE" >> /home/your-server-user/.ssh/authorized_keys
    ```

---

### Step 7: Final Restart and Verification

1.  **On the Pwnagotchi**, restart the service to load all new configurations.
    ```bash
    sudo systemctl restart pwnagotchi
    ```

2.  **Verify:**
    * Watch the Pwnagotchi's screen. You should see the status change from `TS: Starting` -> `TS: Connecting` -> `TS: Up`.
    * Check your [Tailscale Admin Console](https://login.tailscale.com/admin/machines). The Pwnagotchi should appear as a new device.
    * After a sync interval (default 10 minutes), the status will briefly show `TS: Synced: X`, where X is the number of new handshake files transferred.
    * From your server or any other device on your Tailnet, you should be able to SSH into the Pwnagotchi using its new hostname: `ssh pi@pwnagotchi`.

---

### Troubleshooting

* **Plugin doesn't load:** Check the Pwnagotchi logs with `sudo journalctl -u pwnagotchi -f`. Look for errors related to `[Tailscale]`. Common issues are missing `config.toml` options or `rsync`/`tailscale` not being installed.
* **Connection Fails:** Ensure your `auth_key` is correct and has not expired. If you used a non-reusable key, you will need to generate a new one.
* **Sync Fails:**
    * Manually test the `rsync` command from the Pwnagotchi as the root user: `sudo rsync -av /home/pi/handshakes/ your-server-user@100.X.X.X:/path/to/remote/handshakes/`. This will help diagnose SSH key or path issues.
    * Verify the SSH key was copied correctly and that file permissions on your server's `.ssh` directory and `authorized_keys` file are correct (`700` for `.ssh`, `600` for `authorized_keys`).
