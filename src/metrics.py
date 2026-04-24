"""
All metric computations for the CoE dashboard.
Pure functions — no I/O, no side effects.
All durations in business days (Mon–Fri, weekends excluded).
"""

from __future__ import annotations

import statistics
from datetime import date, datetime, timedelta
from typing import Optional

# ── Constants ────────────────────────────────────────────────────────────────

COE_START_DATE = date(2026, 4, 15)   # Date CoE received first intake
PRE_COE_DAYS = 174                   # Days from Oct 23 2025 to Apr 15 2026 (static label)

CLOSED_AT_GATE_TAGS = {"Already Completed", "No Needed", "Not Needed"}
TBD_TAGS = {"TBD"}
ALL_GATE_TAGS = CLOSED_AT_GATE_TAGS | TBD_TAGS

WORK_TYPE_GROUPS: dict[str, list[str]] = {
    "Task Set changes":        ["Task Set Change", "New Task Set"],
    "Automation changes":      ["Automation", "Change Automation"],
    "Picklist changes":        ["Update Picklist", "Add New Picklist"],
    "New / Modified Fields":   ["New Field"],
    "Template changes":        ["Change Template"],
    "Stage changes":           ["Add New Stage"],
    "Object modifications":    ["Modify Object"],
    "No action / Already done": ["Already Completed", "No Needed", "Not Needed"],
    "TBD":                     ["TBD"],
}

# Map work type group name → slug used in template variables
WORK_TYPE_SLUGS: dict[str, str] = {
    "Task Set changes":        "task_set",
    "Automation changes":      "automation",
    "Picklist changes":        "picklist",
    "New / Modified Fields":   "fields",
    "Template changes":        "template",
    "Stage changes":           "stage",
    "Object modifications":    "object",
    "No action / Already done": "no_action",
    "TBD":                     "tbd",
}

ESCALATED_STAGES = {"Escalated/rejected"}


# ── Helpers ──────────────────────────────────────────────────────────────────

def business_days_between(start: date, end: date) -> int:
    """Count Mon–Fri business days between start (inclusive) and end (exclusive)."""
    if end <= start:
        return 0
    days = 0
    current = start
    while current < end:
        if current.weekday() < 5:  # 0=Mon … 4=Fri
            days += 1
        current += timedelta(days=1)
    return days


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


def _is_substantive(tags: list[str]) -> bool:
    """A review is substantive if not ALL tags are in the closed-at-gate set."""
    if not tags:
        return False
    return not all(t in ALL_GATE_TAGS for t in tags)


def _is_closed_at_gate(tags: list[str]) -> bool:
    """All tags are in the closed-at-gate set (not TBD)."""
    if not tags:
        return False
    return all(t in CLOSED_AT_GATE_TAGS for t in tags)


def _is_pending(tags: list[str]) -> bool:
    """Item has TBD tag OR no first_review value yet."""
    if not tags:
        return True
    return any(t in TBD_TAGS for t in tags)


def _iso_week(d: date) -> int:
    return d.isocalendar()[1]


def _iso_year(d: date) -> int:
    return d.isocalendar()[0]


def _fmt_day(d: date) -> str:
    """e.g. 'Apr 20' — no leading zero."""
    return d.strftime("%b %-d")


def _fmt_month(d: date) -> str:
    """e.g. 'April'."""
    return d.strftime("%B")


def _fmt_month_year(d: date) -> str:
    """e.g. 'Oct 2025'."""
    return d.strftime("%b %Y")


def _fmt_long_date(d: date) -> str:
    """e.g. 'April 15, 2026'."""
    return d.strftime("%B %-d, %Y")


def _iso_week_start(year: int, week: int) -> date:
    """Monday of the given ISO week."""
    return date.fromisocalendar(year, week, 1)


def _iso_week_end(year: int, week: int) -> date:
    """Sunday of the given ISO week."""
    return date.fromisocalendar(year, week, 7)


