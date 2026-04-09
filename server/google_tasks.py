"""Google Tasks integration for Reminders lists on non-macOS (Raspberry Pi).

Uses the Google Tasks API to provide full CRUD for task lists, replacing
CalDAV/iCloud which can't see custom Reminders lists.

Requires the Google Tasks API enabled in the Cloud project and the
'tasks' scope authorized via setup_google_oauth.py.
"""
import logging
from datetime import datetime
from googleapiclient.discovery import build
from server.google_auth import get_credentials

logger = logging.getLogger(__name__)

_service = None


def _get_service():
    """Build (and cache) the Tasks API service."""
    global _service
    if _service:
        return _service
    creds = get_credentials()
    if not creds:
        return None
    _service = build("tasks", "v1", credentials=creds)
    return _service


def _task_to_item(task):
    """Convert a Google Tasks task to our standard item dict."""
    completed = task.get("status") == "completed"
    return {
        "id": task["id"],
        "title": task.get("title", ""),
        "completed": completed,
        "completed_date": task.get("completed"),
        "created": task.get("updated"),
    }


def _find_tasklist_id(list_name):
    """Find a task list ID by name (case-insensitive)."""
    service = _get_service()
    if not service:
        return None
    try:
        result = service.tasklists().list(maxResults=100).execute()
        for tl in result.get("items", []):
            if tl["title"].lower() == list_name.lower():
                return tl["id"]
    except Exception as e:
        logger.error("Tasks list lookup failed: %s", e)
    return None


def discover_lists():
    """Discover all Google Tasks lists.
    Returns list of dicts: [{name, id, account, color, count}, ...]
    """
    service = _get_service()
    if not service:
        return None
    try:
        result = service.tasklists().list(maxResults=100).execute()
        lists = []
        for tl in result.get("items", []):
            # Get task count
            try:
                tasks = service.tasks().list(
                    tasklist=tl["id"], showCompleted=True, maxResults=100
                ).execute()
                count = len(tasks.get("items", []))
            except Exception:
                count = 0
            lists.append({
                "name": tl["title"],
                "id": tl["id"],
                "account": "Google",
                "color": None,
                "count": count,
            })
        return lists
    except Exception as e:
        logger.error("Tasks discover failed: %s", e)
        return None


def get_items(list_name):
    """Fetch all tasks from a Google Tasks list."""
    service = _get_service()
    if not service:
        return None
    tl_id = _find_tasklist_id(list_name)
    if not tl_id:
        return None
    try:
        items = []
        page_token = None
        while True:
            result = service.tasks().list(
                tasklist=tl_id,
                showCompleted=True,
                showHidden=True,
                maxResults=100,
                pageToken=page_token,
            ).execute()
            for task in result.get("items", []):
                if task.get("title"):  # skip empty tasks
                    items.append(_task_to_item(task))
            page_token = result.get("nextPageToken")
            if not page_token:
                break
        return items
    except Exception as e:
        logger.error("Tasks fetch failed for %s: %s", list_name, e)
        return None


def add_item(list_name, title):
    """Add a task to a Google Tasks list."""
    service = _get_service()
    if not service:
        return None
    tl_id = _find_tasklist_id(list_name)
    if not tl_id:
        return None
    try:
        task = service.tasks().insert(
            tasklist=tl_id,
            body={"title": title, "status": "needsAction"},
        ).execute()
        return _task_to_item(task)
    except Exception as e:
        logger.error("Tasks add failed: %s", e)
        return None


def set_completed(list_name, item_id, completed):
    """Set completed status on a task."""
    service = _get_service()
    if not service:
        return None
    tl_id = _find_tasklist_id(list_name)
    if not tl_id:
        return None
    try:
        body = {"id": item_id}
        if completed:
            body["status"] = "completed"
        else:
            body["status"] = "needsAction"
            body["completed"] = None
        service.tasks().patch(
            tasklist=tl_id, task=item_id, body=body
        ).execute()
        return {"ok": True}
    except Exception as e:
        logger.error("Tasks complete/uncomplete failed: %s", e)
        return None


def delete_item(list_name, item_id):
    """Delete a task."""
    service = _get_service()
    if not service:
        return None
    tl_id = _find_tasklist_id(list_name)
    if not tl_id:
        return None
    try:
        service.tasks().delete(tasklist=tl_id, task=item_id).execute()
        return {"ok": True}
    except Exception as e:
        logger.error("Tasks delete failed: %s", e)
        return None


def update_item(list_name, item_id, new_title):
    """Update a task's title."""
    service = _get_service()
    if not service:
        return None
    tl_id = _find_tasklist_id(list_name)
    if not tl_id:
        return None
    try:
        service.tasks().patch(
            tasklist=tl_id, task=item_id, body={"title": new_title}
        ).execute()
        return {"ok": True}
    except Exception as e:
        logger.error("Tasks update failed: %s", e)
        return None


def reset_list(list_name):
    """Uncheck all completed tasks in a list."""
    service = _get_service()
    if not service:
        return None
    tl_id = _find_tasklist_id(list_name)
    if not tl_id:
        return None
    try:
        count = 0
        result = service.tasks().list(
            tasklist=tl_id, showCompleted=True, showHidden=True, maxResults=100
        ).execute()
        for task in result.get("items", []):
            if task.get("status") == "completed":
                service.tasks().patch(
                    tasklist=tl_id,
                    task=task["id"],
                    body={"status": "needsAction", "completed": None},
                ).execute()
                count += 1
        return {"ok": True, "reset": count}
    except Exception as e:
        logger.error("Tasks reset failed: %s", e)
        return None
