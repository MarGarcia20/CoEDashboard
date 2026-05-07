"""
Asana API client — fetches CoE Portfolio items with all custom fields.
Uses plain requests + PAT auth. No Asana SDK.
"""

import json
import os
import sys

import requests

PORTFOLIO_GID = "1214057614427291"
EXCLUDE_GID = "1214064295588748"  # CoE - Migration Requirements Log

CUSTOM_FIELD_GIDS = {
    "created_on": "1214074365466540",
    "received_date": "1214209865999072",
    "first_review_date": "1214209868756759",
    "ba_assigned": "1214210168318475",
    "first_review": "1214210153504061",
    "coe_stage": "1214061494576315",
    "coe_classification": "1214057968804957",
    "pm_assigned": "1210474554240546",
    "priority": "1214593752433962",  # CoE Priority (replaces old "Priority" 1206729686320253)
    "project_paused": "1214267182280877",
    "deployed": "1214267165903924",
    "completed_date": "1208524309563086",
    "classification_date": "1214083489074997",
    "it_prioritization_date": "1214205709219888",
    "start_date": "1205996528539007",        # IT "In Progress" start
    "uat_start": "1214267250385733",          # UAT/Testing start
}

BASE_URL = "https://app.asana.com/api/1.0"


def _get_headers(pat: str) -> dict:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/json",
    }


def _get(pat: str, url: str, params: dict = None) -> dict:
    resp = requests.get(url, headers=_get_headers(pat), params=params, timeout=30)
    if not resp.ok:
        print(f"ERROR: Asana API returned {resp.status_code} for {url}", file=sys.stderr)
        print(f"       {resp.text[:400]}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def _extract_custom_field(item: dict, field_name: str):
    """Extract a custom field value from an item by GID."""
    gid = CUSTOM_FIELD_GIDS.get(field_name)
    for cf in item.get("custom_fields", []):
        if cf.get("gid") == gid:
            field_type = cf.get("type")
            if field_type == "date":
                return cf.get("date_value", {}).get("date") if cf.get("date_value") else None
            elif field_type == "enum":
                ev = cf.get("enum_value")
                return ev.get("name") if ev else None
            elif field_type == "multi_enum":
                return [e.get("name") for e in cf.get("multi_enum_values", []) if e.get("name")]
            elif field_type == "text":
                return cf.get("text_value")
            elif field_type == "people":
                # Returns a comma-separated string of names so downstream
                # metrics logic (which splits on ",") keeps working unchanged.
                people = cf.get("people_value") or []
                names = [p.get("name") for p in people if p.get("name")]
                return ", ".join(names) if names else None
            else:
                return cf.get("display_value")
    return None


def _normalize_item(raw: dict) -> dict:
    """Flatten a raw Asana portfolio item into a clean dict."""
    status = raw.get("current_status") or {}
    return {
        "gid": raw.get("gid"),
        "name": raw.get("name"),
        "completed": raw.get("completed", False),
        "completed_at": raw.get("completed_at"),
        "status_color": status.get("color"),
        "created_on": _extract_custom_field(raw, "created_on"),
        "received_date": _extract_custom_field(raw, "received_date"),
        "first_review_date": _extract_custom_field(raw, "first_review_date"),
        "ba_assigned": _extract_custom_field(raw, "ba_assigned"),
        "first_review_tags": _extract_custom_field(raw, "first_review") or [],
        "coe_stage": _extract_custom_field(raw, "coe_stage"),
        "coe_classification": _extract_custom_field(raw, "coe_classification"),
        "pm_assigned": _extract_custom_field(raw, "pm_assigned"),
        "priority": _extract_custom_field(raw, "priority"),
        "project_paused": _extract_custom_field(raw, "project_paused"),
        "deployed": _extract_custom_field(raw, "deployed"),
        "completed_date": _extract_custom_field(raw, "completed_date"),
        "classification_date": _extract_custom_field(raw, "classification_date"),
        "it_prioritization_date": _extract_custom_field(raw, "it_prioritization_date"),
        "start_date": _extract_custom_field(raw, "start_date"),
        "uat_start": _extract_custom_field(raw, "uat_start"),
    }


def fetch_portfolio_items(pat: str, verbose: bool = False) -> list[dict]:
    """
    Fetch all items from the CoE Portfolio, excluding the MRL log.
    Returns a list of normalized item dicts.
    """
    opt_fields = ",".join([
        "name", "completed", "completed_at", "current_status.color",
        "custom_fields.gid", "custom_fields.type", "custom_fields.name",
        "custom_fields.display_value", "custom_fields.text_value",
        "custom_fields.date_value", "custom_fields.enum_value.name",
        "custom_fields.multi_enum_values.name",
        "custom_fields.people_value.name",
    ])

    url = f"{BASE_URL}/portfolios/{PORTFOLIO_GID}/items"
    params = {"opt_fields": opt_fields, "limit": 100}

    all_items = []
    while url:
        data = _get(pat, url, params)
        all_items.extend(data.get("data", []))
        next_page = data.get("next_page") or {}
        url = next_page.get("uri")
        params = None  # pagination URI already has params

    # Exclude the Migration Requirements Log
    filtered = [i for i in all_items if i.get("gid") != EXCLUDE_GID]

    normalized = [_normalize_item(i) for i in filtered]

    if verbose:
        print(f"  Fetched {len(all_items)} items from Asana, excluded 1 MRL → {len(normalized)} items")

    return normalized


def load_fixture(path: str, verbose: bool = False) -> list[dict]:
    """Load items from a JSON fixture file (--dry-run mode)."""
    with open(path) as f:
        raw = json.load(f)
    items = raw if isinstance(raw, list) else raw.get("data", [])
    normalized = [_normalize_item(i) for i in items if i.get("gid") != EXCLUDE_GID]
    if verbose:
        print(f"  Loaded {len(normalized)} items from fixture: {path}")
    return normalized
