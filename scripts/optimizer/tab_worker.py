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
import json
import time
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from .config import (
    CHECKBOX_PARAM_NAMES,
    HILL_CLIMB_PARAMS,
    INPUT_INDEX,
    LIQ_DISTANCE_RANGES,
    OPTIMIZER_CONTEXT_PARAM_DEFAULTS,
    materialize_result_params,
)
from .models import BacktestResult, NoDataForRangeError
from .optimizer_mcp import broker_to_tv_exchange, broker_to_tv_symbol_prefix

if TYPE_CHECKING:
    from playwright.async_api import Page
    from .optimizer import TradingViewOptimizer

log = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_SLEEP = 2.0          # seconds between retry attempts
_UPDATE_APPEAR_TIMEOUT = 20  # seconds to wait for "Updating report" to appear (needs headroom for parallel workers)
_UPDATE_FINISH_TIMEOUT = 150 # seconds max for chart to finish recalculating
_UPDATE_SETTLE_TIMEOUT = 25   # seconds to require stable Strategy Report results after spinner disappears
_UPDATE_SETTLE_SLEEP = 0.5
_UPDATE_SETTLE_POLLS = 3
_HISTORY_COVERAGE_MIN_RATIO = 0.80
_HISTORY_LOAD_MAX_ATTEMPTS = 12
_HISTORY_LOAD_SLEEP = 3.0
_TRADE_COVERAGE_MIN_RATIO = 0.80

_LOADING_INDICATORS = [
    "Updating report", "Calculating...", "Loading...", "Compiling..."
]

_REPORT_TIMEOUT_TEXT = "request took too long to process"

_REPORT_METRIC_LABELS = [
    "Net profit",
    "Total P&L",
    "Total trades",
    "Total closed trades",
    "Profitable trades",
    "Percent profitable",
    "Profit factor",
    "Max equity drawdown",
]

_BACKTEST_RANGE_PRESETS: dict[str, dict[str, object]] = {
    "30d": {
        "label": "Last 30 days",
        "chart_tab": "date-range-tab-1M",
        "min_days": 25,
        "max_days": 35,
        "summary": "~30 days",
    },
    "90d": {
        "label": "Last 90 days",
        "chart_tab": "date-range-tab-3M",
        "min_days": 80,
        "max_days": 100,
        "summary": "~90 days",
    },
    "365d": {
        "label": "Last 365 days",
        "chart_tab": "date-range-tab-12M",
        "min_days": 330,
        "max_days": 370,
        "summary": "~1 year",
    },
    "all": {
        "label": "Entire history",
        "chart_tab": "date-range-tab-ALL",
        "min_days": 365 * 3,
        "max_days": None,
        "summary": "entire history",
    },
    "custom": {
        "label": "Custom range",
        "chart_tab": "",
        "min_days": 30,
        "max_days": None,
        "summary": "custom range",
    },
}

_BACKTEST_RANGE_ALIASES = {
    "30": "30d",
    "30d": "30d",
    "last 30 days": "30d",
    "90": "90d",
    "90d": "90d",
    "last 90 days": "90d",
    "365": "365d",
    "365d": "365d",
    "1y": "365d",
    "1yr": "365d",
    "last 365 days": "365d",
    "all": "all",
    "entire history": "all",
    "custom": "custom",
    "custom range": "custom",
}


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


@dataclass(slots=True)
class ChartHistoryCoverage:
    """Loaded chart-history coverage for a requested backtest date window."""

    requested_days: float
    covered_days: float
    coverage_ratio: float
    loaded_bar_count: int
    loaded_first_ts: int
    loaded_last_ts: int
    loaded_first_date: str
    loaded_last_date: str


@dataclass(slots=True)
class StrategyTradeCoverage:
    """Actual Strategy Tester trade-date coverage for a requested window."""

    requested_days: float
    trade_span_days: float
    coverage_ratio: float
    total_trades: int
    inspected_orders: int
    trade_date_count: int
    first_trade_ts: int
    last_trade_ts: int
    first_trade_date: str
    last_trade_date: str


def normalize_backtest_range(value: str | None) -> str:
    """Return the canonical optimizer backtest range key."""
    normalized = (value or "365d").strip().lower()
    try:
        return _BACKTEST_RANGE_ALIASES[normalized]
    except KeyError as exc:
        choices = ", ".join(sorted(_BACKTEST_RANGE_PRESETS))
        raise ValueError(f"Unsupported backtest range '{value}'. Expected one of: {choices}") from exc


def backtest_range_to_label(value: str | None) -> str:
    """Translate a canonical or human-readable range into the TradingView preset label."""
    preset = _BACKTEST_RANGE_PRESETS[normalize_backtest_range(value)]
    return str(preset["label"])


def _backtest_range_preset(range_label: str) -> dict[str, object]:
    """Resolve a TradingView label or shorthand range key to a preset spec."""
    return _BACKTEST_RANGE_PRESETS[normalize_backtest_range(range_label)]


def _iso_date_to_unix_seconds(value: str) -> int:
    parsed = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


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
    const metricLabels = __REPORT_METRIC_LABELS__;
    const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim();
    const visible = (el) => {
        const rect = el?.getBoundingClientRect?.();
        const style = el ? window.getComputedStyle(el) : null;
        return !!rect && rect.width > 0 && rect.height > 0 &&
            style?.visibility !== 'hidden' && style?.display !== 'none';
    };
    const buildFallbackParts = () => {
        const parts = [];
        const seen = new Set();
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
        let node;
        while ((node = walker.nextNode())) {
            const label = normalize(node.textContent);
            if (!metricLabels.includes(label)) continue;
            const el = node.parentElement;
            if (!el || !visible(el)) continue;
            const row = el.closest('[role="row"], [class*="row"], [class*="cell"], [class*="container"]')
                || el.parentElement
                || el;
            const rowText = normalize(row?.textContent || '');
            if (!rowText || rowText === label || seen.has(label)) continue;
            seen.add(label);
            parts.push(label + '=' + rowText);
        }
        return parts;
    };

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
    if (!parts.length) {
        parts.push(...buildFallbackParts());
    }
    return parts.join(';');
})()
""".replace("__REPORT_METRIC_LABELS__", json.dumps(_REPORT_METRIC_LABELS))

_JS_CLICK_UPDATE_REPORT = """
(() => {
    for (const btn of document.querySelectorAll('button')) {
        if (btn.textContent?.trim() === 'Update report') { btn.click(); return true; }
    }
    return false;
})()
"""

_JS_HAS_REPORT_TIMEOUT = """
(needle) => {
    const wanted = (needle || '').trim().toLowerCase();
    if (!wanted) return false;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    let node;
    while ((node = walker.nextNode())) {
        const text = node.textContent?.trim().toLowerCase();
        if (!text || !text.includes(wanted)) continue;
        const el = node.parentElement;
        if (!el || el.offsetParent === null) continue;
        return true;
    }
    return false;
}
"""

_JS_COLLECT_METRICS = """
(() => {
    const metricLabels = __REPORT_METRIC_LABELS__;
    const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim();
    const visible = (el) => {
        const rect = el?.getBoundingClientRect?.();
        const style = el ? window.getComputedStyle(el) : null;
        return !!rect && rect.width > 0 && rect.height > 0 &&
            style?.visibility !== 'hidden' && style?.display !== 'none';
    };
    const r = {};
    for (const cell of document.querySelectorAll('[class*="containerCell-"]')) {
        const t = cell.querySelector('[class*="title-"]');
        const title = t?.textContent?.trim() || '';
        const vals = cell.querySelectorAll('[class*="value-"], [class*="additional-"]');
        const cellText = (cell.textContent || '').replace(/\\s+/g, ' ').trim();
        if (!title || !cellText) continue;

        let body = cellText;
        if (body.startsWith(title)) {
            body = body.slice(title.length).trim();
        }

        if (title) {
            const vs = [];
            for (const v of vals) { const x = v.textContent?.trim(); if (x) vs.push(x); }
            if (vs.length) {
                const joined = vs.join('|');
                // TradingView sometimes renders the drawdown percent outside the
                // value/additional nodes. Preserve the full cell body so the
                // parser can still read the displayed percentage.
                if (
                    title.toLowerCase().includes('drawdown') &&
                    body.includes('%') &&
                    !joined.includes('%')
                ) {
                    r[title] = joined + '|' + body;
                } else {
                    r[title] = joined;
                }
                continue;
            }

            // Fallback: capture full cell text in case TradingView moved
            // percentage/value elements outside value/additional classes.
            r[title] = body || cellText;
        }
    }

    if (Object.keys(r).length) return r;

    const seen = new Set();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    let node;
    while ((node = walker.nextNode())) {
        const label = normalize(node.textContent);
        if (!metricLabels.includes(label) || seen.has(label)) continue;
        const el = node.parentElement;
        if (!el || !visible(el)) continue;
        const row = el.closest('[role="row"], [class*="row"], [class*="cell"], [class*="container"]')
            || el.parentElement
            || el;
        const rowText = normalize(row?.textContent || '');
        if (!rowText) continue;
        let body = rowText;
        if (body.startsWith(label)) {
            body = body.slice(label.length).trim();
        }
        if (!body) continue;
        r[label] = body;
        seen.add(label);
    }

    return r;
})()
""".replace("__REPORT_METRIC_LABELS__", json.dumps(_REPORT_METRIC_LABELS))

_JS_HAS_STRATEGY_REPORT_METRICS = """
(() => {
    const metricLabels = [
        'Profit factor',
        'Profitable trades',
        'Total trades',
        'Max equity drawdown',
        'Net profit',
    ];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    let node;
    while ((node = walker.nextNode())) {
        const text = node.textContent?.trim();
        if (!text || !metricLabels.includes(text)) continue;
        const el = node.parentElement;
        if (!el || el.offsetParent === null) continue;
        return true;
    }
    return false;
})()
"""

_JS_SETTINGS_DIALOG_HELPERS = """
const __tvVisible = (el) => {
    const rect = el?.getBoundingClientRect?.();
    const style = el ? window.getComputedStyle(el) : null;
    return !!rect && rect.width > 0 && rect.height > 0 &&
        style?.visibility !== 'hidden' && style?.display !== 'none';
};
const __tvNormalize = (text) => (text || '').replace(/\\s+/g, ' ').trim();
const __tvDialogText = (dialog) => __tvNormalize(dialog?.textContent || '');
const __tvDialogTabTexts = (dialog) => Array.from(dialog?.querySelectorAll?.('[role="tab"], button') || [])
    .map((el) => __tvNormalize(el.textContent).toLowerCase())
    .filter(Boolean);
