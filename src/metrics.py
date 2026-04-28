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

# Stages that are part of the active backlog (excluded: terminal stages like
# Rejected, Completed, etc.). Order here = order in cards / area chart.
BACKLOG_STAGES_ORDERED = [
    "New Request",
    "Triage",
    "IT Prioritization",
    "In Progress",
    "Awaiting Next Sprint",
]

# Stage colors for stacked-area + cards (matching the boss's mock)
STAGE_COLOR_MAP = {
    "New Request":         "#4f7ef0",   # blue
    "Triage":              "#a463f5",   # purple
    "IT Prioritization":   "#e1417a",   # pink
    "In Progress":         "#e87a3a",   # orange
    "Awaiting Next Sprint": "#d4a23a",  # gold
}

# CoE Classification values that mark a request as "Pushed to EPMO".
# Boss-confirmed mapping: today's "Escalated/rejected" stage maps here too
# until Asana classification options are updated.
EPMO_CLASSIFICATIONS = {"Pushed to EPMO"}

# Color palette for donut segments — assigned in priority order.
# CSS variables that exist in the template's :root.
STAGE_COLOR_PALETTE = [
    {"css": "var(--indigo)", "hex_start": "#5e5ce6", "hex_end": "#bf5af2"},
    {"css": "var(--orange)", "hex_start": "#ff9f0a", "hex_end": "#ff375f"},
    {"css": "var(--green)",  "hex_start": "#30d158", "hex_end": "#30d158"},
    {"css": "var(--cyan)",   "hex_start": "#64d2ff", "hex_end": "#0a84ff"},
    {"css": "var(--purple)", "hex_start": "#bf5af2", "hex_end": "#5e5ce6"},
    {"css": "var(--yellow)", "hex_start": "#ffd60a", "hex_end": "#ff9f0a"},
    {"css": "var(--mint)",   "hex_start": "#63e6e2", "hex_end": "#40c8e0"},
    {"css": "var(--pink)",   "hex_start": "#ff375f", "hex_end": "#bf5af2"},
    {"css": "var(--red)",    "hex_start": "#ff453a", "hex_end": "#ff375f"},
    {"css": "var(--teal)",   "hex_start": "#40c8e0", "hex_end": "#63e6e2"},
]


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

    # Top work-type category (dynamic §04 header)
    if work_type_counts and wt_max > 0:
        top_wt_name = max(work_type_counts.items(), key=lambda kv: kv[1])[0]
    else:
        top_wt_name = None

    # Flow chart peak week (dynamic §06 header)
    if flow_weeks:
        peak_week_num, peak_week_count = max(flow_weeks.items(), key=lambda kv: kv[1])
        flow_peak_week_label = f"W{peak_week_num}"
    else:
        peak_week_num, peak_week_count = None, 0
        flow_peak_week_label = ""

    # Metric 11: PM workload
    pm_counts: dict[str, int] = {}
    for i in items:
        pm_raw = i.get("pm_assigned") or ""
        for name in [n.strip() for n in pm_raw.split(",") if n.strip()]:
            pm_counts[name] = pm_counts.get(name, 0) + 1

    mar_count = _find_pm_count(pm_counts, "mar")
    david_count = _find_pm_count(pm_counts, "david")

    # Metric 14: timeline buckets — per-period stats
    tomorrow = today + timedelta(days=1)

    # This week
    monday_this_week = today - timedelta(days=today.weekday())
    tw = _period_stats(items, monday_this_week, tomorrow)

    # Last week
    monday_last_week = monday_this_week - timedelta(weeks=1)
    lw = _period_stats(items, monday_last_week, monday_this_week)

    # This month
    month_start = today.replace(day=1)
    tm = _period_stats(items, month_start, tomorrow)

    # Last month
    last_month_end = month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    lm = _period_stats(items, last_month_start, month_start)

    # 6 months rolling
    six_mo_start = today - timedelta(days=182)
    six_mo = _period_stats(items, six_mo_start, tomorrow)

    # Did the CoE even exist during last month?
    last_month_has_coe = last_month_end >= COE_START_DATE

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

    # Donut SVG math (dynamic — every stage that has open items gets a segment)
    donut_total = len(open_items)
    donut_segments = _build_donut_segments(stage_counts, donut_total)

    # Backwards-compat keys still used by tests
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

    # ── §06 v2: Backlog equation, per-stage deltas, outcomes, area chart ────

    # Items in the active backlog = open AND in one of the active stages
    backlog_items = [
        i for i in open_items
        if i.get("coe_stage") in BACKLOG_STAGES_ORDERED
    ]

    # Per-stage current counts (only stages we track for the board)
    stage_current = {s: 0 for s in BACKLOG_STAGES_ORDERED}
    for i in backlog_items:
        s = i.get("coe_stage")
        if s in stage_current:
            stage_current[s] += 1

    # Pull last week's counts from history if available; otherwise fall back
    # to the first available snapshot (so the dashboard shows real movement
    # while history is still accumulating, instead of "no prior week").
    history_snapshots = _load_history_for_metrics()
    last_week_snap = _find_snapshot_n_days_ago(history_snapshots, today, 7)

    using_first_snapshot = False
    first_snapshot_date_str = None
    if last_week_snap:
        baseline_metrics = last_week_snap
    else:
        # Find oldest snapshot strictly before today
        baseline_metrics, first_snapshot_date_str = _find_first_snapshot_before(
            history_snapshots, today
        )
        using_first_snapshot = baseline_metrics is not None

    stage_baseline = {}
    if baseline_metrics:
        prev_stage_current = baseline_metrics.get("stage_current", {}) or {}
        for s in BACKLOG_STAGES_ORDERED:
            stage_baseline[s] = int(prev_stage_current.get(s, 0))

    # Pretty label for the comparison source ("last week" vs "since Apr 24")
    if last_week_snap:
        baseline_label = "from last week"
    elif using_first_snapshot and first_snapshot_date_str:
        d = _parse_date(first_snapshot_date_str)
        baseline_label = f"since {d.strftime('%b %-d')}" if d else "since first snapshot"
    else:
        baseline_label = None

    stage_cards = []
    for s in BACKLOG_STAGES_ORDERED:
        cur = stage_current.get(s, 0)
        prev = stage_baseline.get(s)
        delta = (cur - prev) if prev is not None else None

        # Context note: stage is empty NOW but had items in the baseline
        empty_with_history = (cur == 0 and prev is not None and prev > 0)
        empty_note = None
        if empty_with_history:
            if s == "IT Prioritization":
                empty_note = "all moved forward in the pipeline"
            elif s == "Triage":
                empty_note = "all classified and progressed"
            elif s == "New Request":
                empty_note = "all picked up for triage"
            else:
                empty_note = "all moved to next stage"

        stage_cards.append({
            "name": s,
            "count": cur,
            "delta": delta,                      # None if no baseline at all
            "baseline_label": baseline_label,    # "from last week" / "since Apr 24" / None
            "empty_note": empty_note,            # short explanation when count=0 but had history
            "color": STAGE_COLOR_MAP.get(s, "#888"),
            "slug": s.lower().replace(" ", "_").replace("/", "_"),
        })

    # Backlog equation — week-over-week
    monday_this_week_dt = monday_this_week
    sunday_last_week_dt = monday_this_week_dt - timedelta(days=1)

    intakes_this_week = sum(
        1 for i in items
        if _in_range(i, monday_this_week_dt, today + timedelta(days=1))
    )
    completed_this_week = sum(
        1 for i in items
        if _completed_in_range(i, monday_this_week_dt, today + timedelta(days=1))
    )
    closed_at_review_this_week = sum(
        1 for i in items
        if _closed_at_review_in_range(i, monday_this_week_dt, today + timedelta(days=1))
    )

    # Prior backlog: total in active stages as of last Sunday end-of-day
    if last_week_snap:
        prior_backlog = int(last_week_snap.get("backlog_total", sum(stage_baseline.values())))
    else:
        # Fallback: derive from current = prior + intakes - completed - closed
        prior_backlog = max(0, len(backlog_items) - intakes_this_week + completed_this_week + closed_at_review_this_week)

    current_backlog = len(backlog_items)
    backlog_delta = current_backlog - prior_backlog

    # ── Outcomes (trailing 4 weeks based on relevant exit date) ────────────
    # Mutually exclusive: an item appears in exactly ONE outcome bucket.
    # Rejected and EPMO are tracked separately — they are NOT the same thing.
    four_weeks_ago = today - timedelta(weeks=4)

    def _is_rejected(i):
        return (
            i.get("coe_classification") == "Rejected"
            or i.get("coe_stage") in ESCALATED_STAGES   # legacy "Escalated/rejected"
            or i.get("coe_stage") == "Rejected"
        )

    def _is_pushed_to_epmo(i):
        return i.get("coe_classification") in EPMO_CLASSIFICATIONS

    outcome_rejected = sum(
        1 for i in items
        if _is_rejected(i)
        and _exit_date_in_range(i, four_weeks_ago, today + timedelta(days=1))
    )

    outcome_pushed_to_epmo = sum(
        1 for i in items
        if _is_pushed_to_epmo(i)
        and not _is_rejected(i)
        and _exit_date_in_range(i, four_weeks_ago, today + timedelta(days=1))
    )

    outcome_closed_at_review = sum(
        1 for i in items
        if not _is_rejected(i)
        and not _is_pushed_to_epmo(i)
        and _closed_at_review_in_range(i, four_weeks_ago, today + timedelta(days=1))
    )

    outcome_on_hold = sum(
        1 for i in items
        if _date_in_range(i.get("project_paused"), four_weeks_ago, today + timedelta(days=1))
    )

    outcome_delivered = sum(
        1 for i in items
        if i.get("completed")
        and i.get("coe_classification") != "Rejected"
        and i.get("status_color") != "dropped"
        and _completed_in_range(i, four_weeks_ago, today + timedelta(days=1))
    )

    # ── Stacked area chart series (last 8 weeks of snapshots) ──────────────
    area_series = _build_area_series(history_snapshots, today, weeks=8)

    # New intakes this week vs last week (for the +N badge)
    intakes_last_week = sum(
        1 for i in items
        if _in_range(i, monday_last_week, monday_this_week_dt)
    )
    completed_last_week = sum(
        1 for i in items
        if _completed_in_range(i, monday_last_week, monday_this_week_dt)
    )
    closed_last_week = sum(
        1 for i in items
        if _closed_at_review_in_range(i, monday_last_week, monday_this_week_dt)
    )

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
        "donut_segments": donut_segments,
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

        # Timeline — all period stats expressed as per-period intakes/reviews/cycle/gate/escalated
        "tw_intakes": tw["intakes"],
        "tw_reviews": tw["reviews"],
        "tw_avg_cycle": str(tw["avg_cycle"]) if tw["avg_cycle"] is not None else "—",
        "tw_gate": tw["gate"],
        "tw_escalated": tw["escalated"],

        "lw_intakes": lw["intakes"],
        "lw_reviews": lw["reviews"],
        "lw_avg_cycle": str(lw["avg_cycle"]) if lw["avg_cycle"] is not None else "—",
        "lw_gate": lw["gate"],
        "lw_escalated": lw["escalated"],
        "lw_has_reviews": lw["reviews"] > 0,

        "tm_intakes": tm["intakes"],
        "tm_reviewed": tm["reviews"],
        "tm_avg_cycle": str(tm["avg_cycle"]) if tm["avg_cycle"] is not None else "—",
        "tm_escalated": tm["escalated"],
        "tm_gate": tm["gate"],

        "lm_intakes": lm["intakes"],
        "lm_reviews": lm["reviews"],
        "lm_avg_cycle": str(lm["avg_cycle"]) if lm["avg_cycle"] is not None else "—",
        "lm_escalated": lm["escalated"],
        "lm_has_coe": last_month_has_coe,

        "six_mo_intakes": six_mo["intakes"],
        "six_mo_reviews": six_mo["reviews"],
        "six_mo_avg_cycle": str(six_mo["avg_cycle"]) if six_mo["avg_cycle"] is not None else "—",

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
        "rec_no_color_count": len(no_color),
        "rec_ba_count": ba_count,

        # Dynamic date labels
        "tw_window_label": tw_window,
        "lw_window_label": lw_window,
        "tm_month_name": tm_month_name,
        "tm_window_label": tm_window,
        "lm_month_name": lm_month_name,
        "lm_window_label": lm_window,
        "six_mo_window_label": six_mo_label,
        "top_work_type": top_wt_name,
        "flow_peak_week_label": flow_peak_week_label,
        "flow_peak_count": peak_week_count,
        "flow_w_minus3_range": flow_w_minus3_range,
        "flow_w_minus2_range": flow_w_minus2_range,
        "flow_w_minus1_range": flow_w_minus1_range,
        "flow_w_current_range": flow_w_current_range,
        "pending_received_label": pending_received_label,
        "coe_start_display": coe_start_display,

        # Static
        "coe_start_date": COE_START_DATE.isoformat(),

        # ── §06 v2 — Backlog flow / stages / outcomes / area chart ──────────
        "stage_current": stage_current,
        "stage_cards": stage_cards,
        "backlog_total": current_backlog,
        "backlog_prior": prior_backlog,
        "backlog_delta": backlog_delta,
        "backlog_intakes_this_week": intakes_this_week,
        "backlog_completed_this_week": completed_this_week,
        "backlog_closed_this_week": closed_at_review_this_week,
        "intakes_last_week": intakes_last_week,
        "completed_last_week": completed_last_week,
        "closed_last_week": closed_last_week,
        "has_history": bool(history_snapshots),
        "outcome_closed_at_review": outcome_closed_at_review,
        "outcome_rejected": outcome_rejected,
        "outcome_pushed_to_epmo": outcome_pushed_to_epmo,
        "outcome_on_hold": outcome_on_hold,
        "outcome_delivered": outcome_delivered,
        "area_chart": area_series,
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


