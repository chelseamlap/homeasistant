"""Google Calendar API integration."""
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from googleapiclient.discovery import build
from server.google_auth import get_credentials
import config

logger = logging.getLogger(__name__)


def _get_tz():
    """Get the configured timezone."""
    settings = config.load_settings()
    return ZoneInfo(settings.get("timezone", config.DEFAULT_TIMEZONE))


def _now():
    """Get current time in the user's configured timezone."""
    return datetime.now(_get_tz())


def _local_rfc3339(dt):
    """Convert a datetime to RFC 3339 in the user's timezone for Google Calendar API."""
    tz = _get_tz()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz).isoformat()


def _get_service():
    """Build the Calendar API service."""
    creds = get_credentials()
    if not creds:
        return None
    return build("calendar", "v3", credentials=creds)


def _get_calendar_ids():
    """Get configured calendar IDs. Returns list of calendar IDs to query."""
    settings = config.load_settings()
    ids = settings.get("calendar_ids", [])
    return ids if ids else ["primary"]


def discover_calendars():
    """Discover all calendars available to the Google account."""
    service = _get_service()
    if not service:
        return []
    try:
        result = service.calendarList().list().execute()
        calendars = []
        for cal in result.get("items", []):
            calendars.append({
                "id": cal["id"],
                "name": cal.get("summary", cal["id"]),
                "color": cal.get("backgroundColor", ""),
                "primary": cal.get("primary", False),
                "access_role": cal.get("accessRole", ""),
            })
        return calendars
    except Exception as e:
        logger.error(f"Calendar discovery failed: {e}")
        return []


def _get_calendar_colors():
    """Build a map of calendar ID → background color from the API."""
    service = _get_service()
    if not service:
        return {}
    try:
        result = service.calendarList().list().execute()
        return {
            cal["id"]: cal.get("backgroundColor", "")
            for cal in result.get("items", [])
        }
    except Exception:
        return {}


# Cache calendar colors for the lifetime of the process
_cal_color_cache = None


def _get_color_map():
    global _cal_color_cache
    if _cal_color_cache is None:
        _cal_color_cache = _get_calendar_colors()
    return _cal_color_cache


def _fetch_events_multi(calendar_ids, time_min, time_max, max_per_cal=100):
    """Fetch events from multiple calendars and merge them."""
    service = _get_service()
    if not service:
        return []

    color_map = _get_color_map()
    all_events = []
    for cal_id in calendar_ids:
        try:
            result = service.events().list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=max_per_cal,
            ).execute()
            cal_color = color_map.get(cal_id, "")
            for item in result.get("items", []):
                ev = _parse_event(item)
                ev["calendar_color"] = cal_color
                all_events.append(ev)
        except Exception as e:
            logger.error(f"Calendar fetch failed for {cal_id}: {e}")

    # Sort merged events by start time
    all_events.sort(key=lambda e: e["start"])
    return all_events


def _has_guests(event):
    """Check if an event has guests/visitors."""
    attendees = event.get("attendees", [])
    if len(attendees) > 1:  # More than just the organizer
        return True
    summary = (event.get("summary", "") + " " + event.get("description", "")).lower()
    visitor_keywords = ["visit", "visiting", "arriving", "guest", "visitor", "coming over"]
    return any(kw in summary for kw in visitor_keywords)


def _parse_event(event):
    """Parse a Google Calendar event into our format."""
    start = event.get("start", {})
    end = event.get("end", {})
    tz = _get_tz()

    # Handle all-day vs timed events
    if "dateTime" in start:
        # Convert to local timezone so times/dates display correctly
        start_dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
        end_dt = datetime.fromisoformat(end["dateTime"]).astimezone(tz)
        all_day = False
        start_str = start_dt.strftime("%-I:%M %p")
        end_str = end_dt.strftime("%-I:%M %p")
        time_display = f"{start_str} \u2013 {end_str}"
    else:
        start_dt = datetime.strptime(start["date"], "%Y-%m-%d").replace(tzinfo=tz)
        end_dt = datetime.strptime(end["date"], "%Y-%m-%d").replace(tzinfo=tz)
        all_day = True
        time_display = "All day"

    guests = []
    for att in event.get("attendees", []):
        if not att.get("self", False):
            guests.append(att.get("displayName", att.get("email", "")))

    return {
        "id": event.get("id", ""),
        "summary": event.get("summary", "(No title)"),
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "time_display": time_display,
        "all_day": all_day,
        "location": event.get("location", ""),
        "description": event.get("description", ""),
        "has_guests": _has_guests(event),
        "guests": guests,
        "date": start_dt.strftime("%Y-%m-%d"),
        "day_name": start_dt.strftime("%A"),
    }


def get_today_events():
    """Get all events for today from all configured calendars."""
    now = _now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    return _fetch_events_multi(_get_calendar_ids(), _local_rfc3339(start_of_day), _local_rfc3339(end_of_day), max_per_cal=50)


def get_week_events():
    """Get events for the next 5 days starting today."""
    now = _now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=5)
    return _fetch_events_multi(_get_calendar_ids(), _local_rfc3339(start), _local_rfc3339(end))


def get_upcoming_events(days=30):
    """Get all upcoming events for the next N days."""
    now = _now()
    end = now + timedelta(days=days)
    return _fetch_events_multi(_get_calendar_ids(), _local_rfc3339(now), _local_rfc3339(end), max_per_cal=250)


def get_month_events(year, month):
    """Get all events for a specific month."""
    tz = _get_tz()
    start = datetime(year, month, 1, tzinfo=tz)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end = datetime(year, month + 1, 1, tzinfo=tz)
    return _fetch_events_multi(_get_calendar_ids(), _local_rfc3339(start), _local_rfc3339(end), max_per_cal=300)
