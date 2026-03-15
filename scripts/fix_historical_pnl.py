#!/usr/bin/env python3
"""
Bulk correction script for all historical trades where commission was
incorrectly folded into pnl_usd by the old reconciliation logic.

Correction: pnl_usd = gross profit only (pnl_usd - commission)
This matches what MT5 shows per-trade in its History tab.

Usage:
    python3 scripts/fix_historical_pnl.py
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(url, key)

# All LIVE trades where commission != 0 and was incorrectly included in pnl_usd
trades_to_fix = [
    {'id': 199, 'pnl_usd': 481.0,   'commission': -5.0},    # EURUSD  -> +486.0
    {'id': 197, 'pnl_usd': -261.49, 'commission': -13.9},   # GBPCAD  -> -247.59
    {'id': 196, 'pnl_usd': -270.98, 'commission': -14.2},   # NZDJPY  -> -256.78
    {'id': 195, 'pnl_usd': 359.33,  'commission': -9.95},   # USDJPY  -> +369.28
    {'id': 194, 'pnl_usd': -318.02, 'commission': -30.18},  # USDJPY  -> -287.84
    {'id': 191, 'pnl_usd': -266.19, 'commission': -12.5},   # GBPCAD  -> -253.69
    {'id': 189, 'pnl_usd': -2.72,   'commission': -0.2},    # NZDJPY  -> -2.52
    {'id': 188, 'pnl_usd': -239.64, 'commission': -8.1},    # GBPCAD  -> -231.54
    {'id': 180, 'pnl_usd': -314.44, 'commission': -14.35},  # GBPCAD  -> -300.09
]

print("Correcting historical PnL values (removing commission from pnl_usd)...")
for t in trades_to_fix:
    gross = round(t['pnl_usd'] - t['commission'], 2)  # subtract negative = add back
    outcome = 'win' if gross > 0 else ('loss' if gross < 0 else 'breakeven')
    supabase.table("trading_signals").update({
        'pnl_usd': gross,
        'outcome': outcome,
    }).eq('id', t['id']).execute()
    print(f"  id={t['id']:>4} | {t['pnl_usd']:>10} -> {gross:>10} (commission={t['commission']})")

print("Done.")
