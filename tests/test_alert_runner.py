from __future__ import annotations

import asyncio
import logging
import sys
import threading
from typing import Any
from types import ModuleType, SimpleNamespace

from scripts.optimizer.alert_runner import (
    AlertBatchRunner,
    AlertDeployment,
    TradingViewAlertBrowser,
    TradingViewMcpAlertRunner,
    build_chart_symbol,
)
from scripts.optimizer import local_agent


class FakeAlertBrowser:
    def __init__(self, failures: set[str] | None = None, skipped: set[str] | None = None) -> None:
        self.failures = failures or set()
        self.skipped = skipped or set()
        self.deployments: list[dict[str, Any]] = []

    async def deploy_alert(
        self,
        *,
        pair: str,
        timeframe: str,
        config_snapshot: dict[str, Any],
        alert_name_prefix: str | None,
        webhook_url: str,
        should_stop,
    ) -> AlertDeployment:
        self.deployments.append(
            {
                "pair": pair,
                "timeframe": timeframe,
                "config_snapshot": config_snapshot,
                "alert_name_prefix": alert_name_prefix,
                "webhook_url": webhook_url,
            }
        )
        if pair in self.failures:
            raise RuntimeError(f"boom for {pair}")
        return AlertDeployment(
            pair=pair,
            timeframe=timeframe,
            config_snapshot=config_snapshot,
            alert_name=f"{pair} {timeframe}",
            alert_id=f"alert-{pair}",
            params=dict(config_snapshot.get("params") or {}),
            skipped_existing=pair in self.skipped,
        )


def test_tradingview_mcp_runner_falls_back_to_browser_on_failure() -> None:
    fallback_browser = FakeAlertBrowser()

    class FakeMcpRunner(TradingViewMcpAlertRunner):
        async def _run_tv(self, *args: str) -> dict[str, Any]:
            raise RuntimeError("mcp exploded")

    async def run() -> AlertDeployment:
        runner = FakeMcpRunner(fallback_factory=lambda: fallback_browser)
        return await runner.deploy_alert(
            pair="EURUSD",
            timeframe="5m",
            config_snapshot={"params": {"lookback": 20}},
            alert_name_prefix="TradeOps",
            webhook_url="https://example.test/webhook",
            should_stop=lambda: False,
        )

    result = asyncio.run(run())

    assert result.alert_id == "alert-EURUSD"
    assert fallback_browser.deployments[0]["pair"] == "EURUSD"


def test_build_chart_symbol_forces_vantage_prefix() -> None:
    assert build_chart_symbol("USDJPY") == "VANTAGE:USDJPY"
    assert build_chart_symbol("OANDA:USDJPY") == "VANTAGE:USDJPY"


def test_tradingview_mcp_runner_uses_vantage_chart_symbol() -> None:
    class FakeMcpRunner(TradingViewMcpAlertRunner):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[str, ...]] = []

        async def _run_tv(self, *args: str) -> dict[str, Any]:
            self.calls.append(args)
            return {"success": True}

        async def _apply_params(self, params: dict[str, Any]) -> None:
            return None

        async def _has_existing_alert(self, *, pair: str, timeframe: str) -> bool:
            return True

    runner = FakeMcpRunner()

    async def run() -> AlertDeployment:
        return await runner.deploy_alert(
            pair="USDJPY",
            timeframe="5m",
            config_snapshot={"params": {"lookback": 20}},
            alert_name_prefix="TradeOps",
            webhook_url="https://example.test/webhook",
            should_stop=lambda: False,
        )

    deployment = asyncio.run(run())

    assert deployment.skipped_existing is True
    assert ("symbol", "VANTAGE:USDJPY") in [call[0:2] for call in runner.calls]


def test_tradingview_mcp_runner_sets_message_before_webhook() -> None:
    class FakeMcpRunner(TradingViewMcpAlertRunner):
        def __init__(self) -> None:
            super().__init__()
            self.step_order: list[str] = []

        async def _run_tv(self, *args: str) -> dict[str, Any]:
            return {"success": True}

        async def _apply_params(self, params: dict[str, Any]) -> None:
            return None

        async def _has_existing_alert(self, *, pair: str, timeframe: str) -> bool:
            return False

        async def _open_alert_dialog(self) -> None:
            self.step_order.append("open")

        async def _select_alert_function_mode(self) -> None:
            self.step_order.append("mode")

        async def _set_optional_field(self, label: str, value: str) -> bool:
            if label == "Alert name":
                self.step_order.append("name")
            return True

        async def _set_message(self, message: str) -> None:
            self.step_order.append("message")

        async def _set_webhook_url(self, webhook_url: str) -> None:
            self.step_order.append("webhook")

        async def _submit_alert(self) -> None:
            self.step_order.append("submit")

    runner = FakeMcpRunner()

    asyncio.run(
        runner.deploy_alert(
            pair="USDJPY",
            timeframe="5m",
            config_snapshot={"params": {"lookback": 20}},
            alert_name_prefix="TradeOps",
            webhook_url="https://example.test/webhook",
            should_stop=lambda: False,
        )
    )

    assert runner.step_order == ["open", "mode", "name", "message", "webhook", "submit"]


