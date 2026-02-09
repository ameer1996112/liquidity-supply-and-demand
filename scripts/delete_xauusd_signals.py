"""
Delete all XAUUSD signals from Supabase trading_signals table.

CAUTION: This is a DESTRUCTIVE operation. Use with care.
"""

import os
import sys
from pathlib import Path

# Add project root to path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from src.adapters.supabase import get_supabase, init_supabase


def count_xauusd_signals():
    """Count XAUUSD signals in the database"""
    supabase = get_supabase()

    try:
        response = supabase.table('trading_signals').select('id', count='exact').eq('symbol', 'XAUUSD').execute()
        count = response.count if hasattr(response, 'count') else len(response.data)
        return count
    except Exception as e:
        print(f"❌ Error counting XAUUSD signals: {e}")
        return None


def delete_xauusd_signals():
    """Delete all XAUUSD signals from the database"""
    supabase = get_supabase()

    try:
        response = supabase.table('trading_signals').delete().eq('symbol', 'XAUUSD').execute()
        deleted_count = len(response.data) if response.data else 0
        return deleted_count
    except Exception as e:
        print(f"❌ Error deleting XAUUSD signals: {e}")
        raise


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Delete XAUUSD signals from Supabase')
    parser.add_argument('--confirm', action='store_true', help='Confirm deletion without prompting')
    args = parser.parse_args()

    print("=" * 60)
    print("XAUUSD Signal Deletion Tool")
    print("=" * 60)

    # Initialize Supabase
    try:
        init_supabase()
    except Exception as e:
        print(f"❌ Failed to initialize Supabase: {e}")
        sys.exit(1)

    # Count existing signals
    print("\n📊 Counting XAUUSD signals...")
    count = count_xauusd_signals()

    if count is None:
        print("❌ Failed to count signals. Exiting.")
        sys.exit(1)

    if count == 0:
        print("✅ No XAUUSD signals found in the database.")
        sys.exit(0)

    print(f"⚠️  Found {count} XAUUSD signals in the database.")

    if not args.confirm:
        print("\n⚠️  WARNING: This will PERMANENTLY delete all XAUUSD signals!")
        print("This action CANNOT be undone.\n")
        print("To proceed, run the script with --confirm flag:")
        print("  python scripts/delete_xauusd_signals.py --confirm")
        sys.exit(0)

    # Perform deletion
    print("\n🗑️  Deleting XAUUSD signals...")
    try:
        deleted_count = delete_xauusd_signals()
        print(f"✅ Successfully deleted {deleted_count} XAUUSD signals!")
    except Exception as e:
        print(f"❌ Deletion failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
