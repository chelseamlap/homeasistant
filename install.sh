#!/bin/bash
# ============================================================
# Family Dashboard — Raspberry Pi Install Script
# Run: chmod +x install.sh && ./install.sh
# ============================================================
set -e

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║     Family Home Dashboard — Pi Setup             ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# --- Check architecture ---
ARCH=$(uname -m)
if [[ "$ARCH" == "armv7l" ]]; then
    echo "⚠  You're running 32-bit OS ($ARCH)."
    echo "   This works but 64-bit Raspberry Pi OS is recommended."
    echo ""
fi

# --- Install system deps ---
echo "→ Installing system dependencies..."
sudo apt update -qq
# chromium-browser was renamed to chromium in newer Pi OS
if apt-cache policy chromium-browser 2>/dev/null | grep -q "Candidate: (none)"; then
    CHROMIUM_PKG="chromium"
elif apt-cache policy chromium-browser 2>/dev/null | grep -q "Candidate:"; then
    CHROMIUM_PKG="chromium-browser"
else
    CHROMIUM_PKG="chromium"
fi
echo "  Using package: $CHROMIUM_PKG"
sudo apt install -y -qq python3 python3-pip $CHROMIUM_PKG git

# --- Install Python packages ---
echo "→ Installing Python packages..."
pip install -r requirements.txt --break-system-packages --quiet

# --- Create data directory ---
mkdir -p data

# --- Prompt for location ---
echo ""
echo "─── Location Setup (for weather) ───"
echo "  You can set this later from the Home tab if you don't know your coordinates."
echo "  Find them at https://www.latlong.net/"
echo ""
read -p "City name (e.g. Portland, OR) [skip]: " CITY
read -p "Latitude (e.g. 45.5152) [skip]: " LAT
read -p "Longitude (e.g. -122.6784) [skip]: " LON

# Default to 0 if left blank so JSON stays valid
CITY="${CITY:-}"
LAT="${LAT:-0}"
LON="${LON:-0}"

cat > data/settings.json << EOF
{
  "location_name": "$CITY",
  "latitude": $LAT,
  "longitude": $LON,
  "budget_sheet_id": ""
}
EOF
echo "✓ Location saved"

# --- Google OAuth ---
echo ""
echo "─── Google Calendar & Sheets Setup ───"
echo ""
if [ -f "client_secret.json" ]; then
    echo "✓ client_secret.json found"
    echo "→ Running OAuth setup (this will open a browser)..."
    python3 setup_google_oauth.py
else
    echo "⚠  No client_secret.json found — skipping Google setup."
    echo "   Calendar and Sheets won't work until you:"
    echo "   1. Create a Google Cloud project"
    echo "   2. Enable Calendar API + Sheets API"
    echo "   3. Download OAuth credentials as client_secret.json"
    echo "   4. Place it in this folder and run: python3 setup_google_oauth.py"
    echo ""
fi

# --- iCloud / Reminders ---
echo ""
echo "─── Apple Reminders ───"
echo ""
echo "The dashboard uses local JSON files by default."
echo "For iCloud sync, create data/icloud_creds.json with your Apple ID"
echo "and an app-specific password. See README.md for details."

# --- Seed sample chores ---
if [ ! -f "data/reminders_daily_chores.json" ]; then
    echo ""
    read -p "Add some sample daily chores? (y/n): " ADD_SAMPLES
    if [[ "$ADD_SAMPLES" == "y" ]]; then
        cat > data/reminders_daily_chores.json << 'EOF'
[
  {"id": "sample_1", "title": "Unload dishwasher", "completed": false, "completed_date": null, "created": "2026-01-01T00:00:00"},
  {"id": "sample_2", "title": "Wipe kitchen counters", "completed": false, "completed_date": null, "created": "2026-01-01T00:00:00"},
  {"id": "sample_3", "title": "Pick up toys", "completed": false, "completed_date": null, "created": "2026-01-01T00:00:00"},
  {"id": "sample_4", "title": "Sort mail", "completed": false, "completed_date": null, "created": "2026-01-01T00:00:00"}
]
EOF
        echo "✓ Sample daily chores added (edit from the touchscreen)"
    fi
fi

# --- Systemd service ---
echo ""
read -p "Install as a system service (auto-start on boot)? (y/n): " INSTALL_SERVICE
if [[ "$INSTALL_SERVICE" == "y" ]]; then
    DASHBOARD_DIR=$(pwd)
    sudo tee /etc/systemd/system/home-launchpad.service > /dev/null << EOF
