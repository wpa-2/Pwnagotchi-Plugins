#!/bin/bash

# Exit on error
set -e

CONFIG_FILE="/etc/pwnagotchi/config.toml"
PLUGIN_DIR="/usr/local/share/pwnagotchi/custom-plugins"
REMOTE_URL="https://raw.githubusercontent.com/wpa-2/Pwnagotchi-Plugins/main/TelePwn/telepwn.py"

echo "[ + ] Checking internet connection..."
if ! wget -q --spider http://google.com; then
    echo "[ - ] No internet connection. Please connect and retry."
    exit 1
fi

echo "[ + ] Checking filesystem status..."
if mount | grep " on / type " | grep "ro," >/dev/null; then
    echo "[ + ] Filesystem is read-only. Remounting as read-write..."
    mount -o remount,rw /
    if [ $? -ne 0 ]; then
        echo "[ - ] Failed to remount filesystem as read-write. Please remount manually and try again."
        exit 1
    fi
else
    echo "[ + ] Filesystem is already read-write."
fi

echo "[ + ] Ensuring pip3 is installed..."
if ! command -v pip3 &> /dev/null; then
    echo "[ + ] pip3 not found. Installing python3-pip..."
    echo "[ - ] Warning: Cannot update package lists due to read-only filesystem constraints."
    echo "[ - ] Please ensure python3-pip is installed in your Pwnagotchi image."
    exit 1
fi

echo "[ + ] Installing Python dependencies..."
# Using --break-system-packages for newer Debian/Raspbian versions
pip3 install python-telegram-bot==13.15 requests>=2.28.0 psutil>=5.9.0 schedule>=1.2.0 --break-system-packages || true

echo "[ + ] Creating plugin directory..."
mkdir -p "$PLUGIN_DIR"

PLUGIN_PATH="$PLUGIN_DIR/telepwn.py"
echo "[ + ] Downloading TelePwn plugin..."
wget -O "$PLUGIN_PATH" "$REMOTE_URL"
if [ $? -ne 0 ]; then
    echo "[ - ] Failed to download telepwn.py."
    exit 1
fi
chmod +x "$PLUGIN_PATH"

echo "[ + ] Creating telepwn_webhooks.toml and telepwn_schedules.toml..."
touch /etc/pwnagotchi/telepwn_webhooks.toml
chmod 644 /etc/pwnagotchi/telepwn_webhooks.toml
touch /etc/pwnagotchi/telepwn_schedules.toml
chmod 644 /etc/pwnagotchi/telepwn_schedules.toml

echo "[ + ] Backing up config..."
cp "$CONFIG_FILE" "$CONFIG_FILE.bak"

echo "[ + ] Configuring TelePwn..."
echo "Enter your Telegram Bot Token:"
read -r BOT_TOKEN
echo "Enter your Telegram Chat ID:"
read -r CHAT_ID

if ! grep -q "main.custom_plugins" "$CONFIG_FILE"; then
    echo -e "\nmain.custom_plugins = \"$PLUGIN_DIR\"" >> "$CONFIG_FILE"
fi

# Check if [main.plugins.telepwn] section exists
if ! grep -q "\[main.plugins.telepwn\]" "$CONFIG_FILE"; then
    # Section doesn't exist, create it
    cat >> "$CONFIG_FILE" <<EOF

[main.plugins.telepwn]
enabled = true
bot_token = "$BOT_TOKEN"
chat_id = "$CHAT_ID"
send_message = true
auto_start = true
EOF
else
    # Section exists, update values using awk for proper TOML section handling
    # This approach preserves the section structure and updates only the values
    awk -v bot_token="$BOT_TOKEN" -v chat_id="$CHAT_ID" '
    BEGIN { in_telepwn = 0 }
    
    # Detect when we enter the [main.plugins.telepwn] section
    /^\[main\.plugins\.telepwn\]/ { in_telepwn = 1; print; next }
    
    # Detect when we enter a different section
    /^\[/ && !/^\[main\.plugins\.telepwn\]/ { in_telepwn = 0 }
    
    # Update values within the telepwn section
    in_telepwn && /^enabled\s*=/ { print "enabled = true"; next }
    in_telepwn && /^bot_token\s*=/ { print "bot_token = \"" bot_token "\""; next }
    in_telepwn && /^chat_id\s*=/ { print "chat_id = \"" chat_id "\""; next }
    in_telepwn && /^send_message\s*=/ { print "send_message = true"; next }
    in_telepwn && /^auto_start\s*=/ { print "auto_start = true"; next }
    
    # Print all other lines unchanged
    { print }
    ' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
fi

echo "[ + ] Remounting filesystem as read-only..."
mount -o remount,ro / || echo "[ - ] Warning: Could not remount RO."

echo "[ + ] Restarting Pwnagotchi..."
systemctl restart pwnagotchi

echo "[ * ] Installation complete!"
echo "[ * ] Send /start to your bot to begin!"