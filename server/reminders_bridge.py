"""
Reminders bridge with multiple backends:

1. macOS native (JXA) — used on Mac, reads/writes the Reminders app directly.
2. Google Tasks — used on Raspberry Pi or any non-Mac. Uses the Google Tasks
   API (same OAuth as Calendar/Sheets). Full read/write for all lists.
3. CalDAV (iCloud) — legacy fallback for non-Mac if Google Tasks unavailable.
4. Local JSON — fallback when none of the above is available.

For Google Tasks (Raspberry Pi):
  Enable the Google Tasks API in your Cloud project and re-run
  setup_google_oauth.py to authorize the Tasks scope.
"""
import os
import json
import logging
import platform
import subprocess
import uuid as _uuid
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

# Project root is one level up from server/
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

_IS_MACOS = platform.system() == "Darwin"

# Google Tasks support for non-macOS (Raspberry Pi)
_GOOGLE_TASKS_AVAILABLE = False
try:
    from server import google_tasks
    _GOOGLE_TASKS_AVAILABLE = True
except ImportError:
    if not _IS_MACOS:
        logger.warning("google_tasks not available — check Google OAuth setup")

# CalDAV support (legacy fallback for non-macOS)
_CALDAV_AVAILABLE = False
_caldav_principal = None

try:
    import caldav
    _CALDAV_AVAILABLE = True
except ImportError:
    if not _IS_MACOS:
        logger.info("caldav not installed — using Google Tasks or local fallback")


# ---- Local JSON storage (fallback + reset tracking) ----

def _local_path(list_name):
    safe = list_name.lower().replace(" ", "_")
    return os.path.join(DATA_DIR, f"reminders_{safe}.json")


