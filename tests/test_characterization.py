"""
Characterization tests for the existing PDF Date Sorter contract.

These tests protect the current business logic ahead of a UI-only upgrade.
They document the behavior as implemented today; they do not authorize
changing it. If any of these fail, the discrepancy must be reported before
any UI work proceeds.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.date_logic import (
    validate_date,
    display_date,
    apply_next,
    apply_backward_edit,
    sort_assignments,
)
from core.session_manager import create_session, save_assignments, load_session


def make_assignments(n: int) -> list[dict]:
    return [
        {"page_index": i, "original_page_number": i + 1, "date": None, "source": None, "updated_at": None}
        for i in range(n)
    ]


# --- 1 & 2: MM-DD-YYYY input/display, ISO internal representation ---

def test_typed_mm_dd_yyyy_is_stored_as_iso():
    ok, iso = validate_date("09-13-2026")
    assert ok is True
    assert iso == "2026-09-13"


def test_iso_is_displayed_as_mm_dd_yyyy():
    assert display_date("2026-09-13") == "09-13-2026"


def test_display_and_parse_roundtrip():
    ok, iso = validate_date("01-05-2020")
    assert ok is True
    assert display_date(iso) == "01-05-2020"


# --- 3: Initial forward inheritance ---

def test_initial_forward_inheritance():
    assignments = make_assignments(5)
    assignments = apply_next(assignments, 0, "2026-09-01")
    for a in assignments[1:]:
        assert a["date"] == "2026-09-01"
        assert a["source"] == "inherited"
    assert assignments[0]["source"] == "explicit"


# --- 4 & 5: a new explicit date starts a new group; status is preserved ---

def test_new_explicit_date_starts_new_group_and_preserves_status():
    assignments = make_assignments(6)
    assignments = apply_next(assignments, 0, "2026-09-01")
    assignments = apply_next(assignments, 3, "2026-09-10")

    assert assignments[0]["source"] == "explicit" and assignments[0]["date"] == "2026-09-01"
    assert assignments[1]["source"] == "inherited" and assignments[1]["date"] == "2026-09-01"
    assert assignments[2]["source"] == "inherited" and assignments[2]["date"] == "2026-09-01"
    assert assignments[3]["source"] == "explicit" and assignments[3]["date"] == "2026-09-10"
    assert assignments[4]["source"] == "inherited" and assignments[4]["date"] == "2026-09-10"
    assert assignments[5]["source"] == "inherited" and assignments[5]["date"] == "2026-09-10"


# --- 7: Backward correction affects only the selected page ---

def test_backward_correction_touches_only_selected_page():
    assignments = make_assignments(6)
    assignments = apply_next(assignments, 0, "2026-09-01")
    assignments = apply_next(assignments, 3, "2026-09-10")

    assignments = apply_backward_edit(assignments, 1, "2026-09-20")

    assert assignments[0]["date"] == "2026-09-01" and assignments[0]["source"] == "explicit"
    assert assignments[1]["date"] == "2026-09-20" and assignments[1]["source"] == "explicit"
    assert assignments[2]["date"] == "2026-09-01" and assignments[2]["source"] == "inherited"
    assert assignments[3]["date"] == "2026-09-10" and assignments[3]["source"] == "explicit"
    assert assignments[4]["date"] == "2026-09-10" and assignments[4]["source"] == "inherited"
    assert assignments[5]["date"] == "2026-09-10" and assignments[5]["source"] == "inherited"


# --- 8: Stable chronological sort, ties keep original order ---

def test_sort_is_chronological_with_stable_ties():
    assignments = [
        {"page_index": 0, "date": "2026-09-01"},
        {"page_index": 1, "date": "2026-09-20"},
        {"page_index": 2, "date": "2026-09-01"},
        {"page_index": 3, "date": "2026-09-10"},
        {"page_index": 4, "date": "2026-09-10"},
        {"page_index": 5, "date": "2026-09-10"},
    ]
    order = sort_assignments(assignments)
    assert order == [0, 2, 3, 4, 5, 1]


def test_sort_raises_when_any_page_unassigned():
    assignments = make_assignments(3)
    assignments[0]["date"] = "2026-09-01"
    try:
        sort_assignments(assignments)
        assert False, "expected ValueError"
    except ValueError:
        pass


# --- 9: Save/reload (session persistence) ---

def test_session_persists_and_reloads(tmp_path, monkeypatch):
    import core.session_manager as sm
    monkeypatch.setattr(sm, "TMP_DIR", tmp_path)

    session = create_session("test.pdf", 3, "abc123")
    session["assignments"] = apply_next(session["assignments"], 0, "2026-09-01")
    save_assignments(session)

    reloaded = load_session(session["session_id"])
    assert reloaded is not None
    assert reloaded["assignments"][1]["date"] == "2026-09-01"
    assert reloaded["assignments"][1]["source"] == "inherited"
    assert reloaded["original_filename"] == "test.pdf"


# --- Concrete regression scenario from the spec ---

def test_concrete_six_page_regression_scenario():
    """
    1. Assign page 1: 09-01-2026.
    2. Forward inheritance covers pages 2-6.
    3. Assign page 4: 09-10-2026 (new group starts).
    4. Return to page 2, correct it to 09-20-2026 (backward correction).
    Expected final dates:
      page1=09-01-2026, page2=09-20-2026, page3=09-01-2026,
      page4=09-10-2026, page5=09-10-2026, page6=09-10-2026.
    Expected sort order (1-based original page numbers): 1, 3, 4, 5, 6, 2.
    """
    assignments = make_assignments(6)

    ok, iso1 = validate_date("09-01-2026")
    assert ok
    assignments = apply_next(assignments, 0, iso1)

    ok, iso4 = validate_date("09-10-2026")
    assert ok
    assignments = apply_next(assignments, 3, iso4)

    ok, iso2 = validate_date("09-20-2026")
    assert ok
    assignments = apply_backward_edit(assignments, 1, iso2)

    expected_display = {
        0: "09-01-2026",
        1: "09-20-2026",
        2: "09-01-2026",
        3: "09-10-2026",
        4: "09-10-2026",
        5: "09-10-2026",
    }
    for idx, expected in expected_display.items():
        assert display_date(assignments[idx]["date"]) == expected, f"page {idx + 1}"

    order = sort_assignments(assignments)
    original_page_numbers = [i + 1 for i in order]
    assert original_page_numbers == [1, 3, 4, 5, 6, 2]
