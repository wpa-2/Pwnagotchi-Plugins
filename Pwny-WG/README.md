# Pwnagotchi WireGuard Plugin

This plugin allows your Pwnagotchi to automatically connect to a home WireGuard VPN server. Once connected, it enables secure remote access (SSH, Web UI) and periodically synchronizes handshakes to your server using `rsync`.

## Table of Contents
1.  [Prerequisites](#prerequisites)
2.  [Step 1: Server Setup](#step-1-server-setup)
3.  [Step 2: Pwnagotchi Dependency Installation](#step-2-pwnagotchi-dependency-installation)
4.  [Step 3: Plugin Installation](#step-3-plugin-installation)
5.  [Step 4: Pwnagotchi Configuration](#step-4-pwnagotchi-configuration)
6.  [Step 5: Enable Passwordless Sync (SSH Key Setup)](#step-5-enable-passwordless-sync-ssh-key-setup)
7.  [Step 6: Enable Full Remote Access (Server Firewall)](#step-6-enable-full-remote-access-server-firewall)
8.  [Step 7: Final Restart and Verification](#step-7-final-restart-and-verification)
9.  [Troubleshooting](#troubleshooting)

---

### Prerequisites

* A Pwnagotchi device with network access for the initial setup.
* A working WireGuard VPN server (e.g., set up with PiVPN).
* A server or PC on your VPN to act as the sync destination.

---

### Step 1: Server Setup

On your WireGuard server, create a new client profile for your Pwnagotchi.

1.  **Create the Client Profile:**
    ```bash
    # If using PiVPN, run:
    pivpn add
    ```
    When prompted, give it a name like `pwnagotchi-client`.

2.  **Get the Configuration:**
    PiVPN will create a `.conf` file (e.g., `/home/your-user/configs/pwnagotchi-client.conf`). You will need the keys and endpoint information from this file for Step 4.

---

### Step 2: Pwnagotchi Dependency Installation

Log into your Pwnagotchi via SSH and install `rsync`.

```bash
sudo apt-get update
sudo apt-get install rsync
```

---

### Step 3: Plugin Installation

1.  Place the `wireguard.py` script into the Pwnagotchi's custom plugins directory.
    ```bash
    # Make sure the directory exists
    sudo mkdir -p /usr/local/share/pwnagotchi/custom-plugins/
    
    # Move the plugin file (adjust the source path if needed)
    sudo mv /path/to/your/wireguard.py /usr/local/share/pwnagotchi/custom-plugins/
    ```

---

### Step 4: Pwnagotchi Configuration

1.  Open the main Pwnagotchi config file:
    ```bash
    sudo nano /etc/pwnagotchi/config.toml
    ```

2.  Add the following **required** configuration block.

    ```toml
    # --- Required WireGuard Settings ---
    main.plugins.wireguard.enabled = true
    main.plugins.wireguard.private_key = "PASTE_CLIENT_PRIVATE_KEY_HERE"
    main.plugins.wireguard.address = "10.x.x.x/24"
    main.plugins.wireguard.peer_public_key = "PASTE_SERVER_PUBLIC_KEY_HERE"
    main.plugins.wireguard.peer_endpoint = "your.server.com:51820"
    main.plugins.wireguard.server_user = "your-user-on-server"
    main.plugins.wireguard.handshake_dir = "/home/your-user/pwnagotchi_handshakes/"
    ```

#### Optional Configuration

You can add any of the following optional lines to the configuration block to customize the plugin's behavior.

```toml
# --- Optional Settings ---

# Add a preshared key for extra security (recommended)
main.plugins.wireguard.preshared_key = "PASTE_PRESHARED_KEY_HERE"

# Set a custom DNS server for the Pwnagotchi to use when connected
main.plugins.wireguard.dns = "9.9.9.9"

# Specify a custom SSH port if your server doesn't use port 22
main.plugins.wireguard.server_port = 2222

# Change the sync interval in seconds (default is 600 = 10 minutes)
main.plugins.wireguard.sync_interval = 600

# Delay connection on boot to allow network to settle (default 60)
main.plugins.wireguard.startup_delay_secs = 60
```

---

### Step 5: Enable Passwordless Sync (SSH Key Setup)

For the plugin to automatically sync files, the Pwnagotchi (running as `root`) needs permission to log into your server. We will generate a key and send it to your server using a utility that handles file permissions automatically.

1.  **Generate a Key for Root:**
    Run this on your Pwnagotchi. Press **Enter** at all prompts to accept defaults (do not set a password).
    ```bash
    sudo ssh-keygen -t ed25519
    ```

2.  **Send Key to Server:**
    Run this command to automatically copy the key to your server.
    *(Replace `2222` with your SSH port, `your-server-user` with your actual username, and `10.x.x.x` with your server IP).*

    ```bash
    sudo ssh-copy-id -i /root/.ssh/id_ed25519.pub -p 2222 your-server-user@10.x.x.x
    ```
    *You will be asked for your server password one last time. Once it says "Number of key(s) added: 1", you are done!*

3.  **Test the Connection:**
    Verify it works without a password:
    ```bash
    sudo ssh -p 2222 your-server-user@10.x.x.x "echo Connection Successful"
    ```

---

### Step 6: Enable Full Remote Access (Server Firewall)

To access your Pwnagotchi from your home network or from other VPN clients (like your phone), you must configure your WireGuard server's firewall.

1.  **On your WireGuard Server**, enable IP forwarding:
    ```bash
    # Uncomment the net.ipv4.ip_forward=1 line
    sudo nano /etc/sysctl.conf
    # Apply the change immediately
    sudo sysctl -p
    ```

2.  **On your WireGuard Server**, add forwarding rules to the WireGuard config file (`/etc/wireguard/wg0.conf`). Replace `eth0` with your server's main LAN interface name.
    ```ini
    # Add these lines under the [Interface] section of wg0.conf
    
    # Rule for VPN clients to access your home LAN and the internet
    PostUp = iptables -A FORWARD -i %i -o eth0 -j ACCEPT; iptables -A FORWARD -i eth0 -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    PostDown = iptables -D FORWARD -i %i -o eth0 -j ACCEPT; iptables -D FORWARD -i eth0 -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
    
    # Rule for VPN clients to talk to each other (e.g., phone -> pwnagotchi)
    PostUp = iptables -A FORWARD -i %i -o %i -j ACCEPT
    PostDown = iptables -D FORWARD -i %i -o %i -j ACCEPT
    ```

---

### Step 7: Final Restart and Verification

1.  **On your WireGuard Server**, restart the service to apply the new firewall rules.
    ```bash
    sudo systemctl restart wg-quick@wg0
    ```

2.  **On your Pwnagotchi**, restart the service to load the new plugin and configuration.
    ```bash
    sudo systemctl restart pwnagotchi
    ```

3.  **Verify:**
    * Watch the Pwnagotchi's screen. You should see the `WG:` status change from `Conn...` to `Up`. After a sync, it will briefly show `Sync: X`.
    * From another machine on your VPN or home LAN, you should be able to access the Pwnagotchi via its VPN IP.
    * Check your server. A new folder should be created inside your `handshake_dir`.

---

### Troubleshooting

* **`Permission denied (publickey)` in logs:** The SSH key setup is incorrect. Ensure you generated the key using `sudo` (for root) or copied your `pi` keys to `/root/.ssh/`.
* **`Connection timed out`:** A network or firewall issue. Verify both devices are connected to the VPN (`sudo wg show`). Check the server firewall rules from Step 6.
* **`Sync Failed` on screen:** Usually a permission issue on the server. Make sure the `server_user` has permission to write to the `handshake_dir`.
