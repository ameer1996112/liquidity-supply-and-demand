#!/usr/bin/env python3
"""
TradingView Strategy Optimizer via Playwright (Google Chrome)

Automates the process of finding optimal PineScript settings per trading pair:
1. Connects to your open Chrome browser (you must be logged into TradingView)
2. Switches to each pair's 5-minute chart
3. Opens strategy settings and tries parameter combinations
4. Records backtest results (PF, win rate, net profit, max DD, trades)
5. Picks the best settings per pair
6. Outputs results to CSV + generates Pine preset code

Usage:
    # Step 1: Start Chrome with remote debugging:
    #   open -a "Google Chrome" --args --remote-debugging-port=9222

    # Step 2: Open TradingView and navigate to any chart with S&D Algo [Pro] loaded

    # Step 3: Run the optimizer (use venv python):
    source venv/bin/activate && python3 scripts/optimize_pairs.py

    # Or optimize specific pairs:
    python3 scripts/optimize_pairs.py --pairs EURUSD,GBPJPY,XAUUSD

    # Or customize parameter ranges:
    python3 scripts/optimize_pairs.py --fast  # Quick scan (fewer combos, ~5 min/pair)
"""

# Auto-activate venv if not already active
import os
import sys

if "_OPTIMIZER_VENV_ACTIVE" not in os.environ:
    VENV_PYTHON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "venv", "bin", "python3")
    if os.path.exists(VENV_PYTHON):
        os.environ["_OPTIMIZER_VENV_ACTIVE"] = "1"
        os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

print("Starting TradingView Strategy Optimizer...")

import asyncio
import csv
import json
import math
import os
import sys
import time
from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

try:
    from playwright.async_api import async_playwright, Page, Browser
except ImportError:
    print("ERROR: playwright not installed. Run: pip3 install playwright")
    sys.exit(1)


# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "scripts" / "optimization_results"
RESULTS_DIR.mkdir(exist_ok=True)

# Default pairs to optimize (grouped by asset class)
DEFAULT_PAIRS = [
    # Major USD Pairs
    "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF",
    # JPY Pairs
    "USDJPY", "GBPJPY", "EURJPY", "NZDJPY", "CADJPY", "AUDJPY", "CHFJPY",
    # GBP Crosses
    "EURGBP", "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD",
    # EUR Crosses
    "EURAUD", "EURCAD", "EURCHF", "EURNZD",
    # AUD/NZD Crosses
    "AUDNZD", "AUDCAD", "AUDCHF",
    # CAD/CHF Crosses
    "CADCHF", "NZDCAD", "NZDCHF",
    # Gold & Metals
    "XAUUSD", "XAGUSD",
    # Indices
    "NAS100", "US30", "US500",
]

# Parameters to optimize and their search ranges
# Format: {param_name: [values_to_test]}
PARAM_GRID_FULL = {
    "liq_max_distance_pips_forex": [10.0, 15.0, 20.0, 25.0, 30.0],
    "ai_quality_threshold": [40, 50, 55, 60, 65, 70],
    "min_tp_distance_pips": [5.0, 8.0, 10.0, 12.0, 15.0],
    "max_sweep_to_touch_bars": [8, 12, 15, 20, 25],
    "max_peak_to_touch_bars": [20, 25, 30, 40, 50],
}

PARAM_GRID_FAST = {
    "liq_max_distance_pips_forex": [12.0, 18.0, 25.0],
    "ai_quality_threshold": [50, 60, 70],
    "min_tp_distance_pips": [5.0, 10.0, 15.0],
    "max_sweep_to_touch_bars": [10, 15, 20],
    "max_peak_to_touch_bars": [25, 35, 50],
}

# Gold-specific parameters (different scale)
PARAM_GRID_GOLD = {
    "liq_max_distance_pips_gold": [80.0, 120.0, 150.0, 200.0],
    "ai_quality_threshold": [40, 50, 60, 70],
    "min_tp_distance_pips": [5.0, 10.0, 15.0],
    "max_sweep_to_touch_bars": [10, 15, 20],
    "max_peak_to_touch_bars": [25, 35, 50],
}

# Index-specific parameters
PARAM_GRID_INDEX = {
    "liq_max_distance_pips_index": [300.0, 400.0, 500.0, 700.0],
    "ai_quality_threshold": [40, 50, 60],
    "min_tp_distance_pips": [5.0, 8.0, 12.0],
    "max_sweep_to_touch_bars": [10, 15, 20],
    "max_peak_to_touch_bars": [25, 35, 50],
}

# Map parameter names to their INPUT INDEX in TradingView settings dialog
# These indices were discovered by tv_debug3.py on 2026-04-06
# The dialog has inputs[0..56], indexed in DOM order
INPUT_INDEX = {
    "account_size_usd": 0,           # 50000
    "risk_per_trade_pct": 1,         # 0.5
    "max_zones": 8,                  # 20
    "min_body_perc": 9,              # 50
    "liq_pivot_len": 12,             # 5 (Pivot Strength)
    "pvtMax": 13,                    # 5 (Max Liquidity Lines)
    "liq_max_distance_pips_forex": 15,  # 20
    "liq_max_distance_pips_gold": 16,   # 150
    "liq_max_distance_pips_index": 17,  # 500
    "liq_entry_max_dist": 18,        # 10 (Max Zone-to-Liq Distance)
    "stop_loss_buffer_pips": 31,     # 1 (SL Buffer Pips)
    "use_custom_rr": 32,             # checkbox: Override Use Fixed RR
    "risk_reward_ratio": 33,         # 3 (Custom R:R Ratio)
    "min_tp_distance_pips": 34,      # 15
    "take_profit_pips": 35,          # 0 (Fixed TP Override)
    "use_break_even": 36,            # checkbox: Break-Even Mode
    "max_bars_held": 37,             # 72 (Time-Based Exit)
    "enable_double_tp": 38,          # checkbox: Double TP Mode
    "max_position_size_lots": 39,    # 100
    "max_lots_per_10k": 40,          # 10
    "max_usd_risk_cap": 41,          # 0
    "max_daily_loss_pct": 43,        # 4
    "max_daily_profit_pct": 44,      # 5
    "max_trades_per_day": 46,        # 2
    "trading_start_hour": 48,        # 6
    "trading_end_hour": 49,          # 22
    "enable_ai_quality_filter": 51,  # checkbox: AI Quality Filter
    "ai_quality_threshold": 52,      # 60
    "max_peak_to_touch_bars": 55,    # 30
    "max_sweep_to_touch_bars": 56,   # 15
}

# CHECKBOX indices — these need special handling (toggle, not fill)
CHECKBOX_INDICES = {32, 36, 38, 51}

