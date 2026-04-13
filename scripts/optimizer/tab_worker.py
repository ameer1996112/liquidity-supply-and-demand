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
import re
from dataclasses import dataclass
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
_UPDATE_APPEAR_TIMEOUT = 20  # seconds to wait for "Updating report" to appear (needs headroom for parallel workers)
_UPDATE_FINISH_TIMEOUT = 150 # seconds max for chart to finish recalculating

_LOADING_INDICATORS = [
    "Updating report", "Calculating...", "Loading...", "Compiling..."
]


@dataclass(slots=True)
class ApplyOutcome:
    """Structured outcome for a TradingView param application."""

    ok: bool
    fresh: bool
    reason: str = ""
    attempt: int = 0
    results_hash_before: str = ""
    results_hash_after: str = ""

    def __bool__(self) -> bool:
        return self.ok


# ─────────────────────────────────── JS snippets ─────────────────────────────

_JS_FIND_LOADING = """
(indicators) => {
    // Use TreeWalker to scan only text-bearing leaf nodes — much cheaper than querySelectorAll('*')
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    let node;
    while ((node = walker.nextNode())) {
        const t = node.textContent?.trim();
        if (!t || !indicators.includes(t)) continue;
        const el = node.parentElement;
        if (!el) continue;
        if (el.children.length > 2) continue;
        if (el.offsetParent === null) continue;
        return t;
    }
    return null;
}
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

_JS_CLICK_UPDATE_REPORT = """
(() => {
    for (const btn of document.querySelectorAll('button')) {
        if (btn.textContent?.trim() === 'Update report') { btn.click(); return true; }
    }
    return false;
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
                # Only check width — y-position varies with window/panel layout
                if box and 0 < box["width"] < 400:
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

    def sample_params(self, trial, symbol: str, fixed_overrides: dict = None) -> dict:
        """
        Translate an Optuna trial into a concrete parameter dict for TradingView.
        Handles liq_distance resolution per asset class and rr_mode expansion.

        fixed_overrides: dict of param→value to pin (bypasses Optuna's suggestion).
        e.g. {"rr_mode": "fixed_4.0"} locks RR and lets Bayesian explore the rest.
        """
        from .config import OPTUNA_SEARCH_SPACE

        params: dict = {}
        liq_range = self._liq_range(symbol)
        liq_param_name = liq_range["param"]
        overrides = fixed_overrides or {}

        for name, space in OPTUNA_SEARCH_SPACE.items():
            # Fixed override — bypass Optuna entirely for this param
            if name in overrides:
                if name == "liq_distance":
                    params[liq_param_name] = overrides[name]
                else:
                    params[name] = overrides[name]
                # Still need to register with Optuna so it doesn't complain
                # Use a dummy suggest that stays within bounds
                if space["type"] == "categorical":
                    trial.suggest_categorical(name, [overrides[name]])
                elif space["type"] == "int":
                    trial.suggest_int(name, space["low"], space["high"])
                elif space["type"] == "float":
                    trial.suggest_float(name, space["low"], space["high"])
                continue

            if name == "liq_distance":
                val = trial.suggest_float(
                    "liq_distance", liq_range["low"], liq_range["high"]
                )
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

        # ── Session constraint: start must be < end ───────────────────────────
        # If Optuna picks an invalid combination, clamp end to start+3 minimum.
        start = params.get("trading_start_hour")
        end = params.get("trading_end_hour")
        if start is not None and end is not None and end <= start:
            # Pick the next valid end hour from the choices that is > start
            valid_ends = [h for h in [12, 15, 17, 20, 22, 24] if h > start]
            params["trading_end_hour"] = valid_ends[0] if valid_ends else 24

        return params

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Collapse chart/title symbols into a comparable uppercase token."""
        return symbol.split(":")[-1].upper().strip()

    async def _current_symbol(self) -> str:
        """Return the symbol TradingView currently shows for this tab."""
        try:
            title = await self.page.title()
        except Exception:
            title = ""

        if title:
            token = title.split(" ")[0].split(":")[-1].upper().strip()
            if token:
                return token

        try:
            current_url = self.page.url
        except Exception:
            current_url = ""

        if "symbol=" in current_url:
            token = current_url.split("symbol=")[-1].split("&")[0]
            token = token.split("%3A")[-1].split(":")[-1].upper().strip()
            if token:
                return token

        return ""

    async def _verify_symbol(self, expected_symbol: str) -> str:
        """Fail closed if the tab is not on the requested symbol."""
        expected = self._normalize_symbol(expected_symbol)
        observed = await self._current_symbol()
        if not observed:
            raise RuntimeError(f"Could not verify TradingView symbol for {expected}")
        if observed != expected:
            raise RuntimeError(
                f"Symbol mismatch: expected {expected}, observed {observed}"
            )
        return observed


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

        # Always lock the backtest range to "Last 365 days" so optimizer
        # results are consistent and don't trigger slow Deep Backtesting mode.
        # NOTE: This is also called unconditionally in optimize_pair_bayesian
        # so it runs even when the symbol doesn't need to switch.
        await self._set_backtest_range("Last 365 days")


    async def _ensure_strategy_tester_open(self) -> None:
        """Ensure the Strategy Tester panel is visible and expanded.

        Tries in order:
          1. Check if the panel is already visible (has date-range button or
             the 'Strategy Tester' tab text in the bottom bar).
          2. Click the 'Strategy Tester' tab in the bottom toolbar.
          3. Fall back to the keyboard shortcut Alt+B.
        """
        try:
            already_open = await self.page.evaluate(
                """
                (() => {
                    // Check for the date-range button or any strategy-tester cells
                    if (document.querySelector('[data-name="report-range-button"]'))
                        return true;
                    if (document.querySelector('[class*="containerCell-"]'))
                        return true;
                    // Check for the "Updating report" / result cells being present
                    const tabs = document.querySelectorAll('[class*="bottomBar"] button, [class*="tab-"]');
                    for (const t of tabs) {
                        if (t.textContent?.trim() === 'Strategy Tester' && t.getAttribute('aria-selected') === 'true')
                            return true;
                    }
                    return false;
                })()
                """
            )
            if already_open:
                return

            # Try clicking the "Strategy Tester" tab
            clicked = await self.page.evaluate(
                """
                (() => {
                    for (const btn of document.querySelectorAll('button, [role="tab"]')) {
                        if (btn.textContent?.trim() === 'Strategy Tester') {
                            btn.click(); return true;
                        }
                    }
                    return false;
                })()
                """
            )
            if clicked:
                await asyncio.sleep(1.5)
                return

            # Fallback: Alt+B keyboard shortcut (TradingView default for Strategy Tester)
            await self.page.keyboard.press("Alt+b")
            await asyncio.sleep(1.5)

        except Exception as e:
            log.debug("_ensure_strategy_tester_open: %s", e)

    async def _read_backtest_range_button_text(self) -> str:
        """Return the bottom Strategy Report date-span button text, if visible."""
        try:
            return await self.page.evaluate(
                """
                (() => {
                    const visibleButtons = [...document.querySelectorAll('button, [role="button"]')]
                        .map((el) => {
                            const text = (el.textContent || '').trim().replace(/\\s+/g, ' ');
                            const rect = el.getBoundingClientRect();
                            const visible = rect.width > 0 && rect.height > 0;
                            return { el, text, rect, visible };
                        })
                        .filter((item) => item.visible && item.text.includes('\\u2014'));

                    if (!visibleButtons.length) {
                        return '';
                    }

                    // Prefer the date-range control in the Strategy Report area,
                    // which lives near the bottom of the viewport.
                    visibleButtons.sort((a, b) => b.rect.y - a.rect.y);
                    return visibleButtons[0].text;
                })()
                """
            )
        except Exception:
            return ""

    @staticmethod
    def _range_matches_label(btn_text: str, range_label: str) -> bool:
        """Return True when the Strategy Report span matches the requested preset."""
        if not btn_text:
            return False

        normalized = " ".join(btn_text.split())
        raw_dates = re.findall(
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}',
            normalized,
        )
        dates: list[str] = []
        for value in raw_dates:
            if not dates or dates[-1] != value:
                dates.append(value)

        if len(dates) < 2:
            return False

        try:
            start = datetime.strptime(dates[0], "%b %d, %Y")
            end = datetime.strptime(dates[1], "%b %d, %Y")
        except ValueError:
            return False

        delta_days = (end - start).days
        if range_label == "Last 365 days":
            return 330 <= delta_days <= 370
        if range_label == "Entire history":
            return delta_days >= 365 * 3
        return False

    async def _select_backtest_range_preset(self, range_label: str) -> bool:
        """Open the Strategy Report range menu and click a preset item."""
        opened = await self.page.evaluate(
            """
            (() => {
                const buttons = [...document.querySelectorAll('button, [role="button"]')]
                    .map((el) => {
                        const text = (el.textContent || '').trim().replace(/\\s+/g, ' ');
                        const rect = el.getBoundingClientRect();
                        const visible = rect.width > 0 && rect.height > 0;
                        return { el, text, rect, visible };
                    })
                    .filter((item) => item.visible && item.text.includes('\\u2014'));

                if (!buttons.length) {
                    return false;
                }

                buttons.sort((a, b) => b.rect.y - a.rect.y);
                buttons[0].el.click();
                return true;
            })()
            """
        )
        if not opened:
            return False

        await asyncio.sleep(0.4)

        chosen = await self.page.evaluate(
            """
            (targetLabel) => {
                const items = [...document.querySelectorAll('[role="menuitemcheckbox"], [role="menuitem"]')]
                    .map((el) => {
                        const text = (el.textContent || '').trim().replace(/\\s+/g, ' ');
                        const rect = el.getBoundingClientRect();
                        const visible = rect.width > 0 && rect.height > 0;
                        return { el, text, visible };
                    })
                    .filter((item) => item.visible);

                const target = items.find((item) => item.text === targetLabel);
                if (!target) {
                    return false;
                }

                target.el.click();
                return true;
            }
            """,
            range_label,
        )
        return bool(chosen)

    async def _set_backtest_range(self, range_label: str = "Entire history") -> bool:
        """
        Ensure the strategy tester date range covers approximately the desired period.

        In recent TradingView versions, the range button shows a floating date span
        like "Apr 12, 2025 — Apr 12, 2026" rather than a named preset.
        We detect if the span already covers the right period and skip if so.

        For "Last 365 days" — we check that the button's date span covers ~1 year.
        Returns True (success) in all cases where the range appears correct already.
        """
        try:
            await self._ensure_strategy_tester_open()
            btn_text = await self._read_backtest_range_button_text()

            if self._range_matches_label(btn_text, range_label):
                if range_label == "Last 365 days":
                    print(f"  [backtest range ✓ already ~1 year: {btn_text[:40].strip()}]", flush=True)
                else:
                    print(f"  [backtest range ✓ already entire history]", flush=True)
                return True

            if not await self._select_backtest_range_preset(range_label):
                log.warning(
                    "_set_backtest_range: could not open preset menu for '%s' "
                    "(button text='%s')",
                    range_label,
                    btn_text[:60] if btn_text else "(not found)",
                )
                return False

            await asyncio.sleep(0.4)
            await self._wait_for_update_complete()
            await self._wait_for_load()

            updated_text = await self._read_backtest_range_button_text()
            if self._range_matches_label(updated_text, range_label):
                if range_label == "Last 365 days":
                    print(f"  [backtest range ✓ set to ~1 year: {updated_text[:40].strip()}]", flush=True)
                else:
                    print(f"  [backtest range ✓ set to entire history]", flush=True)
                return True

            log.warning(
                "_set_backtest_range: attempted '%s' but final button text was '%s'",
                range_label,
                updated_text[:60] if updated_text else "(not found)",
            )
            return False

        except Exception as e:
            log.warning("_set_backtest_range: %s", e)
            return False





    async def _wait_for_load(self, timeout: int = 30) -> None:
        """Wait for chart and strategy tester to finish loading."""
        await asyncio.sleep(1.0)
        start = time.time()
        while time.time() - start < timeout:
            try:
                loading = await self.page.evaluate(
                    _JS_FIND_LOADING, _LOADING_INDICATORS
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
                _JS_FIND_LOADING, _LOADING_INDICATORS
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
            # TradingView sometimes stops auto-refreshing and shows this button instead
            await self.page.evaluate(_JS_CLICK_UPDATE_REPORT)

            if await self._check_loading_text():
                appeared = True
                break
            await asyncio.sleep(0.3)

        if not appeared:
            # TV didn't start a loading indicator — might be instant recalc,
            # might be that TV hasn't started yet. Wait longer and recheck.
            await asyncio.sleep(2.0)
            # Click "Update report" in case TV is waiting for manual trigger
            await self.page.evaluate(_JS_CLICK_UPDATE_REPORT)
            # Check once more — if loading appeared after the click, fall through to Phase 2
            if await self._check_loading_text():
                appeared = True
            else:
                # Still nothing: wait an extra second for any late recalc to settle
                await asyncio.sleep(1.0)
                return True

        # Phase 2 — wait for loading to disappear
        deadline = time.time() + _UPDATE_FINISH_TIMEOUT

        while time.time() < deadline:
            if not await self._check_loading_text():
                await asyncio.sleep(0.5)   # small buffer after disappears
                return True
            # Periodically try to click "Update report" in case TV is waiting
            if int(time.time()) % 10 == 0:
                await self.page.evaluate(_JS_CLICK_UPDATE_REPORT)
            await asyncio.sleep(0.5)

        log.warning("_wait_for_update_complete: timed out after %ds — trying recovery", _UPDATE_FINISH_TIMEOUT)
        # Recovery: press Escape to dismiss any stuck dialog, then wait extra
        try:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(2.0)
            # One final check after recovery
            if not await self._check_loading_text():
                return True
        except Exception:
            pass
        return False

    # ─────────────────────────────────── results fingerprint ─────────────────

    async def _ensure_fresh_results(self) -> None:
        """
        If TradingView is showing an 'Update report' button, click it and wait
        for recalculation to finish before reading results.
        """
        try:
            clicked = await self.page.evaluate(_JS_CLICK_UPDATE_REPORT)
            if clicked:
                # Wait for the loading indicator to appear then disappear
                await self._wait_for_update_complete()
        except Exception:
            pass

    async def _get_results_hash(self) -> str:
        """
        Return a short hash of the current strategy-tester result cells.
        Used to detect whether TradingView has recalculated after a param change.
        Clicks 'Update report' first if the tab is showing a stale report.
        """
        await self._ensure_fresh_results()
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

        # Click strategy name to reveal action buttons, then click Settings gear.
        # Must use page.mouse.click() with real pixel coords — JS btn.click() is
        # ignored by TradingView's React event handlers for these buttons.
        el = await page_query_snd(self.page)
        if el:
            box = await el.bounding_box()
            if box:
                await self.page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                await asyncio.sleep(0.4)

                # Find the Settings button pixel coordinates
                settings_coords = await self.page.evaluate(
                    """
                    (() => {
                        for (const btn of document.querySelectorAll('[title="Settings"]')) {
                            const box = btn.getBoundingClientRect();
                            if (btn.offsetParent !== null && box.width > 0)
                                return {x: box.x + box.width / 2, y: box.y + box.height / 2};
                        }
                        return null;
                    })()
                    """
                )
                if settings_coords:
                    await self.page.mouse.click(settings_coords['x'], settings_coords['y'])
                    await asyncio.sleep(1.5)
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

        # Fallback: try dblclick via Playwright (works when page has focus)
        if el:
            await el.dblclick()
            await asyncio.sleep(1.5)
            return True

        return False

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

    async def _reload_strategy_script(self) -> None:
        """
        Toggle the strategy visibility (eye icon) off then on.
        This is TradingView's standard way to restart a 'Script calculation timed out' error.
        Equivalent to clicking the eye icon in the chart legend twice.
        """
        try:
            # Click the eye/visibility button in the chart legend
            toggled = await self.page.evaluate(
                """
                (() => {
                    // Try data-name attribute first (most reliable)
                    let btn = document.querySelector(
                        '[data-name="legend-visibility-action"]'
                    );
                    // Fallback: find strategy row by name and grab first button
                    if (!btn) {
                        const rows = document.querySelectorAll(
                            '[class*="legendItem"], [class*="legend-"]'
                        );
                        for (const row of rows) {
                            if (row.textContent?.includes('S&D Algo')) {
                                btn = row.querySelector('button');
                                break;
                            }
                        }
                    }
                    if (btn) { btn.click(); return true; }
                    return false;
                })()
                """
            )
            if toggled:
                await asyncio.sleep(1.5)   # wait for script to unload
                # Click again to re-enable
                await self.page.evaluate(
                    """
                    (() => {
                        let btn = document.querySelector(
                            '[data-name="legend-visibility-action"]'
                        );
                        if (!btn) {
                            const rows = document.querySelectorAll(
                                '[class*="legendItem"], [class*="legend-"]'
                            );
                            for (const row of rows) {
                                if (row.textContent?.includes('S&D Algo')) {
                                    btn = row.querySelector('button'); break;
                                }
                            }
                        }
                        if (btn) btn.click();
                    })()
                    """
                )
                await asyncio.sleep(3.0)   # wait for script to reload & recalculate
                print(" [script reloaded via eye toggle]", end="", flush=True)
        except Exception as e:
            log.warning("_reload_strategy_script failed: %s", e)

    async def _dismiss_tv_errors(self) -> None:
        """Dismiss TradingView error toasts. If 'Script calculation timed out' detected,
        also reloads the strategy via eye-click toggle."""
        try:
            # Check if the timeout error is visible
            timed_out = await self.page.evaluate(
                """
                (() => {
                    const walker = document.createTreeWalker(
                        document.body, NodeFilter.SHOW_TEXT, null
                    );
                    let node;
                    while ((node = walker.nextNode())) {
                        if (node.textContent?.includes('timed out')) {
                            const el = node.parentElement;
                            if (el && el.childElementCount === 0) return true;
                        }
                    }
                    return false;
                })()
                """
            )
            if timed_out:
                print(" [⚠ script timed out, reloading...]", end="", flush=True)
                await self._reload_strategy_script()

            # Close any visible close/dismiss buttons on toasts
            dismissed = await self.page.evaluate(
                """
                (() => {
                    let count = 0;
                    for (const btn of document.querySelectorAll(
                        '[class*="close-"][class*="button"], [data-name="close-button"], '
                        + '[class*="toast"] button, [class*="notification"] button'
                    )) {
                        btn.click();
                        count++;
                    }
                    for (const btn of document.querySelectorAll('button')) {
                        const t = btn.textContent?.trim();
                        if (t === 'OK' || t === 'Dismiss' || t === 'Close') {
                            const inSettings = btn.closest('[class*="dialog-"][class*="rounded"]');
                            if (!inSettings) { btn.click(); count++; }
                        }
                    }
                    return count;
                })()
                """
            )
            if dismissed:
                await asyncio.sleep(0.5)
        except Exception:
            pass


    async def _ensure_custom_profile(self) -> bool:
        """
        Switch the strategy profile dropdown to 'Custom' if it isn't already.
        When any preset profile is active (e.g. 'Balanced (Recommended)'),
        TradingView locks inputs and ignores our changes — params never apply.
        This must be called before setting any param values.
        Returns True if profile is Custom (or was switched), False on failure.
        """
        try:
            profile = await self.page.evaluate(
                """
                (() => {
                    const d = document.querySelector('[class*="dialog-"][class*="rounded"]');
                    if (!d) return '';
                    const combo = d.querySelector('button[role="combobox"]');
                    return combo?.textContent?.trim() || '';
                })()
                """
            )

            # profile='' means dialog isn't ready (TV error state / script timeout)
            if profile == '':
                # Dismiss any error toasts first
                await self._dismiss_tv_errors()
                await asyncio.sleep(0.5)

                # Close the current (broken) dialog with Escape and reopen it
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.8)
                await self._open_settings()
                await asyncio.sleep(1.0)

                # Re-read the profile
                profile = await self.page.evaluate(
                    """
                    (() => {
                        const d = document.querySelector('[class*="dialog-"][class*="rounded"]');
                        if (!d) return '';
                        const combo = d.querySelector('button[role="combobox"]');
                        return combo?.textContent?.trim() || '';
                    })()
                    """
                )

            if profile == "Custom":
                return True

            print(f" [profile='{profile}', switching to Custom...]", end="", flush=True)

            # Click the combobox to open the dropdown
            await self.page.evaluate(
                """
                (() => {
                    const d = document.querySelector('[class*="dialog-"][class*="rounded"]');
                    if (!d) return;
                    const combo = d.querySelector('button[role="combobox"]');
                    if (combo) combo.click();
                })()
                """
            )
            await asyncio.sleep(0.6)

            # Click the "Custom" option — it can appear in a portal outside the dialog
            clicked = await self.page.evaluate(
                """
                (() => {
                    const selectors = [
                        '[role="option"]', '[class*="option"]',
                        '[class*="item-"]', 'li', '[class*="listItem"]',
                        '[class*="menuItem"]', '[class*="dropdownItem"]',
                    ];
                    for (const sel of selectors) {
                        for (const el of document.querySelectorAll(sel)) {
                            if (el.textContent?.trim() === 'Custom') {
                                el.click();
                                return true;
                            }
                        }
                    }
                    return false;
                })()
                """
            )

            if not clicked:
                # Couldn't find "Custom" option — press Escape to close dropdown
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                log.warning("_ensure_custom_profile: could not find 'Custom' option in dropdown")
                return False

            await asyncio.sleep(0.5)

            # Verify the switch worked
            new_profile = await self.page.evaluate(
                """
                (() => {
                    const d = document.querySelector('[class*="dialog-"][class*="rounded"]');
                    if (!d) return '';
                    const combo = d.querySelector('button[role="combobox"]');
                    return combo?.textContent?.trim() || '';
                })()
                """
            )
            if new_profile == "Custom":
                print(" [switched ✓]", end="", flush=True)
                return True
            else:
                log.warning(
                    "_ensure_custom_profile: still showing '%s' after click", new_profile
                )
                return False

        except Exception as e:
            log.warning("_ensure_custom_profile failed: %s", e)
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

    async def _apply_params(self, params: dict) -> ApplyOutcome:
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
            hash_before = ""
            hash_after = ""
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

                # Ensure profile is Custom — preset profiles lock inputs and ignore changes
                await self._ensure_custom_profile()

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
                        "_apply_params attempt %d: update timed out — pressing Escape and retrying", attempt
                    )
                    # Try to dismiss any stuck overlay before retry
                    try:
                        await self.page.keyboard.press("Escape")
                        await asyncio.sleep(1.0)
                    except Exception:
                        pass

                # ── Stale result detection ─────────────────────────────────
                hash_after = await self._get_results_hash()
                if not hash_after:
                    log.warning(
                        "_apply_params attempt %d: could not read results hash",
                        attempt,
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(_RETRY_SLEEP)
                        continue
                    return ApplyOutcome(
                        ok=False,
                        fresh=False,
                        reason="missing_results_hash",
                        attempt=attempt,
                        results_hash_before=hash_before,
                        results_hash_after=hash_after,
                    )
                if hash_before and hash_after and hash_before == hash_after:
                    log.warning(
                        "_apply_params attempt %d: results hash unchanged "
                        "(hash_before=%s hash_after=%s — possible stale read or param rejected)",
                        attempt, hash_before, hash_after,
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(_RETRY_SLEEP)
                        continue

                    return ApplyOutcome(
                        ok=False,
                        fresh=False,
                        reason="stale_result_hash",
                        attempt=attempt,
                        results_hash_before=hash_before,
                        results_hash_after=hash_after,
                    )

                return ApplyOutcome(
                    ok=True,
                    fresh=True,
                    reason="fresh_result",
                    attempt=attempt,
                    results_hash_before=hash_before,
                    results_hash_after=hash_after,
                )

            except Exception as e:
                log.warning(
                    "_apply_params attempt %d/%d failed: %s", attempt, _MAX_RETRIES, e
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_SLEEP)
                else:
                    log.warning("_apply_params: all retries exhausted, skipping combo")
                    return ApplyOutcome(
                        ok=False,
                        fresh=False,
                        reason="apply_failed",
                        attempt=attempt,
                        results_hash_before=hash_before,
                        results_hash_after=hash_after,
                    )
        return ApplyOutcome(
            ok=False,
            fresh=False,
            reason="apply_failed",
            attempt=_MAX_RETRIES,
            results_hash_before="",
            results_hash_after="",
        )

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
                completed = await self._wait_for_update_complete()

                # Stale check
                hash_after = await self._get_results_hash()
                if hash_before and hash_after and hash_before == hash_after:
                    log.warning(
                        "_apply_and_test: stale result after %s=%s (attempt %d)",
                        param_name, value, attempt
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(_RETRY_SLEEP)
                        continue
                    return BacktestResult(
                        symbol=symbol,
                        params={param_name: value},
                        timestamp=datetime.now().isoformat(),
                    )

                if not completed:
                    log.warning(
                        "_apply_and_test: update did not complete for %s=%s",
                        param_name, value,
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(_RETRY_SLEEP)
                        continue
                    return BacktestResult(
                        symbol=symbol,
                        params={param_name: value},
                        timestamp=datetime.now().isoformat(),
                    )

                try:
                    return await self._read_results(symbol, {param_name: value})
                except RuntimeError as e:
                    log.warning(
                        "_apply_and_test: symbol verification failed for %s=%s: %s",
                        param_name, value, e,
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(_RETRY_SLEEP)
                        continue
                    return BacktestResult(
                        symbol=symbol,
                        params={param_name: value},
                        timestamp=datetime.now().isoformat(),
                    )

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
        observed_symbol = await self._verify_symbol(symbol)
        result = BacktestResult(
            symbol=symbol,
            params=params.copy(),
            verified_symbol=observed_symbol,
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

            apply_outcome = await self._apply_params(params)
            if not apply_outcome.fresh:
                print(f" -> SKIP ({apply_outcome.reason or 'stale apply outcome'})")
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
