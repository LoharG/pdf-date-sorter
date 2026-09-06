from __future__ import annotations

from datetime import datetime, timezone
import copy


def validate_date(date_str: str) -> tuple[bool, str]:
    """Parse MM-DD-YYYY. Returns (True, 'YYYY-MM-DD') or (False, error_key)."""
    if not date_str or not date_str.strip():
        return False, "invalid_date"
    try:
        dt = datetime.strptime(date_str.strip(), "%m-%d-%Y")
        return True, dt.strftime("%Y-%m-%d")
    except ValueError:
        parts = date_str.strip().split("-")
        if len(parts) == 3:
            return False, "invalid_date_calendar"
        return False, "invalid_date"


def display_date(iso_date: str | None) -> str:
    """Convert YYYY-MM-DD to MM-DD-YYYY for display. None -> ''."""
    if not iso_date:
        return ""
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return dt.strftime("%m-%d-%Y")
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
