from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
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
                raise RuntimeError(f"could not apply params for {pair}: {outcome.reason}")

            await page.keyboard.press("Alt+A")
            await page.wait_for_timeout(1000)
            await page.wait_for_function(
                """
                () => {
                  const body = document.body?.innerText || "";
                  return body.includes("Create Alert") || body.includes("Alert name") || body.includes("Webhook URL");
                }
                """,
                timeout=15000,
            )
            await self._set_field(page, "Alert name", alert_name)
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

    async def _set_field(self, page: Any, label: str, value: str) -> None:
        ok = await page.evaluate(
            """
            ({ label, value }) => {
              const wanted = (label || '').trim().toLowerCase();
              const nodes = Array.from(document.querySelectorAll('label, span, div'));
              for (const node of nodes) {
                const text = (node.textContent || '').trim().toLowerCase();
                if (!text || !text.includes(wanted)) continue;
                const root = node.closest('label, [role="group"], [class*="container"], [class*="content"], [data-name]') || node.parentElement || document;
                const input = root.querySelector('input, textarea');
                if (!input) continue;
                input.focus();
                input.value = value;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
              }
              return false;
            }
            """,
            {"label": label, "value": value},
        )
        if not ok:
            raise RuntimeError(f"could not find alert field: {label}")

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
