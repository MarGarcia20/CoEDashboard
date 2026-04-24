"""
Renders dashboard.jinja with live metrics context.
Handles all derived display values (spelled numbers, bar widths, etc.)
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from src.metrics import WORK_TYPE_SLUGS, WORK_TYPE_GROUPS

# ── Constants ─────────────────────────────────────────────────────────────────

# Qualitative meter pin position for §07 (editorial, not computed)
METER_PIN_POSITION = "42%"

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
OUTPUT_PATH = Path(__file__).parent.parent / "output" / "index.html"
PREVIEW_PATH = Path(__file__).parent.parent / "output" / "preview.html"


# ── Number helpers ────────────────────────────────────────────────────────────

_ONES = [
    "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def num_to_words(n: int) -> str:
    """Convert integer 0–100 to English words. Capitalised for editorial use."""
    if n == 0:
        return "zero"
    if n == 100:
        return "one hundred"
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return (_TENS[tens] + ("-" + _ONES[ones] if ones else "")).strip()


def num_to_words_cap(n: int) -> str:
    return num_to_words(n).capitalize()


# ── Context builder ───────────────────────────────────────────────────────────

def build_context(metrics: dict, today: date | None = None) -> dict:
    today = today or date.today()

    # Render in UTC with explicit timezone so the JS in the browser can
    # convert to the viewer's local timezone. Previously used datetime.now()
    # which returned the server's clock (UTC on GitHub Actions) labeled as if
    # it were local — causing "9:36 PM" when the user was at 4:36 PM.
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(ZoneInfo("America/New_York"))

    # snapshot_iso is consumed by JS new Date() — must be ISO 8601 with offset
    snapshot_iso = now_utc.isoformat(timespec="seconds")

    # Server-side fallback strings (shown on first paint before JS converts).
    # Use ET so North American viewers see a sensible approximation.
    snapshot_timestamp = now_et.strftime("%B %-d, %Y · %-I:%M %p ET")
    snapshot_eyebrow = f"Snapshot · {now_et.strftime('%B %-d')} · {now_et.strftime('%-I:%M %p ET')}"
    snapshot_banner_text = f"taken {now_et.strftime('%B %-d, %Y')} at {now_et.strftime('%-I:%M %p ET')}"

    total = metrics["total"]
    escalated_count = metrics["escalated_count"]
    gate_count = metrics["yield_gate"]
    gate_pct_num = round(gate_count / total * 100) if total else 0

    # Hero subtitle numbers spelled out
    hero_total_spelled = num_to_words_cap(total)
    hero_cycle_bd = metrics["review_avg"]
    hero_gate_pct_spelled = num_to_words_cap(gate_pct_num)

    # W-labels for flow section
    w_current = metrics["w_current"]
    w_minus1 = metrics["w_minus1"]
    w_minus2 = metrics["w_minus2"]
    w_minus3 = metrics["w_minus3"]

    flow_weeks = metrics["flow_weeks"]
    flow_labels = metrics["flow_week_labels"]
    flow_pcts = metrics["flow_bar_pcts"]

    # Work type cards
    wt_max = metrics["work_type_max"]
    wt_data = {}
    for group_name, slug in WORK_TYPE_SLUGS.items():
        count = metrics["work_type_counts"].get(group_name, 0)
        pct = round(count / total * 100) if total else 0
        bar_width = f"{round(count / wt_max * 100)}%" if wt_max else "0%"
        wt_data[slug] = {
            "count": count,
            "pct": f"{pct}%",
            "bar_width": bar_width,
        }

    # PM percentages
    mar_count = metrics["team_mar_count"]
    david_count = metrics["team_david_count"]
    mar_pct = round(mar_count / total * 100) if total else 0
    david_pct = round(david_count / total * 100) if total else 0

    # §08 section title (dynamic)
    team_section_title = f"{mar_count} and {david_count} projects."

    # Footer stats line
    footer_stats = (
        f"{total} requests · {metrics['review_avg']} bd review · "
        f"{gate_pct_num}% rejected at gate · {metrics['delivered_count']} delivered"
    )

    # Sweet spot spelled
    sweet_spot_it_prio_count_word = num_to_words(metrics["rec_it_prio_count"])

    ctx = {
        # Snapshot
        "snapshot_iso": snapshot_iso,
        "snapshot_timestamp": snapshot_timestamp,
        "snapshot_eyebrow": snapshot_eyebrow,
        "snapshot_banner_text": snapshot_banner_text,

        # Hero
        "hero_total_spelled": hero_total_spelled,
        "hero_cycle_bd": hero_cycle_bd,
        "hero_gate_pct_spelled": hero_gate_pct_spelled,
        "hero_gate_pct_num": gate_pct_num,

        # §01 KPIs
        "kpi_review_avg": metrics["review_avg"],
        "kpi_review_median": metrics["review_median"],
        "kpi_review_range_low": metrics["review_min"],
        "kpi_review_range_high": metrics["review_max"],
        "kpi_review_substantive_count": metrics["review_substantive_count"],
        "kpi_backlog_open": metrics["open_count"],
        "kpi_backlog_total": total,
        "kpi_backlog_real_work": metrics["yield_substantive"],
        "kpi_ba_pending_total": metrics["ba_pending_total"],
        "kpi_ba_avg": metrics["ba_avg"],
        "kpi_ba_count": metrics["ba_count"],
        "kpi_w_current": w_current,
        "kpi_w_current_intakes": metrics["tw_intakes"],
        "kpi_w_minus1": w_minus1,
        "kpi_w_minus1_intakes": metrics["lw_intakes"],
        "kpi_escalated": metrics["escalated_count"],
        "kpi_escalated_pct": metrics["escalated_pct"],
        "kpi_delivered": metrics["delivered_count"],
        "kpi_priority_set": metrics["priority_set_count"],
        "kpi_priority_total": total,
        "kpi_priority_unset": metrics["priority_unset_count"],

        # §02 Timeline — per-period stats (intakes by received_date, reviews by first_review_date)
        "timeline_w_current": w_current,
        "timeline_w_current_intakes": metrics["tw_intakes"],
        "timeline_w_current_reviews": metrics["tw_reviews"],
        "timeline_w_current_cycle": metrics["tw_avg_cycle"],
        "timeline_w_current_gate": metrics["tw_gate"],

        "timeline_w_minus1": w_minus1,
        "timeline_w_minus1_intakes": metrics["lw_intakes"],
        "timeline_w_minus1_reviews": metrics["lw_reviews"],
        "timeline_w_minus1_cycle": metrics["lw_avg_cycle"],
        "timeline_w_minus1_has_reviews": metrics["lw_has_reviews"],

        "timeline_month_intakes": metrics["tm_intakes"],
        "timeline_month_reviewed": metrics["tm_reviewed"],
        "timeline_month_avg_cycle": metrics["tm_avg_cycle"],
        "timeline_month_escalated": metrics["tm_escalated"],

        "timeline_lm_intakes": metrics["lm_intakes"],
        "timeline_lm_reviews": metrics["lm_reviews"],
        "timeline_lm_avg_cycle": metrics["lm_avg_cycle"],
        "timeline_lm_escalated": metrics["lm_escalated"],
        "timeline_lm_has_coe": metrics["lm_has_coe"],

        "timeline_6mo_intakes": metrics["six_mo_intakes"],
        "timeline_6mo_reviews": metrics["six_mo_reviews"],
        "timeline_6mo_days_pre_coe": metrics["pre_coe_days"],
        "timeline_6mo_days_active": metrics["days_coe_active"],
        "timeline_6mo_avg_cycle": metrics["six_mo_avg_cycle"],

        # §04 + §06 header dynamics
        "top_work_type": metrics.get("top_work_type") or "No classification yet",
        "flow_peak_week_label": metrics["flow_peak_week_label"],
        "flow_peak_count": metrics["flow_peak_count"],

        # §03 Pipeline
        "pipeline_upstream_bd": metrics["upstream_avg"],
        "pipeline_review_bd": metrics["review_avg"],

        # §04 Classification
        "wt": wt_data,

        # §05 Yield
        "yield_substantive": metrics["yield_substantive"],
        "yield_substantive_pct": metrics["yield_substantive_pct"],
        "yield_gate": metrics["yield_gate"],
        "yield_gate_pct": metrics["yield_gate_pct"],
        "yield_pending": metrics["yield_pending"],
        "yield_pending_pct": metrics["yield_pending_pct"],
        "yield_pending_names": metrics["yield_pending_names"],

        # §06 Flow — bar chart
        "flow_w_minus3_label": f"W{w_minus3}",
        "flow_w_minus2_label": f"W{w_minus2}",
        "flow_w_minus1_label": f"W{w_minus1}",
        "flow_w_current_label": f"W{w_current}",
        "flow_w_minus3_count": flow_weeks.get(w_minus3, 0),
        "flow_w_minus2_count": flow_weeks.get(w_minus2, 0),
        "flow_w_minus1_count": flow_weeks.get(w_minus1, 0),
        "flow_w_current_count": flow_weeks.get(w_current, 0),
        "flow_w_minus3_bar": flow_pcts[0] if len(flow_pcts) > 0 else "0%",
        "flow_w_minus2_bar": flow_pcts[1] if len(flow_pcts) > 1 else "0%",
        "flow_w_minus1_bar": flow_pcts[2] if len(flow_pcts) > 2 else "0%",
        "flow_w_current_bar": flow_pcts[3] if len(flow_pcts) > 3 else "0%",

        # §06 Donut
        "donut_total_open": metrics["donut_total_open"],
        "donut_segments": metrics["donut_segments"],
        "donut_it_prio": metrics["donut_it_prio"],
        "donut_triage": metrics["donut_triage"],
        "donut_new_request": metrics["donut_new_request"],
        "donut_it_prio_dasharray": metrics["donut_it_prio_dasharray"],
        "donut_triage_dasharray": metrics["donut_triage_dasharray"],
        "donut_new_request_dasharray": metrics["donut_new_request_dasharray"],
        "donut_it_prio_dashoffset": metrics["donut_it_prio_dashoffset"],
        "donut_triage_dashoffset": metrics["donut_triage_dashoffset"],
        "donut_new_request_dashoffset": metrics["donut_new_request_dashoffset"],

        # §07 Sweet spot
        "sweet_spot_it_prio_count_word": sweet_spot_it_prio_count_word,
        "meter_pin_position": METER_PIN_POSITION,

        # §08 Team
        "team_mar_count": mar_count,
        "team_mar_pct": f"{mar_pct}%",
        "team_david_count": david_count,
        "team_david_pct": f"{david_pct}%",
        "team_section_title": team_section_title,

        # §09 Recs
        "rec_it_prio_count": metrics["rec_it_prio_count"],
        "rec_status_color_blank": metrics["rec_status_color_blank"],
        "rec_workload_note": metrics["rec_workload_note"],

        # Footer
        "footer_stats": footer_stats,

        # Dynamic date labels (from metrics)
        "tw_window_label": metrics["tw_window_label"],
        "lw_window_label": metrics["lw_window_label"],
        "tm_month_name": metrics["tm_month_name"],
        "tm_window_label": metrics["tm_window_label"],
        "lm_month_name": metrics["lm_month_name"],
        "lm_window_label": metrics["lm_window_label"],
        "six_mo_window_label": metrics["six_mo_window_label"],
        "flow_w_minus3_range": metrics["flow_w_minus3_range"],
        "flow_w_minus2_range": metrics["flow_w_minus2_range"],
        "flow_w_minus1_range": metrics["flow_w_minus1_range"],
        "flow_w_current_range": metrics["flow_w_current_range"],
        "pending_received_label": metrics["pending_received_label"],
        "coe_start_display": metrics["coe_start_display"],
    }

    return ctx


def render(metrics: dict, today: date | None = None, verbose: bool = False, preview: bool = False) -> Path:
    """
    Render the Jinja template with computed context.

    When preview=True, writes to output/preview.html (gitignored local-only file).
    When preview=False, writes to output/index.html (what Vercel serves).
    """
    ctx = build_context(metrics, today)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=StrictUndefined,
        autoescape=False,
    )
    template = env.get_template("dashboard.jinja")
    html = template.render(**ctx)

    target = PREVIEW_PATH if preview else OUTPUT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")

    if verbose:
        print(f"  Rendered → {target}")

    return target
