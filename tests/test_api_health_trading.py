from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api_health_trading import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class _FakeRedis:
    def __init__(self, heartbeat_payload, queue_depth: int) -> None:
        self._heartbeat_payload = heartbeat_payload
        self._queue_depth = queue_depth

    def get(self, key: str):
        return self._heartbeat_payload

    def llen(self, key: str) -> int:
        return self._queue_depth


def test_trading_health_reports_running_worker_from_redis_heartbeat(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    heartbeat = {
        "ts": now.timestamp(),
        "host": "railway-worker",
        "pid": 4321,
    }

    monkeypatch.setattr("src.api_health_trading._get_meta_api_cache", lambda: {"equity": 101.5, "balance": 100.0})
    monkeypatch.setattr("src.api_health_trading._get_open_positions", lambda: {"count": 2, "unrealised_pnl": 5.25})
    monkeypatch.setattr("src.api_health_trading._get_todays_trades", lambda: {"count": 1, "realised_pnl": 12.0})
    monkeypatch.setattr("src.api_health_trading._get_redis_status", lambda: "running")
    monkeypatch.setattr(
        "src.adapters.redis_queue.get_redis",
        lambda: _FakeRedis(
            heartbeat_payload='{"ts": %s, "host": "railway-worker", "pid": 4321}' % heartbeat["ts"],
            queue_depth=3,
        ),
    )

    client = _client()
    response = client.get("/api/health/trading")
    assert response.status_code == 200

    body = response.json()
    assert body["pipeline"]["worker"] == "running"
    assert body["pipeline"]["queue_depth"] == 3
    assert body["pipeline"]["worker_host"] == "railway-worker"
    assert body["pipeline"]["overall"] == "healthy"


def test_trading_health_marks_stale_worker_heartbeat(monkeypatch) -> None:
    stale_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).timestamp()

    monkeypatch.setattr("src.api_health_trading._get_meta_api_cache", lambda: {})
    monkeypatch.setattr("src.api_health_trading._get_open_positions", lambda: {"count": 0, "unrealised_pnl": 0.0})
    monkeypatch.setattr("src.api_health_trading._get_todays_trades", lambda: {"count": 0, "realised_pnl": 0.0})
    monkeypatch.setattr("src.api_health_trading._get_redis_status", lambda: "running")
    monkeypatch.setattr(
        "src.adapters.redis_queue.get_redis",
        lambda: _FakeRedis(
            heartbeat_payload='{"ts": %s, "host": "railway-worker", "pid": 999}' % stale_ts,
            queue_depth=7,
        ),
    )

    client = _client()
    response = client.get("/api/health/trading")
    assert response.status_code == 200

    body = response.json()
    assert body["pipeline"]["worker"] == "stale"
    assert body["pipeline"]["queue_depth"] == 7
    assert body["pipeline"]["overall"] == "degraded"
