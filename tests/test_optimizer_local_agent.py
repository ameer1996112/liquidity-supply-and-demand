from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from unittest import mock

import pytest


@pytest.fixture
def local_agent(monkeypatch):
    monkeypatch.setenv("API_URL", "https://example.test")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setenv("LOCAL_AGENT_TARGET", "optimizer")
    monkeypatch.setenv("_OPTIMIZER_VENV_ACTIVE", "1")
    sys.modules.pop("scripts.optimizer.local_agent", None)
    module = importlib.import_module("scripts.optimizer.local_agent")
    module._optimizer_run_blocked_events.clear()
    return module


class _FakeProcess:
    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.terminated = False
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        return self.exit_code

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


def _capture_http_calls(module, monkeypatch):
    patch_calls: list[tuple[str, dict]] = []
    post_calls: list[tuple[str, dict | None]] = []
    get_calls: list[str] = []

    monkeypatch.setattr(module, "api_patch", lambda path, body: patch_calls.append((path, body)) or {"ok": True})
    monkeypatch.setattr(module, "api_post", lambda path, body=None: post_calls.append((path, body)) or {"ok": True})
    monkeypatch.setattr(module, "api_get", lambda path: get_calls.append(path) or {"status": "running"})

    return patch_calls, post_calls, get_calls


def test_execute_run_blocks_without_claim_when_optimizer_readiness_fails(local_agent, monkeypatch):
    patch_calls, post_calls, _ = _capture_http_calls(local_agent, monkeypatch)

    monkeypatch.setattr(local_agent, "_playwright_available", lambda: True)

    controller = mock.Mock()
    controller.ensure_ready = mock.AsyncMock(side_effect=RuntimeError("TradingView MCP desktop workspace is not ready"))
    controller._list_workspace_tabs = mock.AsyncMock()
    monkeypatch.setattr(local_agent, "OptimizerMcpController", mock.Mock(return_value=controller))
    popen = mock.Mock()
    monkeypatch.setattr(local_agent.subprocess, "Popen", popen)

    local_agent.execute_run(
        {
            "id": "run-1",
            "mode": "bayesian",
            "workers": 3,
            "pairs": ["AAPL"],
            "n_trials": 10,
            "dd_limit": 6.0,
            "dry_run": False,
            "broker": "vantage",
        }
    )

    assert patch_calls == []
    assert post_calls == [
        (
            "/api/optimizer/runs/run-1/events",
            {
                "event_type": "log",
                "payload": {
                    "level": "warning",
                    "message": "TradingView MCP desktop workspace is not ready",
                    "status": "queued",
                    "workers": 3,
                    "dry_run": False,
                    "python": sys.executable,
                },
            },
        )
    ]
    assert not popen.called
    assert controller.ensure_ready.await_count == 2
    controller._list_workspace_tabs.assert_not_called()


def test_execute_run_claims_only_after_optimizer_readiness_succeeds(local_agent, monkeypatch):
    patch_calls, post_calls, get_calls = _capture_http_calls(local_agent, monkeypatch)

    monkeypatch.setattr(local_agent, "_playwright_available", lambda: True)

    controller = mock.Mock()
    controller.ensure_ready = mock.AsyncMock(return_value=None)
    controller._list_workspace_tabs = mock.AsyncMock(
        return_value=[
            {"id": "tab-1"},
            {"id": "tab-2"},
        ]
    )
    monkeypatch.setattr(local_agent, "OptimizerMcpController", mock.Mock(return_value=controller))
    process = _FakeProcess(exit_code=0)
    popen = mock.Mock(return_value=process)
    monkeypatch.setattr(local_agent.subprocess, "Popen", popen)
    monkeypatch.setattr(local_agent, "_stream_and_report", lambda run_id, proc: None)

    local_agent.execute_run(
        {
            "id": "run-2",
            "mode": "bayesian",
            "workers": 2,
            "pairs": ["EURUSD", "GBPUSD"],
            "n_trials": 12,
            "dd_limit": 5.5,
            "dry_run": False,
            "broker": "oanda",
            "backtest_range": "90d",
        }
    )

    assert any(
        path == "/api/optimizer/runs/run-2" and body == {"status": "running"}
        for path, body in patch_calls
    )
    assert any(
        path == "/api/optimizer/runs/run-2/events" and body["event_type"] == "run_started"
        for path, body in post_calls
    )
    assert popen.called
    controller.ensure_ready.assert_awaited_once_with()
    controller._list_workspace_tabs.assert_awaited_once_with()
    assert get_calls == ["/api/optimizer/runs/run-2"]
    command = popen.call_args.args[0]
    assert "--results-label" in command
    assert command[command.index("--results-label") + 1] == "run-2"
    assert "--backtest-range" in command
    assert command[command.index("--backtest-range") + 1] == "90d"


