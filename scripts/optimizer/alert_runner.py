from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from math import isclose
from typing import Any, Callable, Protocol


class AlertBatchCancelled(Exception):
    pass


def load_batch_from_api_payload(payload: dict[str, Any]) -> dict[str, Any]:
    batch = dict(payload)
    batch["pairs"] = [str(item).strip().upper() for item in (batch.get("pairs") or []) if str(item).strip()]
    batch["config_snapshot"] = list(batch.get("config_snapshot") or [])
    batch["timeframe"] = str(batch.get("timeframe") or "5m").strip() or "5m"
    return batch


def build_alert_name(prefix: str | None, pair: str, timeframe: str) -> str:
    base = prefix.strip() if prefix and prefix.strip() else "TradeOps"
    return f"{base} · {pair} · {timeframe}"


def build_alert_message(config_snapshot: dict[str, Any], *, batch_id: str, pair: str, timeframe: str) -> str:
    return json.dumps(
        {
            "batch_id": batch_id,
            "pair": pair,
            "timeframe": timeframe,
            "risk_weight": config_snapshot.get("risk_weight", 1.0),
            "source_run_id": config_snapshot.get("source_run_id"),
            "params": config_snapshot.get("params") or {},
        },
        separators=(",", ":"),
    )


@dataclass
class AlertDeployment:
    pair: str
    timeframe: str
    config_snapshot: dict[str, Any]
    alert_name: str
    alert_id: str
    params: dict[str, Any]


class AlertBrowser(Protocol):
    async def deploy_alert(
        self,
        *,
        pair: str,
        timeframe: str,
        config_snapshot: dict[str, Any],
        alert_name_prefix: str | None,
        webhook_url: str,
        should_stop: Callable[[], bool],
    ) -> AlertDeployment: ...


