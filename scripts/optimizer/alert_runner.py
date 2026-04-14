from __future__ import annotations

import asyncio
import json
import re
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


def build_alert_message(
    config_snapshot: dict[str, Any],
    *,
    batch_id: str,
    pair: str,
    timeframe: str,
    alert_name: str | None = None,
) -> str:
    return json.dumps(
        {
            "batch_id": batch_id,
            "pair": pair,
            "timeframe": timeframe,
            "alert_name": alert_name or build_alert_name(None, pair, timeframe),
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
    skipped_existing: bool = False


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
            page, created_for_pair = await self._prepare_pair_chart_page(
                browser,
                pair,
                ensure_tradingview_tabs,
                TabWorker,
                optimizer_factory=lambda: TradingViewOptimizer(
                    pairs=[pair],
                    bayesian_mode=True,
                    n_trials=1,
                    dd_limit=10.0,
                    generate_report=False,
                ),
            )
            try:
                page.on("dialog", lambda dialog: asyncio.create_task(self._dismiss_js_dialog(dialog)))
                optimizer = TradingViewOptimizer(
                    pairs=[pair],
                    bayesian_mode=True,
                    n_trials=1,
                    dd_limit=10.0,
                    generate_report=False,
                )
                worker = TabWorker(page, optimizer)
                outcome = await worker._apply_params_for_alert(params)
                if not outcome.ok:
                    raise RuntimeError(f"could not apply params for {pair}: {outcome.reason}")

                if await self._has_existing_alert(page, pair=pair, timeframe=timeframe):
                    return AlertDeployment(
                        pair=pair,
                        timeframe=timeframe,
                        config_snapshot=config_snapshot,
                        alert_name=alert_name,
                        alert_id=f"{pair.lower()}-{timeframe}",
                        params=params,
                        skipped_existing=True,
                    )

                await page.keyboard.press("Alt+A")
                await page.wait_for_timeout(1000)
                await self._wait_for_alert_dialog(page)
                await self._select_alert_function_mode(page)
                await self._set_optional_field(page, "Alert name", alert_name)
                await self._set_webhook_url(page, webhook_url)
                await self._submit_alert(page)
            finally:
                if created_for_pair:
                    try:
                        await page.close()
                    except Exception:
                        pass

        return AlertDeployment(
            pair=pair,
            timeframe=timeframe,
            config_snapshot=config_snapshot,
            alert_name=alert_name,
            alert_id=f"{pair.lower()}-{timeframe}",
            params=params,
        )

    async def _open_pair_chart_page(self, browser: Any, pair: str, ensure_tabs: Callable[..., Any]) -> tuple[Any, bool]:
        existing_pages: list[Any] = []
        for context in browser.contexts:
            for page in context.pages:
                try:
                    if "tradingview.com/chart" in page.url:
                        existing_pages.append(page)
                except Exception:
                    continue

        if not existing_pages:
            pages = await ensure_tabs(browser, 1, pair)
            return pages[0], False

        before_ids = {id(page) for page in existing_pages}
        pages = await ensure_tabs(browser, len(existing_pages) + 1, pair)
        for page in reversed(pages):
            if id(page) not in before_ids:
                return page, True

        return pages[-1], False

    async def _prepare_pair_chart_page(
        self,
        browser: Any,
        pair: str,
        ensure_tabs: Callable[..., Any],
        worker_cls: type[Any],
        optimizer_factory: Callable[[], Any],
        max_attempts: int = 3,
    ) -> tuple[Any, bool]:
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            page, created_for_pair = await self._open_pair_chart_page(browser, pair, ensure_tabs)
            try:
                worker = worker_cls(page, optimizer_factory())
                await worker._switch_symbol(pair)
                return page, created_for_pair
            except Exception as exc:
                last_error = exc
                if created_for_pair:
                    try:
                        await page.close()
                    except Exception:
                        pass
                if attempt >= max_attempts:
                    break
                await asyncio.sleep(1.5)
        assert last_error is not None
        raise last_error

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

    async def _wait_for_main_alert_dialog(self, page: Any) -> None:
        await page.wait_for_function(
            """
            () => {
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const dialogs = Array.from(
                document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
              ).filter((el) => {
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              });
              return dialogs.some((el) => normalize(el.textContent).includes('create alert on'));
            }
            """,
            timeout=5000,
        )

    async def _wait_for_main_alert_dialog_close(self, page: Any) -> None:
        await page.wait_for_function(
            """
            () => {
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const dialogs = Array.from(
                document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
              ).filter((el) => {
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              });
              return !dialogs.some((el) => normalize(el.textContent).includes('create alert on'));
            }
            """,
            timeout=5000,
        )

    async def _select_alert_function_mode(self, page: Any) -> None:
        selected = await page.evaluate(
            """
            () => {
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const dialogs = Array.from(
                document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
              ).filter((el) => {
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              });
              const dialog =
                dialogs.find((el) => normalize(el.textContent).includes('create alert on')) ||
                dialogs[dialogs.length - 1] ||
                document;
              const controls = Array.from(dialog.querySelectorAll('input, button, [role="button"], [role="combobox"], select, span, div'));
              return controls.some((node) => {
                const text = normalize(
                  node.value ??
                  node.getAttribute?.('aria-label') ??
                  node.textContent
                );
                return text === 'alert() function calls only';
              });
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

    async def _open_labeled_panel(self, page: Any, label: str) -> bool:
        coords = await page.evaluate(
            """
            (label) => {
              const wanted = (label || '').trim().toLowerCase();
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const dialogs = Array.from(
                document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
              ).filter((el) => {
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              });
              const mainDialog =
                dialogs.find((el) => normalize(el.textContent).includes('create alert on')) ||
                dialogs[dialogs.length - 1] ||
                document;
              const nodes = Array.from(mainDialog.querySelectorAll('button, [role="button"], div, span'));
              const matches = [];
              for (const node of nodes) {
                const text = normalize(node.textContent);
                if (!text) continue;
                if (text === wanted || text.startsWith(wanted + ' ')) {
                  const clickable =
                    node.closest('button, [role="button"], [data-name], [class*="container"], [class*="content"]') ||
                    node;
                  const rect = clickable.getBoundingClientRect?.();
                  if (!rect || rect.width <= 0 || rect.height <= 0) continue;
                  matches.push({
                    text,
                    x: rect.left + rect.width / 2,
                    y: rect.top + rect.height / 2,
                  });
                }
              }
              matches.sort((a, b) => a.text.length - b.text.length);
              return matches[0] || null;
            }
            """,
            label,
        )
        if not coords:
            return False
        await page.mouse.click(coords["x"], coords["y"])
        return True

    async def _wait_for_panel(self, page: Any, *titles: str) -> None:
        wanted_titles = [title for title in titles if title]
        await page.wait_for_function(
            """
            (titles) => {
              const wanted = Array.isArray(titles) ? titles.map((title) => (title || '').trim().toLowerCase()) : [];
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const dialogs = Array.from(
                document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
              ).filter((el) => {
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              });
              return dialogs.some((el) => {
                const headers = Array.from(el.querySelectorAll('button, span, div, h1, h2, h3'));
                return headers.some((node) => wanted.includes(normalize(node.textContent)));
              });
            }
            """,
            arg=wanted_titles,
            timeout=5000,
        )

    async def _set_webhook_url(self, page: Any, webhook_url: str) -> None:
        try:
            await self._set_field(page, "Webhook URL", webhook_url)
            return
        except Exception:
            pass

        opened = await self._open_labeled_panel(page, "Notifications")
        if opened:
            await page.wait_for_timeout(400)
            await self._wait_for_panel(page, "Notifications")
            webhook_enabled = await page.evaluate(
                """
                () => {
                  const dialogs = Array.from(
                    document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
                  ).filter((el) => {
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                  });
                  const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
                  const panel =
                    dialogs.find((el) => {
                      const headers = Array.from(el.querySelectorAll('button, span, div, h1, h2, h3'));
                      return headers.some((node) => normalize(node.textContent) === 'notifications');
                    }) ||
                    dialogs[dialogs.length - 1] ||
                    document;
                  const nodes = Array.from(panel.querySelectorAll('label, span, div, button'));
                  for (const node of nodes) {
                    const text = normalize(node.textContent);
                    if (!text || !(text === 'webhook url' || text.startsWith('webhook url '))) continue;
                    const root = node.closest('label, [role="group"], [class*="container"], [class*="content"], [data-name]') || node.parentElement || document;
                    const input = root.querySelector('input[type="checkbox"]');
                    if (input && !input.checked) {
                      input.click();
                      return true;
                    }
                    const button = root.querySelector('button, [role="button"]');
                    button?.click?.();
                    return true;
                  }
                  return false;
                }
                """
            )
            if webhook_enabled:
                await page.wait_for_timeout(400)
            await self._set_field(page, "Webhook URL", webhook_url)
            applied = await self._click_button(page, ["Apply"])
            if not applied:
                raise RuntimeError("could not find Notifications Apply button")
            await page.wait_for_timeout(400)
            await self._wait_for_main_alert_dialog(page)
            return

        raise RuntimeError("could not find alert field: Webhook URL")

    async def _set_message(self, page: Any, message: str) -> None:
        opened = await self._open_labeled_panel(page, "Message")
        if opened:
            await page.wait_for_timeout(400)
            await self._wait_for_panel(page, "Edit message", "Message")
            await self._set_active_panel_text(page, message, panel_titles=["edit message", "message"])
            applied = await self._click_button(page, ["Apply"])
            if not applied:
                raise RuntimeError("could not find Message Apply button")
            await page.wait_for_timeout(400)
            await self._wait_for_main_alert_dialog(page)
            return

        raise RuntimeError("could not find alert field: Message")

    async def _set_active_panel_text(self, page: Any, value: str, *, panel_titles: list[str]) -> None:
        ok = await page.evaluate(
            """
            ({ value, panelTitles }) => {
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const wanted = (panelTitles || []).map((title) => normalize(title));
              const dialogs = Array.from(
                document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
              ).filter((el) => {
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              });
              const panel =
                dialogs.find((el) => {
                  const headers = Array.from(el.querySelectorAll('button, span, div, h1, h2, h3'));
                  return headers.some((node) => wanted.includes(normalize(node.textContent)));
                }) ||
                dialogs[dialogs.length - 1] ||
                null;
              if (!panel) return false;
              const input = panel.querySelector('textarea, input[type="text"], input:not([type]), [contenteditable="true"]');
              if (!input) return false;
              input.focus?.();
              if (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) {
                input.value = value;
              } else {
                input.textContent = value;
              }
              input.dispatchEvent(new Event('input', { bubbles: true }));
              input.dispatchEvent(new Event('change', { bubbles: true }));
              return true;
            }
            """,
            {"value": value, "panelTitles": panel_titles},
        )
        if not ok:
            raise RuntimeError("could not fill message editor")

    async def _submit_alert(self, page: Any) -> None:
        if await self._click_button(page, ["Create", "Create Alert"], dialog_titles=["Create alert on"]):
            await page.wait_for_timeout(500)
            try:
                await self._wait_for_main_alert_dialog_close(page)
                return
            except Exception:
                pass

        # Fallback: find the submit button via broader selector inside the alert dialog
        submitted = await page.evaluate(
            """
            () => {
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const dialogs = Array.from(
                document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
              ).filter((el) => {
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              });
              const dialog =
                dialogs.find((el) => normalize(el.textContent).includes('create alert on')) ||
                dialogs[dialogs.length - 1] ||
                document;
              const buttons = Array.from(dialog.querySelectorAll('button, [role="button"]'));
              for (const btn of buttons) {
                const text = normalize(btn.textContent);
                if (text.startsWith('create') && !text.includes('cancel') && !text.includes('condition')) {
                  btn.click();
                  return true;
                }
              }
              // Try submit-style buttons (type="submit" or data-name containing submit/create)
              for (const btn of buttons) {
                if (btn.type === 'submit' || (btn.dataset?.name || '').toLowerCase().includes('submit')) {
                  btn.click();
                  return true;
                }
              }
              return false;
            }
            """
        )
        if submitted:
            await page.wait_for_timeout(500)
            try:
                await self._wait_for_main_alert_dialog_close(page)
                return
            except Exception:
                pass

        try:
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            await self._wait_for_main_alert_dialog_close(page)
            return
        except Exception:
            raise RuntimeError("could not click TradingView Create button")

    async def _has_existing_alert(self, page: Any, *, pair: str, timeframe: str) -> bool:
        opened = await page.evaluate(
            """
            () => {
              const buttons = Array.from(document.querySelectorAll('button, [role="button"], div[role="button"]'));
              for (const node of buttons) {
                const text = (node.textContent || '').trim().toLowerCase();
                if (text === 'alerts') {
                  node.click?.();
                  return true;
                }
              }
              return false;
            }
            """
        )
        if opened:
            await page.wait_for_timeout(500)
        return await page.evaluate(
            """
            ({ pair, timeframe }) => {
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const panelCandidates = Array.from(document.querySelectorAll('aside, section, div, [role="complementary"], [role="dialog"]'))
                .filter((node) => {
                  const rect = node.getBoundingClientRect?.();
                  if (!rect || rect.width <= 0 || rect.height <= 0) return false;
                  const text = normalize(node.textContent || '');
                  if (!text.includes('alerts')) return false;
                  return rect.left > window.innerWidth * 0.55;
                });
              const panel = panelCandidates.sort((a, b) => {
                const aRect = a.getBoundingClientRect();
                const bRect = b.getBoundingClientRect();
                return (bRect.width * bRect.height) - (aRect.width * aRect.height);
              })[0];
              if (!panel) return false;
              const body = normalize(panel.innerText || panel.textContent || '');
              const wantedPair = normalize(pair);
              const wantedTf = normalize(timeframe);
              return body.includes(wantedPair) && body.includes(wantedTf) && body.includes('s&d algo [pro]');
            }
            """,
            {"pair": pair, "timeframe": timeframe},
        )

    async def _click_button(
        self,
        page: Any,
        labels: list[str],
        *,
        dialog_titles: list[str] | None = None,
    ) -> bool:
        if hasattr(page, "locator"):
            dialog = self._resolve_dialog_locator(page, dialog_titles)
            for label in labels:
                try:
                    locator = dialog.get_by_role("button", name=re.compile(rf"^{re.escape(label)}$", re.I))
                    if await locator.count() > 0:
                        await locator.first.click(force=True)
                        return True
                except Exception:
                    continue
        elif hasattr(page, "get_by_role"):
            for label in labels:
                locator = page.get_by_role("button", name=label, exact=False)
                try:
                    if await locator.count() > 0:
                        await locator.first.click()
                        return True
                except Exception:
                    continue
        for label in labels:
            coords = await page.evaluate(
                """
                ({ label, dialogTitles }) => {
                  const wanted = (label || '').trim().toLowerCase();
                  const wantedDialogs = Array.isArray(dialogTitles)
                    ? dialogTitles.map((title) => (title || '').trim().toLowerCase())
                    : [];
                  const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
                  const dialogs = Array.from(
                    document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
                  ).filter((el) => {
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                  });
                  const dialog = wantedDialogs.length
                    ? dialogs.find((el) => {
                        const text = normalize(el.textContent);
                        return wantedDialogs.some((title) => text.includes(title));
                      }) || dialogs[dialogs.length - 1] || document
                    : dialogs[dialogs.length - 1] || document;
                  const nodes = Array.from(dialog.querySelectorAll('button, [role="button"]'));
                  for (const node of nodes) {
                    const text = normalize(node.textContent);
                    if (!text) continue;
                    if (text === wanted) {
                      const clickable =
                        node.closest('button, [role="button"], [data-name], [class*="container"], [class*="content"]') ||
                        node;
                      const rect = clickable.getBoundingClientRect?.();
                      if (!rect || rect.width <= 0 || rect.height <= 0) continue;
                      return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
                    }
                  }
                  return null;
                }
                """,
                {"label": label, "dialogTitles": dialog_titles or []},
            )
            if coords:
                await page.mouse.click(coords["x"], coords["y"])
                return True
        return False

    def _resolve_dialog_locator(self, page: Any, dialog_titles: list[str] | None) -> Any:
        dialogs = page.locator('[role="dialog"], [class*="dialog"], [class*="modal"]')
        if not dialog_titles:
            return dialogs.last
        locator = dialogs
        for title in dialog_titles:
            locator = locator.filter(has_text=re.compile(re.escape(title), re.I))
        return locator.first


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
        created_alerts = 0
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
                if not deployed.skipped_existing:
                    created_alerts += 1
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
                        "skipped_existing": deployed.skipped_existing,
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
            "created_alerts": created_alerts,
            "running_pairs": 0,
            "pending_pairs": max(0, len(results) - completed - failed),
        }
        emit_event("batch_finished", None, {"status": status, "summary": summary})
        return {"status": status, "summary": summary}