def _reviewed_in_range(item: dict, start: date, end: date) -> bool:
    """True if item's first_review_date falls in [start, end)."""
    frd = _parse_date(item.get("first_review_date"))
    if not frd:
        return False
    return start <= frd < end


def _period_stats(items: list[dict], start: date, end: date) -> dict:
    """
    Per-period stats — intakes by received_date, reviews by first_review_date.

    All durations in business days.
    """
    intake_items = [i for i in items if _in_range(i, start, end)]
    review_items = [i for i in items if _reviewed_in_range(i, start, end)]

    # Substantive cycle times among reviews completed in range
    cycle_bds = []
    for i in review_items:
        tags = i.get("first_review_tags") or []
        if not _is_substantive(tags):
            continue
        rd = _parse_date(i.get("received_date"))
        frd = _parse_date(i.get("first_review_date"))
        if rd and frd and frd >= rd:
            cycle_bds.append(business_days_between(rd, frd))

    avg_cycle = round(statistics.mean(cycle_bds), 1) if cycle_bds else None

    gate_items = [
        i for i in review_items
        if _is_closed_at_gate(i.get("first_review_tags") or [])
    ]

    escalated_items = [
        i for i in review_items
        if i.get("coe_stage") in ESCALATED_STAGES
        or i.get("coe_classification") == "Rejected"
    ]

    return {
        "intakes": len(intake_items),
        "reviews": len(review_items),
        "avg_cycle": avg_cycle,
        "gate": len(gate_items),
        "escalated": len(escalated_items),
    }


