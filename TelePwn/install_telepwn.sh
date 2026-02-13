#!/bin/bash

# TelePwn v2.0 Installation Script
# Python 3.13 Compatible
# Author: WPA2

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
PLUGIN_DIR="/usr/local/share/pwnagotchi/custom-plugins"
CONFIG_FILE="/etc/pwnagotchi/config.toml"
PLUGIN_URL="https://gitea.wpa3lab.homes/wpa2/Pwnagotchi-Plugins/raw/branch/Testing/TelePwn/telepwn.py"  # Update this URL

print_banner() {
    echo -e "${CYAN}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "   TelePwn v2.0 Installation"
    echo "   Python 3.13 Compatible"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${NC}"
}

print_success() { echo -e "${GREEN}[✓] $1${NC}"; }
print_error() { echo -e "${RED}[✗] $1${NC}"; }
print_info() { echo -e "${BLUE}[i] $1${NC}"; }
print_step() { echo -e "${CYAN}➜ $1${NC}"; }

check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "Run as root: sudo bash install.sh"
        exit 1
    fi
}

install_dependencies() {
    print_step "Installing dependencies..."
    
    pip3 install python-telegram-bot pytz --upgrade --break-system-packages 2>&1 | grep -v "WARNING" || true
    pip3 install requests psutil schedule toml --break-system-packages 2>&1 | grep -v "WARNING" || true
    
    print_success "Dependencies installed (python-telegram-bot v20 + pytz)"
}

install_plugin() {
    print_step "Installing TelePwn plugin..."
    
    mkdir -p "$PLUGIN_DIR"
    
    # Backup existing
    if [ -f "$PLUGIN_DIR/telepwn.py" ]; then
        cp "$PLUGIN_DIR/telepwn.py" "$PLUGIN_DIR/telepwn.py.backup.$(date +%Y%m%d_%H%M%S)"
        print_info "Backed up existing plugin"
    fi
    
    # Try downloading first
    if wget -q "$PLUGIN_URL" -O "$PLUGIN_DIR/telepwn.py" 2>/dev/null; then
        print_success "Plugin downloaded from repository"
    # Fallback to local file
    elif [ -f "telepwn_v20.py" ]; then
        cp telepwn_v20.py "$PLUGIN_DIR/telepwn.py"
        print_success "Plugin installed from local file"
    elif [ -f "telepwn.py" ]; then
        cp telepwn.py "$PLUGIN_DIR/telepwn.py"
        print_success "Plugin installed from local file"
    else
        print_error "Could not download plugin and no local file found"
        echo ""
        echo "Options:"
        echo "1. Update PLUGIN_URL in this script to your repository"
        echo "2. Run from same directory as telepwn.py or telepwn_v20.py"
        echo ""
        exit 1
    fi
    
    chmod 644 "$PLUGIN_DIR/telepwn.py"
}

