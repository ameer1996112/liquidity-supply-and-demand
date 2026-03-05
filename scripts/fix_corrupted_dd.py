import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))

from config import get_settings
from supabase import create_client

def fix_corrupted_metrics():
    settings = get_settings()
    
    raw_key = settings.supabase_service_role_key or settings.supabase_key or ""
    key = raw_key.strip().strip('"\'').strip()
    if key.upper().startswith("SUPA") and "=" in key[:50]:
        key = key.split("=", 1)[-1].strip().strip('"\'').strip()
        
    if not settings.supabase_url or not key:
        print("❌ Supabase credentials missing.")
        return

    supabase = create_client(settings.supabase_url, key)
    
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    
    print(f"🔍 Looking for corrupted snapshots since {today_start}...")
    
    try:
        # Fetch snapshots from today
        resp = supabase.table("prop_firm_metrics")\
            .select("id, account_name, daily_start_balance, daily_high_water_mark, daily_drawdown_pct")\
            .gte("snapshot_time", today_start)\
            .execute()
            
        if not resp.data:
            print("✅ No snapshots found for today.")
            return
            
        corrupted_count = 0
        for row in resp.data:
            # If DD is impossibly high (e.g. > 50%) or high water mark is far from start balance
            # we reset it. 224.3% definitely qualifies.
            if row["daily_drawdown_pct"] > 50 or row["daily_drawdown_pct"] < -50:
                print(f"⚠️ Fixing corrupted row {row['id']} for account {row['account_name']}: DD={row['daily_drawdown_pct']}%")
                
                # Reset high water mark and drawdown
                supabase.table("prop_firm_metrics").update({
                    "daily_high_water_mark": row["daily_start_balance"],
                    "max_historical_equity": row["daily_start_balance"],
                    "daily_drawdown_pct": 0.0,
                    "daily_pnl_floating": 0.0,
                    "daily_pnl_total": row.get("daily_pnl_closed", 0.0)
                }).eq("id", row["id"]).execute()
                
                corrupted_count += 1
                
        print(f"🎉 Fixed {corrupted_count} corrupted snapshots.")
        
    except Exception as e:
        print(f"❌ Error fixing metrics: {e}")

if __name__ == "__main__":
    fix_corrupted_metrics()
