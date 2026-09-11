""" day/night/net mode resolution """

from datetime import datetime, time
from enum import Enum


class Mode(Enum):
    """operating mode of the repeater"""

    DAY = "day"
    NIGHT = "night"
    NET = "net"


def _parse_hhmm(value: str) -> time:
    """parse an HH:MM string into a time object"""
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def current_mode(settings, net_mode: bool, now: datetime | None = None) -> Mode:
    """resolve the current operating mode; net_mode always wins over the clock"""
    if net_mode:
        return Mode.NET

    now = now or datetime.now()
    start = _parse_hhmm(settings.day_start)
    end = _parse_hhmm(settings.day_end)
    current = now.time()

    if start <= end:
        is_day = start <= current < end
    else:
        # day window wraps past midnight, ex. DAY_START=22:00, DAY_END=06:00
        is_day = current >= start or current < end
    return Mode.DAY if is_day else Mode.NIGHT
