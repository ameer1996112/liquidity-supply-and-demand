import os
import sys

# Add project root to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from config import get_settings
from supabase import create_client

def main():
    s = get_settings()
    sb = create_client(s.supabase_url, s.supabase_service_role_key or s.supabase_key)

    # Fetch signals 188-200
    print("Fetching signals 188-200...")
    signals = sb.table("trading_signals").select("id").gte("id", 188).lte("id", 200).execute()
    
    if not signals.data:
        print("No signals found in that range.")
        return

    print(f"Found {len(signals.data)} signals to process.")

    count = 0
    for sig in signals.data:
        sig_id = sig["id"]
        corr = f"retro_{sig_id}"
        
        # Check if already exists in ai_runs
        existing = sb.table("ai_runs").select("id").eq("signal_id", sig_id).execute()
        if existing.data and len(existing.data) > 0:
            print(f"Signal {sig_id} already has council data, skipping.")
            continue
            
        print(f"Creating backfill council data for Signal {sig_id}...")
        
        # Insert a dummy "FAST_PATH" allowed AI run row so it displays on the frontend
        row = {
            "correlation_id": corr,
            "signal_id": sig_id,
            "run_type": "debate",
            "recommendation": "allow",
            "confidence": 85,
            "reason_codes": ["FAST_PATH"],
            "memo": "Retroactively backfilled council data (trading council was disabled).",
            "votes": {
                "bear": "allow", 
                "bull": "allow", 
                "judge": "allow", 
                "neutral": "allow", 
                "aggressive": "allow", 
                "conservative": "allow"
            },
            "transcript": [{"role": "system", "content": "Backfilled"}]
        }
        
        try:
            sb.table("ai_runs").insert(row).execute()
            print(f"✅ Success! Generated dummy AI run for signal {sig_id}")
            count += 1
        except Exception as e:
            print(f"❌ Error inserting for {sig_id}: {e}")

    print(f"\nDone! Backfilled {count} signals.")

if __name__ == "__main__":
    main()
