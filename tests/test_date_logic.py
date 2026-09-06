import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from core.date_logic import apply_next, apply_backward_edit, validate_date, is_suspiciously_out_of_order


def make_assignments(n: int) -> list[dict]:
    return [
        {"page_index": i, "original_page_number": i + 1, "date": None, "source": None, "updated_at": None}
        for i in range(n)
    ]


def test_forward_fill_reaches_distant_page():
    assignments = make_assignments(6)
    assignments = apply_next(assignments, 0, "2026-01-01")

    assert assignments[4]["date"] == "2026-01-01"
    assert assignments[4]["source"] == "inherited"


def test_reassigning_an_already_inherited_page_repropagates_forward():
    assignments = make_assignments(4)
    assignments = apply_next(assignments, 0, "2016-12-10")
    assert [a["date"] for a in assignments] == ["2016-12-10"] * 4
    assert [a["source"] for a in assignments] == ["explicit", "inherited", "inherited", "inherited"]

    assignments = apply_next(assignments, 1, "2016-12-09")

    assert assignments[0] == {"page_index": 0, "original_page_number": 1, "date": "2016-12-10",
                               "source": "explicit", "updated_at": assignments[0]["updated_at"]}
    assert assignments[1]["date"] == "2016-12-09"
    assert assignments[1]["source"] == "explicit"
    assert assignments[2]["date"] == "2016-12-09"
    assert assignments[2]["source"] == "inherited"
    assert assignments[3]["date"] == "2016-12-09"
    assert assignments[3]["source"] == "inherited"


def test_forward_fill_stops_at_next_explicit_page():
    assignments = make_assignments(5)
    assignments = apply_next(assignments, 0, "2026-01-01")
    assignments[3]["date"] = "2026-03-01"
    assignments[3]["source"] = "explicit"

    assignments = apply_next(assignments, 1, "2026-02-01")

    assert assignments[2]["date"] == "2026-02-01"
    assert assignments[2]["source"] == "inherited"
    assert assignments[3]["date"] == "2026-03-01"
    assert assignments[3]["source"] == "explicit"
    assert assignments[4]["date"] == "2026-03-01"
    assert assignments[4]["source"] == "inherited"


def test_backward_edit_touches_only_target_page():
    assignments = make_assignments(4)
    assignments = apply_next(assignments, 0, "2026-01-01")
    assignments = apply_backward_edit(assignments, 0, "2026-01-05")

    assert assignments[0]["date"] == "2026-01-05"
    assert assignments[1]["date"] == "2026-01-01"
    assert assignments[2]["date"] == "2026-01-01"
    assert assignments[3]["date"] == "2026-01-01"
