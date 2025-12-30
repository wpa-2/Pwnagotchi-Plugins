# WireGuard Plugin v2.1

Auto-connect your Pwnagotchi to a WireGuard VPN and sync handshakes home.

## Features

- Auto-connects on boot with retry logic
- Syncs only NEW handshakes (checkpoint system - fast!)
- Connection health monitoring
- Remote SSH access from anywhere
- Works in auto and manual mode

---

## Installation

### 1. Server Setup (Do This First!)

Install PiVPN on your home Raspberry Pi:

```bash
curl -L https://install.pivpn.io | bash
# Choose WireGuard during setup
```

Create a client profile:

```bash
pivpn add
# Name it: pwnagotchi-01

# View the config and save these values:
cat ~/configs/pwnagotchi-01.conf
```

You'll need: `PrivateKey`, `Address`, `PublicKey`, `PresharedKey` (if present), and `Endpoint`

Create handshake directory:

```bash
mkdir -p /home/pi/handshakes/
```

---

### 2. Pwnagotchi Setup

SSH into your Pwnagotchi and install dependencies:

```bash
sudo apt-get update
sudo apt-get install rsync wireguard wireguard-tools openresolv -y
```

Install the plugin:

```bash
sudo mkdir -p /usr/local/share/pwnagotchi/custom-plugins/
sudo mv wireguard.py /usr/local/share/pwnagotchi/custom-plugins/
```

Setup SSH keys:

```bash
# Generate key
sudo ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""

# Copy to server (use your server's LOCAL IP, not VPN IP!)
sudo ssh-copy-id -i /root/.ssh/id_ed25519.pub pi@192.168.1.50
```

---

### 3. Configuration

Edit `/etc/pwnagotchi/config.toml`:

```toml
# Enable plugin
main.plugins.wireguard.enabled = true
main.plugins.wireguard.wg_config_path = "/tmp/wg0.conf"

# Keys from your .conf file
main.plugins.wireguard.private_key = "YOUR_CLIENT_PRIVATE_KEY"
main.plugins.wireguard.peer_public_key = "YOUR_SERVER_PUBLIC_KEY"
main.plugins.wireguard.preshared_key = "YOUR_PRESHARED_KEY"  # Optional

# Network (must be unique per device!)
main.plugins.wireguard.address = "10.0.0.5/24"
main.plugins.wireguard.dns = "9.9.9.9"
main.plugins.wireguard.peer_endpoint = "your-home-ip:51820"

# Sync settings
main.plugins.wireguard.server_user = "pi"
main.plugins.wireguard.server_port = 22
main.plugins.wireguard.handshake_dir = "/home/pi/handshakes/"

# Optional
main.plugins.wireguard.startup_delay_secs = 60
main.plugins.wireguard.sync_interval = 600
```

Restart:

```bash
sudo systemctl restart pwnagotchi
```

---

## Screen Status

- `WG: Init` - Starting
- `WG: Wait:Xs` - Boot delay countdown
- `WG: Conn...` - Connecting
- `WG: Retry:X` - Connection retry
- `WG: Up` - Connected ✓
- `WG: Sync:X` - Syncing X files

---

## Troubleshooting

**"KeyErr" on screen:**
```bash
sudo ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""
sudo ssh-copy-id -i /root/.ssh/id_ed25519.pub pi@YOUR_SERVER_LOCAL_IP
```

**Connection retries then succeeds:**  
Normal. DNS resolution can be flaky at boot. If it bothers you, use IP address instead of hostname in `peer_endpoint`.

**View logs:**
```bash
tail -f /var/log/pwnagotchi.log | grep WireGuard
```

**Test manually:**
```bash
sudo wg-quick up /tmp/wg0.conf
sudo wg show
ping YOUR_SERVER_VPN_IP
```

---

## Multiple Pwnagotchis

Each device needs:
- Unique `address` (10.0.0.5, 10.0.0.6, etc.)
- Unique `private_key` (create separate client profiles)

---

## Optional Settings

```toml
# Bandwidth limit (KB/s) - good for cellular
main.plugins.wireguard.bwlimit = 500

# Compression level (0-9)
main.plugins.wireguard.compress_level = 6

# Max retries
main.plugins.wireguard.max_retries = 5

# Health checks
main.plugins.wireguard.health_check_enabled = true
```

---

## What's New

**v2.1:** Fixed blocking issue - now works in auto mode  
**v2.0:** Added connection verification, auto-retry, health monitoring, file filtering, bandwidth limiting

---

## License

GPL3 | Author: WPA2