def test_mcp_open_settings_waits_for_broad_visible_dialog_selector() -> None:
    class FakeMcpRunner(TradingViewMcpAlertRunner):
        def __init__(self) -> None:
            super().__init__()
            self.wait_expression = ""

        async def _ui_eval(self, expression: str) -> Any:
            if "const label = Array.from(document.querySelectorAll('div, span'))" in expression:
                return {"x": 10, "y": 10}
            if "for (const btn of document.querySelectorAll('[title=\"Settings\"]'))" in expression:
                return None
            return False

        async def _ui_mouse_click(self, x: float, y: float, *, double_click: bool = False) -> dict[str, Any]:
            return {"ok": True}

        async def _wait_until(self, expression: str, *, timeout_s: float = 10.0, interval_s: float = 0.3) -> Any:
            self.wait_expression = expression
            return True

    runner = FakeMcpRunner()
    asyncio.run(runner._open_settings())

    assert '[role="dialog"]' in runner.wait_expression
    assert '[class*="dialog-"][class*="rounded"]' not in runner.wait_expression


def test_mcp_apply_params_raises_on_verification_mismatch() -> None:
    class FakeMcpRunner(TradingViewMcpAlertRunner):
        async def _open_settings(self) -> None:
            return None

        async def _ui_eval(self, expression: str) -> Any:
            if "if (b.textContent?.trim() === 'Inputs')" in expression:
                return True
            if "const checks =" in expression:
                return {
                    "max_zones": "20",
                    "use_break_even": True,
                }
            if "const ok = Array.from(dialog.querySelectorAll('button')).find" in expression:
                return True
            return False

        async def _ensure_custom_profile(self) -> bool:
            return True

        async def _set_input(self, index: int, value: Any) -> None:
            return None

        async def _toggle_checkbox(self, index: int, desired_state: bool) -> None:
            return None

        async def _wait_until(self, expression: str, *, timeout_s: float = 10.0, interval_s: float = 0.3) -> Any:
            return True

        async def _wait_for_update_complete(self) -> None:
            return None

    runner = FakeMcpRunner()

    try:
        asyncio.run(runner._apply_params({"max_zones": 28, "use_break_even": True}))
        assert False, "expected verification mismatch"
    except RuntimeError as exc:
        assert "max_zones" in str(exc)


def test_mcp_apply_params_retries_after_initial_verification_mismatch() -> None:
    class FakeMcpRunner(TradingViewMcpAlertRunner):
        def __init__(self) -> None:
            super().__init__()
            self.verify_calls = 0
            self.inputs_set: list[tuple[int, Any]] = []
            self.toggles_set: list[tuple[int, bool]] = []

        async def _open_settings(self) -> None:
            return None

        async def _ui_eval(self, expression: str) -> Any:
            if "if (b.textContent?.trim() === 'Inputs')" in expression:
                return True
            if "const checks =" in expression:
                self.verify_calls += 1
                if self.verify_calls == 1:
                    return {
                        "max_zones": "20",
                        "use_break_even": True,
                    }
                return {
                    "max_zones": "28",
                    "use_break_even": True,
                }
            if "const ok = Array.from(dialog.querySelectorAll('button')).find" in expression:
                return True
            return False

        async def _ensure_custom_profile(self) -> bool:
            return True

        async def _set_input(self, index: int, value: Any) -> None:
            self.inputs_set.append((index, value))

        async def _toggle_checkbox(self, index: int, desired_state: bool) -> None:
            self.toggles_set.append((index, desired_state))

        async def _wait_until(self, expression: str, *, timeout_s: float = 10.0, interval_s: float = 0.3) -> Any:
            return True

        async def _wait_for_update_complete(self) -> None:
            return None

    runner = FakeMcpRunner()
    asyncio.run(runner._apply_params({"max_zones": 28, "use_break_even": True}))

    assert runner.verify_calls == 2
    assert runner.inputs_set.count((8, 28)) == 2


def test_alert_batch_runner_emits_progress_and_summary() -> None:
    batch = {
        "id": "batch-1",
        "timeframe": "5m",
        "pairs": ["EURUSD", "GBPUSD"],
        "config_snapshot": [
            {
                "pair": "EURUSD",
                "timeframe": "5m",
                "params": {"lookback": 20},
                "risk_weight": 0.75,
            },
            {
                "pair": "GBPUSD",
                "timeframe": "5m",
                "params": {"lookback": 30},
                "risk_weight": 0.5,
            },
        ],
        "alert_name_prefix": "TradeOps",
        "webhook_url": "https://example.test/webhook",
    }
    browser = FakeAlertBrowser(failures={"GBPUSD"})
    events: list[dict[str, Any]] = []

    async def run() -> dict[str, Any]:
        runner = AlertBatchRunner(browser_factory=lambda: browser)
        return await runner.run(
            batch,
            emit_event=lambda event_type, pair, payload: events.append(
                {"event_type": event_type, "pair": pair, "payload": payload}
            ),
            should_stop=lambda: False,
        )

    result = asyncio.run(run())

    assert len(browser.deployments) == 2
    assert result["status"] == "failed"
    assert result["summary"]["completed_pairs"] == 1
    assert result["summary"]["failed_pairs"] == 1
    assert result["summary"]["created_alerts"] == 1
    assert [event["event_type"] for event in events] == [
        "pair_started",
        "alert_created",
        "pair_completed",
        "pair_started",
        "pair_failed",
        "batch_finished",
    ]
    assert events[1]["payload"]["alert_id"] == "alert-EURUSD"
    assert events[4]["payload"]["error_message"] == "boom for GBPUSD"


