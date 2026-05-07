#!/usr/bin/env python3
"""Backfill exact setup evidence screenshots for historical trading signals.

Preview by default:
    PYTHONPATH=. python3 scripts/backfill_setup_evidence.py --limit 20

Apply:
    PYTHONPATH=. python3 scripts/backfill_setup_evidence.py --limit 20 --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supabase import create_client

from src.services.setup_evidence_capture import (
    capture_setup_evidence_for_signal,
    needs_setup_evidence_backfill,
)


SELECT_FIELDS = (
    "id,created_at,symbol,status,run_mode,zone_id,zone_type,zone_top,zone_bottom,"
    "entry,sl,tp,setup_evidence,image_url"
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


def _supabase_client() -> Any:
    url = (os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
        or ""
    ).strip()
    if not url or not key:
        raise RuntimeError("Missing Supabase URL/key in environment")
    return create_client(url, key)


def _parse_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    ids: list[int] = []
    for item in raw.split(","):
        stripped = item.strip()
        if stripped:
            ids.append(int(stripped))
    return ids


def _fetch_rows(client: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    ids = _parse_ids(args.ids)
    query = (
        client.table("trading_signals")
        .select(SELECT_FIELDS)
        .not_.is_("zone_id", "null")
        .not_.is_("zone_top", "null")
        .not_.is_("zone_bottom", "null")
        .order("created_at", desc=True)
        .limit(args.limit)
    )
    if ids:
        query = query.in_("id", ids)
    if args.since:
        query = query.gte("created_at", args.since)
    if args.until:
        query = query.lte("created_at", args.until)
    return query.execute().data or []


def _row_summary(row: dict[str, Any]) -> str:
    evidence = row.get("setup_evidence")
    focus_zone = evidence.get("focus_zone") if isinstance(evidence, dict) else None
    focus_id = focus_zone.get("id") if isinstance(focus_zone, dict) else None
    return (
        f"id={row.get('id')} {row.get('created_at')} {row.get('symbol')} "
        f"zone={row.get('zone_id')} {row.get('zone_type')} "
        f"{row.get('zone_bottom')}..{row.get('zone_top')} "
        f"evidence={evidence.get('status') if isinstance(evidence, dict) else None} "
        f"focus_id={focus_id}"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write repaired setup evidence")
    parser.add_argument("--force", action="store_true", help="Capture every fetched row, even if evidence is already exact")
    parser.add_argument("--limit", type=int, default=25, help="Maximum rows to fetch")
    parser.add_argument("--ids", help="Comma-separated trading_signals ids to process")
    parser.add_argument("--since", help="Only fetch rows created at or after this ISO timestamp")
    parser.add_argument("--until", help="Only fetch rows created at or before this ISO timestamp")
    return parser.parse_args()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    _load_dotenv(repo_root / ".env")
    args = _parse_args()
    client = _supabase_client()

    rows = _fetch_rows(client, args)
    if not rows:
        print("No zone rows found.")
        return 0

    candidates = [row for row in rows if args.force or needs_setup_evidence_backfill(row)]
    print(f"Fetched {len(rows)} rows; {len(candidates)} need setup evidence backfill.")

    for row in candidates:
        print(f"  {'APPLY' if args.apply else 'DRY'} {_row_summary(row)}")
        if not args.apply:
            continue

        ok = capture_setup_evidence_for_signal(
            client,
            int(row["id"]),
            {
                "symbol": row.get("symbol"),
                "timeframe": "5m",
                "zone_id": row.get("zone_id"),
                "created_at": row.get("created_at"),
                "zone_type": row.get("zone_type"),
                "zone_top": row.get("zone_top"),
                "zone_bottom": row.get("zone_bottom"),
            },
        )
        print(f"    captured={ok}")

    if not args.apply:
        print("Preview only. Re-run with --apply to write repaired evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
