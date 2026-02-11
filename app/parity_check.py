"""
Parity checker: compare Python backtest trades to TradingView List of Trades CSV.

Usage:
  python -m app.parity_check --tv trades_tv.csv --py trades.csv
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_tv_trades(path: Path) -> pd.DataFrame:
    """Parse TradingView List of Trades CSV export.

    TV format: one row per entry/exit. Columns: Trade #, Type, Date and time, Signal, Price USD, ...
    Merge Entry+Exit rows into one row per trade.
    """
    df = pd.read_csv(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    # TV has 2 rows per trade (Entry + Exit). Pivot to one row per trade.
    entry_rows = df[df["type"].astype(str).str.contains("entry", case=False, na=False)].copy()
    exit_rows = df[df["type"].astype(str).str.contains("exit", case=False, na=False)].copy()
    entry_rows = entry_rows.rename(columns={"date_and_time": "entry_time", "price_usd": "entry_price"})
    exit_rows = exit_rows.rename(columns={"date_and_time": "exit_time", "price_usd": "exit_price"})
    # Merge by trade #
    trade_col = "trade_#" if "trade_#" in df.columns else df.columns[0]
    merged = entry_rows[[trade_col, "entry_time", "entry_price", "type"]].merge(
        exit_rows[[trade_col, "exit_time", "exit_price"]],
        on=trade_col,
        how="left",
    )
    return merged


def parse_py_trades(path: Path) -> pd.DataFrame:
    """Parse our trades.csv output."""
    return pd.read_csv(path)


def _parse_time(s: str) -> Optional[pd.Timestamp]:
    """Parse time string to comparable timestamp."""
    try:
        return pd.to_datetime(s, utc=True)
    except Exception:
        return None


def _tolerance_ticks(price: float, tick_size: float, max_ticks: int = 2) -> float:
    return max_ticks * tick_size


def compare_trades(
    tv_path: Path,
    py_path: Path,
    tick_size: float = 0.01,
    tick_tolerance: int = 2,
) -> dict:
    """
    Compare TV and Python trades. Match by (entry_time, side).

    Returns dict with: missing, extra, mismatches, parity_score, summary.
    """
    tv_df = parse_tv_trades(tv_path)
    py_df = parse_py_trades(py_path)

    # Normalize column names for both
    def norm_df(d: pd.DataFrame, prefix: str) -> pd.DataFrame:
        cols = {}
        for c in d.columns:
            if "entry" in c and "time" in c:
                cols[c] = "entry_time"
            elif "exit" in c and "time" in c:
                cols[c] = "exit_time"
            elif "type" in c or "side" in c or "direction" in c:
                cols[c] = "side"
            elif "entry" in c and "price" not in c.lower() and "entry" in c:
                cols[c] = "entry_price"
            elif "exit" in c and "price" not in c.lower():
                cols[c] = "exit_price"
            elif "entry" in c and "price" in c:
                cols[c] = "entry_price"
            elif "exit" in c and "price" in c:
                cols[c] = "exit_price"
        return d.rename(columns=cols) if cols else d

    tv_df = norm_df(tv_df, "tv")
    py_df = norm_df(py_df, "py")

    # TV: use entry_time (from parse_tv_trades rename) or date_and_time
    entry_col_tv = next((c for c in tv_df.columns if c in ("entry_time", "date_and_time") or ("entry" in c and "time" in c)), "entry_time")
    entry_col_py = next((c for c in py_df.columns if "entry" in c and "time" in c), "entry_time")
    if entry_col_tv not in tv_df.columns:
        entry_col_tv = tv_df.columns[0]

    tv_df["_entry_ts"] = tv_df[entry_col_tv].apply(_parse_time)
    py_df["_entry_ts"] = py_df[entry_col_py].apply(_parse_time)

    def norm_side(s: str) -> str:
        if s is None or (isinstance(s, float) and pd.isna(s)):
            return ""
        s = str(s).upper()
        if "LONG" in s or "BUY" in s:
            return "long"
        if "SHORT" in s or "SELL" in s:
            return "short"
        return s.lower()

    side_series = tv_df.get("side", tv_df.get("type", pd.Series([""])))
    if isinstance(side_series, pd.DataFrame):
        side_series = side_series.iloc[:, 0]
    tv_df["_side"] = side_series.apply(norm_side)
    py_df["_side"] = py_df["side"].apply(norm_side)

    # Build match keys
    tv_keys = set()
    tv_by_key = {}
    for _, row in tv_df.iterrows():
        ts = row["_entry_ts"]
        side = row["_side"]
        if ts is not None and side:
            key = (ts.floor("min"), side)
            tv_keys.add(key)
            tv_by_key[key] = row

    py_keys = set()
    py_by_key = {}
    for _, row in py_df.iterrows():
        ts = row["_entry_ts"]
        side = row["_side"]
        if ts is not None and side:
            key = (ts.floor("min"), side)
            py_keys.add(key)
            py_by_key[key] = row

    missing = list(tv_keys - py_keys)
    extra = list(py_keys - tv_keys)
    matched = list(tv_keys & py_keys)

    tol = tick_tolerance * tick_size
    mismatches = []
    for key in matched:
        tv_row = tv_by_key[key]
        py_row = py_by_key[key]
        tv_entry = tv_row.get("entry_price", tv_row.get("entry", float("nan")))
        py_entry = py_row.get("entry_price")
        tv_exit = tv_row.get("exit_price", tv_row.get("exit", float("nan")))
        py_exit = py_row.get("exit_price")
        try:
            tv_entry = float(tv_entry)
            py_entry = float(py_entry)
            tv_exit = float(tv_exit)
            py_exit = float(py_exit)
        except (TypeError, ValueError):
            continue
        if abs(tv_entry - py_entry) > tol or abs(tv_exit - py_exit) > tol:
            mismatches.append({
                "key": key,
                "tv_entry": tv_entry,
                "py_entry": py_entry,
                "tv_exit": tv_exit,
                "py_exit": py_exit,
            })

    total_tv = len(tv_keys)
    total_py = len(py_keys)
    exact_match = len(matched) - len(mismatches)
    parity_score = (exact_match / total_tv * 100) if total_tv > 0 else 0.0

    return {
        "missing": missing,
        "extra": extra,
        "mismatches": mismatches,
        "parity_score": parity_score,
        "total_tv": total_tv,
        "total_py": total_py,
        "matched": len(matched),
        "exact_match": exact_match,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Parity check: TV vs Python backtest trades")
    parser.add_argument("--tv", required=True, type=Path, help="TradingView List of Trades CSV")
    parser.add_argument("--py", required=True, type=Path, help="Python backtest trades.csv")
    parser.add_argument("--tick-size", type=float, default=0.01, help="Instrument tick size")
    parser.add_argument("--tick-tolerance", type=int, default=2, help="Max ticks difference for match")
    args = parser.parse_args()

    if not args.tv.exists():
        logger.error("TV file not found: %s", args.tv)
        return
    if not args.py.exists():
        logger.error("Python file not found: %s", args.py)
        return

    result = compare_trades(args.tv, args.py, args.tick_size, args.tick_tolerance)

    print("\n=== PARITY REPORT ===")
    print(f"Parity Score:     {result['parity_score']:.1f}%")
    print(f"TV Trades:        {result['total_tv']}")
    print(f"Python Trades:    {result['total_py']}")
    print(f"Matched:         {result['matched']}")
    print(f"Exact Match:     {result['exact_match']}")
    print(f"Missing (in TV, not in Py): {len(result['missing'])}")
    print(f"Extra (in Py, not in TV):   {len(result['extra'])}")
    print(f"Price Mismatches: {len(result['mismatches'])}")

    if result["missing"]:
        print("\n--- Missing trades (first 10) ---")
        for k in result["missing"][:10]:
            print(f"  {k}")

    if result["extra"]:
        print("\n--- Extra trades (first 10) ---")
        for k in result["extra"][:10]:
            print(f"  {k}")

    if result["mismatches"]:
        print("\n--- Price mismatches (first 5) ---")
        for m in result["mismatches"][:5]:
            print(f"  {m['key']}: TV entry={m['tv_entry']} py entry={m['py_entry']} | TV exit={m['tv_exit']} py exit={m['py_exit']}")


if __name__ == "__main__":
    main()
