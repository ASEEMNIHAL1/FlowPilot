from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def zone(tz_name: str) -> ZoneInfo:
    return ZoneInfo(tz_name)


def ensure_aware(dt: datetime, tz_name: str) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=zone(tz_name))
    return dt


def to_utc(dt: datetime, tz_name: str) -> datetime:
    return ensure_aware(dt, tz_name).astimezone(timezone.utc)


def coerce_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_local(dt: datetime, tz_name: str) -> datetime:
    return coerce_utc(dt).astimezone(zone(tz_name))


def parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def combine_local(day: date, clock: time, tz_name: str) -> datetime:
    return datetime.combine(day, clock, tzinfo=zone(tz_name))


def local_now(tz_name: str) -> datetime:
    return datetime.now(zone(tz_name))


def add_days(day: date, days: int) -> date:
    return day + timedelta(days=days)


def isoformat(dt: datetime) -> str:
    return dt.isoformat()
