#!/usr/bin/env python3
"""Backfill missing trading_signals.size from broker history.

Preview:
    PYTHONPATH=. python3 scripts/backfill_signal_sizes.py --days 90 --limit 100

Apply:
    PYTHONPATH=. python3 scripts/backfill_signal_sizes.py --days 90 --limit 100 --apply
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import get_settings
from src.adapters.execution.router import get_adapter
from src.adapters.supabase_api import get_api_supabase


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SELECT_FIELDS = (
    "id,created_at,closed_at,symbol,status,size,broker_order_id,broker_position_id,"
    "account_name,broker_profile_id"
)
EXECUTED_STATUSES = ["OPEN", "open", "CLOSED", "closed", "EXECUTED", "executed", "filled", "FILLED"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill missing signal lot sizes from broker volume")
    parser.add_argument("--apply", action="store_true", help="Write updates to Supabase")
    parser.add_argument("--days", type=int, default=90, help="Look back window by created_at")
    parser.add_argument("--limit", type=int, default=500, help="Maximum rows to scan")
    parser.add_argument("--account-name", help="Only backfill this account_name")
    parser.add_argument("--broker-profile-id", type=int, help="Only backfill this broker_profile_id")
    return parser.parse_args()


def _missing_size(row: dict[str, Any]) -> bool:
    try:
        return float(row.get("size") or 0) <= 0
    except (TypeError, ValueError):
        return True


def _load_profiles(client: Any) -> dict[int, dict[str, Any]]:
    rows = client.table("broker_profiles").select("*").execute().data or []
    return {int(row["id"]): row for row in rows if row.get("id") is not None}


def _adapter_for_row(row: dict[str, Any], profiles: dict[int, dict[str, Any]]) -> Any:
    settings = get_settings()
    profile_id = row.get("broker_profile_id")
    profile = profiles.get(int(profile_id)) if profile_id is not None else None
    return get_adapter(run_mode=settings.run_mode, settings=settings, profile=profile)


def _volume_from_deals(adapter: Any, position_id: str) -> float | None:
    if not hasattr(adapter, "get_deals_by_position"):
        return None

    deals = adapter.get_deals_by_position(position_id) or []
    entry_types = {"DEAL_ENTRY_IN", "DEAL_ENTRY_INOUT"}
    ordered_deals = sorted(
        deals,
        key=lambda deal: 0 if deal.get("entryType") in entry_types else 1,
    )
    for deal in ordered_deals:
        try:
            volume = float(deal.get("volume") or 0)
        except (TypeError, ValueError):
            continue
        if volume > 0:
            return volume
    return None


def _volume_from_open_positions(adapter: Any, position_id: str) -> float | None:
    if not hasattr(adapter, "get_open_positions"):
        return None

    for position in adapter.get_open_positions() or []:
        ids = {
            str(position.get("id") or ""),
            str(position.get("positionId") or ""),
            str(position.get("broker_position_id") or ""),
        }
        if position_id not in ids:
            continue
        try:
            volume = float(position.get("volume") or position.get("size") or 0)
        except (TypeError, ValueError):
            return None
        return volume if volume > 0 else None
    return None


def _broker_volume(adapter: Any, row: dict[str, Any]) -> float | None:
    position_ids = [
        str(row.get("broker_position_id") or "").strip(),
        str(row.get("broker_order_id") or "").strip(),
    ]
    for position_id in [value for value in position_ids if value]:
        volume = _volume_from_deals(adapter, position_id)
        if volume is not None:
            return volume
        volume = _volume_from_open_positions(adapter, position_id)
        if volume is not None:
            return volume
    return None


def _fetch_candidates(client: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()
    query = (
        client.table("trading_signals")
        .select(SELECT_FIELDS)
        .in_("status", EXECUTED_STATUSES)
        .not_.is_("broker_order_id", "null")
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .limit(args.limit)
    )
    if args.account_name:
        query = query.eq("account_name", args.account_name)
    if args.broker_profile_id is not None:
        query = query.eq("broker_profile_id", args.broker_profile_id)

    rows = query.execute().data or []
    return [row for row in rows if _missing_size(row)]


def main() -> int:
    args = _parse_args()
    client = get_api_supabase()
    profiles = _load_profiles(client)
    candidates = _fetch_candidates(client, args)

    logger.info("Fetched %s missing-size candidates", len(candidates))
    if not candidates:
        return 0

    updated = 0
    skipped = 0
    errors = 0

    for row in candidates:
        signal_id = row.get("id")
        symbol = row.get("symbol")
        try:
            adapter = _adapter_for_row(row, profiles)
            volume = _broker_volume(adapter, row)
            if volume is None:
                skipped += 1
                logger.info(
                    "SKIP id=%s %s broker=%s: no broker volume found",
                    signal_id,
                    symbol,
                    row.get("broker_order_id"),
                )
                continue

            logger.info(
                "%s id=%s %s %s size=%s -> %.3f",
                "APPLY" if args.apply else "DRY",
                signal_id,
                row.get("created_at"),
                symbol,
                row.get("size"),
                volume,
            )
            if args.apply:
                client.table("trading_signals").update(
                    {"size": volume, "updated_at": datetime.now(timezone.utc).isoformat()}
                ).eq("id", signal_id).execute()
            updated += 1
        except Exception as exc:
            errors += 1
            logger.error("ERROR id=%s %s: %s", signal_id, symbol, exc)

    logger.info(
        "Done: candidates=%s matched=%s skipped=%s errors=%s apply=%s",
        len(candidates),
        updated,
        skipped,
        errors,
        args.apply,
    )
    if not args.apply:
        logger.info("Preview only. Re-run with --apply to write size values.")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
