#!/usr/bin/env python3
"""
One-time Google OAuth2 setup script.

Run this on the Raspberry Pi (with a display connected, or via SSH with
X11 forwarding) to authenticate the family Google account.

Usage:
    python setup_google_oauth.py

Prerequisites:
    1. Download client_secret.json from Google Cloud Console
    2. Place it in the same directory as this script
    3. Ensure Google Calendar API and Google Sheets API are enabled
"""
import os
import sys

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google_auth import run_oauth_flow, is_authenticated


def main():
    if is_authenticated():
        print("\n✓ Already authenticated with Google!")
        print("  To re-authenticate, delete data/google_token.json and run again.")
        return

    print("\n╔══════════════════════════════════════════════╗")
    print("║   Family Dashboard — Google OAuth Setup     ║")
    print("╚══════════════════════════════════════════════╝\n")
    print("This will open a browser window for you to sign in")
    print("with the family Google account.\n")

    creds, error = run_oauth_flow()

    if error:
        print(f"\n✗ Error: {error}")
        if "client_secret.json" in error:
            print("\n  To fix this:")
            print("  1. Go to https://console.cloud.google.com/")
            print("  2. Create a project → Enable Calendar API & Sheets API")
            print("  3. Create OAuth2 credentials (Desktop application)")
            print("  4. Download the JSON → rename to client_secret.json")
            print("  5. Place in:", os.path.dirname(os.path.abspath(__file__)))
        sys.exit(1)
    else:
        print("\n✓ Google account connected successfully!")
        print("  Token saved to data/google_token.json")
        print("  The dashboard can now access Calendar and Sheets.")


if __name__ == "__main__":
    main()
