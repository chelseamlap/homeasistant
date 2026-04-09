#!/usr/bin/env python3
"""
Mac → Pi Reminders sync.

Runs on your Mac to:
1. Pull pending changes from the Pi (adds/completes/deletes made on the dashboard)
2. Apply those changes to Apple Reminders via JXA
3. Export all Reminders lists to JSON
4. Push the export to the Pi

Usage:
  python3 sync/reminders_sync.py                      # uses config from sync/sync_config.json
  python3 sync/reminders_sync.py --export-only         # just export locally (no Pi communication)

Config file (sync/sync_config.json):
  {
    "pi_host": "your-username@your-pi-ip",
    "pi_dashboard_path": "/home/your-username/git-repo/home-launchpad",
    "ssh_key": "~/.ssh/id_ed25519"          (optional)
  }
"""
import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_FILE = os.path.join(SCRIPT_DIR, "sync_config.json")
LOCAL_EXPORT = os.path.join(PROJECT_DIR, "data", "reminders_sync.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [sync] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE) as f:
        return json.load(f)


def ssh_cmd(config):
    """Build base SSH command list from config."""
    cmd = ["ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new"]
    if config.get("ssh_key"):
        cmd += ["-i", os.path.expanduser(config["ssh_key"])]
    cmd.append(config["pi_host"])
    return cmd


def scp_cmd(config, src, dst):
    """Build SCP command."""
    cmd = ["scp", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new", "-q"]
    if config.get("ssh_key"):
        cmd += ["-i", os.path.expanduser(config["ssh_key"])]
    cmd += [src, dst]
    return cmd


# ---- Pull pending changes from Pi ----

def pull_pending(config):
    """Download and clear pending changes from the Pi."""
    remote_path = f"{config['pi_dashboard_path']}/data/reminders_pending.json"
    local_tmp = os.path.join(SCRIPT_DIR, ".pending_tmp.json")

    # Download
    src = f"{config['pi_host']}:{remote_path}"
    result = subprocess.run(scp_cmd(config, src, local_tmp),
                            capture_output=True, text=True)
    if result.returncode != 0:
        log.info("No pending changes on Pi")
        return []

    with open(local_tmp) as f:
        changes = json.load(f)

    if changes:
        # Clear the pending file on Pi
        subprocess.run(
            ssh_cmd(config) + [f"echo '[]' > {remote_path}"],
            capture_output=True,
        )
        log.info("Pulled %d pending changes from Pi", len(changes))

    os.remove(local_tmp)
    return changes


# ---- Apply changes to Apple Reminders via JXA ----

def apply_change(change):
    """Apply a single pending change to Apple Reminders."""
    action = change.get("action")
    list_name = change.get("list")

    if action == "add":
        title = change.get("title", "")
        script = f"""(() => {{
            const app = Application("Reminders");
            const lists = app.lists();
            for (let i = 0; i < lists.length; i++) {{
                if (lists[i].name() === {json.dumps(list_name)}) {{
                    const rem = app.Reminder({{name: {json.dumps(title)}}});
                    lists[i].reminders.push(rem);
                    return JSON.stringify({{ok: true}});
                }}
            }}
            return JSON.stringify({{ok: false, error: "list not found"}});
        }})()"""

    elif action == "complete":
        item_id = change.get("item_id")
        script = f"""(() => {{
            const app = Application("Reminders");
            const lists = app.lists();
            for (let i = 0; i < lists.length; i++) {{
                if (lists[i].name() === {json.dumps(list_name)}) {{
                    const rems = lists[i].reminders();
                    for (let j = 0; j < rems.length; j++) {{
                        if (rems[j].id() === {json.dumps(item_id)}) {{
                            rems[j].completed = true;
                            return JSON.stringify({{ok: true}});
                        }}
                    }}
                }}
            }}
            return JSON.stringify({{ok: false}});
        }})()"""

    elif action == "uncomplete":
        item_id = change.get("item_id")
        script = f"""(() => {{
            const app = Application("Reminders");
            const lists = app.lists();
            for (let i = 0; i < lists.length; i++) {{
                if (lists[i].name() === {json.dumps(list_name)}) {{
                    const rems = lists[i].reminders();
                    for (let j = 0; j < rems.length; j++) {{
                        if (rems[j].id() === {json.dumps(item_id)}) {{
                            rems[j].completed = false;
                            return JSON.stringify({{ok: true}});
                        }}
                    }}
                }}
            }}
            return JSON.stringify({{ok: false}});
        }})()"""

    elif action == "delete":
        item_id = change.get("item_id")
        script = f"""(() => {{
            const app = Application("Reminders");
            const lists = app.lists();
            for (let i = 0; i < lists.length; i++) {{
                if (lists[i].name() === {json.dumps(list_name)}) {{
                    const rems = lists[i].reminders();
                    for (let j = 0; j < rems.length; j++) {{
                        if (rems[j].id() === {json.dumps(item_id)}) {{
                            app.delete(rems[j]);
                            return JSON.stringify({{ok: true}});
                        }}
                    }}
                }}
            }}
            return JSON.stringify({{ok: false}});
        }})()"""

    elif action == "update":
        item_id = change.get("item_id")
        new_title = change.get("title", "")
        script = f"""(() => {{
            const app = Application("Reminders");
            const lists = app.lists();
            for (let i = 0; i < lists.length; i++) {{
                if (lists[i].name() === {json.dumps(list_name)}) {{
                    const rems = lists[i].reminders();
                    for (let j = 0; j < rems.length; j++) {{
                        if (rems[j].id() === {json.dumps(item_id)}) {{
                            rems[j].name = {json.dumps(new_title)};
                            return JSON.stringify({{ok: true}});
                        }}
                    }}
                }}
            }}
            return JSON.stringify({{ok: false}});
        }})()"""

    elif action == "reset":
        script = f"""(() => {{
            const app = Application("Reminders");
            const lists = app.lists();
            for (let i = 0; i < lists.length; i++) {{
                if (lists[i].name() === {json.dumps(list_name)}) {{
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
            return JSON.stringify({{ok: false}});
        }})()"""
    else:
        log.warning("Unknown action: %s", action)
        return

    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            log.info("Applied %s on '%s'", action, list_name)
        else:
            log.error("JXA error for %s: %s", action, result.stderr.strip())
    except Exception as e:
        log.error("Failed to apply %s: %s", action, e)


# ---- Export all Reminders ----

def export_reminders():
    """Export all Apple Reminders lists to JSON."""
    script = """(() => {
        const app = Application("Reminders");
        const lists = app.lists();
        const data = {};
        for (let i = 0; i < lists.length; i++) {
            const l = lists[i];
            const name = l.name();
            const rems = l.reminders();
            const items = [];
            for (let j = 0; j < rems.length; j++) {
                const r = rems[j];
                items.push({
                    id: r.id(),
                    title: r.name(),
                    completed: r.completed(),
                    completed_date: r.completionDate() ? r.completionDate().toISOString() : null,
                    created: r.creationDate() ? r.creationDate().toISOString() : null,
                });
            }
            data[name] = items;
        }
        return JSON.stringify(data);
    })()"""

    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", script],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        log.error("Export failed: %s", result.stderr.strip())
        return None

    try:
        lists_data = json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        log.error("Export parse error: %s", e)
        return None

    export = {
        "synced_at": datetime.now().isoformat(),
        "lists": lists_data,
    }

    os.makedirs(os.path.dirname(LOCAL_EXPORT), exist_ok=True)
    with open(LOCAL_EXPORT, "w") as f:
        json.dump(export, f, indent=2)

    total_items = sum(len(v) for v in lists_data.values())
    log.info("Exported %d lists, %d total items", len(lists_data), total_items)
    return export


# ---- Push export to Pi ----

def push_to_pi(config):
    """SCP the export file to the Pi."""
    remote_path = f"{config['pi_host']}:{config['pi_dashboard_path']}/data/reminders_sync.json"
    result = subprocess.run(scp_cmd(config, LOCAL_EXPORT, remote_path),
                            capture_output=True, text=True)
    if result.returncode == 0:
        log.info("Pushed export to Pi")
    else:
        log.error("Push failed: %s", result.stderr.strip())


# ---- Main ----

def main():
    parser = argparse.ArgumentParser(description="Sync Apple Reminders to Pi")
    parser.add_argument("--export-only", action="store_true",
                        help="Export locally without pushing to Pi")
    args = parser.parse_args()

    config = load_config()

    if not args.export_only:
        if not config:
            log.error("No sync/sync_config.json found. Create it with:")
            log.error('  {"pi_host": "user@pi-ip", "pi_dashboard_path": "/home/user/git-repo/home-launchpad"}')
            sys.exit(1)

        # Step 1: Pull and apply pending changes from Pi
        changes = pull_pending(config)
        for change in changes:
            apply_change(change)

    # Step 2: Export all Reminders
    export = export_reminders()
    if not export:
        sys.exit(1)

    # Step 3: Push to Pi
    if not args.export_only and config:
        push_to_pi(config)

    log.info("Sync complete")


if __name__ == "__main__":
    main()