def _load_local(list_name):
    path = _local_path(list_name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def _save_local(list_name, items):
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


# ---- macOS native Reminders via JXA ----

def _run_jxa(script):
    """Run a JXA script via osascript and return parsed JSON output."""
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            logger.error("JXA error: %s", result.stderr.strip())
            return None
        output = result.stdout.strip()
        if not output:
            return None
        return json.loads(output)
    except subprocess.TimeoutExpired:
        logger.error("JXA script timed out")
        return None
    except (json.JSONDecodeError, Exception) as e:
        logger.error("JXA parse error: %s (output: %s)", e, result.stdout[:200])
        return None


def _macos_get_items(list_name):
    """Fetch all reminders from a macOS Reminders list."""
    script = f"""
    (() => {{
        const app = Application("Reminders");
        const listName = {json.dumps(list_name)};
        let targetList = null;
        const lists = app.lists();
        for (let i = 0; i < lists.length; i++) {{
            if (lists[i].name() === listName) {{
                targetList = lists[i];
                break;
            }}
        }}
        if (!targetList) return JSON.stringify([]);
        const rems = targetList.reminders();
        const items = [];
        for (let i = 0; i < rems.length; i++) {{
            const r = rems[i];
            items.push({{
                id: r.id(),
                title: r.name(),
                completed: r.completed(),
                completed_date: r.completionDate() ? r.completionDate().toISOString() : null,
                created: r.creationDate() ? r.creationDate().toISOString() : null,
            }});
        }}
        return JSON.stringify(items);
    }})()
    """
    return _run_jxa(script)


def _macos_add_item(list_name, title):
    """Add a reminder to a macOS Reminders list. Returns the new item."""
    script = f"""
    (() => {{
        const app = Application("Reminders");
        const listName = {json.dumps(list_name)};
        let targetList = null;
        const lists = app.lists();
        for (let i = 0; i < lists.length; i++) {{
            if (lists[i].name() === listName) {{
                targetList = lists[i];
                break;
            }}
        }}
        if (!targetList) {{
            // Create the list if it doesn't exist
            targetList = app.List({{name: listName}});
            app.lists.push(targetList);
        }}
        const rem = app.Reminder({{name: {json.dumps(title)}, body: ""}});
        targetList.reminders.push(rem);
        return JSON.stringify({{
            id: rem.id(),
            title: rem.name(),
            completed: false,
            completed_date: null,
            created: new Date().toISOString(),
        }});
    }})()
    """
    return _run_jxa(script)


def _macos_complete_item(list_name, item_id):
    """Mark a reminder as completed."""
    script = f"""
    (() => {{
        const app = Application("Reminders");
        const listName = {json.dumps(list_name)};
        const targetId = {json.dumps(item_id)};
        const lists = app.lists();
        for (let i = 0; i < lists.length; i++) {{
            if (lists[i].name() === listName) {{
                const rems = lists[i].reminders();
                for (let j = 0; j < rems.length; j++) {{
                    if (rems[j].id() === targetId) {{
                        rems[j].completed = true;
                        return JSON.stringify({{ok: true}});
                    }}
                }}
            }}
        }}
        return JSON.stringify({{ok: false, error: "not found"}});
    }})()
    """
    return _run_jxa(script)


def _macos_uncomplete_item(list_name, item_id):
    """Mark a reminder as not completed."""
    script = f"""
    (() => {{
        const app = Application("Reminders");
        const listName = {json.dumps(list_name)};
        const targetId = {json.dumps(item_id)};
        const lists = app.lists();
        for (let i = 0; i < lists.length; i++) {{
            if (lists[i].name() === listName) {{
                const rems = lists[i].reminders();
                for (let j = 0; j < rems.length; j++) {{
                    if (rems[j].id() === targetId) {{
                        rems[j].completed = false;
                        return JSON.stringify({{ok: true}});
                    }}
                }}
            }}
        }}
        return JSON.stringify({{ok: false, error: "not found"}});
    }})()
    """
    return _run_jxa(script)


def _macos_delete_item(list_name, item_id):
    """Delete a reminder."""
    script = f"""
    (() => {{
        const app = Application("Reminders");
        const listName = {json.dumps(list_name)};
        const targetId = {json.dumps(item_id)};
        const lists = app.lists();
        for (let i = 0; i < lists.length; i++) {{
            if (lists[i].name() === listName) {{
                const rems = lists[i].reminders();
                for (let j = 0; j < rems.length; j++) {{
                    if (rems[j].id() === targetId) {{
                        app.delete(rems[j]);
                        return JSON.stringify({{ok: true}});
                    }}
                }}
            }}
        }}
        return JSON.stringify({{ok: false, error: "not found"}});
    }})()
    """
    return _run_jxa(script)


def _macos_update_item(list_name, item_id, new_title):
    """Update a reminder's title."""
    script = f"""
    (() => {{
        const app = Application("Reminders");
        const listName = {json.dumps(list_name)};
        const targetId = {json.dumps(item_id)};
        const lists = app.lists();
        for (let i = 0; i < lists.length; i++) {{
            if (lists[i].name() === listName) {{
                const rems = lists[i].reminders();
                for (let j = 0; j < rems.length; j++) {{
                    if (rems[j].id() === targetId) {{
                        rems[j].name = {json.dumps(new_title)};
                        return JSON.stringify({{ok: true}});
                    }}
                }}
            }}
        }}
        return JSON.stringify({{ok: false, error: "not found"}});
    }})()
    """
    return _run_jxa(script)


def _macos_reset_list(list_name):
    """Uncheck all reminders in a list."""
    script = f"""
    (() => {{
        const app = Application("Reminders");
        const listName = {json.dumps(list_name)};
        const lists = app.lists();
        for (let i = 0; i < lists.length; i++) {{
            if (lists[i].name() === listName) {{
                const rems = lists[i].reminders();
                let count = 0;
                for (let j = 0; j < rems.length; j++) {{
                    if (rems[j].completed()) {{
                        rems[j].completed = false;
                        count++;
                    }}
                }}
                return JSON.stringify({{ok: true, reset: count}});
            }}
        }}
        return JSON.stringify({{ok: false, error: "list not found"}});
    }})()
    """
    return _run_jxa(script)


def _macos_discover_lists():
    """Discover all Reminders lists available on this Mac."""
    script = """
    (() => {
        const app = Application("Reminders");
        const lists = app.lists();
        const result = [];
        for (let i = 0; i < lists.length; i++) {
            const l = lists[i];
            const info = { name: l.name(), id: l.id() };
            try { info.account = l.container().name(); } catch(e) { info.account = null; }
            try { info.color = l.properties().color; } catch(e) { info.color = null; }
            info.count = l.reminders().length;
            result.push(info);
        }
        return JSON.stringify(result);
    })()
    """
    return _run_jxa(script)


# ---- CalDAV (iCloud) for Raspberry Pi ----

def _caldav_connect():
    """Connect to iCloud CalDAV. Returns principal or None."""
    global _caldav_principal
    if _caldav_principal:
        return _caldav_principal
    if not _CALDAV_AVAILABLE:
        return None

    creds_path = os.path.join(DATA_DIR, "icloud_creds.json")
    if not os.path.exists(creds_path):
        return None

    try:
        with open(creds_path) as f:
            creds = json.load(f)
        client = caldav.DAVClient(
            url="https://caldav.icloud.com/",
            username=creds["apple_id"],
            password=creds["password"],
        )
        _caldav_principal = client.principal()
        logger.info("Connected to iCloud CalDAV")
        return _caldav_principal
    except Exception as e:
        logger.error("CalDAV connection failed: %s", e)
        return None


def _caldav_find_calendar(list_name):
    """Find a CalDAV calendar (reminders list) by name."""
    principal = _caldav_connect()
    if not principal:
        return None
    try:
        for cal in principal.calendars():
            if cal.name == list_name:
                # Verify it supports VTODO (reminders)
                return cal
    except Exception as e:
        logger.error("CalDAV calendar lookup failed: %s", e)
    return None


def _vtodo_to_item(todo):
    """Convert a CalDAV VTODO to our item dict."""
    vobj = todo.vobject_instance.vtodo
    uid = str(vobj.uid.value) if hasattr(vobj, "uid") else str(_uuid.uuid4())
    title = str(vobj.summary.value) if hasattr(vobj, "summary") else ""
    completed = hasattr(vobj, "completed")
    completed_date = None
    if completed and hasattr(vobj.completed, "value"):
        completed_date = vobj.completed.value.isoformat()
    created = None
    if hasattr(vobj, "created") and hasattr(vobj.created, "value"):
        created = vobj.created.value.isoformat()
    return {
        "id": uid,
        "title": title,
        "completed": completed,
        "completed_date": completed_date,
        "created": created,
    }


def _caldav_get_items(list_name):
    """Fetch all reminders from an iCloud CalDAV list."""
    cal = _caldav_find_calendar(list_name)
    if not cal:
        return None
    try:
        todos = cal.todos(include_completed=True)
        return [_vtodo_to_item(t) for t in todos]
    except Exception as e:
        logger.error("CalDAV fetch failed for %s: %s", list_name, e)
        return None


def _caldav_add_item(list_name, title):
    """Add a reminder via CalDAV."""
    cal = _caldav_find_calendar(list_name)
    if not cal:
        return None
    try:
        uid = str(_uuid.uuid4())
        vtodo = f"""BEGIN:VCALENDAR
BEGIN:VTODO
UID:{uid}
SUMMARY:{title}
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR"""
        cal.save_todo(vtodo)
        return {
            "id": uid,
            "title": title,
            "completed": False,
            "completed_date": None,
            "created": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("CalDAV add failed: %s", e)
        return None


def _caldav_set_completed(list_name, item_id, completed):
    """Set completed status on a CalDAV todo."""
    cal = _caldav_find_calendar(list_name)
    if not cal:
        return None
    try:
        for todo in cal.todos(include_completed=True):
            vobj = todo.vobject_instance.vtodo
            if hasattr(vobj, "uid") and str(vobj.uid.value) == item_id:
                if completed:
                    todo.complete()
                else:
                    todo.uncomplete()
                return {"ok": True}
    except Exception as e:
        logger.error("CalDAV complete/uncomplete failed: %s", e)
    return None


def _caldav_delete_item(list_name, item_id):
    """Delete a CalDAV todo."""
    cal = _caldav_find_calendar(list_name)
    if not cal:
        return None
    try:
        for todo in cal.todos(include_completed=True):
            vobj = todo.vobject_instance.vtodo
            if hasattr(vobj, "uid") and str(vobj.uid.value) == item_id:
                todo.delete()
                return {"ok": True}
    except Exception as e:
        logger.error("CalDAV delete failed: %s", e)
    return None


def _caldav_update_item(list_name, item_id, new_title):
    """Update a CalDAV todo's summary."""
    cal = _caldav_find_calendar(list_name)
    if not cal:
        return None
    try:
        for todo in cal.todos(include_completed=True):
            vobj = todo.vobject_instance.vtodo
            if hasattr(vobj, "uid") and str(vobj.uid.value) == item_id:
                vobj.summary.value = new_title
                todo.save()
                return {"ok": True}
    except Exception as e:
        logger.error("CalDAV update failed: %s", e)
    return None


def _caldav_reset_list(list_name):
    """Uncheck all completed items in a CalDAV list."""
    cal = _caldav_find_calendar(list_name)
    if not cal:
        return None
    try:
        count = 0
        for todo in cal.todos(include_completed=True):
            vobj = todo.vobject_instance.vtodo
            if hasattr(vobj, "completed"):
                todo.uncomplete()
                count += 1
        return {"ok": True, "reset": count}
    except Exception as e:
        logger.error("CalDAV reset failed: %s", e)
        return None


def _caldav_discover_lists():
    """Discover all Reminders-capable calendars via CalDAV."""
    principal = _caldav_connect()
    if not principal:
        return None
    try:
        result = []
        for cal in principal.calendars():
            # Check if calendar supports VTODO (reminders)
            supported = getattr(cal, "supported_components", None)
            if supported and "VTODO" not in supported:
                continue
            try:
                count = len(cal.todos(include_completed=True))
            except Exception:
                count = 0
            result.append({
                "name": cal.name,
                "id": str(cal.id) if hasattr(cal, "id") else cal.url,
                "account": "iCloud",
                "color": None,
                "count": count,
            })
        return result
    except Exception as e:
        logger.error("CalDAV discover failed: %s", e)
        return None


# Determine which remote backend to use
_USE_GOOGLE_TASKS = not _IS_MACOS and _GOOGLE_TASKS_AVAILABLE
_USE_CALDAV = not _IS_MACOS and _CALDAV_AVAILABLE and not _USE_GOOGLE_TASKS


# ---- Public API (dispatches to macOS native, Google Tasks, CalDAV, or local JSON) ----

def discover_lists():
    """Discover all available Reminders/Tasks lists from the system.
    Returns list of dicts: [{name, id, account, color, count}, ...]
    """
    if _IS_MACOS:
        result = _macos_discover_lists()
        if result is not None:
            return result
    if _USE_GOOGLE_TASKS:
        result = google_tasks.discover_lists()
        if result is not None:
            return result
    if _USE_CALDAV:
        result = _caldav_discover_lists()
        if result is not None:
            return result
    return []

def _remote_get_items(list_name):
    if _IS_MACOS:
        return _macos_get_items(list_name)
    if _USE_GOOGLE_TASKS:
        return google_tasks.get_items(list_name)
    if _USE_CALDAV:
        return _caldav_get_items(list_name)
    return None


def _remote_add_item(list_name, title):
    if _IS_MACOS:
        return _macos_add_item(list_name, title)
    if _USE_GOOGLE_TASKS:
        return google_tasks.add_item(list_name, title)
    if _USE_CALDAV:
        return _caldav_add_item(list_name, title)
    return None


def _remote_complete(list_name, item_id, completed):
    if _IS_MACOS:
        fn = _macos_complete_item if completed else _macos_uncomplete_item
        return fn(list_name, item_id)
    if _USE_GOOGLE_TASKS:
        return google_tasks.set_completed(list_name, item_id, completed)
    if _USE_CALDAV:
        return _caldav_set_completed(list_name, item_id, completed)
    return None


def _remote_delete(list_name, item_id):
    if _IS_MACOS:
        return _macos_delete_item(list_name, item_id)
    if _USE_GOOGLE_TASKS:
        return google_tasks.delete_item(list_name, item_id)
    if _USE_CALDAV:
        return _caldav_delete_item(list_name, item_id)
    return None


def _remote_update(list_name, item_id, new_title):
    if _IS_MACOS:
        return _macos_update_item(list_name, item_id, new_title)
    if _USE_GOOGLE_TASKS:
        return google_tasks.update_item(list_name, item_id, new_title)
    if _USE_CALDAV:
        return _caldav_update_item(list_name, item_id, new_title)
    return None


def _remote_reset(list_name):
    if _IS_MACOS:
        return _macos_reset_list(list_name)
    if _USE_GOOGLE_TASKS:
        return google_tasks.reset_list(list_name)
    if _USE_CALDAV:
        return _caldav_reset_list(list_name)
    return None


def get_items(list_name):
    """Get all items from a Reminders list."""
    items = _remote_get_items(list_name)
    if items is not None:
        return items
    return _load_local(list_name)


def add_item(list_name, title):
    """Add an item to a Reminders list."""
    item = _remote_add_item(list_name, title)
    if item is not None:
        return item

    # Local fallback
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
    return new_item


def complete_item(list_name, item_id):
    """Mark an item as completed."""
    if not item_id.startswith("local_"):
        result = _remote_complete(list_name, item_id, True)
        if result and result.get("ok"):
            return True

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
    if not item_id.startswith("local_"):
        result = _remote_complete(list_name, item_id, False)
        if result and result.get("ok"):
            return True

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
    if not item_id.startswith("local_"):
        result = _remote_delete(list_name, item_id)
        if result and result.get("ok"):
            return True

    items = _load_local(list_name)
    items = [i for i in items if i["id"] != item_id]
    _save_local(list_name, items)
    return True


def update_item(list_name, item_id, new_title):
    """Update an item's title."""
    if not item_id.startswith("local_"):
        result = _remote_update(list_name, item_id, new_title)
        if result and result.get("ok"):
            return True

    items = _load_local(list_name)
    for item in items:
        if item["id"] == item_id:
            item["title"] = new_title
            break
    _save_local(list_name, items)
    return True


def reset_daily_chores():
    """Reset daily chores if we haven't already today."""
    from config import get_reminders_lists
    dates = _load_reset_dates()
    today = date.today().isoformat()

    if dates.get("daily") != today:
        # Find lists that look like daily chores
        for lst in get_reminders_lists():
            if "daily" in lst["key"] or "morning" in lst["key"]:
                result = _remote_reset(lst["name"])
                if not result:
                    items = _load_local(lst["name"])
                    for item in items:
                        item["completed"] = False
                        item["completed_date"] = None
                    _save_local(lst["name"], items)

        dates["daily"] = today
        _save_reset_dates(dates)
        logger.info("Daily chores reset for %s", today)
        return True
    return False


def reset_weekly_chores():
    """Reset weekly chores on Sunday if not already done this week."""
    from config import get_reminders_lists
    dates = _load_reset_dates()
    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()

    if dates.get("weekly") != week_start:
        if today.weekday() == 6:  # Sunday
            for lst in get_reminders_lists():
                if "weekly" in lst["key"]:
                    result = _remote_reset(lst["name"])
                    if not result:
                        items = _load_local(lst["name"])
                        for item in items:
                            item["completed"] = False
                            item["completed_date"] = None
                        _save_local(lst["name"], items)

            dates["weekly"] = week_start
            _save_reset_dates(dates)
            logger.info("Weekly chores reset for week of %s", week_start)
            return True
    return False
