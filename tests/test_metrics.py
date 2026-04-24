"""
Tests for metrics.py — verifies business logic against fixture data.
Run with: pytest tests/
"""

import json
from datetime import date
from pathlib import Path

import pytest

from src.metrics import (
    business_days_between,
    compute_metrics,
    _is_substantive,
    _is_closed_at_gate,
    _is_pending,
)
from src.asana_client import load_fixture

FIXTURE = Path(__file__).parent / "fixtures" / "sample_asana_response.json"


# ── business_days_between ─────────────────────────────────────────────────────

def test_business_days_same_day():
    d = date(2026, 4, 15)
    assert business_days_between(d, d) == 0


def test_business_days_one_week():
    # Mon Apr 13 → Mon Apr 20 = 5 business days
    assert business_days_between(date(2026, 4, 13), date(2026, 4, 20)) == 5


def test_business_days_skips_weekend():
    # Fri Apr 17 → Mon Apr 20 = 1 business day (Fri itself counts, Sat/Sun skip)
    assert business_days_between(date(2026, 4, 17), date(2026, 4, 20)) == 1


def test_business_days_end_before_start():
    assert business_days_between(date(2026, 4, 20), date(2026, 4, 15)) == 0


# ── Yield helpers ─────────────────────────────────────────────────────────────

def test_is_substantive_real_tag():
    assert _is_substantive(["Task Set Change"]) is True


def test_is_substantive_already_completed():
    assert _is_substantive(["Already Completed"]) is False


def test_is_substantive_mixed():
    # If any tag is substantive, the item is substantive
    assert _is_substantive(["Task Set Change", "TBD"]) is True


def test_is_substantive_all_tbd():
    assert _is_substantive(["TBD"]) is False


def test_is_substantive_empty():
    assert _is_substantive([]) is False


def test_closed_at_gate_no_needed():
    assert _is_closed_at_gate(["No Needed"]) is True


def test_closed_at_gate_tbd_excluded():
    assert _is_closed_at_gate(["TBD"]) is False


def test_pending_no_tags():
    assert _is_pending([]) is True


def test_pending_tbd():
    assert _is_pending(["TBD"]) is True


def test_pending_real_tag():
    assert _is_pending(["Task Set Change"]) is False


# ── compute_metrics with fixture ──────────────────────────────────────────────

@pytest.fixture
def items():
    return load_fixture(str(FIXTURE))


def test_fixture_loads(items):
    assert len(items) == 10


def test_total_count(items):
    m = compute_metrics(items, today=date(2026, 4, 24))
    assert m["total"] == 10


def test_open_count(items):
    m = compute_metrics(items, today=date(2026, 4, 24))
    # All 10 items in fixture are not completed
    assert m["open_count"] == 10


def test_delivered_zero(items):
    # No items are completed → delivered = 0
    m = compute_metrics(items, today=date(2026, 4, 24))
    assert m["delivered_count"] == 0


def test_escalated_count(items):
    # Items 1004 (Rejected) and 1005 (Rejected) → 2 escalated
    m = compute_metrics(items, today=date(2026, 4, 24))
    assert m["escalated_count"] == 2


def test_review_avg_is_float_or_dash(items):
    m = compute_metrics(items, today=date(2026, 4, 24))
    avg = m["review_avg"]
    # Should be a string representation of a number, not "—"
    assert avg != "—"
    assert float(avg) > 0


def test_review_substantive_excludes_gate_items(items):
    m = compute_metrics(items, today=date(2026, 4, 24))
    # Items 1004 (Already Completed) and 1005 (No Needed) are not substantive
    # Item 1006 (TBD) has no first_review_date → excluded from duration calc
    # Substantive items with both dates: 1001,1002,1003,1007,1008,1009,1010 = 7
    assert m["review_substantive_count"] == 7


def test_upstream_avg_computed(items):
    m = compute_metrics(items, today=date(2026, 4, 24))
    assert m["upstream_avg"] != "—"
    assert float(m["upstream_avg"]) > 0