def test_alert_batch_runner_does_not_count_skipped_existing_as_created() -> None:
    batch = {
        "id": "batch-skip",
        "timeframe": "5m",
        "pairs": ["EURUSD"],
        "config_snapshot": [
            {
                "pair": "EURUSD",
                "timeframe": "5m",
                "params": {"lookback": 20},
                "risk_weight": 0.75,
            },
        ],
        "alert_name_prefix": "TradeOps",
        "webhook_url": "https://example.test/webhook",
    }
    browser = FakeAlertBrowser(skipped={"EURUSD"})
    events: list[dict[str, Any]] = []

    async def run() -> dict[str, Any]:
        runner = AlertBatchRunner(browser_factory=lambda: browser)
        return await runner.run(
            batch,
            emit_event=lambda event_type, pair, payload: events.append(
                {"event_type": event_type, "pair": pair, "payload": payload}
            ),
            should_stop=lambda: False,
        )

    result = asyncio.run(run())

    assert result["status"] == "completed"
    assert result["summary"]["completed_pairs"] == 1
    assert result["summary"]["created_alerts"] == 0
    assert [event["event_type"] for event in events] == [
        "pair_started",
        "pair_completed",
        "batch_finished",
    ]
    assert events[1]["payload"]["skipped_existing"] is True


def test_alert_batch_agent_updates_backend_state_without_browser(monkeypatch) -> None:
    batch = {
        "id": "batch-2",
        "status": "queued",
        "source_mode": "approved",
        "timeframe": "5m",
        "pairs": ["EURUSD"],
        "config_snapshot": [
            {
                "pair": "EURUSD",
                "timeframe": "5m",
                "params": {"lookback": 20},
                "risk_weight": 0.75,
            },
        ],
        "alert_name_prefix": "TradeOps",
        "webhook_url": "https://example.test/webhook",
    }
    patched_calls: list[tuple[str, str, dict[str, Any]]] = []
    posted_events: list[dict[str, Any]] = []
    state = {"status": "queued"}

    monkeypatch.setattr(local_agent, "ensure_chrome", lambda: True)

    def fake_api_get(path: str) -> dict[str, Any] | None:
        if path == "/api/alert-setup/batches/batch-2":
            return {**batch, "status": state["status"]}
        if path == "/api/alert-setup/batches?status=queued&limit=1":
            return {"batches": [{**batch, "status": state["status"]}]}
        return None

    def fake_api_patch(path: str, body: dict) -> dict[str, Any] | None:
        patched_calls.append(("PATCH", path, body.copy()))
        if path == "/api/alert-setup/batches/batch-2" and "status" in body:
            state["status"] = body["status"]
        return body

    def fake_api_post(path: str, body: dict | None = None) -> dict[str, Any] | None:
        posted_events.append({"path": path, "body": body.copy() if body else None})
        return body

    class FakeRunner:
        def __init__(self, browser_factory=None) -> None:
            self.browser_factory = browser_factory

        async def run(self, batch_payload, *, emit_event, should_stop=None):
            emit_event(
                "pair_started",
                "EURUSD",
                {
                    "timeframe": "5m",
                    "config_snapshot": batch_payload["config_snapshot"][0],
                    "params": {"lookback": 20},
                },
            )
            emit_event(
                "alert_created",
                "EURUSD",
                {
                    "alert_name": "TradeOps EURUSD 5m",
                    "alert_id": "alert-1",
                    "config_snapshot": batch_payload["config_snapshot"][0],
                    "details": {"pair": "EURUSD"},
                },
            )
            emit_event(
                "pair_completed",
                "EURUSD",
                {
                    "alert_name": "TradeOps EURUSD 5m",
                    "alert_id": "alert-1",
                    "config_snapshot": batch_payload["config_snapshot"][0],
                    "params": {"lookback": 20},
                },
            )
            emit_event(
                "batch_finished",
                None,
                {
                    "status": "completed",
                    "summary": {
                        "total_pairs": 1,
                        "pending_pairs": 0,
                        "running_pairs": 0,
                        "completed_pairs": 1,
                        "failed_pairs": 0,
                        "cancelled_pairs": 0,
                        "created_alerts": 1,
                    },
                },
            )
            return {
                "status": "completed",
                "summary": {
                    "total_pairs": 1,
                    "pending_pairs": 0,
                    "running_pairs": 0,
                    "completed_pairs": 1,
                    "failed_pairs": 0,
                    "cancelled_pairs": 0,
                    "created_alerts": 1,
                },
            }

    monkeypatch.setattr(local_agent, "api_get", fake_api_get)
    monkeypatch.setattr(local_agent, "api_patch", fake_api_patch)
    monkeypatch.setattr(local_agent, "api_post", fake_api_post)
    monkeypatch.setattr(local_agent, "AlertBatchRunner", FakeRunner)

    asyncio.run(local_agent._execute_alert_batch(batch, threading.Event()))

    assert state["status"] == "completed"
    assert any(
        path == "/api/alert-setup/batches/batch-2" and body.get("status") == "running"
        for _, path, body in patched_calls
    )
    assert any(
        path == "/api/alert-setup/batches/batch-2/results/EURUSD"
        and body.get("status") == "running"
        for _, path, body in patched_calls
    )
    assert any(
        path == "/api/alert-setup/batches/batch-2/results/EURUSD"
        and body.get("status") == "created"
        for _, path, body in patched_calls
    )
    assert any(
        event["path"] == "/api/alert-setup/batches/batch-2/events"
        and event["body"]["event_type"] == "batch_finished"
        for event in posted_events
    )


