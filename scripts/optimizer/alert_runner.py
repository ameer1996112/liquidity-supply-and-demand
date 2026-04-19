from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from math import isclose
from pathlib import Path
from typing import Any, Callable, Protocol

from scripts.optimizer.config import INPUT_INDEX
from scripts.optimizer.tradingview_mcp import DEFAULT_TV_CLI_PATH, TradingViewMcpClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LOADING_INDICATORS = [
    "Updating report",
    "Calculating...",
    "Loading...",
    "Compiling...",
]


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


def build_chart_symbol(pair: str) -> str:
    clean_pair = str(pair).split(":")[-1].strip().upper()
    if not clean_pair:
        raise ValueError("pair is required to build a chart symbol")
    return f"VANTAGE:{clean_pair}"


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


class TradingViewMcpAlertRunner:
    def __init__(
        self,
        *,
        cli_path: Path | None = None,
        fallback_factory: Callable[[], AlertBrowser] | None = None,
    ) -> None:
        self._client = TradingViewMcpClient(cli_path=cli_path or DEFAULT_TV_CLI_PATH)
        self._fallback_factory = fallback_factory

    @classmethod
    async def healthcheck(cls, cli_path: Path | None = None) -> tuple[bool, str]:
        runner = cls(cli_path=cli_path)
        return await runner._client.healthcheck()

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

        alert_name = build_alert_name(alert_name_prefix, pair, timeframe)
        params = dict(config_snapshot.get("params") or {})
        message = build_alert_message(
            config_snapshot,
            batch_id=str(config_snapshot.get("batch_id") or config_snapshot.get("source_run_id") or ""),
            pair=pair,
            timeframe=timeframe,
            alert_name=alert_name,
        )

        try:
            await self._run_tv("symbol", build_chart_symbol(pair))
            await self._run_tv("timeframe", self._normalize_timeframe(timeframe))
            await self._apply_params(params)
            if await self._has_existing_alert(pair=pair, timeframe=timeframe):
                return AlertDeployment(
                    pair=pair,
                    timeframe=timeframe,
                    config_snapshot=config_snapshot,
                    alert_name=alert_name,
                    alert_id=f"{pair.lower()}-{timeframe}",
                    params=params,
                    skipped_existing=True,
                )
            await self._open_alert_dialog()
            await self._select_alert_function_mode()
            await self._set_optional_field("Alert name", alert_name)
            await self._set_message(message)
            await self._set_webhook_url(webhook_url)
            await self._submit_alert()
            return AlertDeployment(
                pair=pair,
                timeframe=timeframe,
                config_snapshot=config_snapshot,
                alert_name=alert_name,
                alert_id=f"{pair.lower()}-{timeframe}",
                params=params,
            )
        except AlertBatchCancelled:
            raise
        except Exception:
            if self._fallback_factory is None:
                raise
            fallback = self._fallback_factory()
            return await fallback.deploy_alert(
                pair=pair,
                timeframe=timeframe,
                config_snapshot=config_snapshot,
                alert_name_prefix=alert_name_prefix,
                webhook_url=webhook_url,
                should_stop=should_stop,
            )

    async def _run_tv(self, *args: str) -> dict[str, Any]:
        return await self._client.run(*args)

    async def _ui_eval(self, expression: str) -> Any:
        result = await self._run_tv("ui", "eval", expression)
        return result.get("result")

    async def _ui_keyboard(self, key: str, modifiers: list[str] | None = None) -> dict[str, Any]:
        args = ["ui", "keyboard"]
        for modifier in modifiers or []:
            args.append(f"--{modifier}")
        args.append(key)
        return await self._run_tv(*args)

    async def _ui_mouse_click(self, x: float, y: float, *, double_click: bool = False) -> dict[str, Any]:
        args = ["ui", "mouse", str(x), str(y)]
        if double_click:
            args.append("--double")
        return await self._run_tv(*args)

    async def _wait_until(self, expression: str, *, timeout_s: float = 10.0, interval_s: float = 0.3) -> Any:
        deadline = asyncio.get_running_loop().time() + timeout_s
        last_value: Any = None
        while asyncio.get_running_loop().time() < deadline:
            last_value = await self._ui_eval(expression)
            if last_value:
                return last_value
            await asyncio.sleep(interval_s)
        raise RuntimeError(f"Timed out waiting for MCP condition: {expression[:120]}")

    @staticmethod
    def _visible_dialog_expr() -> str:
        return """
            (() => {
              const dialogs = Array.from(document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]'))
                .filter((el) => {
                  const rect = el.getBoundingClientRect();
                  const style = window.getComputedStyle?.(el);
                  return rect.width > 0 && rect.height > 0 &&
                    style?.visibility !== 'hidden' && style?.display !== 'none';
                });
              return dialogs[dialogs.length - 1] || null;
            })()
        """

    def _inject_visible_dialog(self, script: str) -> str:
        return script.replace("__VISIBLE_DIALOG__", self._visible_dialog_expr())

    async def _open_settings(self) -> None:
        already_open = await self._ui_eval(
            self._inject_visible_dialog(
                """
            (() => {
              const d = __VISIBLE_DIALOG__;
              return !!(d && d.offsetParent !== null);
            })()
            """
            )
        )
        if already_open:
            return
        coords = await self._ui_eval(
            """
            (() => {
              const visible = (el) => {
                const rect = el?.getBoundingClientRect?.();
                return !!rect && rect.width > 0 && rect.height > 0;
              };
              const label = Array.from(document.querySelectorAll('div, span'))
                .find((el) => el.textContent?.trim() === 'S&D Algo [Pro]' && visible(el));
              if (!label) return null;
              const box = label.getBoundingClientRect();
              return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
            })()
            """
        )
        if not coords:
            raise RuntimeError("could not locate S&D Algo [Pro] legend label for MCP settings open")
        await self._ui_mouse_click(coords["x"], coords["y"])
        await asyncio.sleep(0.4)
        settings = await self._ui_eval(
            """
            (() => {
              for (const btn of document.querySelectorAll('[title="Settings"]')) {
                const box = btn.getBoundingClientRect();
                if (btn.offsetParent !== null && box.width > 0 && box.height > 0) {
                  return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
                }
              }
              return null;
            })()
            """
        )
        if not settings:
            await self._ui_mouse_click(coords["x"], coords["y"], double_click=True)
        else:
            await self._ui_mouse_click(settings["x"], settings["y"])
        await self._wait_until(
            self._inject_visible_dialog(
                """
            (() => {
              const d = __VISIBLE_DIALOG__;
              return !!(d && d.offsetParent !== null);
            })()
            """,
            ),
            timeout_s=8.0,
        )

    async def _apply_params(self, params: dict[str, Any]) -> None:
        await self._open_settings()
        await self._ui_eval(
            """
            (() => {
              for (const b of document.querySelectorAll('button')) {
                if (b.textContent?.trim() === 'Inputs') {
                  b.click();
                  return true;
                }
              }
              return false;
            })()
            """
        )
        await asyncio.sleep(0.3)
        if not await self._ensure_custom_profile():
            raise RuntimeError("could not ensure Custom profile in MCP settings flow")

        last_error: RuntimeError | None = None
        for attempt in range(2):
            rr_mode = params.get("rr_mode")
            if rr_mode is not None:
                await self._apply_rr_mode(str(rr_mode))
                await asyncio.sleep(0.1)

            for name, value in params.items():
                if name == "rr_mode":
                    continue
                idx = INPUT_INDEX.get(name)
                if idx is None:
                    continue
                if name in ("enable_ai_quality_filter", "use_break_even", "enable_double_tp"):
                    await self._toggle_checkbox(idx, bool(value))
                else:
                    await self._set_input(idx, value)

            try:
                await self._verify_applied_params(params)
                last_error = None
                break
            except RuntimeError as exc:
                last_error = exc
                if attempt == 1:
                    raise
                await asyncio.sleep(0.3)
        if last_error is not None:
            raise last_error

        await self._ui_eval(
            self._inject_visible_dialog(
                """
            (() => {
              const dialog = __VISIBLE_DIALOG__;
              if (!dialog) return false;
              const ok = Array.from(dialog.querySelectorAll('button')).find((btn) => btn.textContent?.trim() === 'Ok');
              if (ok) {
                ok.click();
                return true;
              }
              return false;
            })()
            """
            )
        )
        await self._wait_until(
            self._inject_visible_dialog(
                """
            (() => {
              const d = __VISIBLE_DIALOG__;
              return !d || d.offsetParent === null;
            })()
            """,
            ),
            timeout_s=8.0,
        )
        await self._wait_for_update_complete()

    async def _ensure_custom_profile(self) -> bool:
        profile = await self._ui_eval(
            self._inject_visible_dialog(
                """
            (() => {
              const d = __VISIBLE_DIALOG__;
              if (!d) return '';
              const combo = d.querySelector('button[role="combobox"]');
              return combo?.textContent?.trim() || '';
            })()
            """
            )
        )
        if profile == "Custom":
            return True
        opened = await self._ui_eval(
            self._inject_visible_dialog(
                """
            (() => {
              const d = __VISIBLE_DIALOG__;
              const combo = d?.querySelector('button[role="combobox"]');
              if (!combo) return false;
              combo.click();
              return true;
            })()
            """
            )
        )
        if not opened:
            return False
        await asyncio.sleep(0.4)
        selected = await self._ui_eval(
            """
            (() => {
              const visible = (el) => {
                const rect = el?.getBoundingClientRect?.();
                const style = window.getComputedStyle?.(el);
                return !!rect && rect.width > 0 && rect.height > 0 &&
                  style?.visibility !== 'hidden' && style?.display !== 'none';
              };
              for (const el of document.querySelectorAll('[role="option"], [class*="option"], [class*="item-"], li, button, [role="button"], [data-name]')) {
                if (el.textContent?.trim() === 'Custom' && visible(el)) {
                  el.click();
                  return true;
                }
              }
              return false;
            })()
            """
        )
        if not selected:
            return False
        await asyncio.sleep(0.4)
        profile = await self._ui_eval(
            self._inject_visible_dialog(
                """
            (() => {
              const d = __VISIBLE_DIALOG__;
              if (!d) return '';
              const combo = d.querySelector('button[role="combobox"]');
              return combo?.textContent?.trim() || '';
            })()
            """
            )
        )
        return profile == "Custom"

    async def _apply_rr_mode(self, mode: str) -> None:
        if mode == "dynamic":
            await self._toggle_checkbox(INPUT_INDEX["use_custom_rr"], False)
            return
        await self._toggle_checkbox(INPUT_INDEX["use_custom_rr"], True)
        await asyncio.sleep(0.1)
        await self._set_input(INPUT_INDEX["risk_reward_ratio"], mode.replace("fixed_", ""))

    async def _set_input(self, index: int, value: Any) -> None:
        ok = await self._ui_eval(
            self._inject_visible_dialog(
                f"""
            (() => {{
              const d = __VISIBLE_DIALOG__;
              if (!d) return false;
              const inputs = d.querySelectorAll('input');
              const input = {index} < inputs.length ? inputs[{index}] : null;
              if (!input || input.type === 'checkbox') return false;
              const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
              input.focus();
              input.select?.();
              if (nativeSetter) nativeSetter.call(input, {json.dumps(str(value))});
              else input.value = {json.dumps(str(value))};
              input.dispatchEvent(new Event('input', {{ bubbles: true }}));
              input.dispatchEvent(new Event('change', {{ bubbles: true }}));
              input.blur?.();
              return true;
            }})()
            """
            )
        )
        if not ok:
            raise RuntimeError(f"could not set MCP input index {index}")

    async def _toggle_checkbox(self, index: int, desired_state: bool) -> None:
        ok = await self._ui_eval(
            self._inject_visible_dialog(
                f"""
            (() => {{
              const d = __VISIBLE_DIALOG__;
              if (!d) return false;
              const inputs = d.querySelectorAll('input');
              const input = {index} < inputs.length ? inputs[{index}] : null;
              if (!input || input.type !== 'checkbox') return false;
              if (input.checked !== {str(desired_state).lower()}) {{
                input.click();
              }}
              return true;
            }})()
            """
            )
        )
        if not ok:
            raise RuntimeError(f"could not toggle MCP checkbox index {index}")

    async def _verify_applied_params(self, params: dict[str, Any]) -> None:
        checks = self._build_param_checks(params)
        if not checks:
            return

        observed = await self._ui_eval(
            self._inject_visible_dialog(
                f"""
            (() => {{
              const d = __VISIBLE_DIALOG__;
              if (!d) return null;
              const checks = {json.dumps(checks)};
              const inputs = Array.from(d.querySelectorAll('input'));
              const result = {{}};
              for (const check of checks) {{
                const input = check.index < inputs.length ? inputs[check.index] : null;
                if (!input) {{
                  result[check.name] = null;
                  continue;
                }}
                if (check.kind === 'checkbox') {{
                  result[check.name] = !!input.checked;
                  continue;
                }}
                result[check.name] = input.value ?? null;
              }}
              return result;
            }})()
            """
            )
        )
        if not isinstance(observed, dict):
            raise RuntimeError("could not read back MCP inputs for verification")

        mismatches: list[str] = []
        for check in checks:
            actual = observed.get(check["name"])
            if not self._matches_expected_value(actual, check["expected"], kind=check["kind"]):
                mismatches.append(f'{check["name"]} expected {check["expected"]} got {actual}')

        if mismatches:
            raise RuntimeError(f"MCP params did not stick after apply: {', '.join(mismatches)}")

    def _build_param_checks(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []

        rr_mode = params.get("rr_mode")
        if rr_mode is not None:
            mode = str(rr_mode).strip()
            if mode == "dynamic":
                checks.append({
                    "name": "use_custom_rr",
                    "index": INPUT_INDEX["use_custom_rr"],
                    "kind": "checkbox",
                    "expected": False,
                })
            elif mode.startswith("fixed_"):
                checks.append({
                    "name": "use_custom_rr",
                    "index": INPUT_INDEX["use_custom_rr"],
                    "kind": "checkbox",
                    "expected": True,
                })
                checks.append({
                    "name": "risk_reward_ratio",
                    "index": INPUT_INDEX["risk_reward_ratio"],
                    "kind": "number",
                    "expected": float(mode.replace("fixed_", "")),
                })

        for name, value in params.items():
            if name == "rr_mode":
                continue
            idx = INPUT_INDEX.get(name)
            if idx is None:
                continue
            kind = "checkbox" if name in {"enable_ai_quality_filter", "use_break_even", "enable_double_tp"} else "number"
            checks.append({
                "name": name,
                "index": idx,
                "kind": kind,
                "expected": bool(value) if kind == "checkbox" else value,
            })
        return checks

    def _matches_expected_value(self, actual: Any, expected: Any, *, kind: str) -> bool:
        if kind == "checkbox":
            return bool(actual) is bool(expected)

        if actual is None:
            return False

        try:
            actual_number = float(str(actual).strip())
        except (TypeError, ValueError):
            return False

        try:
            expected_number = float(expected)
        except (TypeError, ValueError):
            return False

        return isclose(actual_number, expected_number, rel_tol=0.0, abs_tol=0.05)

    async def _wait_for_update_complete(self) -> None:
        deadline = asyncio.get_running_loop().time() + 45.0
        seen_loading = False
        while asyncio.get_running_loop().time() < deadline:
            loading = await self._ui_eval(
                f"""
                (() => {{
                  const indicators = {json.dumps(_LOADING_INDICATORS)};
                  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
                  let node;
                  while ((node = walker.nextNode())) {{
                    const text = node.textContent?.trim();
                    if (!text || !indicators.includes(text)) continue;
                    const el = node.parentElement;
                    if (!el || el.offsetParent === null) continue;
                    return text;
                  }}
                  return null;
                }})()
                """
            )
            if loading:
                seen_loading = True
            elif seen_loading:
                return
            await asyncio.sleep(1.0)
        if not seen_loading:
            return
        raise RuntimeError("TradingView report update did not complete in MCP flow")

    async def _has_existing_alert(self, *, pair: str, timeframe: str) -> bool:
        result = await self._run_tv("alert", "list")
        alerts = list(result.get("alerts") or [])
        wanted_pair = pair.upper()
        wanted_resolution = self._normalize_timeframe(timeframe)
        for alert in alerts:
            symbol = str(alert.get("symbol") or "").upper()
            resolution = str(alert.get("resolution") or "").strip()
            if wanted_pair in symbol and self._normalize_timeframe(resolution) == wanted_resolution:
                return True
        return False

    async def _open_alert_dialog(self) -> None:
        await self._ui_keyboard("a", ["alt"])
        await self._wait_until(
            """
            (() => {
              const dialogs = Array.from(document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]'));
              return dialogs.some((node) => {
                const text = (node.textContent || '').trim();
                return text.includes('Create alert on') || text.includes('Condition') || text.includes('Notifications');
              });
            })()
            """,
            timeout_s=15.0,
        )

    async def _select_alert_function_mode(self) -> None:
        selected = await self._ui_eval(
            """
            (() => {
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const dialogs = Array.from(document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]'))
                .filter((el) => {
                  const rect = el.getBoundingClientRect();
                  return rect.width > 0 && rect.height > 0;
                });
              const dialog = dialogs.find((el) => normalize(el.textContent).includes('create alert on')) || dialogs[dialogs.length - 1] || document;
              const controls = Array.from(dialog.querySelectorAll('input, button, [role="button"], [role="combobox"], select, span, div'));
              return controls.some((node) => {
                const text = normalize(node.value ?? node.getAttribute?.('aria-label') ?? node.textContent);
                return text === 'alert() function calls only';
              });
            })()
            """
        )
        if selected:
            return
        opened = await self._ui_eval(
            """
            (() => {
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
            })()
            """
        )
        if not opened:
            raise RuntimeError("could not open MCP alert trigger mode dropdown")
        await asyncio.sleep(0.4)
        picked = await self._ui_eval(
            """
            (() => {
              const nodes = Array.from(document.querySelectorAll('[role="option"], button, div[role="button"], span'));
              for (const node of nodes) {
                if ((node.textContent || '').trim() === 'alert() function calls only') {
                  node.click();
                  return true;
                }
              }
              return false;
            })()
            """
        )
        if not picked:
            raise RuntimeError("could not select MCP alert() function calls only mode")

    async def _set_field(self, label: str, value: str) -> None:
        ok = await self._ui_eval(
            f"""
            (() => {{
              const wanted = {json.dumps(label.strip().lower())};
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const nodes = Array.from(document.querySelectorAll('label, span, div, button'));
              for (const node of nodes) {{
                const text = normalize(node.textContent);
                if (!text || !text.includes(wanted)) continue;
                const root = node.closest('label, [role="group"], [class*="container"], [class*="content"], [data-name]') || node.parentElement || document;
                const input = root.querySelector('input, textarea');
                if (input) {{
                  input.focus();
                  input.value = {json.dumps(value)};
                  input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                  input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                  return true;
                }}

                const clickable =
                  node.closest('button, [role="button"], [data-name], [class*="container"], [class*="content"]') ||
                  node;
                clickable.click?.();

                const activeDialogs = Array.from(
                  document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
                ).filter((el) => {{
                  const rect = el.getBoundingClientRect();
                  return rect.width > 0 && rect.height > 0;
                }});
                const dialog = activeDialogs[activeDialogs.length - 1] || document;
                const expanded = dialog.querySelector('input, textarea');
                if (expanded) {{
                  expanded.focus();
                  expanded.value = {json.dumps(value)};
                  expanded.dispatchEvent(new Event('input', {{ bubbles: true }}));
                  expanded.dispatchEvent(new Event('change', {{ bubbles: true }}));
                  return true;
                }}
              }}
              return false;
            }})()
            """
        )
        if not ok:
            raise RuntimeError(f"could not find alert field: {label}")

    async def _set_optional_field(self, label: str, value: str) -> bool:
        try:
            await self._set_field(label, value)
            return True
        except Exception:
            return False

    async def _open_labeled_panel(self, label: str) -> bool:
        coords = await self._ui_eval(
            f"""
            (() => {{
              const wanted = {json.dumps(label.strip().lower())};
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const dialogs = Array.from(
                document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
              ).filter((el) => {{
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              }});
              const mainDialog =
                dialogs.find((el) => normalize(el.textContent).includes('create alert on')) ||
                dialogs[dialogs.length - 1] ||
                document;
              const nodes = Array.from(mainDialog.querySelectorAll('button, [role="button"], div, span'));
              const matches = [];
              for (const node of nodes) {{
                const text = normalize(node.textContent);
                if (!text) continue;
                if (text === wanted || text.startsWith(wanted + ' ')) {{
                  const clickable =
                    node.closest('button, [role="button"], [data-name], [class*="container"], [class*="content"]') ||
                    node;
                  const rect = clickable.getBoundingClientRect?.();
                  if (!rect || rect.width <= 0 || rect.height <= 0) continue;
                  matches.push({{
                    text,
                    x: rect.left + rect.width / 2,
                    y: rect.top + rect.height / 2,
                  }});
                }}
              }}
              matches.sort((a, b) => a.text.length - b.text.length);
              return matches[0] || null;
            }})()
            """
        )
        if not coords:
            return False
        await self._ui_mouse_click(coords["x"], coords["y"])
        return True

    async def _wait_for_panel(self, *titles: str) -> None:
        wanted_titles = [title.strip().lower() for title in titles if title and title.strip()]
        await self._wait_until(
            f"""
            (() => {{
              const wanted = {json.dumps(wanted_titles)};
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const dialogs = Array.from(
                document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
              ).filter((el) => {{
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              }});
              return dialogs.some((el) => {{
                const headers = Array.from(el.querySelectorAll('button, span, div, h1, h2, h3'));
                return headers.some((node) => wanted.includes(normalize(node.textContent)));
              }});
            }})()
            """,
            timeout_s=5.0,
        )

    async def _wait_for_main_alert_dialog(self) -> None:
        await self._wait_until(
            """
            (() => {
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const dialogs = Array.from(
                document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
              ).filter((el) => {
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              });
              return dialogs.some((el) => normalize(el.textContent).includes('create alert on'));
            })()
            """,
            timeout_s=5.0,
        )

    async def _click_button(self, *labels: str) -> bool:
        normalized = [label.strip().lower() for label in labels if label and label.strip()]
        if not normalized:
            return False
        coords = await self._ui_eval(
            f"""
            (() => {{
              const labels = {json.dumps(normalized)};
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const dialogs = Array.from(
                document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
              ).filter((el) => {{
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              }});
              const dialog = dialogs[dialogs.length - 1] || document;
              const buttons = Array.from(dialog.querySelectorAll('button, [role="button"]'));
              for (const button of buttons) {{
                const text = normalize(button.textContent);
                if (!labels.includes(text)) continue;
                const rect = button.getBoundingClientRect?.();
                if (!rect || rect.width <= 0 || rect.height <= 0) continue;
                return {{ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }};
              }}
              return null;
            }})()
            """
        )
        if not coords:
            return False
        await self._ui_mouse_click(coords["x"], coords["y"])
        return True

    async def _set_active_panel_text(self, value: str, *, panel_titles: list[str]) -> None:
        ok = await self._ui_eval(
            f"""
            (() => {{
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const wanted = {json.dumps([title.strip().lower() for title in panel_titles if title and title.strip()])};
              const dialogs = Array.from(
                document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]')
              ).filter((el) => {{
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              }});
              const panel =
                dialogs.find((el) => {{
                  const headers = Array.from(el.querySelectorAll('button, span, div, h1, h2, h3'));
                  return headers.some((node) => wanted.includes(normalize(node.textContent)));
                }}) ||
                dialogs[dialogs.length - 1] ||
                null;
              if (!panel) return false;
              const input = panel.querySelector('textarea, input[type="text"], input:not([type]), [contenteditable="true"]');
              if (!input) return false;
              input.focus?.();
              if (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) input.value = {json.dumps(value)};
              else input.textContent = {json.dumps(value)};
              input.dispatchEvent(new Event('input', {{ bubbles: true }}));
              input.dispatchEvent(new Event('change', {{ bubbles: true }}));
              return true;
            }})()
            """
        )
        if not ok:
            raise RuntimeError("could not fill message editor")

    async def _set_webhook_url(self, webhook_url: str) -> None:
        if await self._set_optional_field("Webhook URL", webhook_url):
            return

        opened = await self._open_labeled_panel("Notifications")
        if opened:
            await asyncio.sleep(0.4)
            await self._wait_for_panel("Notifications")
            webhook_enabled = await self._ui_eval(
                """
                (() => {
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
                })()
                """
            )
            if webhook_enabled:
                await asyncio.sleep(0.4)
            await self._set_field("Webhook URL", webhook_url)
            applied = await self._click_button("Apply")
            if not applied:
                raise RuntimeError("could not find Notifications Apply button")
            await asyncio.sleep(0.4)
            await self._wait_for_main_alert_dialog()
            return

        raise RuntimeError("could not set MCP webhook URL")

    async def _set_message(self, message: str) -> None:
        opened = await self._open_labeled_panel("Message")
        if opened:
            await asyncio.sleep(0.4)
            await self._wait_for_panel("Edit message", "Message")
            await self._set_active_panel_text(message, panel_titles=["edit message", "message"])
            applied = await self._click_button("Apply")
            if not applied:
                raise RuntimeError("could not find Message Apply button")
            await asyncio.sleep(0.4)
            await self._wait_for_main_alert_dialog()
            return

        raise RuntimeError("could not set MCP alert message")

    async def _submit_alert(self) -> None:
        submitted = await self._ui_eval(
            """
            (() => {
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const dialogs = Array.from(document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]'))
                .filter((el) => {
                  const rect = el.getBoundingClientRect();
                  return rect.width > 0 && rect.height > 0;
                });
              const dialog = dialogs.find((el) => normalize(el.textContent).includes('create alert on')) || dialogs[dialogs.length - 1] || document;
              const button = Array.from(dialog.querySelectorAll('button, [role="button"]'))
                .find((btn) => {
                  const text = normalize(btn.textContent);
                  return text === 'create' || text === 'create alert';
                });
              if (!button) return false;
              button.click();
              return true;
            })()
            """
        )
        if not submitted:
            await self._ui_keyboard("Enter")
        await self._wait_until(
            """
            (() => {
              const normalize = (text) => (text || '').trim().toLowerCase().replace(/\\s+/g, ' ');
              const dialogs = Array.from(document.querySelectorAll('[role="dialog"], [class*="dialog"], [class*="modal"]'))
                .filter((el) => {
                  const rect = el.getBoundingClientRect();
                  return rect.width > 0 && rect.height > 0;
                });
              return !dialogs.some((el) => normalize(el.textContent).includes('create alert on'));
            })()
            """,
            timeout_s=8.0,
        )

    @staticmethod
    def _normalize_timeframe(timeframe: str) -> str:
        tf = str(timeframe).strip()
        if tf.endswith("m") and tf[:-1].isdigit():
            return tf[:-1]
        return tf


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
