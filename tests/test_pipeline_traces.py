"""
Tests for Sprint 2.1: Pipeline Latency Instrumentation.

Covers:
  TraceObserver
  ─────────────
  - SIGNAL_RECEIVED event → upserts row with received_at + symbol + run_mode
  - ORDER_SUBMITTED event → upserts exec_submitted_at (same correlation_id)
  - ERROR event → upserts error_at + error_type + error_message
  - Unknown event type → no DB call (no crash)
  - Supabase client = None → no crash (graceful skip)
  - Client raises on upsert → exception swallowed by observer harness

  Integration with WorkerSubject
  ───────────────────────────────
  - Full SIGNAL_RECEIVED → ORDER_SUBMITTED run: two upserts with matching
    correlation_id; exec_submitted_at > received_at (monotonic)
  - Full SIGNAL_RECEIVED → ERROR run: received_at + error_at set

  API endpoints (unit, Supabase mocked)
  ───────────────────────────────────────
  - GET /api/traces → list of TraceSummary (200)
  - GET /api/traces/stats → StatsResponse with hop buckets (200)
  - GET /api/traces/{correlation_id} → TraceDetail (200)
  - GET /api/traces/missing → 404
  - total_ms helper: correct, non-negative, None when timestamps missing
"""

from __future__ import annotations

import time
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.core.observers.base import (
    ERROR,
    ORDER_SUBMITTED,
    SIGNAL_RECEIVED,
    TradeEvent,
    WorkerSubject,
)
from src.core.observers.metrics import MetricsObserver, TraceObserver


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now_ts() -> float:
    return time.time()


def _event(event_type: str, correlation_id: str = "abc123", **meta) -> TradeEvent:
    return TradeEvent(
        event_type=event_type,
        correlation_id=correlation_id,
        payload={"symbol": "XAUUSD", "run_mode": "PAPER"},
        timestamp=_now_ts(),
        metadata=meta,
    )


def _make_mock_client() -> MagicMock:
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])
    return client


# ── TraceObserver unit tests ───────────────────────────────────────────────────

class TraceObserverUpsertTests(unittest.TestCase):

    def test_signal_received_inserts_row(self):
        client = _make_mock_client()
        obs = TraceObserver(supabase_client=client)
        obs.on_event(_event(SIGNAL_RECEIVED, "cid1"))

        client.table.assert_called_once_with("pipeline_traces")
        upsert_args = client.table.return_value.upsert.call_args
        row = upsert_args[0][0]
        self.assertEqual(row["correlation_id"], "cid1")
        self.assertIn("received_at", row)
        self.assertEqual(row["symbol"], "XAUUSD")
        self.assertEqual(row["run_mode"], "PAPER")

    def test_order_submitted_upserts_exec_submitted_at(self):
        client = _make_mock_client()
        obs = TraceObserver(supabase_client=client)
        obs.on_event(_event(ORDER_SUBMITTED, "cid2"))

        row = client.table.return_value.upsert.call_args[0][0]
        self.assertEqual(row["correlation_id"], "cid2")
        self.assertIn("exec_submitted_at", row)
        self.assertNotIn("received_at", row)

    def test_order_submitted_captures_signal_id(self):
        client = _make_mock_client()
        obs = TraceObserver(supabase_client=client)
        evt = TradeEvent(
            event_type=ORDER_SUBMITTED,
            correlation_id="cid3",
            payload={"symbol": "EURUSD", "run_mode": "PAPER", "_signal_id": 42},
            timestamp=_now_ts(),
            metadata={},
        )
        obs.on_event(evt)
        row = client.table.return_value.upsert.call_args[0][0]
        self.assertEqual(row["signal_id"], 42)

    def test_error_event_sets_error_fields(self):
        client = _make_mock_client()
        obs = TraceObserver(supabase_client=client)
        obs.on_event(_event(
            ERROR,
            "cid4",
            error_type="ValueError",
            error="something went wrong",
        ))
        row = client.table.return_value.upsert.call_args[0][0]
        self.assertEqual(row["correlation_id"], "cid4")
        self.assertIn("error_at", row)
        self.assertEqual(row["error_type"], "ValueError")
        self.assertEqual(row["error_message"], "something went wrong")

    def test_unknown_event_type_makes_no_db_call(self):
        client = _make_mock_client()
        obs = TraceObserver(supabase_client=client)
        obs.on_event(_event("SIGNAL_VALIDATED", "cid5"))
        client.table.assert_not_called()

    def test_none_client_does_not_raise(self):
        obs = TraceObserver(supabase_client=None)
        # Patch lazy resolution to also return None so we test the guard
        with patch.object(obs, "_get_client", return_value=None):
            obs.on_event(_event(SIGNAL_RECEIVED, "cid6"))  # must not raise

    def test_upsert_exception_is_swallowed_by_observer_harness(self):
        """WorkerSubject catches observer exceptions — but TraceObserver also
        catches internally, so we verify the internal catch as well."""
        client = _make_mock_client()
        client.table.return_value.upsert.return_value.execute.side_effect = RuntimeError("boom")
        obs = TraceObserver(supabase_client=client)
        obs.on_event(_event(SIGNAL_RECEIVED, "cid7"))  # must not raise

    def test_metrics_observer_alias_is_trace_observer(self):
        self.assertIs(MetricsObserver, TraceObserver)


