# WireGuard Plugin v2.2
Auto-connect your Pwnagotchi to a WireGuard VPN and sync handshakes home.

## Features
- Auto-connects on boot with retry logic
- Syncs only NEW handshakes (checkpoint system - fast!)
- Connection health monitoring
- **Web UI statistics dashboard** (NEW in v2.2!)
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
sudo wget -O /usr/local/share/pwnagotchi/custom-plugins/wireguard.py https://raw.githubusercontent.com/wpa-2/Pwnagotchi-Plugins/main/wireguard.py
```

Setup SSH keys:
```bash
# Generate key
sudo ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""

# Copy to server (use your server's LOCAL IP, not VPN IP!)
sudo ssh-copy-id -i /root/.ssh/id_ed25519.pub pi@192.168.1.50
```

**Note:** If your server uses a custom SSH port (e.g., 2222), add `-p 2222` to the ssh-copy-id command.

---

### 3. Configuration

Edit `/etc/pwnagotchi/config.toml`:

```toml
[main.plugins.wireguard]
enabled = true
wg_config_path = "/tmp/wg0.conf"

# Keys (from your PiVPN client config)
private_key = "YOUR_CLIENT_PRIVATE_KEY"
peer_public_key = "YOUR_SERVER_PUBLIC_KEY"
preshared_key = "YOUR_PRESHARED_KEY"  # Optional - remove line if not in your config

# Network Settings
address = "10.16.244.2/24"  # From client config - each device needs unique IP
dns = ["9.9.9.9", "149.112.112.112"]  # Can be single string or array
peer_endpoint = "your-domain.duckdns.org:51820"  # Or use public IP

# Handshake Sync Settings
server_user = "pi"
server_port = 22  # SSH port on your server (use 2222 if you changed it)
server_vpn_ip = "10.16.244.1"  # Server's VPN IP (usually .1) - auto-detected if not specified
handshake_dir = "/home/pi/pwnagotchi_handshakes/"  # Destination on server
sync_interval = 600  # Sync every 10 minutes

# Startup & Connection
startup_delay_secs = 60  # Wait before connecting (helps with boot stability)
max_retries = 5
connection_timeout = 10

# Performance & Health
bwlimit = 0  # Bandwidth limit (KB/s) - 0 = unlimited, 500 = good for cellular
compress_level = 6  # Compression level (0-9, higher = more CPU, smaller transfers)
persistent_keepalive = 25  # Keep connection alive through NAT
health_check_enabled = true  # Periodic connection health checks
```

**Configuration Notes:**
- **Required:** `private_key`, `address`, `peer_public_key`, `peer_endpoint`, `handshake_dir`, `server_user`
- **Optional:** All others have sensible defaults
- **DNS:** Can be single string `"9.9.9.9"` or array `["9.9.9.9", "149.112.112.112"]`
- **server_vpn_ip:** Auto-detected from your `address` if not specified (assumes server is .1)

Restart:
```bash
sudo systemctl restart pwnagotchi
```

---

## Web UI Statistics

Access detailed statistics at:
```
http://YOUR_PWNAGOTCHI_IP:8080/plugins/wireguard
```

Or click "wireguard" from the main plugins page at `http://YOUR_PWNAGOTCHI_IP:8080/plugins`

**Stats displayed:**
- Today's synced handshakes (resets at midnight)
- Total synced this session
- Connection status and health
- VPN IP and connection uptime
- WireGuard interface stats (last handshake, transfer data)
- Sync information (last sync time, next sync countdown)
- Connection statistics (attempts, failures, success rate)
- Server configuration

**Note:** Page auto-refreshes every 30 seconds to keep stats current.

---

## Screen Status

- `WG: Init` - Starting
- `WG: Wait:Xs` - Boot delay countdown
- `WG: Conn...` - Connecting
- `WG: Retry:X` - Connection retry
- `WG: Up` - Connected ✓
- `WG: Sync:X` - Syncing X files
- `WG: Err` - Connection error
- `WG: Failed` - Max retries exceeded

---

## Troubleshooting

**"KeyErr" on screen:**
```bash
sudo ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""
sudo ssh-copy-id -i /root/.ssh/id_ed25519.pub pi@YOUR_SERVER_LOCAL_IP

# If using custom SSH port:
sudo ssh-copy-id -p 2222 -i /root/.ssh/id_ed25519.pub pi@YOUR_SERVER_LOCAL_IP
```

**Connection retries then succeeds:**  
Normal. DNS resolution can be flaky at boot. If it bothers you, use IP address instead of hostname in `peer_endpoint`.

**Health check failures:**
Check the web UI for detailed health status. If you see "Degraded (X/3 failures)", the plugin will auto-reconnect after 3 consecutive failures.

**View logs:**
```bash
# Follow live logs
tail -f /etc/pwnagotchi/log/pwnagotchi.log | grep WireGuard

# Or use journalctl if systemd logging is enabled
sudo journalctl -u pwnagotchi -f | grep WireGuard
```

**Test manually:**
```bash
# Check WireGuard interface
sudo wg show

# Test connectivity to server
ping -c 4 10.16.244.1  # Your server's VPN IP

# Manual sync test (as root)
sudo rsync -avz -e "ssh -p 2222 -i /root/.ssh/id_ed25519" /home/pi/handshakes/ wpa2@10.16.244.1:/home/wpa2/pwntest_handshakes/
```

**Custom SSH port not working:**
Make sure you set `server_port = 2222` in your config and verified SSH key works:
```bash
sudo ssh -p 2222 -i /root/.ssh/id_ed25519 pi@10.16.244.1
```

---

## Multiple Pwnagotchis

Each device needs:
- Unique `address` (10.16.244.2, 10.16.244.3, etc.)
- Unique `private_key` (create separate PiVPN client profiles)
- Unique `handshake_dir` on server to keep handshakes separate

**Example for second device:**
```bash
# On server, create second profile
pivpn add  # Name: pwnagotchi-02

# Create separate directory
mkdir -p /home/pi/pwnagotchi02_handshakes/
```

Then use different values in second Pwnagotchi's config.

---

## What's New

**v2.2:** Added web UI statistics dashboard with daily counters, WireGuard interface stats, and auto-refresh  
**v2.1:** Fixed blocking issue - now works in auto mode  
**v2.0:** Added connection verification, auto-retry, health monitoring, file filtering, bandwidth limiting

---

## License
GPL3 | Author: WPA2
