#!/usr/bin/env python3
"""
CoE Dashboard refresh script.

Usage:
  python run.py              # Pull from Asana, write output/index.html
  python run.py --dry-run    # Use fixture data, write output/index.html
  python run.py --verbose    # Log every metric to stdout
"""

import argparse
import sys
import time
from datetime import date, datetime
from pathlib import Path

# Allow running from project root without installing
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
import os

from src.asana_client import fetch_portfolio_items, load_fixture
from src.history import save_snapshot
from src.metrics import compute_metrics
from src.renderer import render

FIXTURE_PATH = Path(__file__).parent / "tests" / "fixtures" / "sample_asana_response.json"


def main():
    parser = argparse.ArgumentParser(description="Refresh CoE dashboard HTML")
    parser.add_argument("--dry-run", action="store_true", help="Use fixture data instead of Asana")
    parser.add_argument("--verbose", action="store_true", help="Log all metrics to stdout")
    args = parser.parse_args()

    start = time.time()
    today = date.today()
    now = datetime.now()

    print(f"\n{'─' * 56}")
    print(f"  CoE Dashboard Refresh · {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'─' * 56}")

    # ── Load data ────────────────────────────────────────────
    if args.dry_run:
        print(f"\n  Mode: DRY RUN (fixture)")
        items = load_fixture(str(FIXTURE_PATH), verbose=True)
    else:
        print(f"\n  Mode: LIVE (Asana)")
        load_dotenv()
        pat = os.getenv("ASANA_PAT")
        if not pat:
            print("ERROR: ASANA_PAT not set. Copy .env.example → .env and add your token.", file=sys.stderr)
            sys.exit(1)
        items = fetch_portfolio_items(pat, verbose=True)

    print(f"  Items loaded: {len(items)}")

    # ── Compute metrics ──────────────────────────────────────
    print(f"\n  Computing metrics...")
    metrics = compute_metrics(items, today=today, verbose=args.verbose)

    if args.verbose:
        print()

    # ── Key metrics summary ───────────────────────────────────
    print(f"  Total requests:      {metrics['total']}")
    print(f"  Open backlog:        {metrics['open_count']}")
    print(f"  Delivered:           {metrics['delivered_count']}")
    print(f"  Escalated/rejected:  {metrics['escalated_count']}")
    print(f"  Review avg (bd):     {metrics['review_avg']}")
    print(f"  Upstream avg (bd):   {metrics['upstream_avg']}")
    print(f"  Substantive reviews: {metrics['review_substantive_count']}")
    print(f"  Priority set:        {metrics['priority_set_count']} of {metrics['total']}")
    print(f"  Yield — gate:        {metrics['yield_gate']} ({metrics['yield_gate_pct']})")
    print(f"  PM Mar:              {metrics['team_mar_count']}")
    print(f"  PM David:            {metrics['team_david_count']}")

    # ── Render ───────────────────────────────────────────────
    print(f"\n  Rendering template...")
    output_path = render(metrics, today=today, verbose=True)

    # ── Archive snapshot ─────────────────────────────────────
    print(f"\n  Archiving snapshot...")
    save_snapshot(metrics, today, verbose=True)

    elapsed = time.time() - start
    print(f"\n{'─' * 56}")
    print(f"  Done in {elapsed:.1f}s → {output_path}")
    print(f"{'─' * 56}\n")


if __name__ == "__main__":
    main()