def test_alert_batch_agent_prefers_mcp_when_healthy(monkeypatch) -> None:
    batch = {
        "id": "batch-mcp",
        "status": "queued",
        "source_mode": "approved",
        "timeframe": "5m",
        "pairs": ["EURUSD"],
        "config_snapshot": [
            {
                "pair": "EURUSD",
                "timeframe": "5m",
                "params": {"lookback": 20},
                "risk_weight": 0.75,
            },
        ],
        "alert_name_prefix": "TradeOps",
        "webhook_url": "https://example.test/webhook",
    }
    posted_events: list[dict[str, Any]] = []
    captured_backend: dict[str, str] = {}
    state = {"status": "queued"}

    monkeypatch.setattr(local_agent, "ensure_chrome", lambda: True)
    monkeypatch.setattr(local_agent, "_playwright_available", lambda: False)

    async def fake_healthcheck(cli_path=None):
        return True, "ok"

    monkeypatch.setattr(local_agent.TradingViewMcpAlertRunner, "healthcheck", fake_healthcheck)

    def fake_api_get(path: str) -> dict[str, Any] | None:
        if path == "/api/alert-setup/batches/batch-mcp":
            return {**batch, "status": state["status"]}
        return None

    def fake_api_patch(path: str, body: dict) -> dict[str, Any] | None:
        if path == "/api/alert-setup/batches/batch-mcp" and "status" in body:
            state["status"] = body["status"]
        return body

    def fake_api_post(path: str, body: dict | None = None) -> dict[str, Any] | None:
        posted_events.append({"path": path, "body": body.copy() if body else None})
        return body

    class FakeRunner:
        def __init__(self, browser_factory=None) -> None:
            browser = browser_factory()
            captured_backend["name"] = type(browser).__name__

        async def run(self, batch_payload, *, emit_event, should_stop=None):
            emit_event(
                "batch_finished",
                None,
                {
                    "status": "completed",
                    "summary": {
                        "total_pairs": 1,
                        "pending_pairs": 0,
                        "running_pairs": 0,
                        "completed_pairs": 1,
                        "failed_pairs": 0,
                        "cancelled_pairs": 0,
                        "created_alerts": 1,
                    },
                },
            )
            return {
                "status": "completed",
                "summary": {
                    "total_pairs": 1,
                    "pending_pairs": 0,
                    "running_pairs": 0,
                    "completed_pairs": 1,
                    "failed_pairs": 0,
                    "cancelled_pairs": 0,
                    "created_alerts": 1,
                },
            }

    monkeypatch.setattr(local_agent, "api_get", fake_api_get)
    monkeypatch.setattr(local_agent, "api_patch", fake_api_patch)
    monkeypatch.setattr(local_agent, "api_post", fake_api_post)
    monkeypatch.setattr(local_agent, "AlertBatchRunner", FakeRunner)

    asyncio.run(local_agent._execute_alert_batch(batch, threading.Event()))

    assert captured_backend["name"] == "TradingViewMcpAlertRunner"
    assert state["status"] == "completed"
    assert any(
        event["path"] == "/api/alert-setup/batches/batch-mcp/events"
        and event["body"]["event_type"] == "log"
        and event["body"]["payload"]["preferred_backend"] == "mcp"
        for event in posted_events
    )


def test_select_alert_function_mode_picks_alert_only() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.dropdown_open = False
            self.selected = False

        async def evaluate(self, script: str):
            if "const controls = Array.from(dialog.querySelectorAll" in script:
                return self.selected
            if "Order fills and alert() function calls" in script:
                self.dropdown_open = True
                return True
            if "text === 'alert() function calls only'" in script:
                if self.dropdown_open:
                    self.selected = True
                    return True
                return False
            return False

        async def wait_for_timeout(self, ms: int) -> None:
            return None

    page = FakePage()
    browser = TradingViewAlertBrowser()
    asyncio.run(browser._select_alert_function_mode(page))
    assert page.selected is True


