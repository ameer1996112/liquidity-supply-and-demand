#!/usr/bin/env python3
"""
Diagnose High Latency Issues
Shows breakdown of execution time for recent trades
"""

import sys
from pathlib import Path

# Add project root to path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from src.adapters.supabase import init_supabase
from datetime import datetime, timedelta
import json

def main():
    client = init_supabase()

    # Get recent NZDJPY trades with high latency
    cutoff = (datetime.now() - timedelta(hours=3)).isoformat()

    print("\n" + "="*120)
    print("EXECUTION LATENCY ANALYSIS - Recent NZDJPY Trades")
    print("="*120 + "\n")

    # Fetch TCA metrics joined with trading_signals to get symbol
    response = client.table('tca_execution_metrics')\
        .select('*, trading_signals!inner(symbol, status, created_at, received_at)')\
        .gte('created_at', cutoff)\
        .order('created_at', desc=True)\
        .limit(50)\
        .execute()

    # Filter for NZDJPY only
    response.data = [r for r in response.data if r.get('trading_signals', {}).get('symbol') == 'NZDJPY']

    if not response.data:
        print("❌ No recent NZDJPY trades found in TCA metrics")
        return

    print(f"Found {len(response.data)} recent NZDJPY trade(s):\n")

    for i, row in enumerate(response.data, 1):
        signal_id = row.get('signal_id')
        signal_data = row.get('trading_signals', {})
        symbol = signal_data.get('symbol', 'UNKNOWN')

        signal_to_submit = row.get('signal_to_submit_ms') or 0
        submit_to_fill = row.get('submit_to_fill_ms') or 0
        total = row.get('total_execution_ms') or 0
        created = row.get('created_at', '')

        sig_status = signal_data.get('status', 'unknown')
        sig_created = signal_data.get('created_at')
        sig_received = signal_data.get('received_at')

        print(f"Trade #{i} - Signal ID: {signal_id} - {symbol}")
        print(f"  Created: {created}")
        print(f"  Status: {sig_status}")
        print(f"  ┌─ Signal → Submit: {signal_to_submit:,}ms ({signal_to_submit/1000:.1f}s) {'⚠️  SLOW' if signal_to_submit > 5000 else ''}")
        print(f"  ├─ Submit → Fill:   {submit_to_fill:,}ms ({submit_to_fill/1000:.1f}s) {'⚠️  SLOW' if submit_to_fill > 2000 else ''}")
        print(f"  └─ TOTAL LATENCY:   {total:,}ms ({total/1000:.1f}s) {'🔴 ALERT' if total > 5000 else '✅ OK'}")

        # Calculate webhook latency
        if sig_created and sig_received:
            created_dt = datetime.fromisoformat(sig_created.replace('Z', '+00:00'))
            received_dt = datetime.fromisoformat(sig_received.replace('Z', '+00:00'))
            webhook_latency = int((received_dt - created_dt).total_seconds() * 1000)

            print(f"  │")
            print(f"  └─ Webhook Latency: {webhook_latency:,}ms ({webhook_latency/1000:.1f}s) {'⚠️  NETWORK DELAY' if webhook_latency > 1000 else ''}")

        print()

    # Analysis summary
    print("\n" + "="*120)
    print("LATENCY BREAKDOWN ANALYSIS")
    print("="*120 + "\n")

    avg_signal_to_submit = sum(r.get('signal_to_submit_ms', 0) for r in response.data) / len(response.data)
    avg_submit_to_fill = sum(r.get('submit_to_fill_ms', 0) for r in response.data) / len(response.data)

    print(f"Average Signal → Submit: {avg_signal_to_submit:,.0f}ms ({avg_signal_to_submit/1000:.1f}s)")
    print(f"Average Submit → Fill:   {avg_submit_to_fill:,.0f}ms ({avg_submit_to_fill/1000:.1f}s)")
    print()

    if avg_signal_to_submit > 10000:
        print("⚠️  HIGH 'Signal → Submit' LATENCY DETECTED")
        print("   This includes:")
        print("   - Webhook reception time (network)")
        print("   - Guard rail processing (kill switch, AI ensemble, PropGuard, etc.)")
        print("   - Position sizing calculations")
        print("   - Portfolio VaR guard (requires fetching all active positions)")
        print("   - Sector exposure guard (requires fetching all active positions)")
        print("   - Correlation manager (requires historical correlation matrix)")
        print()
        print("   Possible causes:")
        print("   1. AI ensemble timeout (default 5s per AI provider)")
        print("   2. Database query slowness (too many active positions)")
        print("   3. Historical returns fetching (yfinance API)")
        print("   4. Network latency between bot and TradingView")
        print()

    if avg_submit_to_fill > 2000:
        print("⚠️  HIGH 'Submit → Fill' LATENCY DETECTED")
        print("   This is the broker execution time (MetaAPI → broker)")
        print("   Possible causes:")
        print("   1. Broker API slowness")
        print("   2. Market volatility (requotes)")
        print("   3. MetaAPI proxy latency")
        print()

    print("\n" + "="*120)
    print("RECOMMENDATIONS")
    print("="*120 + "\n")

    if avg_signal_to_submit > 10000:
        print("1. Enable latency instrumentation to see detailed breakdown:")
        print("   export ENABLE_LATENCY_INSTRUMENTATION=true")
        print()
        print("2. Consider disabling AI ensemble for high-confidence signals (fast-path):")
        print("   export FAST_PATH_RF_THRESHOLD=0.85  # Skip LLM for RF confidence > 85%")
        print()
        print("3. Optimize portfolio guards (cache active positions in Redis):")
        print("   export PORTFOLIO_CACHE_TTL_SECONDS=10")
        print()

    if avg_submit_to_fill > 2000:
        print("4. Check MetaAPI broker latency:")
        print("   - Use MetaAPI dashboard to check broker ping times")
        print("   - Consider switching to a faster broker server location")
        print()

    print("5. Increase TCA latency threshold if these delays are expected:")
    print(f"   export TCA_LATENCY_THRESHOLD_MS=30000  # Current: 5000ms")
    print()

if __name__ == "__main__":
    main()
