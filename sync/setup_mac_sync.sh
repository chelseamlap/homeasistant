#!/bin/bash
#
# Sets up the Apple Reminders → Pi sync on your Mac.
#
# What it does:
#   1. Creates sync/sync_config.json with your Pi connection info
#   2. Installs a launchd job that syncs every 5 minutes
#   3. Runs the first sync immediately
#
# Usage:
#   cd /path/to/home-launchpad
#   bash sync/setup_mac_sync.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SYNC_SCRIPT="$SCRIPT_DIR/reminders_sync.py"
CONFIG_FILE="$SCRIPT_DIR/sync_config.json"
PLIST_SRC="$SCRIPT_DIR/com.home-launchpad.reminders-sync.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.home-launchpad.reminders-sync.plist"

echo "=== Home Launchpad: Mac → Pi Reminders Sync Setup ==="
echo ""

# Step 1: Configure Pi connection
if [ -f "$CONFIG_FILE" ]; then
    echo "Found existing config: $CONFIG_FILE"
    cat "$CONFIG_FILE"
    echo ""
    read -p "Reconfigure? (y/n): " RECONFIG
    if [[ "$RECONFIG" != "y" ]]; then
        echo "Keeping existing config."
    else
        rm "$CONFIG_FILE"
    fi
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Enter your Pi connection details:"
    read -p "  Pi username (e.g. pi): " PI_USER
    read -p "  Pi IP or hostname (e.g. 192.168.1.100): " PI_HOST
    read -p "  Dashboard path on Pi (default: /home/$PI_USER/git-repo/home-launchpad): " PI_PATH
    PI_PATH="${PI_PATH:-/home/$PI_USER/git-repo/home-launchpad}"

    cat > "$CONFIG_FILE" << EOF
{
  "pi_host": "$PI_USER@$PI_HOST",
  "pi_dashboard_path": "$PI_PATH"
}
EOF
    echo "Saved config to $CONFIG_FILE"
fi

# Step 2: Test SSH connection
echo ""
echo "Testing SSH connection..."
PI_HOST=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['pi_host'])")
if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new "$PI_HOST" "echo 'SSH OK'" 2>/dev/null; then
    echo "SSH connection works!"
else
    echo "WARNING: SSH connection failed. Make sure you have SSH keys set up:"
    echo "  ssh-keygen -t ed25519  (if you don't have a key)"
    echo "  ssh-copy-id $PI_HOST"
    echo ""
    echo "Continuing setup anyway — fix SSH before the sync will work."
fi

# Step 3: Install launchd job
echo ""
echo "Installing launchd sync job (runs every 5 minutes)..."

# Unload existing job if present
launchctl unload "$PLIST_DST" 2>/dev/null || true

# Create the plist with the correct path
sed "s|SYNC_SCRIPT_PATH|$SYNC_SCRIPT|g" "$PLIST_SRC" > "$PLIST_DST"

launchctl load "$PLIST_DST"
echo "Installed and started: $PLIST_DST"

# Step 4: Run first sync
echo ""
echo "Running first sync..."
python3 "$SYNC_SCRIPT"

echo ""
echo "=== Setup complete ==="
echo ""
echo "The sync runs every 5 minutes automatically."
echo "  Logs: /tmp/home-launchpad-sync.log"
echo "  Config: $CONFIG_FILE"
echo "  To stop: launchctl unload $PLIST_DST"
echo "  To restart: launchctl unload $PLIST_DST && launchctl load $PLIST_DST"
echo ""
echo "IMPORTANT: If you switch to a new Mac, just clone the repo and re-run this script."