def test_matches_source_metrics_accepts_already_configured_chart() -> None:
    class FakeWorker:
        async def _read_results(self, symbol: str, params: dict[str, Any]) -> Any:
            return SimpleNamespace(
                profit_factor=1.391,
                max_drawdown_pct=4.06,
                total_trades=370,
            )

    browser = TradingViewAlertBrowser()
    matched = asyncio.run(
        browser._matches_source_metrics(
            FakeWorker(),
            "USDJPY",
            {
                "params": {"lookback": 20},
                "source_metrics": {
                    "profit_factor": 1.391,
                    "max_drawdown_pct": 4.06,
                    "total_trades": 370,
                },
            },
        )
    )
    assert matched is True


def test_has_existing_alert_detects_existing_pair() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.opened_alerts = False

        async def evaluate(self, script: str, payload: Any = None) -> Any:
            if "text === 'alerts'" in script:
                self.opened_alerts = True
                return True
            if isinstance(payload, dict) and payload.get("pair") == "USDJPY":
                return self.opened_alerts
            return False

        async def wait_for_timeout(self, ms: int) -> None:
            return None

    page = FakePage()
    browser = TradingViewAlertBrowser()
    exists = asyncio.run(browser._has_existing_alert(page, pair="USDJPY", timeframe="5m"))
    assert exists is True


def test_has_existing_alert_ignores_main_chart_text_without_alerts_panel_match() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.opened_alerts = False

        async def evaluate(self, script: str, payload: Any = None) -> Any:
            if "text === 'alerts'" in script:
                self.opened_alerts = True
                return True
            if isinstance(payload, dict) and payload.get("pair") == "USDJPY":
                return False
            return False

        async def wait_for_timeout(self, ms: int) -> None:
            return None

    page = FakePage()
    browser = TradingViewAlertBrowser()
    exists = asyncio.run(browser._has_existing_alert(page, pair="USDJPY", timeframe="5m"))
    assert exists is False


def test_set_field_expands_collapsed_row_before_fill() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.expanded = False
            self.filled = False

        async def evaluate(self, script: str, payload: dict[str, Any]) -> bool:
            label = payload["label"]
            value = payload["value"]
            if label != "Webhook URL" or value != "https://example.test/hook":
                return False
            self.expanded = True
            self.filled = True
            return True

    page = FakePage()
    browser = TradingViewAlertBrowser()
    asyncio.run(browser._set_field(page, "Webhook URL", "https://example.test/hook"))
    assert page.expanded is True
    assert page.filled is True


def test_set_webhook_url_uses_notifications_panel_fallback() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.notifications_opened = False
            self.webhook_filled = False
            self.waited_for_notifications = False
            self.waited_for_main = False
            self.apply_clicked = False
            self.main_dialog_already_mentions_notifications = True
            self.mouse = self.Mouse(self)

        class Mouse:
            def __init__(self, outer) -> None:
                self.outer = outer

            async def click(self, x: float, y: float) -> None:
                self.outer.notifications_opened = True

        async def evaluate(self, script: str, payload: Any = None) -> Any:
            if isinstance(payload, dict):
                if payload["label"] == "Webhook URL" and not self.notifications_opened:
                    return False
                if payload["label"] == "Webhook URL" and self.notifications_opened:
                    self.webhook_filled = True
                    return True
            if payload == "Notifications":
                return {"x": 10, "y": 10}
            if "headers.some((node) => normalize(node.textContent) === 'notifications')" in script:
                return self.notifications_opened
            if "headers.some((node) => normalize(node.textContent) === wanted)" in script:
                return self.notifications_opened
            if "text === wanted || text.startsWith(wanted + ' ')" in script:
                return {"x": 10, "y": 10}
            if "startsWith('webhook url ')" in script or "text === 'webhook url'" in script:
                return True
            if "includes('create alert on')" in script:
                return self.apply_clicked
            return False

        async def wait_for_function(self, script: str, title: str | None = None, timeout: int = 0, arg: Any = None) -> None:
            wanted = arg if arg is not None else title
            if wanted == ["Notifications"] or wanted == "Notifications":
                self.waited_for_notifications = True
            elif "create alert on" in script:
                self.waited_for_main = True

        async def wait_for_timeout(self, ms: int) -> None:
            return None

        def get_by_role(self, role: str, name: str, exact: bool = False):
            outer = self

            class FakeLocator:
                async def count(self) -> int:
                    return 1 if role == "button" and name == "Apply" else 0

                @property
                def first(self):
                    return self

                async def click(self) -> None:
                    outer.apply_clicked = True

            return FakeLocator()

    page = FakePage()
    browser = TradingViewAlertBrowser()
    asyncio.run(browser._set_webhook_url(page, "https://example.test/hook"))
    assert page.notifications_opened is True
    assert page.waited_for_notifications is True
    assert page.apply_clicked is True
    assert page.waited_for_main is True
    assert page.webhook_filled is True


