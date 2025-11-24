# Pwnagotchi WireGuard Plugin (v1.8)

This plugin allows your Pwnagotchi to automatically connect to a home WireGuard VPN server.

* **Secure Access:** SSH into your Pwnagotchi from anywhere in the world.
* **Gapless Sync:** Automatically syncs **only new** handshakes to your server. It uses a smart "checkpoint" system, so the sync takes seconds even if you have 50,000 old files on your SD card.
* **Resilient:** Automatically retries connections if the network is spotty.

## Table of Contents
1.  [Prerequisites](#prerequisites)
2.  [Step 1: Server Setup](#step-1-server-setup)
3.  [Step 2: Pwnagotchi Dependency Installation](#step-2-pwnagotchi-dependency-installation)
4.  [Step 3: Plugin Installation](#step-3-plugin-installation)
5.  [Step 4: Pwnagotchi Configuration](#step-4-pwnagotchi-configuration)
6.  [Step 5: Enable Passwordless Sync (The Easy Way)](#step-5-enable-passwordless-sync-the-easy-way)
7.  [Step 6: Enable Full Remote Access](#step-6-enable-full-remote-access)
8.  [Troubleshooting](#troubleshooting)

---

### Prerequisites

* A Pwnagotchi device.
* A working WireGuard VPN server (e.g., PiVPN running on a Raspberry Pi at home).
* **Important:** If you have multiple Pwnagotchis, **every device needs its own unique WireGuard Client Profile**. Do not share keys between devices.

---

### Step 1: Server Setup

On your WireGuard server, create a new client profile for your Pwnagotchi.

1.  **Create the Client Profile:**
    ```bash
    # If using PiVPN, run:
    pivpn add
    ```
    Name it something unique (e.g., `pwnagotchi-01`).

2.  **Get the Configuration:**
    Open the generated `.conf` file (e.g., `cat configs/pwnagotchi-01.conf`). You will need the **Private Key**, **Address**, and **Public Key** from this file for Step 4.

---

### Step 2: Pwnagotchi Dependency Installation

Log into your Pwnagotchi via SSH and install the required system tools.

```bash
sudo apt-get update
# Install rsync (for syncing) and WireGuard tools (for the connection)
sudo apt-get install rsync wireguard wireguard-tools openresolv -y
```

---

### Step 3: Plugin Installation

1.  Place the `wireguard.py` script into the Pwnagotchi's custom plugins directory.
    ```bash
    # Make sure the directory exists
    sudo mkdir -p /usr/local/share/pwnagotchi/custom-plugins/
    
    # Move the plugin file (adjust the source path if needed)
    sudo mv wireguard.py /usr/local/share/pwnagotchi/custom-plugins/
    ```

---

### Step 4: Pwnagotchi Configuration

Open the config file: `sudo nano /etc/pwnagotchi/config.toml`

Add the following block. **You must replace the values with data from your Step 1 `.conf` file.**

```toml
main.plugins.wireguard.enabled = true
main.plugins.wireguard.wg_config_path = "/tmp/wg0.conf"

# --- SECURITY KEYS (From your .conf file) ---
main.plugins.wireguard.private_key = "PASTE_YOUR_PRIVATE_KEY_HERE"
main.plugins.wireguard.peer_public_key = "PASTE_SERVER_PUBLIC_KEY_HERE"
# Only if your .conf has a PresharedKey:
main.plugins.wireguard.preshared_key = "PASTE_PRESHARED_KEY_HERE"

# --- NETWORK SETTINGS ---
# The IP *inside* the VPN. MUST be unique for every Pwnagotchi (e.g., .5, .6, .7)
main.plugins.wireguard.address = "10.x.x.x/24"
main.plugins.wireguard.dns = "9.9.9.9"

# Your home IP/DDNS. Example: "myhome.duckdns.org:51820"
main.plugins.wireguard.peer_endpoint = "YOUR_PUBLIC_IP:51820"

# --- SYNC SETTINGS ---
main.plugins.wireguard.server_user = "pi"
main.plugins.wireguard.server_port = 22
main.plugins.wireguard.handshake_dir = "/home/pi/handshakes/"

# Increase delay if you see DNS errors on boot (default 60)
main.plugins.wireguard.startup_delay_secs = 60
```

---

### Step 5: Enable Passwordless Sync (The Easy Way)

We need to give your Pwnagotchi a "key" to unlock your server without typing a password.

**1. Generate the Key (One Command)**
Run this on your Pwnagotchi. It creates the key and sets an empty password automatically.
```bash
sudo ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""
```

**2. Send Key to Server**
Run this to copy the key to your server.
* **CRITICAL:** Use your server's **Local LAN IP** here (e.g., `192.168.1.50`), NOT the WireGuard IP. The VPN isn't on yet!

```bash
# Syntax: sudo ssh-copy-id -i /root/.ssh/id_ed25519.pub -p <PORT> <USER>@<LAN_IP>
sudo ssh-copy-id -i /root/.ssh/id_ed25519.pub -p 22 pi@192.168.1.50
```
*(Enter your server password when asked. It should say "Number of key(s) added: 1".)*

**3. Test It**
```bash
sudo ssh -p 22 -i /root/.ssh/id_ed25519 pi@192.168.1.50 "echo Success"
```
*If it says "Success" without asking for a password, proceed.*

---

### Step 6: Enable Full Remote Access

To access the Pwnagotchi from your phone or PC over the VPN, your server needs to know how to route the traffic.

1.  **On your Server**, enable IP forwarding:
    ```bash
    sudo nano /etc/sysctl.conf
    # Uncomment: net.ipv4.ip_forward=1
    sudo sysctl -p
    ```

2.  **Add Firewall Rules:**
    Edit your server config (`/etc/wireguard/wg0.conf`) and add these lines under `[Interface]`:
    ```ini
    PostUp = iptables -A FORWARD -i %i -o %i -j ACCEPT
    PostDown = iptables -D FORWARD -i %i -o %i -j ACCEPT
    ```
    *Restart the server WireGuard service after saving (`sudo systemctl restart wg-quick@wg0`).*

---

### Step 7: Final Restart

Restart your Pwnagotchi:
```bash
sudo systemctl restart pwnagotchi
```

**What to look for:**
1.  **Screen:** Status changes from `WG: Conn...` to `WG: Up`.
2.  **Sync:** After a few minutes, it may show `WG: Sync: X` (where X is the number of **new** handshakes sent).
3.  **Logs:** `tail -f /var/log/pwnagotchi.log | grep WireGuard`

---

### Troubleshooting

* **DNS Errors / "No address associated with hostname":**
    * This happens on boot if the internet isn't ready yet. The plugin will auto-retry.
    * Fix: Increase `main.plugins.wireguard.startup_delay_secs` to `60` or `120`.
* **Permission denied (publickey):**
    * You likely generated the SSH keys as the default user `pi` but the plugin runs as `root`. Rerun **Step 5** exactly as written using `sudo`.
* **Devices kicking each other off:**
    * You are using the same `Address` (IP) or `PrivateKey` on two different Pwnagotchis.
    * **Fix:** Generate a new client (`pivpn add`) on the server for the second device and update its `config.toml`.
* **Sync is slow:**
    * Ensure you are using plugin **v1.8**. It uses a "Checkpoint" system to ignore old files.
    * Check logs: `Plugin loaded. Checkpoint system active.`
