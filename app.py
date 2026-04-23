#!/usr/bin/env python3
"""Family Home Dashboard — Flask server."""
import os
import json
import glob as globmod
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, render_template, jsonify, request, send_from_directory

import config


def _now():
    """Get current time in the user's configured timezone."""
    settings = config.load_settings()
    tz = ZoneInfo(settings.get("timezone", config.DEFAULT_TIMEZONE))
    return datetime.now(tz)
from config import get_reminders_lists, get_reminders_list_name
from server.weather import fetch_weather
from server.reminders_bridge import (
    get_items, add_item, complete_item, uncomplete_item,
    delete_item, update_item, reset_daily_chores, reset_weekly_chores,
    discover_lists,
)
from server.google_calendar import (
    get_today_events, get_week_events, get_upcoming_events,
    get_month_events, discover_calendars,
)
from server.google_sheets import get_budget_data, is_sheets_connected
from server.google_auth import is_authenticated

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# ---- Startup resets ----
reset_daily_chores()
reset_weekly_chores()


# ============================================================
# Pages
# ============================================================

@app.route("/")
def index():
    settings = config.load_settings()
    return render_template(
        "index.html",
        refresh_interval=config.REFRESH_INTERVAL_MS,
        location_name=settings["location_name"],
        google_connected=is_authenticated(),
        configured_timezone=settings.get("timezone", config.DEFAULT_TIMEZONE),
    )


# ============================================================
# Weather API
# ============================================================

@app.route("/api/weather")
def api_weather():
    settings = config.load_settings()
    data = fetch_weather(settings["latitude"], settings["longitude"])
    return jsonify(data)


# ============================================================
# Reminders API
# ============================================================

@app.route("/api/reminders/config")
def api_reminders_config():
    """Return the configured reminders lists so the frontend can render dynamically."""
    return jsonify(get_reminders_lists())


@app.route("/api/reminders/discover")
def api_reminders_discover():
    """Discover all available Reminders lists from Apple/iCloud."""
    available = discover_lists()
    configured = {l["name"] for l in get_reminders_lists()}
    for item in available:
        item["enabled"] = item["name"] in configured
    return jsonify(available)


@app.route("/api/reminders/config", methods=["POST"])
def api_reminders_save_config():
    """Save which reminders lists to display."""
    data = request.get_json()
    lists = data.get("lists", [])
    settings = config.load_settings()
    settings["reminders_lists"] = lists
    config.save_settings(settings)
    return jsonify({"ok": True})


@app.route("/api/reminders/<list_key>")
def api_get_reminders(list_key):
    list_name = get_reminders_list_name(list_key)
    items = get_items(list_name)
    return jsonify({"list": list_name, "items": items})


@app.route("/api/reminders/<list_key>/add", methods=["POST"])
def api_add_reminder(list_key):
    list_name = get_reminders_list_name(list_key)
    data = request.get_json()
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Title required"}), 400
    item = add_item(list_name, title)
    return jsonify(item)


@app.route("/api/reminders/<list_key>/complete", methods=["POST"])
def api_complete_reminder(list_key):
    list_name = get_reminders_list_name(list_key)
    data = request.get_json()
    item_id = data.get("id")
    complete_item(list_name, item_id)
    return jsonify({"ok": True})


@app.route("/api/reminders/<list_key>/uncomplete", methods=["POST"])
def api_uncomplete_reminder(list_key):
    list_name = get_reminders_list_name(list_key)
    data = request.get_json()
    item_id = data.get("id")
    uncomplete_item(list_name, item_id)
    return jsonify({"ok": True})


@app.route("/api/reminders/<list_key>/delete", methods=["POST"])
def api_delete_reminder(list_key):
    list_name = get_reminders_list_name(list_key)
    data = request.get_json()
    item_id = data.get("id")
    delete_item(list_name, item_id)
    return jsonify({"ok": True})


@app.route("/api/reminders/<list_key>/update", methods=["POST"])
def api_update_reminder(list_key):
    list_name = get_reminders_list_name(list_key)
    data = request.get_json()
    item_id = data.get("id")
    new_title = data.get("title", "").strip()
    if not new_title:
        return jsonify({"error": "Title required"}), 400
    update_item(list_name, item_id, new_title)
    return jsonify({"ok": True})


@app.route("/api/reminders/reset", methods=["POST"])
def api_reset_reminders():
    d = reset_daily_chores()
    w = reset_weekly_chores()
    return jsonify({"daily_reset": d, "weekly_reset": w})


# ============================================================
# Calendar API
# ============================================================

@app.route("/api/calendar/today")
def api_calendar_today():
    events = get_today_events()
    return jsonify(events)


@app.route("/api/calendar/week")
def api_calendar_week():
    events = get_week_events()
    return jsonify(events)


@app.route("/api/calendar/upcoming")
def api_calendar_upcoming():
    days = request.args.get("days", 30, type=int)
    events = get_upcoming_events(days)
    return jsonify(events)