def _build_donut_segments(stage_counts: dict, total: int) -> list[dict]:
    """
    Build a list of donut segments, one per stage with at least 1 open item.
    Sorted by count desc so the biggest slice starts at the top of the circle.

    Each segment: {name, count, dasharray, dashoffset, stroke (CSS), gradient_id}.
    """
    if total == 0:
        return []

    sorted_stages = sorted(
        ((name, count) for name, count in stage_counts.items() if count > 0),
        key=lambda kv: kv[1],
        reverse=True,
    )

    segments = []
    cumulative = 0.0
    for idx, (name, count) in enumerate(sorted_stages):
        pct = round(count / total * 100, 1)
        # First segment: dashoffset = 25 (start at top). Subsequent segments offset
        # by the cumulative percentage already placed (negative).
        if idx == 0:
            offset = 25.0
        else:
            offset = round(25.0 - cumulative, 1)

        color = STAGE_COLOR_PALETTE[idx % len(STAGE_COLOR_PALETTE)]
        gradient_id = f"donut-grad-{idx}"

        segments.append({
            "name": name,
            "count": count,
            "pct": pct,
            "dasharray": pct,
            "dashoffset": offset,
            "stroke_css": color["css"],
            "gradient_id": gradient_id,
            "hex_start": color["hex_start"],
            "hex_end": color["hex_end"],
        })
        cumulative += pct

    return segments