class TradingViewAlertBrowser:
    def __init__(self, chrome_port: int = 9222) -> None:
        self._chrome_port = chrome_port

    async def deploy_alert(
        self,
        *,
        pair: str,
        timeframe: str,
        config_snapshot: dict[str, Any],
        alert_name_prefix: str | None,
        webhook_url: str,
        should_stop: Callable[[], bool],
    ) -> AlertDeployment:
        if should_stop():
            raise AlertBatchCancelled()
        if not webhook_url:
            raise RuntimeError("webhook_url is required to create TradingView alerts")

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("playwright not installed in alert runner environment") from exc

        from scripts.optimizer.parallel_runner import ensure_tradingview_tabs
        from scripts.optimizer.optimizer import TradingViewOptimizer
        from scripts.optimizer.tab_worker import TabWorker

        alert_name = build_alert_name(alert_name_prefix, pair, timeframe)
        params = dict(config_snapshot.get("params") or {})

        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{self._chrome_port}")
            pages = await ensure_tradingview_tabs(browser, 1, pair)
            page = pages[0]
            page.on("dialog", lambda dialog: asyncio.create_task(self._dismiss_js_dialog(dialog)))
            optimizer = TradingViewOptimizer(
                pairs=[pair],
                bayesian_mode=True,
                n_trials=1,
                dd_limit=10.0,
                generate_report=False,
            )
            worker = TabWorker(page, optimizer)
            await worker._switch_symbol(pair)
            await worker._require_last_365_days()
            outcome = await worker._apply_params(params)
            if not outcome.fresh:
                metrics_match = await self._matches_source_metrics(worker, pair, config_snapshot)
                # For alert setup, a stale hash or blank dialog can still be acceptable
                # if the current chart already matches the approved snapshot.
                if not metrics_match and outcome.reason != "stale_result_hash":
                    raise RuntimeError(f"could not apply params for {pair}: {outcome.reason}")
                if not metrics_match and outcome.reason == "stale_result_hash":
                    raise RuntimeError(f"could not verify params for {pair}: {outcome.reason}")

            await page.keyboard.press("Alt+A")
            await page.wait_for_timeout(1000)
            await self._wait_for_alert_dialog(page)
            await self._select_alert_function_mode(page)
            await self._set_optional_field(page, "Alert name", alert_name)
            await self._set_field(page, "Webhook URL", webhook_url)
            await self._set_field(
                page,
                "Message",
                build_alert_message(config_snapshot, batch_id="live", pair=pair, timeframe=timeframe),
            )
            if not await self._click_button(page, ["Create", "Create Alert"]):
                raise RuntimeError("could not find TradingView Create Alert button")

        return AlertDeployment(
            pair=pair,
            timeframe=timeframe,
            config_snapshot=config_snapshot,
            alert_name=alert_name,
            alert_id=f"{pair.lower()}-{timeframe}",
            params=params,
        )

    async def _dismiss_js_dialog(self, dialog: Any) -> None:
        try:
            await dialog.dismiss()
        except Exception:
            try:
                await dialog.accept()
            except Exception:
                return

    async def _matches_source_metrics(
        self,
        worker: Any,
        pair: str,
        config_snapshot: dict[str, Any],
    ) -> bool:
        source_metrics = dict(config_snapshot.get("source_metrics") or {})
        if not source_metrics:
            return False
        try:
            result = await worker._read_results(pair, dict(config_snapshot.get("params") or {}))
        except Exception:
            return False

        target_pf = source_metrics.get("profit_factor")
        target_dd = source_metrics.get("max_drawdown_pct")
        target_trades = source_metrics.get("total_trades")
        if target_pf in (None, "") or target_dd in (None, "") or target_trades in (None, ""):
            return False

        try:
            return (
                isclose(float(result.profit_factor or 0.0), float(target_pf), rel_tol=0.0, abs_tol=0.02)
                and isclose(float(result.max_drawdown_pct or 0.0), float(target_dd), rel_tol=0.0, abs_tol=0.15)
                and abs(int(result.total_trades or 0) - int(target_trades)) <= 2
            )
        except Exception:
            return False

    async def _wait_for_alert_dialog(self, page: Any) -> None:
        await page.wait_for_function(
            """
            () => {
              const dialogs = Array.from(document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]'));
              return dialogs.some((node) => {
                const text = (node.textContent || '').trim();
                return text.includes('Create alert on') || text.includes('Condition') || text.includes('Notifications');
              });
            }
            """,
            timeout=15000,
        )

    async def _select_alert_function_mode(self, page: Any) -> None:
        selected = await page.evaluate(
            """
            () => {
              const body = document.body?.innerText || '';
              return body.includes('alert() function calls only');
            }
            """
        )
        if selected:
            return

        opened = await page.evaluate(
            """
            () => {
              const nodes = Array.from(document.querySelectorAll('button, div[role="button"], span'));
              for (const node of nodes) {
                const text = (node.textContent || '').trim();
                if (!text) continue;
                if (
                  text.includes('Order fills and alert() function calls') ||
                  text.includes('Order fills only') ||
                  text.includes('alert() function calls only')
                ) {
                  node.click();
                  return true;
                }
              }
              return false;
            }
            """
        )
        if not opened:
            raise RuntimeError("could not open alert trigger mode dropdown")

        await page.wait_for_timeout(500)
        picked = await page.evaluate(
            """
            () => {
              const nodes = Array.from(document.querySelectorAll('[role="option"], button, div[role="button"], span'));
              for (const node of nodes) {
                const text = (node.textContent || '').trim();
                if (text === 'alert() function calls only') {
                  node.click();
                  return true;
                }
              }
              return false;
            }
            """
        )
        if not picked:
            raise RuntimeError("could not select 'alert() function calls only'")

    async def _set_field(self, page: Any, label: str, value: str) -> None:
        ok = await page.evaluate(
            """
            ({ label, value }) => {
              const wanted = (label || '').trim().toLowerCase();
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const nodes = Array.from(document.querySelectorAll('label, span, div, button'));
              for (const node of nodes) {
                const text = normalize(node.textContent);
                if (!text || !text.includes(wanted)) continue;
                const root = node.closest('label, [role="group"], [class*="container"], [class*="content"], [data-name]') || node.parentElement || document;
                const input = root.querySelector('input, textarea');
                if (input) {
                  input.focus();
                  input.value = value;
                  input.dispatchEvent(new Event('input', { bubbles: true }));
                  input.dispatchEvent(new Event('change', { bubbles: true }));
                  return true;
                }

                // TradingView often renders Webhook URL / Message as collapsed rows.
                // Click the row first, then try the active dialog again.
                const clickable =
                  node.closest('button, [role="button"], [data-name], [class*="container"], [class*="content"]') ||
                  node;
                clickable.click?.();

                const activeDialogs = Array.from(
                  document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
                ).filter((el) => {
                  const rect = el.getBoundingClientRect();
                  return rect.width > 0 && rect.height > 0;
                });
                const dialog = activeDialogs[activeDialogs.length - 1] || document;
                const expanded = dialog.querySelector('input, textarea');
                if (expanded) {
                  expanded.focus();
                  expanded.value = value;
                  expanded.dispatchEvent(new Event('input', { bubbles: true }));
                  expanded.dispatchEvent(new Event('change', { bubbles: true }));
                  return true;
                }
              }
              return false;
            }
            """,
            {"label": label, "value": value},
        )
        if not ok:
            raise RuntimeError(f"could not find alert field: {label}")

    async def _set_optional_field(self, page: Any, label: str, value: str) -> bool:
        try:
            await self._set_field(page, label, value)
            return True
        except Exception:
            return False

    async def _click_button(self, page: Any, labels: list[str]) -> bool:
        for label in labels:
            locator = page.get_by_role("button", name=label, exact=False)
            try:
                if await locator.count() > 0:
                    await locator.first.click()
                    return True
            except Exception:
                continue
        return False


