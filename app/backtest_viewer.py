"""
Strategy Tester UI - view backtest results similar to TradingView Strategy Tester.

Usage:
  streamlit run app/backtest_viewer.py

  Or after running backtest:
  python -m app.backtest_run --from 2026-01-01 --to 2026-02-10 --no-fetch
  streamlit run app/backtest_viewer.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

# Default paths
DEFAULT_DATA_DIR = Path("data/backtest")
DEFAULT_SYMBOLS = ["XAUUSD", "GBPUSD", "GBPJPY", "NAS100", "CHFJPY", "GBPCAD"]


def load_backtest_data(symbol: str, data_dir: Path) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Load trades.csv and equity.csv for a symbol."""
    base = data_dir / symbol
    trades_path = base / "trades.csv"
    equity_path = base / "equity.csv"

    trades = None
    if trades_path.exists():
        trades = pd.read_csv(trades_path)
        trades["entry_time"] = pd.to_datetime(trades["entry_time"])
        trades["exit_time"] = pd.to_datetime(trades["exit_time"])

    equity = None
    if equity_path.exists():
        equity = pd.read_csv(equity_path)
        equity["time"] = pd.to_datetime(equity["time"])

    return trades, equity


def compute_summary_from_df(trades: pd.DataFrame) -> dict:
    """Compute summary stats from trades DataFrame."""
    if trades.empty:
        return {
            "net_profit": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "win_count": 0,
            "loss_count": 0,
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade": 0.0,
            "avg_bars_held": 0.0,
        }

    wins = trades[trades["pnl"] > 0]
    losses = trades[trades["pnl"] < 0]
    gross_profit = wins["pnl"].sum()
    gross_loss = abs(losses["pnl"].sum())
    net_profit = gross_profit - gross_loss
    pf = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    return {
        "net_profit": net_profit,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "win_count": len(wins),
        "loss_count": len(losses),
        "total_trades": len(trades),
        "win_rate": len(wins) / len(trades) * 100 if len(trades) > 0 else 0.0,
        "profit_factor": pf,
        "avg_trade": net_profit / len(trades) if len(trades) > 0 else 0.0,
        "avg_bars_held": trades["bars_held"].mean() if len(trades) > 0 else 0.0,
    }


def main() -> None:
    st.set_page_config(
        page_title="Strategy Tester",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("📊 Strategy Tester")
    st.caption("SND backtest results – similar to TradingView Strategy Tester")

    # Sidebar
    data_dir = Path(st.sidebar.text_input("Data dir", str(DEFAULT_DATA_DIR)))
    symbols = [d.name for d in data_dir.iterdir() if d.is_dir()] if data_dir.exists() else DEFAULT_SYMBOLS
    symbol = st.sidebar.selectbox("Symbol", symbols, index=0 if symbols else 0)

    trades, equity = load_backtest_data(symbol, data_dir)

    if trades is None or trades.empty:
        st.warning(f"No trades found for {symbol}. Run backtest first: `python -m app.backtest_run --from 2026-01-01 --to 2026-02-10`")
        return

    # Filters
    st.sidebar.subheader("Filters")
    all_sides = trades["side"].unique().tolist()
    side_filter = st.sidebar.multiselect("Side", all_sides, default=all_sides)
    all_models = trades["entry_model"].dropna().unique().tolist()
    model_filter = st.sidebar.multiselect("Entry model", all_models, default=all_models if all_models else [])
    all_reasons = trades["reason"].unique().tolist()
    reason_filter = st.sidebar.multiselect("Exit reason", all_reasons, default=all_reasons)

    filtered = trades[
        trades["side"].isin(side_filter)
        & (trades["entry_model"].isin(model_filter) if model_filter else True)
        & trades["reason"].isin(reason_filter)
    ]

    # Summary cards (TradingView-style)
    summary = compute_summary_from_df(filtered)
    st.subheader("Performance Summary")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Net Profit", f"${summary['net_profit']:,.2f}", delta=None)
    col2.metric("Gross Profit", f"${summary['gross_profit']:,.2f}")
    col3.metric("Gross Loss", f"${summary['gross_loss']:,.2f}")
    col4.metric("Total Trades", summary["total_trades"])
    col5.metric("Win Rate", f"{summary['win_rate']:.1f}%")

    col6, col7, col8, col9, col10 = st.columns(5)
    col6.metric("Profit Factor", f"{summary['profit_factor']:.2f}" if summary["profit_factor"] < 999 else "∞")
    col7.metric("Avg Trade", f"${summary['avg_trade']:,.2f}")
    col8.metric("Avg Bars Held", f"{summary['avg_bars_held']:.1f}")
    col9.metric("Wins", summary["win_count"])
    col10.metric("Losses", summary["loss_count"])

    # Equity curve
    st.subheader("Equity Curve")
    if equity is not None and len(equity) > 1:
        eq_df = equity.copy()
        eq_df = eq_df.rename(columns={"time": "date", "equity": "Equity"})
        st.line_chart(eq_df.set_index("date")[["Equity"]], height=350)
    else:
        # Build from trades if no equity file
        cum = filtered.sort_values("exit_time")["pnl"].cumsum()
        initial = 50_000  # default
        eq_trades = filtered.sort_values("exit_time").copy()
        eq_trades["cum_pnl"] = eq_trades["pnl"].cumsum()
        eq_trades["equity"] = initial + eq_trades["cum_pnl"]
        st.line_chart(eq_trades.set_index("exit_time")[["equity"]], height=350)

    # Trade list
    st.subheader("Trade List")
    display_cols = ["entry_time", "exit_time", "side", "entry_model", "entry_price", "exit_price", "pnl", "bars_held", "reason"]
    available = [c for c in display_cols if c in filtered.columns]
    display_df = filtered[available].copy()
    display_df["pnl"] = display_df["pnl"].apply(lambda x: f"${x:,.2f}")
    st.dataframe(display_df, use_container_width=True, height=400)


if __name__ == "__main__":
    main()
