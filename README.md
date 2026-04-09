# The Home Launchpad

A touch-optimized family command center for a 24" Dell touchscreen on a Raspberry Pi 4. Five tabs: Today + This Week, Lists, Calendar, Home, Money.

## Architecture

- **Backend**: Python/Flask on the Pi, serves localhost
- **Frontend**: Single-page HTML/CSS/JS, dark mode, 1920x1080 landscape
- **Lists**: Apple Reminders via iCloud (pyicloud), with local JSON fallback
- **Calendar**: Google Calendar API via OAuth2
- **Budget**: Google Sheets API via OAuth2
- **Weather**: Open-Meteo (free, no API key)

---

## Setup on Raspberry Pi

### 1. Install Python & Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Ensure Python 3.9+ is installed
python3 --version

# Clone or copy the project
cd /home/pi
mkdir family-dashboard
# (copy all project files here)

# Install Python packages
cd /home/pi/family-dashboard
pip install -r requirements.txt --break-system-packages
```

### 2. Create Apple Reminders Lists

On your iPhone or Mac, open Reminders and create these 5 lists (exact names matter):

1. **Daily Chores**
2. **Weekly Chores**
3. **Things to Talk About**
4. **Home Projects**
5. **Vacation Planning**

Add your initial items to each list.

### 3. Set Up Apple Reminders iCloud Bridge

The dashboard uses `pyicloud` to access Apple Reminders via iCloud.

```bash
pip install pyicloud --break-system-packages
```

**First-time authentication:**

```bash
cd /home/pi/family-dashboard
python3 -c "
from pyicloud import PyiCloudService
api = PyiCloudService('YOUR_APPLE_ID@icloud.com', 'YOUR_PASSWORD')
if api.requires_2fa:
    code = input('Enter 2FA code sent to your device: ')
    api.validate_2fa_code(code)
    print('Authenticated!')
