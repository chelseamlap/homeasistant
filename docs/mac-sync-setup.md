# Mac Sync Setup & Migration Guide

How the Apple Reminders sync works, how to set it up, and what to do when you switch Macs.

---

## How It Works

Your Mac has native access to Apple Reminders. A sync script runs every 5 minutes:

1. Pulls any changes made on the Pi dashboard (adds, completes, deletes)
2. Applies those changes to Apple Reminders on the Mac
3. Exports all Reminders lists to a JSON file
4. Pushes the JSON to the Pi via SSH

The Pi dashboard reads from this JSON file. Changes made on your phone sync to Apple Reminders, then to the Pi on the next sync cycle.

---

## First-Time Setup

### Prerequisites

- SSH key access from your Mac to the Pi (so sync doesn't need a password)
- The home-launchpad repo cloned on both Mac and Pi

### Set Up SSH Keys (if you haven't already)

```
ssh-keygen -t ed25519
ssh-copy-id your-username@your-pi-ip
```

Test it: `ssh your-username@your-pi-ip "echo works"` — should not ask for a password.

### Run the Setup Script

```
cd /path/to/home-launchpad
bash sync/setup_mac_sync.sh
```

This will:
- Ask for your Pi's username and IP
- Save the config to `sync/sync_config.json`
- Install a launchd job that syncs every 5 minutes
- Run the first sync immediately

### Set the Backend on the Pi

On the Pi dashboard, go to **Home > Settings** and set **Lists Backend** to **Apple Reminders (Mac sync)**. Save and restart the dashboard.

---

## Switching to a New Mac

When you get a new Mac (e.g., job change), here's exactly what to do:

### 1. Set Up SSH Keys on the New Mac

```
ssh-keygen -t ed25519
ssh-copy-id your-username@your-pi-ip
```

### 2. Clone the Repo

```
git clone https://github.com/chelseamlap/home-launchpad.git
cd home-launchpad
```

### 3. Run the Sync Setup

```
bash sync/setup_mac_sync.sh
```

That's it. The script will ask for your Pi connection info and set everything up.

### What About the Old Mac?

The launchd job on the old Mac will just fail silently (it won't have network access to the Pi). If you still have access to the old Mac, you can clean up:

```
launchctl unload ~/Library/LaunchAgents/com.home-launchpad.reminders-sync.plist
rm ~/Library/LaunchAgents/com.home-launchpad.reminders-sync.plist
```

---

## If You Don't Have a Mac at All

If you're between Macs or don't have one available, switch the Pi to a different backend:

1. On the Pi dashboard, go to **Home > Settings**
2. Change **Lists Backend** to **Todoist** or **Local only**
3. Save and restart: `sudo systemctl restart home-launchpad`

The Pi will keep working — just with a different list source. You can switch back to Apple Sync when you have a Mac again.

---

## Troubleshooting

### Check if sync is running

```
cat /tmp/home-launchpad-sync.log
```

### Manually trigger a sync

```
cd /path/to/home-launchpad
python3 sync/reminders_sync.py
```

### Sync seems stuck / not updating

Check SSH: `ssh your-username@your-pi-ip "echo works"`

If SSH fails, your Pi's IP may have changed. Update `sync/sync_config.json` with the new IP.

### Reinstall the launchd job

```
launchctl unload ~/Library/LaunchAgents/com.home-launchpad.reminders-sync.plist
bash sync/setup_mac_sync.sh
```

---

## What Lives Where

| Component | Location | Purpose |
|---|---|---|
| Sync script | Mac: `sync/reminders_sync.py` | Exports Reminders, pushes to Pi |
| Sync config | Mac: `sync/sync_config.json` | Pi hostname and path (gitignored) |
| Launchd job | Mac: `~/Library/LaunchAgents/com.home-launchpad.reminders-sync.plist` | Runs sync every 5 min |
| Sync data | Pi: `data/reminders_sync.json` | Latest Reminders export |
| Pending changes | Pi: `data/reminders_pending.json` | Changes made on dashboard, waiting for Mac to apply |
