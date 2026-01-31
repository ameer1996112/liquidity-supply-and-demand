#!/usr/bin/env python3
"""
Notion CSV to TradingView CSV Converter

Converts manual trade logs from Notion exports into the standardized format
expected by the ML Guardian training pipeline (train_ai_guardian.py).

Input: Notion CSV exports with columns like "Open", "+ R (%)", "Trade Score", etc.
Output: TradingView-style CSV with Signal column in v5.1 Key-Value format.

Author: Data Engineering Pipeline
Version: 1.0.0
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


# =============================================================================
# CONFIGURATION
# =============================================================================

# Paths (relative to this script's location)
SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_DIR = SCRIPT_DIR / "backtest_data" / "notion_exports"
OUTPUT_FILE = SCRIPT_DIR / "backtest_data" / "trades_Notion_Manual.csv"

# Score mapping: Letter grades to numeric scores
SCORE_MAP = {
    "A+": 95,
    "A": 85,
    "A-": 80,
    "B+": 72,
    "B": 65,
    "B-": 58,
    "C+": 55,
    "C": 50,
    "C-": 45,
    "D+": 42,
    "D": 40,
    "D-": 35,
    "F": 20,
}

# Session mapping: Market sessions to encoded integers
# Note: Some Notion entries have multiple sessions (e.g., "London, New York")
# We take the highest priority session
SESSION_MAP = {
    "new york": 3,
    "ny": 3,
    "london": 2,
    "tokyo": 1,
    "asia": 1,
    "sydney": 0,
}

# Zone type mapping
ZONE_MAP = {
    "supply": 0,
    "demand": 1,
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_notion_date(date_str: str) -> Optional[datetime]:
    """
    Parse Notion date format into a datetime object.

    Examples:
        "January 2, 2024 10:30 (GMT+2)" -> datetime(2024, 1, 2, 10, 30)
        "June 12, 2025 18:00 (GMT+3)" -> datetime(2025, 6, 12, 18, 0)
    """
    if pd.isna(date_str) or not date_str:
        return None

    try:
        # Remove timezone info in parentheses for parsing
        date_clean = re.sub(r'\s*\(GMT[+-]?\d+\)', '', str(date_str)).strip()
        # Try parsing with various formats
        for fmt in [
            "%B %d, %Y %H:%M",      # January 2, 2024 10:30
            "%B %d, %Y %I:%M %p",   # January 2, 2024 10:30 AM
            "%Y-%m-%d %H:%M",       # 2024-01-02 10:30
        ]:
            try:
                return datetime.strptime(date_clean, fmt)
            except ValueError:
                continue
        return None
    except Exception:
        return None


def parse_r_multiple(r_str: str) -> Optional[float]:
    """
    Parse R-multiple string into float.

    Examples:
        "3%" -> 3.0
        "-1%" -> -1.0
        "2.5%" -> 2.5
    """
    if pd.isna(r_str) or not r_str:
        return None

    try:
        # Remove % sign and convert to float
        clean = str(r_str).replace('%', '').strip()
        return float(clean)
    except (ValueError, TypeError):
        return None


def map_score(score_str: str) -> int:
    """
    Map letter grade to numeric score.

    Args:
        score_str: Letter grade (e.g., "A+", "B", "C-")

    Returns:
        Numeric score (e.g., 95, 65, 45)
    """
    if pd.isna(score_str) or not score_str:
        return 50  # Default to middle score

    score_upper = str(score_str).strip().upper()
    return SCORE_MAP.get(score_upper, 50)


def map_session(session_str: str) -> int:
    """
    Map session string to encoded integer.
    Takes the highest priority session if multiple are listed.

    Args:
        session_str: Session name(s) (e.g., "London", "London, New York")

    Returns:
        Encoded session (0=Sydney, 1=Asia/Tokyo, 2=London, 3=NY)
    """
    if pd.isna(session_str) or not session_str:
        return 1  # Default to Asia

    session_lower = str(session_str).lower()

    # Find highest priority session mentioned
    max_priority = 0
    for session_name, priority in SESSION_MAP.items():
        if session_name in session_lower:
            max_priority = max(max_priority, priority)

    return max_priority if max_priority > 0 else 1


def map_zone_type(zone_str: str) -> int:
    """
    Map zone type string to encoded integer.

    Args:
        zone_str: Zone type ("Supply" or "Demand")

    Returns:
        Encoded zone type (0=Supply, 1=Demand)
    """
    if pd.isna(zone_str) or not zone_str:
        return 1  # Default to Demand

    zone_lower = str(zone_str).lower().strip()
    return ZONE_MAP.get(zone_lower, 1)


def build_signal_string(
    signal_encoded: int,
    session_encoded: int,
    zone_type: int,
    liq_distance: float,
    source_encoded: int = 2
) -> str:
    """
    Build the v5.1 Key-Value format signal string.

    Format: | F:signal_encoded={score} | F:session_encoded={session} | F:zone_type={zone} | F:liq_distance={dist} | F:source_encoded=2

    Args:
        signal_encoded: Numeric score from trade grade
        session_encoded: Encoded session
        zone_type: Encoded zone type
        liq_distance: Liquidity distance value
        source_encoded: Data source flag (2 = Manual/Human)

    Returns:
        Formatted signal string
    """
    return (
        f" | F:signal_encoded={signal_encoded}"
        f" | F:session_encoded={session_encoded}"
        f" | F:zone_type={zone_type}"
        f" | F:liq_distance={liq_distance:.0f}"
        f" | F:source_encoded={source_encoded}"
    )


def detect_trade_type(zone_type: str, r_value: float) -> str:
    """
    Determine trade type based on zone and outcome.

    Args:
        zone_type: "Supply" or "Demand"
        r_value: R-multiple (positive = win, negative = loss)

    Returns:
        Trade type string (e.g., "Entry long", "Entry short")
    """
    zone_lower = str(zone_type).lower() if zone_type else ""

    # Demand zones = long trades, Supply zones = short trades
    if "demand" in zone_lower:
        return "Entry long"
    elif "supply" in zone_lower:
        return "Entry short"
    else:
        return "Entry long"  # Default


# =============================================================================
# MAIN CONVERSION LOGIC
# =============================================================================

def process_notion_file(file_path: Path) -> Optional[pd.DataFrame]:
    """
    Process a single Notion CSV file and convert to TradingView format.

    Args:
        file_path: Path to the Notion CSV file

    Returns:
        DataFrame in TradingView format, or None if file is invalid
    """
    print(f"  Processing: {file_path.name}")

    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
    except Exception as e:
        print(f"    ERROR reading file: {e}")
        return None

    # Check if this is a valid Notion trade file (must have "+ R (%)" column)
    if "+ R (%)" not in df.columns:
        print(f"    SKIPPED: Missing '+ R (%)' column (not a Notion trade file)")
        return None

    # Check for required columns
    required_cols = ["Open", "+ R (%)", "Trade Score", "Session", "Zone Type"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        print(f"    SKIPPED: Missing required columns: {missing}")
        return None

    # Extract symbol from parent directory name
    symbol = file_path.parent.name

    # Process each row
    rows = []
    trade_num = 0

    for idx, row in df.iterrows():
        # Parse R-multiple (skip rows without valid R value)
        r_value = parse_r_multiple(row.get("+ R (%)"))
        if r_value is None:
            continue

        # Parse date
        open_date = parse_notion_date(row.get("Open"))
        if open_date is None:
            continue

        trade_num += 1

        # Map features
        signal_encoded = map_score(row.get("Trade Score"))
        session_encoded = map_session(row.get("Session"))
        zone_type = map_zone_type(row.get("Zone Type"))

        # Parse liquidity distance (default to 50 if missing)
        liq_distance = row.get("Liquidity Distance", 50)
        try:
            liq_distance = float(liq_distance) if not pd.isna(liq_distance) else 50.0
        except (ValueError, TypeError):
            liq_distance = 50.0

        # Build signal string
        signal = build_signal_string(
            signal_encoded=signal_encoded,
            session_encoded=session_encoded,
            zone_type=zone_type,
            liq_distance=liq_distance,
            source_encoded=2  # Manual/Human data
        )

        # Determine trade type
        trade_type = detect_trade_type(row.get("Zone Type"), r_value)
        exit_type = "Long Exit" if "long" in trade_type else "Short Exit"

        # Calculate P&L percentage (R-multiple is already in percentage)
        pnl_pct = r_value

        # Format datetime
        date_str = open_date.strftime("%Y-%m-%d %H:%M")

        # Create exit row (comes first in TradingView format for display)
        exit_row = {
            "Trade #": trade_num,
            "Type": exit_type,
            "Date and time": date_str,
            "Signal": exit_type,
            "Price": 0,
            "Position size (qty)": 1,
            "Position size (value)": 0,
            "Net P&L USD": 0,
            "Net P&L %": pnl_pct,
            "Favorable excursion USD": 0,
            "Favorable excursion %": max(0, pnl_pct),
            "Adverse excursion USD": 0,
            "Adverse excursion %": min(0, pnl_pct),
            "Cumulative P&L USD": 0,
            "Cumulative P&L %": 0.0,  # Float type to avoid dtype warning
            "Symbol": symbol,
        }
        rows.append(exit_row)

        # Create entry row (comes second - contains the signal data)
        entry_row = {
            "Trade #": trade_num,
            "Type": trade_type,
            "Date and time": date_str,
            "Signal": signal,
            "Price": 0,  # Not available in Notion data
            "Position size (qty)": 1,
            "Position size (value)": 0,
            "Net P&L USD": 0,
            "Net P&L %": pnl_pct,
            "Favorable excursion USD": 0,
            "Favorable excursion %": max(0, pnl_pct),
            "Adverse excursion USD": 0,
            "Adverse excursion %": min(0, pnl_pct),
            "Cumulative P&L USD": 0,
            "Cumulative P&L %": 0.0,  # Float type to avoid dtype warning
            "Symbol": symbol,
        }
        rows.append(entry_row)

    if not rows:
        print(f"    SKIPPED: No valid trades found")
        return None

    result_df = pd.DataFrame(rows)
    print(f"    SUCCESS: Converted {trade_num} trades from {symbol}")
    return result_df


def convert_all_notion_data():
    """
    Main function: Scan all Notion exports and convert to a single TradingView-style CSV.
    """
    print("=" * 60)
    print("Notion to TradingView CSV Converter")
    print("=" * 60)
    print(f"\nInput directory: {INPUT_DIR}")
    print(f"Output file: {OUTPUT_FILE}")
    print()

    if not INPUT_DIR.exists():
        print(f"ERROR: Input directory not found: {INPUT_DIR}")
        return

    # Find all CSV files recursively
    # Filter out "_all.csv" files to avoid duplicates (they contain same data as regular files)
    csv_files = [f for f in INPUT_DIR.rglob("*.csv") if "_all.csv" not in f.name]
    print(f"Found {len(csv_files)} unique CSV files to process\n")

    if not csv_files:
        print("No CSV files found.")
        return

    # Process each file
    all_dfs = []
    for csv_file in csv_files:
        df = process_notion_file(csv_file)
        if df is not None:
            all_dfs.append(df)

    if not all_dfs:
        print("\nNo valid Notion trade data found.")
        return

    # Combine all DataFrames
    combined_df = pd.concat(all_dfs, ignore_index=True)

    # Add a sort key: Exit rows should come before Entry rows for same trade
    # TradingView format: Exit row, then Entry row (Entry has the signal data)
    def type_sort_key(t):
        if "Exit" in str(t):
            return 0  # Exit first
        return 1  # Entry second

    combined_df["_type_order"] = combined_df["Type"].apply(type_sort_key)

    # Sort by date first, then by type order (Exit before Entry for same trade)
    combined_df = combined_df.sort_values(
        by=["Date and time", "Symbol", "_type_order"]
    ).reset_index(drop=True)

    # Remove temporary sort column
    combined_df = combined_df.drop(columns=["_type_order"])

    # Re-number trades sequentially (pair Exit and Entry rows together)
    trade_nums = {}
    current_trade = 0
    for idx in combined_df.index:
        old_num = combined_df.loc[idx, "Trade #"]
        symbol = combined_df.loc[idx, "Symbol"]
        date = combined_df.loc[idx, "Date and time"]
        key = (symbol, date, old_num)  # Unique by symbol, date, and original trade num

        if key not in trade_nums:
            current_trade += 1
            trade_nums[key] = current_trade

        combined_df.loc[idx, "Trade #"] = trade_nums[key]

    # Calculate cumulative P&L (ensure float type)
    combined_df["Cumulative P&L %"] = combined_df["Cumulative P&L %"].astype(float)
    cumulative_pnl = 0.0
    for idx in combined_df.index:
        if "Entry" in str(combined_df.loc[idx, "Type"]):
            cumulative_pnl += float(combined_df.loc[idx, "Net P&L %"])
        combined_df.at[idx, "Cumulative P&L %"] = cumulative_pnl

    # Save to output file
    output_cols = [
        "Trade #", "Type", "Date and time", "Signal", "Price",
        "Position size (qty)", "Position size (value)",
        "Net P&L USD", "Net P&L %",
        "Favorable excursion USD", "Favorable excursion %",
        "Adverse excursion USD", "Adverse excursion %",
        "Cumulative P&L USD", "Cumulative P&L %", "Symbol"
    ]

    combined_df.to_csv(OUTPUT_FILE, columns=output_cols, index=False)

    print("\n" + "=" * 60)
    print("CONVERSION COMPLETE")
    print("=" * 60)
    print(f"Total trades converted: {len(trade_nums)}")
    print(f"Total rows: {len(combined_df)}")
    print(f"Symbols: {combined_df['Symbol'].unique().tolist()}")
    print(f"Date range: {combined_df['Date and time'].min()} to {combined_df['Date and time'].max()}")
    print(f"Output saved to: {OUTPUT_FILE}")

    # Summary statistics
    entry_rows = combined_df[combined_df["Type"].str.contains("Entry")]
    wins = (entry_rows["Net P&L %"] > 0).sum()
    losses = (entry_rows["Net P&L %"] < 0).sum()
    total = len(entry_rows)
    win_rate = (wins / total * 100) if total > 0 else 0

    print(f"\nTrade Statistics:")
    print(f"  Wins: {wins}")
    print(f"  Losses: {losses}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Total R: {entry_rows['Net P&L %'].sum():.2f}R")


if __name__ == "__main__":
    convert_all_notion_data()
