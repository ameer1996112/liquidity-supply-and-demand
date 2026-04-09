"""
tab_worker.py — TabWorker: handles optimization on a single TradingView tab.

Reliability guarantees:
  - _wait_for_update_complete(): detects the full appear→disappear cycle of
    "Updating report" so we never read stale results.
  - _get_results_hash(): fingerprints the current result set so we can detect
    when TradingView has (or hasn't) recalculated.
  - _apply_params() retries up to _MAX_RETRIES times, validates the hash
    changed before returning.
  - sample_params(): translates an Optuna trial into concrete TradingView
    parameter values (resolves liq_distance per asset class).
"""

import asyncio
import hashlib
import time
import logging
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from .config import INPUT_INDEX, CHECKBOX_INDICES, HILL_CLIMB_PARAMS, LIQ_DISTANCE_RANGES
from .models import BacktestResult

if TYPE_CHECKING:
    from playwright.async_api import Page
    from .optimizer import TradingViewOptimizer

log = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_SLEEP = 2.0          # seconds between retry attempts
_UPDATE_APPEAR_TIMEOUT = 4  # seconds to wait for "Updating report" to appear
_UPDATE_FINISH_TIMEOUT = 90 # seconds max for chart to finish recalculating

_LOADING_INDICATORS = [
    "Updating report", "Calculating...", "Loading...", "Compiling..."
]


# ─────────────────────────────────── JS snippets ─────────────────────────────

_JS_FIND_LOADING = """
(() => {
    const indicators = arguments[0];
    for (const el of document.querySelectorAll('*')) {
        const t = el.textContent?.trim();
        if (
            indicators.includes(t)
            && el.offsetParent !== null
            && el.getBoundingClientRect().height > 0
            && el.children.length <= 2
        ) return t;
    }
    return null;
})()
"""

_JS_RESULTS_FINGERPRINT = """
(() => {
    const cells = document.querySelectorAll('[class*="containerCell-"]');
    const parts = [];
    for (const cell of cells) {
        const t = cell.querySelector('[class*="title-"]');
        const vals = cell.querySelectorAll('[class*="value-"], [class*="additional-"]');
        if (t) {
            const vs = [];
            for (const v of vals) { const x = v.textContent?.trim(); if (x) vs.push(x); }
            if (vs.length) parts.push(t.textContent.trim() + '=' + vs.join('|'));
        }
    }
    return parts.join(';');
})()
"""

_JS_COLLECT_METRICS = """
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
"""


async def page_query_snd(page: "Page"):
    """Find the S&D Algo [Pro] strategy text element in the legend."""
    elements = await page.query_selector_all("div")
    for el in elements:
        try:
            text = await el.inner_text()
            if text.strip() == "S&D Algo [Pro]":
                box = await el.bounding_box()
                if box and box["width"] < 300 and box["y"] < 150:
                    return el
        except Exception:
            continue
    return None