# ── Received_at / exec_submitted_at are valid ISO timestamps ──────────────────

class TraceObserverTimestampTests(unittest.TestCase):

    def test_received_at_is_valid_iso(self):
        client = _make_mock_client()
        obs = TraceObserver(supabase_client=client)
        obs.on_event(_event(SIGNAL_RECEIVED, "ts1"))
        row = client.table.return_value.upsert.call_args[0][0]
        dt = datetime.fromisoformat(row["received_at"])
        self.assertIsNotNone(dt.tzinfo)

    def test_exec_submitted_at_is_valid_iso(self):
        client = _make_mock_client()
        obs = TraceObserver(supabase_client=client)
        obs.on_event(_event(ORDER_SUBMITTED, "ts2"))
        row = client.table.return_value.upsert.call_args[0][0]
        dt = datetime.fromisoformat(row["exec_submitted_at"])
        self.assertIsNotNone(dt.tzinfo)


# ── Integration: WorkerSubject + TraceObserver ────────────────────────────────

class TraceObserverIntegrationTests(unittest.TestCase):

    def _make_payload(self):
        return {
            "symbol": "EURUSD",
            "side": "buy",
            "entry": 1.10,
            "sl": 1.09,
            "tp": 1.12,
            "size": 0.5,
            "run_mode": "PAPER",
        }

    def test_success_path_two_upserts_same_correlation_id(self):
        upsert_calls = []
        client = MagicMock()
        table_mock = MagicMock()
        upsert_mock = MagicMock()
        upsert_mock.execute.return_value = MagicMock(data=[])

        def capture_upsert(row, **kw):
            upsert_calls.append(dict(row))
            return upsert_mock

        table_mock.upsert.side_effect = capture_upsert
        client.table.return_value = table_mock

        obs = TraceObserver(supabase_client=client)
        subject = WorkerSubject(process_fn=lambda p: None)
        subject.attach(obs)

        payload = self._make_payload()
        subject.process_signal(payload)

        self.assertEqual(len(upsert_calls), 2)
        cid_received = upsert_calls[0]["correlation_id"]
        cid_submitted = upsert_calls[1]["correlation_id"]
        self.assertEqual(cid_received, cid_submitted)
        self.assertIn("received_at", upsert_calls[0])
        self.assertIn("exec_submitted_at", upsert_calls[1])

    def test_success_path_timestamps_monotonic(self):
        """exec_submitted_at must not precede received_at."""
        upsert_calls = []
        client = MagicMock()
        table_mock = MagicMock()
        upsert_mock = MagicMock()
        upsert_mock.execute.return_value = MagicMock(data=[])

        def capture_upsert(row, **kw):
            upsert_calls.append(dict(row))
            return upsert_mock

        table_mock.upsert.side_effect = capture_upsert
        client.table.return_value = table_mock

        obs = TraceObserver(supabase_client=client)
        subject = WorkerSubject(process_fn=lambda p: None)
        subject.attach(obs)
        subject.process_signal(self._make_payload())

        t_recv = datetime.fromisoformat(upsert_calls[0]["received_at"])
        t_sub  = datetime.fromisoformat(upsert_calls[1]["exec_submitted_at"])
        self.assertGreaterEqual(t_sub, t_recv)

    def test_error_path_sets_error_fields(self):
        upsert_calls = []
        client = MagicMock()
        table_mock = MagicMock()
        upsert_mock = MagicMock()
        upsert_mock.execute.return_value = MagicMock(data=[])

        def capture_upsert(row, **kw):
            upsert_calls.append(dict(row))
            return upsert_mock

        table_mock.upsert.side_effect = capture_upsert
        client.table.return_value = table_mock

        def boom(p):
            raise ValueError("trade rejected")

        obs = TraceObserver(supabase_client=client)
        subject = WorkerSubject(process_fn=boom)
        subject.attach(obs)

        with self.assertRaises(ValueError):
            subject.process_signal(self._make_payload())

        self.assertEqual(len(upsert_calls), 2)
        error_row = upsert_calls[1]
        self.assertIn("error_at", error_row)
        self.assertEqual(error_row["error_type"], "ValueError")


