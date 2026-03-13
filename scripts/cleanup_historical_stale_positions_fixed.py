#!/usr/bin/env python3
"""Cleanup historical stale positions: Close zero-PNL active/executed signals older than 30d."""

import argparse
from datetime import datetime, timedelta, timezone
from src.adapters.supabase_api import get_api_supabase

def main(dry_run=True):
    sb = get_api_supabase()
    
    # Find stale: active/executed, pnl=0, created_at < 30d ago
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    
    stale = sb.table('trading_signals')\
        .select('id, symbol, created_at, status, pnl_usd')\
        .in_('status', ['active', 'executed', 'ACTIVE', 'EXECUTED'])\
        .eq('pnl_usd', 0)\
        .lt('created_at', cutoff)\
        .execute().data
    
    print(f"Found {len(stale)} stale positions:")
    for s in stale:
        print(f"  ID {s['id']}: {s['symbol']} ({s['status']}) created {s['created_at']}")
    
    if dry_run:
        print("\nDRY RUN: No changes made. Run with --execute to apply.")
        return
    
    # Close them
    updates = [{'id': s['id'], 'status': 'CLOSED', 'closed_at': datetime.now(timezone.utc).isoformat()} for s in stale]
    sb.table('trading_signals').upsert(updates, on_conflict='id').execute()
    print(f"\nClosed {len(updates)} stale positions.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true', help='Apply changes (not dry-run)')
    args = parser.parse_args()
    main(dry_run=not args.execute)