# Hill-climbing parameter definitions: ordered by expected impact
# Each entry: (param_name, [values_to_test], type)
# type: "numeric" = use fill(), "checkbox" = toggle on/off, "rr_mode" = special handling
HILL_CLIMB_PARAMS = [
    # 1. RR Mode: dynamic rules (checkbox off) vs fixed 2.5 vs fixed 4.0
    ("rr_mode", ["dynamic", "fixed_2.5", "fixed_4.0"], "rr_mode"),
    # 2. AI Filter on/off
    ("enable_ai_quality_filter", [True, False], "checkbox"),
    # 3. AI threshold (only matters if AI filter is on)
    ("ai_quality_threshold", [50, 60, 70], "numeric"),
    # 4. Min TP Distance
    ("min_tp_distance_pips", [5, 10, 15], "numeric"),
    # 5. Liq Distance (asset-class dependent — resolved at runtime)
    ("liq_distance", [10, 20, 30], "liq_distance"),
    # 6. Time-Based Exit
    ("max_bars_held", [24, 48, 72], "numeric"),
    # 7. SL Buffer
    ("stop_loss_buffer_pips", [0.5, 1.0, 2.0], "numeric"),
    # 8. Break-Even Mode
    ("use_break_even", [True, False], "checkbox"),
    # 9. Double TP Mode
    ("enable_double_tp", [True, False], "checkbox"),
    # 10. Pivot Strength
    ("liq_pivot_len", [3, 5, 8], "numeric"),
    # 11. Max Liquidity Lines
    ("pvtMax", [3, 5, 10], "numeric"),
    # 12. Max Sweep to Touch Bars
    ("max_sweep_to_touch_bars", [10, 15, 20], "numeric"),
    # 13. Max Peak to Touch Bars
    ("max_peak_to_touch_bars", [25, 35, 50], "numeric"),
    # 14. Min Body %
    ("min_body_perc", [30, 50, 70], "numeric"),
    # 15. Max Zones Displayed
    ("max_zones", [10, 20, 30], "numeric"),
    # 16. Max Trades/Day
    ("max_trades_per_day", [1, 2, 3], "numeric"),
]


@dataclass
class BacktestResult:
    """Single backtest result for a parameter combination."""
    symbol: str
    params: dict
    net_profit: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    profitable_trades: int = 0
    score: float = 0.0  # Composite optimization score
    timestamp: str = ""

    def calculate_score(self):
        """
        Composite score: PF * sqrt(trades) * (1 - DD%/100)²
        DD penalty is squared to heavily penalize high drawdown (prop firm priority).
        """
        if self.total_trades < 10 or self.profit_factor <= 0:
            self.score = 0.0
            return
        trade_factor = math.sqrt(self.total_trades)
        dd_penalty = max(0.0, 1.0 - self.max_drawdown_pct / 100.0)
        self.score = self.profit_factor * trade_factor * (dd_penalty ** 2)


