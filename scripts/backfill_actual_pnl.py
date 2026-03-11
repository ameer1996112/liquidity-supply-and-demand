#!/usr/bin/env python3
"""
Backfill Actual Broker PnL for Closed Trades

This script fetches actual PnL from MetaAPI for all closed trades and updates
the database with real broker values instead of TradingView simulated values.

Usage:
    python scripts/backfill_actual_pnl.py --account ACD-DEMO --days 30
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_settings
from src.adapters.supabase_api import get_api_supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_adapter_for_account(account_name: Optional[str] = None):
    """
    Get MetaAPI adapter for the specified account.

    If account_name is None, uses the default broker profile.
    """
    from src.adapters.execution.router import get_adapter

    settings = get_settings()
    sb = get_api_supabase()

    try:
        if account_name:
            # Try to fetch broker profile for this account
            resp = sb.table("account_strategies").select("broker_profile_id").eq("account_name", account_name).single().execute()
            profile_data = resp.data

            if not profile_data or not profile_data.get("broker_profile_id"):
                logger.warning(f"No broker profile found for account {account_name}, using default")
                return get_adapter(run_mode=settings.run_mode, settings=settings, profile=None)

            profile_id = profile_data["broker_profile_id"]
        else:
            # Use the first available broker profile
            resp = sb.table("broker_profiles").select("*").limit(1).execute()
            if not resp.data:
                logger.error("No broker profiles found")
                return None
            profile = resp.data[0]
            logger.info(f"Using default broker profile: {profile.get('name')}")
            return get_adapter(run_mode=settings.run_mode, settings=settings, profile=profile)

        # Fetch broker profile details
        profile_resp = sb.table("broker_profiles").select("*").eq("id", profile_id).single().execute()
        profile = profile_resp.data

        if not profile:
            logger.error(f"Broker profile {profile_id} not found")
            return None

        logger.info(f"Using broker profile: {profile.get('name')} (ID: {profile_id})")
        return get_adapter(run_mode=settings.run_mode, settings=settings, profile=profile)

    except Exception as e:
        logger.error(f"Failed to get adapter: {e}")
        return None


def fetch_closed_trades(account_id: Optional[str] = None, days: int = 30) -> List[Dict]:
    """Fetch closed trades from database for the specified account."""
    sb = get_api_supabase()

    # Calculate date range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)

    logger.info(f"Fetching closed trades from {start_time.date()} to {end_time.date()}")

    try:
        query = (
            sb.table("trading_signals")
            .select("id, zone_id, symbol, side, entry, sl, tp, size, broker_order_id, broker_position_id, "
                   "pnl_usd, pnl, closed_at, exit_price, status, execution_source, account_id")
            .eq("status", "CLOSED")
            .eq("execution_source", "metaapi")  # Only fetch LIVE trades, not PAPER
            .gte("closed_at", start_time.isoformat())
            .lte("closed_at", end_time.isoformat())
        )

        # Filter by account_id if specified
        if account_id:
            query = query.eq("account_id", account_id)

        resp = query.execute()

        trades = resp.data or []
        logger.info(f"Found {len(trades)} closed trades in database")
        return trades

    except Exception as e:
        logger.error(f"Failed to fetch closed trades: {e}")
        return []


def fetch_broker_deals(adapter, start_time: datetime, end_time: datetime) -> List[Dict]:
    """Fetch historical deals from MetaAPI."""
    if not hasattr(adapter, "get_historical_deals"):
        logger.error("Adapter does not support get_historical_deals()")
        return []

    try:
        logger.info(f"Fetching broker deals from {start_time} to {end_time}")
        deals = adapter.get_historical_deals(
            start_time.isoformat(),
            end_time.isoformat()
        )

        # Filter for closing deals only
        closing_deals = [
            d for d in deals
            if d.get("entryType") in ["DEAL_ENTRY_OUT", "DEAL_ENTRY_OUT_BY"]
        ]

        logger.info(f"Fetched {len(closing_deals)} closing deals from broker")

        # Debug: show what deals we got
        if closing_deals:
            logger.info("\nBroker deals found:")
            for deal in closing_deals[:10]:  # Show first 10
                logger.info(
                    f"  - Deal: {deal.get('symbol')} @ {deal.get('time')} | "
                    f"positionId={deal.get('positionId')} | orderId={deal.get('orderId')} | "
                    f"profit=${deal.get('profit', 0):.2f}"
                )

        return closing_deals

    except Exception as e:
        logger.error(f"Failed to fetch broker deals: {e}")
        return []


def match_trade_to_deal(trade: Dict, deals: List[Dict]) -> Optional[Dict]:
    """
    Match a database trade to a broker deal.

    Tries to match by:
    1. broker_position_id against deal.positionId
    2. broker_order_id against deal.positionId (often broker_order_id stores the position ID)
    3. broker_order_id against deal.orderId
    4. Symbol + close time (within 5 minutes)
    """
    broker_position_id = trade.get("broker_position_id")
    broker_order_id = trade.get("broker_order_id")
    symbol = trade.get("symbol")
    closed_at = trade.get("closed_at")

    # Parse closed_at time
    try:
        trade_close_time = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        trade_close_time = None

    # Convert broker IDs to strings for comparison
    broker_position_id_str = str(broker_position_id) if broker_position_id else None
    broker_order_id_str = str(broker_order_id) if broker_order_id else None

    for deal in deals:
        deal_position_id = str(deal.get("positionId", ""))
        deal_order_id = str(deal.get("orderId", ""))

        # Match by broker_position_id against deal.positionId
        if broker_position_id_str and deal_position_id == broker_position_id_str:
            return deal

        # Match by broker_order_id against deal.positionId
        # (Often broker_order_id stores the position ID, not the order ID)
        if broker_order_id_str and deal_position_id == broker_order_id_str:
            return deal

        # Match by broker_order_id against deal.orderId
        if broker_order_id_str and deal_order_id == broker_order_id_str:
            return deal

        # Match by symbol + time (less reliable, use as fallback)
        if symbol and deal.get("symbol") == symbol and trade_close_time:
            try:
                deal_time = datetime.fromisoformat(deal.get("time", "").replace("Z", "+00:00"))
                time_diff = abs((deal_time - trade_close_time).total_seconds())

                # If within 5 minutes, consider it a match
                if time_diff < 300:
                    return deal
            except (ValueError, AttributeError):
                continue

    return None


def update_trade_pnl(trade_id: int, deal: Dict, dry_run: bool = False) -> bool:
    """Update a trade's PnL with actual broker values."""
    actual_profit = float(deal.get("profit", 0))
    actual_commission = float(deal.get("commission", 0))
    actual_swap = float(deal.get("swap", 0))
    total_pnl = actual_profit + actual_commission + actual_swap

    logger.info(
        f"Trade #{trade_id}: profit=${actual_profit:.2f} + commission=${actual_commission:.2f} + swap=${actual_swap:.2f} = ${total_pnl:.2f}"
    )

    if dry_run:
        logger.info(f"[DRY RUN] Would update trade #{trade_id} with broker PnL: ${total_pnl:.2f}")
        return True

    sb = get_api_supabase()

    try:
        update_data = {
            "pnl_usd": total_pnl,
            "pnl": total_pnl,
            "commission": actual_commission,
            "swap": actual_swap,
        }

        sb.table("trading_signals").update(update_data).eq("id", trade_id).execute()
        logger.info(f"✅ Updated trade #{trade_id} with actual broker PnL: ${total_pnl:.2f}")
        return True

    except Exception as e:
        logger.error(f"Failed to update trade #{trade_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Backfill actual broker PnL for closed trades")
    parser.add_argument("--account", help="Account ID from trading_signals table (e.g., default)")
    parser.add_argument("--account-name", help="Account name from account_strategies table (e.g., ACG-DEMO)")
    parser.add_argument("--days", type=int, default=30, help="Number of days to look back (default: 30)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without making changes")

    args = parser.parse_args()

    logger.info(f"Starting PnL backfill")
    if args.account:
        logger.info(f"Account ID filter: {args.account}")
    if args.account_name:
        logger.info(f"Account name: {args.account_name}")
    logger.info(f"Looking back: {args.days} days")
    logger.info(f"Dry run: {args.dry_run}")

    # Get adapter for account
    adapter = get_adapter_for_account(args.account_name)
    if not adapter:
        logger.error("Failed to get adapter, aborting")
        return

    # Calculate date range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=args.days)

    # Fetch closed trades from database
    trades = fetch_closed_trades(args.account, args.days)
    if not trades:
        logger.warning("No closed trades found in database")
        return

    # Fetch broker deals
    deals = fetch_broker_deals(adapter, start_time, end_time)
    if not deals:
        logger.warning("No broker deals found")
        return

    # Match and update
    matched_count = 0
    updated_count = 0
    unmatched_trades = []

    for trade in trades:
        trade_id = trade.get("id")
        symbol = trade.get("symbol")
        old_pnl = trade.get("pnl_usd") or trade.get("pnl") or 0

        logger.info(f"\nProcessing trade #{trade_id} ({symbol}), current PnL: ${old_pnl:.2f}")

        # Try to match to a broker deal
        matching_deal = match_trade_to_deal(trade, deals)

        if matching_deal:
            matched_count += 1

            actual_pnl = (
                float(matching_deal.get("profit", 0)) +
                float(matching_deal.get("commission", 0)) +
                float(matching_deal.get("swap", 0))
            )

            # Check if PnL changed significantly
            pnl_diff = abs(actual_pnl - old_pnl)
            pnl_diff_pct = (pnl_diff / abs(old_pnl) * 100) if old_pnl != 0 else 0

            logger.info(f"Matched! Broker PnL: ${actual_pnl:.2f} (diff: ${pnl_diff:.2f}, {pnl_diff_pct:.1f}%)")

            # Update if difference is significant (>1%)
            if pnl_diff_pct > 1.0 or pnl_diff > 5.0:
                if update_trade_pnl(trade_id, matching_deal, dry_run=args.dry_run):
                    updated_count += 1
            else:
                logger.info(f"PnL difference too small ({pnl_diff_pct:.1f}%), skipping update")
        else:
            logger.warning(f"No matching broker deal found for trade #{trade_id} ({symbol})")
            unmatched_trades.append(trade)

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total trades processed: {len(trades)}")
    logger.info(f"Matched to broker deals: {matched_count}")
    logger.info(f"Updated with actual PnL: {updated_count}")
    logger.info(f"Unmatched trades: {len(unmatched_trades)}")

    if unmatched_trades:
        logger.info("\nUnmatched trades:")
        for trade in unmatched_trades:
            logger.info(
                f"  - Trade #{trade['id']}: {trade['symbol']} closed at {trade.get('closed_at')} "
                f"(broker_position_id={trade.get('broker_position_id')}, broker_order_id={trade.get('broker_order_id')})"
            )

    if args.dry_run:
        logger.info("\n[DRY RUN] No changes were made. Run without --dry-run to apply updates.")
    else:
        logger.info(f"\n✅ Backfill complete! Updated {updated_count} trades with actual broker PnL.")


if __name__ == "__main__":
    main()
