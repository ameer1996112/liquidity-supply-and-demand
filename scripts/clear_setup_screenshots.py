#!/usr/bin/env python3
"""Remove setup screenshot references from trading signals.

Preview:
    PYTHONPATH=. python3 scripts/clear_setup_screenshots.py --limit 1000

Apply:
    PYTHONPATH=. python3 scripts/clear_setup_screenshots.py --limit 1000 --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supabase import create_client

from src.services.setup_evidence_capture import strip_setup_screenshot_fields


SELECT_FIELDS = "id,created_at,symbol,setup_evidence,image_url"


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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write cleanup updates")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum rows to fetch")
    return parser.parse_args()


def _needs_cleanup(row: dict[str, Any]) -> bool:
    if row.get("image_url"):
        return True
    setup_evidence = row.get("setup_evidence")
    if not isinstance(setup_evidence, dict):
        return False
    return setup_evidence.get("focus_image") is not None


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    _load_dotenv(repo_root / ".env")
    args = _parse_args()
    client = _supabase_client()

    rows = (
        client.table("trading_signals")
        .select(SELECT_FIELDS)
        .order("created_at", desc=True)
        .limit(args.limit)
        .execute()
        .data
        or []
    )
    candidates = [row for row in rows if _needs_cleanup(row)]
    print(f"Fetched {len(rows)} rows; {len(candidates)} rows contain setup screenshots.")

    for row in candidates:
        print(f"  {'APPLY' if args.apply else 'DRY'} id={row.get('id')} {row.get('created_at')} {row.get('symbol')}")
        if not args.apply:
            continue
        setup_evidence = strip_setup_screenshot_fields(row.get("setup_evidence"))
        payload: dict[str, Any] = {"image_url": None}
        if isinstance(setup_evidence, dict):
            payload["setup_evidence"] = setup_evidence
        client.table("trading_signals").update(payload).eq("id", int(row["id"])).execute()

    if not args.apply:
        print("Preview only. Re-run with --apply to clear screenshot references.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