def test_mcp_set_webhook_url_uses_notifications_panel_fallback() -> None:
    class FakeMcpRunner(TradingViewMcpAlertRunner):
        def __init__(self) -> None:
            super().__init__()
            self.notifications_opened = False
            self.webhook_filled = False
            self.waited_for_notifications = False
            self.waited_for_main = False
            self.apply_clicked = False

        async def _ui_eval(self, script: str) -> Any:
            if 'const wanted = "webhook url"' in script and "expanded = dialog.querySelector('input, textarea')" in script:
                if not self.notifications_opened:
                    return False
                self.webhook_filled = True
                return True
            if "text === wanted || text.startsWith(wanted + ' ')" in script:
                return {"x": 10, "y": 10}
            if "headers.some((node) => wanted.includes(normalize(node.textContent)))" in script:
                return self.notifications_opened
            if "normalize(node.textContent) === 'notifications'" in script and "button?.click?.()" in script:
                return True
            if 'const labels = ["apply"]' in script:
                return {"x": 20, "y": 20}
            if "normalize(el.textContent).includes('create alert on')" in script:
                return self.apply_clicked
            return False

        async def _ui_mouse_click(self, x: float, y: float, *, double_click: bool = False) -> dict[str, Any]:
            if x == 10 and y == 10:
                self.notifications_opened = True
            elif x == 20 and y == 20:
                self.apply_clicked = True
            return {"ok": True}

        async def _wait_until(self, expression: str, *, timeout_s: float = 10.0, interval_s: float = 0.3) -> Any:
            if "wanted.includes(normalize(node.textContent))" in expression:
                self.waited_for_notifications = True
                return True
            if "normalize(el.textContent).includes('create alert on')" in expression:
                self.waited_for_main = True
                return True
            return True

    runner = FakeMcpRunner()
    asyncio.run(runner._set_webhook_url("https://example.test/hook"))
    assert runner.notifications_opened is True
    assert runner.waited_for_notifications is True
    assert runner.apply_clicked is True
    assert runner.waited_for_main is True
    assert runner.webhook_filled is True


def test_set_message_uses_message_panel_fallback() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.message_opened = False
            self.message_filled = False
            self.waited_for_message = False
            self.waited_for_main = False
            self.apply_clicked = False
            self.mouse = self.Mouse(self)
            self.keyboard = self.Keyboard(self)

        class Mouse:
            def __init__(self, outer) -> None:
                self.outer = outer

            async def click(self, x: float, y: float) -> None:
                self.outer.message_opened = True

        class Keyboard:
            def __init__(self, outer) -> None:
                self.outer = outer

            async def press(self, key: str) -> None:
                return None

        async def evaluate(self, script: str, payload: Any = None) -> Any:
            if isinstance(payload, dict):
                if payload.get("panelTitles") == ["edit message", "message"] and self.message_opened:
                    self.message_filled = True
                    return True
                if payload.get("label") == "Message" and not self.message_opened:
                    return False
            if payload == "Message":
                return {"x": 10, "y": 10}
            if payload == "Apply":
                return {"x": 10, "y": 10}
            if "create alert on" in script:
                return self.apply_clicked
            return False

        async def wait_for_function(self, script: str, title: str | None = None, timeout: int = 0, arg: Any = None) -> None:
            wanted = arg if arg is not None else title
            if wanted == ["Edit message", "Message"] or wanted == ["Edit message", "Message"]:
                self.waited_for_message = True
            elif wanted == "Message":
                self.waited_for_message = True
            elif "create alert on" in script:
                self.waited_for_main = True

        async def wait_for_timeout(self, ms: int) -> None:
            return None

        def get_by_role(self, role: str, name: str, exact: bool = False):
            outer = self

            class FakeLocator:
                async def count(self) -> int:
                    return 1 if role == "button" and name == "Apply" else 0

                @property
                def first(self):
                    return self

                async def click(self) -> None:
                    outer.apply_clicked = True

            return FakeLocator()

    page = FakePage()
    browser = TradingViewAlertBrowser()
    asyncio.run(browser._set_message(page, '{"ok":true}'))
    assert page.message_opened is True
    assert page.waited_for_message is True
    assert page.apply_clicked is True
    assert page.waited_for_main is True
    assert page.message_filled is True


def test_click_button_falls_back_to_mouse_click() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.clicked = False
            self.mouse = self.Mouse(self)

        class Mouse:
            def __init__(self, outer) -> None:
                self.outer = outer

            async def click(self, x: float, y: float) -> None:
                self.outer.clicked = True

        def get_by_role(self, role: str, name: str, exact: bool = False):
            class FakeLocator:
                async def count(self) -> int:
                    return 0

                @property
                def first(self):
                    return self

                async def click(self) -> None:
                    return None

            return FakeLocator()

        async def evaluate(self, script: str, payload: Any = None) -> Any:
            if isinstance(payload, dict) and payload.get("label") == "Create":
                return {"x": 20, "y": 20}
            return None

    page = FakePage()
    browser = TradingViewAlertBrowser()
    clicked = asyncio.run(browser._click_button(page, ["Create"]))
    assert clicked is True
    assert page.clicked is True


