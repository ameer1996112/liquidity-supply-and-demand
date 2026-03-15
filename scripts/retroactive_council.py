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

    print("Fetching signals 188-200...")
    # Get the raw webhook payloads from the DB (often stored in 'payload' or we can rebuild it)
    signals = sb.table("trading_signals").select("*").gte("id", 188).execute()
    
    if not signals.data:
        print("No signals found in that range.")
        return

    print(f"Found {len(signals.data)} signals to process.")

    from src.ai.trading_council import run_trading_council
    from src.services.ai_run_service import persist_debate, init_ai_run
    from src.services.redis_cache import get_redis
    
    try:
        redis_client = get_redis()
    except Exception as e:
        print(f"Warning: redis failed to init, but we will proceed: {e}")
        redis_client = None

    count = 0
    for sig in signals.data:
        sig_id = sig["id"]
        corr = sig.get("correlation_id") or f"retro_{sig_id}"
        
        # Check if ai_runs already has it
        existing = sb.table("ai_runs").select("id").eq("signal_id", sig_id).execute()
        if existing.data and len(existing.data) > 0:
            print(f"Signal {sig_id} already has council data, skipping.")
            continue
            
        print(f"\nRunning Trading Council for Signal {sig_id} ({sig.get('symbol')})...")
        
        # Reconstruct a basic payload for the council
        payload = {
            "symbol": sig.get("symbol", "UNKNOWN"),
            "side": sig.get("side", "long"),
            "entry": sig.get("entry_price", 0),
            "sl": sig.get("stop_loss", 0),
            "tp": sig.get("take_profit", 0),
            "_correlation_id": corr,
            "zone_id": sig.get("zone_id"),
            "timeframe": sig.get("timeframe", "5m"),
            "run_mode": sig.get("mode", "LIVE"),
            "account_balance": 50000,
            "risk_percent": 0.5
        }
        
        try:
            init_ai_run(sb, corr)
            
            # The council is synchronous in run_trading_council
            council_result = run_trading_council(payload, supabase=sb, redis_client=redis_client)
            
            # Persist it
            run_id = persist_debate(sb, corr, council_result)
            if run_id:
                # Link it!
                sb.table("ai_runs").update({"signal_id": sig_id}).eq("id", run_id).execute()
                print(f"✅ Success! Saved ai_run {run_id} for signal {sig_id}")
                count += 1
            else:
                print(f"❌ Failed to persist run for signal {sig_id}")
                
        except Exception as e:
            print(f"Error running council for {sig_id}: {e}")

    print(f"\nDone! Retroactively generated council data for {count} signals.")

if __name__ == "__main__":
    main()