[Unit]
Description=The Home Launchpad
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$DASHBOARD_DIR
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=5
Environment=DASHBOARD_PORT=5000

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable home-launchpad
    sudo systemctl start home-launchpad
    echo "✓ Service installed and started"
else
    echo "→ To start manually: python3 app.py"
fi

# --- Chrome autostart ---
echo ""
read -p "Auto-launch Chrome on boot? (y/n): " AUTO_CHROME
if [[ "$AUTO_CHROME" == "y" ]]; then
    # Detect correct chromium binary name
    if command -v chromium-browser &>/dev/null; then
        CHROMIUM_BIN="chromium-browser"
    else
        CHROMIUM_BIN="chromium"
    fi
    CHROME_CMD="$CHROMIUM_BIN --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --disable-restore-session-state --password-store=basic --app=http://localhost:5000"
    # Wait-for-port script: waits up to 30s for the dashboard to be ready
    WAIT_CMD="for i in \$(seq 1 30); do curl -s http://localhost:5000 >/dev/null 2>&1 && break; sleep 1; done"
    # Guard: skip launch if the user exited kiosk mode (flag clears on reboot)
    GUARD_CMD="[ ! -f /tmp/home-launchpad-kiosk-paused ]"

    # Clean up any old autostart entries to prevent multiple launches
    echo "→ Cleaning up old autostart entries..."
    rm -f "$HOME/.config/autostart/home-launchpad.desktop" 2>/dev/null
    rm -f "$HOME/.config/autostart/family-dashboard.desktop" 2>/dev/null
    LXDE_DIR="$HOME/.config/lxsession/LXDE-pi"
    if [ -f "$LXDE_DIR/autostart" ]; then
        sed -i '/home-launchpad/d' "$LXDE_DIR/autostart" 2>/dev/null
        sed -i '/family-dashboard/d' "$LXDE_DIR/autostart" 2>/dev/null
    fi
    WAYFIRE_INI="$HOME/.config/wayfire.ini"
    if [ -f "$WAYFIRE_INI" ]; then
        sed -i '/home-launchpad/d' "$WAYFIRE_INI" 2>/dev/null
        sed -i '/family-dashboard/d' "$WAYFIRE_INI" 2>/dev/null
    fi

    # Detect which desktop environment is active and use ONLY that one
    if [ -f "$WAYFIRE_INI" ] && pgrep -x wayfire &>/dev/null; then
        # Wayfire (Raspberry Pi OS Bookworm+ default)
        if grep -q "\[autostart\]" "$WAYFIRE_INI"; then
            sed -i "/\[autostart\]/a home-launchpad = bash -c '$GUARD_CMD && $WAIT_CMD && $CHROME_CMD'" "$WAYFIRE_INI"
        else
            echo -e "\n[autostart]\nhome-launchpad = bash -c '$GUARD_CMD && $WAIT_CMD && $CHROME_CMD'" >> "$WAYFIRE_INI"
        fi
        echo "✓ Wayfire autostart configured (Bookworm+)"
    elif [ -d "$LXDE_DIR" ]; then
        # LXDE (older Pi OS)
        echo "@bash -c '$GUARD_CMD && $WAIT_CMD && $CHROME_CMD'" >> "$LXDE_DIR/autostart"
        echo "✓ LXDE autostart configured"
    else
        # Fallback: XDG autostart
        XDG_DIR="$HOME/.config/autostart"
        mkdir -p "$XDG_DIR"
        cat > "$XDG_DIR/home-launchpad.desktop" << EOF
[Desktop Entry]
Type=Application
Name=The Home Launchpad
Comment=Launch dashboard in Chrome kiosk mode
Exec=bash -c '$GUARD_CMD && $WAIT_CMD && $CHROME_CMD'
X-GNOME-Autostart-enabled=true
EOF
        echo "✓ XDG autostart configured"
    fi

    echo "→ Chrome will open in full-screen kiosk mode once the server is ready"
    echo "  (Press Alt+F4 to exit kiosk mode if needed)"
fi

# --- Done ---
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✓ Setup complete!                               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Dashboard: http://localhost:5000"
echo ""
echo "  To open now:"
echo "  chromium --start-maximized --app=http://localhost:5000"
echo ""
echo "  Next steps:"
echo "  • Create these lists in Apple Reminders on your phone:"
echo "    Daily Chores, Weekly Chores, Things to Talk About,"
echo "    Home Projects, Vacation Planning"
echo "  • Set up Google Sheet for budget (see README.md)"
echo "  • Configure location & Sheet ID in Home → Settings"
echo ""
