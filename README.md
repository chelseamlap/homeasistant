# Home Launchpad

A touch-optimized family command center for a 24" Dell touchscreen on a Raspberry Pi 4. Five tabs: Today + This Week, Lists, Calendar, Home, Money.

**New here?** Start with these guides:
- **[See what it looks like](docs/mockup.html)** — Open in a browser to preview the dashboard UI
- **[implementation.md](docs/implementation.md)** — Step-by-step setup from scratch (written for non-technical users)
- **[google-setup.md](docs/google-setup.md)** — Google Calendar + Sheets setup (OAuth & service account)
- **[updates.md](docs/updates.md)** — How to update the Pi, change settings, and request new features

## Architecture

- **Backend**: Python/Flask on the Pi, serves localhost
- **Frontend**: Single-page HTML/CSS/JS, themeable (light/dark/warm), 1920x1080 landscape
- **Lists**: Apple Reminders — native macOS (JXA) with configurable Pi backend (Mac sync, Todoist, Google Tasks, or local JSON)
- **Calendar**: Google Calendar API via OAuth2 (multi-calendar support)
- **Budget**: Google Sheets API via Service Account (folder-scoped)
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

## Lists Backend (Reminders/Tasks)

The dashboard supports multiple list backends, configurable from **Home > Settings > Lists Backend** on the touchscreen:

| Backend | Shared Lists? | Requires |
|---|---|---|
| **Apple Reminders (Mac sync)** | Yes | A Mac running the sync script (see [Mac Sync Setup](docs/mac-sync-setup.md)) |
| **Todoist** | Yes | Free Todoist account + API token in `data/todoist_token.txt` |
| **Google Tasks** | No | Google Tasks API enabled + OAuth re-authorization |
| **Local only** | No | Nothing — lists stored on Pi only |

On macOS, the dashboard always uses native Apple Reminders access (JXA) regardless of this setting.

### 2. Set Up Google (Calendar + Sheets)

See **[Google Setup Guide](docs/google-setup.md)** for detailed instructions covering:
- Creating a Google Cloud project
- **Calendar** — OAuth2 login for your personal calendars
- **Sheets** — Service account scoped to a single Drive folder (for budget/bills)

Quick version:

```bash
# Calendar: place client_secret.json in project root, then:
cd /home/pi/git-repo/home-launchpad && python3 setup_google_oauth.py

# Sheets: place service account key in data/, then share your Drive folder with the service account email
```

### 3. Configure Google Calendars

After connecting your Google account, go to **Home > Google Calendars** to select which calendars appear on the dashboard. The dashboard auto-discovers all calendars on the connected account (primary, shared, family, etc.). By default, only the primary calendar is shown.

### 4. Set Up the Google Sheet for Budget

Create a Google Sheet **inside the Drive folder you shared with the service account** with two tabs:

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

### 5. Configure Location

On first launch, go to the **Home** tab and enter:
- Your city name (for display)
- Latitude and longitude (for weather)
- The Google Sheet ID (for budget)

Find your coordinates at https://www.latlong.net/

### 6. Launch the Dashboard

```bash
cd /home/pi/git-repo/home-launchpad
python3 app.py
```

The server starts on port 5000 by default.

### 7. Launch Chrome in Kiosk Mode

```bash
chromium --kiosk --noerrdialogs --disable-infobars --app=http://localhost:5000
```

This opens Chrome in true full-screen kiosk mode — no title bar, no address bar, no OS menu bar. Press **Alt+F4** to exit if needed.

### 8. Auto-Start on Boot (Optional)

Create a systemd service:

```bash
sudo nano /etc/systemd/system/home-launchpad.service
```

```ini
[Unit]
Description=Home Launchpad
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

The dashboard ships with four themes, selectable from **Home > Appearance**:

| Theme | Description |
|---|---|
| **Light** (default) | Clean light theme inspired by Home Assistant |
| **Dark** | Dark blue-gray theme |
| **Warm** | Soft warm tones |
| **System** | Auto dark at night, light by day |

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

## Apple Reminders / Lists Integration

The dashboard supports five list backends:

| Backend | Platform | Description |
|---|---|---|
| **macOS native (JXA)** | macOS only | Always used on Mac — reads/writes the Reminders app directly via osascript |
| **Apple Sync** | Pi | A Mac exports Reminders JSON to the Pi via SSH on a schedule (see [Mac Sync Setup](docs/mac-sync-setup.md)) |
| **Todoist** | Pi | REST API integration — supports shared projects, two-way sync |
| **Google Tasks** | Pi | Uses your existing Google OAuth credentials — no extra setup beyond enabling the API |
| **Local JSON** | Any | Fallback when nothing else is available — lists stored on-device only, no sync |

On macOS, native JXA is always used regardless of the configured backend. On the Pi, choose your backend from **Home > Settings > Lists Backend**.

### Configuring Lists

Lists are configured from the **Home tab → Lists** section:

1. The dashboard auto-discovers all available lists from your configured backend
2. Each list has two checkboxes: **Lists Tab** (shows on the Lists tab) and **Today Tab** (shows on the Today tab)
3. Lists on the Today tab appear side-by-side at half width
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

- All operations (add, complete, delete, edit) go to the configured backend and sync to connected devices
- If the remote backend is unreachable, operations fall back to local JSON files
- The dashboard refreshes data every 5 minutes

---

## Planned Integrations

- **Google Home / Chromecast**: Show "Now Playing" track info from Google Home speakers
- **Ecobee Thermostat**: Display current temperature, set point, and HVAC mode

---

## File Structure

```
home-launchpad/
├── app.py                  # Flask server + API routes
├── config.py               # Configuration & settings
├── setup_google_oauth.py   # Convenience wrapper for OAuth setup
├── requirements.txt        # Python dependencies
├── .gitignore              # Excludes secrets & data files from git
├── docs/
│   ├── implementation.md   # Setup guide for non-technical users
│   ├── google-setup.md     # Google Calendar + Sheets setup (OAuth & service account)
│   ├── updates.md          # How to update, change settings, request features
│   └── mac-sync-setup.md   # How to set up Mac → Pi reminders sync
├── server/
│   ├── __init__.py
│   ├── weather.py          # Open-Meteo weather API
│   ├── reminders_bridge.py # Lists backend dispatcher (JXA / sync / Todoist / Google Tasks / local)
│   ├── google_auth.py      # Google OAuth2 handler
│   ├── google_calendar.py  # Google Calendar API (multi-calendar)
│   ├── google_sheets.py    # Google Sheets API via service account (budget)
│   ├── google_tasks.py     # Google Tasks API (lists backend)
│   ├── todoist.py          # Todoist REST API (lists backend)
│   └── setup_google_oauth.py # One-time OAuth setup script
├── sync/
│   ├── reminders_sync.py       # Exports Apple Reminders to JSON for Pi sync
│   ├── setup_mac_sync.sh       # One-time setup script for Mac sync
│   └── com.home-launchpad.reminders-sync.plist  # launchd schedule for auto-sync
├── templates/
│   └── index.html          # Full single-page dashboard UI
├── client_secret.json      # (you provide, gitignored) Google OAuth credentials
└── data/                   # (auto-created, gitignored) runtime data
    ├── settings.json
    ├── google_token.json          # OAuth token (Calendar)
    ├── google_service_account.json # Service account key (Sheets)
    ├── todoist_token.txt           # (optional) Todoist API token
    └── reminders_*.json            # Local list data
```
