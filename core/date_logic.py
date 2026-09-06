from __future__ import annotations

from datetime import datetime, timezone
import copy
import re

# Tried in order; all are day-first to match the app's DD-MM-YYYY convention
# (no MM/DD support — that would make two-digit-day dates genuinely ambiguous).
_DATE_FORMATS = [
    "%d-%m-%Y",   # 05-09-2026
    "%d/%m/%Y",   # 05/09/2026
    "%d.%m.%Y",   # 05.09.2026
    "%d %b %Y",   # 5 Sep 2026
    "%d %B %Y",   # 5 September 2026
]

# Loose shape check used only to distinguish "not a date at all" from
# "looks like a date but the day/month/year values don't form a real calendar
# date" (e.g. 31-02-2026) so we can show a more specific error message.
_DATE_SHAPE_RE = re.compile(
    r"^\d{1,2}\s*[-/.]\s*\d{1,2}\s*[-/.]\s*\d{4}$"
    r"|^\d{1,2}\s+[A-Za-z]+\s+\d{4}$"
)


def validate_date(date_str: str) -> tuple[bool, str]:
    """Parse a date in DD-MM-YYYY or a few common alternate formats
    (DD/MM/YYYY, DD.MM.YYYY, "5 Sep 2026", "5 September 2026").
    Returns (True, 'YYYY-MM-DD') or (False, error_key).
    """
    if not date_str or not date_str.strip():
        return False, "invalid_date"
    cleaned = date_str.strip()
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return True, dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    if _DATE_SHAPE_RE.match(cleaned):
        return False, "invalid_date_calendar"
    return False, "invalid_date"


def display_date(iso_date: str | None) -> str:
    """Convert YYYY-MM-DD to DD-MM-YYYY for display. None -> ''."""
    if not iso_date:
        return ""
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except ValueError:
        return ""


def apply_next(assignments: list[dict], current_idx: int, date_iso: str) -> list[dict]:
    """
    Save date_iso to current page as explicit.
    Fill forward all unassigned pages after current as inherited.
    Never overwrites an already-explicit next page but continues past it.
    Returns a deep copy — original is not mutated.
    """
    a = copy.deepcopy(assignments)
    now = datetime.now(timezone.utc).isoformat()
    a[current_idx]["date"] = date_iso
    a[current_idx]["source"] = "explicit"
    a[current_idx]["updated_at"] = now
    for next_idx in range(current_idx + 1, len(a)):
        if a[next_idx]["source"] == "explicit":
            date_iso = a[next_idx]["date"]
        else:
            a[next_idx]["date"] = date_iso
            a[next_idx]["source"] = "inherited"
            a[next_idx]["updated_at"] = now
    return a


def apply_backward_edit(assignments: list[dict], page_idx: int, date_iso: str) -> list[dict]:
    """
    Update only page_idx to date_iso (explicit).
    All other pages remain unchanged.
    Returns a deep copy — original is not mutated.
    """
    a = copy.deepcopy(assignments)
    now = datetime.now(timezone.utc).isoformat()
    a[page_idx]["date"] = date_iso
    a[page_idx]["source"] = "explicit"
    a[page_idx]["updated_at"] = now
    return a


def sort_assignments(assignments: list[dict]) -> list[int]:
    """
    Returns page indexes in chronological order.
    Sort key: (date ascending, page_index ascending).
    Raises ValueError if any assignment has date=None.
    """
    missing = [a["page_index"] for a in assignments if not a["date"]]
    if missing:
        raise ValueError(f"Assignments have missing dates: {missing}")
    sorted_a = sorted(assignments, key=lambda a: (a["date"], a["page_index"]))
    return [a["page_index"] for a in sorted_a]


def get_sticky_date(assignments: list[dict], current_idx: int) -> str | None:
    """
    Scan backward from current_idx (inclusive) and return first non-null date.
    Returns None if no date has been set at or before current_idx.
    """
    for i in range(current_idx, -1, -1):
        if assignments[i]["date"]:
            return assignments[i]["date"]
    return None


def is_suspiciously_out_of_order(prev_iso: str, new_iso: str, threshold_days: int = 3) -> bool:
    """
    Heuristic nudge only — never blocks saving.
    Flags a newly saved date as suspicious if it lands more than
    threshold_days before the previous page's date, or if the year looks
    like a 100/1000-year typo (e.g. 1926 instead of 2026).
    """
    prev_dt = datetime.strptime(prev_iso, "%Y-%m-%d")
    new_dt = datetime.strptime(new_iso, "%Y-%m-%d")
    if (prev_dt - new_dt).days > threshold_days:
        return True
    if abs(new_dt.year - prev_dt.year) in (100, 1000):
        return True
    return False