# ── API endpoint tests ────────────────────────────────────────────────────────

def _make_app_with_mock_supabase(mock_sb):
    """Return a TestClient whose supabase client is replaced with mock_sb."""
    import src.api_traces as api_module
    with patch.object(api_module, "_get_supabase", return_value=mock_sb):
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(api_module.router)
        return TestClient(app)


class ApiTracesListTests(unittest.TestCase):

    def _mock_sb(self, rows):
        sb = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=rows)
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        chain.not_.is_.return_value = chain
        chain.is_.return_value = chain
        sb.table.return_value.select.return_value = chain
        return sb

    def test_list_returns_200(self):
        rows = [{
            "trace_id": "uuid-1",
            "correlation_id": "aaa",
            "signal_id": 1,
            "account_id": "acc1",
            "symbol": "XAUUSD",
            "run_mode": "PAPER",
            "received_at": "2025-01-01T10:00:00+00:00",
            "exec_submitted_at": "2025-01-01T10:00:01+00:00",
            "error_at": None,
            "error_type": None,
            "created_at": "2025-01-01T10:00:00+00:00",
        }]
        import src.api_traces as api_module
        with patch.object(api_module, "_get_supabase", return_value=self._mock_sb(rows)):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(api_module.router)
            client = TestClient(app)
            resp = client.get("/api/traces")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["correlation_id"], "aaa")

    def test_total_ms_is_non_negative(self):
        rows = [{
            "trace_id": "uuid-2",
            "correlation_id": "bbb",
            "signal_id": None,
            "account_id": None,
            "symbol": "EURUSD",
            "run_mode": "PAPER",
            "received_at": "2025-01-01T10:00:00+00:00",
            "exec_submitted_at": "2025-01-01T10:00:00.500000+00:00",
            "error_at": None,
            "error_type": None,
            "created_at": "2025-01-01T10:00:00+00:00",
        }]
        import src.api_traces as api_module
        with patch.object(api_module, "_get_supabase", return_value=self._mock_sb(rows)):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(api_module.router)
            client = TestClient(app)
            resp = client.get("/api/traces")
        data = resp.json()
        ms = data[0]["total_ms"]
        self.assertIsNotNone(ms)
        self.assertGreaterEqual(ms, 0)

    def test_total_ms_none_when_no_timestamps(self):
        from src.api_traces import _total_ms
        self.assertIsNone(_total_ms({"received_at": None, "exec_submitted_at": None}))
        self.assertIsNone(_total_ms({"received_at": "2025-01-01T10:00:00+00:00"}))

    def test_list_empty_db_returns_empty_list(self):
        import src.api_traces as api_module
        with patch.object(api_module, "_get_supabase", return_value=self._mock_sb([])):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(api_module.router)
            client = TestClient(app)
            resp = client.get("/api/traces")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])


