# The Home Launchpad

A touch-optimized family command center for a 24" Dell touchscreen on a Raspberry Pi 4. Five tabs: Today + This Week, Lists, Calendar, Home, Money.

## Architecture

- **Backend**: Python/Flask on the Pi, serves localhost
- **Frontend**: Single-page HTML/CSS/JS, dark mode, 1920x1080 landscape
- **Lists**: Apple Reminders — native macOS (JXA) or CalDAV (Pi), with local JSON fallback
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
mkdir home-launchpad
# (copy all project files here)

# Install Python packages
cd /home/pi/git-repo/home-launchpad
pip install -r requirements.txt --break-system-packages
```

### 2. Set Up Apple Reminders (CalDAV)

On the Raspberry Pi, the dashboard connects to Apple Reminders via iCloud's CalDAV protocol. This gives full read/write access to your Reminders lists.

1. **Generate an app-specific password** at https://appleid.apple.com → Sign-In and Security → App-Specific Passwords

2. **Create the credentials file** `data/icloud_creds.json`:

   ```json
   {
     "apple_id": "you@icloud.com",
     "password": "xxxx-xxxx-xxxx-xxxx"
   }
   ```

3. **Choose which lists to display** from the Home tab → Apple Reminders section. The dashboard auto-discovers all lists available to the configured Apple ID.

If CalDAV isn't configured, the dashboard falls back to local JSON files in `data/`. You can manage everything from the touchscreen — you just won't get sync with your phones.

> **Note on shared lists**: Each Apple ID can only see its own lists and lists explicitly shared *to* it. If both household members have Reminders lists you want on the dashboard, you'll need to configure both Apple IDs. Multi-account support is planned — for now, configure the account that owns the most lists you want to display, and have the other person share their lists to that account.

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
11. Place it in /home/pi/git-repo/home-launchpad/
```

**Run the OAuth flow:**

```bash
cd /home/pi/git-repo/home-launchpad
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
cd /home/pi/git-repo/home-launchpad
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
sudo nano /etc/systemd/system/home-launchpad.service
```

```ini
[Unit]
Description=Family Dashboard
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/git-repo/home-launchpad
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable home-launchpad
sudo systemctl start home-launchpad
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

### Themes & Background Image

The dashboard ships with three themes, selectable from **Home > Appearance**:

| Theme | Description |
|---|---|
| **Light** (default) | Clean light theme inspired by Home Assistant |
| **Dark** | Dark blue-gray theme |
| **Warm** | Soft warm tones |

Theme choice is saved per-browser (instant) and also synced to `settings.json` so all devices use the same default.

You can also set a **background image** (e.g., a family photo) from the Appearance section. The image is overlaid with a semi-transparent tint matching your theme so text stays readable. Adding new themes is straightforward — just add a new `[data-theme="name"]` CSS block in `index.html`.

#### Sending a background image to the Pi via SSH

From your laptop/desktop, use `scp` to copy the image directly to the Pi's data folder:

```bash
scp ~/Pictures/family-photo.jpg your-username@your-pi-ip:/home/pi/git-repo/home-launchpad/data/background.jpg
```

Then update `data/settings.json` on the Pi to point to it:

```bash
ssh your-username@your-pi-ip
cd /home/pi/git-repo/home-launchpad
python3 -c "
import json
s = json.load(open('data/settings.json'))
s['background_url'] = '/data/background.jpg'
json.dump(s, open('data/settings.json', 'w'), indent=2)
print('Done — refresh the dashboard browser to see the new background')
"
```

Replace `raspberrypi.local` with your Pi's hostname or IP address, and adjust the image filename/extension as needed (`.jpg`, `.png`, `.webp` are all supported). The dashboard will pick up the new background on the next page refresh.

---

## Updating the Dashboard

When new changes are pushed to the repo, update the Pi:

```bash
cd /home/pi/git-repo/home-launchpad
git pull origin main
```

If you're running the dashboard as a systemd service, restart it:

```bash
sudo systemctl restart home-launchpad
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

## Apple Reminders Integration

The dashboard connects to Apple Reminders with three backends, chosen automatically:

| Platform | Backend | Setup Required |
|---|---|---|
| **macOS** (development) | Native JXA via osascript | None — reads the Reminders app directly |
| **Raspberry Pi / Linux** | CalDAV via iCloud | App-specific password in `data/icloud_creds.json` |
| **Fallback** | Local JSON files | None — works offline, no sync |

### Configuring Lists

Lists are configured from the **Home tab → Apple Reminders** section:

1. The dashboard auto-discovers all available lists from your Apple account
2. Toggle which lists to display on the dashboard
3. Star lists to show them on the Today tab
4. Hit "Save List Selection" — config is stored in `data/settings.json`

You can also edit `data/settings.json` directly:

```json
{
  "reminders_lists": [
    {"key": "weekday_morning", "name": "Weekday morning", "show_on_today": true},
    {"key": "things_to_talk_about", "name": "Things to Talk About", "show_on_today": true},
    {"key": "vacation_planning", "name": "Vacation Planning", "show_on_today": false}
  ]
}
```

### How Sync Works

- All operations (add, complete, delete, edit) go directly to Apple Reminders and sync via iCloud to all your devices
- If the remote backend is unreachable, operations fall back to local JSON files
- The dashboard refreshes data every 5 minutes

### Known Limitations

- **Shared lists visibility**: On macOS, the JXA scripting API only sees lists owned by or explicitly shared *to* the logged-in user. Lists shared from another family member's account may not appear in auto-discovery. On CalDAV (Pi), only lists accessible to the configured Apple ID are visible.
- **Multi-account**: The dashboard currently supports one Apple ID at a time. If both household members have lists they want on the dashboard, the workaround is to share those lists to one account. Multi-account CalDAV support (configuring multiple Apple IDs) is planned for a future update.

---

## Planned Integrations

- **Multi-account Apple Reminders**: Support multiple Apple IDs so both household members' lists appear on the dashboard
- **Google Home / Chromecast**: Show "Now Playing" track info from Google Home speakers
- **Ecobee Thermostat**: Display current temperature, set point, and HVAC mode

---

## File Structure

```
home-launchpad/
├── app.py                  # Flask server + API routes
├── config.py               # Configuration & settings
├── weather.py              # Open-Meteo weather API
├── reminders_bridge.py     # Apple Reminders bridge (JXA / CalDAV / local JSON)
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
