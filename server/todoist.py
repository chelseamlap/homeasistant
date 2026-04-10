"""Todoist integration for Reminders/Tasks lists.

Uses the Todoist API v1. Supports shared projects (lists),
full CRUD, and works from any device.

Setup:
  1. Go to https://todoist.com/app/settings/integrations/developer
  2. Copy your API token
  3. Save it to data/todoist_token.txt (just the token, nothing else)
"""
import json
import logging
import os
import uuid

import requests

logger = logging.getLogger(__name__)

_BASE = "https://api.todoist.com/api/v1"
_TOKEN = None

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _get_token():
    global _TOKEN
    if _TOKEN:
        return _TOKEN
    token_path = os.path.join(DATA_DIR, "todoist_token.txt")
    if not os.path.exists(token_path):
        logger.warning("No Todoist token found at %s", token_path)
        return None
    with open(token_path) as f:
        _TOKEN = f.read().strip()
    return _TOKEN


def _headers():
    token = _get_token()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


def _api_get(path, params=None):
    h = _headers()
    if not h:
        return None
    resp = requests.get(f"{_BASE}/{path}", headers=h, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    # v1 API wraps collections in {"results": [...]}
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


def _api_post(path, body=None):
    h = _headers()
    if not h:
        return None
    h["Content-Type"] = "application/json"
    h["X-Request-Id"] = str(uuid.uuid4())
    resp = requests.post(f"{_BASE}/{path}", headers=h, json=body, timeout=10)
    resp.raise_for_status()
    if resp.content:
        return resp.json()
    return {"ok": True}


def _api_delete(path):
    h = _headers()
    if not h:
        return None
    resp = requests.delete(f"{_BASE}/{path}", headers=h, timeout=10)
    resp.raise_for_status()
    return {"ok": True}


def _task_to_item(task):
    """Convert a Todoist task to our standard item dict."""
    return {
        "id": task["id"],
        "title": task.get("content", ""),
        "completed": task.get("is_completed", False),
        "completed_date": task.get("completed_at"),
        "created": task.get("created_at"),
    }


def _find_project_id(list_name):
    """Find a Todoist project ID by name (case-insensitive)."""
    try:
        projects = _api_get("projects")
        if not projects:
            return None
        for p in projects:
            if p["name"].lower() == list_name.lower():
                return p["id"]
    except Exception as e:
        logger.error("Todoist project lookup failed: %s", e)
    return None


def discover_lists():
    """Discover all Todoist projects.
    Returns list of dicts: [{name, id, account, color, count}, ...]
    """
    try:
        projects = _api_get("projects")
        if projects is None:
            return None
        result = []
        for p in projects:
            # Get task count per project
            try:
                tasks = _api_get("tasks", params={"project_id": p["id"]})
                count = len(tasks) if tasks else 0
            except Exception:
                count = 0
            result.append({
                "name": p["name"],
                "id": p["id"],
                "account": "Todoist",
                "color": p.get("color"),
                "count": count,
            })
        return result
    except Exception as e:
        logger.error("Todoist discover failed: %s", e)
        return None


def get_items(list_name):
    """Fetch all tasks from a Todoist project."""
    project_id = _find_project_id(list_name)
    if not project_id:
        return None
    try:
        # Get active tasks
        active = _api_get("tasks", params={"project_id": project_id}) or []
        items = [_task_to_item(t) for t in active]

        # Get completed tasks via v1 API
        try:
            h = _headers()
            resp = requests.get(
                f"{_BASE}/tasks/completed_by_completion_date",
                headers=h,
                params={"project_id": project_id, "limit": 100},
                timeout=10,
            )
            if resp.ok:
                completed_data = resp.json()
                for t in completed_data.get("results", completed_data.get("items", [])):
                    items.append({
                        "id": t["id"],
                        "title": t.get("content", ""),
                        "completed": True,
                        "completed_date": t.get("completed_at"),
                        "created": None,
                    })
        except Exception:
            pass  # completed tasks are optional

        return items
    except Exception as e:
        logger.error("Todoist fetch failed for %s: %s", list_name, e)
        return None


def add_item(list_name, title):
    """Add a task to a Todoist project."""
    project_id = _find_project_id(list_name)
    if not project_id:
        return None
    try:
        task = _api_post("tasks", {"content": title, "project_id": project_id})
        return _task_to_item(task)
    except Exception as e:
        logger.error("Todoist add failed: %s", e)
        return None


def set_completed(list_name, item_id, completed):
    """Complete or uncomplete a task."""
    try:
        if completed:
            _api_post(f"tasks/{item_id}/close")
        else:
            _api_post(f"tasks/{item_id}/reopen")
        return {"ok": True}
    except Exception as e:
        logger.error("Todoist complete/uncomplete failed: %s", e)
        return None


def delete_item(list_name, item_id):
    """Delete a task."""
    try:
        _api_delete(f"tasks/{item_id}")
        return {"ok": True}
    except Exception as e:
        logger.error("Todoist delete failed: %s", e)
        return None


def update_item(list_name, item_id, new_title):
    """Update a task's content."""
    try:
        h = _headers()
        if not h:
            return None
        h["Content-Type"] = "application/json"
        resp = requests.post(
            f"{_BASE}/tasks/{item_id}",
            headers=h,
            json={"content": new_title},
            timeout=10,
        )
        resp.raise_for_status()
        return {"ok": True}
    except Exception as e:
        logger.error("Todoist update failed: %s", e)
        return None


def reset_list(list_name):
    """Reopen all completed tasks in a project (uncomplete them)."""
    project_id = _find_project_id(list_name)
    if not project_id:
        return None
    try:
        # Get completed tasks via v1 API
        h = _headers()
        resp = requests.get(
            f"{_BASE}/tasks/completed_by_completion_date",
            headers=h,
            params={"project_id": project_id, "limit": 100},
            timeout=10,
        )
        count = 0
        if resp.ok:
            for t in resp.json().get("items", []):
                try:
                    _api_post(f"tasks/{t['id']}/reopen")
                    count += 1
                except Exception:
                    pass
        return {"ok": True, "reset": count}
    except Exception as e:
        logger.error("Todoist reset failed: %s", e)
        return None