def _donut_dasharrays(total: int, it_prio: int, triage: int, new_req: int):
    """Compute SVG stroke-dasharray values for donut chart segments."""
    if total == 0:
        return (0, 0, 0)
    it_da = round(it_prio / total * 100, 1)
    tr_da = round(triage / total * 100, 1)
    nr_da = round(new_req / total * 100, 1)
    return (it_da, tr_da, nr_da)


# ── Date / range helpers used by the new §06 flow section ─────────────────────

def _completed_in_range(item: dict, start: date, end: date) -> bool:
    """True if the item completed in [start, end). Tries completed_at first,
    then completed_date custom field, then deployed."""
    for key in ("completed_at", "completed_date", "deployed"):
        d = _parse_date((item.get(key) or "")[:10] if item.get(key) else None)
        if d and start <= d < end:
            return True
    return False


def _closed_at_review_in_range(item: dict, start: date, end: date) -> bool:
    """True if the item was closed at the gate (Already Completed / No Needed /
    Not Needed) and its first review happened in [start, end)."""
    tags = item.get("first_review_tags") or []
    if not _is_closed_at_gate(tags):
        return False
    frd = _parse_date(item.get("first_review_date"))
    return bool(frd and start <= frd < end)


def _exit_date_in_range(item: dict, start: date, end: date) -> bool:
    """For EPMO push: use classification_date or first_review_date as exit."""
    for key in ("classification_date", "first_review_date"):
        d = _parse_date(item.get(key))
        if d and start <= d < end:
            return True
    return False


