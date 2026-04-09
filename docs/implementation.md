# Setting Up The Home Launchpad

A step-by-step guide to getting the family dashboard running on the Raspberry Pi kitchen display.

> **Before you start:** You'll need your Pi's hostname (or IP address) and username. To find your Pi's IP address, run `hostname -I` on the Pi. Your SSH connection will look like `ssh your-username@your-pi-ip`.

---

## What You Need

- Raspberry Pi 4 with Raspberry Pi OS installed
- 24" Dell touchscreen monitor connected to the Pi
- The Pi connected to your home Wi-Fi
- A computer (Mac or PC) on the same network to do initial setup
- Your Google account credentials (for Calendar and Budget)
- Your Apple ID (optional, for Reminders sync)

---

## Step 1: Connect to the Pi

From your Mac, open **Terminal** (Cmd+Space, type "Terminal") and connect:

```
ssh your-username@your-pi-ip
```

Type your Pi password when asked. You're now controlling the Pi from your Mac.

> **Tip:** If you've already set up SSH keys, it won't ask for a password.

---

## Step 2: Get the Code

If this is the first time:

```
cd ~/git-repo
git clone https://github.com/chelseamlap/home-launchpad.git
cd home-launchpad
```

If the code is already there:

```
cd ~/git-repo/home-launchpad
git pull
```

---

## Step 3: Run the Installer

```
chmod +x install.sh
./install.sh
```

The installer will walk you through everything:

1. **System packages** — installs Python, Chrome, etc.
2. **Python packages** — installs the dashboard's dependencies
3. **Location** — asks for your city and coordinates (you can skip this and set it from the dashboard later). Find your coordinates at https://www.latlong.net/
4. **Google account** — if you've placed `client_secret.json` in the folder, it runs the Google sign-in. If not, skip for now.
5. **System service** — say **yes** to install as a service so it starts automatically on boot
6. **Chrome autostart** — say **yes** so the dashboard opens in Chrome when the Pi boots up

---

## Step 4: Set Up Google Calendar and Sheets

This is the most involved step but you only do it once.

### Create a Google Cloud Project

1. Go to https://console.cloud.google.com/
2. Click **Select a project** at the top, then **New Project**
3. Name it "Family Dashboard" and click **Create**
4. Make sure your new project is selected at the top

### Turn on the APIs

1. Go to **APIs & Services > Library** (in the left menu)
2. Search for "Google Calendar API" and click **Enable**
3. Search for "Google Sheets API" and click **Enable**
4. Search for "Google Tasks API" and click **Enable**

### Create Login Credentials

1. Go to **APIs & Services > Credentials**
2. Click **+ Create Credentials > OAuth client ID**
3. If asked to configure a consent screen, choose "External", fill in the app name ("Family Dashboard"), your email, and save
4. Back in Credentials, click **+ Create Credentials > OAuth client ID**
5. Choose **Desktop app**, name it anything
6. Click **Download JSON**
7. Rename the downloaded file to `client_secret.json`

### Copy the File to the Pi

From a **new Terminal window on your Mac** (don't close the SSH one):

```
scp ~/Downloads/client_secret.json your-username@your-pi-ip:~/git-repo/home-launchpad/
```

### Run the Google Sign-In

Back in your **SSH window** (on the Pi):

```
cd ~/git-repo/home-launchpad
python3 setup_google_oauth.py
```

This opens a browser on the Pi. Sign in with your family Google account and allow access. The token is saved locally — you won't need to do this again unless it expires.

---

## Step 5: Choose Your Lists Backend

The dashboard supports multiple list/task services. On the Pi dashboard, go to **Home > Settings > Lists Backend** to choose:

| Backend | Best For | Setup |
|---|---|---|
| **Apple Reminders (Mac sync)** | Families already using Apple Reminders | Requires a Mac running the sync script. See [Mac Sync Setup](mac-sync-setup.md) |
| **Todoist** | Shared lists, no Mac required | Free account at todoist.com. Get your API token from todoist.com/app/settings/integrations/developer, then save it on the Pi: `echo 'YOUR_TOKEN' > ~/git-repo/home-launchpad/data/todoist_token.txt` |
| **Google Tasks** | Already using Google, no sharing needed | Enable the Google Tasks API in your Cloud project (same place you enabled Calendar/Sheets), then re-run `python3 setup_google_oauth.py` |
| **Local only** | Simple, no external service | Lists stored on the Pi only. No sync. |

---

## Step 6: Set a Background Photo

### Option A: From the Touchscreen

Go to **Home > Appearance > Background Image** and tap to upload a photo.

### Option B: From Your Mac

1. Put the photo on your Mac Desktop in the `home-launchpad-photos` folder
2. Open Terminal on your Mac and run:

```
scp ~/Desktop/home-launchpad-photos/your-photo.jpg your-username@your-pi-ip:~/git-repo/home-launchpad/data/background.jpg
```

3. Then set it as the background:

```
ssh your-username@your-pi-ip "cd ~/git-repo/home-launchpad && python3 -c \"
import json
s = json.load(open('data/settings.json'))
s['background_url'] = '/data/background.jpg'
json.dump(s, open('data/settings.json', 'w'), indent=2)
print('Done')
\""
```

4. Refresh the dashboard browser

---

## Step 7: Configure from the Touchscreen

Once the dashboard is running, go to the **Home** tab on the touchscreen to:

- **Apple Reminders** — check which lists to show, star the ones for the Today tab
- **Google Calendars** — check which calendars to include (primary, family, shared, etc.)
- **Appearance** — pick a theme (Light, Dark, or Warm) and set a background photo
- **Settings** — enter your location, coordinates, and Google Sheet ID

---

## Step 8: Reboot and Verify

```
sudo reboot
```

After about 30 seconds, the Pi should:
1. Boot up
2. Start the dashboard server automatically
3. Open Chrome in full-screen mode showing the dashboard

If Chrome opens but shows a blank page, wait a few more seconds — the server might still be starting up. It will retry automatically.

---

## Troubleshooting

### The dashboard isn't loading after reboot

Check if the service is running:

```
ssh your-username@your-pi-ip
sudo systemctl status home-launchpad
```

If it says "failed", check the error:

```
sudo journalctl -u home-launchpad -n 20 --no-pager
```

> **Note:** If you installed before the rename, your service may be called `family-dashboard` instead. Use `sudo systemctl status family-dashboard` to check.

### Port 5000 is already in use

Something else is using the port. Kill it and restart:

```
sudo fuser -k 5000/tcp
sudo systemctl restart home-launchpad
```

### Google Calendar isn't showing my events

Go to **Home > Google Calendars** and make sure all the calendars you want are checked. Your "Family" calendar is separate from your primary calendar — you need to check both.

### Weather shows the wrong location

Go to **Home > Settings** and update the latitude/longitude. Find your coordinates at https://www.latlong.net/

### Exit kiosk mode without a keyboard

Go to **Home > Settings** on the touchscreen and tap **Exit Kiosk**. This closes Chrome so you can access the Pi desktop. To re-enter kiosk mode, reboot the Pi or run:

```
chromium --kiosk --password-store=basic --app=http://localhost:5000
```

### I forgot the Pi's password

If you can still connect with SSH keys, change it with `passwd`. Otherwise, you'll need physical access to the Pi to reset it (see the README for instructions).
