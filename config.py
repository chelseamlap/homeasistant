"""Configuration for the Family Home Dashboard."""
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# --- Location (for weather) ---
# Default: set via Home tab settings, stored in data/settings.json
DEFAULT_LAT = 39.6133
DEFAULT_LON = -105.0166
DEFAULT_LOCATION_NAME = "Littleton, CO"
DEFAULT_TIMEZONE = "America/Denver"

# --- Google OAuth2 ---
GOOGLE_CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, "client_secret.json")
GOOGLE_TOKEN_FILE = os.path.join(DATA_DIR, "google_token.json")
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
]

# --- Reminders Lists ---
# Populated by the user via Home > Settings, stored in data/settings.json
# under "reminders_lists". Each entry:
#   { "key": "url_safe_slug", "name": "Exact Project Name",
#     "show_on_today": true/false }
DEFAULT_REMINDERS_LISTS = []

# --- Google Sheets (Money tab) ---
BUDGET_SHEET_ID = os.environ.get("BUDGET_SHEET_ID", "")

# --- Refresh interval (ms) ---
REFRESH_INTERVAL_MS = 30 * 60 * 1000  # 30 minutes

# --- Flask ---
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "home-launchpad-secret-change-me")
PORT = int(os.environ.get("DASHBOARD_PORT", 5000))


def load_settings():
    """Load user settings from disk."""
    path = os.path.join(DATA_DIR, "settings.json")
    defaults = {
        "latitude": DEFAULT_LAT,
        "longitude": DEFAULT_LON,
        "location_name": DEFAULT_LOCATION_NAME,
        "budget_sheet_id": BUDGET_SHEET_ID,
        "timezone": DEFAULT_TIMEZONE,
        "chores_list": "chores",
        "chore_unassigned_label": "Home",
    }
    if os.path.exists(path):
        with open(path) as f:
            saved = json.load(f)
            defaults.update(saved)
    return defaults


def save_settings(settings):
    """Save user settings to disk."""
    path = os.path.join(DATA_DIR, "settings.json")
    with open(path, "w") as f:
        json.dump(settings, f, indent=2)


def get_reminders_lists():
    """Get configured reminders lists. Returns list of dicts with key, name, show_on_today."""
    settings = load_settings()
    return settings.get("reminders_lists", DEFAULT_REMINDERS_LISTS)


def get_reminders_list_name(key):
    """Look up the Apple Reminders list name for a given URL key."""
    for lst in get_reminders_lists():
        if lst["key"] == key:
            return lst["name"]
    return key  # fallback: use the key itself
