"""
Google OAuth2 authentication for Calendar and Sheets.

This is a standalone OAuth flow for the family's personal Google account.
It does NOT rely on any pre-existing Google session on the device.

SETUP:
1. Go to https://console.cloud.google.com/
2. Create a new project (e.g. "Family Dashboard")
3. Enable: Google Calendar API, Google Sheets API
4. Create OAuth2 credentials (Desktop application type)
5. Download the JSON and save as client_secret.json in the project root
6. Run: python setup_google_oauth.py  (one-time, opens a browser for consent)
"""
import os
import json
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

# Project root is one level up from server/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRETS = os.path.join(BASE_DIR, "client_secret.json")
TOKEN_FILE = os.path.join(BASE_DIR, "data", "google_token.json")


def get_credentials():
    """Get valid Google OAuth2 credentials, refreshing if needed."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            creds = None

    return creds


def is_authenticated():
    """Check if we have valid Google credentials."""
    creds = get_credentials()
    return creds is not None and creds.valid


def run_oauth_flow(port=8090):
    """Run the OAuth consent flow. Call this during initial setup."""
    if not os.path.exists(CLIENT_SECRETS):
        return None, "client_secret.json not found. Download it from Google Cloud Console."

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
    creds = flow.run_local_server(port=port, open_browser=True)
    _save_token(creds)
    return creds, None


def _save_token(creds):
    """Save credentials to disk."""
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