def _date_in_range(value, start: date, end: date) -> bool:
    d = _parse_date(value)
    return bool(d and start <= d < end)


# ── History helpers ──────────────────────────────────────────────────────────

def _load_history_for_metrics() -> list[dict]:
    """Lazy import to avoid circular dep with src.history."""
    try:
        from src.history import load_history
        return load_history()
    except Exception:
        return []


def _find_snapshot_n_days_ago(snapshots: list[dict], today: date, n: int) -> dict | None:
    """Find the snapshot whose date is closest to (today - n days), within
    a 3-day tolerance. Returns the metrics dict from that snapshot or None."""
    target = today - timedelta(days=n)
    best, best_diff = None, 4
    for snap in snapshots:
        snap_date_str = snap.get("date") or ""
        d = _parse_date(snap_date_str)
        if not d:
            continue
        diff = abs((d - target).days)
        if diff < best_diff:
            best_diff = diff
            best = snap.get("metrics", {})
    return best


def _find_first_snapshot_before(snapshots: list[dict], today: date):
    """Return (metrics_dict, date_str) of the oldest snapshot dated strictly
    before today. Returns (None, None) if none exists."""
    candidates = []
    for snap in snapshots:
        snap_date_str = snap.get("date") or ""
        d = _parse_date(snap_date_str)
        if d and d < today:
            candidates.append((d, snap))
    if not candidates:
        return None, None
    candidates.sort(key=lambda kv: kv[0])  # oldest first
    oldest_date, oldest_snap = candidates[0]
    return oldest_snap.get("metrics", {}), oldest_date.isoformat()


