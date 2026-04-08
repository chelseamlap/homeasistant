"""Configuration for the Family Home Dashboard."""
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# --- Location (for weather) ---
# Default: set via Home tab settings, stored in data/settings.json
DEFAULT_LAT = 40.7128
DEFAULT_LON = -74.0060
DEFAULT_LOCATION_NAME = "New York, NY"

# --- Google OAuth2 ---
GOOGLE_CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, "client_secret.json")
GOOGLE_TOKEN_FILE = os.path.join(DATA_DIR, "google_token.json")
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

# --- Apple Reminders Lists ---
REMINDERS_LISTS = {
    "daily_chores": "Daily Chores",
    "weekly_chores": "Weekly Chores",
    "things_to_talk_about": "Things to Talk About",
    "home_projects": "Home Projects",
    "vacation_planning": "Vacation Planning",
}

# --- Google Sheets (Money tab) ---
BUDGET_SHEET_ID = ""  # Set via settings or env var
BUDGET_SHEET_ID = os.environ.get("BUDGET_SHEET_ID", "")

# --- Refresh interval (ms) ---
REFRESH_INTERVAL_MS = 5 * 60 * 1000  # 5 minutes

# --- Flask ---
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "family-dashboard-secret-change-me")
PORT = int(os.environ.get("DASHBOARD_PORT", 5000))


def load_settings():
    """Load user settings from disk."""
    path = os.path.join(DATA_DIR, "settings.json")
    defaults = {
        "latitude": DEFAULT_LAT,
        "longitude": DEFAULT_LON,
        "location_name": DEFAULT_LOCATION_NAME,
        "budget_sheet_id": BUDGET_SHEET_ID,
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