def test_click_button_does_not_treat_header_as_create_button() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.clicked = False
            self.mouse = self.Mouse(self)

        class Mouse:
            def __init__(self, outer) -> None:
                self.outer = outer

            async def click(self, x: float, y: float) -> None:
                self.outer.clicked = True

        def get_by_role(self, role: str, name: str, exact: bool = False):
            class FakeLocator:
                async def count(self) -> int:
                    return 0

                @property
                def first(self):
                    return self

                async def click(self) -> None:
                    return None

            return FakeLocator()

        async def evaluate(self, script: str, payload: Any = None) -> Any:
            # The fallback should only accept actual buttons, not the
            # "Create alert on ..." header text.
            if isinstance(payload, dict) and payload.get("label") == "Create":
                return {"x": 20, "y": 20}
            return None

    page = FakePage()
    browser = TradingViewAlertBrowser()
    clicked = asyncio.run(browser._click_button(page, ["Create"]))
    assert clicked is True
    assert page.clicked is True


def test_submit_alert_closes_main_dialog() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.clicked = False
            self.enter_pressed = False
            self.closed = False
            self.mouse = self.Mouse(self)
            self.keyboard = self.Keyboard(self)

        class Mouse:
            def __init__(self, outer) -> None:
                self.outer = outer

            async def click(self, x: float, y: float) -> None:
                self.outer.clicked = True
                self.outer.closed = True

        class Keyboard:
            def __init__(self, outer) -> None:
                self.outer = outer

            async def press(self, key: str) -> None:
                self.outer.enter_pressed = True
                if key == "Enter":
                    self.outer.closed = True

        def get_by_role(self, role: str, name: str, exact: bool = False):
            class FakeLocator:
                async def count(self) -> int:
                    return 0

                @property
                def first(self):
                    return self

                async def click(self) -> None:
                    return None

            return FakeLocator()

        async def evaluate(self, script: str, payload: Any = None) -> Any:
            if isinstance(payload, dict) and payload.get("label") == "Create":
                return {"x": 20, "y": 20}
            if "create alert on" in script:
                return self.closed
            return None

        async def wait_for_timeout(self, ms: int) -> None:
            return None

        async def wait_for_function(self, script: str, title: str | None = None, timeout: int = 0, arg: Any = None) -> None:
            return None

    page = FakePage()
    browser = TradingViewAlertBrowser()
    asyncio.run(browser._submit_alert(page))
    assert page.clicked is True
    assert page.closed is True


def test_prepare_pair_chart_page_retries_with_fresh_tab() -> None:
    class FakePage:
        def __init__(self, label: str) -> None:
            self.label = label
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    class FakeWorker:
        attempts: list[str] = []

        def __init__(self, page: Any, optimizer: Any) -> None:
            self.page = page

        async def _switch_symbol(self, symbol: str) -> None:
            FakeWorker.attempts.append(self.page.label)
            if self.page.label == "first":
                raise RuntimeError("Symbol switch failed: expected GBPNZD, observed XAUUSD")

    pages = [FakePage("first"), FakePage("second")]

    async def fake_ensure_tabs(browser: Any, required_tabs: int, pair: str) -> list[Any]:
        return []

    browser = SimpleNamespace(contexts=[])
    alert_browser = TradingViewAlertBrowser()
    call_count = {"value": 0}

    async def fake_open_pair_chart_page(browser: Any, pair: str, ensure_tabs: Any) -> tuple[Any, bool]:
        idx = call_count["value"]
        call_count["value"] += 1
        return pages[idx], True

    alert_browser._open_pair_chart_page = fake_open_pair_chart_page  # type: ignore[method-assign]

    page, created = asyncio.run(
        alert_browser._prepare_pair_chart_page(
            browser,
            "GBPNZD",
            fake_ensure_tabs,
            FakeWorker,
            optimizer_factory=lambda: object(),
        )
    )

    assert created is True
    assert page is pages[1]
    assert pages[0].closed is True
    assert FakeWorker.attempts == ["first", "second"]


