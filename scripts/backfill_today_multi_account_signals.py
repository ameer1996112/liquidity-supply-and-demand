#!/usr/bin/env python3
"""
Backfill today's unscoped LIVE global-rejection rows into per-account rows.

This script targets historical rows created before the worker started fanning
out global LIVE rejections (filtered / staleness / holiday / swap) across all
active LIVE broker profiles.

Strategy:
  - find today's candidate rows where broker_profile_id/account_name are NULL
  - load active LIVE broker profiles
  - update the original row to the first active profile
  - insert clones for the remaining active profiles

Preview is the default. Use --apply to perform the backfill.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


GLOBAL_STATUSES = (
    "filtered",
    "staleness_rejected",
    "holiday_rejected",
    "swap_rejected",
)


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _get_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _supabase_request(
    method: str,
    path: str,
    *,
    payload: dict | list[dict] | None = None,
    prefer_return_representation: bool = False,
    insecure: bool = False,
) -> list[dict]:
    base_url = _get_env("SUPABASE_URL").rstrip("/")
    service_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE")
        or os.getenv("SUPABASE_KEY")
        or ""
    ).strip()
    if not service_key:
        raise RuntimeError("Missing Supabase service key")

    url = f"{base_url}/rest/v1/{path.lstrip('/')}"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    if prefer_return_representation:
        headers["Prefer"] = "return=representation"

    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, headers=headers, method=method)

    try:
        context = ssl._create_unverified_context() if insecure else None
        with urlopen(request, context=context) as response:
            raw = response.read().decode("utf-8").strip()
            return json.loads(raw) if raw else []
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase {method} {url} failed: {exc.code} {detail}") from exc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--date", type=str, help="UTC date in YYYY-MM-DD format; defaults to today")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--insecure", action="store_true")
    return parser.parse_args()


def _load_live_profiles(*, insecure: bool) -> list[dict]:
    rows = _supabase_request(
        "GET",
        "broker_profiles?select=id,name,run_mode,is_active,venue&is_active=eq.true&run_mode=eq.LIVE&order=id.asc",
        insecure=insecure,
    )
    return [
        row for row in rows
        if row.get("id")
        and row.get("name")
        and (row.get("venue") or "metaapi_mt5").strip().lower() != "ctrader"
    ]


def _load_candidates(day: str, *, limit: int, insecure: bool) -> list[dict]:
    encoded_day = quote(f"{day}T00:00:00+00:00", safe=":")
    status_list = ",".join(GLOBAL_STATUSES)
    return _supabase_request(
        "GET",
        (
            "trading_signals"
            "?select=*"
            f"&created_at=gte.{encoded_day}"
            "&run_mode=eq.LIVE"
            "&account_name=is.null"
            "&broker_profile_id=is.null"
            f"&status=in.({status_list})"
            "&order=created_at.asc"
            f"&limit={limit}"
        ),
        insecure=insecure,
    )


def _clone_payload(row: dict, profile: dict) -> dict:
    clone = deepcopy(row)
    clone.pop("id", None)
    clone.pop("webhook_receipt_id", None)
    clone["account_name"] = profile["name"]
    clone["broker_profile_id"] = profile["id"]
    return clone


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    _load_dotenv(repo_root / ".env")
    args = _parse_args()

    day = args.date or datetime.now(timezone.utc).date().isoformat()
    profiles = _load_live_profiles(insecure=args.insecure)
    candidates = _load_candidates(day, limit=args.limit, insecure=args.insecure)

    if not profiles:
        print("No active LIVE broker profiles found.")
        return 1

    print(f"Active LIVE profiles: {', '.join(p['name'] for p in profiles)}")

    if not candidates:
        print(f"No unscoped candidate rows found for {day}.")
        return 0

    print(f"Found {len(candidates)} candidate row(s) for {day}:")
    for row in candidates:
        print(f"  id={row['id']} | {row['created_at']} | {row['status']} | {row.get('symbol')}")

    if not args.apply:
        print("\nPreview only. Re-run with --apply to backfill these rows.")
        return 0

    primary_profile = profiles[0]
    clone_profiles = profiles[1:]
    updated = 0
    inserted = 0

    for row in candidates:
        _supabase_request(
            "PATCH",
            f"trading_signals?id=eq.{row['id']}",
            payload={
                "account_name": primary_profile["name"],
                "broker_profile_id": primary_profile["id"],
            },
            prefer_return_representation=True,
            insecure=args.insecure,
        )
        updated += 1

        for profile in clone_profiles:
            _supabase_request(
                "POST",
                "trading_signals",
                payload=_clone_payload(row, profile),
                prefer_return_representation=True,
                insecure=args.insecure,
            )
            inserted += 1

    print(
        f"\nBackfill complete: updated {updated} original row(s), "
        f"inserted {inserted} cloned row(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
