# Updating The Home Launchpad

> **Note:** Replace `your-username@your-pi-ip` in commands below with your Pi's actual username and IP address. Run `hostname -I` on the Pi to find its IP.

> **Note:** If you installed before the rename, your service may be called `family-dashboard` instead of `home-launchpad`.

How to make changes, update the Pi, and common things you might want to do.

---

## Pulling New Changes to the Pi

Whenever changes are made to the code (by you or with Claude), get them onto the Pi:

### From the Pi's Terminal (if you're at the keyboard)

```
cd ~/git-repo/home-launchpad
git pull
sudo systemctl restart home-launchpad
```

### From your Mac (remotely)

```
ssh your-username@your-pi-ip "cd ~/git-repo/home-launchpad && git pull && sudo systemctl restart home-launchpad"
```

Then refresh the browser on the Pi (or just wait — it refreshes itself every 5 minutes).

---

## Things You Can Change from the Touchscreen

These don't require any code changes — just tap on the **Home** tab:

| What | Where | How |
|---|---|---|
| Which Reminders lists show up | Home > Apple Reminders | Check/uncheck lists, star for Today tab, tap Save |
| Which Google calendars show up | Home > Google Calendars | Check/uncheck calendars, tap Save |
| Theme (with auto option) | Home > Appearance | System (auto dark/light), Dark, Light, Warm |
| Background photo | Home > Appearance | Tap "Choose File" to upload from the Pi |
| Location & weather | Home > Settings | Type your city, lat/lon, and tap Save |
| Budget sheet | Home > Settings | Paste your Google Sheet ID and tap Save (the sheet must be in the Drive folder shared with the service account) |
| Lists backend | Home > Settings | Pick from dropdown: Apple Sync, Todoist, Google Tasks, Local |
| Weekend plans | Today tab | Tap Saturday/Sunday fields — now saved to settings (survives restarts) |
| Exit kiosk mode | Home > Settings | Tap "Exit Kiosk" to close Chrome and access the Pi desktop |
| Add items to a list | Lists tab | Tap the "+" button at the bottom of any list |
| Check off items | Today or Lists tab | Tap any row to mark it done |
| Delete items | Today or Lists tab | Long-press (hold for ~1 second) to show the delete button |

---

## Sending a New Background Photo

### From your Mac

1. Put the photo in `~/Desktop/home-launchpad-photos/`
2. Open Terminal and run:

```
scp ~/Desktop/home-launchpad-photos/your-photo.jpg your-username@your-pi-ip:~/git-repo/home-launchpad/data/background.jpg
```

3. Then tell the dashboard to use it:

```
ssh your-username@your-pi-ip "cd ~/git-repo/home-launchpad && python3 -c \"
import json
s = json.load(open('data/settings.json'))
s['background_url'] = '/data/background.jpg'
json.dump(s, open('data/settings.json', 'w'), indent=2)
print('Done')
\""
```

4. Refresh the dashboard browser on the Pi

### From the touchscreen

Go to **Home > Appearance > Background Image** and upload directly.

---

## Restarting the Dashboard

If something looks wrong or the screen is frozen:

### Quick restart (from your Mac)

```
ssh your-username@your-pi-ip "sudo systemctl restart home-launchpad"
```

### Full reboot (from your Mac)

```
ssh your-username@your-pi-ip "sudo reboot"
```

The Pi takes about 30 seconds to come back up. Chrome will reopen automatically.

### From the Pi itself

If you have a keyboard connected, press **Ctrl+Alt+T** to open a terminal, then:

```
sudo systemctl restart home-launchpad
```

---

## Requesting Feature Changes

When you want something new or different on the dashboard, here's how to work with Claude:

1. **Describe what you want** in plain language — "I want the calendar to show birthdays" or "Make the font bigger on the Today tab"
2. **Claude will make the code changes** on your Mac
3. **Claude will push to a feature branch** and merge when you approve
4. **Pull the changes on the Pi** (see "Pulling New Changes" above)