def _build_area_series(snapshots: list[dict], today: date, weeks: int = 8) -> dict:
    """
    Build the data points for the stacked area chart.

    Returns:
      {
        "labels": ["W10","W11",...],
        "stages": [
          {"name": "New Request",        "color": "...", "values": [int,...]},
          {"name": "Triage",             ...},
          ...
        ],
        "y_max": int,                    # for SVG scaling
        "polygons": [str,...],           # SVG points strings, one per stage
        "width": int, "height": int,
      }
    """
    # Anchor weeks: weeks = N most-recent ISO weeks ending with the current
    monday_this_week = today - timedelta(days=today.weekday())
    week_anchors = [monday_this_week - timedelta(weeks=(weeks - 1 - i)) for i in range(weeks)]

    labels = [f"W{a.isocalendar()[1]}" for a in week_anchors]

    # For each anchor week, find the closest snapshot whose date falls in
    # [anchor, anchor+7days). Use most-recent snapshot in that window.
    weekly_stage_counts: list[dict] = []
    for a in week_anchors:
        end = a + timedelta(days=7)
        candidates = []
        for snap in snapshots:
            d = _parse_date(snap.get("date") or "")
            if d and a <= d < end:
                candidates.append((d, snap))
        if candidates:
            candidates.sort(key=lambda kv: kv[0], reverse=True)
            metrics = candidates[0][1].get("metrics", {})
            stage_counts_map = metrics.get("stage_current", {}) or {}
        else:
            stage_counts_map = {}

        weekly_stage_counts.append({
            s: int(stage_counts_map.get(s, 0)) for s in BACKLOG_STAGES_ORDERED
        })

    # If today's week has no snapshot yet (we haven't run today), fill it from
    # current state passed in implicitly via... hmm — caller will overwrite.
    stages_out = []
    for s in BACKLOG_STAGES_ORDERED:
        stages_out.append({
            "name": s,
            "color": STAGE_COLOR_MAP.get(s, "#888"),
            "values": [w[s] for w in weekly_stage_counts],
        })

    # Compute totals per week for y-axis max
    week_totals = [sum(w.values()) for w in weekly_stage_counts]
    y_max = max(week_totals) if any(week_totals) else 10
    # Add a little headroom and round up to nearest 5
    y_max = max(10, ((y_max // 5) + 1) * 5)

    # SVG canvas dimensions
    width, height = 720, 280
    pad_left, pad_right, pad_top, pad_bottom = 40, 20, 16, 36

    # Build polygons (stacked from bottom up: New Request first)
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    if weeks > 1:
        x_for = lambda i: pad_left + (plot_w * i / (weeks - 1))
    else:
        x_for = lambda i: pad_left + plot_w / 2
    y_for = lambda v: pad_top + plot_h - (v / y_max * plot_h) if y_max else pad_top + plot_h

    cumulative = [0] * weeks
    polygons = []
    for stage in stages_out:
        bottom = list(cumulative)
        cumulative = [bottom[i] + stage["values"][i] for i in range(weeks)]
        # Build polygon: top edge left→right, then bottom edge right→left
        top_pts = [f"{x_for(i):.1f},{y_for(cumulative[i]):.1f}" for i in range(weeks)]
        bot_pts = [f"{x_for(i):.1f},{y_for(bottom[i]):.1f}" for i in range(weeks - 1, -1, -1)]
        polygons.append(" ".join(top_pts + bot_pts))

    # X-axis labels positions
    x_labels = [{"x": x_for(i), "label": labels[i]} for i in range(weeks)]
    # Y-axis ticks (0, mid, max)
    y_ticks = [0, y_max // 2, y_max]
    y_label_positions = [{"y": y_for(v), "label": str(v)} for v in y_ticks]

    return {
        "labels": labels,
        "stages": stages_out,
        "polygons": polygons,
        "y_max": y_max,
        "x_labels": x_labels,
        "y_labels": y_label_positions,
        "width": width,
        "height": height,
        "pad_left": pad_left,
        "pad_top": pad_top,
        "plot_w": plot_w,
        "plot_h": plot_h,
        "has_data": any(week_totals),
        "weeks_with_data": sum(1 for t in week_totals if t > 0),
    }