class AlertBatchRunner:
    def __init__(self, browser_factory: Callable[[], AlertBrowser] | None = None) -> None:
        self._browser_factory = browser_factory or TradingViewAlertBrowser

    async def run(
        self,
        batch: dict[str, Any],
        *,
        emit_event: Callable[[str, str | None, dict[str, Any]], None],
        should_stop: Callable[[], bool],
    ) -> dict[str, Any]:
        batch = load_batch_from_api_payload(batch)
        if should_stop():
            raise AlertBatchCancelled()

        browser = self._browser_factory()
        results = list(batch.get("config_snapshot") or [])
        if not results:
            raise RuntimeError("alert batch missing config_snapshot")

        completed = 0
        failed = 0
        for config_snapshot in results:
            if should_stop():
                raise AlertBatchCancelled()
            pair = str(config_snapshot.get("pair") or "").strip().upper()
            timeframe = str(config_snapshot.get("timeframe") or batch.get("timeframe") or "5m").strip()
            if not pair:
                failed += 1
                emit_event("pair_failed", None, {"error_message": "config snapshot missing pair"})
                continue

            emit_event("pair_started", pair, {"timeframe": timeframe})
            try:
                deployed = await browser.deploy_alert(
                    pair=pair,
                    timeframe=timeframe,
                    config_snapshot=config_snapshot,
                    alert_name_prefix=batch.get("alert_name_prefix"),
                    webhook_url=batch.get("webhook_url") or "",
                    should_stop=should_stop,
                )
                completed += 1
                emit_event(
                    "alert_created",
                    pair,
                    {
                        "alert_name": deployed.alert_name,
                        "alert_id": deployed.alert_id,
                        "config_snapshot": deployed.config_snapshot,
                    },
                )
                emit_event(
                    "pair_completed",
                    pair,
                    {
                        "alert_name": deployed.alert_name,
                        "alert_id": deployed.alert_id,
                        "config_snapshot": deployed.config_snapshot,
                        "params": deployed.params,
                    },
                )
            except AlertBatchCancelled:
                raise
            except Exception as exc:
                failed += 1
                emit_event("pair_failed", pair, {"error_message": str(exc)})

        status = "completed" if failed == 0 else "failed"
        summary = {
            "total_pairs": len(results),
            "completed_pairs": completed,
            "failed_pairs": failed,
            "created_alerts": completed,
            "running_pairs": 0,
            "pending_pairs": max(0, len(results) - completed - failed),
        }
        emit_event("batch_finished", None, {"status": status, "summary": summary})
        return {"status": status, "summary": summary}
