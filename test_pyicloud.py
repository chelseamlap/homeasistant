#!/usr/bin/env python3
"""Quick test to see if pyicloud can discover all Reminders lists."""
import json, os

try:
    from pyicloud import PyiCloudService
except ImportError:
    print("pyicloud not installed. Run: pip3 install pyicloud")
    exit(1)

creds_path = os.path.join(os.path.dirname(__file__), "data", "icloud_creds.json")
with open(creds_path) as f:
    creds = json.load(f)

print(f"Connecting as {creds['apple_id']}...")
api = PyiCloudService(creds["apple_id"], creds["password"])

if api.requires_2fa:
    print("2FA required — enter the code sent to your device:")
    code = input("Code: ")
    api.validate_2fa_code(code)

print("\nReminders service:")
service = api.reminders
service.refresh()

# Try to find lists
if hasattr(service, "lists"):
    print(f"\nFound {len(service.lists)} lists:")
    for guid, lst in service.lists.items():
        title = lst.get("title", lst.get("name", guid))
        print(f"  - {title} (guid: {guid})")
elif hasattr(service, "collections"):
    print(f"\nFound {len(service.collections)} collections:")
    for key, col in service.collections.items():
        print(f"  - {col}")
else:
    print("\nDumping service attributes for debugging:")
    for attr in sorted(dir(service)):
        if not attr.startswith("_"):
            print(f"  {attr}: {type(getattr(service, attr))}")
