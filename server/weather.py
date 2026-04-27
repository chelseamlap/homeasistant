"""Open-Meteo weather integration — free, no API key needed."""
import json
import logging
import os
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_CACHE_FILE = os.path.join(DATA_DIR, "weather_cache.json")


def _save_cache(data):
    """Cache last good weather response."""
    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump({"ts": datetime.now().isoformat(), "data": data}, f)
    except Exception:
        pass


def _load_cache(max_age_min=120):
    """Load cached weather if fresh enough (default 2 hours)."""
    try:
        with open(_CACHE_FILE) as f:
            cache = json.load(f)
        age = datetime.now() - datetime.fromisoformat(cache["ts"])
        if age.total_seconds() < max_age_min * 60:
            return cache["data"]
    except Exception:
        pass
    return None


def _dress_recommendation(temp_f, precip_mm, wind_mph):
    """Generate a 'dress the kids' recommendation."""
    parts = []
    if temp_f < 25:
        parts.append("heavy winter coat + snow pants")
    elif temp_f < 40:
        parts.append("heavy jacket + warm layers")
    elif temp_f < 50:
        parts.append("medium jacket")
    elif temp_f < 60:
        parts.append("light jacket or hoodie")
    elif temp_f < 70:
        parts.append("long sleeves")
    else:
        parts.append("t-shirt & shorts")

    if precip_mm > 2:
        parts.append("rain boots + umbrella")
    elif precip_mm > 0.5:
        parts.append("rain jacket")

    if wind_mph > 20:
        parts.append("windbreaker")

    if temp_f < 40:
        parts.append("hat + gloves")

    return " \u2022 ".join(parts)


def _wmo_to_icon(code):
    """Map WMO weather code to emoji icon."""
    mapping = {
        0: "\u2600\ufe0f", 1: "\U0001f324\ufe0f", 2: "\u26c5", 3: "\u2601\ufe0f",
        45: "\U0001f32b\ufe0f", 48: "\U0001f32b\ufe0f",
        51: "\U0001f326\ufe0f", 53: "\U0001f326\ufe0f", 55: "\U0001f327\ufe0f",
        56: "\U0001f327\ufe0f", 57: "\U0001f327\ufe0f",
        61: "\U0001f326\ufe0f", 63: "\U0001f327\ufe0f", 65: "\U0001f327\ufe0f",
        66: "\U0001f9ca", 67: "\U0001f9ca",
        71: "\U0001f328\ufe0f", 73: "\U0001f328\ufe0f", 75: "\U0001f328\ufe0f", 77: "\U0001f328\ufe0f",
        80: "\U0001f326\ufe0f", 81: "\U0001f327\ufe0f", 82: "\U0001f327\ufe0f",
        85: "\U0001f328\ufe0f", 86: "\U0001f328\ufe0f",
        95: "\u26c8\ufe0f", 96: "\u26c8\ufe0f", 99: "\u26c8\ufe0f",
    }
    return mapping.get(code, "\U0001f300")


def _wmo_to_desc(code):
    """Map WMO weather code to short description."""
    mapping = {
        0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Rime fog",
        51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
        56: "Freezing drizzle", 57: "Heavy freezing drizzle",
        61: "Light rain", 63: "Rain", 65: "Heavy rain",
        66: "Freezing rain", 67: "Heavy freezing rain",
        71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
        80: "Light showers", 81: "Showers", 82: "Heavy showers",
        85: "Light snow showers", 86: "Heavy snow showers",
        95: "Thunderstorm", 96: "Thunderstorm + hail", 99: "Severe thunderstorm",
    }
    return mapping.get(code, "Unknown")


def fetch_weather(lat, lon):
    """Fetch current + hourly + daily weather from Open-Meteo."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,wind_speed_10m,precipitation,weather_code",
        "hourly": "temperature_2m,precipitation_probability,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "auto",
        "forecast_days": 7,
    }

    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Weather API request failed: %s", e)
        cached = _load_cache()
        if cached:
            cached["_cached"] = True
            return cached
        return {"error": str(e)}

    def _num(val, default=0):
        """Safely coerce a value to a number (handles None from API)."""
        return val if val is not None else default

    # Current conditions — wrapped separately so hourly/daily still work
    current_data = data.get("current") or {}
    temp_f = _num(current_data.get("temperature_2m"))
    feels_like = _num(current_data.get("apparent_temperature"))
    wind = _num(current_data.get("wind_speed_10m"))
    precip = _num(current_data.get("precipitation"))
    wcode = _num(current_data.get("weather_code"))

    # Hourly — next 8 hours
    hourly = data.get("hourly") or {}
    now_hour = datetime.now().hour
    hourly_forecast = []
    h_temps = hourly.get("temperature_2m") or []
    h_rain = hourly.get("precipitation_probability") or []
    h_codes = hourly.get("weather_code") or []
    times = hourly.get("time") or []
    for i, t in enumerate(times):
        if len(hourly_forecast) >= 8:
            break
        h = int(t.split("T")[1].split(":")[0])
        d = t.split("T")[0]
        today_str = datetime.now().strftime("%Y-%m-%d")
        if (d == today_str and h >= now_hour) or d > today_str:
            hourly_forecast.append({
                "hour": datetime.strptime(t, "%Y-%m-%dT%H:%M").strftime("%-I%p").lower(),
                "temp": round(_num(h_temps[i] if i < len(h_temps) else 0)),
                "rain_pct": _num(h_rain[i] if i < len(h_rain) else 0),
                "icon": _wmo_to_icon(_num(h_codes[i] if i < len(h_codes) else 0)),
            })

    # Daily — 7-day forecast
    daily = data.get("daily") or {}
    daily_forecast = []
    d_times = daily.get("time") or []
    d_highs = daily.get("temperature_2m_max") or []
    d_lows = daily.get("temperature_2m_min") or []
    d_rain = daily.get("precipitation_probability_max") or []
    d_codes = daily.get("weather_code") or []
    for i, d in enumerate(d_times):
        dt = datetime.strptime(d, "%Y-%m-%d")
        daily_forecast.append({
            "date": d,
            "day_name": dt.strftime("%A"),
            "day_short": dt.strftime("%a"),
            "high": round(_num(d_highs[i] if i < len(d_highs) else 0)),
            "low": round(_num(d_lows[i] if i < len(d_lows) else 0)),
            "rain_pct": _num(d_rain[i] if i < len(d_rain) else 0),
            "icon": _wmo_to_icon(_num(d_codes[i] if i < len(d_codes) else 0)),
            "desc": _wmo_to_desc(_num(d_codes[i] if i < len(d_codes) else 0)),
        })

    result = {
        "current": {
            "temp": round(temp_f),
            "feels_like": round(feels_like),
            "wind": round(wind),
            "precip": round(precip, 2),
            "icon": _wmo_to_icon(wcode),
            "desc": _wmo_to_desc(wcode),
            "dress_rec": _dress_recommendation(temp_f, precip * 25.4, wind),
        },
        "hourly": hourly_forecast,
        "daily": daily_forecast,
    }
    _save_cache(result)
    return result