"
```

Your session is cached in `~/.pyicloud` — you won't need to re-authenticate unless the session expires.

**If pyicloud doesn't work on your Pi**, the dashboard falls back to local JSON files in the `data/` folder. You can manage everything from the touchscreen and it works perfectly — you just won't get automatic sync with your phones. This is the recommended starting point.

### 4. Set Up Google OAuth2

You need a Google Cloud project with Calendar API and Sheets API enabled.

```
1. Go to https://console.cloud.google.com/
2. Create a new project: "Family Dashboard"
3. Go to APIs & Services → Library
4. Enable: Google Calendar API
5. Enable: Google Sheets API
6. Go to APIs & Services → Credentials
7. Click "Create Credentials" → "OAuth client ID"
8. Application type: "Desktop app"
9. Download the JSON file
10. Rename it to client_secret.json
11. Place it in /home/pi/family-dashboard/
```

**Run the OAuth flow:**

```bash
cd /home/pi/family-dashboard
python3 setup_google_oauth.py
```

This opens a browser. Sign in with your family Google account and grant Calendar + Sheets read access. The token is stored locally in `data/google_token.json`.

### 5. Set Up the Google Sheet for Budget

Create a Google Sheet with two tabs:

**Tab 1: "Budget"**
| Category | Budget | Spent |
|---|---|---|
| Groceries | 800 | 523.45 |
| Dining | 400 | 287.00 |
| Home | 300 | 150.00 |
| Kids | 200 | 89.50 |
| Subscriptions | 150 | 149.99 |
| Misc | 200 | 45.00 |

**Tab 2: "Bills"**
| Bill Name | Amount | Due Date |
|---|---|---|
| Mortgage | 2400 | 2026-04-15 |
| Electric | 185 | 2026-04-10 |
| Internet | 75 | 2026-04-12 |

Copy the Sheet ID from the URL (the long string between `/d/` and `/edit`). You'll enter this in the dashboard's Home tab settings.

### 6. Configure Location

On first launch, go to the **Home** tab and enter:
- Your city name (for display)
- Latitude and longitude (for weather)
- The Google Sheet ID (for budget)

Find your coordinates at https://www.latlong.net/

### 7. Launch the Dashboard

```bash
cd /home/pi/family-dashboard
python3 app.py
```

The server starts on port 5000 by default.

### 8. Launch Chrome in Soft Kiosk Mode

```bash
chromium-browser --start-maximized --app=http://localhost:5000
```

This opens Chrome in "app mode" — no address bar, no tabs — but the user can still Alt+F4 or switch windows.

### 9. Auto-Start on Boot (Optional)

Create a systemd service:

```bash
sudo nano /etc/systemd/system/family-dashboard.service
```

```ini
[Unit]
Description=Family Dashboard
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/family-dashboard
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable family-dashboard
sudo systemctl start family-dashboard
```

For auto-launching Chrome, add to `/home/pi/.config/lxsession/LXDE-pi/autostart`:

```
@chromium-browser --start-maximized --app=http://localhost:5000
```

---

## Environment Variables (Optional)

| Variable | Default | Description |
|---|---|---|
| `DASHBOARD_PORT` | 5000 | Flask server port |
| `FLASK_SECRET_KEY` | (preset) | Flask session secret |
| `BUDGET_SHEET_ID` | (empty) | Google Sheet ID for budget |

---

## How It Works

### Data Refresh
All data refreshes automatically every 5 minutes. Use the "Refresh All Data" button in Home settings for an immediate refresh.

### Chore Resets
- **Daily Chores** automatically uncheck each morning (on first page load of the day)
- **Weekly Chores** automatically uncheck each Sunday

### Touch Interactions
- **Tap** any chore/list row to check it off
- **Long press** (600ms) a row to reveal the delete button
- **"+" buttons** open the in-app keyboard for adding items
- **Undo toasts** appear for 3 seconds after completing or deleting anything

### In-App Keyboard
A built-in on-screen keyboard appears when adding or editing items. It covers the bottom 35% of the screen with large touch-friendly keys. If it doesn't work well for your setup, you can fall back to the Raspberry Pi's system keyboard (e.g., Onboard or Squeekboard).

---

## Updating the Dashboard

When new changes are pushed to the repo, update the Pi:

```bash
cd /home/pi/family-dashboard
git pull origin main
```

If you're running the dashboard as a systemd service, restart it:

```bash
sudo systemctl restart family-dashboard
```

If you're running it manually, stop the process (Ctrl+C) and relaunch:

```bash
python3 app.py
```

Then refresh the browser (F5 or tap the Refresh button in the Home tab). Since the entire UI is a single HTML file served by Flask, pulling and restarting picks up all changes immediately.

If dependencies changed (check `requirements.txt`):

```bash
pip install -r requirements.txt --break-system-packages
```

---

## Apple Reminders Sync

The dashboard supports two modes for lists: **iCloud sync** (two-way with Apple Reminders on your iPhone/Mac) and **local-only** (JSON files on the Pi). Local-only is the default and works out of the box.

### Local-Only Mode (Default)

Lists are stored as JSON files in `data/reminders_*.json`. You can add, check off, edit, and delete items directly from the touchscreen. This is reliable and has zero external dependencies. The tradeoff is that changes on the dashboard don't sync to your phone and vice versa.

### iCloud Sync Mode

To enable two-way sync with Apple Reminders:

1. **Install pyicloud:**

   ```bash
   pip install pyicloud --break-system-packages
   ```

2. **Authenticate with iCloud:**

   ```bash
   cd /home/pi/family-dashboard
   python3 -c "
   from pyicloud import PyiCloudService
   api = PyiCloudService('YOUR_APPLE_ID@icloud.com', 'YOUR_PASSWORD')
   if api.requires_2fa:
       code = input('Enter 2FA code sent to your device: ')
       api.validate_2fa_code(code)
       print('Authenticated!')
   "
   ```

3. **Create matching lists in Apple Reminders** (exact names):
   - Daily Chores
   - Weekly Chores
   - Things to Talk About
   - Home Projects
   - Vacation Planning

4. **Store credentials** (so the dashboard can reconnect automatically):

   Create `data/icloud_creds.json`:
   ```json
   {
     "apple_id": "YOUR_APPLE_ID@icloud.com",
     "password": "YOUR_APP_SPECIFIC_PASSWORD"
   }
   ```

   Use an [app-specific password](https://support.apple.com/en-us/102654) rather than your main Apple ID password.

### How Sync Works

- On each page load or 5-minute refresh, the dashboard pulls the latest items from iCloud and saves them locally as a backup
- Items added on the touchscreen are pushed to iCloud immediately and also saved locally
- If iCloud is unreachable (network issues, session expired), the dashboard falls back to the local JSON files seamlessly
- Completions and deletions made on the touchscreen currently only update the local copy (iCloud write-back for these is a future improvement)

### Re-authenticating

iCloud sessions expire periodically. When that happens the dashboard quietly falls back to local data. To re-authenticate:

```bash
cd /home/pi/family-dashboard
python3 -c "
from pyicloud import PyiCloudService
api = PyiCloudService('YOUR_APPLE_ID@icloud.com', 'YOUR_PASSWORD')
if api.requires_2fa:
    code = input('Enter 2FA code: ')
    api.validate_2fa_code(code)
print('Re-authenticated!')
"
```

Then restart the dashboard service.

---

## Planned Integrations

- **Google Home / Chromecast**: Show "Now Playing" track info from Google Home speakers
- **Ecobee Thermostat**: Display current temperature, set point, and HVAC mode

---

## File Structure

```
family-dashboard/
├── app.py                  # Flask server + API routes
├── config.py               # Configuration & settings
├── weather.py              # Open-Meteo weather API
├── reminders_bridge.py     # Apple Reminders iCloud bridge
├── google_auth.py          # Google OAuth2 handler
├── google_calendar.py      # Google Calendar API
├── google_sheets.py        # Google Sheets API (budget)
├── setup_google_oauth.py   # One-time OAuth setup script
├── requirements.txt        # Python dependencies
├── .gitignore              # Excludes secrets & data files from git
├── templates/
│   └── index.html          # Full single-page dashboard UI
├── client_secret.json      # (you provide, gitignored) Google OAuth credentials
└── data/                   # (auto-created, gitignored) runtime data
    ├── settings.json
    ├── google_token.json
    ├── icloud_creds.json   # (optional) Apple ID for Reminders sync
    └── reminders_*.json    # Local list data
```
