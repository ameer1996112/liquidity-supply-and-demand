"""
Backtest CLI: run SND strategy backtest.

Usage:
  python -m app.backtest_run --symbol XAUUSD --from 2026-01-01 --to 2026-02-10 --timeframe M5
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from app.config import BacktestConfig
from app.data import get_candles
from app.engine import BacktestEngine
from app.outputs import compute_summary, print_summary, write_equity_csv, write_trades_csv
from app.snd_strategy import SNDStrategy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SND backtest")
    parser.add_argument("--symbol", default="XAUUSD", help="Symbol (e.g. XAUUSD)")
    parser.add_argument("--from", dest="from_date", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--timeframe", default="M5", help="Timeframe (M5, M15, H1, etc.)")
    parser.add_argument("--data-dir", type=Path, default=Path("data/backtest_candles"), help="Candle cache dir")
    parser.add_argument("--output-dir", type=Path, default=Path("data/backtest"), help="Output dir for trades/equity")
    parser.add_argument("--tick-size", type=float, default=0.01, help="Instrument tick size (XAUUSD: 0.01)")
    parser.add_argument("--no-fetch", action="store_true", help="Do not fetch from MetaApi (use local only)")
    parser.add_argument("--debug-trades", action="store_true", help="Log each trade with entry reason (FLIP/BREAK_CANDLE/DIR_CLOSE)")
    args = parser.parse_args()

    from_date = datetime.strptime(args.from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    to_date = datetime.strptime(args.to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

    # Config
    cfg = BacktestConfig(
        symbol=args.symbol,
        timeframe=args.timeframe,
        tick_size=args.tick_size,
        pip_size=0.01 if "XAU" in args.symbol else 0.0001,
        start_date=from_date,
        end_date=to_date,
    )

    logger.info("tick_size=%s, timezone=UTC, slippage=3 ticks", cfg.tick_size)

    # Load candles
    meta_token = os.getenv("META_API_TOKEN_VANTAGE") or os.getenv("META_API_TOKEN")
    meta_account = os.getenv("META_API_ACCOUNT_ID_VANTAGE") or os.getenv("META_API_ACCOUNT_ID")
    if not meta_token or not meta_account:
        logger.warning("MetaApi credentials not set; will try local data only")

    try:
        candles = get_candles(
            symbol=args.symbol,
            from_date=from_date,
            to_date=to_date,
            timeframe=args.timeframe,
            data_dir=args.data_dir,
            metaapi_token=None if args.no_fetch else meta_token,
            metaapi_account_id=None if args.no_fetch else meta_account,
            symbol_aliases=cfg.symbol_aliases,
            persist=True,
        )
    except ValueError as e:
        logger.error("Failed to load candles: %s", e)
        return

    logger.info("Loaded %d candles from %s to %s", len(candles), candles["time"].min(), candles["time"].max())

    # Engine + strategy
    engine = BacktestEngine(
        tick_size=cfg.tick_size,
        slippage_ticks=3,
        initial_equity=cfg.account_size_usd,
        commission_pct=0.0,
        pyramiding=0,
        max_bars_held=cfg.max_bars_held,
    )

    strategy = SNDStrategy(config=cfg)

    def on_bar(bar_idx: int, bar: pd.Series, history: pd.DataFrame, has_position: bool):
        return strategy.on_bar(bar_idx, bar, history, has_position)

    trades = engine.run(candles, on_bar)

    # Outputs
    summary = compute_summary(trades, engine.equity_curve)
    print_summary(summary)

    out_dir = args.output_dir / args.symbol
    write_trades_csv(trades, out_dir / "trades.csv")
    write_equity_csv(engine.equity_curve, out_dir / "equity.csv")
    logger.info("Wrote trades to %s", out_dir / "trades.csv")
    if args.debug_trades and trades:
        logger.info("--- DEBUG TRADES (entry_model) ---")
        for t in trades:
            logger.info("  %s | %s @ %.2f -> %.2f | entry_model=%s exit=%s",
                t.entry_time, t.side.value, t.entry_price, t.exit_price, t.entry_comment or "?", t.reason)


if __name__ == "__main__":
    main()
