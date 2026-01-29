"""
Reclassify imported trading_signals rows from LIVE to BACKTEST.

Use this when you imported historical/backtest trades and they were stored
with run_mode='LIVE'. After running, the dashboard LIVE filter will show
only real webhook/live trades.

Usage:
  # Dry run (default): show what would be updated
  python reclassify_imported.py --before-id 515
  python reclassify_imported.py --before-date 2026-01-29

  # Actually update the database
  python reclassify_imported.py --before-id 515 --apply
  python reclassify_imported.py --before-date 2026-01-29 --apply

Requires: SUPABASE_URL and SUPABASE_ANON_KEY in backend/.env
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")


def main():
    parser = argparse.ArgumentParser(description="Reclassify imported rows to BACKTEST")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--before-id", type=int, metavar="N", help="Reclassify rows with id <= N and run_mode=LIVE")
    g.add_argument("--before-date", type=str, metavar="YYYY-MM-DD", help="Reclassify rows with created_at < this date and run_mode=LIVE")
    parser.add_argument("--apply", action="store_true", help="Apply updates (default is dry run)")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("ERROR: Set SUPABASE_URL and SUPABASE_ANON_KEY in backend/.env", file=sys.stderr)
        sys.exit(1)

    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    # Build filter for rows to update
    update = {"run_mode": "BACKTEST", "run_id": "imported"}
    q = supabase.table("trading_signals").update(update).eq("run_mode", "LIVE")
    if args.before_id is not None:
        q = q.lte("id", args.before_id)
    else:
        q = q.lt("created_at", f"{args.before_date}T00:00:00")

    if not args.apply:
        # Dry run: count matching rows
        count_q = supabase.table("trading_signals").select("id").eq("run_mode", "LIVE")
        if args.before_id is not None:
            count_q = count_q.lte("id", args.before_id)
        else:
            count_q = count_q.lt("created_at", f"{args.before_date}T00:00:00")
        r = count_q.limit(1000).execute()
        total = len(r.data) if r.data else 0
        if total == 0:
            print("No rows with run_mode='LIVE' match the criteria. Nothing to do.")
            return
        print(f"Would update {total} row(s) with run_mode='LIVE' to run_mode='BACKTEST', run_id='imported'.")
        print("\nDry run. Run with --apply to update the database.")
        return

    result = q.execute()
    updated_count = len(result.data) if result.data else 0
    print(f"Done. Updated {updated_count} row(s) to run_mode='BACKTEST', run_id='imported'.")
    print("Dashboard LIVE filter will now show only real webhook/live trades.")


if __name__ == "__main__":
    main()
