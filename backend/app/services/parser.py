import re
from datetime import date, timedelta

from app.config import Settings
from app.schemas.api import GoalRequirements, ParsedTask
from app.timeutil import local_now

WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "an": 1,
    "a": 1,
}


def _to_int(token: str) -> int | None:
    token = token.lower()
    if token.isdigit():
        return int(token)
    return WORD_NUMBERS.get(token)


def _clean_title(raw: str) -> str:
    text = re.sub(r"^(of|for)\s+", "", raw.strip(" .,;"), flags=re.I)
    text = re.sub(r"\b(tomorrow|today|please|and)\b", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" .,;")
    return text[:120] or "Untitled task"


def _parse_clock(hour: str, minute: str | None, meridiem: str | None) -> str:
    hours = int(hour)
    minutes = int(minute or 0)
    if meridiem:
        suffix = meridiem.lower()
        if suffix == "pm" and hours != 12:
            hours += 12
        if suffix == "am" and hours == 12:
            hours = 0
    return f"{hours:02d}:{minutes:02d}"


def parse_goal(goal: str, settings: Settings, today: date | None = None) -> GoalRequirements:
    tz_now = local_now(settings.timezone)
    today = today or tz_now.date()
    text = goal.strip()
    lower = text.lower()
    ambiguities: list[str] = []
    defaults: list[str] = []

    target: date | None = None
    iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if iso:
        target = date.fromisoformat(iso.group(1))
    elif re.search(r"\btomorrow\b", lower):
        target = today + timedelta(days=1)
    elif re.search(r"\btoday\b", lower):
        target = today
    else:
        ambiguities.append("No date found; specify today, tomorrow, or YYYY-MM-DD.")

    finish_by = None
    finish_match = re.search(
        r"finish by\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
        lower,
        flags=re.I,
    )
    if finish_match:
        finish_by = _parse_clock(finish_match.group(1), finish_match.group(2), finish_match.group(3))
        if not finish_match.group(3) and int(finish_match.group(1)) <= 12:
            defaults.append(f"Interpreted 'finish by {finish_match.group(1)}' as {finish_by} in 24-hour local time; add AM/PM if that is wrong.")

    work_start = settings.work_start
    work_end = finish_by or settings.work_end
    defaults.append(f"Working hours default to {settings.work_start}–{settings.work_end} {settings.timezone} unless the goal says otherwise.")

    fixed_events: list[ParsedTask] = []
    for match in re.finditer(
        r"(?:team\s+)?meeting at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
        lower,
        flags=re.I,
    ):
        start = _parse_clock(match.group(1), match.group(2), match.group(3))
        hours, minutes = [int(part) for part in start.split(":")]
        end_minutes = hours * 60 + minutes + settings.default_meeting_minutes
        end = f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"
        fixed_events.append(
            ParsedTask(
                title="Team meeting",
                duration_minutes=settings.default_meeting_minutes,
                priority=1,
                kind="fixed",
                start_time=start,
                end_time=end,
            )
        )
        defaults.append(
            f"Meeting duration was not specified; used documented default of {settings.default_meeting_minutes} minutes."
        )
        if not match.group(3) and int(match.group(1)) <= 7:
            ambiguities.append("Meeting hour has no AM/PM; interpreted using 24-hour clock / workday afternoon defaults.")

    for match in re.finditer(
        r"class at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
        lower,
        flags=re.I,
    ):
        start = _parse_clock(match.group(1), match.group(2), match.group(3))
        hours, minutes = [int(part) for part in start.split(":")]
        end_minutes = hours * 60 + minutes + 60
        end = f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"
        fixed_events.append(
            ParsedTask(
                title="Class",
                duration_minutes=60,
                priority=1,
                kind="fixed",
                start_time=start,
                end_time=end,
            )
        )
        defaults.append("Class duration was not specified; used documented default of 60 minutes.")

    breaks: list[ParsedTask] = []
    if re.search(r"\blunch\b", lower):
        breaks.append(
            ParsedTask(
                title="Lunch",
                duration_minutes=settings.default_lunch_minutes,
                priority=2,
                kind="break",
                start_time=settings.lunch_start,
                end_time=settings.lunch_end,
            )
        )
        defaults.append(
            f"Lunch time was not specified; used documented default {settings.lunch_start}–{settings.lunch_end}."
        )

    tasks: list[ParsedTask] = []
    duration_pattern = re.compile(
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten|an|a|\d+)\s+"
        r"(hours?|hrs?|minutes?|mins?)\s+(?:of\s+|for\s+(?:my\s+)?|for\s+)?"
        r"([a-zA-Z][a-zA-Z0-9 +\-]{0,60}?)(?=,|\s+and\b|$)",
        flags=re.I,
    )
    for match in duration_pattern.finditer(text):
        amount = _to_int(match.group(1))
        if amount is None:
            continue
        unit = match.group(2).lower()
        minutes = amount * 60 if unit.startswith("h") else amount
        title = _clean_title(match.group(3))
        if "lunch" in title.lower() or "meeting" in title.lower():
            continue
        if title.lower() in {"my project", "project"}:
            title = "Project work"
        if "dsa" in title.lower():
            title = "DSA practice"
        priority = 2 if "dsa" in title.lower() or "exam" in title.lower() else 3
        tasks.append(
            ParsedTask(
                title=title,
                duration_minutes=minutes,
                priority=priority,
                kind="flexible",
                deadline=f"{target.isoformat()}T{work_end}:00" if target else None,
            )
        )

    blocking = target is None or (not tasks and not fixed_events)
    if not tasks and not fixed_events:
        ambiguities.append("No schedulable tasks or fixed events could be extracted.")

    return GoalRequirements(
        date=target.isoformat() if target else None,
        tasks=tasks,
        fixed_events=fixed_events,
        breaks=breaks,
        finish_by=finish_by,
        work_start=work_start,
        work_end=work_end,
        ambiguities=ambiguities,
        documented_defaults=defaults,
        blocking=blocking,
    )
