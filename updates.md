# Updating The Home Launchpad

How to make changes, update the Pi, and common things you might want to do.

---

## Pulling New Changes to the Pi

Whenever changes are made to the code (by you or with Claude), get them onto the Pi:

### From the Pi's Terminal (if you're at the keyboard)

```
cd ~/git-repo/home-launchpad
git pull
sudo systemctl restart family-dashboard
```

### From your Mac (remotely)

```
ssh your-username@your-pi-ip "cd ~/git-repo/home-launchpad && git pull && sudo systemctl restart family-dashboard"
```

Then refresh the browser on the Pi (or just wait — it refreshes itself every 5 minutes).

---

## Things You Can Change from the Touchscreen

These don't require any code changes — just tap on the **Home** tab:

| What | Where | How |
|---|---|---|
| Which Reminders lists show up | Home > Apple Reminders | Check/uncheck lists, star for Today tab, tap Save |
| Which Google calendars show up | Home > Google Calendars | Check/uncheck calendars, tap Save |
| Theme (Light/Dark/Warm) | Home > Appearance | Pick from the dropdown — changes instantly |
| Background photo | Home > Appearance | Tap "Choose File" to upload from the Pi |
| Location & weather | Home > Settings | Type your city, lat/lon, and tap Save |
| Budget sheet | Home > Settings | Paste your Google Sheet ID and tap Save |
| Weekend plans | Today tab | Tap the Saturday/Sunday fields to type |
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
ssh your-username@your-pi-ip "sudo systemctl restart family-dashboard"
```

### Full reboot (from your Mac)

```
ssh your-username@your-pi-ip "sudo reboot"
```

The Pi takes about 30 seconds to come back up. Chrome will reopen automatically.

### From the Pi itself

If you have a keyboard connected, press **Ctrl+Alt+T** to open a terminal, then:

```
sudo systemctl restart family-dashboard
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
ssh your-username@your-pi-ip "sudo systemctl status family-dashboard"
```

If it says "failed", restart it:

```
ssh your-username@your-pi-ip "sudo systemctl restart family-dashboard"
```

### Calendar is missing events

Go to **Home > Google Calendars** on the touchscreen and make sure all your calendars are checked (primary, family, shared, etc.). Tap **Save Calendar Selection**.

### Reminders aren't syncing

Check that `data/icloud_creds.json` has the right Apple ID and app-specific password. If Apple changed something, you may need to generate a new app-specific password at https://appleid.apple.com.

### Weather is wrong or missing

Go to **Home > Settings** and check that latitude/longitude are correct for ***REMOVED***
***REMOVED***
your location. Find your coordinates at https://www.latlong.net/

### Screen went black / Chrome closed

SSH in and check if the service is running, then restart Chrome:

```
ssh your-username@your-pi-ip
sudo systemctl status family-dashboard  # should say "active (running)"
DISPLAY=:0 chromium --start-maximized --app=http://localhost:5000 &
```

### I pulled changes but nothing changed on screen

After pulling, you need to restart the service AND refresh the browser:

```
ssh your-username@your-pi-ip "sudo systemctl restart family-dashboard"
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
| Restart the dashboard | `sudo systemctl restart family-dashboard` |
| Check if dashboard is running | `sudo systemctl status family-dashboard` |
| See error logs | `sudo journalctl -u family-dashboard -n 20 --no-pager` |
| Reboot the Pi | `sudo reboot` |
| Send a file to the Pi | `scp ~/path/to/file your-username@your-pi-ip:~/git-repo/home-launchpad/data/` |
| Kill something on port 5000 | `sudo fuser -k 5000/tcp` |