class TabWorker:
    """Handles optimization on a single TradingView tab. Safe for parallel use."""

    def __init__(self, page: Page, optimizer: 'TradingViewOptimizer'):
        self.page = page
        self.optimizer = optimizer
        self.results: list[BacktestResult] = []

    async def _switch_symbol(self, symbol: str):
        """Switch chart to a different symbol using URL-based navigation."""
        clean_symbol = symbol.split(":")[-1].upper().strip()

        # Check if already on this symbol
        try:
            title = await self.page.title()
            title_symbol = title.split(" ")[0].split(":")[-1].upper().strip() if title else ""
            if title_symbol == clean_symbol:
                print(f"  Already on {clean_symbol}, skipping switch")
                await self._wait_for_load()
                return
        except Exception:
            pass

        # Extract chart ID from URL
        current_url = self.page.url
        chart_id = ""
        if "/chart/" in current_url:
            try:
                chart_id = current_url.split("/chart/")[1].split("/")[0].split("?")[0]
            except (IndexError, ValueError):
                pass

        if not chart_id:
            raise RuntimeError(f"Cannot switch symbol: no chart ID in URL {current_url}")

        target_url = f"https://www.tradingview.com/chart/{chart_id}/?symbol=VANTAGE%3A{clean_symbol}"
        print(f"  Navigating to VANTAGE:{clean_symbol}...")

        try:
            await self.page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"  Navigation warning: {e}")

        await asyncio.sleep(3.0)
        await self._wait_for_load()

        # Verify
        try:
            new_title = await self.page.title()
            new_sym = new_title.split(" ")[0].split(":")[-1].upper().strip() if new_title else ""
            if clean_symbol in new_sym or new_sym in clean_symbol:
                print(f"  Switched to {clean_symbol} (verified)")
            else:
                print(f"  Warning: Expected {clean_symbol}, title shows '{new_sym}'")
        except Exception:
            pass

    async def _wait_for_load(self, timeout: int = 30):
        """Wait for chart and strategy tester to finish loading."""
        await asyncio.sleep(1.0)
        start = time.time()
        while time.time() - start < timeout:
            try:
                loading = await self.page.evaluate("""
                    (() => {
                        const indicators = ['Updating report', 'Calculating...', 'Loading...', 'Compiling...'];
                        for (const el of document.querySelectorAll('*')) {
                            const t = el.textContent?.trim();
                            if (indicators.includes(t) && el.offsetParent !== null
                                && el.getBoundingClientRect().height > 0 && el.children.length <= 2)
                                return t;
                        }
                        return null;
                    })()
                """)
                if not loading:
                    await asyncio.sleep(0.5)
                    return
            except Exception:
                pass
            await asyncio.sleep(0.5)

    async def optimize_pair(self, symbol: str) -> Optional[BacktestResult]:
        """Run full optimization for one symbol on this tab."""
        tag = f"[{symbol}]"
        print(f"\n{'=' * 60}")
        print(f"{tag} OPTIMIZING: {symbol}")
        print(f"{'=' * 60}")

        # Switch to the correct symbol first
        await self._switch_symbol(symbol)

        param_grid = self.optimizer.get_param_grid(symbol)
        combos = self.optimizer.generate_combinations(param_grid)
        total = len(combos)
        print(f"{tag} Testing {total} combinations...")

        best = None
        for idx, params in enumerate(combos, 1):
            param_str = " | ".join(f"{k.split('_')[-1]}={v}" for k, v in params.items())
            print(f"  {tag} [{idx}/{total}] {param_str}", end="", flush=True)

            success = await self._apply_params(params)
            if not success:
                print(" -> SKIP")
                continue

            result = await self._read_results(symbol, params)
            self.results.append(result)

            pf = f"PF={result.profit_factor:.2f}" if result.profit_factor else "PF=N/A"
            wr = f"WR={result.win_rate:.1f}%" if result.win_rate else "WR=N/A"
            trades = f"T={result.total_trades}" if result.total_trades else "T=0"
            print(f" -> {pf} {wr} {trades} Score={result.score:.1f}")

            if best is None or result.score > best.score:
                best = result
                print(f"  {tag} >>> NEW BEST! Score={result.score:.1f} PF={result.profit_factor:.2f}")

        if best:
            print(f"\n  {tag} BEST: PF={best.profit_factor:.2f} WR={best.win_rate:.1f}% T={best.total_trades} Score={best.score:.1f}")
            print(f"  {tag} Settings: {best.params}")

        return best

    async def _open_settings(self):
        """Open strategy settings dialog on this tab's page."""
        is_open = await self.page.evaluate("""
            (() => {
                const d = document.querySelector('[class*="dialog-"][class*="rounded"]');
                return d && d.offsetParent !== null;
            })()
        """)
        if is_open:
            return True

        el = await page_query_snd(self.page)
        if el:
            await el.dblclick()
            await asyncio.sleep(1.5)
            return True

        # Fallback
        await self.page.evaluate("""
            (() => {
                const divs = document.querySelectorAll('div');
                for (const d of divs) {
                    if (d.textContent?.trim() === 'S&D Algo [Pro]'
                        && d.children.length <= 2
                        && d.getBoundingClientRect().width < 300) {
                        d.dispatchEvent(new MouseEvent('dblclick', {bubbles: true}));
                        return;
                    }
                }
            })()
        """)
        await asyncio.sleep(1.5)
        return True

    async def _set_input(self, index: int, value):
        """Set input by index using Playwright fill()."""
        handle = await self.page.evaluate_handle(f"""
            (() => {{
                const d = document.querySelector('[class*="dialog-"][class*="rounded"]');
                if (!d) return null;
                const inputs = d.querySelectorAll('input');
                return ({index} < inputs.length) ? inputs[{index}] : null;
            }})()
        """)
        el = handle.as_element()
        if not el:
            return False
        try:
            inp_type = await el.get_attribute("type")
            if inp_type == "checkbox":
                return True
            await el.scroll_into_view_if_needed()
            await el.fill(str(value))
            return True
        except Exception:
            return False

    async def _apply_params(self, params: dict) -> bool:
        """Open dialog, set params, click Ok, wait for recalc."""
        if not await self._open_settings():
            return False
        await asyncio.sleep(0.5)

        # Click Inputs tab
        await self.page.evaluate("""
            (() => {
                for (const b of document.querySelectorAll('button')) {
                    if (b.textContent?.trim() === 'Inputs') { b.click(); return; }
                }
            })()
        """)
        await asyncio.sleep(0.3)

        # Check profile is Custom
        profile = await self.page.evaluate("""
            (() => {
                const d = document.querySelector('[class*="dialog-"][class*="rounded"]');
                if (!d) return '';
                const combo = d.querySelector('button[role="combobox"]');
                return combo?.textContent?.trim() || '';
            })()
        """)
        if profile != 'Custom':
            print(f" [WARN: profile={profile}, need Custom]", end="")

        # Set each param
        for name, value in params.items():
            idx = INPUT_INDEX.get(name)
            if idx is not None:
                await self._set_input(idx, value)

        # Click Ok
        try:
            ok = await self.page.query_selector('button:has-text("Ok")')
            if ok:
                await ok.click()
            else:
                await self.page.keyboard.press("Enter")
        except Exception:
            await self.page.keyboard.press("Enter")

        # Wait for dialog to close
        for _ in range(20):
            gone = await self.page.evaluate("""
                !document.querySelector('[class*="dialog-"][class*="rounded"]')?.offsetParent
            """)
            if gone:
                break
            await asyncio.sleep(0.3)

        # Wait for "Updating report" to finish
        await asyncio.sleep(1.0)
        for _ in range(60):
            updating = await self.page.evaluate("""
                (() => {
                    for (const el of document.querySelectorAll('*')) {
                        const t = el.textContent?.trim();
                        if ((t === 'Updating report' || t === 'Calculating...')
                            && el.offsetParent && el.getBoundingClientRect().height > 0)
                            return true;
                    }
                    return false;
                })()
            """)
            if not updating:
                break
            await asyncio.sleep(0.5)

        await asyncio.sleep(1.0)
        return True

    async def _read_results(self, symbol: str, params: dict) -> BacktestResult:
        """Read strategy tester metrics from this tab."""
        result = BacktestResult(symbol=symbol, params=params.copy(),
                                timestamp=datetime.now().isoformat())
        try:
            metrics = await self.page.evaluate("""
                (() => {
                    const r = {};
                    for (const cell of document.querySelectorAll('[class*="containerCell-"]')) {
                        const t = cell.querySelector('[class*="title-"]');
                        const vals = cell.querySelectorAll('[class*="value-"], [class*="additional-"]');
                        if (t) {
                            const vs = [];
                            for (const v of vals) { const x = v.textContent?.trim(); if (x) vs.push(x); }
                            if (vs.length) r[t.textContent.trim()] = vs.join('|');
                        }
                    }
                    return r;
                })()
            """)
            for key, value in (metrics or {}).items():
                kl = key.lower()
                c = value.split('|')[0].replace("$","").replace(",","").replace("%","")
                c = c.replace("USD","").replace(" ","").replace("\u2212","-").replace("−","-").replace("+","")
                try:
                    num = float(c)
                except (ValueError, TypeError):
                    continue
                if "total p&l" in kl:
                    result.net_profit = num
                elif "total trades" in kl:
                    result.total_trades = int(num)
                elif "profitable" in kl:
                    result.win_rate = num
                elif "profit factor" in kl:
                    result.profit_factor = num
                elif "drawdown" in kl:
                    result.max_drawdown = num
            if result.max_drawdown > 0 and result.max_drawdown_pct == 0:
                result.max_drawdown_pct = (result.max_drawdown / 50000) * 100
        except Exception as e:
            print(f" [read error: {e}]", end="")
        result.calculate_score()
        return result


    async def _toggle_checkbox(self, index: int, desired_state: bool):
        """Toggle a checkbox to the desired state (True=checked, False=unchecked)."""
        handle = await self.page.evaluate_handle(f"""
            (() => {{
                const d = document.querySelector('[class*="dialog-"][class*="rounded"]');
                if (!d) return null;
                const inputs = d.querySelectorAll('input');
                return ({index} < inputs.length) ? inputs[{index}] : null;
            }})()
        """)
        el = handle.as_element()
        if not el:
            return False
        try:
            is_checked = await el.is_checked()
            if is_checked != desired_state:
                await el.click()
                await asyncio.sleep(0.1)
            return True
        except Exception:
            return False

    async def _apply_rr_mode(self, mode: str):
        """Set RR mode: 'dynamic' = uncheck override, 'fixed_X' = check override + set value."""
        if mode == "dynamic":
            await self._toggle_checkbox(INPUT_INDEX["use_custom_rr"], False)
        else:
            rr_value = mode.replace("fixed_", "")
            await self._toggle_checkbox(INPUT_INDEX["use_custom_rr"], True)
            await asyncio.sleep(0.1)
            await self._set_input(INPUT_INDEX["risk_reward_ratio"], rr_value)

    async def _apply_single_param(self, param_name: str, value, param_type: str):
        """Apply a single parameter change. Handles numeric, checkbox, and special types."""
        if param_type == "rr_mode":
            await self._apply_rr_mode(value)
        elif param_type == "checkbox":
            idx = INPUT_INDEX.get(param_name)
            if idx is not None:
                await self._toggle_checkbox(idx, value)
        elif param_type == "liq_distance":
            # Set the appropriate liq distance param based on current symbol
            # Caller should resolve to correct param name
            pass  # Handled in optimize_pair_smart
        elif param_type == "numeric":
            idx = INPUT_INDEX.get(param_name)
            if idx is not None:
                await self._set_input(idx, value)

    async def _apply_and_test(self, param_name: str, value, param_type: str, symbol: str) -> BacktestResult:
        """Open dialog, change one param, click Ok, read results."""
        if not await self._open_settings():
            return BacktestResult(symbol=symbol, params={param_name: value})

        await asyncio.sleep(0.3)

        # Click Inputs tab
        await self.page.evaluate("""
            (() => { for (const b of document.querySelectorAll('button'))
                if (b.textContent?.trim() === 'Inputs') { b.click(); return; } })()
        """)
        await asyncio.sleep(0.2)

        # Apply the single param
        await self._apply_single_param(param_name, value, param_type)
        await asyncio.sleep(0.1)

        # Click Ok
        try:
            ok = await self.page.query_selector('button:has-text("Ok")')
            if ok:
                await ok.click()
            else:
                await self.page.keyboard.press("Enter")
        except Exception:
            await self.page.keyboard.press("Enter")

        # Wait for dialog close
        for _ in range(20):
            gone = await self.page.evaluate("""
                !document.querySelector('[class*="dialog-"][class*="rounded"]')?.offsetParent
            """)
            if gone:
                break
            await asyncio.sleep(0.3)

        # Wait for recalculation
        await asyncio.sleep(1.0)
        for _ in range(60):
            updating = await self.page.evaluate("""
                (() => {
                    for (const el of document.querySelectorAll('*')) {
                        const t = el.textContent?.trim();
                        if ((t === 'Updating report' || t === 'Calculating...')
                            && el.offsetParent && el.getBoundingClientRect().height > 0)
                            return true;
                    }
                    return false;
                })()
            """)
            if not updating:
                break
            await asyncio.sleep(0.5)
        await asyncio.sleep(1.0)

        # Read results
        result = await self._read_results(symbol, {param_name: value})
        return result

    async def optimize_pair_smart(self, symbol: str) -> Optional[BacktestResult]:
        """Hill-climbing optimization: test one param at a time, keep improvements."""
        tag = f"[{symbol}]"
        print(f"\n{'=' * 60}")
        print(f"{tag} SMART OPTIMIZATION: {symbol}")
        print(f"{'=' * 60}")

        # Switch to the correct symbol first
        await self._switch_symbol(symbol)

        # Step 1: Read baseline (current settings)
        print(f"{tag} Reading baseline results...")
        baseline = await self._read_results(symbol, {"baseline": True})
        print(f"{tag} Baseline: PF={baseline.profit_factor:.2f} WR={baseline.win_rate:.1f}% "
              f"T={baseline.total_trades} DD={baseline.max_drawdown:.0f} Score={baseline.score:.1f}")

        best_score = baseline.score
        best_result = baseline
        test_count = 0

        # Resolve liq_distance param name based on symbol
        sym_upper = symbol.upper()
        if "XAU" in sym_upper or "GOLD" in sym_upper:
            liq_param = "liq_max_distance_pips_gold"
            liq_values = [80, 120, 200]
        elif any(x in sym_upper for x in ["NAS", "US100", "US500", "US30", "SPX"]):
            liq_param = "liq_max_distance_pips_index"
            liq_values = [300, 500, 700]
        else:
            liq_param = "liq_max_distance_pips_forex"
            liq_values = [10, 20, 30]

        # Build resolved param list
        params_to_test = []
        for name, values, ptype in HILL_CLIMB_PARAMS:
            if name == "liq_distance":
                params_to_test.append((liq_param, liq_values, "numeric"))
            else:
                params_to_test.append((name, values, ptype))

        total_params = len(params_to_test)
        total_tests = sum(len(v) for _, v, _ in params_to_test)

        print(f"{tag} Testing {total_params} parameters, ~{total_tests} total tests")
        print(f"{tag} Estimated time: ~{total_tests * 30 // 60} minutes\n")

        improved_params = {}

        for p_idx, (param_name, values, ptype) in enumerate(params_to_test, 1):
            short_name = param_name.split("_")[-1] if len(param_name) > 15 else param_name
            print(f"\n  {tag} [{p_idx}/{total_params}] Testing: {param_name}")

            param_best_score = best_score
            param_best_value = None

            for value in values:
                test_count += 1
                val_str = str(value)
                print(f"    {tag} #{test_count} {short_name}={val_str}", end="", flush=True)

                result = await self._apply_and_test(param_name, value, ptype, symbol)
                self.results.append(result)

                pf = f"PF={result.profit_factor:.2f}" if result.profit_factor else "PF=N/A"
                wr = f"WR={result.win_rate:.1f}%" if result.win_rate else "WR=N/A"
                trades = f"T={result.total_trades}" if result.total_trades else "T=0"
                dd = f"DD={result.max_drawdown:.0f}"
                print(f" -> {pf} {wr} {trades} {dd} Score={result.score:.1f}", end="")

                if result.score > param_best_score:
                    param_best_score = result.score
                    param_best_value = value
                    print(f" +++")
                else:
                    print()

            # Keep the best value for this param, or revert
            if param_best_value is not None and param_best_score > best_score:
                print(f"  {tag} >> KEEPING {param_name}={param_best_value} (Score: {best_score:.1f} -> {param_best_score:.1f})")
                best_score = param_best_score
                improved_params[param_name] = param_best_value

                # Re-apply the best value (it may have been overwritten by last test)
                await self._apply_and_test(param_name, param_best_value, ptype, symbol)
                best_result = await self._read_results(symbol, improved_params)
                best_result.params = dict(improved_params)
            else:
                print(f"  {tag} >> No improvement from {param_name}, reverting")
                # Need to revert to previous best value
                # Re-open dialog and restore the original/previous value
                # For simplicity, re-apply all improved params so far
                if improved_params:
                    if not await self._open_settings():
                        continue
                    await asyncio.sleep(0.3)
                    await self.page.evaluate("""
                        (() => { for (const b of document.querySelectorAll('button'))
                            if (b.textContent?.trim() === 'Inputs') { b.click(); return; } })()
                    """)
                    await asyncio.sleep(0.2)
                    # Revert this param's changes by clicking Cancel
                    await self.page.evaluate("""
                        (() => { for (const b of document.querySelectorAll('button'))
                            if (b.textContent?.trim() === 'Cancel') { b.click(); return; } })()
                    """)
                    await asyncio.sleep(0.5)

        # Final summary
        print(f"\n{tag} {'=' * 50}")
        print(f"{tag} OPTIMIZATION COMPLETE")
        print(f"{tag} Tests run: {test_count}")
        print(f"{tag} Baseline score: {baseline.score:.1f}")
        print(f"{tag} Final score:    {best_score:.1f} ({'+' if best_score > baseline.score else ''}{best_score - baseline.score:.1f})")
        print(f"{tag} Improved params: {improved_params}")
        if best_result:
            print(f"{tag} Final: PF={best_result.profit_factor:.2f} WR={best_result.win_rate:.1f}% "
                  f"T={best_result.total_trades} DD%={best_result.max_drawdown_pct:.1f}%")

        best_result.params = improved_params
        return best_result


