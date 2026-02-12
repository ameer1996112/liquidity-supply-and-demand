#!/usr/bin/env python3
"""
Setup and manage symbol risk rules in the database.

Usage:
    python scripts/setup_symbol_rules.py --list                # List all configured symbols
    python scripts/setup_symbol_rules.py --check NAS100        # Check specific symbol config
    python scripts/setup_symbol_rules.py --migrate             # Run migration 012
    python scripts/setup_symbol_rules.py --verify              # Verify position sizing for NAS100
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client
from config import get_settings
from src.core.risk_engine import calculate_max_position_size

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_supabase_client():
    """Get Supabase client instance."""
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key or settings.supabase_key
    )


def list_symbol_rules():
    """List all configured symbol risk rules."""
    sb = get_supabase_client()
    result = sb.table("symbol_risk_rules").select("*").order("symbol").execute()

    if not result.data:
        logger.warning("No symbol risk rules configured!")
        return

    print("\n" + "=" * 120)
    print(f"{'Symbol':<12} {'Pip Size':<10} {'Pip Value':<12} {'SL Buffer':<12} {'Risk %':<10} {'Max Lots':<10} {'Enabled':<8}")
    print("=" * 120)

    for rule in result.data:
        print(
            f"{rule['symbol']:<12} "
            f"{rule['pip_size']:<10.5f} "
            f"{rule['pip_value_per_lot']:<12.2f} "
            f"{rule.get('stop_loss_buffer_pips', 1.0):<12.2f} "
            f"{rule['risk_percent']:<10.1f} "
            f"{rule['max_lot_size']:<10.2f} "
            f"{'✅' if rule['enabled'] else '❌':<8}"
        )

    print("=" * 120 + "\n")


def check_symbol(symbol: str):
    """Check configuration for a specific symbol."""
    sb = get_supabase_client()
    result = sb.table("symbol_risk_rules").select("*").eq("symbol", symbol.upper()).execute()

    if not result.data:
        logger.warning(f"❌ No configuration found for {symbol}")
        logger.info("This symbol will use hardcoded fallback values from risk_engine.py")
        return None

    rule = result.data[0]
    print("\n" + "=" * 80)
    print(f"📊 Configuration for {symbol.upper()}")
    print("=" * 80)
    print(f"  Pip Size:           {rule['pip_size']:.5f}")
    print(f"  Pip Value/Lot:      ${rule['pip_value_per_lot']:.2f}")
    print(f"  Stop Loss Buffer:   {rule.get('stop_loss_buffer_pips', 1.0):.2f} pips")
    print(f"  Risk Percent:       {rule['risk_percent']:.1f}%")
    print(f"  Max Lot Size:       {rule['max_lot_size']:.2f} lots")
    print(f"  Min Lot Size:       {rule.get('min_lot_size', 0.01):.2f} lots")
    print(f"  Lot Step:           {rule.get('lot_step', 0.01):.2f}")
    print(f"  Max Positions:      {rule['max_positions']}")
    print(f"  Enabled:            {'✅ Yes' if rule['enabled'] else '❌ No'}")
    print("=" * 80 + "\n")

    return rule


def run_migration():
    """Run migration 012 to add missing columns and presets."""
    migration_file = Path(__file__).parent / "sql" / "migrations" / "012_symbol_risk_rules_enhancements.sql"

    if not migration_file.exists():
        logger.error(f"❌ Migration file not found: {migration_file}")
        return False

    logger.info("📦 Loading migration SQL...")
    with open(migration_file, "r") as f:
        sql = f.read()

    logger.info("🚀 Running migration 012...")
    sb = get_supabase_client()

    try:
        # Split by semicolons and execute each statement
        statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]

        for i, statement in enumerate(statements, 1):
            if not statement:
                continue

            logger.info(f"  Executing statement {i}/{len(statements)}...")
            # Use rpc or raw SQL execution if available
            # Note: Supabase Python client doesn't support raw SQL well, recommend running via psql

        logger.warning("⚠️  Migration SQL prepared, but Supabase Python client doesn't support raw DDL.")
        logger.info("📝 Please run this SQL manually in Supabase SQL Editor:")
        logger.info(f"   {migration_file}")

        return False

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


def verify_position_sizing():
    """Verify position sizing calculation for NAS100 example from user's signal."""
    settings = get_settings()

    # User's signal data
    payload = {
        "symbol": "NAS100",
        "side": "buy",
        "entry": 25167.6,
        "sl": 25104.4,
    }

    account_balance = 50000.0
    risk_percent = 0.5

    logger.info("\n" + "=" * 80)
    logger.info("🧪 Testing Position Sizing Calculation")
    logger.info("=" * 80)
    logger.info(f"  Symbol:           {payload['symbol']}")
    logger.info(f"  Entry:            ${payload['entry']:.2f}")
    logger.info(f"  Stop Loss:        ${payload['sl']:.2f}")
    logger.info(f"  SL Distance:      {abs(payload['entry'] - payload['sl']):.2f} points")
    logger.info(f"  Account Balance:  ${account_balance:,.2f}")
    logger.info(f"  Risk Percent:     {risk_percent}%")
    logger.info("=" * 80)

    # Check if symbol has DB override
    sb = get_supabase_client()
    result = sb.table("symbol_risk_rules").select("*").eq("symbol", "NAS100").execute()
    symbol_overrides = result.data[0] if result.data else None

    if symbol_overrides:
        logger.info("✅ Using database overrides for NAS100")
    else:
        logger.info("⚠️  No database overrides - using hardcoded fallback")

    # Calculate position size
    lot_size = calculate_max_position_size(
        payload=payload,
        account_balance=account_balance,
        risk_percent=risk_percent,
        risk_multiplier=1.0,
        symbol_overrides=symbol_overrides
    )

    logger.info("\n📊 Result:")
    logger.info(f"  Calculated Lot Size: {lot_size:.2f} lots")

    if lot_size == 0.0:
        logger.error("❌ FAILED: Position size is 0 (stop loss too wide)")
        logger.info("\n💡 Possible fixes:")
        logger.info("  1. Run migration 012 to add NAS100 config (pip_size=1.0, pip_value=1.0)")
        logger.info("  2. Tighten stop loss (currently 63.2 points)")
        logger.info("  3. Increase risk percent (currently 0.5%)")
    elif lot_size > 0:
        # Calculate notional value
        from src.services.position_optimizer import PositionOptimizer

        optimizer = PositionOptimizer()
        notional = optimizer.calculate_notional_value(
            symbol=payload["symbol"],
            side=payload["side"],
            size=lot_size,
            entry_price=payload["entry"]
        )

        risk_usd = account_balance * (risk_percent / 100)

        logger.info(f"  Notional Value:      ${notional:,.2f}")
        logger.info(f"  Risk Amount:         ${risk_usd:,.2f}")
        logger.info(f"  Position as % of Account: {(notional / account_balance) * 100:.2f}%")
        logger.info("✅ SUCCESS: Position sizing working correctly!")

    logger.info("=" * 80 + "\n")

    return lot_size > 0


def main():
    parser = argparse.ArgumentParser(description="Manage symbol risk rules")
    parser.add_argument("--list", action="store_true", help="List all configured symbols")
    parser.add_argument("--check", type=str, metavar="SYMBOL", help="Check specific symbol config")
    parser.add_argument("--migrate", action="store_true", help="Run migration 012")
    parser.add_argument("--verify", action="store_true", help="Verify NAS100 position sizing")

    args = parser.parse_args()

    if args.list:
        list_symbol_rules()
    elif args.check:
        check_symbol(args.check)
    elif args.migrate:
        run_migration()
    elif args.verify:
        success = verify_position_sizing()
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        print("\n💡 Quick Start:")
        print("  1. Run migration: python scripts/setup_symbol_rules.py --migrate")
        print("  2. Verify fix:    python scripts/setup_symbol_rules.py --verify")
        print("  3. List all:      python scripts/setup_symbol_rules.py --list")


if __name__ == "__main__":
    main()
