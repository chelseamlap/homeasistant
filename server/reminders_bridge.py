"""
Reminders/Tasks bridge with configurable backends:

1. apple_sync — Mac syncs Apple Reminders to Pi via JSON (bidirectional)
2. todoist   — Todoist REST API (shared lists, works anywhere)
3. google_tasks — Google Tasks API (same OAuth as Calendar/Sheets)
4. local     — Local JSON files (no sync, dashboard-only)

On macOS, always uses native JXA for direct Apple Reminders access,
regardless of the backend setting (the setting only affects the Pi).

The backend is configured via the 'lists_backend' key in data/settings.json.
Change it from the Home > Settings panel on the dashboard.
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

# Lazy-loaded backend modules
_todoist_mod = None
_google_tasks_mod = None


def _get_backend():
    """Read the configured backend from settings. Returns one of:
    'apple_sync', 'todoist', 'google_tasks', 'local'."""
    if _IS_MACOS:
        return "macos"
    settings_path = os.path.join(DATA_DIR, "settings.json")
    if os.path.exists(settings_path):
        with open(settings_path) as f:
            settings = json.load(f)
        return settings.get("lists_backend", "apple_sync")
    return "apple_sync"


def _get_todoist():
    global _todoist_mod
    if _todoist_mod is None:
        try:
            from server import todoist as _mod
            _todoist_mod = _mod
        except ImportError:
            logger.error("todoist module not available")
            return None
    return _todoist_mod


def _get_google_tasks():
    global _google_tasks_mod
    if _google_tasks_mod is None:
        try:
            from server import google_tasks as _mod
            _google_tasks_mod = _mod
        except ImportError:
            logger.error("google_tasks module not available")
            return None
    return _google_tasks_mod


# ---- Apple Sync backend (reads JSON exported by Mac, queues changes) ----

_SYNC_FILE = os.path.join(DATA_DIR, "reminders_sync.json")
_PENDING_FILE = os.path.join(DATA_DIR, "reminders_pending.json")


def _load_sync_data():
    """Load the sync export from the Mac."""
    if not os.path.exists(_SYNC_FILE):
        return None
    try:
        with open(_SYNC_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load sync file: %s", e)
        return None


def _queue_pending(change):
    """Add a change to the pending queue for the Mac to pick up."""
    pending = []
    if os.path.exists(_PENDING_FILE):
        try:
            with open(_PENDING_FILE) as f:
                pending = json.load(f)
        except (json.JSONDecodeError, OSError):
            pending = []
    change["timestamp"] = datetime.now().isoformat()
    pending.append(change)
    with open(_PENDING_FILE, "w") as f:
        json.dump(pending, f, indent=2)


def _sync_discover_lists():
    data = _load_sync_data()
    if not data:
        return None
    result = []
    for name, items in data.get("lists", {}).items():
        result.append({
            "name": name,
            "id": name,
            "account": "Apple (synced)",
            "color": None,
            "count": len(items),
        })
    return result


def _sync_get_items(list_name):
    data = _load_sync_data()
    if not data:
        return None
    lists = data.get("lists", {})
    # Case-insensitive lookup
    for name, items in lists.items():
        if name.lower() == list_name.lower():
            return items
    return None


def _sync_add_item(list_name, title):
    _queue_pending({"action": "add", "list": list_name, "title": title})
    # Also add locally so it shows immediately
    new_item = {
        "id": f"pending_{datetime.now().timestamp()}",
        "title": title,
        "completed": False,
        "completed_date": None,
        "created": datetime.now().isoformat(),
    }
    # Update sync file in place for immediate display
    data = _load_sync_data()
    if data:
        for name in data.get("lists", {}):
            if name.lower() == list_name.lower():
                data["lists"][name].append(new_item)
                with open(_SYNC_FILE, "w") as f:
                    json.dump(data, f, indent=2)
                break
    return new_item


def _sync_complete(list_name, item_id, completed):
    action = "complete" if completed else "uncomplete"
    _queue_pending({"action": action, "list": list_name, "item_id": item_id})
    # Update sync file for immediate display
    data = _load_sync_data()
    if data:
        for name, items in data.get("lists", {}).items():
            if name.lower() == list_name.lower():
                for item in items:
                    if item["id"] == item_id:
                        item["completed"] = completed
                        item["completed_date"] = datetime.now().isoformat() if completed else None
                        break
                with open(_SYNC_FILE, "w") as f:
                    json.dump(data, f, indent=2)
                break
    return {"ok": True}


def _sync_delete(list_name, item_id):
    _queue_pending({"action": "delete", "list": list_name, "item_id": item_id})
    data = _load_sync_data()
    if data:
        for name, items in data.get("lists", {}).items():
            if name.lower() == list_name.lower():
                data["lists"][name] = [i for i in items if i["id"] != item_id]
                with open(_SYNC_FILE, "w") as f:
                    json.dump(data, f, indent=2)
                break
    return {"ok": True}


def _sync_update(list_name, item_id, new_title):
    _queue_pending({"action": "update", "list": list_name, "item_id": item_id, "title": new_title})
    data = _load_sync_data()
    if data:
        for name, items in data.get("lists", {}).items():
            if name.lower() == list_name.lower():
                for item in items:
                    if item["id"] == item_id:
                        item["title"] = new_title
                        break
                with open(_SYNC_FILE, "w") as f:
                    json.dump(data, f, indent=2)
                break
    return {"ok": True}


def _sync_reset(list_name):
    _queue_pending({"action": "reset", "list": list_name})
    count = 0
    data = _load_sync_data()
    if data:
        for name, items in data.get("lists", {}).items():
            if name.lower() == list_name.lower():
                for item in items:
                    if item.get("completed"):
                        item["completed"] = False
                        item["completed_date"] = None
                        count += 1
                with open(_SYNC_FILE, "w") as f:
                    json.dump(data, f, indent=2)
                break
    return {"ok": True, "reset": count}


# CalDAV support (legacy)
_CALDAV_AVAILABLE = False
_caldav_principal = None

try:
    import caldav
    _CALDAV_AVAILABLE = True
except ImportError:
    pass


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


# ---- Public API (dispatches based on configured backend) ----

def discover_lists():
    """Discover all available lists from the active backend.
    Returns list of dicts: [{name, id, account, color, count}, ...]
    """
    backend = _get_backend()
    if backend == "macos":
        result = _macos_discover_lists()
        if result is not None:
            return result
    elif backend == "apple_sync":
        result = _sync_discover_lists()
        if result is not None:
            return result
    elif backend == "todoist":
        mod = _get_todoist()
        if mod:
            result = mod.discover_lists()
            if result is not None:
                return result
    elif backend == "google_tasks":
        mod = _get_google_tasks()
        if mod:
            result = mod.discover_lists()
            if result is not None:
                return result
    return []


def _remote_get_items(list_name):
    backend = _get_backend()
    if backend == "macos":
        return _macos_get_items(list_name)
    elif backend == "apple_sync":
        return _sync_get_items(list_name)
    elif backend == "todoist":
        mod = _get_todoist()
        return mod.get_items(list_name) if mod else None
    elif backend == "google_tasks":
        mod = _get_google_tasks()
        return mod.get_items(list_name) if mod else None
    return None


def _remote_add_item(list_name, title):
    backend = _get_backend()
    if backend == "macos":
        return _macos_add_item(list_name, title)
    elif backend == "apple_sync":
        return _sync_add_item(list_name, title)
    elif backend == "todoist":
        mod = _get_todoist()
        return mod.add_item(list_name, title) if mod else None
    elif backend == "google_tasks":
        mod = _get_google_tasks()
        return mod.add_item(list_name, title) if mod else None
    return None


def _remote_complete(list_name, item_id, completed):
    backend = _get_backend()
    if backend == "macos":
        fn = _macos_complete_item if completed else _macos_uncomplete_item
        return fn(list_name, item_id)
    elif backend == "apple_sync":
        return _sync_complete(list_name, item_id, completed)
    elif backend == "todoist":
        mod = _get_todoist()
        return mod.set_completed(list_name, item_id, completed) if mod else None
    elif backend == "google_tasks":
        mod = _get_google_tasks()
        return mod.set_completed(list_name, item_id, completed) if mod else None
    return None


def _remote_delete(list_name, item_id):
    backend = _get_backend()
    if backend == "macos":
        return _macos_delete_item(list_name, item_id)
    elif backend == "apple_sync":
        return _sync_delete(list_name, item_id)
    elif backend == "todoist":
        mod = _get_todoist()
        return mod.delete_item(list_name, item_id) if mod else None
    elif backend == "google_tasks":
        mod = _get_google_tasks()
        return mod.delete_item(list_name, item_id) if mod else None
    return None


def _remote_update(list_name, item_id, new_title):
    backend = _get_backend()
    if backend == "macos":
        return _macos_update_item(list_name, item_id, new_title)
    elif backend == "apple_sync":
        return _sync_update(list_name, item_id, new_title)
    elif backend == "todoist":
        mod = _get_todoist()
        return mod.update_item(list_name, item_id, new_title) if mod else None
    elif backend == "google_tasks":
        mod = _get_google_tasks()
        return mod.update_item(list_name, item_id, new_title) if mod else None
    return None


def _remote_reset(list_name):
    backend = _get_backend()
    if backend == "macos":
        return _macos_reset_list(list_name)
    elif backend == "apple_sync":
        return _sync_reset(list_name)
    elif backend == "todoist":
        mod = _get_todoist()
        return mod.reset_list(list_name) if mod else None
    elif backend == "google_tasks":
        mod = _get_google_tasks()
        return mod.reset_list(list_name) if mod else None
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
