#!/bin/bash

# Exit on error
set -e

CONFIG_FILE="/etc/pwnagotchi/config.toml"
PLUGIN_DIR="/usr/local/share/pwnagotchi/custom-plugins"
REMOTE_URL="https://raw.githubusercontent.com/wpa-2/TelePwn/refs/heads/main/telepwn.py"

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

if ! grep -q "main.plugins.telepwn" "$CONFIG_FILE"; then
    cat >> "$CONFIG_FILE" <<EOF

[main.plugins.telepwn]
enabled = true
bot_token = "$BOT_TOKEN"
chat_id = "$CHAT_ID"
send_message = true
auto_start = true
EOF
else
    sed -i "/main.plugins.telepwn.enabled/c\main.plugins.telepwn.enabled = true" "$CONFIG_FILE"
    sed -i "/main.plugins.telepwn.bot_token/c\main.plugins.telepwn.bot_token = \"$BOT_TOKEN\"" "$CONFIG_FILE"
    sed -i "/main.plugins.telepwn.chat_id/c\main.plugins.telepwn.chat_id = \"$CHAT_ID\"" "$CONFIG_FILE"
    sed -i "/main.plugins.telepwn.send_message/c\main.plugins.telepwn.send_message = true" "$CONFIG_FILE"
    sed -i "/main.plugins.telepwn.auto_start/c\main.plugins.telepwn.auto_start = true" "$CONFIG_FILE"
fi

echo "[ + ] Remounting filesystem as read-only..."
mount -o remount,ro / || echo "[ - ] Warning: Could not remount RO."

echo "[ + ] Restarting Pwnagotchi..."
systemctl restart pwnagotchi

echo "[ * ] Installation complete!"
