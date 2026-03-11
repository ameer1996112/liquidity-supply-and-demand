"""
Cleanup Stale Positions Script

Identifies and closes database positions that:
1. Are marked as OPEN/PENDING but have no corresponding broker position
2. Are older than 7 days with no activity
3. Have broker_order_id but broker position no longer exists
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

from src.adapters.supabase_api import get_api_supabase
from src.adapters.execution.router import get_adapter
from config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_broker_open_positions(adapter) -> Dict[str, Any]:
    """Fetch actually open positions from broker."""
    if not hasattr(adapter, "get_open_positions"):
        logger.warning("Adapter doesn't support get_open_positions, checking via get_account_information")
        if hasattr(adapter, "get_account_information"):
            try:
                account_info = adapter.get_account_information()
                # MetaAPI returns positions in account info
                return {pos.get("id"): pos for pos in account_info.get("positions", [])}
            except Exception as e:
                logger.error(f"Failed to get account info: {e}")
                return {}
        return {}

    try:
        positions = adapter.get_open_positions()
        return {pos.get("id"): pos for pos in positions}
    except Exception as e:
        logger.error(f"Failed to fetch broker positions: {e}")
        return {}


def find_stale_positions(sb, broker_positions: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find database positions that should be closed."""
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    # Query all OPEN/PENDING/executed positions
    resp = sb.table("trading_signals").select("*").in_(
        "status", ["OPEN", "open", "active", "executed", "PENDING", "pending"]
    ).execute()

    stale = []
    for signal in resp.data or []:
        signal_id = signal.get("id")
        status = signal.get("status")
        created_at = signal.get("created_at")
        broker_order_id = signal.get("broker_order_id")
        broker_position_id = signal.get("broker_position_id")

        # Stale if PENDING with no broker link (never executed)
        if status.upper() == "PENDING" and not broker_order_id and not broker_position_id:
            stale.append({
                "signal": signal,
                "reason": "PENDING with no broker link (never executed)",
            })
            continue

        # Stale if OPEN/executed but broker position doesn't exist (closed on broker but not in DB)
        if status.upper() in ("OPEN", "EXECUTED") and broker_order_id:
            if broker_order_id not in broker_positions:
                stale.append({
                    "signal": signal,
                    "reason": f"Position closed on broker but not in database",
                })
                continue

        # Stale if older than 7 days
        if created_at and created_at < cutoff_date:
            stale.append({
                "signal": signal,
                "reason": f"Older than 7 days (created {created_at[:10]})",
            })
            continue

        # Stale if status is 'received' (stuck in processing)
        if status.lower() == "received":
            stale.append({
                "signal": signal,
                "reason": "Stuck in 'received' status",
            })
            continue

    return stale


def close_stale_signal(sb, signal_id: int, reason: str, dry_run: bool = True):
    """Close a stale signal in the database."""
    if dry_run:
        logger.info(f"[DRY RUN] Would close signal {signal_id}: {reason}")
        return

    logger.info(f"Closing signal {signal_id}: {reason}")

    try:
        sb.table("trading_signals").update({
            "status": "CLOSED",
            "closed_at": datetime.now(timezone.utc).isoformat(),
            "exit_type": "STALE_CLEANUP",
        }).eq("id", signal_id).execute()

        logger.info(f"✓ Closed signal {signal_id}")
    except Exception as e:
        logger.error(f"✗ Failed to close signal {signal_id}: {e}")


def main(dry_run: bool = True):
    """Main cleanup process."""
    logger.info("=" * 80)
    logger.info("Stale Position Cleanup")
    logger.info("=" * 80)

    if dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made")
    else:
        logger.warning("⚠️  LIVE MODE - Changes will be committed to database!")

    logger.info("")

    sb = get_api_supabase()
    settings = get_settings()
    adapter = get_adapter(run_mode=settings.run_mode, settings=settings)

    # Fetch broker positions for reconciliation
    logger.info("Fetching broker positions for reconciliation...")
    broker_positions = get_broker_open_positions(adapter)
    logger.info(f"Found {len(broker_positions)} open positions on broker")
    logger.info("")

    # Find stale positions
    logger.info("Scanning for stale positions...")
    stale_positions = find_stale_positions(sb, broker_positions)

    if not stale_positions:
        logger.info("✓ No stale positions found")
        return

    logger.info(f"Found {len(stale_positions)} stale positions:")
    logger.info("")

    # Group by reason
    by_reason = {}
    for item in stale_positions:
        reason = item["reason"]
        by_reason.setdefault(reason, []).append(item["signal"])

    # Display grouped results
    for reason, signals in by_reason.items():
        logger.info(f"{reason} ({len(signals)}):")
        for s in signals:
            logger.info(f"  - ID {s.get('id'):3d}: {s.get('symbol'):7s} {s.get('side'):4s} "
                       f"(Created: {s.get('created_at')[:16]})")

    logger.info("")

    # Close all stale positions
    for item in stale_positions:
        signal = item["signal"]
        close_stale_signal(sb, signal["id"], item["reason"], dry_run=dry_run)

    logger.info("")
    logger.info("=" * 80)
    if dry_run:
        logger.info("✓ Dry run completed - run with --live to apply changes")
    else:
        logger.info(f"✓ Cleanup completed - closed {len(stale_positions)} stale positions")
    logger.info("=" * 80)


if __name__ == "__main__":
    import sys

    dry_run = "--live" not in sys.argv
    main(dry_run=dry_run)