class ApiTracesDetailTests(unittest.TestCase):

    def _mock_sb_detail(self, rows):
        sb = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=rows)
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        sb.table.return_value.select.return_value = chain
        return sb

    def _row(self):
        return {
            "trace_id": "uuid-3",
            "correlation_id": "ccc",
            "signal_id": 5,
            "account_id": "acc2",
            "symbol": "GBPUSD",
            "run_mode": "PAPER",
            "received_at":       "2025-01-01T10:00:00+00:00",
            "enqueued_at":       None,
            "dequeued_at":       None,
            "validated_at":      None,
            "risk_started_at":   None,
            "risk_finished_at":  None,
            "exec_started_at":   None,
            "exec_submitted_at": "2025-01-01T10:00:00.200000+00:00",
            "broker_ack_at":     None,
            "broker_confirmed_at": None,
            "reconciled_at":     None,
            "error_at":          None,
            "error_type":        None,
            "error_message":     None,
            "created_at": "2025-01-01T10:00:00+00:00",
            "updated_at": "2025-01-01T10:00:00+00:00",
        }

    def test_get_trace_200(self):
        import src.api_traces as api_module
        with patch.object(api_module, "_get_supabase", return_value=self._mock_sb_detail([self._row()])):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(api_module.router)
            client = TestClient(app)
            resp = client.get("/api/traces/ccc")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["correlation_id"], "ccc")
        self.assertIn("hops", data)
        self.assertEqual(data["hops"]["received_at"], "2025-01-01T10:00:00+00:00")

    def test_get_trace_404(self):
        import src.api_traces as api_module
        with patch.object(api_module, "_get_supabase", return_value=self._mock_sb_detail([])):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(api_module.router)
            client = TestClient(app)
            resp = client.get("/api/traces/nonexistent")
        self.assertEqual(resp.status_code, 404)


class ApiTracesStatsTests(unittest.TestCase):

    def _mock_sb_stats(self, rows):
        sb = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=rows)
        chain.gte.return_value = chain
        chain.limit.return_value = chain
        sb.table.return_value.select.return_value = chain
        return sb

    def test_stats_returns_200_with_hop_list(self):
        import src.api_traces as api_module
        rows = [
            {
                "received_at": "2025-01-01T10:00:00+00:00",
                "exec_submitted_at": "2025-01-01T10:00:00.300000+00:00",
                **{f: None for f in [
                    "enqueued_at", "dequeued_at", "validated_at",
                    "risk_started_at", "risk_finished_at", "exec_started_at",
                    "broker_ack_at", "broker_confirmed_at", "reconciled_at",
                    "error_at", "trace_id", "correlation_id", "signal_id",
                    "account_id", "symbol", "run_mode", "error_type",
                    "error_message", "created_at", "updated_at",
                ]},
            }
        ]
        with patch.object(api_module, "_get_supabase", return_value=self._mock_sb_stats(rows)):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(api_module.router)
            client = TestClient(app)
            resp = client.get("/api/traces/stats")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("hops", body)
        self.assertIn("total_traces", body)
        total_hop = next((h for h in body["hops"] if h["hop"] == "total_ms"), None)
        self.assertIsNotNone(total_hop)
        self.assertEqual(total_hop["count"], 1)
        self.assertAlmostEqual(total_hop["p50_ms"], 300.0, places=0)

    def test_stats_empty_returns_zero_counts(self):
        import src.api_traces as api_module
        with patch.object(api_module, "_get_supabase", return_value=self._mock_sb_stats([])):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(api_module.router)
            client = TestClient(app)
            resp = client.get("/api/traces/stats")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["total_traces"], 0)
        for hop in body["hops"]:
            self.assertEqual(hop["count"], 0)
            self.assertIsNone(hop["p50_ms"])


if __name__ == "__main__":
    unittest.main()