def test_execute_run_downgrades_workers_to_available_mcp_tabs(local_agent, monkeypatch):
    patch_calls, post_calls, get_calls = _capture_http_calls(local_agent, monkeypatch)

    monkeypatch.setattr(local_agent, "_playwright_available", lambda: True)

    async def fake_not_ready(workers: int) -> tuple[bool, str]:
        return False, "TradingView MCP tab creation did not increase the available tab count"

    monkeypatch.setattr(local_agent, "_ensure_optimizer_run_ready", fake_not_ready)
    monkeypatch.setattr(local_agent, "_available_optimizer_worker_count", mock.AsyncMock(return_value=2))
    monkeypatch.setattr(
        local_agent,
        "OptimizerMcpController",
        mock.Mock(side_effect=AssertionError("controller should not be recreated directly in this test")),
    )

    process = _FakeProcess(exit_code=0)
    popen = mock.Mock(return_value=process)
    monkeypatch.setattr(local_agent.subprocess, "Popen", popen)
    monkeypatch.setattr(local_agent, "_stream_and_report", lambda run_id, proc: None)

    local_agent.execute_run(
        {
            "id": "run-5",
            "mode": "bayesian",
            "workers": 4,
            "pairs": ["EURUSD", "EURJPY", "AUDCAD", "XAUUSD"],
            "n_trials": 80,
            "dd_limit": 7.0,
            "dry_run": False,
            "broker": "oanda",
            "backtest_range": "90d",
        }
    )

    assert any(
        path == "/api/optimizer/runs/run-5" and body == {"status": "running"}
        for path, body in patch_calls
    )
    assert any(
        path == "/api/optimizer/runs/run-5/events"
        and body["payload"]["message"].startswith("Downgrading workers from 4 to 2")
        for path, body in post_calls
    )
    assert any(
        path == "/api/optimizer/runs/run-5/events"
        and body["event_type"] == "run_started"
        and body["payload"]["workers"] == 2
        for path, body in post_calls
    )
    assert get_calls == ["/api/optimizer/runs/run-5"]
    command = popen.call_args.args[0]
    assert "--workers" in command
    assert command[command.index("--workers") + 1] == "2"


def test_execute_run_preflight_does_not_expand_tabs(local_agent, monkeypatch):
    monkeypatch.setattr(local_agent, "_playwright_available", lambda: True)

    controller = mock.Mock()
    controller.ensure_ready = mock.AsyncMock(return_value=None)
    controller._list_workspace_tabs = mock.AsyncMock(return_value=[{"id": "tab-1"}])
    controller.ensure_optimizer_ready = mock.AsyncMock(
        side_effect=AssertionError("readiness preflight must not create tabs")
    )
    monkeypatch.setattr(local_agent, "OptimizerMcpController", mock.Mock(return_value=controller))

    ready, reason = local_agent.asyncio.run(local_agent._ensure_optimizer_run_ready(3))

    assert ready is False
    assert "currently exposes 1 tab(s); requested 3" in reason
    controller.ensure_ready.assert_awaited_once_with()
    controller._list_workspace_tabs.assert_awaited_once_with()
    controller.ensure_optimizer_ready.assert_not_called()