async def page_query_snd(page):
    """Find the S&D Algo [Pro] strategy text element in the legend."""
    elements = await page.query_selector_all('div')
    for el in elements:
        try:
            text = await el.inner_text()
            if text.strip() == 'S&D Algo [Pro]':
                box = await el.bounding_box()
                if box and box['width'] < 300 and box['y'] < 150:
                    return el
        except Exception:
            continue
    return None


class TradingViewOptimizer:
    """Automates TradingView strategy backtesting via Playwright."""

    def __init__(self, pairs: list[str], param_grid: dict = None, fast_mode: bool = False, smart_mode: bool = False):
        self.pairs = pairs
        self.fast_mode = fast_mode
        self.smart_mode = smart_mode
        self.results: list[BacktestResult] = []
        self.best_per_pair: dict[str, BacktestResult] = {}
        self.page: Optional[Page] = None
        self.browser: Optional[Browser] = None
        self.tv_pages: list[Page] = []

        # Select parameter grid based on mode
        if param_grid:
            self.default_param_grid = param_grid
        elif fast_mode:
            self.default_param_grid = PARAM_GRID_FAST
        else:
            self.default_param_grid = PARAM_GRID_FULL

    def get_param_grid(self, symbol: str) -> dict:
        """Return the appropriate parameter grid for the symbol."""
        sym = symbol.upper()
        if "XAU" in sym or "GOLD" in sym:
            return PARAM_GRID_GOLD if not self.fast_mode else {
                k: v[:3] for k, v in PARAM_GRID_GOLD.items()
            }
        elif any(idx in sym for idx in ["NAS", "US100", "US500", "US30", "SPX", "NDX"]):
            return PARAM_GRID_INDEX if not self.fast_mode else {
                k: v[:3] for k, v in PARAM_GRID_INDEX.items()
            }
        else:
            return self.default_param_grid

    def generate_combinations(self, param_grid: dict) -> list[dict]:
        """Generate all parameter combinations from the grid."""
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combos = []

        def _recurse(idx, current):
            if idx == len(keys):
                combos.append(dict(current))
                return
            for val in values[idx]:
                current[keys[idx]] = val
                _recurse(idx + 1, current)

        _recurse(0, {})
        return combos

    async def connect_to_brave(self):
        """Connect to an already-running Chrome browser via CDP."""
        print("\n" + "=" * 70)
        print("TRADINGVIEW STRATEGY OPTIMIZER")
        print("=" * 70)
        print(f"\nConnecting to Chrome browser on port 9222...")
        print("Make sure you started Chrome with:")
        print('  open -a "Google Chrome" --args --remote-debugging-port=9222\n')

        self._pw = await async_playwright().start()

        try:
            self.browser = await self._pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
            print("Connected to Chrome browser!")
        except Exception as e:
            print(f"\nERROR: Could not connect to Chrome browser: {e}")
            print("\nTo fix this:")
            print("1. Close all Chrome windows")
            print("2. Start Chrome with remote debugging:")
            print('   open -a "Google Chrome" --args --remote-debugging-port=9222')
            print("3. Open TradingView and load your chart with S&D Algo [Pro]")
            print("4. Run this script again")
            sys.exit(1)

        # Find ALL TradingView tabs
        self.tv_pages = []
        contexts = self.browser.contexts
        for context in contexts:
            for page in context.pages:
                if "tradingview.com/chart" in page.url:
                    self.tv_pages.append(page)
                    print(f"  Found TradingView tab: {page.url}")

        if not self.tv_pages:
            print("\nERROR: No TradingView chart tabs found.")
            print("Please open TradingView chart tabs in Chrome with S&D Algo [Pro]")
            sys.exit(1)

        # For backward compat, set self.page to first tab
        self.page = self.tv_pages[0]
        print(f"\nFound {len(self.tv_pages)} TradingView tab(s)")
        print("Ready to optimize!\n")

    async def switch_symbol(self, symbol: str):
        """Switch the chart to a different trading pair using URL-based navigation.

        This is the most reliable method: navigates to the same chart URL with
        ?symbol= parameter, which forces TradingView to change the symbol without
        needing to interact with the search UI.
        """
        print(f"\n--- Switching to {symbol} ---")

        # Normalize symbol: strip broker prefixes like "VANTAGE:" or "OANDA:"
        clean_symbol = symbol.split(":")[-1].upper().strip()

        # Check if we're already on the correct symbol by inspecting the page title
        # TradingView titles look like: "EURUSD 1.08573 ▲ +0.12% — S&D Algo [Pro] — TradingView"
        try:
            title = await self.page.title()
            # Extract the symbol from the title (first word before a space or digit)
            title_symbol = title.split(" ")[0].split(":")[-1].upper().strip() if title else ""
            if title_symbol == clean_symbol:
                print(f"  Already on {clean_symbol}, skipping switch")
                await self._wait_for_chart_load()
                return
        except Exception:
            pass

        # Also check the URL for a symbol= parameter
        current_url = self.page.url
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(current_url)
            url_symbol = parse_qs(parsed.query).get("symbol", [""])[0].split(":")[-1].upper()
            if url_symbol == clean_symbol:
                print(f"  Already on {clean_symbol} (from URL), skipping switch")
                await self._wait_for_chart_load()
                return
        except Exception:
            pass

        # Extract the chart ID from the current URL
        # URL format: https://www.tradingview.com/chart/EIuJ3KCm/?...
        chart_id = ""
        if "/chart/" in current_url:
            try:
                after_chart = current_url.split("/chart/")[1]
                chart_id = after_chart.split("/")[0].split("?")[0]
            except (IndexError, ValueError):
                pass

        if not chart_id:
            print(f"  ERROR: Could not extract chart ID from URL: {current_url}")
            print(f"  URL must contain /chart/<ID>/ pattern")
            raise RuntimeError(f"Cannot switch symbol: no chart ID in URL {current_url}")

        # Navigate to the chart URL with the symbol parameter
        target_url = f"https://www.tradingview.com/chart/{chart_id}/?symbol=VANTAGE%3A{clean_symbol}"
        print(f"  Navigating to: VANTAGE:{clean_symbol}")

        try:
            await self.page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"  Navigation warning (may be OK): {e}")

        # Wait for initial page load
        await asyncio.sleep(3.0)

        # Wait for chart + strategy tester to finish calculating
        await self._wait_for_chart_load(timeout=30)

        # Verify the symbol actually changed by checking the page title
        try:
            new_title = await self.page.title()
            new_title_symbol = new_title.split(" ")[0].split(":")[-1].upper().strip() if new_title else ""
            if clean_symbol in new_title_symbol or new_title_symbol in clean_symbol:
                print(f"  Switched to {clean_symbol} (verified via title: '{new_title_symbol}')")
            else:
                print(f"  Warning: Expected {clean_symbol} but title shows '{new_title_symbol}'")
                print(f"  Full title: {new_title}")
        except Exception:
            print(f"  Switched to {clean_symbol} (could not verify title)")

    async def _wait_for_chart_load(self, timeout: int = 30):
        """Wait for the chart and strategy tester to finish loading.

        Polls for loading indicators: 'Updating report', 'Calculating...',
        'Loading...', 'Compiling...' — and waits until none are visible.
        """
        start = time.time()

        # First, wait a moment for loading indicators to appear
        await asyncio.sleep(1.0)

        while time.time() - start < timeout:
            try:
                still_loading = await self.page.evaluate("""
                    (() => {
                        const indicators = [
                            'Updating report', 'Calculating...', 'Loading...', 'Compiling...'
                        ];
                        for (const el of document.querySelectorAll('*')) {
                            const t = el.textContent?.trim();
                            if (indicators.includes(t)
                                && el.offsetParent !== null
                                && el.getBoundingClientRect().height > 0
                                && el.children.length <= 2) {
                                return t;
                            }
                        }
                        return null;
                    })()
                """)
                if not still_loading:
                    await asyncio.sleep(0.5)  # Small buffer after indicators clear
                    return
                if time.time() - start > 5:
                    # Only log after the first few seconds to reduce noise
                    print(f"  Waiting for chart... ({still_loading})")
            except Exception:
                pass
            await asyncio.sleep(0.5)
        print(f"  Warning: Chart may still be loading after {timeout}s timeout")

    async def open_strategy_settings(self):
        """Open the strategy settings dialog by double-clicking strategy name."""
        # Check if dialog is already open
        is_open = await self.page.evaluate("""
            (() => {
                const d = document.querySelector('[class*="dialog-"][class*="rounded"]');
                return d && d.offsetParent !== null;
            })()
        """)
        if is_open:
            return True

        # Double-click the strategy name in the legend
        try:
            elements = await page_query_snd(self.page)
            if elements:
                await elements.dblclick()
                await asyncio.sleep(1.5)
                return True
        except Exception:
            pass

        # Fallback: find by text content
        try:
            opened = await self.page.evaluate("""
                (() => {
                    const divs = document.querySelectorAll('div');
                    for (const d of divs) {
                        if (d.textContent?.trim() === 'S&D Algo [Pro]'
                            && d.children.length <= 2
                            && d.getBoundingClientRect().width < 300) {
                            d.dispatchEvent(new MouseEvent('dblclick', {bubbles: true}));
                            return true;
                        }
                    }
                    return false;
                })()
            """)
            if opened:
                await asyncio.sleep(1.5)
                return True
        except Exception:
            pass

        print("  ERROR: Could not open strategy settings dialog")
        return False

    async def _set_input_by_index(self, index: int, value):
        """Set an input value by its index using Playwright's fill() for React compatibility."""
        input_handle = await self.page.evaluate_handle(f"""
            (() => {{
                const dialog = document.querySelector('[class*="dialog-"][class*="rounded"]');
                if (!dialog) return null;
                const inputs = dialog.querySelectorAll('input');
                if ({index} >= inputs.length) return null;
                return inputs[{index}];
            }})()
        """)

        el = input_handle.as_element()
        if not el:
            return False

        try:
            input_type = await el.get_attribute("type")
            if input_type == "checkbox":
                return True

            await el.scroll_into_view_if_needed()
            await asyncio.sleep(0.05)

            # Playwright's fill() properly handles React synthetic events
            await el.fill(str(value))
            await asyncio.sleep(0.05)

            return True
        except Exception as e:
            print(f"  Input set error [{index}]: {e}")
            return False

    async def _ensure_custom_profile(self):
        """Ensure Configuration Profile is set to 'Custom'."""
        result = await self.page.evaluate("""
            (() => {
                const dialog = document.querySelector('[class*="dialog-"][class*="rounded"]');
                if (!dialog) return 'NO_DIALOG';

                // Find the profile dropdown button (role=combobox)
                const combo = dialog.querySelector('button[role="combobox"]');
                if (!combo) return 'NO_COMBOBOX';

                const currentText = combo.textContent?.trim() || '';
                if (currentText === 'Custom') return 'ALREADY_CUSTOM';

                // Need to click dropdown and select Custom
                combo.click();
                return 'OPENED_DROPDOWN:' + currentText;
            })()
        """)

        if result == 'ALREADY_CUSTOM':
            return True

        if 'OPENED_DROPDOWN' in result:
            await asyncio.sleep(0.5)
            # Find and click "Custom" in the dropdown popup
            selected = await self.page.evaluate("""
                (() => {
                    // TradingView dropdown uses a popup with items
                    const allEls = document.querySelectorAll('[class*="item-"], [role="option"], [role="listbox"] *');
                    for (const el of allEls) {
                        if (el.textContent?.trim() === 'Custom' && el.offsetParent !== null) {
                            el.click();
                            return 'SELECTED';
                        }
                    }
                    // Fallback: find any visible "Custom" text element
                    const divs = document.querySelectorAll('div, span');
                    for (const el of divs) {
                        if (el.textContent?.trim() === 'Custom'
                            && el.offsetParent !== null
                            && el.getBoundingClientRect().height > 10
                            && el.getBoundingClientRect().height < 45
                            && el.children.length <= 1) {
                            el.click();
                            return 'SELECTED_FALLBACK';
                        }
                    }
                    return 'NOT_FOUND';
                })()
            """)
            await asyncio.sleep(0.5)
            return 'SELECTED' in selected

        return False

    async def apply_params(self, params: dict):
        """Apply a set of parameters to the strategy settings."""
        # Always open settings fresh (dialog closes after each Ok click)
        if not await self.open_strategy_settings():
            return False

        await asyncio.sleep(1.0)

        # Click Inputs tab
        await self.page.evaluate("""
            (() => {
                const buttons = document.querySelectorAll('button');
                for (const b of buttons) {
                    if (b.textContent?.trim() === 'Inputs') { b.click(); return true; }
                }
                return false;
            })()
        """)
        await asyncio.sleep(0.5)

        # Ensure profile is Custom (only change if needed — avoid closing dialog)
        profile_status = await self.page.evaluate("""
            (() => {
                const dialog = document.querySelector('[class*="dialog-"][class*="rounded"]');
                if (!dialog) return 'NO_DIALOG';
                const combo = dialog.querySelector('button[role="combobox"]');
                if (!combo) return 'NO_COMBOBOX';
                return combo.textContent?.trim() || 'UNKNOWN';
            })()
        """)

        if profile_status != 'Custom' and profile_status not in ('NO_DIALOG', 'NO_COMBOBOX', 'UNKNOWN'):
            print(f"  Profile is '{profile_status}', switching to Custom...")
            await self._ensure_custom_profile()
            await asyncio.sleep(0.5)
            # Re-open dialog if dropdown closed it
            is_open = await self.page.evaluate("""
                document.querySelector('[class*="dialog-"][class*="rounded"]')?.offsetParent !== null
            """)
            if not is_open:
                if not await self.open_strategy_settings():
                    return False
                await asyncio.sleep(1.0)

        # Set each parameter by its input index
        all_set = True
        for param_name, value in params.items():
            idx = INPUT_INDEX.get(param_name)
            if idx is None:
                print(f"  Warning: No index mapping for {param_name}")
                continue
            success = await self._set_input_by_index(idx, value)
            if not success:
                print(f"  Warning: Failed to set [{idx}] {param_name} = {value}")
                all_set = False

        # Click Ok button
        try:
            ok_btn = await self.page.query_selector('button:has-text("Ok")')
            if ok_btn:
                await ok_btn.click()
            else:
                await self.page.keyboard.press("Enter")
        except Exception:
            await self.page.keyboard.press("Enter")

        # Wait for dialog to close
        for _ in range(20):
            dialog_gone = await self.page.evaluate("""
                (() => {
                    const d = document.querySelector('[class*="dialog-"][class*="rounded"]');
                    return !d || d.offsetParent === null;
                })()
            """)
            if dialog_gone:
                break
            await asyncio.sleep(0.3)

        # Wait for "Updating report" / "Calculating" to finish
        await asyncio.sleep(1.0)
        for _ in range(60):  # Up to 30 seconds
            still_updating = await self.page.evaluate("""
                (() => {
                    const all = document.querySelectorAll('*');
                    for (const el of all) {
                        const t = el.textContent?.trim();
                        if (t === 'Updating report' || t === 'Calculating...'
                            || t === 'Loading...' || t === 'Compiling...') {
                            if (el.offsetParent !== null && el.getBoundingClientRect().height > 0) {
                                return true;
                            }
                        }
                    }
                    return false;
                })()
            """)
            if not still_updating:
                break
            await asyncio.sleep(0.5)

        # Extra buffer for metrics to stabilize
        await asyncio.sleep(1.0)
        return all_set

    async def read_backtest_results(self, symbol: str, params: dict) -> BacktestResult:
        """Read the strategy tester results from the TradingView UI."""
        result = BacktestResult(
            symbol=symbol,
            params=params.copy(),
            timestamp=datetime.now().isoformat()
        )

        try:
            # Read metrics using the proven containerCell + title selectors
            metrics = await self.page.evaluate("""
                (() => {
                    const results = {};
                    const cells = document.querySelectorAll('[class*="containerCell-"]');
                    for (const cell of cells) {
                        const titleEl = cell.querySelector('[class*="title-"]');
                        const valueEls = cell.querySelectorAll('[class*="value-"], [class*="additional-"]');
                        if (titleEl) {
                            const title = titleEl.textContent?.trim();
                            const values = [];
                            for (const v of valueEls) {
                                const t = v.textContent?.trim();
                                if (t) values.push(t);
                            }
                            if (title && values.length > 0) {
                                results[title] = values.join(' | ');
                            }
                        }
                    }
                    return results;
                })()
            """)

            if metrics:
                for key, value in metrics.items():
                    kl = key.lower()
                    cleaned = value.split('|')[0].strip()
                    cleaned = cleaned.replace("$", "").replace(",", "").replace("%", "")
                    cleaned = cleaned.replace("USD", "").replace("usd", "").replace(" ", "")
                    cleaned = cleaned.replace("\u2212", "-").replace("−", "-").replace("+", "")

                    try:
                        num = float(cleaned)
                    except (ValueError, TypeError):
                        continue

                    if "total p&l" in kl or "net profit" in kl:
                        result.net_profit = num
                    elif "total trades" in kl:
                        result.total_trades = int(num)
                    elif "profitable" in kl:
                        result.win_rate = num
                    elif "profit factor" in kl:
                        result.profit_factor = num
                    elif "drawdown" in kl:
                        result.max_drawdown = num

            # Calculate DD%
            if result.max_drawdown > 0 and result.max_drawdown_pct == 0:
                result.max_drawdown_pct = (result.max_drawdown / 50000) * 100

        except Exception as e:
            print(f"  Error reading results: {e}")

        result.calculate_score()
        return result

    async def optimize_pair(self, symbol: str) -> Optional[BacktestResult]:
        """Run the full optimization for a single trading pair."""
        print(f"\n{'=' * 60}")
        print(f"OPTIMIZING: {symbol}")
        print(f"{'=' * 60}")

        # Switch to the pair
        await self.switch_symbol(symbol)
        await asyncio.sleep(2.0)

        # Get the appropriate parameter grid
        param_grid = self.get_param_grid(symbol)
        combos = self.generate_combinations(param_grid)
        total_combos = len(combos)

        print(f"Testing {total_combos} parameter combinations...")
        print(f"Parameters: {list(param_grid.keys())}")
        print(f"Estimated time: ~{total_combos * 8 // 60} minutes\n")

        best_result = None
        pair_results = []

        for idx, params in enumerate(combos, 1):
            param_str = " | ".join(f"{k}={v}" for k, v in params.items())
            print(f"  [{idx}/{total_combos}] {param_str}", end="", flush=True)

            # Apply parameters
            success = await self.apply_params(params)
            if not success:
                print(" -> SKIP (settings error)")
                continue

            # Wait for recalculation
            await asyncio.sleep(3.0)
            await self._wait_for_chart_load(timeout=15)

            # Read results
            result = await self.read_backtest_results(symbol, params)
            pair_results.append(result)
            self.results.append(result)

            # Print result summary
            pf = f"PF={result.profit_factor:.2f}" if result.profit_factor else "PF=N/A"
            wr = f"WR={result.win_rate:.1f}%" if result.win_rate else "WR=N/A"
            trades = f"T={result.total_trades}" if result.total_trades else "T=0"
            score = f"Score={result.score:.1f}"
            print(f" -> {pf} {wr} {trades} {score}")

            # Track best
            if best_result is None or result.score > best_result.score:
                best_result = result
                print(f"  >>> NEW BEST! Score={result.score:.1f} PF={result.profit_factor:.2f}")

        # Save pair results
        if best_result:
            self.best_per_pair[symbol] = best_result
            print(f"\n  BEST for {symbol}:")
            print(f"    Score: {best_result.score:.1f}")
            print(f"    Net Profit: ${best_result.net_profit:,.2f}")
            print(f"    Profit Factor: {best_result.profit_factor:.2f}")
            print(f"    Win Rate: {best_result.win_rate:.1f}%")
            print(f"    Total Trades: {best_result.total_trades}")
            print(f"    Max Drawdown: {best_result.max_drawdown_pct:.1f}%")
            print(f"    Settings: {best_result.params}")

        return best_result

    async def _run_pair_on_page(self, page: Page, symbol: str):
        """Run optimization for a single pair on a dedicated tab. Thread-safe."""
        try:
            worker = TabWorker(page, self)
            if self.smart_mode:
                result = await worker.optimize_pair_smart(symbol)
            else:
                result = await worker.optimize_pair(symbol)
            if result:
                self.best_per_pair[symbol] = result
                self.results.extend(worker.results)
        except Exception as e:
            print(f"\n  ERROR optimizing {symbol}: {e}")
            import traceback
            traceback.print_exc()

    async def run(self):
        """Run the full optimization pipeline — parallel if multiple tabs available."""
        await self.connect_to_brave()

        start_time = time.time()
        # NOTE: Parallel mode disabled — TradingView syncs settings across tabs
        # with the same chart layout ID, causing cross-contamination.
        # To use parallel mode, each tab needs a DIFFERENT chart layout
        # (create new layouts via TradingView UI: right-click tab → "New layout").
        #
        # For now, always run sequential on the first tab.

        # Use first tab for all pairs (sequential)
        page = self.tv_pages[0]
        print(f"\nRunning {len(self.pairs)} pairs sequentially on one tab...\n")

        for symbol in self.pairs:
            try:
                worker = TabWorker(page, self)
                if self.smart_mode:
                    result = await worker.optimize_pair_smart(symbol)
                else:
                    result = await worker.optimize_pair(symbol)
                if result:
                    self.best_per_pair[symbol] = result
                    self.results.extend(worker.results)
            except Exception as e:
                print(f"\n  ERROR optimizing {symbol}: {e}")
                import traceback
                traceback.print_exc()
                continue

        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        # Save all results
        self.save_results()
        self.generate_pine_presets()

        print(f"\n{'=' * 60}")
        print(f"OPTIMIZATION COMPLETE")
        print(f"{'=' * 60}")
        print(f"Time elapsed: {minutes}m {seconds}s")
        print(f"Pairs optimized: {len(self.best_per_pair)}/{len(self.pairs)}")
        print(f"Total combinations tested: {len(self.results)}")
        print(f"\nResults saved to: {RESULTS_DIR}/")

        if self.best_per_pair:
            print(f"\nBEST SETTINGS SUMMARY:")
            print(f"{'Symbol':<10} {'PF':>6} {'WR':>7} {'Trades':>7} {'Score':>7}")
            print("-" * 40)
            for sym, res in sorted(self.best_per_pair.items()):
                print(f"{sym:<10} {res.profit_factor:>6.2f} {res.win_rate:>6.1f}% {res.total_trades:>7} {res.score:>7.1f}")

    def save_results(self):
        """Save all results to CSV."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save all results
        all_results_file = RESULTS_DIR / f"all_results_{timestamp}.csv"
        if self.results:
            fieldnames = ["symbol", "net_profit", "total_trades", "win_rate",
                         "profit_factor", "max_drawdown", "max_drawdown_pct",
                         "profitable_trades", "score", "timestamp"]
            param_keys = set()
            for r in self.results:
                param_keys.update(r.params.keys())
            fieldnames.extend(sorted(param_keys))

            with open(all_results_file, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in self.results:
                    row = {
                        "symbol": r.symbol,
                        "net_profit": r.net_profit,
                        "total_trades": r.total_trades,
                        "win_rate": r.win_rate,
                        "profit_factor": r.profit_factor,
                        "max_drawdown": r.max_drawdown,
                        "max_drawdown_pct": r.max_drawdown_pct,
                        "profitable_trades": r.profitable_trades,
                        "score": r.score,
                        "timestamp": r.timestamp,
                    }
                    row.update(r.params)
                    writer.writerow(row)
            print(f"\nAll results: {all_results_file}")

        # Save best results
        best_file = RESULTS_DIR / f"best_settings_{timestamp}.json"
        best_data = {}
        for sym, res in self.best_per_pair.items():
            best_data[sym] = {
                "params": res.params,
                "metrics": {
                    "net_profit": res.net_profit,
                    "total_trades": res.total_trades,
                    "win_rate": res.win_rate,
                    "profit_factor": res.profit_factor,
                    "max_drawdown_pct": res.max_drawdown_pct,
                    "score": res.score,
                }
            }
        with open(best_file, "w") as f:
            json.dump(best_data, f, indent=2)
        print(f"Best settings: {best_file}")

    def generate_pine_presets(self):
        """Generate Pine Script code for the best presets per asset class."""
        if not self.best_per_pair:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        preset_file = RESULTS_DIR / f"pine_presets_{timestamp}.pine"

        # Group by asset class
        groups = {
            "Major USD": [], "Cross/Minor": [], "JPY Pairs": [],
            "Gold": [], "Indices": [], "Other": []
        }
        for sym, res in self.best_per_pair.items():
            sym_upper = sym.upper()
            if "XAU" in sym_upper or "GOLD" in sym_upper:
                groups["Gold"].append((sym, res))
            elif any(idx in sym_upper for idx in ["NAS", "US100", "US500", "US30", "SPX"]):
                groups["Indices"].append((sym, res))
            elif "JPY" in sym_upper:
                groups["JPY Pairs"].append((sym, res))
            elif sym_upper in ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"]:
                groups["Major USD"].append((sym, res))
            elif any(x in sym_upper for x in ["EUR", "GBP", "AUD", "NZD", "CAD", "CHF"]):
                groups["Cross/Minor"].append((sym, res))
            else:
                groups["Other"].append((sym, res))

        # Average the best params within each group
        lines = []
        lines.append(f"// === AUTO-GENERATED PRESETS ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===")
        lines.append(f"// Generated by scripts/optimize_pairs.py")
        lines.append(f"// Timeframe: 5-minute | Scoring: PF * sqrt(trades) * (1 - DD%/100)")
        lines.append(f"//")
        lines.append(f"// Paste this block inside the 'if use_profile_defaults' section,")
        lines.append(f"// after adding 'Per-Asset-Class (Optimized)' to config_profile options.")
        lines.append(f"")
        lines.append(f'    if config_profile == "Per-Asset-Class (Optimized)"')

        for group_name, pairs in groups.items():
            if not pairs:
                continue

            # Average the params across pairs in this group
            avg_params = {}
            for _, res in pairs:
                for k, v in res.params.items():
                    if k not in avg_params:
                        avg_params[k] = []
                    avg_params[k].append(v)

            for k in list(avg_params.keys()):
                vals = avg_params[k]
                # Skip non-numeric values (like "fixed_2.5", "dynamic", True/False)
                if isinstance(vals[0], str):
                    # Use most common value
                    from collections import Counter
                    avg_params[k] = Counter(vals).most_common(1)[0][0]
                elif isinstance(vals[0], bool):
                    avg_params[k] = sum(vals) > len(vals) / 2  # majority vote
                elif isinstance(vals[0], int):
                    avg_params[k] = int(round(sum(vals) / len(vals)))
                else:
                    avg_params[k] = round(sum(vals) / len(vals), 1)

            # Build metrics comment
            avg_pf = sum(r.profit_factor for _, r in pairs) / len(pairs)
            avg_wr = sum(r.win_rate for _, r in pairs) / len(pairs)
            avg_trades = sum(r.total_trades for _, r in pairs) / len(pairs)
            pair_names = ", ".join(s for s, _ in pairs)

            lines.append(f"")
            lines.append(f"        // {group_name}: {pair_names}")
            lines.append(f"        // Avg PF={avg_pf:.2f} WR={avg_wr:.1f}% Trades={avg_trades:.0f}")

            # Build condition
            if group_name == "Gold":
                lines.append(f"        if is_gold or is_xpt")
            elif group_name == "Indices":
                lines.append(f"        else if is_index")
            elif group_name == "JPY Pairs":
                lines.append(f"        else if is_jpy_pair")
            elif group_name == "Major USD":
                lines.append(f"        else if is_usd_quote or is_usd_base")
            else:
                lines.append(f"        else  // {group_name}")

            # Write param assignments
            for param, val in avg_params.items():
                lines.append(f"            {param} := {val}")

        lines.append(f"")
        lines.append(f"        // Common settings for all Per-Asset-Class presets")
        lines.append(f"        require_major_liquidity := true")
        lines.append(f"        structure_mode := \"Relaxed (Wicks)\"")
        lines.append(f"        stop_loss_buffer_pips := 1.0")

        preset_code = "\n".join(lines)

        with open(preset_file, "w") as f:
            f.write(preset_code)
        print(f"Pine presets: {preset_file}")

        # Also print to console
        print(f"\n{'=' * 60}")
        print("GENERATED PINE PRESET CODE")
        print(f"{'=' * 60}")
        print(preset_code)


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="TradingView Strategy Optimizer")
    parser.add_argument("--pairs", type=str, help="Comma-separated list of pairs to optimize")
    parser.add_argument("--fast", action="store_true", help="Fast mode: fewer parameter combinations (grid search)")
    parser.add_argument("--smart", action="store_true", help="Smart mode: hill-climbing, one param at a time (~48 tests/pair)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be tested without running")
    args = parser.parse_args()

    pairs = args.pairs.split(",") if args.pairs else DEFAULT_PAIRS

    optimizer = TradingViewOptimizer(pairs=pairs, fast_mode=args.fast, smart_mode=args.smart)

    if args.dry_run:
        print("DRY RUN - Parameter combinations that would be tested:\n")
        for symbol in pairs:
            grid = optimizer.get_param_grid(symbol)
            combos = optimizer.generate_combinations(grid)
            print(f"  {symbol}: {len(combos)} combinations")
            print(f"    Params: {list(grid.keys())}")
            for k, v in grid.items():
                print(f"      {k}: {v}")
        total = sum(len(optimizer.generate_combinations(optimizer.get_param_grid(s))) for s in pairs)
        est_minutes = total * 8 // 60
        print(f"\n  TOTAL: {total} combinations across {len(pairs)} pairs")
        print(f"  Estimated time: ~{est_minutes} minutes ({est_minutes // 60}h {est_minutes % 60}m)")
        return

    await optimizer.run()


if __name__ == "__main__":
    asyncio.run(main())