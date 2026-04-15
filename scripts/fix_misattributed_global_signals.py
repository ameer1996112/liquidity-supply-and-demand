#!/usr/bin/env python3
"""
Clear incorrect account_name values from historical global-rejection rows.

Background:
    In multi-account LIVE mode, some globally filtered/rejected signals were
    historically saved with the first matching account_name even though they
    were not account-specific decisions. Those rows have no broker_profile_id
    and should be left unscoped.

What this script fixes:
    - status in filtered / staleness_rejected / holiday_rejected / swap_rejected
    - run_mode = LIVE
    - account_name IS NOT NULL
    - broker_profile_id IS NULL

By default this script previews candidate rows only.
Use --apply to actually set account_name = null for the matched rows.

Examples:
    python3 scripts/fix_misattributed_global_signals.py --hours 24
    python3 scripts/fix_misattributed_global_signals.py --hours 24 --apply
    python3 scripts/fix_misattributed_global_signals.py --since 2026-04-15T00:00:00+00:00 --apply
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_STATUSES = (
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
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _get_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _supabase_request(
    method: str,
    path: str,
    *,
    payload: dict | None = None,
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
        raise RuntimeError(
            "Missing Supabase service key (SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY)"
        )

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


def _build_candidate_query(since: str, statuses: Iterable[str], limit: int) -> str:
    encoded_since = quote(since, safe=":")
    status_list = ",".join(statuses)
    return (
        "trading_signals"
        "?select=id,created_at,symbol,status,run_mode,account_name,broker_profile_id,notes"
        f"&created_at=gte.{encoded_since}"
        "&run_mode=eq.LIVE"
        "&account_name=not.is.null"
        "&broker_profile_id=is.null"
        f"&status=in.({status_list})"
        "&order=created_at.desc"
        f"&limit={limit}"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply the repair instead of previewing only")
    parser.add_argument("--hours", type=int, default=24, help="Look back this many hours when --since is omitted")
    parser.add_argument("--since", type=str, help="Inclusive UTC ISO timestamp lower bound")
    parser.add_argument("--limit", type=int, default=200, help="Maximum candidate rows to fetch")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification for local repair runs")
    return parser.parse_args()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    _load_dotenv(repo_root / ".env")

    args = _parse_args()
    since = args.since or (
        datetime.now(timezone.utc) - timedelta(hours=args.hours)
    ).isoformat()

    rows = _supabase_request(
        "GET",
        _build_candidate_query(since, DEFAULT_STATUSES, args.limit),
        insecure=args.insecure,
    )

    if not rows:
        print("No candidate rows found.")
        return 0

    print(f"Found {len(rows)} candidate rows since {since}:")
    for row in rows:
        print(
            f"  id={row['id']} | {row['created_at']} | {row['status']} | "
            f"{row.get('symbol') or 'UNKNOWN'} | account_name={row.get('account_name')!r}"
        )

    if not args.apply:
        print("\nPreview only. Re-run with --apply to clear account_name on these rows.")
        return 0

    updated = 0
    for row in rows:
        _supabase_request(
            "PATCH",
            f"trading_signals?id=eq.{row['id']}",
            payload={"account_name": None},
            prefer_return_representation=True,
            insecure=args.insecure,
        )
        updated += 1

    print(f"\nUpdated {updated} row(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
