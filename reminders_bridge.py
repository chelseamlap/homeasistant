"""
Apple Reminders iCloud bridge for Raspberry Pi.

This module provides access to Apple Reminders via iCloud using the
pyicloud library. Since the Pi doesn't have native macOS Reminders
access, we authenticate directly with iCloud.

SETUP REQUIRED:
1. pip install pyicloud --break-system-packages
2. On first run, you'll need to complete 2FA verification
3. Your iCloud credentials are stored locally in ~/.pyicloud

If pyicloud is unavailable, falls back to a local JSON file store
so the dashboard still works for development/testing.
"""
import os
import json
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Try to import pyicloud for real iCloud access
_ICLOUD_AVAILABLE = False
_icloud_api = None

try:
    from pyicloud import PyiCloudService
    _ICLOUD_AVAILABLE = True
except ImportError:
    logger.warning("pyicloud not installed — using local JSON fallback for Reminders")


def _local_path(list_name):
    """Path to local JSON fallback file for a list."""
    safe = list_name.lower().replace(" ", "_")
    return os.path.join(DATA_DIR, f"reminders_{safe}.json")


def _load_local(list_name):
    """Load items from local JSON fallback."""
    path = _local_path(list_name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def _save_local(list_name, items):
    """Save items to local JSON fallback."""
    path = _local_path(list_name)
    with open(path, "w") as f:
        json.dump(items, f, indent=2, default=str)


def _reset_file_path():
    return os.path.join(DATA_DIR, "last_reset.json")


def _load_reset_dates():
    path = _reset_file_path()
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _save_reset_dates(dates):
    path = _reset_file_path()
    with open(path, "w") as f:
        json.dump(dates, f, indent=2)


# ---- iCloud connection ----

def connect_icloud(apple_id=None, password=None):
    """Connect to iCloud. Returns True if connected, error string otherwise."""
    global _icloud_api, _ICLOUD_AVAILABLE

    if not _ICLOUD_AVAILABLE:
        return "pyicloud not installed"

    if apple_id is None:
        creds_path = os.path.join(DATA_DIR, "icloud_creds.json")
        if os.path.exists(creds_path):
            with open(creds_path) as f:
                creds = json.load(f)
                apple_id = creds.get("apple_id")
                password = creds.get("password")

    if not apple_id or not password:
        return "No iCloud credentials configured"

    try:
        _icloud_api = PyiCloudService(apple_id, password)
        if _icloud_api.requires_2fa:
            return "2fa_required"
        return True
    except Exception as e:
        logger.error(f"iCloud connection failed: {e}")
        return str(e)


def verify_2fa(code):
    """Complete 2FA verification."""
    global _icloud_api
    if _icloud_api is None:
        return "Not connected"
    try:
        result = _icloud_api.validate_2fa_code(code)
        return True if result else "Invalid code"
    except Exception as e:
        return str(e)


# ---- Reminders CRUD (with local fallback) ----

def get_items(list_name):
    """Get all items from a Reminders list."""
    # Always try local first (it's the reliable path on Pi)
    items = _load_local(list_name)

    # If iCloud is connected, sync from there
    if _icloud_api and _ICLOUD_AVAILABLE:
        try:
            reminders = _icloud_api.reminders
            lists = reminders.lists
            target = None
            for lst in lists.values():
                if lst.get("title", "").lower() == list_name.lower():
                    target = lst
                    break
            if target:
                cloud_items = []
                for r in reminders.items.get(target["guid"], []):
                    cloud_items.append({
                        "id": r.get("guid", ""),
                        "title": r.get("title", ""),
                        "completed": r.get("completed", False),
                        "completed_date": r.get("completedDate"),
                        "created": r.get("createdDate"),
                    })
                _save_local(list_name, cloud_items)
                return cloud_items
        except Exception as e:
            logger.error(f"iCloud fetch failed for {list_name}: {e}")

    return items


def add_item(list_name, title):
    """Add an item to a Reminders list."""
    items = _load_local(list_name)
    new_item = {
        "id": f"local_{datetime.now().timestamp()}",
        "title": title,
        "completed": False,
        "completed_date": None,
        "created": datetime.now().isoformat(),
    }
    items.append(new_item)
    _save_local(list_name, items)

    # Try to sync to iCloud
    if _icloud_api and _ICLOUD_AVAILABLE:
        try:
            reminders = _icloud_api.reminders
            for lst in reminders.lists.values():
                if lst.get("title", "").lower() == list_name.lower():
                    reminders.add(lst["guid"], title)
                    break
        except Exception as e:
            logger.error(f"iCloud add failed: {e}")

    return new_item


def complete_item(list_name, item_id):
    """Mark an item as completed."""
    items = _load_local(list_name)
    for item in items:
        if item["id"] == item_id:
            item["completed"] = True
            item["completed_date"] = datetime.now().isoformat()
            break
    _save_local(list_name, items)
    return True


def uncomplete_item(list_name, item_id):
    """Undo completion of an item."""
    items = _load_local(list_name)
    for item in items:
        if item["id"] == item_id:
            item["completed"] = False
            item["completed_date"] = None
            break
    _save_local(list_name, items)
    return True


def delete_item(list_name, item_id):
    """Delete an item from a list."""
    items = _load_local(list_name)
    items = [i for i in items if i["id"] != item_id]
    _save_local(list_name, items)
    return True


def update_item(list_name, item_id, new_title):
    """Update an item's title."""
    items = _load_local(list_name)
    for item in items:
        if item["id"] == item_id:
            item["title"] = new_title
            break
    _save_local(list_name, items)
    return True


def reset_daily_chores():
    """Reset daily chores if we haven't already today."""
    dates = _load_reset_dates()
    today = date.today().isoformat()

    if dates.get("daily") != today:
        items = _load_local("Daily Chores")
        for item in items:
            item["completed"] = False
            item["completed_date"] = None
        _save_local("Daily Chores", items)
        dates["daily"] = today
        _save_reset_dates(dates)
        logger.info("Daily chores reset for %s", today)
        return True
    return False


def reset_weekly_chores():
    """Reset weekly chores on Sunday if not already done this week."""
    dates = _load_reset_dates()
    today = date.today()

    # Calculate start of current week (Monday)
    week_start = (today - __import__('datetime').timedelta(days=today.weekday())).isoformat()

    if dates.get("weekly") != week_start:
        if today.weekday() == 6:  # Sunday
            items = _load_local("Weekly Chores")
            for item in items:
                item["completed"] = False
                item["completed_date"] = None
            _save_local("Weekly Chores", items)
            dates["weekly"] = week_start
            _save_reset_dates(dates)
            logger.info("Weekly chores reset for week of %s", week_start)
            return True
    return False