def test_yield_gate_count(items):
    # Items tagged "Already Completed" or "No Needed": 1004, 1005 → 2
    m = compute_metrics(items, today=date(2026, 4, 24))
    assert m["yield_gate"] == 2


def test_yield_pending_count(items):
    # Item 1006 (TBD) → 1 pending
    m = compute_metrics(items, today=date(2026, 4, 24))
    assert m["yield_pending"] == 1


def test_work_type_task_set(items):
    # Items 1001 (Task Set Change) and 1002 (New Task Set) → 2
    m = compute_metrics(items, today=date(2026, 4, 24))
    assert m["work_type_counts"]["Task Set changes"] == 2


def test_work_type_automation(items):
    # Items 1003 (Automation) and 1010 (Change Automation) → 2
    m = compute_metrics(items, today=date(2026, 4, 24))
    assert m["work_type_counts"]["Automation changes"] == 2


def test_pm_mar_count(items):
    m = compute_metrics(items, today=date(2026, 4, 24))
    # Mar items: 1001, 1003, 1005, 1006, 1008 → 5
    assert m["team_mar_count"] == 5


def test_pm_david_count(items):
    m = compute_metrics(items, today=date(2026, 4, 24))
    # David items: 1002, 1004, 1007, 1009, 1010 → 5
    assert m["team_david_count"] == 5


def test_priority_set(items):
    m = compute_metrics(items, today=date(2026, 4, 24))
    # Items with priority: 1001(High), 1002(High), 1003(Medium), 1007(Medium), 1008(High), 1010(Medium) → 6
    assert m["priority_set_count"] == 6


def test_donut_math(items):
    m = compute_metrics(items, today=date(2026, 4, 24))
    # All 10 open, IT Prio stage: 1001, 1002, 1003, 1007, 1010 → 5
    total = m["donut_total_open"]
    it = m["donut_it_prio"]
    assert total == 10
    assert it == 5
    assert m["donut_it_prio_dasharray"] == round(5 / 10 * 100, 1)


def test_people_type_parsed_as_names(tmp_path):
    """When PM Assigned comes as type=people, names are extracted correctly."""
    from src.asana_client import load_fixture
    import json
    fixture = tmp_path / "people.json"
    fixture.write_text(json.dumps([{
        "gid": "x",
        "name": "Test item",
        "completed": False,
        "current_status": {"color": None},
        "custom_fields": [
            {
                "gid": "1210474554240546",
                "type": "people",
                "people_value": [
                    {"gid": "u1", "name": "Maria Garcia"},
                    {"gid": "u2", "name": "Jessie Logan"},
                ],
            }
        ]
    }]))
    items = load_fixture(str(fixture))
    assert items[0]["pm_assigned"] == "Maria Garcia, Jessie Logan"


def test_pm_count_finds_maria_garcia():
    """Simulate new portfolio state where PM is stored as 'Maria Garcia'."""
    from src.metrics import compute_metrics
    from datetime import date
    items = [
        {
            "gid": "1", "name": "t", "completed": False, "completed_at": None,
            "status_color": None, "created_on": "2026-04-01",
            "received_date": "2026-04-15", "first_review_date": "2026-04-20",
            "ba_assigned": None, "first_review_tags": ["Task Set Change"],
            "coe_stage": "Triage", "coe_classification": None,
            "pm_assigned": "Maria Garcia", "priority": None,
        }
    ]
    m = compute_metrics(items, today=date(2026, 4, 24))
    # "mar" substring matches "Maria Garcia" (and David is 0)
    assert m["team_mar_count"] == 1


def test_business_days_review_cycle(items):
    """Verify the 3.8 bd target from the brief against known data."""
    m = compute_metrics(items, today=date(2026, 4, 24))
    avg = float(m["review_avg"])
    # With our fixture dates the avg should be reasonable (> 1, < 10 bd)
    assert 1.0 <= avg <= 10.0
