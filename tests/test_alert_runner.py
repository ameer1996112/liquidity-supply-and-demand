from __future__ import annotations

import asyncio
import threading
from typing import Any

from scripts.optimizer.alert_runner import AlertBatchRunner, AlertDeployment
from scripts.optimizer import local_agent


class FakeAlertBrowser:
    def __init__(self, failures: set[str] | None = None) -> None:
        self.failures = failures or set()
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
        )


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
        and body.get("status") == "completed"
        for _, path, body in patched_calls
    )
    assert any(
        event["path"] == "/api/alert-setup/batches/batch-2/events"
        and event["body"]["event_type"] == "batch_finished"
        for event in posted_events
    )

