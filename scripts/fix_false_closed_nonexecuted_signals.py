#!/usr/bin/env python3
"""
Repair rows that were wrongly marked CLOSED with pnl_usd even though the trade
never executed because a guard blocked it.

Target pattern:
  - run_mode = LIVE
  - status = CLOSED
  - pnl_usd is not null
  - execution_source is null or signal_only
  - broker_order_id is null
  - notes / ai_reasoning indicate filtered / rejected / non-executed flow

Repair action:
  - set status back to filtered (or preserve the more specific rejection status
    if it can be inferred from notes/ai_reasoning)
  - clear closed_at / close_time / exit_time / exit_price / close_price
  - clear pnl / pnl_usd / commission / swap / outcome / exit_type
  - append a repair note

Preview is the default. Use --apply to execute the repair.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


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
    parser.add_argument("--hours", type=int, default=48)
    parser.add_argument("--since", type=str)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--insecure", action="store_true")
    return parser.parse_args()


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.lower()
    try:
        return json.dumps(value).lower()
    except Exception:
        return str(value).lower()


def _infer_repaired_status(row: dict) -> str:
    haystack = " ".join(
        [
            _safe_text(row.get("notes")),
            _safe_text(row.get("ai_reasoning")),
            _safe_text(row.get("filter_reason_json")),
        ]
    )
    if "staleness" in haystack:
        return "staleness_rejected"
    if "holiday" in haystack:
        return "holiday_rejected"
    if "swap" in haystack:
        return "swap_rejected"
    if "risk" in haystack:
        return "risk_rejected"
    if "blacklist" in haystack or "whitelist" in haystack:
        return "symbol_blacklisted"
    if "ai_reject" in haystack or "ai rejected" in haystack:
        return "ai_rejected"
    return "filtered"


def _is_corrupted_nonexecuted(row: dict) -> bool:
    if str(row.get("run_mode") or "").upper() != "LIVE":
        return False
    if str(row.get("status") or "").lower() != "closed":
        return False
    if row.get("pnl_usd") in (None, "") and row.get("pnl") in (None, ""):
        return False
    if row.get("broker_order_id"):
        return False

    exec_source = (row.get("execution_source") or "signal_only").lower()
    if exec_source not in {"signal_only", ""}:
        return False

    haystack = " ".join(
        [
            _safe_text(row.get("notes")),
            _safe_text(row.get("ai_reasoning")),
            _safe_text(row.get("filter_reason_json")),
        ]
    )
    tokens = (
        "filtered",
        "rejected",
        "guard",
        "not recorded",
        "never executed",
        "unexecuted",
        "monthly loss limit",
        "daily loss limit",
        "staleness",
        "holiday",
        "swap",
    )
    return any(token in haystack for token in tokens)


def _load_candidates(since: str, *, limit: int, insecure: bool) -> list[dict]:
    encoded_since = quote(since, safe=":")
    rows = _supabase_request(
        "GET",
        (
            "trading_signals"
            "?select=id,created_at,symbol,account_name,broker_profile_id,status,run_mode,"
            "pnl,pnl_usd,commission,swap,execution_source,broker_order_id,"
            "notes,ai_reasoning,filter_reason_json,closed_at,close_time,exit_time,exit_type"
            f"&created_at=gte.{encoded_since}"
            "&run_mode=eq.LIVE"
            "&status=eq.CLOSED"
            "&order=created_at.desc"
            f"&limit={limit}"
        ),
        insecure=insecure,
    )
    return [row for row in rows if _is_corrupted_nonexecuted(row)]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    _load_dotenv(repo_root / ".env")
    args = _parse_args()

    since = args.since or (
        datetime.now(timezone.utc) - timedelta(hours=args.hours)
    ).isoformat()

    rows = _load_candidates(since, limit=args.limit, insecure=args.insecure)
    if not rows:
        print("No corrupted non-executed CLOSED rows found.")
        return 0

    print(f"Found {len(rows)} corrupted row(s) since {since}:")
    for row in rows:
        repaired_status = _infer_repaired_status(row)
        print(
            f"  id={row['id']} | {row['created_at']} | {row.get('symbol')} | "
            f"{row.get('account_name') or '-'} | pnl={row.get('pnl_usd') or row.get('pnl')} "
            f"| -> {repaired_status}"
        )

    if not args.apply:
        print("\nPreview only. Re-run with --apply to repair these rows.")
        return 0

    updated = 0
    for row in rows:
        repaired_status = _infer_repaired_status(row)
        original_note = (row.get("notes") or "").strip()
        repair_note = (
            f"{original_note} | "
            if original_note
            else ""
        ) + "AI repair: cleared false CLOSED/PnL state because trade never executed on broker."

        payload = {
            "status": repaired_status,
            "pnl": None,
            "pnl_usd": None,
            "commission": None,
            "swap": None,
            "outcome": None,
            "closed_at": None,
            "close_time": None,
            "exit_time": None,
            "close_price": None,
            "exit_price": None,
            "exit_type": None,
            "notes": repair_note,
        }
        _supabase_request(
            "PATCH",
            f"trading_signals?id=eq.{row['id']}",
            payload=payload,
            prefer_return_representation=True,
            insecure=args.insecure,
        )
        updated += 1

    print(f"\nUpdated {updated} row(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