get_bot_token() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Step 1: Telegram Bot Token${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Create bot: Message @BotFather → /newbot"
    echo ""
    
    while true; do
        read -p "Enter bot token: " BOT_TOKEN
        
        if [ -z "$BOT_TOKEN" ]; then
            print_error "Token required!"
            continue
        fi
        
        if [[ ! "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]]; then
            print_error "Invalid format! Should be: 1234567890:ABCdef..."
            continue
        fi
        
        break
    done
    
    print_success "Token saved"
}

get_chat_id() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Step 2: Your Chat ID${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Get ID: Message @userinfobot in Telegram"
    echo ""
    
    while true; do
        read -p "Enter chat ID: " CHAT_ID
        
        if [ -z "$CHAT_ID" ]; then
            print_error "Chat ID required!"
            continue
        fi
        
        if [[ ! "$CHAT_ID" =~ ^-?[0-9]+$ ]]; then
            print_error "Invalid format! Should be a number"
            continue
        fi
        
        break
    done
    
    print_success "Chat ID saved"
}

ask_community() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Step 3: Community Features (Optional)${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Join the UK Pwnagotchi community!"
    echo ""
    echo "Features:"
    echo "  • Share screenshots"
    echo "  • Celebrate milestones (100, 500, 1K, 5K, 10K)"
    echo "  • Connect with other Pwnagotchi users"
    echo ""
    echo "Privacy: Opt-in only, you control what gets shared"
    echo ""
    
    read -p "Enable community features? (y/n): " ENABLE_COMMUNITY
    
    if [[ "$ENABLE_COMMUNITY" =~ ^[Yy]$ ]]; then
        COMMUNITY_ENABLED="true"
        COMMUNITY_CHAT_ID="@Pwnagotchi_UK_Chat"
        print_success "Community enabled!"
        SHOW_COMMUNITY_STEPS=true
    else
        COMMUNITY_ENABLED="false"
        COMMUNITY_CHAT_ID=""
        print_info "Community disabled (private mode)"
        SHOW_COMMUNITY_STEPS=false
    fi
}

update_config() {
    print_step "Updating configuration..."
    
    if [ ! -f "$CONFIG_FILE" ]; then
        print_error "Config not found: $CONFIG_FILE"
        exit 1
    fi
    
    # Backup
    cp "$CONFIG_FILE" "${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    print_info "Config backed up"
    
    # Update using Python
    python3 << EOF
import toml

with open('$CONFIG_FILE', 'r') as f:
    config = toml.load(f)

# Ensure structure
if 'main' not in config:
    config['main'] = {}
if 'plugins' not in config['main']:
    config['main']['plugins'] = {}

# TelePwn v2.0 config
telepwn_config = {
    'enabled': True,
    'bot_token': '$BOT_TOKEN',
    'chat_id': '$CHAT_ID',
    'send_message': True,
    'send_handshake_file': True,  # v2.0: Auto-send .pcap files
    'auto_start': True,
    'community_enabled': $COMMUNITY_ENABLED
}

# Add community_chat_id only if enabled
if $COMMUNITY_ENABLED:
    telepwn_config['community_chat_id'] = '$COMMUNITY_CHAT_ID'

config['main']['plugins']['telepwn'] = telepwn_config

with open('$CONFIG_FILE', 'w') as f:
    toml.dump(config, f)
EOF
    
    print_success "Configuration updated"
}

show_community_steps() {
    if [ "$SHOW_COMMUNITY_STEPS" = true ]; then
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}Community Setup${NC}"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo "1. Join: https://t.me/Pwnagotchi_UK_Chat"
        echo ""
        echo "2. Add your bot to the group:"
        echo "   • Open the group"
        echo "   • Click group name → Add Members"
        echo "   • Search for your bot"
        echo "   • Add it"
        echo ""
        echo "3. Test: Send /screenshot to your bot"
        echo "   • Click 'Share to Community'"
        echo "   • Screenshot appears in group!"
        echo ""
        
        read -p "Press Enter when bot is added to group..."
    fi
}

restart_service() {
    print_step "Restarting Pwnagotchi..."
    systemctl restart pwnagotchi
    sleep 2
    print_success "Service restarted"
}

show_completion() {
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✓ TelePwn v2.0 Installed!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${CYAN}Quick Start:${NC}"
    echo "1. Open Telegram, find your bot"
    echo "2. Send: /start"
    echo "3. Try: /screenshot or /uptime"
    echo ""
    
    echo -e "${CYAN}What's New in v2.0:${NC}"
    echo "✓ Python 3.13 compatible"
    echo "✓ Handshake .pcap files auto-sent to Telegram"
    echo "✓ All commands have back buttons"
    echo "✓ Better error handling"
    echo ""
    
    if [ "$SHOW_COMMUNITY_STEPS" = true ]; then
        echo -e "${CYAN}Community:${NC}"
        echo "https://t.me/Pwnagotchi_UK_Chat"
        echo ""
    fi
    
    echo -e "${CYAN}Check Logs:${NC}"
    echo "sudo tail -f /var/log/pwnagotchi.log | grep TelePwn"
    echo ""
    echo -e "${GREEN}Happy Pwning!${NC}"
    echo ""
}

# Main
main() {
    print_banner
    
    check_root
    install_dependencies
    install_plugin
    
    get_bot_token
    get_chat_id
    ask_community
    
    update_config
    show_community_steps
    restart_service
    show_completion
}

trap 'print_error "Installation failed!"; exit 1' ERR

main
