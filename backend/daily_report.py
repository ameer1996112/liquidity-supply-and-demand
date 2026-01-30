#!/usr/bin/env python3
"""
Daily Trading Report
====================
Quick snapshot of system performance for the last 24 hours.

Usage:
    python daily_report.py
"""

from backend import supabase_db
from datetime import datetime, timedelta
from collections import defaultdict

def generate_daily_report():
    """Generate daily summary"""
    print("="*60)
    print(f"📊 DAILY TRADING REPORT - {datetime.utcnow().strftime('%Y-%m-%d')}")
    print("="*60)

    # Initialize Supabase
    supabase_db.init_supabase()

    # Get all trades
    all_trades = supabase_db.supabase.table('trading_signals').select('*').execute().data

    # Last 24 hours
    from datetime import timezone
    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_24h = [
        t for t in all_trades
        if datetime.fromisoformat(t['created_at'].replace('Z', '+00:00')) >= cutoff_24h
    ]

    # Last 7 days
    cutoff_7d = datetime.now(timezone.utc) - timedelta(days=7)
    recent_7d = [
        t for t in all_trades
        if datetime.fromisoformat(t['created_at'].replace('Z', '+00:00')) >= cutoff_7d
    ]

    print(f"\n📥 SIGNAL VOLUME")
    print(f"   Last 24 Hours: {len(recent_24h)} signals")
    print(f"   Last 7 Days:   {len(recent_7d)} signals")
    print(f"   All Time:      {len(all_trades)} signals")

    # Breakdown by status
    print(f"\n📊 TRADE STATUS (Last 7 Days)")
    status_counts = defaultdict(int)
    for t in recent_7d:
        status_counts[t.get('status', 'unknown')] += 1

    for status, count in sorted(status_counts.items()):
        print(f"   {status.capitalize():12s}: {count:3d}")

    # Win Rate Analysis
    closed_trades = [t for t in recent_7d if t.get('status') == 'closed' and t.get('outcome') in ['win', 'loss']]

    if len(closed_trades) > 0:
        wins = sum(1 for t in closed_trades if t.get('outcome') == 'win')
        losses = len(closed_trades) - wins
        win_rate = wins / len(closed_trades)

        print(f"\n🎯 PERFORMANCE (Last 7 Days)")
        print(f"   Closed: {len(closed_trades)} trades")
        print(f"   Wins:   {wins} ({win_rate:.1%})")
        print(f"   Losses: {losses}")

        # Average R:R and P&L
        avg_rr = sum(t.get('rr_ratio', 0) for t in closed_trades) / len(closed_trades)
        total_pnl = sum(t.get('pnl_r', 0) or 0 for t in closed_trades)

        print(f"   Avg R:R: 1:{avg_rr:.2f}")
        print(f"   Total P&L: {total_pnl:+.2f}R")

        # Symbol breakdown
        symbol_wins = defaultdict(lambda: {'wins': 0, 'total': 0})
        for t in closed_trades:
            symbol = t.get('symbol', 'UNKNOWN')
            symbol_wins[symbol]['total'] += 1
            if t.get('outcome') == 'win':
                symbol_wins[symbol]['wins'] += 1

        print(f"\n📈 BY SYMBOL (Last 7 Days)")
        for symbol in sorted(symbol_wins.keys()):
            data = symbol_wins[symbol]
            wr = data['wins'] / data['total'] if data['total'] > 0 else 0
            print(f"   {symbol:8s}: {data['wins']}/{data['total']} ({wr:.0%})")

    else:
        print(f"\n⏳ No closed trades yet in last 7 days.")
        print(f"   Open trades: {len([t for t in recent_7d if t.get('status') == 'active'])}")

    # Data collection progress
    print(f"\n📦 DATA COLLECTION PROGRESS")
    target_samples = 50
    current_samples = len(closed_trades)
    progress = min(100, (current_samples / target_samples) * 100)

    print(f"   Target: {target_samples} closed trades for validation")
    print(f"   Current: {current_samples} closed trades")
    print(f"   Progress: [{'='*int(progress//5)}{' '*(20-int(progress//5))}] {progress:.0f}%")

    if current_samples < target_samples:
        days_to_go = max(1, (target_samples - current_samples) / max(1, len(recent_7d) / 7))
        print(f"   Estimate: ~{days_to_go:.0f} more days to reach target")
    else:
        print(f"   ✅ Ready for shadow mode analysis!")

    print("\n" + "="*60)
    print("💡 NEXT STEPS:")
    if current_samples < 10:
        print("   1. Keep collecting data (need 10+ closed trades)")
        print("   2. Focus on trade execution quality")
        print("   3. Check webhook logs for any issues")
    elif current_samples < 50:
        print("   1. Run: python monitor_shadow_mode.py")
        print("   2. Review model predictions vs outcomes")
        print("   3. Continue collecting data to 50+ trades")
    else:
        print("   1. Run: python monitor_shadow_mode.py")
        print("   2. Decide: Enable AI filter OR Retrain model")
        print("   3. If enabling filter, start with threshold=0.45")

    print("="*60)

if __name__ == '__main__':
    generate_daily_report()