@app.route("/api/calendar/discover")
def api_calendar_discover():
    """Discover all calendars available to the Google account."""
    calendars = discover_calendars()
    settings = config.load_settings()
    selected_ids = settings.get("calendar_ids", [])
    for cal in calendars:
        cal["enabled"] = cal["id"] in selected_ids or (not selected_ids and cal["primary"])
    return jsonify(calendars)


@app.route("/api/calendar/config", methods=["POST"])
def api_calendar_save_config():
    """Save which calendars to include."""
    data = request.get_json()
    calendar_ids = data.get("calendar_ids", [])
    settings = config.load_settings()
    settings["calendar_ids"] = calendar_ids
    config.save_settings(settings)
    return jsonify({"ok": True})


@app.route("/api/calendar/month/<int:year>/<int:month>")
def api_calendar_month(year, month):
    events = get_month_events(year, month)
    return jsonify(events)


# ============================================================
# Money / Budget API
# ============================================================

@app.route("/api/budget")
def api_budget():
    settings = config.load_settings()
    sheet_id = settings.get("budget_sheet_id", "")
    data = get_budget_data(sheet_id)
    return jsonify(data)


# ============================================================
# Settings API
# ============================================================

@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    settings = config.load_settings()
    settings["google_connected"] = is_authenticated()
    settings["sheets_connected"] = is_sheets_connected()
    settings["kiosk_paused"] = os.path.exists("/tmp/home-launchpad-kiosk-paused")
    return jsonify(settings)


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    data = request.get_json()
    settings = config.load_settings()
    for key in ["latitude", "longitude", "location_name", "budget_sheet_id", "reminders_lists", "theme", "calendar_ids", "lists_backend", "weekend_sat", "weekend_sun", "timezone"]:
        if key in data:
            settings[key] = data[key]
    config.save_settings(settings)
    return jsonify({"ok": True})