### Examples of things you can ask for

- "Add a new tab for _____"
- "Make the weather show Celsius instead of Fahrenheit"
- "Change the accent color to green"
- "Add a countdown to our vacation"
- "Show the grocery list on the Today tab"
- "Make the font bigger/smaller"
- "Change the layout of the Calendar tab"

---

## Common Quick Fixes

### Dashboard shows "Loading..." forever

The server might not be running:

```
ssh your-username@your-pi-ip "sudo systemctl status home-launchpad"
```

If it says "failed", restart it:

```
ssh your-username@your-pi-ip "sudo systemctl restart home-launchpad"
```

### Calendar is missing events

Go to **Home > Google Calendars** on the touchscreen and make sure all your calendars are checked (primary, family, shared, etc.). Tap **Save Calendar Selection**.

### Reminders aren't syncing

Check which backend is selected in **Home > Settings > Lists Backend**:
- **Apple Sync**: Make sure the Mac sync script is running (`cat /tmp/home-launchpad-sync.log` on the Mac)
- **Todoist**: Verify the API token in `data/todoist_token.txt`
- **Google Tasks**: Re-run `python3 setup_google_oauth.py` if the token expired (this handles Calendar/Tasks auth only — Sheets uses a separate service account now)

### Weather is wrong or missing

Go to **Home > Settings** and check that latitude/longitude are correct for your location. Find your coordinates at https://www.latlong.net/

### Kiosk mode — can't access the desktop

Go to **Home > Settings** and tap **Exit Kiosk**. This closes Chrome so you can access the Pi desktop. To re-enter kiosk mode, reboot or run: `chromium --kiosk --password-store=basic --app=http://localhost:5000`

### Budget/Money tab shows sample data

Make sure the service account key file exists at `data/google_service_account.json` and that the spreadsheet is in the Drive folder shared with the service account. If the file is missing or the sheet isn't shared, the dashboard falls back to sample data.

### Todoist lists missing names

If you're using Todoist, each task now shows the **assigned person** next to it. If names look wrong, double-check that collaborators are set up correctly in your Todoist project.

### Lists showing old/fallback data

Check which backend is selected in **Home > Settings > Lists Backend**. If using Apple Sync, make sure the Mac sync script is running. If using Todoist, verify the API token in `data/todoist_token.txt`.

### Screen went black / Chrome closed

SSH in and check if the service is running, then restart Chrome:

```
ssh your-username@your-pi-ip
sudo systemctl status home-launchpad  # should say "active (running)"
DISPLAY=:0 chromium --start-maximized --app=http://localhost:5000 &
```

### I pulled changes but nothing changed on screen

After pulling, you need to restart the service AND refresh the browser:

```
ssh your-username@your-pi-ip "sudo systemctl restart home-launchpad"
```

Then tap the screen or press F5 on the Pi to refresh the browser.

---

## How the Pi Stays Updated

The Pi does **not** auto-update from GitHub. Changes only arrive when you explicitly run `git pull`. This is by design — nothing changes on the kitchen display unless you want it to.

The typical flow is:

1. You ask Claude to make changes on your Mac
2. Claude pushes the changes to GitHub
3. You (or Claude) runs `git pull` on the Pi
4. The dashboard restarts with the new code

---

## Useful SSH Commands Reference

| What | Command |
|---|---|
| Connect to the Pi | `ssh your-username@your-pi-ip` |
| Pull latest code | `cd ~/git-repo/home-launchpad && git pull` |
| Restart the dashboard | `sudo systemctl restart home-launchpad` |
| Check if dashboard is running | `sudo systemctl status home-launchpad` |
| See error logs | `sudo journalctl -u home-launchpad -n 20 --no-pager` |
| Reboot the Pi | `sudo reboot` |
| Send a file to the Pi | `scp ~/path/to/file your-username@your-pi-ip:~/git-repo/home-launchpad/data/` |
| Kill something on port 5000 | `sudo fuser -k 5000/tcp` |