def test_deploy_alert_does_not_force_last_365_days(monkeypatch) -> None:
    class FakeKeyboard:
        async def press(self, key: str) -> None:
            return None

    class FakePage:
        def __init__(self) -> None:
            self.keyboard = FakeKeyboard()

        def on(self, event: str, callback: Any) -> None:
            return None

        async def wait_for_timeout(self, ms: int) -> None:
            return None

        async def close(self) -> None:
            return None

    class FakeBrowser:
        contexts: list[Any] = []

    class FakePlaywrightContext:
        class Chromium:
            async def connect_over_cdp(self, url: str) -> Any:
                return FakeBrowser()

        def __init__(self) -> None:
            self.chromium = self.Chromium()

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeOptimizer:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class FakeTabWorker:
        applied_params: list[dict[str, Any]] = []
        alert_apply_called = False
        optimizer_apply_called = False

        def __init__(self, page: Any, optimizer: Any) -> None:
            self.page = page
            self.optimizer = optimizer

        async def _switch_symbol(self, symbol: str) -> None:
            return None

        async def _apply_params(self, params: dict[str, Any]) -> Any:
            FakeTabWorker.optimizer_apply_called = True
            raise AssertionError("alert setup should not use optimizer retry apply path")

        async def _apply_params_for_alert(self, params: dict[str, Any]) -> Any:
            FakeTabWorker.alert_apply_called = True
            FakeTabWorker.applied_params.append(params.copy())
            return SimpleNamespace(ok=True, fresh=True, reason="")

    playwright_module = ModuleType("playwright")
    async_api_module = ModuleType("playwright.async_api")
    async_api_module.async_playwright = lambda: FakePlaywrightContext()
    parallel_runner_module = ModuleType("scripts.optimizer.parallel_runner")
    optimizer_module = ModuleType("scripts.optimizer.optimizer")
    tab_worker_module = ModuleType("scripts.optimizer.tab_worker")

    async def fake_ensure_tradingview_tabs(browser: Any, required_tabs: int, pair: str) -> list[Any]:
        return []

    parallel_runner_module.ensure_tradingview_tabs = fake_ensure_tradingview_tabs
    optimizer_module.TradingViewOptimizer = FakeOptimizer
    tab_worker_module.TabWorker = FakeTabWorker

    monkeypatch.setitem(sys.modules, "playwright", playwright_module)
    monkeypatch.setitem(sys.modules, "playwright.async_api", async_api_module)
    monkeypatch.setitem(sys.modules, "scripts.optimizer.parallel_runner", parallel_runner_module)
    monkeypatch.setitem(sys.modules, "scripts.optimizer.optimizer", optimizer_module)
    monkeypatch.setitem(sys.modules, "scripts.optimizer.tab_worker", tab_worker_module)

    page = FakePage()
    browser = TradingViewAlertBrowser()

    async def fake_prepare_pair_chart_page(*args: Any, **kwargs: Any) -> tuple[Any, bool]:
        return page, False

    async def fake_has_existing_alert(page: Any, *, pair: str, timeframe: str) -> bool:
        return False

    async def fake_wait_for_alert_dialog(page: Any) -> None:
        return None

    async def fake_select_alert_function_mode(page: Any) -> None:
        return None

    async def fake_set_optional_field(page: Any, label: str, value: str) -> None:
        return None

    async def fake_set_webhook_url(page: Any, webhook_url: str) -> None:
        return None

    async def fake_submit_alert(page: Any) -> None:
        return None

    monkeypatch.setattr(browser, "_prepare_pair_chart_page", fake_prepare_pair_chart_page)
    monkeypatch.setattr(browser, "_has_existing_alert", fake_has_existing_alert)
    monkeypatch.setattr(browser, "_wait_for_alert_dialog", fake_wait_for_alert_dialog)
    monkeypatch.setattr(browser, "_select_alert_function_mode", fake_select_alert_function_mode)
    monkeypatch.setattr(browser, "_set_optional_field", fake_set_optional_field)
    monkeypatch.setattr(browser, "_set_webhook_url", fake_set_webhook_url)
    monkeypatch.setattr(browser, "_submit_alert", fake_submit_alert)

    deployment = asyncio.run(
        browser.deploy_alert(
            pair="USDJPY",
            timeframe="5m",
            config_snapshot={"params": {"pvtMax": 12}},
            alert_name_prefix="TradeOps",
            webhook_url="https://example.test/webhook",
            should_stop=lambda: False,
        )
    )

    assert deployment.pair == "USDJPY"
    assert FakeTabWorker.optimizer_apply_called is False
    assert FakeTabWorker.alert_apply_called is True
    assert FakeTabWorker.applied_params == [{"pvtMax": 12}]


def test_process_line_logs_plain_runner_output_locally(caplog, monkeypatch) -> None:
    posted: list[dict[str, Any]] = []

    def fake_api_post(path: str, body: dict | None = None) -> dict | None:
        posted.append({"path": path, "body": body})
        return body

    monkeypatch.setattr(local_agent, "api_post", fake_api_post)
    caplog.set_level(logging.INFO, logger="optimizer-agent")

    local_agent._process_line("run-1", "Traceback: boom")

    assert any("run run-1" in record.getMessage() and "Traceback: boom" in record.getMessage() for record in caplog.records)
    assert posted == [
        {
            "path": "/api/optimizer/runs/run-1/events",
            "body": {"event_type": "log", "payload": {"message": "Traceback: boom"}},
        }
    ]


def test_process_line_logs_when_backend_event_post_fails(caplog, monkeypatch) -> None:
    def fake_api_post(path: str, body: dict | None = None) -> dict | None:
        raise RuntimeError("backend down")

    monkeypatch.setattr(local_agent, "api_post", fake_api_post)
    caplog.set_level(logging.INFO, logger="optimizer-agent")

    local_agent._process_line("run-1", "worker exploded")

    messages = [record.getMessage() for record in caplog.records]
    assert any("worker exploded" in message for message in messages)
    assert any("Failed to forward optimizer run output" in message for message in messages)