@app.route("/api/settings/background", methods=["POST"])
def api_upload_background():
    """Upload a background image.

    Resizes to max 1920x1920 (preserving aspect ratio) and re-encodes as
    JPEG at quality 85 so the kiosk browser — which runs with software
    rasterization on the Pi — never has to decode a multi-megapixel image.
    A full-res phone photo will hang chromium's compositor thread and
    crash-loop the renderer.
    """
    from PIL import Image, ImageOps

    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400
    f = request.files["image"]
    if not f.filename:
        return jsonify({"error": "No file selected"}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    if ext and ext not in allowed:
        return jsonify({"error": "Unsupported image format"}), 400

    # Remove old backgrounds (any extension)
    for old in globmod.glob(os.path.join(config.DATA_DIR, "background.*")):
        os.remove(old)

    try:
        img = Image.open(f.stream)
        img = ImageOps.exif_transpose(img)  # respect EXIF orientation
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.thumbnail((1920, 1920), Image.LANCZOS)
        filename = "background.jpg"
        out_path = os.path.join(config.DATA_DIR, filename)
        img.save(out_path, "JPEG", quality=85, optimize=True)
    except Exception as e:
        return jsonify({"error": f"Failed to process image: {e}"}), 400

    url = f"/data/{filename}"
    settings = config.load_settings()
    settings["background_url"] = url
    config.save_settings(settings)
    return jsonify({"ok": True, "url": url})


@app.route("/api/settings/background/remove", methods=["POST"])
def api_remove_background():
    """Remove the background image."""
    for old in globmod.glob(os.path.join(config.DATA_DIR, "background.*")):
        os.remove(old)
    settings = config.load_settings()
    settings.pop("background_url", None)
    config.save_settings(settings)
    return jsonify({"ok": True})


@app.route("/data/<path:filename>")
def serve_data_file(filename):
    """Serve files from the data directory (background images)."""
    # Only allow image files to be served
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed:
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(config.DATA_DIR, filename)


@app.route("/api/exit-kiosk", methods=["POST"])
def api_exit_kiosk():
    """Kill Chromium to exit kiosk mode, giving access to the desktop."""
    import subprocess as sp
    # Write a pause flag so the autostart script won't relaunch Chrome.
    # The flag lives in /tmp so it auto-clears on reboot.
    try:
        with open("/tmp/home-launchpad-kiosk-paused", "w") as f:
            f.write("paused")
    except OSError:
        pass
    sp.Popen(["pkill", "-f", "chromium"])
    return jsonify({"ok": True})


@app.route("/api/resume-kiosk", methods=["POST"])
def api_resume_kiosk():
    """Remove the kiosk pause flag so autostart will work on next login/reboot."""
    try:
        os.remove("/tmp/home-launchpad-kiosk-paused")
    except FileNotFoundError:
        pass
    return jsonify({"ok": True})


# ============================================================
# Message Board API
# ============================================================

_MESSAGES_FILE = os.path.join(config.DATA_DIR, "messages.json")


def _load_messages():
    """Load messages, auto-clearing any older than 24 hours."""
    if not os.path.exists(_MESSAGES_FILE):
        return []
    with open(_MESSAGES_FILE) as f:
        msgs = json.load(f)
    cutoff = (_now() - timedelta(hours=24)).isoformat()
    fresh = [m for m in msgs if m.get("ts", "") > cutoff]
    if len(fresh) != len(msgs):
        _save_messages(fresh)
    return fresh


def _save_messages(msgs):
    with open(_MESSAGES_FILE, "w") as f:
        json.dump(msgs, f, indent=2)


@app.route("/api/messages")
def api_get_messages():
    return jsonify(_load_messages())


@app.route("/api/messages", methods=["POST"])
def api_add_message():
    data = request.get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Text required"}), 400
    msgs = _load_messages()
    msgs.append({"id": str(__import__('uuid').uuid4()), "text": text, "ts": _now().isoformat()})
    _save_messages(msgs)
    return jsonify({"ok": True})


@app.route("/api/messages/<msg_id>", methods=["DELETE"])
def api_delete_message(msg_id):
    msgs = _load_messages()
    msgs = [m for m in msgs if m["id"] != msg_id]
    _save_messages(msgs)
    return jsonify({"ok": True})


@app.route("/api/health")
def api_health():
    """Diagnostic endpoint — visit localhost:5000/api/health from Pi browser."""
    import requests as req
    checks = {}

    # 1. Internet connectivity
    try:
        r = req.get("https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0&current=temperature_2m", timeout=5)
        r.raise_for_status()
        checks["internet"] = {"ok": True}
    except Exception as e:
        checks["internet"] = {"ok": False, "error": str(e)}

    # 2. Google OAuth token
    from server.google_auth import get_credentials, TOKEN_FILE
    creds = get_credentials()
    if creds and creds.valid:
        checks["google_auth"] = {"ok": True, "expiry": str(creds.expiry) if creds.expiry else "unknown"}
    elif os.path.exists(TOKEN_FILE):
        checks["google_auth"] = {"ok": False, "error": "Token exists but is invalid or expired — re-run setup_google_oauth.py"}
    else:
        checks["google_auth"] = {"ok": False, "error": "No token file — run setup_google_oauth.py"}

    # 3. Weather
    settings = config.load_settings()
    w = fetch_weather(settings["latitude"], settings["longitude"])
    if w.get("error"):
        checks["weather"] = {"ok": False, "error": w["error"]}
    else:
        checks["weather"] = {"ok": True, "temp": w.get("current", {}).get("temp")}

    # 4. Google Calendar
    try:
        events = get_today_events()
        checks["calendar"] = {"ok": True, "event_count": len(events) if events else 0}
    except Exception as e:
        checks["calendar"] = {"ok": False, "error": str(e)}

    # 5. Google Sheets (service account)
    checks["sheets"] = {"ok": is_sheets_connected(), "auth": "service_account"}
    if not is_sheets_connected():
        checks["sheets"]["error"] = "No service account key at data/google_service_account.json"

    # 6. Settings summary
    checks["settings"] = {
        "location": settings.get("location_name"),
        "lat": settings.get("latitude"),
        "lon": settings.get("longitude"),
        "lists_backend": settings.get("lists_backend", "apple_sync"),
        "timezone": settings.get("timezone", config.DEFAULT_TIMEZONE),
    }

    all_ok = all(checks.get(k, {}).get("ok", False) for k in ["internet", "google_auth", "weather", "calendar"])
    return jsonify({"status": "healthy" if all_ok else "degraded", "checks": checks})


@app.route("/api/refresh", methods=["POST"])
def api_refresh_all():
    """Manual refresh trigger — resets chores and returns status."""
    reset_daily_chores()
    reset_weekly_chores()
    # Clear calendar color cache so new calendars pick up their colors
    from server.google_calendar import _cal_color_cache
    import server.google_calendar as gcal
    gcal._cal_color_cache = None
    return jsonify({"ok": True, "timestamp": _now().isoformat()})


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":
    import threading
    import webbrowser

    port = config.PORT
    logger.info(f"Starting The Home Launchpad on port {port}")

    # Auto-open the dashboard in a browser when run interactively on a dev
    # machine. Skip this under systemd (the Pi kiosk has labwc autostart
    # spawn chromium itself) — otherwise every service restart launches a
    # stray chromium window that fights with the kiosk.
    running_under_systemd = bool(os.environ.get("INVOCATION_ID"))

    if not running_under_systemd:
        import subprocess
        import platform

        def open_app_mode():
            url = f"http://localhost:{port}"
            system = platform.system()
            try:
                if system == "Darwin":
                    # --new-window ensures app mode even if Chrome is already running
                    subprocess.Popen([
                        "open", "-na", "Google Chrome", "--args",
                        f"--app={url}", "--new-window"
                    ])
                elif system == "Linux":
                    import shutil
                    chromium = shutil.which("chromium-browser") or shutil.which("chromium") or "chromium"
                    subprocess.Popen([chromium, f"--app={url}", "--start-maximized", "--password-store=basic"])
                else:
                    webbrowser.open(url)
            except FileNotFoundError:
                webbrowser.open(url)

        threading.Timer(1.5, open_app_mode).start()

    app.run(host="0.0.0.0", port=port, debug=False)