def _week_range_label(d: date, end_is_today: bool = False) -> str:
    """e.g. 'Apr 20 – Today' (current week) or 'Apr 13 – Apr 19'."""
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    if end_is_today:
        return f"{_fmt_day(monday)} – Today"
    return f"{_fmt_day(monday)} – {_fmt_day(sunday)}"


def _month_range_label(d: date) -> str:
    """e.g. 'Apr 1 – Apr 30'."""
    first = d.replace(day=1)
    # Last day of month
    if d.month == 12:
        next_first = date(d.year + 1, 1, 1)
    else:
        next_first = date(d.year, d.month + 1, 1)
    last = next_first - timedelta(days=1)
    return f"{_fmt_day(first)} – {_fmt_day(last)}"


# ── Core metrics ─────────────────────────────────────────────────────────────

def compute_metrics(items: list[dict], today: Optional[date] = None, verbose: bool = False) -> dict:
    today = today or date.today()

    total = len(items)
    open_items = [i for i in items if not i["completed"]]
    completed_items = [i for i in items if i["completed"]]

    # Metric 3: delivered = completed + not rejected + not dropped
    delivered = [
        i for i in completed_items
        if i.get("coe_classification") != "Rejected"
        and i.get("status_color") != "dropped"
    ]

    # Metric 4: escalated/rejected
    escalated = [
        i for i in items
        if i.get("coe_stage") in ESCALATED_STAGES
        or i.get("coe_classification") == "Rejected"
    ]

    # Metric 5: review cycle (substantive only)
    review_durations = []
    for i in items:
        tags = i.get("first_review_tags") or []
        if not _is_substantive(tags):
            continue
        rd = _parse_date(i.get("received_date"))
        frd = _parse_date(i.get("first_review_date"))
        if rd and frd and frd >= rd:
            review_durations.append(business_days_between(rd, frd))

    review_avg = round(statistics.mean(review_durations), 1) if review_durations else None
    review_median = round(statistics.median(review_durations), 1) if review_durations else None
    review_min = min(review_durations) if review_durations else None
    review_max = max(review_durations) if review_durations else None

    # Metric 6: First Review → BA Assigned (business days)
    ba_durations = []
    ba_assigned_items = []
    for i in items:
        frd = _parse_date(i.get("first_review_date"))
        ba = _parse_date(i.get("ba_assigned"))
        if ba:
            ba_assigned_items.append(i)
        if frd and ba and ba >= frd:
            ba_durations.append(business_days_between(frd, ba))

    ba_avg = round(statistics.mean(ba_durations), 1) if ba_durations else None
    ba_count = len(ba_assigned_items)

    # Metric 7: upstream lag (Created on → Received Date)
    upstream_durations = []
    for i in items:
        co = _parse_date(i.get("created_on"))
        rd = _parse_date(i.get("received_date"))
        if co and rd and rd >= co:
            upstream_durations.append(business_days_between(co, rd))

    upstream_avg = round(statistics.mean(upstream_durations), 1) if upstream_durations else None
    upstream_median = round(statistics.median(upstream_durations), 1) if upstream_durations else None

    # Metric 12: priority set
    priority_set = [i for i in items if i.get("priority")]

    # Metric 13: yield split
    substantive_items = [i for i in items if _is_substantive(i.get("first_review_tags") or [])]
    gate_items = [i for i in items if _is_closed_at_gate(i.get("first_review_tags") or [])]
    pending_items = [i for i in items if _is_pending(i.get("first_review_tags") or [])]
    pending_names = " + ".join(i["name"] for i in pending_items if i.get("name"))

    # Metric 8: weekly intakes by ISO week (last 4 ISO weeks ending this week)
    this_week_num = _iso_week(today)
    this_week_year = _iso_year(today)
    weekly_counts: dict[int, int] = {}
    for i in items:
        rd = _parse_date(i.get("received_date"))
        if rd:
            wk = _iso_week(rd)
            weekly_counts[wk] = weekly_counts.get(wk, 0) + 1

    # Build last 4 ISO weeks relative to today
    def week_num_offset(offset: int) -> int:
        d = today - timedelta(weeks=offset)
        return _iso_week(d)

    w_current = week_num_offset(0)
    w_minus1 = week_num_offset(1)
    w_minus2 = week_num_offset(2)
    w_minus3 = week_num_offset(3)

    flow_weeks = {
        w_minus3: weekly_counts.get(w_minus3, 0),
        w_minus2: weekly_counts.get(w_minus2, 0),
        w_minus1: weekly_counts.get(w_minus1, 0),
        w_current: weekly_counts.get(w_current, 0),
    }

    # Metric 9: stage distribution of open items
    stage_counts: dict[str, int] = {}
    for i in open_items:
        stage = i.get("coe_stage") or "Unknown"
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    it_prio_count = stage_counts.get("IT Prioritization", 0)
    triage_count = stage_counts.get("Triage", 0)
    new_request_count = stage_counts.get("New Request", 0)

    # Metric 10: work type distribution
    work_type_counts: dict[str, int] = {}
    for group_name in WORK_TYPE_GROUPS:
        work_type_counts[group_name] = 0

    for i in items:
        tags = set(i.get("first_review_tags") or [])
        for group_name, group_tags in WORK_TYPE_GROUPS.items():
            if tags & set(group_tags):
                work_type_counts[group_name] += 1

    wt_max = max(work_type_counts.values()) if work_type_counts else 1

    # Metric 11: PM workload
    pm_counts: dict[str, int] = {}
    for i in items:
        pm_raw = i.get("pm_assigned") or ""
        for name in [n.strip() for n in pm_raw.split(",") if n.strip()]:
            pm_counts[name] = pm_counts.get(name, 0) + 1

    mar_count = _find_pm_count(pm_counts, "mar")
    david_count = _find_pm_count(pm_counts, "david")

    # Metric 14: timeline buckets
    # This week
    monday_this_week = today - timedelta(days=today.weekday())
    tw_items = [i for i in items if _in_range(i, monday_this_week, today + timedelta(days=1))]

    # Last week
    monday_last_week = monday_this_week - timedelta(weeks=1)
    sunday_last_week = monday_this_week - timedelta(days=1)
    lw_items = [i for i in items if _in_range(i, monday_last_week, monday_this_week)]

    # This month
    month_start = today.replace(day=1)
    tm_items = [i for i in items if _in_range(i, month_start, today + timedelta(days=1))]

    # Last month
    last_month_end = month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    lm_items = [i for i in items if _in_range(i, last_month_start, month_start)]

    # 6 months rolling
    six_mo_start = today - timedelta(days=182)
    six_mo_items = [i for i in items if _in_range(i, six_mo_start, today + timedelta(days=1))]

    # Days CoE active
    days_coe_active = (today - COE_START_DATE).days

    # ── Dynamic date labels ─────────────────────────────────────────────────
    tw_iso_year = _iso_year(today)
    tw_iso_week = _iso_week(today)

    # Flow weeks: compute Mon–Sun for each
    def _week_mon_sun_label(offset_weeks: int) -> str:
        anchor = today - timedelta(weeks=offset_weeks)
        y = _iso_year(anchor)
        w = _iso_week(anchor)
        mon = _iso_week_start(y, w)
        sun = _iso_week_end(y, w)
        return f"{_fmt_day(mon)} – {_fmt_day(sun)}"

    # Current week may include today in its range
    tw_window = _week_range_label(today, end_is_today=True)
    lw_window = _week_mon_sun_label(1)

    # Month labels
    tm_month_name = _fmt_month(today)
    tm_window = _month_range_label(today)

    last_month_anchor = month_start - timedelta(days=1)
    lm_month_name = _fmt_month(last_month_anchor)
    lm_window = _month_range_label(last_month_anchor)

    # 6-month range label
    six_mo_label = f"{_fmt_month_year(six_mo_start)} – {_fmt_month_year(today)}"

    # Flow week labels for W-3 through W-current
    flow_w_minus3_range = _week_mon_sun_label(3)
    flow_w_minus2_range = _week_mon_sun_label(2)
    flow_w_minus1_range = _week_mon_sun_label(1)
    # Current week is special: end shows "Now"
    mon = today - timedelta(days=today.weekday())
    flow_w_current_range = f"{_fmt_day(mon)} – Now"

    # CoE founding date display
    coe_start_display = _fmt_long_date(COE_START_DATE)

    # Most recent received date among pending items (for §05 copy)
    pending_dates = [
        _parse_date(i.get("received_date"))
        for i in pending_items
        if _parse_date(i.get("received_date"))
    ]
    pending_received_label = _fmt_day(max(pending_dates)) if pending_dates else "recently"

    # Donut SVG math
    donut_total = len(open_items)
    donut_it_prio_da, donut_triage_da, donut_new_req_da = _donut_dasharrays(
        donut_total, it_prio_count, triage_count, new_request_count
    )

    # Flow bar widths (relative to max week)
    flow_values = list(flow_weeks.values())
    flow_max = max(flow_values) if any(flow_values) else 1
    week_labels = list(flow_weeks.keys())

    def bar_pct(count: int) -> str:
        if flow_max == 0:
            return "0%"
        return f"{round(count / flow_max * 100)}%"

    # PM workload note
    mar_pct = round(mar_count / total * 100) if total else 0
    david_pct = round(david_count / total * 100) if total else 0
    if mar_count and david_count and mar_count != david_count:
        diff_pct = round(abs(mar_count - david_count) / min(mar_count, david_count) * 100)
        heavier = "Mar" if mar_count > david_count else "David"
        workload_note = f"{mar_count}/{david_count} — {heavier} is +{diff_pct}% this week"
    else:
        workload_note = f"{mar_count}/{david_count}"

    escalated_pct = round(len(escalated) / total * 100) if total else 0
    gate_pct = round(len(gate_items) / total * 100) if total else 0
    substantive_pct = round(len(substantive_items) / total * 100) if total else 0
    pending_pct = round(len(pending_items) / total * 100) if total else 0

    # Status color blank count
    no_color = [i for i in items if not i.get("status_color")]
    rec_status_color_blank = f"{len(no_color)} of {total}"

    result = {
        # Snapshot
        "total": total,
        "open_count": len(open_items),
        "delivered_count": len(delivered),
        "escalated_count": len(escalated),
        "escalated_pct": f"{escalated_pct}%",

        # Review cycle
        "review_avg": str(review_avg) if review_avg is not None else "—",
        "review_median": str(int(review_median)) if review_median is not None else "—",
        "review_min": str(review_min) if review_min is not None else "—",
        "review_max": str(review_max) if review_max is not None else "—",
        "review_substantive_count": len(review_durations),

        # Upstream lag
        "upstream_avg": str(upstream_avg) if upstream_avg is not None else "—",
        "upstream_median": str(upstream_median) if upstream_median is not None else "—",

        # Priority
        "priority_set_count": len(priority_set),
        "priority_unset_count": total - len(priority_set),

        # BA
        "ba_avg": str(ba_avg) if ba_avg is not None else "—",
        "ba_count": ba_count,
        "ba_pending_total": f"{ba_count} of {total}",

        # Yield
        "yield_substantive": len(substantive_items),
        "yield_substantive_pct": f"{substantive_pct}%",
        "yield_gate": len(gate_items),
        "yield_gate_pct": f"{gate_pct}%",
        "yield_pending": len(pending_items),
        "yield_pending_pct": f"{pending_pct}%",
        "yield_pending_names": pending_names,

        # Weekly flow
        "flow_weeks": flow_weeks,
        "flow_week_labels": week_labels,
        "flow_bar_pcts": [bar_pct(v) for v in flow_values],
        "flow_max": flow_max,

        # Stage donut
        "donut_total_open": donut_total,
        "donut_it_prio": it_prio_count,
        "donut_triage": triage_count,
        "donut_new_request": new_request_count,
        "donut_it_prio_dasharray": donut_it_prio_da,
        "donut_triage_dasharray": donut_triage_da,
        "donut_new_request_dasharray": donut_new_req_da,
        "donut_it_prio_dashoffset": "25",
        "donut_triage_dashoffset": str(round(25 - donut_it_prio_da, 1)),
        "donut_new_request_dashoffset": str(round(25 - donut_it_prio_da - donut_triage_da, 1)),

        # Work types
        "work_type_counts": work_type_counts,
        "work_type_max": wt_max,

        # PM workload
        "pm_counts": pm_counts,
        "team_mar_count": mar_count,
        "team_mar_pct": f"{mar_pct}%",
        "team_david_count": david_count,
        "team_david_pct": f"{david_pct}%",
        "rec_workload_note": workload_note,

        # Timeline
        "tw_intakes": len(tw_items),
        "lw_intakes": len(lw_items),
        "tm_intakes": len(tm_items),
        "tm_reviewed": len([i for i in tm_items if i.get("first_review_date")]),
        "tm_escalated": sum(
            1 for i in tm_items
            if i.get("coe_stage") in ESCALATED_STAGES
            or i.get("coe_classification") == "Rejected"
        ),
        "lm_intakes": len(lm_items),
        "six_mo_intakes": len(six_mo_items),
        "days_coe_active": days_coe_active,
        "pre_coe_days": PRE_COE_DAYS,

        # W-number labels for current and last 3 weeks
        "w_current": w_current,
        "w_minus1": w_minus1,
        "w_minus2": w_minus2,
        "w_minus3": w_minus3,

        # Recs
        "rec_it_prio_count": it_prio_count,
        "rec_status_color_blank": rec_status_color_blank,

        # Dynamic date labels
        "tw_window_label": tw_window,
        "lw_window_label": lw_window,
        "tm_month_name": tm_month_name,
        "tm_window_label": tm_window,
        "lm_month_name": lm_month_name,
        "lm_window_label": lm_window,
        "six_mo_window_label": six_mo_label,
        "flow_w_minus3_range": flow_w_minus3_range,
        "flow_w_minus2_range": flow_w_minus2_range,
        "flow_w_minus1_range": flow_w_minus1_range,
        "flow_w_current_range": flow_w_current_range,
        "pending_received_label": pending_received_label,
        "coe_start_display": coe_start_display,

        # Static
        "coe_start_date": COE_START_DATE.isoformat(),
    }

    if verbose:
        for k, v in result.items():
            if not isinstance(v, (dict, list)):
                print(f"  {k}: {v}")

    return result


# ── Private helpers ───────────────────────────────────────────────────────────

def _find_pm_count(pm_counts: dict, name_fragment: str) -> int:
    """Find count for a PM whose name contains the given fragment (case-insensitive)."""
    for name, count in pm_counts.items():
        if name_fragment.lower() in name.lower():
            return count
    return 0


def _in_range(item: dict, start: date, end: date) -> bool:
    """True if item's received_date falls in [start, end)."""
    rd = _parse_date(item.get("received_date"))
    if not rd:
        return False
    return start <= rd < end


def _donut_dasharrays(total: int, it_prio: int, triage: int, new_req: int):
    """Compute SVG stroke-dasharray values for donut chart segments."""
    if total == 0:
        return (0, 0, 0)
    it_da = round(it_prio / total * 100, 1)
    tr_da = round(triage / total * 100, 1)
    nr_da = round(new_req / total * 100, 1)
    return (it_da, tr_da, nr_da)
