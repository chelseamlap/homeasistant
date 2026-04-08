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
sudo apt install -y -qq python3 python3-pip chromium-browser git

# --- Install Python packages ---
echo "→ Installing Python packages..."
pip install -r requirements.txt --break-system-packages --quiet

# --- Create data directory ---
mkdir -p data

# --- Prompt for location ---
echo ""
echo "─── Location Setup (for weather) ───"
echo ""
read -p "City name (e.g. Portland, OR): " CITY
read -p "Latitude (e.g. 45.5152): " LAT
read -p "Longitude (e.g. -122.6784): " LON

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
echo "The dashboard uses local JSON files by default (works great)."
echo "Manage lists directly from the touchscreen."
echo ""
echo "For iCloud sync (optional), run separately:"
echo "  python3 -c \"from pyicloud import PyiCloudService; ...\""
echo "See README.md for full instructions."

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
    sudo tee /etc/systemd/system/family-dashboard.service > /dev/null << EOF
[Unit]
Description=Family Home Dashboard
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
    sudo systemctl enable family-dashboard
    sudo systemctl start family-dashboard
    echo "✓ Service installed and started"
else
    echo "→ To start manually: python3 app.py"
fi

# --- Chrome autostart ---
echo ""
read -p "Auto-launch Chrome on boot? (y/n): " AUTO_CHROME
if [[ "$AUTO_CHROME" == "y" ]]; then
    AUTOSTART_DIR="$HOME/.config/lxsession/LXDE-pi"
    mkdir -p "$AUTOSTART_DIR"
    # Append if not already there
    if ! grep -q "family-dashboard" "$AUTOSTART_DIR/autostart" 2>/dev/null; then
        echo "@chromium-browser --start-maximized --app=http://localhost:5000" >> "$AUTOSTART_DIR/autostart"
        echo "✓ Chrome will auto-launch on boot"
    else
        echo "✓ Chrome autostart already configured"
    fi
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
echo "  chromium-browser --start-maximized --app=http://localhost:5000"
echo ""
echo "  Next steps:"
echo "  • Create these lists in Apple Reminders on your phone:"
echo "    Daily Chores, Weekly Chores, Things to Talk About,"
echo "    Home Projects, Vacation Planning"
echo "  • Set up Google Sheet for budget (see README.md)"
echo "  • Configure location & Sheet ID in Home → Settings"
echo ""
