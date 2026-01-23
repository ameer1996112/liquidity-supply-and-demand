#!/usr/bin/env python3
"""
Database Migration Script - Add Telemetry Columns
Run once to upgrade existing trades.db schema
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / 'trades.db'

def migrate_database():
    """Add new columns to alerts table"""
    print("=" * 60)
    print("DATABASE MIGRATION: Adding Telemetry Columns")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Define all new columns
    new_columns = [
        # Exit telemetry
        ('exit_type', 'TEXT'),
        ('bars_held', 'INTEGER'),
        ('mae_pips', 'REAL'),
        ('pnl_r', 'REAL'),

        # AI features
        ('score', 'REAL'),
        ('freshness', 'INTEGER'),
        ('session', 'INTEGER'),
        ('atr_ratio', 'REAL'),
        ('trend', 'INTEGER'),
        ('rsi', 'REAL'),
        ('htf_trend', 'INTEGER'),
        ('rvol', 'REAL'),
        ('adx', 'REAL'),
        ('touch_count', 'INTEGER'),
        ('base_quality', 'REAL'),
        ('departure_strength', 'REAL'),
        ('liquidity_distance', 'REAL'),
        ('liquidity_spread', 'REAL'),
        ('return_strength', 'REAL'),

        # Computed features (populated later)
        ('time_to_target_ratio', 'REAL'),
        ('drawdown_liq_alignment', 'REAL'),
        ('liq_invalidation_rate', 'INTEGER'),
        ('liq_confidence_score', 'REAL'),
    ]

    added_count = 0
    skipped_count = 0

    for col_name, col_type in new_columns:
        try:
            cursor.execute(f'ALTER TABLE alerts ADD COLUMN {col_name} {col_type}')
            print(f"  ✅ Added column: {col_name} ({col_type})")
            added_count += 1
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e).lower():
                print(f"  ⏭️  Skipped (exists): {col_name}")
                skipped_count += 1
            else:
                print(f"  ❌ Error adding {col_name}: {e}")

    conn.commit()
    conn.close()

    print()
    print("=" * 60)
    print(f"✅ Migration Complete")
    print(f"   Added: {added_count} columns")
    print(f"   Skipped: {skipped_count} columns (already exist)")
    print("=" * 60)

if __name__ == '__main__':
    migrate_database()
