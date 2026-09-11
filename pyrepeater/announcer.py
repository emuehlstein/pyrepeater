""" generates the daytime time+weather announcement wav via NWS + espeak-ng """

import asyncio
import asyncio.subprocess
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

USER_AGENT = "pyrepeater (https://github.com/emuehlstein/pyrepeater)"
TIMEOUT_SECS = 10

# NWS observation station lookup rarely changes; cache it per (lat, lon)
_station_url_cache: dict[tuple[float, float], str] = {}


def _get(url: str) -> dict:
    """blocking HTTP GET + JSON parse; run via asyncio.to_thread"""
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECS) as resp:
        return json.loads(resp.read())


def _fetch_weather_sync(lat: float, lon: float) -> str | None:
    """fetch a short current-conditions phrase from api.weather.gov, or None on failure"""
    try:
        station_url = _station_url_cache.get((lat, lon))
        if not station_url:
            points = _get(f"https://api.weather.gov/points/{lat},{lon}")
            station_url = points["properties"]["observationStations"]
            _station_url_cache[(lat, lon)] = station_url

        stations = _get(station_url)
        station_id = stations["features"][0]["properties"]["stationIdentifier"]
        obs = _get(f"https://api.weather.gov/stations/{station_id}/observations/latest")
        props = obs["properties"]
        temp_c = props["temperature"]["value"]
        description = props["textDescription"]
        if temp_c is None or not description:
            return None
        temp_f = round(temp_c * 9 / 5 + 32)
        return f"{temp_f} degrees, {description.lower()}"
    except (urllib.error.URLError, KeyError, IndexError, TimeoutError) as err:
        logger.warning("Weather fetch failed: %s", err)
        return None


async def fetch_weather(lat: float, lon: float) -> str | None:
    """fetch a short weather conditions phrase, or None if unavailable"""
    return await asyncio.to_thread(_fetch_weather_sync, lat, lon)


def build_announcement_text(weather: str | None, now: datetime | None = None) -> str:
    """build the spoken announcement text"""
    now = now or datetime.now()
    text = f"The time is {now.strftime('%-I:%M %p')}."
    if weather:
        text += f" Currently {weather}."
    return text


async def generate_wav(text: str, out_path: Path) -> bool:
    """render text to a wav file via espeak-ng; returns True on success"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "espeak-ng",
            "-w",
            str(out_path),
            text,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0 and out_path.exists()
    except FileNotFoundError:
        logger.warning("espeak-ng not installed; skipping time/weather announcement")
        return False
