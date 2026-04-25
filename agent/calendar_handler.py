from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


TIME_HINTS = (
    "am",
    "pm",
    "morning",
    "afternoon",
    "evening",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "mon ",
    "tue",
    "wed",
    "thu",
    "fri",
)


def needs_timezone_confirmation(message: str, prospect_timezone: str | None = None) -> bool:
    normalized = f" {(message or '').casefold()} "
    mentions_time = any(hint in normalized for hint in TIME_HINTS)
    return mentions_time and not prospect_timezone


def build_timezone_confirmation(
    prospect_local_dt: datetime,
    prospect_timezone: str,
    team_timezone: str,
) -> str:
    prospect_zone = ZoneInfo(prospect_timezone)
    team_zone = ZoneInfo(team_timezone)
    localized = prospect_local_dt.replace(tzinfo=prospect_zone)
    team_dt = localized.astimezone(team_zone)

    prospect_label = _friendly_timezone_label(localized)
    team_label = _friendly_timezone_label(team_dt)
    return (
        f"Just confirming — {localized.strftime('%A')} {localized.strftime('%-I%p').lower()} "
        f"{prospect_label}? That's {team_dt.strftime('%-I%p').lower()} {team_label} for our delivery lead."
    )


def _friendly_timezone_label(dt: datetime) -> str:
    offset = dt.utcoffset()
    if offset is None:
        return dt.tzname() or "local time"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{dt.tzname()} (UTC{sign}{hours:02d}:{minutes:02d})"
