"""Google Calendar API integration."""
import logging
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google_auth import get_credentials

logger = logging.getLogger(__name__)


def _get_service():
    """Build the Calendar API service."""
    creds = get_credentials()
    if not creds:
        return None
    return build("calendar", "v3", credentials=creds)


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

    # Handle all-day vs timed events
    if "dateTime" in start:
        start_dt = datetime.fromisoformat(start["dateTime"])
        end_dt = datetime.fromisoformat(end["dateTime"])
        all_day = False
        start_str = start_dt.strftime("%-I:%M %p")
        end_str = end_dt.strftime("%-I:%M %p")
        time_display = f"{start_str} \u2013 {end_str}"
    else:
        start_dt = datetime.strptime(start["date"], "%Y-%m-%d")
        end_dt = datetime.strptime(end["date"], "%Y-%m-%d")
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
    """Get all events for today."""
    service = _get_service()
    if not service:
        return []

    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    try:
        result = service.events().list(
            calendarId="primary",
            timeMin=start_of_day.isoformat() + "Z" if start_of_day.tzinfo is None else start_of_day.isoformat(),
            timeMax=end_of_day.isoformat() + "Z" if end_of_day.tzinfo is None else end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=50,
        ).execute()
        return [_parse_event(e) for e in result.get("items", [])]
    except Exception as e:
        logger.error(f"Calendar fetch failed: {e}")
        return []


def get_week_events():
    """Get all events for Monday–Sunday of the current week."""
    service = _get_service()
    if not service:
        return []

    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=7)

    try:
        result = service.events().list(
            calendarId="primary",
            timeMin=monday.isoformat() + "Z",
            timeMax=sunday.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
            maxResults=100,
        ).execute()
        return [_parse_event(e) for e in result.get("items", [])]
    except Exception as e:
        logger.error(f"Calendar week fetch failed: {e}")
        return []


def get_upcoming_events(days=30):
    """Get all upcoming events for the next N days."""
    service = _get_service()
    if not service:
        return []

    now = datetime.now()
    end = now + timedelta(days=days)

    try:
        result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat() + "Z",
            timeMax=end.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
            maxResults=250,
        ).execute()
        return [_parse_event(e) for e in result.get("items", [])]
    except Exception as e:
        logger.error(f"Calendar upcoming fetch failed: {e}")
        return []


def get_upcoming_visitors(days=30):
    """Get upcoming events that involve visitors/guests."""
    events = get_upcoming_events(days)
    visitors = [e for e in events if e["has_guests"]]

    now = datetime.now()
    for v in visitors:
        event_date = datetime.fromisoformat(v["start"])
        delta = (event_date.date() - now.date()).days
        v["days_until"] = max(0, delta)

    return visitors[:3]


def get_month_events(year, month):
    """Get all events for a specific month."""
    service = _get_service()
    if not service:
        return []

    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)

    try:
        result = service.events().list(
            calendarId="primary",
            timeMin=start.isoformat() + "Z",
            timeMax=end.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
            maxResults=300,
        ).execute()
        return [_parse_event(e) for e in result.get("items", [])]
    except Exception as e:
        logger.error(f"Calendar month fetch failed: {e}")
        return []