const __tvLooksLikeChartSettings = (dialog) => {
    const tabTexts = __tvDialogTabTexts(dialog);
    const chartTabs = ['symbol', 'status line', 'scales and lines', 'canvas', 'trading', 'alerts', 'events'];
    const matches = chartTabs.filter((tab) => tabTexts.includes(tab)).length;
    return matches >= 3 && !tabTexts.includes('inputs');
};
const __tvDialogScore = (dialog) => {
    if (!dialog) return -1;
    const text = __tvDialogText(dialog).toLowerCase();
    if (__tvLooksLikeChartSettings(dialog)) return -100;
    let score = 0;
    if (dialog.matches?.('[data-name="indicator-properties-dialog"][role="dialog"]')) score += 80;
    if (dialog.querySelector('[data-name="indicator-properties-dialog-tabs"]')) score += 35;
    if (dialog.querySelector('button[role="combobox"]')) score += 15;
    if (dialog.querySelector('input, textarea, [role="spinbutton"], [data-name="source-properties-editor"]')) score += 12;
    const tabTexts = __tvDialogTabTexts(dialog);
    if (tabTexts.includes('inputs')) score += 20;
    if (tabTexts.includes('style') || tabTexts.includes('properties')) score += 10;
    const buttonTexts = Array.from(dialog.querySelectorAll('button'))
        .map((el) => __tvNormalize(el.textContent).toLowerCase())
        .filter(Boolean);
    if (buttonTexts.includes('ok')) score += 8;
    if (buttonTexts.includes('cancel')) score += 6;
    if (text.includes('s&d algo')) score += 35;
    if (text.includes('custom')) score += 8;
    const zIndex = Number.parseInt(window.getComputedStyle(dialog).zIndex || '0', 10);
    if (Number.isFinite(zIndex)) score += Math.max(0, Math.min(zIndex, 9999)) / 1000;
    return score;
};
const __tvDialogReady = (dialog) => {
    if (!dialog) return false;
    if (__tvLooksLikeChartSettings(dialog)) return false;
    if (dialog.querySelector('button[role="combobox"]')) return true;
    if (dialog.querySelector('[data-name="indicator-properties-dialog-tabs"]')) return true;
    return !!dialog.querySelector('input, textarea, [role="spinbutton"], [data-name="source-properties-editor"]');
};
const __tvPickSettingsDialog = (requireReady = false) => {
    const dialogs = Array.from(
        document.querySelectorAll(
            '[data-name="indicator-properties-dialog"][role="dialog"], '
            + '[data-name="indicator-properties-dialog"], '
            + '[role="dialog"], [aria-modal="true"], '
            + '[data-name*="dialog"], [data-name*="properties"], '
            + '[class*="dialog-"][class*="rounded"], [class*="dialog"], [class*="modal"]'
        )
    ).filter(__tvVisible);
    const ranked = dialogs
        .map((dialog) => ({ dialog, score: __tvDialogScore(dialog) }))
        .filter(({ dialog, score }) => score >= 40 && (!requireReady || __tvDialogReady(dialog)))
        .sort((a, b) => b.score - a.score);
    return ranked[0]?.dialog || null;
};
const __tvDescribeSettingsDialogs = () => {
    const dialogs = Array.from(
        document.querySelectorAll(
            '[data-name="indicator-properties-dialog"][role="dialog"], '
            + '[data-name="indicator-properties-dialog"], '
            + '[role="dialog"], [aria-modal="true"], '
            + '[data-name*="dialog"], [data-name*="properties"], '
            + '[class*="dialog-"][class*="rounded"], [class*="dialog"], [class*="modal"]'
        )
    ).filter(__tvVisible);
    return dialogs
        .map((dialog) => ({
            score: __tvDialogScore(dialog),
            ready: __tvDialogReady(dialog),
            chartSettings: __tvLooksLikeChartSettings(dialog),
            combo: !!dialog.querySelector('button[role="combobox"]'),
            tabs: __tvDialogTabTexts(dialog).slice(0, 6),
            text: __tvDialogText(dialog).slice(0, 240),
        }))
        .sort((a, b) => b.score - a.score)
        .slice(0, 3);
};
"""

_JS_INPUT_BY_TITLE_HELPERS = """
const __tvTextNodeValues = (root) => {
    const values = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
        const text = __tvNormalize(walker.currentNode.nodeValue);
        if (text) values.push(text);
    }
    return values;
};
const __tvRowHasExactTitle = (root, title) => {
    const target = __tvNormalize(title);
    return __tvTextNodeValues(root).some((text) => text === target);
};
const __tvFindInputByTitle = (dialog, title) => {
    const controls = Array.from(dialog.querySelectorAll('input, textarea, button[role="combobox"]'))
        .filter(__tvVisible);
    for (const control of controls) {
        let node = control.parentElement;
        for (let depth = 0; node && depth < 8; depth += 1, node = node.parentElement) {
            if (node === dialog || node === dialog.parentElement) break;
            const scopedControls = Array.from(node.querySelectorAll('input, textarea, button[role="combobox"]'))
                .filter(__tvVisible);
            if (scopedControls.length !== 1 || scopedControls[0] !== control) continue;
            if (__tvRowHasExactTitle(node, title)) return control;
            const previous = node.previousElementSibling;
            if (previous && __tvVisible(previous) &&
                !previous.querySelector('input, textarea, button[role="combobox"]') &&
                __tvRowHasExactTitle(previous, title)) return control;
        }
    }
    return null;
};
const __tvAvailableInputTitles = (dialog) => {
    const titles = [];
    const controls = Array.from(dialog.querySelectorAll('input, textarea, button[role="combobox"]'))
        .filter(__tvVisible);
    for (const control of controls) {
        let node = control.parentElement;
        for (let depth = 0; node && depth < 8; depth += 1, node = node.parentElement) {
            if (node === dialog || node === dialog.parentElement) break;
            const scopedControls = Array.from(node.querySelectorAll('input, textarea, button[role="combobox"]'))
                .filter(__tvVisible);
            if (scopedControls.length !== 1 || scopedControls[0] !== control) continue;
            const candidates = __tvTextNodeValues(node)
                .filter((text) => /^[A-Za-z_][A-Za-z0-9_]*$/.test(text));
            if (candidates.length) {
                titles.push(candidates[0]);
                break;
            }
            const previous = node.previousElementSibling;
            if (!previous || !__tvVisible(previous) ||
                previous.querySelector('input, textarea, button[role="combobox"]')) continue;
            const siblingCandidates = __tvTextNodeValues(previous)
                .filter((text) => /^[A-Za-z_][A-Za-z0-9_]*$/.test(text));
            if (siblingCandidates.length) {
                titles.push(siblingCandidates[0]);
                break;
            }
        }
    }
    return Array.from(new Set(titles));
};
"""

_JS_HAS_READY_SETTINGS_DIALOG = f"""
(() => {{
    {_JS_SETTINGS_DIALOG_HELPERS}
    return !!__tvPickSettingsDialog(true);
}})()
"""


async def page_query_snd(page: "Page"):
    """Find the S&D strategy legend coordinates."""
    try:
        return await page.evaluate(
            """
            (() => {
                const strategyTitles = ['S&D Algo [Pro]', 'S&D Pro'];
                for (const el of document.querySelectorAll('div')) {
                    const text = el.textContent?.trim();
                    if (!strategyTitles.includes(text)) continue;
                    const box = el.getBoundingClientRect();
                    if (el.offsetParent !== null && box.width > 0 && box.width < 400) {
                        return {
                            x: box.x + box.width / 2,
                            y: box.y + box.height / 2,
                            width: box.width,
                            height: box.height,
                        };
                    }
                }
                return null;
            })()
            """
        )
    except Exception:
        return None



class TabWorker:
    """Handles optimization on a single TradingView tab. Safe for sequential use."""

    def __init__(self, page: "Page", optimizer: "TradingViewOptimizer"):
        self.page = page
        self.optimizer = optimizer
        self.results: list[BacktestResult] = []

    async def _has_ready_settings_dialog(self) -> bool:
        """Return True only when the visible settings dialog has loaded usable controls."""
        try:
            return bool(await self.page.evaluate(_JS_HAS_READY_SETTINGS_DIALOG))
        except Exception:
            return False

    async def _read_profile_dropdown_text(self) -> str:
        """Return the current strategy profile label from the visible settings dialog."""
        try:
            return await self.page.evaluate(
                f"""
                (() => {{
                    {_JS_SETTINGS_DIALOG_HELPERS}
                    const dialog = __tvPickSettingsDialog(true);
                    if (!dialog) return '';
                    const combo = dialog.querySelector('button[role="combobox"]');
                    return __tvNormalize(combo?.textContent || '');
                }})()
                """
            )
        except Exception:
            return ""

    async def _describe_settings_dialogs(self) -> list[dict]:
        """Return a compact summary of the visible settings dialogs for debugging."""
        try:
            dialogs = await self.page.evaluate(
                f"""
                (() => {{
                    {_JS_SETTINGS_DIALOG_HELPERS}
                    return __tvDescribeSettingsDialogs();
                }})()
                """
            )
            if isinstance(dialogs, list):
                return dialogs
        except Exception:
            pass
        return []

    async def _log_dialog_state(self, context: str) -> None:
        """Log the top visible dialog candidates when the expected strategy dialog is missing."""
        dialogs = await self._describe_settings_dialogs()
        if not dialogs:
            log.warning("%s: no visible settings dialogs detected", context)
            return
        log.warning("%s: visible dialog candidates=%s", context, dialogs)

    async def _has_wrong_settings_dialog(self) -> bool:
        """Return True when the visible modal is TradingView chart settings, not strategy settings."""
        dialogs = await self._describe_settings_dialogs()
        return any(bool(dialog.get("chartSettings")) for dialog in dialogs)

    async def _dismiss_wrong_settings_dialog(self) -> bool:
        """Close a visible chart-settings modal if TradingView opened the wrong window."""
        try:
            close_target = await self.page.evaluate(
                f"""
                (() => {{
                    {_JS_SETTINGS_DIALOG_HELPERS}
                    const dialogs = Array.from(
                        document.querySelectorAll(
                            '[data-name="indicator-properties-dialog"][role="dialog"], '
                            + '[data-name="indicator-properties-dialog"], '
                            + '[role="dialog"], [aria-modal="true"], '
                            + '[data-name*="dialog"], [data-name*="properties"], '
                            + '[class*="dialog-"][class*="rounded"], [class*="dialog"], [class*="modal"]'
                        )
                    ).filter(__tvVisible);
                    const wrong = dialogs
                        .map((dialog) => ({{
                            dialog,
                            score: __tvDialogScore(dialog),
                            chartSettings: __tvLooksLikeChartSettings(dialog),
                        }}))
                        .filter((item) => item.chartSettings)
                        .sort((a, b) => b.score - a.score)[0]?.dialog;
                    if (!wrong) return null;
                    const closeButton = Array.from(wrong.querySelectorAll('button'))
                        .find((btn) => __tvVisible(btn) && (
                            __tvNormalize(btn.getAttribute('aria-label')).toLowerCase() === 'close' ||
                            __tvNormalize(btn.getAttribute('title')).toLowerCase() === 'close' ||
                            __tvNormalize(btn.textContent) === '×'
                        ));
                    const rect = wrong.getBoundingClientRect?.();
                    if (closeButton) {{
                        const box = closeButton.getBoundingClientRect?.();
                        if (box && box.width > 0 && box.height > 0) {{
                            return {{
                                x: box.x + box.width / 2,
                                y: box.y + box.height / 2,
                                reason: 'close-button',
                            }};
                        }}
                    }}
                    if (!rect || rect.width <= 0 || rect.height <= 0) return null;
                    return {{
                        x: rect.right - Math.min(32, rect.width * 0.06),
                        y: rect.top + Math.min(28, rect.height * 0.06),
                        reason: 'top-right-fallback',
                    }};
                }})()
                """
            )
            if isinstance(close_target, dict) and "x" in close_target and "y" in close_target:
                await self.page.mouse.click(float(close_target["x"]), float(close_target["y"]))
                await asyncio.sleep(0.5)
                if not await self._has_wrong_settings_dialog():
                    return True
        except Exception:
            pass

        try:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            return not await self._has_wrong_settings_dialog()
        except Exception:
            return False

    async def _recover_blank_settings_dialog(self) -> str:
        """Dismiss broken dialog state, reopen settings, and wait briefly for the profile control."""
        await self._dismiss_tv_errors()
        await asyncio.sleep(0.5)

        for _ in range(2):
            try:
                await self.page.keyboard.press("Escape")
            except Exception:
                break
            await asyncio.sleep(0.4)

        for attempt in range(2):
            await self._dismiss_tv_errors()
            if not await self._open_settings():
                await asyncio.sleep(0.6)
                continue

            if await self._has_wrong_settings_dialog():
                await self._log_dialog_state("_recover_blank_settings_dialog wrong dialog after reopen")
                await self._dismiss_wrong_settings_dialog()
                await asyncio.sleep(0.5)
                continue

            for _ in range(8):
                profile = await self._read_profile_dropdown_text()
                if profile:
                    return profile
                await asyncio.sleep(0.4)

            if attempt == 0:
                await self._log_dialog_state("_recover_blank_settings_dialog before strategy reload")
                log.warning("_recover_blank_settings_dialog: dialog stayed blank, reloading strategy script")
                await self._reload_strategy_script()
                await asyncio.sleep(1.0)

        return ""

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

        params: dict = dict(OPTIMIZER_CONTEXT_PARAM_DEFAULTS)
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

    @staticmethod
    def _split_symbol_token(value: str) -> tuple[str, str]:
        """Split a TradingView symbol token into broker/feed and symbol parts."""
        token = str(value or "").upper().strip()
        if not token:
            return "", ""
        if ":" not in token:
            return "", token
        broker, symbol = token.split(":", 1)
        return broker.strip(), symbol.strip()

    @staticmethod
    def _broker_matches_expected(observed_broker: str, expected_broker: str) -> bool:
        """Return True when TradingView's observed broker/feed should count as expected."""
        observed = str(observed_broker or "").upper().strip()
        expected = str(expected_broker or "").upper().strip()
        if not observed or not expected:
            return False
        if observed == expected:
            return True
        if expected == "FXCM" and observed == "FX":
            return True
        return False

    @staticmethod
    def _looks_like_symbol(value: str) -> bool:
        token = value.upper().strip()
        if not token or len(token) > 32:
            return False
        if any(ch in token for ch in " ${}%[]()|,"):
            return False
        return bool(re.fullmatch(r"[A-Z0-9:._!\-]+", token))

    @staticmethod
    def _extract_first_number(text: str) -> float | None:
        """Extract first numeric token from text (supports thousands separators)."""
        if not text:
            return None
        match = re.search(r"[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[-+]?\d+(?:\.\d+)?", text)
        if not match:
            return None
        try:
            return float(match.group(0).replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def _extract_first_percent(text: str) -> float | None:
        """Extract first percentage token from text (e.g. '12.02%')."""
        if not text:
            return None
        match = re.search(r"([-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[-+]?\d+(?:\.\d+)?)\s*%", text)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None

    async def _current_symbol(self) -> str:
        """Return the symbol TradingView currently shows for this tab."""
        return (await self._current_symbol_details())[1]

    async def _current_broker(self) -> str:
        """Return the active TradingView broker/feed token when available."""
        return (await self._current_symbol_details())[0]

    async def _current_symbol_details(self) -> tuple[str, str]:
        """Return `(broker, symbol)` for the current TradingView chart."""
        if hasattr(self.page, "tab_id"):
            try:
                api_symbol = await self.page.evaluate(
                    """
                    (() => {
                        try {
                            return window.TradingViewApi?._activeChartWidgetWV?.value()?.symbol?.() || '';
                        } catch (error) {
                            return '';
                        }
                    })()
                    """
                )
                raw_api_symbol = str(api_symbol or "").upper().strip()
                if self._looks_like_symbol(raw_api_symbol):
                    broker, symbol = self._split_symbol_token(raw_api_symbol)
                    if self._looks_like_symbol(symbol):
                        return broker, symbol
            except Exception:
                pass

        try:
            title = await self.page.title()
        except Exception:
            title = ""

        if title:
            token = title.split(" ")[0].split(":")[-1].upper().strip()
            if token and token not in {"LIVE", "TRADINGVIEW"} and self._looks_like_symbol(token):
                return "", token

        try:
            current_url = self.page.url
        except Exception:
            current_url = ""

        if "symbol=" in current_url:
            token = current_url.split("symbol=")[-1].split("&")[0]
            token = token.replace("%3A", ":").upper().strip()
            broker, symbol = self._split_symbol_token(token)
            if symbol:
                return broker, symbol

        return "", ""

    async def _has_symbol_error_badge(self) -> bool:
        """Return True when TradingView shows a visible symbol-level error badge."""
        try:
            return bool(
                await self.page.evaluate(
                    """
                    (() => {
                        const visible = (el) => {
                            const rect = el?.getBoundingClientRect?.();
                            const style = el ? window.getComputedStyle(el) : null;
                            return !!rect && rect.width > 0 && rect.height > 0 &&
                                style?.visibility !== 'hidden' && style?.display !== 'none';
                        };
                        const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                        return Array.from(document.querySelectorAll('button, span, div, [role="img"], [aria-label], [title]'))
                            .filter((el) => visible(el))
                            .filter((el) => {
                                const rect = el.getBoundingClientRect();
                                return rect.y < 180 && rect.x < 520;
                            })
                            .some((el) => {
                                const text = normalize(el.textContent);
                                const aria = normalize(el.getAttribute('aria-label'));
                                const title = normalize(el.getAttribute('title'));
                                if (text === '!') return true;
                                return aria.includes('invalid symbol')
                                    || aria.includes('symbol error')
                                    || aria.includes('error')
                                    || title.includes('invalid symbol')
                                    || title.includes('symbol error');
                            });
                    })()
                    """
                )
            )
        except Exception:
            return False

    async def _open_symbol_search_dialog(self, current_symbol: str) -> bool:
        """Open TradingView's symbol search dialog from the chart header."""
        async def dialog_open() -> bool:
            try:
                return bool(
                    await self.page.evaluate(
                        """
                        (() => {
                            const visible = (el) => {
                                const rect = el?.getBoundingClientRect?.();
                                const style = el ? window.getComputedStyle(el) : null;
                                return !!rect && rect.width > 0 && rect.height > 0 &&
                                    style?.visibility !== 'hidden' && style?.display !== 'none';
                            };
                            const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                            const isSearchInput = (el) => {
                                const placeholder = normalize(el?.getAttribute?.('placeholder'));
                                const aria = normalize(el?.getAttribute?.('aria-label'));
                                return placeholder.includes('symbol')
                                    || placeholder.includes('isin')
                                    || placeholder.includes('cusip')
                                    || aria.includes('symbol');
                            };
                            return Array.from(document.querySelectorAll('input'))
                                .some((el) => visible(el) && isSearchInput(el));
                        })()
                        """
                    )
                )
            except Exception:
                return False

        try:
            click_target = await self.page.evaluate(
                    """
                    (currentSymbol) => {
                        const visible = (el) => {
                            const rect = el?.getBoundingClientRect?.();
                            const style = el ? window.getComputedStyle(el) : null;
                            return !!rect && rect.width > 0 && rect.height > 0 &&
                                style?.visibility !== 'hidden' && style?.display !== 'none';
                        };
                        const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                        const isSearchInput = (el) => {
                            const placeholder = normalize(el?.getAttribute?.('placeholder'));
                            const aria = normalize(el?.getAttribute?.('aria-label'));
                            return placeholder.includes('symbol')
                                || placeholder.includes('isin')
                                || placeholder.includes('cusip')
                                || aria.includes('symbol');
                        };
                        const hasSearch = () => {
                            return Array.from(document.querySelectorAll('input'))
                                .some((el) => visible(el) && isSearchInput(el));
                        };
                        if (hasSearch()) return { opened: true };

                        const wanted = normalize(currentSymbol);
                        const candidates = Array.from(document.querySelectorAll('button, [role="button"], [data-name], span, div'))
                            .filter((el) => visible(el))
                            .map((el) => {
                                const rect = el.getBoundingClientRect();
                                return {
                                    el,
                                    rect,
                                    text: normalize(el.textContent),
                                    aria: normalize(el.getAttribute('aria-label')),
                                    title: normalize(el.getAttribute('title')),
                                    dataName: normalize(el.getAttribute('data-name')),
                                };
                            })
                            .filter((item) => item.rect.y < 180 && item.rect.x < 520)
                            .sort((a, b) => a.rect.y - b.rect.y || a.rect.x - b.rect.x);

                        const target = candidates.find((item) =>
                            item.aria.includes('change symbol')
                            || item.title.includes('change symbol')
                        ) || candidates.find((item) =>
                            item.aria.includes('symbol search')
                            || item.title.includes('symbol search')
                            || item.text === wanted
                            || item.dataName.includes('legend-series-item')
                        );
                        if (!target) return null;
                        target.el.click();
                        return {
                            clicked: true,
                            x: target.rect.x + target.rect.width / 2,
                            y: target.rect.y + target.rect.height / 2,
                        };
                    }
                    """,
                    current_symbol,
            )
        except Exception:
            click_target = None

        if await dialog_open():
            return True

        if click_target:
            for _ in range(6):
                await asyncio.sleep(0.2)
                if await dialog_open():
                    return True

            if isinstance(click_target, dict) and "x" in click_target and "y" in click_target:
                try:
                    await self.page.mouse.click(float(click_target["x"]), float(click_target["y"]))
                except Exception:
                    return False

                for _ in range(8):
                    await asyncio.sleep(0.25)
                    if await dialog_open():
                        return True
            print(f"    Search dialog opener clicked for {current_symbol}, but no dialog became visible")
        else:
            print(f"    Search dialog opener not found for {current_symbol}")

        try:
            await self.page.keyboard.type(current_symbol)
            for _ in range(10):
                await asyncio.sleep(0.2)
                if await dialog_open():
                    print(f"    Search dialog opened via keyboard fallback for {current_symbol}")
                    return True
        except Exception:
            pass

        return False

    async def _current_symbol_search_query(self) -> str:
        """Return the visible TradingView symbol search query when the dialog is open."""
        try:
            return str(
                await self.page.evaluate(
                    """
                    /* symbol-search-query-read */
                    (() => {
                        const visible = (el) => {
                            const rect = el?.getBoundingClientRect?.();
                            const style = el ? window.getComputedStyle(el) : null;
                            return !!rect && rect.width > 0 && rect.height > 0 &&
                                style?.visibility !== 'hidden' && style?.display !== 'none';
                        };
                        const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                        const isSearchInput = (el) => {
                            const placeholder = normalize(el?.getAttribute?.('placeholder'));
                            const aria = normalize(el?.getAttribute?.('aria-label'));
                            return placeholder.includes('symbol')
                                || placeholder.includes('isin')
                                || placeholder.includes('cusip')
                                || aria.includes('symbol');
                        };
                        const input = Array.from(document.querySelectorAll('input'))
                            .find((el) => visible(el) && isSearchInput(el));
                        return (input?.value || '').trim().toUpperCase();
                    })()
                    """
                )
                or ""
            ).strip().upper()
        except Exception:
            return ""

    async def _set_symbol_search_query(self, target_symbol: str) -> bool:
        """Force the TradingView symbol search box to the bare target symbol."""
        desired = str(target_symbol or "").upper().strip()
        if not desired:
            return False

        if await self._current_symbol_search_query() == desired:
            return True

        try:
            focused = bool(
                await self.page.evaluate(
                    """
                    /* symbol-search-query-focus */
                    (() => {
                        const visible = (el) => {
                            const rect = el?.getBoundingClientRect?.();
                            const style = el ? window.getComputedStyle(el) : null;
                            return !!rect && rect.width > 0 && rect.height > 0 &&
                                style?.visibility !== 'hidden' && style?.display !== 'none';
                        };
                        const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                        const isSearchInput = (el) => {
                            const placeholder = normalize(el?.getAttribute?.('placeholder'));
                            const aria = normalize(el?.getAttribute?.('aria-label'));
                            return placeholder.includes('symbol')
                                || placeholder.includes('isin')
                                || placeholder.includes('cusip')
                                || aria.includes('symbol');
                        };
                        const input = Array.from(document.querySelectorAll('input'))
                            .find((el) => visible(el) && isSearchInput(el));
                        if (!input) return false;
                        input.focus();
                        input.select?.();
                        return true;
                    })()
                    """
                )
            )
            keyboard = getattr(self.page, "keyboard", None)
            if focused and keyboard is not None:
                await keyboard.press("Meta+A")
                await keyboard.press("Backspace")
                await keyboard.type(desired)
                await asyncio.sleep(0.4)
                if await self._current_symbol_search_query() == desired:
                    return True
        except Exception:
            pass

        try:
            return bool(
                await self.page.evaluate(
                    """
                    /* symbol-search-query-set-native */
                    (targetSymbol) => {
                        const visible = (el) => {
                            const rect = el?.getBoundingClientRect?.();
                            const style = el ? window.getComputedStyle(el) : null;
                            return !!rect && rect.width > 0 && rect.height > 0 &&
                                style?.visibility !== 'hidden' && style?.display !== 'none';
                        };
                        const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                        const isSearchInput = (el) => {
                            const placeholder = normalize(el?.getAttribute?.('placeholder'));
                            const aria = normalize(el?.getAttribute?.('aria-label'));
                            return placeholder.includes('symbol')
                                || placeholder.includes('isin')
                                || placeholder.includes('cusip')
                                || aria.includes('symbol');
                        };
                        const input = Array.from(document.querySelectorAll('input'))
                            .find((el) => visible(el) && isSearchInput(el));
                        if (!input) return false;
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                        setter?.call(input, targetSymbol);
                        input.dispatchEvent(new InputEvent('input', { bubbles: true, data: targetSymbol, inputType: 'insertText' }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        return (input.value || '').trim().toUpperCase() === targetSymbol.toUpperCase();
                    }
                    """,
                    desired,
                )
            )
        except Exception:
            return False

    async def _select_symbol_via_search(self, target_symbol: str, target_broker: str) -> bool:
        """Use TradingView's symbol search dialog to select a broker-filtered instrument."""
        if not await self._open_symbol_search_dialog(target_symbol):
            return False

        last_state = "not-started"
        for attempt in range(20):
            try:
                await asyncio.sleep(0.4)
                selected = await self.page.evaluate(
                    """
                    (payload) => {
                        const { targetSymbol, targetBroker, targetCategory } = payload;
                        const visible = (el) => {
                            const rect = el?.getBoundingClientRect?.();
                            const style = el ? window.getComputedStyle(el) : null;
                            return !!rect && rect.width > 0 && rect.height > 0 &&
                                style?.visibility !== 'hidden' && style?.display !== 'none';
                        };
                        const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                        const isSearchInput = (el) => {
                            const placeholder = normalize(el?.getAttribute?.('placeholder'));
                            const aria = normalize(el?.getAttribute?.('aria-label'));
                            return placeholder.includes('symbol')
                                || placeholder.includes('isin')
                                || placeholder.includes('cusip')
                                || aria.includes('symbol');
                        };
                        const symbolToken = normalize(targetSymbol);
                        const brokerToken = normalize(targetBroker);
                        const categoryToken = normalize(targetCategory);
                        const isSelected = (el) => {
                            if (!el) return false;
                            const ariaSelected = normalize(el.getAttribute('aria-selected'));
                            const ariaPressed = normalize(el.getAttribute('aria-pressed'));
                            const className = normalize(el.className);
                            return ariaSelected === 'true'
                                || ariaPressed === 'true'
                                || className.includes('selected')
                                || className.includes('active');
                        };
                        const clickTextControl = (token, allowedSelector, { maxY = 380 } = {}) => {
                            const matches = Array.from(document.querySelectorAll(allowedSelector))
                                .filter((el) => visible(el))
                                .map((el) => ({
                                    el,
                                    text: normalize(el.textContent),
                                    aria: normalize(el.getAttribute('aria-label')),
                                    title: normalize(el.getAttribute('title')),
                                    rect: el.getBoundingClientRect(),
                                }))
                                .filter((item) => item.rect.y < maxY)
                                .filter((item) =>
                                    item.text === token
                                    || item.aria === token
                                    || item.title === token
                                )
                                .sort((a, b) => a.rect.y - b.rect.y || a.rect.x - b.rect.x);
                            if (!matches.length) return { found: false, selected: false };
                            const best = matches[0];
                            if (isSelected(best.el)) return { found: true, selected: true };
                            best.el.click();
                            return { found: true, selected: false };
                        };

                        // Step 1: Ensure the search input exists and has the right text
                        const input = Array.from(document.querySelectorAll('input'))
                            .find((el) => visible(el) && isSearchInput(el));
                        if (!input) return { state: 'no-input' };

                        // Step 2: Keep the result category on Forex when that tab exists.
                        const categoryResult = clickTextControl(
                            categoryToken,
                            'button, [role="button"], [role="tab"]',
                            { maxY: 260 },
                        );
                        if (categoryResult.found && !categoryResult.selected) {
                            return { state: 'category-selected' };
                        }

                        // Step 3: Apply the explicit broker filter when TradingView exposes one.
                        const brokerResult = clickTextControl(
                            brokerToken,
                            'button, [role="button"], [role="tab"], [aria-pressed], [aria-selected]',
                            { maxY: 320 },
                        );
                        if (brokerResult.found && !brokerResult.selected) {
                            return { state: 'broker-filtered' };
                        }

                        // Step 4: The caller updates the React-controlled query input with
                        // real keyboard/native events. We only signal when it's needed.
                        if ((input.value || '').trim().toUpperCase() !== targetSymbol.toUpperCase()) {
                            return { state: 'needs-query', currentQuery: (input.value || '').trim().toUpperCase() };
                        }

                        // Step 5: Find the result row that matches both symbol and broker.
                        // TradingView often splits the symbol and broker across sibling cells,
                        // so we search within the dialog, walk up from exact broker hits, and
                        // then click the smallest visible row/container that contains both.
                        const dialogRoot = input.closest('[role="dialog"], [data-name*="dialog"], [class*="dialog"]')
                            || document.body;
                        const searchRect = input.getBoundingClientRect();
                        const inSearchPopupBounds = (el) => {
                            const rect = el.getBoundingClientRect();
                            return rect.top >= searchRect.top - 80
                                && rect.top <= searchRect.top + 1100
                                && rect.left >= searchRect.left - 80
                                && rect.right <= searchRect.right + 320;
                        };
                        const areaOf = (el) => {
                            const rect = el.getBoundingClientRect();
                            return rect.width * rect.height;
                        };
                        const clickableTarget = (el) => {
                            let current = el;
                            while (current && current !== dialogRoot.parentElement) {
                                if (!visible(current)) {
                                    current = current.parentElement;
                                    continue;
                                }
                                const role = normalize(current.getAttribute('role'));
                                const dataName = normalize(current.getAttribute('data-name'));
                                const tag = normalize(current.tagName);
                                if (
                                    role === 'button'
                                    || role === 'option'
                                    || role === 'row'
                                    || tag === 'button'
                                    || tag === 'li'
                                    || tag === 'tr'
                                    || dataName.includes('list-item')
                                    || dataName.includes('item-row')
                                    || dataName.includes('result')
                                ) {
                                    return current;
                                }
                                current = current.parentElement;
                            }
                            return el;
                        };
                        const addCandidate = (list, el, method) => {
                            if (!el || !visible(el)) return;
                            const area = areaOf(el);
                            if (area < 100 || area > 200000) return;
                            list.push({ el, area, method });
                        };

                        const scopedElements = Array.from(document.querySelectorAll(
                            '[data-symbol-full], [role="option"], [role="row"], [class*="itemRow"], [class*="listItem"], tr, li, button, div, span'
                        ))
                            .filter((el) => visible(el) && inSearchPopupBounds(el));
                        const candidates = [];

                        const brokerHits = scopedElements.filter((el) => {
                            const text = normalize(el.textContent);
                            const aria = normalize(el.getAttribute('aria-label'));
                            const title = normalize(el.getAttribute('title'));
                            return text === brokerToken || aria === brokerToken || title === brokerToken;
                        });

                        for (const brokerHit of brokerHits) {
                            let current = brokerHit;
                            for (let depth = 0; current && depth < 8; depth += 1) {
                                const text = normalize(current.textContent);
                                if (text.includes(symbolToken) && text.includes(brokerToken)) {
                                    addCandidate(candidates, current, 'broker-ancestor');
                                }
                                if (current === dialogRoot) break;
                                current = current.parentElement;
                            }

                            const parent = brokerHit.parentElement;
                            if (parent && visible(parent)) {
                                const siblingText = normalize(
                                    Array.from(parent.children)
                                        .map((child) => child.textContent || '')
                                        .join(' ')
                                );
                                if (siblingText.includes(symbolToken) && siblingText.includes(brokerToken)) {
                                    addCandidate(candidates, parent, 'broker-siblings');
                                }
                            }
                        }

                        if (!candidates.length) {
                            const exactRows = scopedElements
                                .map((el) => ({ el, text: normalize(el.textContent), area: areaOf(el) }))
                                .filter((item) => item.text.includes(symbolToken) && item.text.includes(brokerToken));
                            exactRows.forEach((item) => addCandidate(candidates, item.el, 'exact-row'));
                        }

                        if (!candidates.length) return { state: 'no-match' };

                        candidates.sort((a, b) => a.area - b.area);
                        const best = candidates[0];
                        clickableTarget(best.el).click();
                        return { state: 'selected', method: best.method };
                    }
                    """,
                    {
                        "targetSymbol": target_symbol,
                        "targetBroker": target_broker,
                        "targetCategory": "Forex",
                    },
                )
            except Exception:
                selected = None

            if isinstance(selected, dict) and selected.get("state") == "selected":
                print(f"    Search dialog: selected {target_broker}:{target_symbol} ({selected.get('method', '?')})")
                return True
            if isinstance(selected, dict):
                state = str(selected.get("state", "unknown"))
                if state == "needs-query":
                    if await self._set_symbol_search_query(target_symbol):
                        last_state = "typed"
                    else:
                        last_state = "query-update-failed"
                    continue
                last_state = state
            elif selected is not None:
                last_state = str(selected)
        print(f"    Search dialog: last state for {target_broker}:{target_symbol} was {last_state}")
        return False

    async def _verify_symbol_state(self, expected_symbol: str, expected_broker: str = "") -> None:
        """Fail closed unless TradingView shows the requested symbol and broker cleanly."""
        observed_symbol = await self._verify_symbol(expected_symbol)
        expected_broker = str(expected_broker or "").upper().strip()
        if expected_broker:
            observed_broker = await self._current_broker()
            if not observed_broker and await self._chart_header_shows_broker(expected_broker):
                observed_broker = expected_broker
            if observed_broker and not self._broker_matches_expected(observed_broker, expected_broker):
                raise RuntimeError(
                    f"Broker mismatch: expected {expected_broker}, observed {observed_broker or 'UNKNOWN'}"
                )
        if await self._has_symbol_error_badge():
            raise RuntimeError(
                f"TradingView shows an invalid symbol state for {expected_broker + ':' if expected_broker else ''}{observed_symbol}"
            )

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

    async def _has_strategy_surface(self) -> bool:
        """Return True when the S&D strategy legend/menu is visible on the chart."""
        try:
            return bool(
                await self.page.evaluate(
                    """
                    (() => {
                        const visible = (el) => {
                            const rect = el?.getBoundingClientRect?.();
                            const style = el ? window.getComputedStyle(el) : null;
                            return !!rect && rect.width > 0 && rect.height > 0 &&
                                style?.visibility !== 'hidden' && style?.display !== 'none';
                        };
                        const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim();
                        const strategyTitles = ['S&D Algo [Pro]', 'S&D Pro'];
                        return Array.from(document.querySelectorAll('div, span, button, [data-name], [class*="title"]'))
                            .some((el) => visible(el) && strategyTitles.includes(normalize(el.textContent)));
                    })()
                    """
                )
            )
        except Exception:
            return False

    async def _chart_header_shows_broker(self, expected_broker: str) -> bool:
        """Return True when the chart header visibly shows the requested broker token."""
        broker = str(expected_broker or "").upper().strip()
        if not broker:
            return False
        try:
            return bool(
                await self.page.evaluate(
                    """
                    (expectedBroker) => {
                        const visible = (el) => {
                            const rect = el?.getBoundingClientRect?.();
                            const style = el ? window.getComputedStyle(el) : null;
                            return !!rect && rect.width > 0 && rect.height > 0 &&
                                style?.visibility !== 'hidden' && style?.display !== 'none';
                        };
                        const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim().toUpperCase();
                        const token = normalize(expectedBroker);
                        return Array.from(document.querySelectorAll('div, span, button, [aria-label], [title]'))
                            .filter((el) => visible(el))
                            .filter((el) => {
                                const rect = el.getBoundingClientRect();
                                return rect.y < 220 && rect.x < 900;
                            })
                            .some((el) => {
                                const text = normalize(el.textContent);
                                const aria = normalize(el.getAttribute('aria-label'));
                                const title = normalize(el.getAttribute('title'));
                                return text === token || aria === token || title === token;
                            });
                    }
                    """,
                    broker,
                )
            )
        except Exception:
            return False

    async def _wait_for_strategy_surface(self, timeout: float = 20.0) -> bool:
        """Wait for the strategy legend to reappear after symbol changes."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if await self._has_strategy_surface():
                return True
            await asyncio.sleep(0.5)
        return False

    async def _current_timeframe(self) -> str:
        """Return the current chart timeframe token when available."""
        if hasattr(self.page, "tab_id"):
            try:
                resolution = await self.page.evaluate(
                    """
                    (() => {
                        try {
                            return window.TradingViewApi?._activeChartWidgetWV?.value()?.resolution?.() || '';
                        } catch (error) {
                            return '';
                        }
                    })()
                    """
                )
                return str(resolution or "").strip()
            except Exception:
                pass
        return ""


    # ─────────────────────────────────── navigation ──────────────────────────

    # Brokers whose symbols can't be loaded via URL (?symbol=BROKER:PAIR) and
    # must be selected through the TradingView search dialog instead.
    _SEARCH_DIALOG_BROKERS = {"FXCM"}

    async def _switch_symbol(self, symbol: str) -> None:
        """Switch chart to a different symbol using URL-based or search-dialog navigation."""
        clean_symbol = symbol.split(":")[-1].upper().strip()
        broker = getattr(self.optimizer, "broker", "vantage").upper()
        tv_exchange = broker_to_tv_exchange(broker)
        tv_symbol_prefix = broker_to_tv_symbol_prefix(broker)
        use_search = broker in self._SEARCH_DIALOG_BROKERS

        # Already on this symbol?
        try:
            title_broker, title_symbol = await self._current_symbol_details()
            observed_broker = title_broker
            if not observed_broker and await self._chart_header_shows_broker(tv_exchange):
                observed_broker = tv_exchange
            if title_symbol == clean_symbol and self._broker_matches_expected(observed_broker, tv_exchange):
                print(f"  Already on {clean_symbol}, skipping switch")
                await self._wait_for_load()
                return
        except Exception:
            pass

        print(f"  Navigating to {tv_symbol_prefix}:{clean_symbol}...")

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

        if hasattr(self.page, "_client"):
            try:
                result = await self.page._client.run("symbol", f"{tv_symbol_prefix}:{clean_symbol}")
                if not result.get("success", True):
                    raise RuntimeError(str(result.get("error") or "symbol command failed"))
                await asyncio.sleep(2.0)
                await self._wait_for_load()
                await self._wait_for_strategy_surface()
                try:
                    await self._verify_symbol_state(clean_symbol, tv_exchange)
                    print(f"  Switched to {tv_symbol_prefix}:{clean_symbol} (verified)")
                    if not await self._ensure_chart_timeframe_5m():
                        raise RuntimeError("Could not confirm chart timeframe is 5m")
                    return
                except Exception as verify_error:
                    observed = await self._current_symbol()
                    log.warning(
                        "_switch_symbol: MCP symbol command did not land on %s (observed=%s, reason=%s), falling back to %s navigation",
                        clean_symbol,
                        observed or "UNKNOWN",
                        verify_error,
                        "search" if use_search else "URL",
                    )
            except Exception as e:
                log.warning("_switch_symbol: MCP symbol command failed, falling back to %s navigation: %s", "search" if use_search else "URL", e)

        # ── Search-dialog fallback path (FXCM) ───────────────────────────────
        if use_search:
            if not await self._select_symbol_via_search(clean_symbol, tv_exchange):
                raise RuntimeError(f"{tv_exchange} symbol search could not find {clean_symbol}")
            await asyncio.sleep(2.0)
            await self._wait_for_load()
            await self._wait_for_strategy_surface()
            await self._verify_symbol_state(clean_symbol, tv_exchange)
            print(f"  Switched to {tv_symbol_prefix}:{clean_symbol} (verified)")
            if not await self._ensure_chart_timeframe_5m():
                raise RuntimeError("Could not confirm chart timeframe is 5m")
            return

        # ── URL fallback path (Vantage, OANDA, etc.) ─────────────────────────
        target_url = (
            f"https://www.tradingview.com/chart/{chart_id}/"
            f"?symbol={tv_symbol_prefix}%3A{clean_symbol}"
        )

        try:
            await self.page.goto(
                target_url, wait_until="domcontentloaded", timeout=30000
            )
        except Exception as e:
            print(f"  Navigation warning: {e}")

        await asyncio.sleep(3.0)
        await self._wait_for_load()
        await self._wait_for_strategy_surface()

        # Verify and fail closed if TradingView kept the old symbol.
        try:
            await self._verify_symbol_state(clean_symbol, tv_exchange)
            print(f"  Switched to {tv_symbol_prefix}:{clean_symbol} (verified)")
            if not await self._ensure_chart_timeframe_5m():
                raise RuntimeError("Could not confirm chart timeframe is 5m")
        except Exception:
            observed = await self._current_symbol()
            raise RuntimeError(
                f"Symbol switch failed: expected {clean_symbol}, observed {observed or 'UNKNOWN'}"
            )

    async def _ensure_chart_timeframe_5m(self) -> bool:
        """Set and verify the optimizer's expected 5-minute chart timeframe."""
        if hasattr(self.page, "_client"):
            try:
                result = await self.page._client.run("timeframe", "5")
                if not result.get("success", True):
                    raise RuntimeError(str(result.get("error") or "timeframe command failed"))
                await asyncio.sleep(1.0)
                if await self._current_timeframe() == "5":
                    return True
            except Exception as e:
                log.warning("_ensure_chart_timeframe_5m: MCP timeframe command failed, falling back to UI click: %s", e)

        try:
            clicked = await self.page.evaluate(
                """
                (() => {
                    const visible = (el) => {
                        const rect = el?.getBoundingClientRect?.();
                        const style = el ? window.getComputedStyle(el) : null;
                        return !!rect && rect.width > 0 && rect.height > 0 &&
                            style?.visibility !== 'hidden' && style?.display !== 'none';
                    };

                    const candidates = Array.from(document.querySelectorAll('button, [role="button"], [role="tab"]'))
                        .map((el) => {
                            const text = (el.textContent || '').trim();
                            const title = (el.getAttribute('title') || '').trim();
                            const aria = (el.getAttribute('aria-label') || '').trim();
                            const rect = el.getBoundingClientRect();
                            return { el, text, title, aria, rect };
                        })
                        .filter((item) => visible(item.el))
                        .filter((item) => item.text === '5m' || item.text === '5')
                        .sort((a, b) => {
                            const aPreferred = (a.title === 'Change interval' || a.aria.includes('interval')) ? 0 : 1;
                            const bPreferred = (b.title === 'Change interval' || b.aria.includes('interval')) ? 0 : 1;
                            if (aPreferred !== bPreferred) return aPreferred - bPreferred;
                            return a.rect.y - b.rect.y || a.rect.x - b.rect.x;
                        });

                    if (!candidates.length) return false;
                    candidates[0].el.click();
                    return true;
                })()
                """
            )
            if clicked:
                await asyncio.sleep(1.0)
        except Exception:
            pass
        return await self._current_timeframe() == "5"

    async def _prepare_clean_chart(self) -> None:
        """Reduce worker tab noise before opening settings."""
        await self._dismiss_tv_errors()
        try:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.2)
        except Exception:
            pass

        try:
            await self.page.evaluate(
                """
                (() => {
                    const visible = (el) => {
                        const rect = el?.getBoundingClientRect?.();
                        const style = el ? window.getComputedStyle(el) : null;
                        return !!rect && rect.width > 0 && rect.height > 0 &&
                            style?.visibility !== 'hidden' && style?.display !== 'none';
                    };
                    const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim().toLowerCase();

                    for (const btn of document.querySelectorAll('button, [role="button"]')) {
                        if (!visible(btn)) continue;
                        const text = normalize(btn.textContent);
                        const aria = normalize(btn.getAttribute('aria-label'));
                        if (text === 'show indicator legend' || aria === 'show indicator legend') {
                            btn.click();
                            break;
                        }
                    }

                    for (const btn of document.querySelectorAll('button, [role="button"]')) {
                        if (!visible(btn)) continue;
                        const aria = normalize(btn.getAttribute('aria-label'));
                        if (![
                            'alerts',
                            'watchlist, details, and news',
                            'object tree and data window',
                            'chats',
                            'screeners',
                            'pine',
                            'calendars',
                            'community',
                            'notifications',
                            'help center',
                        ].includes(aria)) {
                            continue;
                        }
                        if (btn.getAttribute('aria-pressed') === 'true') {
                            btn.click();
                        }
                    }
                    return true;
                })()
                """
            )
        except Exception:
            pass

    async def _ensure_strategy_tester_open(self) -> None:
        """Ensure the Strategy Tester panel is visible and expanded.

        Tries in order:
          1. Check if the panel is already visible (has date-range button or
             visible metric labels).
          2. Click the bottom Strategy Report / Strategy Tester control.
          3. Fall back to the keyboard shortcut Alt+B.
        """
        try:
            async def panel_is_open() -> bool:
                if await self.page.evaluate(_JS_HAS_STRATEGY_REPORT_METRICS):
                    return True
                return bool(
                    await self.page.evaluate(
                        """
                        (() => !!(document.querySelector('[data-name="report-range-button"]') || document.querySelector('[data-name="report-settings"]')))
                        """
                    )
                )

            already_open = await self.page.evaluate(
                """
                (() => {
                    if (document.querySelector('[data-name="report-range-button"]')
                        || document.querySelector('[data-name="report-settings"]'))
                        return true;
                    return %s;
                })()
                """ % _JS_HAS_STRATEGY_REPORT_METRICS.strip()
            )
            if already_open:
                return

            # Prefer the bottom-most Strategy Report / Strategy Tester opener.
            click_target = await self.page.evaluate(
                """
                (() => {
                    const visible = (el) => {
                        const rect = el?.getBoundingClientRect?.();
                        const style = el ? window.getComputedStyle(el) : null;
                        return !!rect && rect.width > 0 && rect.height > 0 &&
                            style?.visibility !== 'hidden' && style?.display !== 'none';
                    };
                    const buttons = Array.from(document.querySelectorAll('button, [role="button"], [role="tab"]'))
                        .map((el) => {
                            const text = (el.textContent || '').trim().replace(/\\s+/g, ' ');
                            const aria = (el.getAttribute('aria-label') || '').trim();
                            const rect = el.getBoundingClientRect();
                            return { el, text, aria, rect };
                        })
                        .filter((item) => visible(item.el))
                        .filter((item) =>
                            item.text === 'Strategy Tester' ||
                            item.text === 'Strategy Report' ||
                            item.aria === 'Open Strategy Report'
                        )
                        .sort((a, b) => b.rect.y - a.rect.y || a.rect.x - b.rect.x);
                    if (buttons.length) {
                        const target = buttons[0];
                        target.el.click();
                        return {
                            clicked: true,
                            x: target.rect.x + target.rect.width / 2,
                            y: target.rect.y + target.rect.height / 2,
                        };
                    }
                    return null;
                })()
                """
            )
            if click_target:
                for _ in range(10):
                    if await panel_is_open():
                        return
                    await asyncio.sleep(0.5)

                if isinstance(click_target, dict) and "x" in click_target and "y" in click_target:
                    await self.page.mouse.click(float(click_target["x"]), float(click_target["y"]))
                    for _ in range(10):
                        if await panel_is_open():
                            return
                        await asyncio.sleep(0.5)

            # Fallback: Alt+B keyboard shortcut (TradingView default for Strategy Tester)
            await self.page.keyboard.press("Alt+b")
            for _ in range(10):
                if await panel_is_open():
                    return
                await asyncio.sleep(0.5)

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

        preset = _backtest_range_preset(range_label)

        dates = TabWorker._extract_report_date_span(btn_text)
        if len(dates) < 2:
            return False

        start = dates[0]
        end = dates[1]
        delta_days = (end - start).days
        min_days = int(preset["min_days"])
        max_days = preset["max_days"]
        if max_days is None:
            return delta_days >= min_days
        return min_days <= delta_days <= int(max_days)

    @staticmethod
    def _extract_report_date_span(btn_text: str) -> list[datetime]:
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
            return []

        try:
            return [
                datetime.strptime(dates[0], "%b %d, %Y"),
                datetime.strptime(dates[1], "%b %d, %Y"),
            ]
        except ValueError:
            return []

    @staticmethod
    def _range_matches_custom_dates(
        btn_text: str,
        start_date: str,
        end_date: str,
        *,
        tolerance_days: int = 1,
    ) -> bool:
        """Return True when the Strategy Report span matches a requested custom range."""
        dates = TabWorker._extract_report_date_span(btn_text)
        if len(dates) < 2:
            return False

        try:
            expected_start = datetime.strptime(start_date, "%Y-%m-%d")
            expected_end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return False

        start_delta = abs((dates[0] - expected_start).days)
        end_delta = abs((dates[1] - expected_end).days)
        return start_delta <= tolerance_days and end_delta <= tolerance_days

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

    async def _open_backtest_range_menu(self) -> bool:
        """Open the Strategy Report range menu from its bottom date-span button."""
        target = await self.page.evaluate(
            """
            (() => {
                const buttons = [...document.querySelectorAll('button, [role="button"]')]
                    .map((el) => {
                        const text = (el.textContent || '').trim().replace(/\\s+/g, ' ');
                        const rect = el.getBoundingClientRect();
                        const visible = rect.width > 0 && rect.height > 0;
                        return { text, rect, visible };
                    })
                    .filter((item) => item.visible && item.text.includes('\\u2014'));

                if (!buttons.length) {
                    return null;
                }

                buttons.sort((a, b) => b.rect.y - a.rect.y);
                const target = buttons[0];
                return {
                    x: target.rect.x + target.rect.width / 2,
                    y: target.rect.y + target.rect.height / 2,
                    text: target.text,
                };
            })()
            """
        )
        if not target:
            return False
        await self.page.mouse.click(float(target["x"]), float(target["y"]))
        return True

    async def _fill_custom_date_range_inputs(self, start_date: str, end_date: str) -> dict:
        """Fill TradingView's custom date dialog using DOM events understood by React."""
        return await self.page.evaluate(
            """
            ({ startDate, endDate }) => {
                const setValue = (input, value) => {
                    input.focus();
                    const setter =
                        Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value')?.set ||
                        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
                    if (setter) {
                        setter.call(input, value);
                    } else {
                        input.value = value;
                    }
                    if (input._valueTracker) {
                        input._valueTracker.setValue('');
                    }
                    input.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: value }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    input.blur();
                };

                const inputs = [...document.querySelectorAll('input')]
                    .map((el) => {
                        const rect = el.getBoundingClientRect();
                        return {
                            el,
                            placeholder: el.getAttribute('placeholder') || '',
                            visible: rect.width > 0 && rect.height > 0,
                            y: rect.y,
                        };
                    })
                    .filter((item) => item.visible && item.placeholder === 'YYYY-MM-DD')
                    .sort((a, b) => a.y - b.y);

                if (inputs.length < 2) {
                    return { ok: false, reason: 'date inputs not found', count: inputs.length };
                }

                setValue(inputs[0].el, startDate);
                setValue(inputs[1].el, endDate);
                return {
                    ok: true,
                    values: [inputs[0].el.value, inputs[1].el.value],
                };
            }
            """,
            {"startDate": start_date, "endDate": end_date},
        )

    async def _click_backtest_custom_date_menu_item(self) -> dict:
        """Click the Custom date range menu item using real mouse coordinates."""
        target = await self.page.evaluate(
            """
            (() => {
                const normalize = (value) => (value || '').trim().replace(/\\s+/g, ' ').toLowerCase();
                const items = [...document.querySelectorAll('[role="menuitemcheckbox"], [role="menuitem"]')]
                    .map((el) => {
                        const text = normalize(el.textContent);
                        const aria = normalize(el.getAttribute('aria-label'));
                        const rect = el.getBoundingClientRect();
                        const visible = rect.width > 0 && rect.height > 0;
                        return { text, aria, visible, rect };
                    })
                    .filter((item) => item.visible);

                const target = items.find((item) =>
                    item.aria.includes('custom date range') ||
                    (item.text.includes('custom') && item.text.includes('date') && item.text.includes('range'))
                );
                if (!target) {
                    return {
                        clicked: false,
                        item_count: items.length,
                        items: items.slice(0, 10).map((item) => ({
                            text: item.text,
                            aria: item.aria,
                            x: item.rect.x,
                            y: item.rect.y,
                        })),
                    };
                }

                return {
                    clicked: true,
                    item_count: items.length,
                    x: target.rect.x + target.rect.width / 2,
                    y: target.rect.y + target.rect.height / 2,
                };
            })()
            """
        )
        if isinstance(target, dict) and target.get("clicked"):
            await self.page.mouse.click(float(target["x"]), float(target["y"]))
        return target or {}

    async def _click_custom_date_select_button(self) -> bool:
        """Click the custom date dialog Select button using real mouse coordinates."""
        target = await self.page.evaluate(
            """
            (() => {
                const buttons = [...document.querySelectorAll('button, [role="button"]')]
                    .map((el) => {
                        const text = (el.textContent || '').trim().replace(/\\s+/g, ' ');
                        const rect = el.getBoundingClientRect();
                        const visible = rect.width > 0 && rect.height > 0;
                        return { text, rect, visible };
                    })
                    .filter((item) => item.visible);

                buttons.sort((a, b) => b.rect.y - a.rect.y);
                const target = buttons.find((item) => item.text === 'Select');
                if (!target) {
                    return null;
                }
                return {
                    x: target.rect.x + target.rect.width / 2,
                    y: target.rect.y + target.rect.height / 2,
                };
            })()
            """
        )
        if not target:
            return False
        await self.page.mouse.click(float(target["x"]), float(target["y"]))
        return True

    async def _is_deep_backtesting_active(self) -> bool:
        """Return True when the Strategy Report is running in Deep Backtesting mode."""
        try:
            return bool(
                await self.page.evaluate(
                    """
                    (() => {
                        const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                        const bodyText = normalize(document.body?.innerText || '');
                        if (bodyText.includes('deep backtesting trades only appear in the strategy report')) {
                            return true;
                        }
                        for (const el of document.querySelectorAll('button, [role="button"], [role="tab"]')) {
                            const rect = el.getBoundingClientRect?.();
                            if (!rect || rect.width <= 0 || rect.height <= 0) continue;
                            const title = normalize(el.getAttribute('title'));
                            const aria = normalize(el.getAttribute('aria-label'));
                            const text = normalize(el.textContent);
                            if (`${title} ${aria} ${text}`.includes('deep backtesting')) {
                                return true;
                            }
                        }
                        return false;
                    })()
                    """
                )
            )
        except Exception:
            return False

    async def _read_chart_history_coverage(self, start_date: str, end_date: str) -> ChartHistoryCoverage:
        """Measure how much of the requested date window is present in loaded chart bars."""
        start_ts = _iso_date_to_unix_seconds(start_date)
        end_ts = _iso_date_to_unix_seconds(end_date)
        requested_days = max((end_ts - start_ts) / 86400.0, 1.0)
        raw = await self.page.evaluate(
            """
            (() => {
                const fmt = (ts) => ts ? new Date(ts * 1000).toISOString().slice(0, 10) : '';
                try {
                    const chart = window.TradingViewApi?._activeChartWidgetWV?.value?.();
                    const bars = chart?._chartWidget?.model?.().mainSeries?.().bars?.();
                    if (!bars) {
                        return { ok: false, error: 'chart bars unavailable' };
                    }
                    const firstIndex = bars.firstIndex();
                    const lastIndex = bars.lastIndex();
                    let firstTs = 0;
                    let lastTs = 0;
                    let count = 0;
                    for (let index = firstIndex; index <= lastIndex; index += 1) {
                        const value = bars.valueAt(index);
                        if (!value) continue;
                        const ts = Number(value[0] || 0);
                        if (!ts) continue;
                        count += 1;
                        if (!firstTs) firstTs = ts;
                        lastTs = ts;
                    }
                    return {
                        ok: true,
                        count,
                        first_ts: firstTs,
                        last_ts: lastTs,
                        first_date: fmt(firstTs),
                        last_date: fmt(lastTs),
                    };
                } catch (error) {
                    return { ok: false, error: String(error?.message || error) };
                }
            })()
            """
        )
        if not isinstance(raw, dict) or not raw.get("ok"):
            error = raw.get("error") if isinstance(raw, dict) else raw
            raise RuntimeError(f"INSUFFICIENT_DATA: could not inspect loaded chart history ({error})")

        loaded_first_ts = int(raw.get("first_ts") or 0)
        loaded_last_ts = int(raw.get("last_ts") or 0)
        if loaded_first_ts <= 0 or loaded_last_ts <= 0:
            return ChartHistoryCoverage(
                requested_days=requested_days,
                covered_days=0.0,
                coverage_ratio=0.0,
                loaded_bar_count=int(raw.get("count") or 0),
                loaded_first_ts=loaded_first_ts,
                loaded_last_ts=loaded_last_ts,
                loaded_first_date=str(raw.get("first_date") or ""),
                loaded_last_date=str(raw.get("last_date") or ""),
            )

        overlap_start = max(start_ts, loaded_first_ts)
        overlap_end = min(end_ts, loaded_last_ts)
        covered_days = max((overlap_end - overlap_start) / 86400.0, 0.0)
        return ChartHistoryCoverage(
            requested_days=requested_days,
            covered_days=covered_days,
            coverage_ratio=covered_days / requested_days,
            loaded_bar_count=int(raw.get("count") or 0),
            loaded_first_ts=loaded_first_ts,
            loaded_last_ts=loaded_last_ts,
            loaded_first_date=str(raw.get("first_date") or ""),
            loaded_last_date=str(raw.get("last_date") or ""),
        )

    async def _request_chart_history_range(self, start_date: str, end_date: str) -> dict:
        """Ask TradingView to load bars for a historical time range."""
        start_ms = _iso_date_to_unix_seconds(start_date) * 1000
        end_ms = _iso_date_to_unix_seconds(end_date) * 1000
        return await self.page.evaluate(
            """
            ({ startMs, endMs }) => {
                try {
                    const chart = window.TradingViewApi?._activeChartWidgetWV?.value?.();
                    const widget = chart?._chartWidget;
                    const model = widget?.model?.();
                    const inner = model?.model?.();
                    if (inner && typeof inner.gotoTimeRange === 'function') {
                        inner.gotoTimeRange(startMs, endMs);
                        return { ok: true, method: 'gotoTimeRange' };
                    }
                    const series = model?.mainSeries?.();
                    if (series && typeof series.loadDataTo === 'function') {
                        series.loadDataTo({ type: 'time-range', from: startMs / 1000, to: endMs / 1000 });
                        return { ok: true, method: 'mainSeries.loadDataTo' };
                    }
                    return { ok: false, error: 'no historical range loader available' };
                } catch (error) {
                    return { ok: false, error: String(error?.message || error) };
                }
            }
            """,
            {"startMs": start_ms, "endMs": end_ms},
        )

    async def _ensure_chart_history_for_custom_range(self, start_date: str, end_date: str) -> ChartHistoryCoverage:
        """Fail closed unless loaded chart bars cover the requested custom range."""
        if await self._is_deep_backtesting_active():
            start_ts = _iso_date_to_unix_seconds(start_date)
            end_ts = _iso_date_to_unix_seconds(end_date)
            requested_days = max((end_ts - start_ts) / 86400.0, 1.0)
            log.info(
                "_ensure_chart_history_for_custom_range: Deep Backtesting active; "
                "chart loaded bars are not used as coverage oracle for %s..%s",
                start_date,
                end_date,
            )
            print(
                f"  [deep backtesting ✓ Strategy Report range {start_date} → {end_date}]",
                flush=True,
            )
            return ChartHistoryCoverage(
                requested_days=requested_days,
                covered_days=requested_days,
                coverage_ratio=1.0,
                loaded_bar_count=0,
                loaded_first_ts=start_ts,
                loaded_last_ts=end_ts,
                loaded_first_date=start_date,
                loaded_last_date=end_date,
            )

        last_coverage: ChartHistoryCoverage | None = None
        for attempt in range(1, _HISTORY_LOAD_MAX_ATTEMPTS + 1):
            coverage = await self._read_chart_history_coverage(start_date, end_date)
            last_coverage = coverage
            log.info(
                "_ensure_chart_history_for_custom_range: attempt=%s coverage=%.1f%% "
                "covered=%.1fd/%.1fd bars=%s loaded=%s..%s",
                attempt,
                coverage.coverage_ratio * 100,
                coverage.covered_days,
                coverage.requested_days,
                coverage.loaded_bar_count,
                coverage.loaded_first_date or "?",
                coverage.loaded_last_date or "?",
            )
            if coverage.coverage_ratio >= _HISTORY_COVERAGE_MIN_RATIO:
                print(
                    f"  [chart history ✓ {coverage.covered_days:.0f}/{coverage.requested_days:.0f}d "
                    f"loaded ({coverage.loaded_first_date} → {coverage.loaded_last_date})]",
                    flush=True,
                )
                return coverage

            request_result = await self._request_chart_history_range(start_date, end_date)
            if not isinstance(request_result, dict) or not request_result.get("ok"):
                raise RuntimeError(
                    "INSUFFICIENT_DATA: could not request historical chart bars "
                    f"for {start_date} to {end_date}: {request_result}"
                )
            await asyncio.sleep(_HISTORY_LOAD_SLEEP)

        coverage = last_coverage or await self._read_chart_history_coverage(start_date, end_date)
        raise RuntimeError(
            "INSUFFICIENT_DATA: only loaded "
            f"{coverage.covered_days:.1f} days of {coverage.requested_days:.1f} requested "
            f"({coverage.coverage_ratio:.0%}); loaded bars={coverage.loaded_bar_count} "
            f"range={coverage.loaded_first_date or '?'}..{coverage.loaded_last_date or '?'}"
        )

    async def _select_backtest_custom_date_range(self, start_date: str, end_date: str) -> bool:
        """Set the Strategy Report custom date range using TradingView's range dialog."""
        try:
            if hasattr(self.page, "keyboard"):
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.2)
        except Exception:
            pass

        if not await self._open_backtest_range_menu():
            log.warning("_select_backtest_custom_date_range: Strategy Report range button not found")
            return False

        await asyncio.sleep(0.4)

        chosen = await self._click_backtest_custom_date_menu_item()
        if not isinstance(chosen, dict) or not chosen.get("clicked"):
            log.warning("_select_backtest_custom_date_range: custom menu item not found/opened: %s", chosen)
            return False

        await asyncio.sleep(0.6)

        fill_result = await self._fill_custom_date_range_inputs(start_date, end_date)
        if not isinstance(fill_result, dict) or not fill_result.get("ok"):
            log.warning("_select_backtest_custom_date_range: could not fill date inputs: %s", fill_result)
            return False

        values = fill_result.get("values") or []
        if values != [start_date, end_date]:
            log.warning(
                "_select_backtest_custom_date_range: date dialog values did not stick "
                "(requested=%s..%s actual=%s)",
                start_date,
                end_date,
                values,
            )
            return False

        return await self._click_custom_date_select_button()

    async def _select_chart_date_range_tab(self, range_label: str) -> bool:
        """Fallback: click the chart-level bottom date-range shortcut."""
        target_name = str(_backtest_range_preset(range_label)["chart_tab"])
        if not target_name:
            return False

        try:
            return bool(
                await self.page.evaluate(
                    """
                    (targetName) => {
                        const button = document.querySelector(`[data-name="${targetName}"]`);
                        if (!button || button.offsetParent === null) {
                            return false;
                        }
                        button.click();
                        return true;
                    }
                    """,
                    target_name,
                )
            )
        except Exception:
            return False

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
            preset = _backtest_range_preset(range_label)
            preset_label = str(preset["label"])
            preset_summary = str(preset["summary"])
            await self._ensure_strategy_tester_open()
            btn_text = await self._read_backtest_range_button_text()

            if self._range_matches_label(btn_text, preset_label):
                if btn_text:
                    print(
                        f"  [backtest range ✓ already {preset_summary}: {btn_text[:40].strip()}]",
                        flush=True,
                    )
                else:
                    print(f"  [backtest range ✓ already {preset_summary}]", flush=True)
                return True

            selected_via_chart_tab = False
            if not await self._select_backtest_range_preset(preset_label):
                if await self._select_chart_date_range_tab(preset_label):
                    selected_via_chart_tab = True
                else:
                    log.warning(
                        "_set_backtest_range: could not open preset menu for '%s' "
                        "(button text='%s')",
                        preset_label,
                        btn_text[:60] if btn_text else "(not found)",
                    )
                    return False

            await asyncio.sleep(0.4)
            await self._wait_for_update_complete()
            await self._wait_for_load()

            updated_text = await self._read_backtest_range_button_text()
            if self._range_matches_label(updated_text, preset_label):
                if updated_text:
                    print(
                        f"  [backtest range ✓ set to {preset_summary}: {updated_text[:40].strip()}]",
                        flush=True,
                    )
                else:
                    print(f"  [backtest range ✓ set to {preset_summary}]", flush=True)
                return True

            log.warning(
                "_set_backtest_range: attempted '%s' but final button text was '%s'",
                preset_label,
                updated_text[:60] if updated_text else "(not found)",
            )
            return False

        except Exception as e:
            log.warning("_set_backtest_range: %s", e)
            return False





    async def _set_custom_date_range(self, start_date: str, end_date: str) -> bool:
        """Set and verify the Strategy Report custom date range."""
        try:
            await self._ensure_strategy_tester_open()

            btn_text = await self._read_backtest_range_button_text()
            if self._range_matches_custom_dates(btn_text, start_date, end_date):
                await self._ensure_chart_history_for_custom_range(start_date, end_date)
                print(f"  [backtest range ✓ already custom {start_date} → {end_date}]", flush=True)
                return True

            log.info(
                "_set_custom_date_range: requesting Strategy Report custom range start=%s end=%s "
                "current_button_text=%s",
                start_date,
                end_date,
                btn_text[:80] if btn_text else "(not found)",
            )

            if not await self._select_backtest_custom_date_range(start_date, end_date):
                return False

            await asyncio.sleep(0.5)
            await self._wait_for_update_complete()
            await self._wait_for_load()

            updated_text = await self._read_backtest_range_button_text()
            log.info(
                "_set_custom_date_range: Strategy Report range after selection=%s",
                updated_text[:120] if updated_text else "(not found)",
            )

            if not self._range_matches_custom_dates(updated_text, start_date, end_date):
                log.warning(
                    "_set_custom_date_range: requested custom range %s..%s but Strategy Report shows '%s'",
                    start_date,
                    end_date,
                    updated_text[:120] if updated_text else "(not found)",
                )
                return False

            await self._ensure_chart_history_for_custom_range(start_date, end_date)
            print(f"  [backtest range ✓ custom {start_date} → {end_date}]", flush=True)
            return True
        except NoDataForRangeError:
            raise
        except Exception as e:
            if str(e).startswith("INSUFFICIENT_DATA:"):
                raise
            log.warning("_set_custom_date_range: %s", e)
            return False

    async def _require_custom_date_range(self, start_date: str, end_date: str) -> None:
        if not await self._set_custom_date_range(start_date, end_date):
            raise RuntimeError(f"Could not confirm custom backtest range {start_date} to {end_date}")

    async def _require_backtest_range(self, range_label: str) -> None:
        """Fail closed unless the strategy tester range is confirmed to match the requested preset."""
        preset_label = backtest_range_to_label(range_label)
        if normalize_backtest_range(range_label) == "custom":
            raise RuntimeError("custom backtest range requires explicit start/end dates")
        if not await self._set_backtest_range(preset_label):
            raise RuntimeError(f"Could not confirm backtest range is {preset_label}")

    async def _require_last_365_days(self) -> None:
        """Backward-compatible wrapper for the historical 1-year validation path."""
        await self._require_backtest_range("Last 365 days")

    async def _wait_for_load(self, timeout: int = 30) -> None:
        """Wait for chart and strategy tester to finish loading."""
        await asyncio.sleep(1.0)
        start = time.time()
        timeout_recovery_attempted = False
        while time.time() - start < timeout:
            try:
                loading = await self._check_loading_text()
                timed_out = await self._check_timeout_banner()
                if timed_out:
                    if not timeout_recovery_attempted:
                        timeout_recovery_attempted = True
                        await self._recover_strategy_report_timeout()
                        await asyncio.sleep(1.0)
                        continue
                    raise RuntimeError("Strategy report timed out loading")
                if not loading:
                    await asyncio.sleep(0.5)
                    return
            except RuntimeError:
                raise
            except Exception:
                pass
            await asyncio.sleep(0.5)

        if await self._check_timeout_banner():
            raise RuntimeError("Strategy report timed out loading")

    # ─────────────────────────────────── update cycle detection ──────────────

    async def _check_loading_text(self) -> Optional[str]:
        """Return the loading indicator text if visible, else None."""
        try:
            return await self.page.evaluate(
                _JS_FIND_LOADING, _LOADING_INDICATORS
            )
        except Exception:
            return None

    async def _check_timeout_banner(self) -> bool:
        """Return True when Strategy Report shows TradingView's timeout banner."""
        try:
            return bool(await self.page.evaluate(_JS_HAS_REPORT_TIMEOUT, _REPORT_TIMEOUT_TEXT))
        except Exception:
            return False

    async def _read_results_fingerprint_raw(self) -> str:
        """Read the raw Strategy Report fingerprint without triggering refresh logic."""
        try:
            fingerprint: str = await self.page.evaluate(_JS_RESULTS_FINGERPRINT)
            return fingerprint or ""
        except Exception:
            return ""

    async def _recover_strategy_report_timeout(self) -> None:
        """Try to recover when Strategy Report times out."""
        log.warning("_wait_for_load: detected Strategy Report timeout banner — trying recovery")
        try:
            await self.page.keyboard.press("Escape")
        except Exception:
            pass
        try:
            await self.page.evaluate(_JS_CLICK_UPDATE_REPORT)
        except Exception:
            pass

    async def _wait_for_results_stable(self) -> bool:
        """
        Require a short stable-idle window after recalculation.

        TradingView can briefly hide the loading spinner before the Strategy
        Report has actually finished repainting. We only accept completion once
        the report fingerprint is identical across several consecutive idle
        polls.
        """
        deadline = time.time() + _UPDATE_SETTLE_TIMEOUT
        last_fingerprint = ""
        stable_polls = 0

        while time.time() < deadline:
            if await self._check_loading_text():
                last_fingerprint = ""
                stable_polls = 0
                await asyncio.sleep(_UPDATE_SETTLE_SLEEP)
                continue

            fingerprint = await self._read_results_fingerprint_raw()
            if not fingerprint:
                last_fingerprint = ""
                stable_polls = 0
                await asyncio.sleep(_UPDATE_SETTLE_SLEEP)
                continue

            if fingerprint == last_fingerprint:
                stable_polls += 1
            else:
                last_fingerprint = fingerprint
                stable_polls = 1

            if stable_polls >= _UPDATE_SETTLE_POLLS:
                return True

            await asyncio.sleep(_UPDATE_SETTLE_SLEEP)

        log.warning(
            "_wait_for_results_stable: timed out after %ds waiting for stable Strategy Report",
            _UPDATE_SETTLE_TIMEOUT,
        )
        return False

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
        await self._raise_if_tradingview_crashed()

        # Phase 1 — wait for loading to appear
        appeared = False
        deadline = time.time() + _UPDATE_APPEAR_TIMEOUT
        while time.time() < deadline:
            await self._raise_if_tradingview_crashed()
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
                # Still nothing: require a stable report before continuing.
                return await self._wait_for_results_stable()

        # Phase 2 — wait for loading to disappear
        deadline = time.time() + _UPDATE_FINISH_TIMEOUT

        while time.time() < deadline:
            await self._raise_if_tradingview_crashed()
            if not await self._check_loading_text():
                return await self._wait_for_results_stable()
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
                return await self._wait_for_results_stable()
        except Exception:
            pass
        return False

    # ─────────────────────────────────── results fingerprint ─────────────────

    async def _raise_if_tradingview_crashed(self) -> None:
        """Fail fast when TradingView Desktop shows its Electron crash dialog."""
        try:
            crashed = await self.page.evaluate(
                """
                (() => {
                    const text = document.body?.innerText || '';
                    return (
                        text.includes('App has crashed due to unexpected error') ||
                        text.includes('needs to be restarted') && text.includes('write EIO')
                    );
                })()
                """
            )
        except Exception as exc:
            raise RuntimeError(f"TradingView page is not reachable: {exc}") from exc

        if crashed:
            raise RuntimeError(
                "TradingView Desktop crashed (Electron write EIO). "
                "Restart TradingView and resume the remaining pairs."
            )

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
            fingerprint = await self._read_results_fingerprint_raw()
            return hashlib.md5(fingerprint.encode()).hexdigest()[:8]
        except Exception:
            return ""

    # ─────────────────────────────────── dialog helpers ──────────────────────

    async def _open_settings(self) -> bool:
        """Open strategy settings dialog on this tab's page."""
        if await self._has_ready_settings_dialog():
            return True

        await self._dismiss_wrong_settings_dialog()

        # On TradingView Desktop, the indicator legend often already exposes a
        # visible settings gear near the strategy title. Prefer that
        # direct path before opening other menus, because it is the most
        # stable UI surface in the desktop shell.
        try:
            opened_direct_legend_settings = await self.page.evaluate(
                """
                (() => {
                    const visible = (el) => {
                        const rect = el?.getBoundingClientRect?.();
                        const style = el ? window.getComputedStyle(el) : null;
                        return !!rect && rect.width > 0 && rect.height > 0 &&
                            style?.visibility !== 'hidden' && style?.display !== 'none';
                    };

                    const center = (rect) => ({
                        x: rect.x + rect.width / 2,
                        y: rect.y + rect.height / 2,
                    });

                    const distance = (a, b) => {
                        const dx = a.x - b.x;
                        const dy = a.y - b.y;
                        return Math.sqrt(dx * dx + dy * dy);
                    };

                    const strategyTitles = ['S&D Algo [Pro]', 'S&D Pro'];
                    const titles = Array.from(
                        document.querySelectorAll('div, span, button, [data-name], [class*="title"]')
                    ).filter((el) =>
                        visible(el) &&
                        strategyTitles.includes((el.textContent || '').replace(/\\s+/g, ' ').trim())
                    );

                    if (!titles.length) return false;

                    const settingsButtons = Array.from(
                        document.querySelectorAll('button, [role="button"], [title], [aria-label]')
                    ).filter((el) => {
                        if (!visible(el)) return false;
                        const text = (el.textContent || '').replace(/\\s+/g, ' ').trim();
                        const title = (el.getAttribute('title') || '').trim();
                        const aria = (el.getAttribute('aria-label') || '').trim();
                        return text === 'Settings' || title === 'Settings' || aria === 'Settings';
                    });

                    if (!settingsButtons.length) return false;

                    let bestButton = null;
                    let bestDistance = Number.POSITIVE_INFINITY;
                    for (const titleEl of titles) {
                        const titleRect = titleEl.getBoundingClientRect();
                        const titleCenter = center(titleRect);
                        for (const btn of settingsButtons) {
                            const btnRect = btn.getBoundingClientRect();
                            const d = distance(titleCenter, center(btnRect));
                            if (d < bestDistance) {
                                bestDistance = d;
                                bestButton = btn;
                            }
                        }
                    }

                    if (!bestButton) return false;
                    bestButton.click();
                    return true;
                })()
                """
            )
            if opened_direct_legend_settings:
                await asyncio.sleep(1.2)
                if await self._has_ready_settings_dialog():
                    return True
                await self._dismiss_wrong_settings_dialog()
            else:
                try:
                    await self.page.keyboard.press("Escape")
                    await asyncio.sleep(0.2)
                except Exception:
                    pass
        except Exception:
            pass

        # TradingView Desktop reliably exposes the bottom Strategy Report
        # strategy menu as "<strategy title> · Deep Backtesting" -> "Settings…".
        # Prefer that deterministic flow before falling back to chart-legend
        # coordinate clicks, which are less stable in the Desktop shell.
        try:
            opened_strategy_menu = await self.page.evaluate(
                """
                (() => {
                    const visible = (el) => {
                        const rect = el?.getBoundingClientRect?.();
                        const style = el ? window.getComputedStyle(el) : null;
                        return !!rect && rect.width > 0 && rect.height > 0 &&
                            style?.visibility !== 'hidden' && style?.display !== 'none';
                    };

                    const strategyTitles = ['S&D Algo [Pro]', 'S&D Pro'];
                    const strategyButton = Array.from(document.querySelectorAll('button'))
                        .find((btn) =>
                            visible(btn) &&
                            strategyTitles.some((title) =>
                                (btn.getAttribute('title') || '').includes(title) ||
                                (btn.textContent || '').includes(title)
                            )
                        );
                    if (!strategyButton) return false;
                    strategyButton.click();
                    return true;
                })()
                """
            )
            if opened_strategy_menu:
                await asyncio.sleep(0.5)
                opened_from_menu = await self.page.evaluate(
                    """
                    (() => {
                        const visible = (el) => {
                            const rect = el?.getBoundingClientRect?.();
                            const style = el ? window.getComputedStyle(el) : null;
                            return !!rect && rect.width > 0 && rect.height > 0 &&
                                style?.visibility !== 'hidden' && style?.display !== 'none';
                        };

                        const selectors = [
                            'button', '[role="menuitem"]', '[role="option"]',
                            '[class*="item"]', '[class*="button"]'
                        ];
                        for (const sel of selectors) {
                            for (const el of document.querySelectorAll(sel)) {
                                if (!visible(el)) continue;
                                const text = (el.textContent || '').replace(/\\s+/g, ' ').trim();
                                if (
                                    text === 'Settings…' ||
                                    text === 'Settings...' ||
                                    text.startsWith('Settings…') ||
                                    text.startsWith('Settings...')
                                ) {
                                    el.click();
                                    return true;
                                }
                            }
                        }
                        return false;
                    })()
                    """
                )
            else:
                opened_from_menu = False

            if opened_from_menu:
                await asyncio.sleep(1.2)
                if await self._has_ready_settings_dialog():
                    return True
                await self._dismiss_wrong_settings_dialog()
            else:
                try:
                    await self.page.keyboard.press("Escape")
                    await asyncio.sleep(0.2)
                except Exception:
                    pass
        except Exception:
            pass

        # Click strategy name to reveal action buttons when possible, then click
        # the nearest visible strategy Settings button using real mouse coords.
        # TradingView's React handlers can ignore synthetic JS clicks here.
        snd_coords = await page_query_snd(self.page)
        if snd_coords:
            await self.page.mouse.click(snd_coords["x"], snd_coords["y"])
            await asyncio.sleep(0.4)

        settings_coords = await self.page.evaluate(
            """
            (() => {
                const visible = (el) => {
                    const rect = el?.getBoundingClientRect?.();
                    const style = el ? window.getComputedStyle(el) : null;
                    return !!rect && rect.width > 0 && rect.height > 0 &&
                        style?.visibility !== 'hidden' && style?.display !== 'none';
                };
                const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim();
                const center = (rect) => ({
                    x: rect.x + rect.width / 2,
                    y: rect.y + rect.height / 2,
                });
                const distance = (a, b) => {
                    const dx = a.x - b.x;
                    const dy = a.y - b.y;
                    return Math.sqrt(dx * dx + dy * dy);
                };
                const strategyTitles = ['S&D Algo [Pro]', 'S&D Pro'];
                const titles = Array.from(
                    document.querySelectorAll('div, span, button, [data-name], [class*="title"]')
                ).filter((el) =>
                    visible(el) &&
                    strategyTitles.includes(normalize(el.textContent))
                );
                if (!titles.length) return null;

                const buttons = Array.from(
                    document.querySelectorAll('button, [role="button"], [title], [aria-label]')
                ).filter((el) => {
                    if (!visible(el)) return false;
                    const text = normalize(el.textContent);
                    const title = normalize(el.getAttribute('title'));
                    const aria = normalize(el.getAttribute('aria-label'));
                    return text === 'Settings' || title === 'Settings' || aria === 'Settings';
                });
                if (!buttons.length) return null;

                let bestButton = null;
                let bestDistance = Number.POSITIVE_INFINITY;
                for (const titleEl of titles) {
                    const titleCenter = center(titleEl.getBoundingClientRect());
                    for (const btn of buttons) {
                        const d = distance(titleCenter, center(btn.getBoundingClientRect()));
                        if (d < bestDistance) {
                            bestDistance = d;
                            bestButton = btn;
                        }
                    }
                }
                if (!bestButton) return null;
                const box = bestButton.getBoundingClientRect();
                return {x: box.x + box.width / 2, y: box.y + box.height / 2};
            })()
            """
        )
        if settings_coords:
            await self.page.mouse.click(settings_coords['x'], settings_coords['y'])
            await asyncio.sleep(1.5)
            if await self._has_ready_settings_dialog():
                return True
            await self._dismiss_wrong_settings_dialog()

        if snd_coords:
            await self.page.mouse.click(snd_coords["x"], snd_coords["y"], double=True)
            await asyncio.sleep(1.5)
            if await self._has_ready_settings_dialog():
                return True
            await self._dismiss_wrong_settings_dialog()

        return False

    async def _set_input(self, index: int, value) -> bool:
        """Set input by index using native setters so TradingView observes the change."""
        try:
            return bool(
                await self.page.evaluate(
                    f"""
                    ({{
                        index,
                        value
                    }}) => {{
                        {_JS_SETTINGS_DIALOG_HELPERS}
                        const dialog = __tvPickSettingsDialog(true) || __tvPickSettingsDialog(false);
                        if (!dialog) return false;
                        const inputs = dialog.querySelectorAll('input');
                        if (index >= inputs.length) return false;
                        const input = inputs[index];
                        if (!input || input.type === 'checkbox') return true;
                        const nextValue = String(value);
                        input.scrollIntoView({{ block: 'center' }});
                        input.focus();
                        input.select?.();

                        const proto = Object.getPrototypeOf(input);
                        const descriptor = Object.getOwnPropertyDescriptor(proto, 'value')
                            || Object.getOwnPropertyDescriptor(window.HTMLInputElement?.prototype || {{}}, 'value')
                            || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement?.prototype || {{}}, 'value');
                        if (descriptor?.set) {{
                            descriptor.set.call(input, nextValue);
                        }} else {{
                            input.value = nextValue;
                        }}

                        input.dispatchEvent(new InputEvent('input', {{
                            bubbles: true,
                            data: nextValue,
                            inputType: 'insertReplacementText',
                        }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        input.blur();
                        return String(input.value).trim() === nextValue.trim();
                    }}
                    """,
                    {"index": index, "value": value},
                )
            )
        except Exception:
            return False

    async def _read_input_value(self, index: int) -> str:
        """Read the current visible settings input value by index."""
        try:
            value = await self.page.evaluate(
                f"""
                ((index) => {{
                    {_JS_SETTINGS_DIALOG_HELPERS}
                    const dialog = __tvPickSettingsDialog(true) || __tvPickSettingsDialog(false);
                    if (!dialog) return '';
                    const inputs = dialog.querySelectorAll('input');
                    if (index >= inputs.length) return '';
                    const input = inputs[index];
                    if (!input || input.type === 'checkbox') return '';
                    return String(input.value || '').trim();
                }})
                """,
                index,
            )
            return str(value or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _setting_titles_for_param(name: str, value) -> tuple[str, ...]:
        if name == "rr_mode":
            titles = ["use_custom_rr"]
            if str(value) != "dynamic":
                titles.append("risk_reward_ratio")
            return tuple(titles)
        return (name,)

    def _setting_titles_for_params(self, params: dict) -> list[str]:
        titles: list[str] = []
        for name, value in params.items():
            titles.extend(self._setting_titles_for_param(name, value))
        return titles

    async def _missing_setting_titles(self, titles: list[str]) -> list[str]:
        """Return canonical Pine input titles that are not visible in the dialog."""
        return list(
            await self.page.evaluate(
                f"""
                ((titles) => {{
                    {_JS_SETTINGS_DIALOG_HELPERS}
                    {_JS_INPUT_BY_TITLE_HELPERS}
                    const dialog = __tvPickSettingsDialog(true) || __tvPickSettingsDialog(false);
                    if (!dialog) return titles;
                    return titles.filter((title) => !__tvFindInputByTitle(dialog, title));
                }})
                """,
                titles,
            )
            or []
        )

    async def _available_setting_titles(self) -> list[str]:
        """Best-effort list of visible canonical Pine input titles for diagnostics."""
        try:
            return list(
                await self.page.evaluate(
                    f"""
                    (() => {{
                        {_JS_SETTINGS_DIALOG_HELPERS}
                        {_JS_INPUT_BY_TITLE_HELPERS}
                        const dialog = __tvPickSettingsDialog(true) || __tvPickSettingsDialog(false);
                        if (!dialog) return [];
                        return __tvAvailableInputTitles(dialog);
                    }})()
                    """
                )
                or []
            )
        except Exception:
            return []

    async def _validate_setting_titles(self, params: dict) -> None:
        missing = await self._missing_setting_titles(self._setting_titles_for_params(params))
        if missing:
            available = await self._available_setting_titles()
            raise KeyError(
                "TradingView settings dialog is missing Pine input title(s): "
                f"{', '.join(missing)}. Available canonical titles: {available}"
            )

    async def _read_input_value_by_title(self, title: str) -> str:
        try:
            value = await self.page.evaluate(
                f"""
                ((title) => {{
                    {_JS_SETTINGS_DIALOG_HELPERS}
                    {_JS_INPUT_BY_TITLE_HELPERS}
                    const dialog = __tvPickSettingsDialog(true) || __tvPickSettingsDialog(false);
                    if (!dialog) return '';
                    const input = __tvFindInputByTitle(dialog, title);
                    if (!input || input.type === 'checkbox') return '';
                    if (input.getAttribute?.('role') === 'combobox') return __tvNormalize(input.textContent || '');
                    return String(input.value || '').trim();
                }})
                """,
                title,
            )
            return str(value or "").strip()
        except Exception:
            return ""

    async def _set_input_by_title(self, title: str, value) -> bool:
        result = await self.page.evaluate(
            f"""
            (({{ title, value }}) => {{
                {_JS_SETTINGS_DIALOG_HELPERS}
                {_JS_INPUT_BY_TITLE_HELPERS}
                const dialog = __tvPickSettingsDialog(true) || __tvPickSettingsDialog(false);
                if (!dialog) return {{ ok: false, oldValue: '', newValue: '', reason: 'missing_dialog' }};
                const input = __tvFindInputByTitle(dialog, title);
                if (!input) return {{ ok: false, oldValue: '', newValue: '', reason: 'missing_input' }};
                if (input.type === 'checkbox') return {{ ok: false, oldValue: String(input.checked), newValue: String(input.checked), reason: 'expected_text_input' }};
                const oldValue = String(input.value || '').trim();
                const nextValue = String(value);
                input.scrollIntoView({{ block: 'center' }});
                input.focus();
                input.select?.();
                const proto = Object.getPrototypeOf(input);
                const descriptor = Object.getOwnPropertyDescriptor(proto, 'value')
                    || Object.getOwnPropertyDescriptor(window.HTMLInputElement?.prototype || {{}}, 'value')
                    || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement?.prototype || {{}}, 'value');
                if (descriptor?.set) {{
                    descriptor.set.call(input, nextValue);
                }} else {{
                    input.value = nextValue;
                }}
                input.dispatchEvent(new InputEvent('input', {{
                    bubbles: true,
                    data: nextValue,
                    inputType: 'insertReplacementText',
                }}));
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                input.blur();
                const newValue = String(input.value || '').trim();
                const expected = nextValue.trim();
                const actualNumber = Number(newValue);
                const expectedNumber = Number(expected);
                const numericMatch = newValue !== '' && expected !== '' &&
                    Number.isFinite(actualNumber) && Number.isFinite(expectedNumber) &&
                    Math.abs(actualNumber - expectedNumber) < 1e-9;
                return {{ ok: newValue === expected || numericMatch, oldValue, newValue, reason: '' }};
            }})
            """,
            {"title": title, "value": value},
        )
        log.debug(
            "_apply_params: %s %s -> %s",
            title,
            (result or {}).get("oldValue"),
            (result or {}).get("newValue"),
        )
        return bool((result or {}).get("ok"))

    async def _set_select_by_title(self, title: str, value: str) -> bool:
        result = await self.page.evaluate(
            f"""
            (({{ title, value }}) => {{
                {_JS_SETTINGS_DIALOG_HELPERS}
                {_JS_INPUT_BY_TITLE_HELPERS}
                const dialog = __tvPickSettingsDialog(true) || __tvPickSettingsDialog(false);
                if (!dialog) return {{ ok: false, oldValue: '', newValue: '', reason: 'missing_dialog' }};
                const control = __tvFindInputByTitle(dialog, title);
                if (!control) return {{ ok: false, oldValue: '', newValue: '', reason: 'missing_input' }};
                if (control.getAttribute?.('role') !== 'combobox') {{
                    return {{ ok: false, oldValue: __tvNormalize(control.textContent || control.value), newValue: __tvNormalize(control.textContent || control.value), reason: 'expected_combobox' }};
                }}
                const expected = String(value).trim();
                const oldValue = __tvNormalize(control.textContent || '');
                if (oldValue === expected) {{
                    return {{ ok: true, oldValue, newValue: oldValue, reason: '' }};
                }}
                control.scrollIntoView({{ block: 'center' }});
                control.click();
                return {{ ok: true, oldValue, newValue: oldValue, reason: 'opened' }};
            }})
            """,
            {"title": title, "value": value},
        )
        if not result or not result.get("ok"):
            log.debug(
                "_apply_params: %s select failed (%s)",
                title,
                (result or {}).get("reason"),
            )
            return False

        await asyncio.sleep(0.3)
        clicked = await self.page.evaluate(
            """
            ((value) => {
                const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim();
                const visible = (el) => {
                    const rect = el?.getBoundingClientRect?.();
                    const style = el ? window.getComputedStyle(el) : null;
                    return !!rect && rect.width > 0 && rect.height > 0 &&
                        style?.visibility !== 'hidden' && style?.display !== 'none';
                };
                const expected = String(value).trim();
                for (const el of document.querySelectorAll('[role="option"], [class*="option"], [class*="item-"], [class*="menuItem"], [class*="dropdownItem"], button, [role="button"]')) {
                    if (normalize(el.textContent) === expected && visible(el)) {
                        el.click();
                        return true;
                    }
                }
                return false;
            })
            """,
            value,
        )
        if not clicked:
            if (str((result or {}).get("oldValue", "")).strip() == str(value).strip()):
                return True
            try:
                await self.page.keyboard.press("Escape")
            except Exception:
                pass
            return False

        await asyncio.sleep(0.2)
        log.debug(
            "_apply_params: %s %s -> %s",
            title,
            (result or {}).get("oldValue"),
            value,
        )
        return True

    async def _toggle_checkbox_by_title(self, title: str, desired_state: bool) -> bool:
        result = await self.page.evaluate(
            f"""
            (({{ title, desiredState }}) => {{
                {_JS_SETTINGS_DIALOG_HELPERS}
                {_JS_INPUT_BY_TITLE_HELPERS}
                const dialog = __tvPickSettingsDialog(true) || __tvPickSettingsDialog(false);
                if (!dialog) return {{ ok: false, oldValue: '', newValue: '', reason: 'missing_dialog' }};
                const input = __tvFindInputByTitle(dialog, title);
                if (!input) return {{ ok: false, oldValue: '', newValue: '', reason: 'missing_input' }};
                if (input.type !== 'checkbox') return {{ ok: false, oldValue: String(input.value || ''), newValue: String(input.value || ''), reason: 'expected_checkbox' }};
                const oldValue = Boolean(input.checked);
                const nextState = Boolean(desiredState);
                if (oldValue !== nextState) {{
                    const proto = Object.getPrototypeOf(input);
                    const descriptor = Object.getOwnPropertyDescriptor(proto, 'checked')
                        || Object.getOwnPropertyDescriptor(window.HTMLInputElement?.prototype || {{}}, 'checked');
                    if (descriptor?.set) {{
                        descriptor.set.call(input, nextState);
                    }} else {{
                        input.checked = nextState;
                    }}
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
                const newValue = Boolean(input.checked);
                return {{ ok: newValue === nextState, oldValue: String(oldValue), newValue: String(newValue), reason: '' }};
            }})
            """,
            {"title": title, "desiredState": desired_state},
        )
        log.debug(
            "_apply_params: %s %s -> %s",
            title,
            (result or {}).get("oldValue"),
            (result or {}).get("newValue"),
        )
        if result and result.get("ok"):
            await asyncio.sleep(0.1)
        return bool((result or {}).get("ok"))

    async def _close_settings_dialog(self) -> bool:
        """Dismiss the visible settings dialog, if any."""
        try:
            await self.page.keyboard.press("Escape")
        except Exception:
            return False
        return await self._wait_dialog_close()

    async def _apply_baseline_risk_reset(self, target_risk_pct: float = 0.5) -> ApplyOutcome:
        """
        Ensure the baseline risk is set before optimization begins.

        If TradingView already shows the target risk value, treat the reset as a
        successful no-op instead of forcing it through stale-hash detection.
        """
        await self._dismiss_tv_errors()
        await self._prepare_clean_chart()

        if not await self._open_settings():
            return await self._apply_params({"risk_per_trade_pct": target_risk_pct})
        await asyncio.sleep(0.5)

        await self._click_inputs_tab()
        await asyncio.sleep(0.3)

        if not await self._ensure_custom_profile():
            try:
                await self._close_settings_dialog()
            except Exception:
                pass
            return await self._apply_params({"risk_per_trade_pct": target_risk_pct})

        current_value = ""
        try:
            current_value = await self._read_input_value(INPUT_INDEX["risk_per_trade_pct"])
        finally:
            try:
                await self._close_settings_dialog()
            except Exception:
                pass

        try:
            if current_value and abs(float(current_value) - float(target_risk_pct)) < 1e-9:
                return ApplyOutcome(
                    ok=True,
                    fresh=True,
                    reason="baseline_already_set",
                    attempt=1,
                )
        except ValueError:
            pass

        return await self._apply_params({"risk_per_trade_pct": target_risk_pct})

    async def _toggle_checkbox(self, index: int, desired_state: bool) -> bool:
        """Toggle a checkbox to the desired state using native checked setters."""
        try:
            changed = await self.page.evaluate(
                f"""
                ({{
                    index,
                    desiredState
                }}) => {{
                    {_JS_SETTINGS_DIALOG_HELPERS}
                    const dialog = __tvPickSettingsDialog(true) || __tvPickSettingsDialog(false);
                    if (!dialog) return false;
                    const inputs = dialog.querySelectorAll('input');
                    if (index >= inputs.length) return false;
                    const input = inputs[index];
                    if (!input || input.type !== 'checkbox') return false;
                    const nextState = Boolean(desiredState);
                    if (Boolean(input.checked) !== nextState) {{
                        const proto = Object.getPrototypeOf(input);
                        const descriptor = Object.getOwnPropertyDescriptor(proto, 'checked')
                            || Object.getOwnPropertyDescriptor(window.HTMLInputElement?.prototype || {{}}, 'checked');
                        if (descriptor?.set) {{
                            descriptor.set.call(input, nextState);
                        }} else {{
                            input.checked = nextState;
                        }}
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                    return Boolean(input.checked) === nextState;
                }}
                """,
                {"index": index, "desiredState": desired_state},
            )
            if changed:
                await asyncio.sleep(0.1)
            return bool(changed)
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
                            if (row.textContent?.includes('S&D Algo') || row.textContent?.includes('S&D Pro')) {
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
                                if (row.textContent?.includes('S&D Algo') || row.textContent?.includes('S&D Pro')) {
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
        """Dismiss TradingView error toasts. If 'Script calculation timed out' or
        'Runtime error' (e.g. modify_study_limit_exceeding) detected,
        also reloads the strategy via eye-click toggle."""
        try:
            await self._raise_if_tradingview_crashed()

            # Check if the timeout error or runtime error is visible
            error_type = await self.page.evaluate(
                """
                (() => {
                    const walker = document.createTreeWalker(
                        document.body, NodeFilter.SHOW_TEXT, null
                    );
                    let node;
                    while ((node = walker.nextNode())) {
                        const txt = node.textContent || '';
                        if (txt.includes('timed out')) {
                            const el = node.parentElement;
                            if (el && el.childElementCount === 0) return 'timed_out';
                        }
                        if (txt.includes('Runtime error') || txt.includes('modify_study_limit')) {
                            const el = node.parentElement;
                            if (el && el.childElementCount === 0) return 'runtime_error';
                        }
                    }
                    return '';
                })()
                """
            )
            if error_type == 'timed_out':
                print(" [⚠ script timed out, reloading...]", end="", flush=True)
                await self._reload_strategy_script()
            elif error_type == 'runtime_error':
                print(" [⚠ runtime error (study limit), reloading...]", end="", flush=True)
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
                            const inSettings = btn.closest('[data-name="indicator-properties-dialog"][role="dialog"], [class*="dialog-"][class*="rounded"]');
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
            profile = await self._read_profile_dropdown_text()

            # profile='' means dialog isn't ready (TV error state / script timeout)
            if profile == '':
                profile = await self._recover_blank_settings_dialog()

                if profile == "":
                    await self._log_dialog_state("_ensure_custom_profile blank after recover")
                    log.warning("_ensure_custom_profile: settings dialog still blank after reopen")
                    return False

            if profile == "Custom":
                return True

            print(f" [profile='{profile}', switching to Custom...]", end="", flush=True)

            # Click the combobox to open the dropdown
            await self.page.evaluate(
                f"""
                (() => {{
                    {_JS_SETTINGS_DIALOG_HELPERS}
                    const dialog = __tvPickSettingsDialog(true) || __tvPickSettingsDialog(false);
                    if (!dialog) return;
                    const combo = dialog.querySelector('button[role="combobox"]');
                    if (combo) combo.click();
                }})()
                """
            )
            await asyncio.sleep(0.6)

            # Click the "Custom" option — it can appear in a portal outside the dialog.
            # TradingView changes the dropdown structure often, so search broadly
            # and require the option to be actually visible before clicking.
            clicked = await self.page.evaluate(
                """
                (() => {
                    const selectors = [
                        '[role="option"]', '[class*="option"]',
                        '[class*="item-"]', 'li', '[class*="listItem"]',
                        '[class*="menuItem"]', '[class*="dropdownItem"]',
                        'button', '[role="button"]', '[data-name]',
                    ];
                    const visible = (el) => {
                        const rect = el.getBoundingClientRect?.();
                        const style = window.getComputedStyle?.(el);
                        return !!rect && rect.width > 0 && rect.height > 0 &&
                               style?.visibility !== 'hidden' && style?.display !== 'none';
                    };
                    for (const sel of selectors) {
                        for (const el of document.querySelectorAll(sel)) {
                            if (el.textContent?.trim() === 'Custom' && visible(el)) {
                                el.click();
                                return true;
                            }
                        }
                    }
                    const all = Array.from(document.querySelectorAll('*'));
                    for (const el of all) {
                        if (el.textContent?.trim() === 'Custom' && visible(el)) {
                            el.click();
                            return true;
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
                await self._log_dialog_state("_ensure_custom_profile missing Custom option")
                log.warning("_ensure_custom_profile: could not find 'Custom' option in dropdown")
                return False

            await asyncio.sleep(0.5)

            # Verify the switch worked
            new_profile = await self._read_profile_dropdown_text()
            if new_profile == "Custom":
                print(" [switched ✓]", end="", flush=True)
                return True
            else:
                await self._log_dialog_state("_ensure_custom_profile verify switch")
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
            if not await self._toggle_checkbox_by_title("use_custom_rr", False):
                raise KeyError("Failed to apply Pine input title: use_custom_rr")
        else:
            rr_value = mode.replace("fixed_", "")
            if not await self._toggle_checkbox_by_title("use_custom_rr", True):
                raise KeyError("Failed to apply Pine input title: use_custom_rr")
            await asyncio.sleep(0.1)
            if not await self._set_input_by_title("risk_reward_ratio", rr_value):
                raise KeyError("Failed to apply Pine input title: risk_reward_ratio")

    async def _apply_single_param(
        self, param_name: str, value, param_type: str
    ) -> None:
        """Apply a single parameter change (numeric / checkbox / special types)."""
        if param_type == "rr_mode":
            await self._apply_rr_mode(value)
        elif param_type == "checkbox":
            if not await self._toggle_checkbox_by_title(param_name, bool(value)):
                raise KeyError(f"Failed to apply Pine input title: {param_name}")
        elif param_type == "select":
            if not await self._set_select_by_title(param_name, str(value)):
                raise KeyError(f"Failed to apply Pine input title: {param_name}")
        elif param_type == "liq_distance":
            pass  # Caller resolves to correct param name
        elif param_type == "numeric":
            if not await self._set_input_by_title(param_name, value):
                raise KeyError(f"Failed to apply Pine input title: {param_name}")

    async def _click_ok(self) -> None:
        """Click the OK button in the settings dialog."""
        try:
            clicked = await self.page.evaluate(
                f"""
                (() => {{
                    {_JS_SETTINGS_DIALOG_HELPERS}
                    const dialog = __tvPickSettingsDialog(true) || __tvPickSettingsDialog(false);
                    if (!dialog) return false;
                    for (const btn of dialog.querySelectorAll('button')) {{
                        if (__tvNormalize(btn.textContent) === 'Ok' && __tvVisible(btn)) {{
                            btn.click();
                            return true;
                        }}
                    }}
                    return false;
                }})()
                """
            )
            if not clicked:
                await self.page.keyboard.press("Enter")
        except Exception:
            await self.page.keyboard.press("Enter")

    async def _click_inputs_tab(self) -> None:
        """Focus the Inputs tab inside the selected strategy settings dialog."""
        await self.page.evaluate(
            f"""
            (() => {{
                {_JS_SETTINGS_DIALOG_HELPERS}
                const dialog = __tvPickSettingsDialog(true) || __tvPickSettingsDialog(false);
                if (!dialog) return false;
                for (const btn of dialog.querySelectorAll('[role="tab"], button')) {{
                    if (__tvNormalize(btn.textContent) === 'Inputs' && __tvVisible(btn)) {{
                        btn.click();
                        return true;
                    }}
                }}
                return false;
            }})()
            """
        )

    async def _wait_dialog_close(self) -> bool:
        """Wait for the settings dialog to close."""
        for _ in range(20):
            gone = await self.page.evaluate(
                f"""
                (() => {{
                    {_JS_SETTINGS_DIALOG_HELPERS}
                    return !__tvPickSettingsDialog(false);
                }})()
                """
            )
            if gone:
                return True
            await asyncio.sleep(0.3)
        return False

    # ─────────────────────────────────── apply params (with retry) ───────────

    async def _apply_params(self, params: dict, *, allow_unchanged_hash: bool = False) -> ApplyOutcome:
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
                # Dismiss any runtime errors before attempting
                await self._dismiss_tv_errors()
                await self._prepare_clean_chart()

                # Snapshot hash BEFORE
                hash_before = await self._get_results_hash()

                if not await self._open_settings():
                    raise RuntimeError("Could not open settings dialog")
                await asyncio.sleep(0.5)

                # Click Inputs tab
                await self._click_inputs_tab()
                await asyncio.sleep(0.3)

                # Ensure profile is Custom — preset profiles lock inputs and ignore changes
                if not await self._ensure_custom_profile():
                    raise RuntimeError("Could not ensure Custom profile")

                await self._validate_setting_titles(params)

                # Apply rr_mode first (special handling)
                rr_mode = params.get("rr_mode")
                if rr_mode is not None:
                    await self._apply_rr_mode(rr_mode)
                    await asyncio.sleep(0.1)

                # Apply remaining params
                for name, value in params.items():
                    if name == "rr_mode":
                        continue  # already handled
                    if name in CHECKBOX_PARAM_NAMES:
                        applied = await self._toggle_checkbox_by_title(name, bool(value))
                    elif isinstance(value, str):
                        applied = await self._set_select_by_title(name, value)
                    else:
                        applied = await self._set_input_by_title(name, value)
                    if not applied:
                        raise KeyError(f"Failed to apply Pine input title: {name}")

                await self._click_ok()
                if not await self._wait_dialog_close():
                    if attempt < _MAX_RETRIES:
                        log.debug(
                            "_apply_params attempt %d: settings dialog remained open after Ok",
                            attempt,
                        )
                        await asyncio.sleep(_RETRY_SLEEP)
                        continue
                    log.warning(
                        "_apply_params attempt %d: settings dialog remained open after Ok",
                        attempt,
                    )
                    return ApplyOutcome(
                        ok=False,
                        fresh=False,
                        reason="settings_dialog_still_open",
                        attempt=attempt,
                        results_hash_before=hash_before,
                        results_hash_after=hash_after,
                    )

                # ── Full update cycle detection ────────────────────────────
                completed = await self._wait_for_update_complete()
                if not completed:
                    if attempt < _MAX_RETRIES:
                        log.debug(
                            "_apply_params attempt %d: update timed out — pressing Escape and retrying",
                            attempt,
                        )
                    else:
                        log.warning(
                            "_apply_params attempt %d: update timed out — final retry",
                            attempt,
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
                    if attempt < _MAX_RETRIES:
                        log.debug(
                            "_apply_params attempt %d: could not read results hash",
                            attempt,
                        )
                    else:
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
                    if allow_unchanged_hash and completed:
                        log.info(
                            "_apply_params attempt %d: results hash unchanged but accepted "
                            "for frozen-parameter validation (hash=%s)",
                            attempt,
                            hash_after,
                        )
                        return ApplyOutcome(
                            ok=True,
                            fresh=True,
                            reason="unchanged_result_hash_allowed",
                            attempt=attempt,
                            results_hash_before=hash_before,
                            results_hash_after=hash_after,
                        )
                    if attempt < _MAX_RETRIES:
                        log.debug(
                            "_apply_params attempt %d: results hash unchanged "
                            "(hash_before=%s hash_after=%s — possible stale read or param rejected)",
                            attempt, hash_before, hash_after,
                        )
                    else:
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

            except KeyError as e:
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

    async def _apply_params_for_alert(self, params: dict) -> ApplyOutcome:
        """
        Apply alert deployment params once without optimizer-style stale-result retries.

        Alert setup only needs the chart configured correctly before opening the
        alert dialog. It should not reopen the settings dialog multiple times or
        mutate the Strategy Report range like optimization does.
        """
        try:
            # Dismiss any runtime errors before attempting
            await self._dismiss_tv_errors()
            await self._prepare_clean_chart()

            if not await self._open_settings():
                raise RuntimeError("Could not open settings dialog")
            await asyncio.sleep(0.5)

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

            if not await self._ensure_custom_profile():
                raise RuntimeError("Could not ensure Custom profile")

            await self._validate_setting_titles(params)

            rr_mode = params.get("rr_mode")
            if rr_mode is not None:
                await self._apply_rr_mode(rr_mode)
                await asyncio.sleep(0.1)

            for name, value in params.items():
                if name == "rr_mode":
                    continue
                if name in CHECKBOX_PARAM_NAMES:
                    applied = await self._toggle_checkbox_by_title(name, bool(value))
                elif isinstance(value, str):
                    applied = await self._set_select_by_title(name, value)
                else:
                    applied = await self._set_input_by_title(name, value)
                if not applied:
                    raise KeyError(f"Failed to apply Pine input title: {name}")

            await self._click_ok()
            if not await self._wait_dialog_close():
                raise RuntimeError("Settings dialog remained open after Ok")
            await self._wait_for_update_complete()

            return ApplyOutcome(
                ok=True,
                fresh=True,
                reason="alert_params_applied",
                attempt=1,
                results_hash_before="",
                results_hash_after="",
            )
        except Exception as e:
            log.warning("_apply_params_for_alert failed: %s", e)
            return ApplyOutcome(
                ok=False,
                fresh=False,
                reason="apply_failed",
                attempt=1,
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
                if not await self._wait_dialog_close():
                    raise RuntimeError("Settings dialog remained open after Ok")

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

            except KeyError:
                raise
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
            params=materialize_result_params(params),
            verified_symbol=observed_symbol,
            timestamp=datetime.now().isoformat(),
        )
        try:
            metrics = await self.page.evaluate(_JS_COLLECT_METRICS)
            for key, value in (metrics or {}).items():
                kl = key.lower()
                raw_value = str(value)
                primary_value = raw_value.split("|")[0]

                if "drawdown" in kl:
                    drawdown_abs = self._extract_first_number(primary_value)
                    if drawdown_abs is not None:
                        result.max_drawdown = abs(drawdown_abs)
                    drawdown_pct = self._extract_first_percent(raw_value)
                    if drawdown_pct is not None:
                        result.max_drawdown_pct = abs(drawdown_pct)
                        result.drawdown_source = "percent"
                    continue

                c = (
                    primary_value
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
                    fallback_num = self._extract_first_number(
                        primary_value.replace("\u2212", "-").replace("−", "-")
                    )
                    if fallback_num is None:
                        continue
                    num = fallback_num
                if "total p&l" in kl or "net profit" in kl:
                    result.net_profit = num
                elif "total trades" in kl:
                    result.total_trades = int(num)
                elif "profitable" in kl:
                    result.win_rate = num
                elif "profit factor" in kl:
                    result.profit_factor = num

            if result.max_drawdown > 0 and result.max_drawdown_pct == 0:
                result.max_drawdown_pct = (result.max_drawdown / 50000) * 100
                result.drawdown_source = "fallback_50k"

        except Exception as e:
            print(f" [read error: {e}]", end="")

        result.calculate_score()
        return result

    async def _read_strategy_trade_coverage(
        self,
        start_date: str,
        end_date: str,
        total_trades: int,
    ) -> StrategyTradeCoverage:
        """Read the actual trade-date span from TradingView's strategy data."""
        start_ts = _iso_date_to_unix_seconds(start_date)
        end_ts = _iso_date_to_unix_seconds(end_date)
        requested_days = max((end_ts - start_ts) / 86400.0, 1.0)
        raw = await self.page.evaluate(
            """
            (() => {
                /* strategy-trade-coverage */
                const fmt = (ts) => ts ? new Date(ts * 1000).toISOString().slice(0, 10) : '';
                const timestamps = [];
                const seen = new Set();
                const pushTimestamp = (value) => {
                    let ts = 0;
                    if (typeof value === 'number' && Number.isFinite(value)) {
                        if (value > 946684800000 && value < 4102444800000) {
                            ts = Math.floor(value / 1000);
                        } else if (value > 946684800 && value < 4102444800) {
                            ts = Math.floor(value);
                        }
                    } else if (typeof value === 'string') {
                        const parsed = Date.parse(value);
                        if (Number.isFinite(parsed)) {
                            ts = Math.floor(parsed / 1000);
                        }
                    }
                    if (!ts || seen.has(ts)) return;
                    seen.add(ts);
                    timestamps.push(ts);
                };
                const collect = (value, key = '', depth = 0) => {
                    if (value == null || depth > 5) return;
                    const keyLooksTemporal = /time|date|timestamp|entry|exit|open|close/i.test(key || '');
                    if (typeof value === 'number' || typeof value === 'string') {
                        if (keyLooksTemporal) pushTimestamp(value);
                        return;
                    }
                    if (Array.isArray(value)) {
                        for (const item of value) collect(item, key, depth + 1);
                        return;
                    }
                    if (typeof value !== 'object') return;
                    for (const childKey of Object.keys(value)) {
                        const child = value[childKey];
                        if (typeof child === 'function') continue;
                        collect(child, childKey, depth + 1);
                    }
                };
                try {
                    const chart = window.TradingViewApi?._activeChartWidgetWV?.value?.()?._chartWidget;
                    const sources = chart?.model?.()?.model?.()?.dataSources?.() || [];
                    let strat = null;
                    for (const source of sources) {
                        const meta = source?.metaInfo?.();
                        const hasStrategyData = !!(source.ordersData || source.tradesData || source.reportData || source.performance);
                        const looksLikeStrategy = meta?.is_price_study === false || hasStrategyData;
                        if (looksLikeStrategy && hasStrategyData) {
                            strat = source;
                            break;
                        }
                    }
                    if (!strat) {
                        return { ok: false, error: 'No strategy found on chart' };
                    }
                    let orders = null;
                    if (strat.ordersData) {
                        orders = typeof strat.ordersData === 'function' ? strat.ordersData() : strat.ordersData;
                        if (orders && typeof orders.value === 'function') orders = orders.value();
                    }
                    if ((!orders || !Array.isArray(orders)) && strat.tradesData) {
                        orders = typeof strat.tradesData === 'function' ? strat.tradesData() : strat.tradesData;
                        if (orders && typeof orders.value === 'function') orders = orders.value();
                    }
                    if ((!orders || !Array.isArray(orders)) && Array.isArray(strat._orders)) {
                        orders = strat._orders;
                    }
                    if (!orders || !Array.isArray(orders)) {
                        return { ok: false, error: 'strategy ordersData/tradesData returned no array' };
                    }
                    for (const order of orders) collect(order);
                    timestamps.sort((a, b) => a - b);
                    const first = timestamps[0] || 0;
                    const last = timestamps[timestamps.length - 1] || 0;
                    return {
                        ok: true,
                        inspected_orders: orders.length,
                        date_count: timestamps.length,
                        first_ts: first,
                        last_ts: last,
                        first_date: fmt(first),
                        last_date: fmt(last),
                    };
                } catch (error) {
                    return { ok: false, error: String(error?.message || error) };
                }
            })()
            """
        )
        if not isinstance(raw, dict) or not raw.get("ok"):
            error = raw.get("error") if isinstance(raw, dict) else raw
            raise RuntimeError(f"PARTIAL_DATA: could not inspect Strategy Tester trade dates ({error})")

        first_ts = int(raw.get("first_ts") or 0)
        last_ts = int(raw.get("last_ts") or 0)
        trade_span_days = max((last_ts - first_ts) / 86400.0, 0.0) if first_ts and last_ts else 0.0
        return StrategyTradeCoverage(
            requested_days=requested_days,
            trade_span_days=trade_span_days,
            coverage_ratio=trade_span_days / requested_days,
            total_trades=total_trades,
            inspected_orders=int(raw.get("inspected_orders") or 0),
            trade_date_count=int(raw.get("date_count") or 0),
            first_trade_ts=first_ts,
            last_trade_ts=last_ts,
            first_trade_date=str(raw.get("first_date") or ""),
            last_trade_date=str(raw.get("last_date") or ""),
        )

    async def _verify_custom_strategy_trade_coverage(
        self,
        result: BacktestResult,
        start_date: str,
        end_date: str,
    ) -> StrategyTradeCoverage:
        """Fail loudly when Strategy Tester only produced trades for part of a custom range."""
        if result.total_trades <= 0:
            log.warning(
                "_verify_custom_strategy_trade_coverage: %s has no trades; cannot prove trade span for %s..%s",
                result.symbol,
                start_date,
                end_date,
            )
            return StrategyTradeCoverage(
                requested_days=max((_iso_date_to_unix_seconds(end_date) - _iso_date_to_unix_seconds(start_date)) / 86400.0, 1.0),
                trade_span_days=0.0,
                coverage_ratio=0.0,
                total_trades=0,
                inspected_orders=0,
                trade_date_count=0,
                first_trade_ts=0,
                last_trade_ts=0,
                first_trade_date="",
                last_trade_date="",
            )

        coverage = await self._read_strategy_trade_coverage(start_date, end_date, result.total_trades)
        result.validation_metrics["strategy_trade_coverage"] = {
            "requested_days": coverage.requested_days,
            "trade_span_days": coverage.trade_span_days,
            "coverage_ratio": coverage.coverage_ratio,
            "total_trades": coverage.total_trades,
            "inspected_orders": coverage.inspected_orders,
            "trade_date_count": coverage.trade_date_count,
            "first_trade_date": coverage.first_trade_date,
            "last_trade_date": coverage.last_trade_date,
        }

        if coverage.trade_date_count < 2:
            raise RuntimeError(
                "PARTIAL_DATA: could not find enough Strategy Tester trade timestamps "
                f"for {result.symbol} ({coverage.trade_date_count} dates from "
                f"{coverage.inspected_orders} orders, total_trades={result.total_trades})"
            )

        if coverage.coverage_ratio < _TRADE_COVERAGE_MIN_RATIO:
            raise RuntimeError(
                "PARTIAL_DATA: Strategy Tester trades span only "
                f"{coverage.trade_span_days:.1f} days of {coverage.requested_days:.1f} requested "
                f"({coverage.coverage_ratio:.0%}); first_trade={coverage.first_trade_date or '?'} "
                f"last_trade={coverage.last_trade_date or '?'} total_trades={result.total_trades}. "
                "Chart likely has insufficient historical bars loaded. Try a higher timeframe "
                "or a TradingView plan with more historical intraday bars."
            )

        print(
            f"  [trade coverage ✓ {coverage.trade_span_days:.0f}/{coverage.requested_days:.0f}d "
            f"({coverage.first_trade_date} → {coverage.last_trade_date})]",
            flush=True,
        )
        return coverage

    # ─────────────────────────────────── high-level optimization ─────────────

    async def validate_pair(
        self,
        symbol: str,
        params: dict,
        *,
        custom_start_date: str | None = None,
        custom_end_date: str | None = None,
    ) -> BacktestResult:
        """Run one frozen-parameter backtest for a symbol."""
        tag = f"[{symbol}]"
        print(f"\n{'=' * 60}")
        print(f"{tag} VALIDATING: {symbol}")
        print(f"{'=' * 60}")

        await self._switch_symbol(symbol)
        if self.optimizer.backtest_range == "custom":
            if not custom_start_date or not custom_end_date:
                raise RuntimeError("custom_start_date and custom_end_date are required")
            await self._require_custom_date_range(custom_start_date, custom_end_date)
        else:
            await self._require_backtest_range(self.optimizer.backtest_range_label)
        await self._prepare_clean_chart()

        apply_outcome = await self._apply_params(params, allow_unchanged_hash=True)
        if not apply_outcome.fresh:
            raise RuntimeError(apply_outcome.reason or "frozen params did not produce a fresh result")
        result = await self._read_results(symbol, params)
        if self.optimizer.backtest_range == "custom":
            await self._verify_custom_strategy_trade_coverage(
                result,
                custom_start_date or self.optimizer.custom_start_date,
                custom_end_date or self.optimizer.custom_end_date,
            )
        self.results.append(result)
        _print_pair_summary_table(result)
        return result

    async def optimize_pair(self, symbol: str) -> Optional[BacktestResult]:
        """Run full grid-search optimization for one symbol on this tab."""
        tag = f"[{symbol}]"
        print(f"\n{'=' * 60}")
        print(f"{tag} OPTIMIZING: {symbol}")
        print(f"{'=' * 60}")

        await self._switch_symbol(symbol)
        if self.optimizer.backtest_range == "custom":
            await self._require_custom_date_range(
                self.optimizer.custom_start_date,
                self.optimizer.custom_end_date,
            )
        else:
            await self._require_backtest_range(self.optimizer.backtest_range_label)
        await self._prepare_clean_chart()

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
        if self.optimizer.backtest_range == "custom":
            await self._require_custom_date_range(
                self.optimizer.custom_start_date,
                self.optimizer.custom_end_date,
            )
        else:
            await self._require_backtest_range(self.optimizer.backtest_range_label)
        await self._prepare_clean_chart()

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