class TabWorker:
    """Handles optimization on a single TradingView tab. Safe for sequential use."""

    def __init__(self, page: "Page", optimizer: "TradingViewOptimizer"):
        self.page = page
        self.optimizer = optimizer
        self.results: list[BacktestResult] = []

    # ─────────────────────────────────── asset class helpers ─────────────────

    @staticmethod
    def _asset_class(symbol: str) -> str:
        """Return 'gold', 'index', or 'forex' for a given symbol."""
        sym = symbol.upper()
        if "XAU" in sym or "GOLD" in sym or "XAG" in sym:
            return "gold"
        if any(x in sym for x in ["NAS", "US100", "US500", "US30", "SPX", "NDX"]):
            return "index"
        return "forex"

    def _liq_range(self, symbol: str) -> dict:
        """Return the liquidity distance range dict for this symbol's asset class."""
        return LIQ_DISTANCE_RANGES[self._asset_class(symbol)]

    # ─────────────────────────────────── Optuna param sampler ────────────────

    def sample_params(self, trial, symbol: str) -> dict:
        """
        Translate an Optuna trial into a concrete parameter dict for TradingView.
        Handles liq_distance resolution per asset class and rr_mode expansion.
        """
        from .config import OPTUNA_SEARCH_SPACE

        params: dict = {}
        liq_range = self._liq_range(symbol)
        liq_param_name = liq_range["param"]

        for name, space in OPTUNA_SEARCH_SPACE.items():
            if name == "liq_distance":
                val = trial.suggest_float(
                    "liq_distance", liq_range["low"], liq_range["high"]
                )
                # Round to 1 decimal place to reduce noise
                params[liq_param_name] = round(val, 1)
            elif space["type"] == "categorical":
                val = trial.suggest_categorical(name, space["choices"])
                params[name] = val
            elif space["type"] == "int":
                val = trial.suggest_int(name, space["low"], space["high"])
                params[name] = val
            elif space["type"] == "float":
                val = trial.suggest_float(name, space["low"], space["high"])
                params[name] = round(val, 1)

        return params

    # ─────────────────────────────────── navigation ──────────────────────────

    async def _switch_symbol(self, symbol: str) -> None:
        """Switch chart to a different symbol using URL-based navigation."""
        clean_symbol = symbol.split(":")[-1].upper().strip()

        # Already on this symbol?
        try:
            title = await self.page.title()
            title_symbol = (
                title.split(" ")[0].split(":")[-1].upper().strip() if title else ""
            )
            if title_symbol == clean_symbol:
                print(f"  Already on {clean_symbol}, skipping switch")
                await self._wait_for_load()
                return
        except Exception:
            pass

        current_url = self.page.url
        chart_id = ""
        if "/chart/" in current_url:
            try:
                chart_id = (
                    current_url.split("/chart/")[1].split("/")[0].split("?")[0]
                )
            except (IndexError, ValueError):
                pass

        if not chart_id:
            raise RuntimeError(
                f"Cannot switch symbol: no chart ID in URL {current_url}"
            )

        target_url = (
            f"https://www.tradingview.com/chart/{chart_id}/"
            f"?symbol=VANTAGE%3A{clean_symbol}"
        )
        print(f"  Navigating to VANTAGE:{clean_symbol}...")

        try:
            await self.page.goto(
                target_url, wait_until="domcontentloaded", timeout=30000
            )
        except Exception as e:
            print(f"  Navigation warning: {e}")

        await asyncio.sleep(3.0)
        await self._wait_for_load()

        # Verify
        try:
            new_title = await self.page.title()
            new_sym = (
                new_title.split(" ")[0].split(":")[-1].upper().strip()
                if new_title
                else ""
            )
            if clean_symbol in new_sym or new_sym in clean_symbol:
                print(f"  Switched to {clean_symbol} (verified)")
            else:
                print(
                    f"  Warning: Expected {clean_symbol}, title shows '{new_sym}'"
                )
        except Exception:
            pass

    async def _wait_for_load(self, timeout: int = 30) -> None:
        """Wait for chart and strategy tester to finish loading."""
        await asyncio.sleep(1.0)
        start = time.time()
        while time.time() - start < timeout:
            try:
                loading = await self.page.evaluate(
                    """
                    (() => {
                        const indicators = [
                            'Updating report', 'Calculating...',
                            'Loading...', 'Compiling...'
                        ];
                        for (const el of document.querySelectorAll('*')) {
                            const t = el.textContent?.trim();
                            if (indicators.includes(t)
                                && el.offsetParent !== null
                                && el.getBoundingClientRect().height > 0
                                && el.children.length <= 2)
                                return t;
                        }
                        return null;
                    })()
                    """
                )
                if not loading:
                    await asyncio.sleep(0.5)
                    return
            except Exception:
                pass
            await asyncio.sleep(0.5)

    # ─────────────────────────────────── update cycle detection ──────────────

    async def _check_loading_text(self) -> Optional[str]:
        """Return the loading indicator text if visible, else None."""
        try:
            return await self.page.evaluate(
                f"""
                (() => {{
                    const indicators = {_LOADING_INDICATORS!r};
                    for (const el of document.querySelectorAll('*')) {{
                        const t = el.textContent?.trim();
                        if (
                            indicators.includes(t)
                            && el.offsetParent !== null
                            && el.getBoundingClientRect().height > 0
                            && el.children.length <= 2
                        ) return t;
                    }}
                    return null;
                }})()
                """
            )
        except Exception:
            return None

    async def _wait_for_update_complete(self) -> bool:
        """
        Wait for TradingView to finish recalculating after a parameter change.

        Detects the full cycle:
          idle → [update starts] → updating → [update ends] → idle

        Phase 1: Wait up to _UPDATE_APPEAR_TIMEOUT seconds for the loading
                 indicator to APPEAR (confirming TV acknowledged the change).
        Phase 2: Wait up to _UPDATE_FINISH_TIMEOUT seconds for it to DISAPPEAR.

        If Phase 1 times out (TV never started updating — e.g. instant recalc
        or param rejected), we add a 1.5 s safety buffer and return True.

        Returns True on clean completion, False if Phase 2 timed out.
        """
        # Phase 1 — wait for loading to appear
        appeared = False
        deadline = time.time() + _UPDATE_APPEAR_TIMEOUT
        while time.time() < deadline:
            if await self._check_loading_text():
                appeared = True
                break
            await asyncio.sleep(0.1)

        if not appeared:
            # TV didn't start a loading indicator; assume instant or missed.
            await asyncio.sleep(1.5)
            return True

        # Phase 2 — wait for loading to disappear
        deadline = time.time() + _UPDATE_FINISH_TIMEOUT
        while time.time() < deadline:
            if not await self._check_loading_text():
                await asyncio.sleep(0.5)   # small buffer after disappears
                return True
            await asyncio.sleep(0.3)

        log.warning("_wait_for_update_complete: timed out after %ds", _UPDATE_FINISH_TIMEOUT)
        return False

    # ─────────────────────────────────── results fingerprint ─────────────────

    async def _get_results_hash(self) -> str:
        """
        Return a short hash of the current strategy-tester result cells.
        Used to detect whether TradingView has recalculated after a param change.
        """
        try:
            fingerprint: str = await self.page.evaluate(_JS_RESULTS_FINGERPRINT)
            return hashlib.md5(fingerprint.encode()).hexdigest()[:8]
        except Exception:
            return ""

    # ─────────────────────────────────── dialog helpers ──────────────────────

    async def _open_settings(self) -> bool:
        """Open strategy settings dialog on this tab's page."""
        is_open = await self.page.evaluate(
            """
            (() => {
                const d = document.querySelector('[class*="dialog-"][class*="rounded"]');
                return d && d.offsetParent !== null;
            })()
            """
        )
        if is_open:
            return True

        el = await page_query_snd(self.page)
        if el:
            await el.dblclick()
            await asyncio.sleep(1.5)
            return True

        # Fallback
        await self.page.evaluate(
            """
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
            """
        )
        await asyncio.sleep(1.5)
        return True

    async def _set_input(self, index: int, value) -> bool:
        """Set input by index using Playwright fill()."""
        handle = await self.page.evaluate_handle(
            f"""
            (() => {{
                const d = document.querySelector('[class*="dialog-"][class*="rounded"]');
                if (!d) return null;
                const inputs = d.querySelectorAll('input');
                return ({index} < inputs.length) ? inputs[{index}] : null;
            }})()
            """
        )
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

    async def _toggle_checkbox(self, index: int, desired_state: bool) -> bool:
        """Toggle a checkbox to the desired state (True=checked, False=unchecked)."""
        handle = await self.page.evaluate_handle(
            f"""
            (() => {{
                const d = document.querySelector('[class*="dialog-"][class*="rounded"]');
                if (!d) return null;
                const inputs = d.querySelectorAll('input');
                return ({index} < inputs.length) ? inputs[{index}] : null;
            }})()
            """
        )
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

    async def _apply_rr_mode(self, mode: str) -> None:
        """Set RR mode: 'dynamic' = uncheck override, 'fixed_X' = check + value."""
        if mode == "dynamic":
            await self._toggle_checkbox(INPUT_INDEX["use_custom_rr"], False)
        else:
            rr_value = mode.replace("fixed_", "")
            await self._toggle_checkbox(INPUT_INDEX["use_custom_rr"], True)
            await asyncio.sleep(0.1)
            await self._set_input(INPUT_INDEX["risk_reward_ratio"], rr_value)

    async def _apply_single_param(
        self, param_name: str, value, param_type: str
    ) -> None:
        """Apply a single parameter change (numeric / checkbox / special types)."""
        if param_type == "rr_mode":
            await self._apply_rr_mode(value)
        elif param_type == "checkbox":
            idx = INPUT_INDEX.get(param_name)
            if idx is not None:
                await self._toggle_checkbox(idx, value)
        elif param_type == "liq_distance":
            pass  # Caller resolves to correct param name
        elif param_type == "numeric":
            idx = INPUT_INDEX.get(param_name)
            if idx is not None:
                await self._set_input(idx, value)

    async def _click_ok(self) -> None:
        """Click the OK button in the settings dialog."""
        try:
            ok = await self.page.query_selector('button:has-text("Ok")')
            if ok:
                await ok.click()
            else:
                await self.page.keyboard.press("Enter")
        except Exception:
            await self.page.keyboard.press("Enter")

    async def _wait_dialog_close(self) -> None:
        """Wait for the settings dialog to close."""
        for _ in range(20):
            gone = await self.page.evaluate(
                """
                !document.querySelector(
                    '[class*="dialog-"][class*="rounded"]'
                )?.offsetParent
                """
            )
            if gone:
                break
            await asyncio.sleep(0.3)

    # ─────────────────────────────────── apply params (with retry) ───────────

    async def _apply_params(self, params: dict) -> bool:
        """
        Open dialog, set all params, click Ok, wait for full recalc cycle.

        Retries up to _MAX_RETRIES times. On each attempt:
          1. Snapshot results hash before applying.
          2. Apply all params.
          3. Click OK, wait for dialog to close.
          4. Wait for the full update cycle (appear → disappear).
          5. Verify results hash changed (stale detection).
        """
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                # Snapshot hash BEFORE
                hash_before = await self._get_results_hash()

                if not await self._open_settings():
                    raise RuntimeError("Could not open settings dialog")
                await asyncio.sleep(0.5)

                # Click Inputs tab
                await self.page.evaluate(
                    """
                    (() => {
                        for (const b of document.querySelectorAll('button')) {
                            if (b.textContent?.trim() === 'Inputs') {
                                b.click(); return;
                            }
                        }
                    })()
                    """
                )
                await asyncio.sleep(0.3)

                # Check profile is Custom
                profile = await self.page.evaluate(
                    """
                    (() => {
                        const d = document.querySelector(
                            '[class*="dialog-"][class*="rounded"]'
                        );
                        if (!d) return '';
                        const combo = d.querySelector('button[role="combobox"]');
                        return combo?.textContent?.trim() || '';
                    })()
                    """
                )
                if profile != "Custom":
                    print(f" [WARN: profile={profile}, need Custom]", end="")

                # Apply rr_mode first (special handling)
                rr_mode = params.get("rr_mode")
                if rr_mode is not None:
                    await self._apply_rr_mode(rr_mode)
                    await asyncio.sleep(0.1)

                # Apply remaining params
                for name, value in params.items():
                    if name == "rr_mode":
                        continue  # already handled
                    if name in ("enable_ai_quality_filter", "use_break_even",
                                "enable_double_tp"):
                        idx = INPUT_INDEX.get(name)
                        if idx is not None:
                            await self._toggle_checkbox(idx, bool(value))
                    else:
                        idx = INPUT_INDEX.get(name)
                        if idx is not None:
                            await self._set_input(idx, value)

                await self._click_ok()
                await self._wait_dialog_close()

                # ── Full update cycle detection ────────────────────────────
                completed = await self._wait_for_update_complete()
                if not completed:
                    log.warning(
                        "_apply_params attempt %d: update timed out", attempt
                    )

                # ── Stale result detection ─────────────────────────────────
                hash_after = await self._get_results_hash()
                if hash_before and hash_after and hash_before == hash_after:
                    log.warning(
                        "_apply_params attempt %d: results hash unchanged "
                        "(possible stale read or param rejected)", attempt
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(_RETRY_SLEEP)
                        continue

                return True

            except Exception as e:
                log.warning(
                    "_apply_params attempt %d/%d failed: %s", attempt, _MAX_RETRIES, e
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_SLEEP)
                else:
                    log.warning("_apply_params: all retries exhausted, skipping combo")
                    return False
        return False

    async def _apply_and_test(
        self, param_name: str, value, param_type: str, symbol: str
    ) -> BacktestResult:
        """
        Open dialog, change one param, click Ok, wait for recalc, read results.
        Retries up to _MAX_RETRIES times on failure.
        """
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                hash_before = await self._get_results_hash()

                if not await self._open_settings():
                    raise RuntimeError("Could not open settings dialog")

                await asyncio.sleep(0.3)

                # Click Inputs tab
                await self.page.evaluate(
                    """
                    (() => {
                        for (const b of document.querySelectorAll('button'))
                            if (b.textContent?.trim() === 'Inputs') {
                                b.click(); return;
                            }
                    })()
                    """
                )
                await asyncio.sleep(0.2)

                await self._apply_single_param(param_name, value, param_type)
                await asyncio.sleep(0.1)

                await self._click_ok()
                await self._wait_dialog_close()

                # Full update cycle
                await self._wait_for_update_complete()

                # Stale check
                hash_after = await self._get_results_hash()
                if hash_before and hash_after and hash_before == hash_after:
                    log.warning(
                        "_apply_and_test: stale result after %s=%s (attempt %d)",
                        param_name, value, attempt
                    )

                return await self._read_results(symbol, {param_name: value})

            except Exception as e:
                log.warning(
                    "_apply_and_test attempt %d/%d failed for %s=%s: %s",
                    attempt, _MAX_RETRIES, param_name, value, e,
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_SLEEP)
                else:
                    log.warning(
                        "_apply_and_test: all retries exhausted for %s=%s",
                        param_name, value,
                    )
                    return BacktestResult(
                        symbol=symbol,
                        params={param_name: value},
                        timestamp=datetime.now().isoformat(),
                    )

    async def _read_results(self, symbol: str, params: dict) -> BacktestResult:
        """Read strategy tester metrics from this tab."""
        result = BacktestResult(
            symbol=symbol,
            params=params.copy(),
            timestamp=datetime.now().isoformat(),
        )
        try:
            metrics = await self.page.evaluate(_JS_COLLECT_METRICS)
            for key, value in (metrics or {}).items():
                kl = key.lower()
                c = (
                    value.split("|")[0]
                    .replace("$", "")
                    .replace(",", "")
                    .replace("%", "")
                    .replace("USD", "")
                    .replace(" ", "")
                    .replace("\u2212", "-")
                    .replace("−", "-")
                    .replace("+", "")
                )
                try:
                    num = float(c)
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

            if result.max_drawdown > 0 and result.max_drawdown_pct == 0:
                result.max_drawdown_pct = (result.max_drawdown / 50000) * 100

        except Exception as e:
            print(f" [read error: {e}]", end="")

        result.calculate_score()
        return result

    # ─────────────────────────────────── high-level optimization ─────────────

    async def optimize_pair(self, symbol: str) -> Optional[BacktestResult]:
        """Run full grid-search optimization for one symbol on this tab."""
        tag = f"[{symbol}]"
        print(f"\n{'=' * 60}")
        print(f"{tag} OPTIMIZING: {symbol}")
        print(f"{'=' * 60}")

        await self._switch_symbol(symbol)

        param_grid = self.optimizer.get_param_grid(symbol)
        combos = self.optimizer.generate_combinations(param_grid)
        total = len(combos)
        print(f"{tag} Testing {total} combinations...")

        best: Optional[BacktestResult] = None

        for idx, params in enumerate(combos, 1):
            _print_progress(idx, total)

            param_str = " | ".join(
                f"{k.split('_')[-1]}={v}" for k, v in params.items()
            )
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
                print(
                    f"  {tag} >>> NEW BEST! "
                    f"Score={result.score:.1f} PF={result.profit_factor:.2f}"
                )

        if best:
            _print_pair_summary_table(best)

        return best

    async def optimize_pair_smart(self, symbol: str) -> Optional[BacktestResult]:
        """Hill-climbing optimization: test one param at a time, keep improvements."""
        tag = f"[{symbol}]"
        print(f"\n{'=' * 60}")
        print(f"{tag} SMART OPTIMIZATION: {symbol}")
        print(f"{'=' * 60}")

        await self._switch_symbol(symbol)

        print(f"{tag} Reading baseline results...")
        baseline = await self._read_results(symbol, {"baseline": True})
        print(
            f"{tag} Baseline: PF={baseline.profit_factor:.2f} "
            f"WR={baseline.win_rate:.1f}% T={baseline.total_trades} "
            f"DD={baseline.max_drawdown:.0f} Score={baseline.score:.1f}"
        )

        best_score = baseline.score
        best_result = baseline
        test_count = 0

        # Resolve liq_distance param
        sym_upper = symbol.upper()
        if "XAU" in sym_upper or "GOLD" in sym_upper:
            liq_param, liq_values = "liq_max_distance_pips_gold", [80, 120, 200]
        elif any(x in sym_upper for x in ["NAS", "US100", "US500", "US30", "SPX"]):
            liq_param, liq_values = "liq_max_distance_pips_index", [300, 500, 700]
        else:
            liq_param, liq_values = "liq_max_distance_pips_forex", [10, 20, 30]

        params_to_test = []
        for name, values, ptype in HILL_CLIMB_PARAMS:
            if name == "liq_distance":
                params_to_test.append((liq_param, liq_values, "numeric"))
            else:
                params_to_test.append((name, values, ptype))

        total_params = len(params_to_test)
        total_tests = sum(len(v) for _, v, _ in params_to_test)
        print(f"{tag} Testing {total_params} parameters, ~{total_tests} total tests")

        improved_params: dict = {}

        for p_idx, (param_name, values, ptype) in enumerate(params_to_test, 1):
            short_name = (
                param_name.split("_")[-1] if len(param_name) > 15 else param_name
            )
            print(f"\n  {tag} [{p_idx}/{total_params}] Testing: {param_name}")

            param_best_score = best_score
            param_best_value = None

            for value in values:
                test_count += 1
                print(
                    f"    {tag} #{test_count} {short_name}={value}",
                    end="", flush=True,
                )

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
                    print(" +++")
                else:
                    print()

            if param_best_value is not None and param_best_score > best_score:
                print(
                    f"  {tag} >> KEEPING {param_name}={param_best_value} "
                    f"(Score: {best_score:.1f} -> {param_best_score:.1f})"
                )
                best_score = param_best_score
                improved_params[param_name] = param_best_value
                await self._apply_and_test(param_name, param_best_value, ptype, symbol)
                best_result = await self._read_results(symbol, improved_params)
                best_result.params = dict(improved_params)
            else:
                print(f"  {tag} >> No improvement from {param_name}, reverting")
                if improved_params:
                    if not await self._open_settings():
                        continue
                    await asyncio.sleep(0.3)
                    await self.page.evaluate(
                        """
                        (() => {
                            for (const b of document.querySelectorAll('button'))
                                if (b.textContent?.trim() === 'Inputs') {
                                    b.click(); return;
                                }
                        })()
                        """
                    )
                    await asyncio.sleep(0.2)
                    await self.page.evaluate(
                        """
                        (() => {
                            for (const b of document.querySelectorAll('button'))
                                if (b.textContent?.trim() === 'Cancel') {
                                    b.click(); return;
                                }
                        })()
                        """
                    )
                    await asyncio.sleep(0.5)

        print(f"\n{tag} {'=' * 50}")
        print(f"{tag} OPTIMIZATION COMPLETE")
        print(f"{tag} Tests run: {test_count}")
        print(f"{tag} Baseline score: {baseline.score:.1f}")
        delta = best_score - baseline.score
        sign = "+" if delta >= 0 else ""
        print(f"{tag} Final score:    {best_score:.1f} ({sign}{delta:.1f})")
        print(f"{tag} Improved params: {improved_params}")
        if best_result:
            print(
                f"{tag} Final: PF={best_result.profit_factor:.2f} "
                f"WR={best_result.win_rate:.1f}% T={best_result.total_trades} "
                f"DD%={best_result.max_drawdown_pct:.1f}%"
            )
            _print_pair_summary_table(best_result)

        best_result.params = improved_params
        return best_result


# ─────────────────────────────────── display helpers ─────────────────────────

def _print_progress(current: int, total: int, width: int = 30) -> None:
    """Print a simple ASCII progress bar to stdout."""
    filled = int(width * current / total) if total else 0
    bar = "=" * filled + ">" + " " * (width - filled - 1)
    print(f"\r  [{bar}] {current}/{total}  ", end="", flush=True)
    print()


def _print_pair_summary_table(result: BacktestResult) -> None:
    """Print a one-row summary table for a completed pair."""
    from .config import PROP_FIRM_MAX_DD_PCT
    compliant = "✅" if result.max_drawdown_pct <= PROP_FIRM_MAX_DD_PCT else "❌"
    header = (
        f"  {'Symbol':<10} | {'PF':>5} | {'WR':>7} | "
        f"{'Trades':>6} | {'DD%':>5} | {'Score':>7} | Prop"
    )
    sep = "  " + "-" * (len(header) - 2)
    row = (
        f"  {result.symbol:<10} | "
        f"{result.profit_factor:>5.2f} | "
        f"{result.win_rate:>6.1f}% | "
        f"{result.total_trades:>6} | "
        f"{result.max_drawdown_pct:>4.1f}% | "
        f"{result.score:>7.1f} | {compliant}"
    )
    print(sep)
    print(header)
    print(sep)
    print(row)
    print(sep)