def test_execute_run_dry_run_claims_without_mcp_or_playwright_ready(local_agent, monkeypatch):
    patch_calls, post_calls, _ = _capture_http_calls(local_agent, monkeypatch)

    monkeypatch.setattr(local_agent, "_playwright_available", lambda: False)
    monkeypatch.setattr(
        local_agent,
        "OptimizerMcpController",
        mock.Mock(side_effect=AssertionError("optimizer readiness should not be checked for dry runs")),
    )
    process = _FakeProcess(exit_code=0)
    monkeypatch.setattr(local_agent.subprocess, "Popen", mock.Mock(return_value=process))
    monkeypatch.setattr(local_agent, "_stream_and_report", lambda run_id, proc: None)

    local_agent.execute_run(
        {
            "id": "run-3",
            "mode": "bayesian",
            "workers": 4,
            "pairs": ["NAS100"],
            "n_trials": 8,
            "dd_limit": 4.0,
            "dry_run": True,
            "broker": "fxcm",
        }
    )

    assert any(
        path == "/api/optimizer/runs/run-3" and body == {"status": "running"}
        for path, body in patch_calls
    )
    assert not any(
        event_path == "/api/optimizer/runs/run-3/events" and body["event_type"] == "log"
        for event_path, body in post_calls
    )


def test_execute_run_does_not_fail_when_playwright_is_missing_before_claim(local_agent, monkeypatch):
    patch_calls, post_calls, _ = _capture_http_calls(local_agent, monkeypatch)

    monkeypatch.setattr(local_agent, "_playwright_available", lambda: False)
    monkeypatch.setattr(
        local_agent,
        "OptimizerMcpController",
        mock.Mock(side_effect=AssertionError("optimizer readiness should not be checked without playwright")),
    )
    popen = mock.Mock()
    monkeypatch.setattr(local_agent.subprocess, "Popen", popen)

    local_agent.execute_run(
        {
            "id": "run-4",
            "mode": "bayesian",
            "workers": 1,
            "pairs": ["BTCUSD"],
            "n_trials": 5,
            "dd_limit": 7.0,
            "dry_run": False,
            "broker": "vantage",
        }
    )

    assert not any(
        path == "/api/optimizer/runs/run-4" and body.get("status") == "failed"
        for path, body in patch_calls
    )
    assert not any(
        path == "/api/optimizer/runs/run-4" and body == {"status": "running"}
        for path, body in patch_calls
    )
    assert any(event_path == "/api/optimizer/runs/run-4/events" for event_path, _ in post_calls)
    assert not popen.called


def test_execute_run_blocks_only_once_for_repeated_same_reason(local_agent, monkeypatch):
    _, post_calls, _ = _capture_http_calls(local_agent, monkeypatch)
    monkeypatch.setattr(local_agent, "log", mock.Mock())

    monotonic_values = iter([100.0, 110.0, 120.0])
    monkeypatch.setattr(local_agent.time, "monotonic", lambda: next(monotonic_values))

    local_agent._report_optimizer_run_blocked("run-9", "desktop bridge missing", workers=2, dry_run=False)
    local_agent._report_optimizer_run_blocked("run-9", "desktop bridge missing", workers=2, dry_run=False)
    local_agent._report_optimizer_run_blocked("run-9", "workspace changed", workers=2, dry_run=False)

    assert post_calls == [
        (
            "/api/optimizer/runs/run-9/events",
            {
                "event_type": "log",
                "payload": {
                    "level": "warning",
                    "message": "desktop bridge missing",
                    "status": "queued",
                    "workers": 2,
                    "dry_run": False,
                    "python": sys.executable,
                },
            },
        ),
        (
            "/api/optimizer/runs/run-9/events",
            {
                "event_type": "log",
                "payload": {
                    "level": "warning",
                    "message": "workspace changed",
                    "status": "queued",
                    "workers": 2,
                    "dry_run": False,
                    "python": sys.executable,
                },
            },
        ),
    ]
