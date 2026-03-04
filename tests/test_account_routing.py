"""
Tests for Sprint 2.3: Multi-account routing foundation.

Covers
──────
AccountRouter
  - resolve_account_id: _account_id field takes priority
  - resolve_account_id: account_id field used if _account_id absent
  - resolve_account_id: defaults to "default" when neither field present
  - queue_key_for: "default" → "signals:default"
  - queue_key_for: other → "signals:<account_id>"
  - queue_key_for: None / empty → "signals:default"
  - resolve_queue_key: end-to-end convenience method

AccountRouterObserver
  - on_event with SIGNAL_RECEIVED: does not raise
  - on_event with ORDER_SUBMITTED: does nothing (no log of routing)
  - observer harness swallows any internal exception

WorkerSubject + account_router
  - stamps _account_id onto the live payload before SIGNAL_RECEIVED is emitted
  - _account_id visible in TradeEvent.payload snapshot
  - falls back to "default" when payload has no account hints
  - explicit account_id on payload is preserved

InMemoryTransport — per-account queue isolation
  - enqueue to named key, dequeue from named key → get correct item
  - enqueue to default, dequeue from named key → returns None (isolation)
  - enqueue to named key, dequeue default → returns None (isolation)
  - queue_size_for counts per-key
  - queue_size totals across all keys
  - queue_names lists only non-empty keys

Integration: single signal end-to-end
  - PAPER signal with no account hints → routed to "default" → queue "trading_queue"
  - Signal with account_id set → routed to that account → named queue

API Accounts endpoints (Supabase mocked)
  - GET /api/accounts → 200 + list
  - GET /api/accounts/{account_id} → 200 + detail
  - GET /api/accounts/nonexistent → 404
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from src.core.account_router import (
    DEFAULT_ACCOUNT_ID,
    DEFAULT_QUEUE_KEY,
    AccountRouter,
)
from src.core.observers.account_router_observer import AccountRouterObserver
from src.core.observers.base import (
    ORDER_SUBMITTED,
    SIGNAL_RECEIVED,
    TradeEvent,
    WorkerSubject,
)
from src.core.transport import InMemoryTransport


# ── Helpers ────────────────────────────────────────────────────────────────────

def _payload(**kw):
    return {"symbol": "XAUUSD", "side": "buy", "run_mode": "PAPER", **kw}


def _event(event_type: str, payload: dict | None = None, cid: str = "abc") -> TradeEvent:
    import time
    return TradeEvent(
        event_type=event_type,
        correlation_id=cid,
        payload=dict(payload or _payload()),
        timestamp=time.time(),
        metadata={},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# AccountRouter
# ═══════════════════════════════════════════════════════════════════════════════

class AccountRouterResolveTests(unittest.TestCase):

    def setUp(self):
        self.router = AccountRouter()

    def test_underscore_account_id_takes_priority(self):
        p = _payload(_account_id="acc-1", account_id="acc-2")
        self.assertEqual(self.router.resolve_account_id(p), "acc-1")

    def test_account_id_used_when_no_underscore(self):
        p = _payload(account_id="acc-2")
        self.assertEqual(self.router.resolve_account_id(p), "acc-2")

    def test_defaults_to_default_when_no_hints(self):
        p = _payload()
        self.assertEqual(self.router.resolve_account_id(p), DEFAULT_ACCOUNT_ID)

    def test_empty_string_falls_back_to_default(self):
        p = _payload(_account_id="", account_id="")
        self.assertEqual(self.router.resolve_account_id(p), DEFAULT_ACCOUNT_ID)


class AccountRouterQueueKeyTests(unittest.TestCase):

    def setUp(self):
        self.router = AccountRouter()

    def test_default_account_returns_signals_default(self):
        self.assertEqual(self.router.queue_key_for("default"), DEFAULT_QUEUE_KEY)
        self.assertEqual(DEFAULT_QUEUE_KEY, "signals:default")

    def test_named_account_returns_partitioned_key(self):
        self.assertEqual(self.router.queue_key_for("prop-1"), "signals:prop-1")
        self.assertEqual(self.router.queue_key_for("abc123"), "signals:abc123")

    def test_none_returns_default_queue(self):
        self.assertEqual(self.router.queue_key_for(None), DEFAULT_QUEUE_KEY)

    def test_empty_string_returns_default_queue(self):
        self.assertEqual(self.router.queue_key_for(""), DEFAULT_QUEUE_KEY)

    def test_resolve_queue_key_end_to_end_default(self):
        p = _payload()
        self.assertEqual(self.router.resolve_queue_key(p), DEFAULT_QUEUE_KEY)

    def test_resolve_queue_key_end_to_end_named(self):
        p = _payload(_account_id="prop-1")
        self.assertEqual(self.router.resolve_queue_key(p), "signals:prop-1")


# ═══════════════════════════════════════════════════════════════════════════════
# AccountRouterObserver
# ═══════════════════════════════════════════════════════════════════════════════

class AccountRouterObserverTests(unittest.TestCase):

    def setUp(self):
        self.obs = AccountRouterObserver()

    def test_signal_received_does_not_raise(self):
        evt = _event(SIGNAL_RECEIVED, _payload(_account_id="acc-1"))
        self.obs.on_event(evt)  # must not raise

    def test_order_submitted_does_not_raise(self):
        evt = _event(ORDER_SUBMITTED, _payload(_account_id="acc-1"))
        self.obs.on_event(evt)  # must not raise

    def test_internal_exception_is_swallowed(self):
        """Observer must never raise even if router internals fail."""
        bad_router = MagicMock()
        bad_router.queue_key_for.side_effect = RuntimeError("boom")
        obs = AccountRouterObserver(router=bad_router)
        evt = _event(SIGNAL_RECEIVED)
        obs.on_event(evt)  # must not raise


# ═══════════════════════════════════════════════════════════════════════════════
# WorkerSubject + account_router param
# ═══════════════════════════════════════════════════════════════════════════════

class WorkerSubjectAccountRouterTests(unittest.TestCase):

    def _run(self, payload, router=None):
        captured_events = []

        class _Cap:
            def on_event(self, ev): captured_events.append(ev)

        subject = WorkerSubject(process_fn=lambda p: None, account_router=router or AccountRouter())
        subject.attach(_Cap())
        subject.process_signal(payload)
        return payload, captured_events

    def test_default_account_stamped_on_payload(self):
        p = _payload()
        final_payload, _ = self._run(p)
        self.assertEqual(final_payload["_account_id"], DEFAULT_ACCOUNT_ID)

    def test_explicit_account_id_preserved(self):
        p = _payload(account_id="prop-1")
        final_payload, _ = self._run(p)
        self.assertEqual(final_payload["_account_id"], "prop-1")

    def test_underscore_account_id_already_set_preserved(self):
        p = _payload(_account_id="special")
        final_payload, _ = self._run(p)
        self.assertEqual(final_payload["_account_id"], "special")

    def test_account_id_visible_in_event_payload_snapshot(self):
        p = _payload(_account_id="acc-x")
        _, events = self._run(p)
        received_evt = next(e for e in events if e.event_type == SIGNAL_RECEIVED)
        self.assertEqual(received_evt.payload.get("_account_id"), "acc-x")

    def test_no_account_router_does_not_stamp(self):
        """WorkerSubject without account_router should NOT set _account_id."""
        p = _payload()
        subject = WorkerSubject(process_fn=lambda _: None)
        subject.process_signal(p)
        self.assertNotIn("_account_id", p)

    def test_router_exception_does_not_crash_pipeline(self):
        bad_router = MagicMock()
        bad_router.resolve_account_id.side_effect = RuntimeError("db down")
        p = _payload()
        subject = WorkerSubject(process_fn=lambda _: None, account_router=bad_router)
        subject.process_signal(p)  # must not raise


# ═══════════════════════════════════════════════════════════════════════════════
# InMemoryTransport — per-account queue isolation
# ═══════════════════════════════════════════════════════════════════════════════

class InMemoryTransportMultiQueueTests(unittest.TestCase):

    def setUp(self):
        self.t = InMemoryTransport()

    def test_enqueue_and_dequeue_named_queue(self):
        self.t.enqueue('{"a":1}', queue_key="signals:acc-1")
        result = self.t.dequeue(queue_keys=["signals:acc-1"])
        self.assertIsNotNone(result)
        key, data = result
        self.assertEqual(key, "signals:acc-1")
        self.assertEqual(data, '{"a":1}')

    def test_default_queue_does_not_leak_to_named_queue(self):
        self.t.enqueue('{"default":1}')  # goes to internal default queue
        result = self.t.dequeue(queue_keys=["signals:acc-1"])
        self.assertIsNone(result)

    def test_named_queue_does_not_leak_to_default(self):
        self.t.enqueue('{"named":1}', queue_key="signals:acc-1")
        result = self.t.dequeue()  # polls default queue only
        self.assertIsNone(result)

    def test_queue_size_for_named(self):
        self.t.enqueue('{"a":1}', queue_key="signals:acc-1")
        self.t.enqueue('{"b":2}', queue_key="signals:acc-1")
        self.assertEqual(self.t.queue_size_for("signals:acc-1"), 2)
        # Internal default queue remains separate
        self.assertEqual(self.t.queue_size_for("trading_queue"), 0)

    def test_queue_size_totals_across_queues(self):
        self.t.enqueue('{"a":1}')
        self.t.enqueue('{"b":2}', queue_key="signals:acc-1")
        self.t.enqueue('{"c":3}', queue_key="signals:acc-2")
        self.assertEqual(self.t.queue_size, 3)

    def test_queue_names_lists_nonempty_queues(self):
        self.t.enqueue('{"x":1}', queue_key="signals:acc-x")
        names = self.t.queue_names()
        self.assertIn("signals:acc-x", names)
        self.assertNotIn("trading_queue", names)

    def test_dequeue_polls_multiple_keys_fifo_per_key(self):
        self.t.enqueue('{"a":1}', queue_key="signals:acc-a")
        self.t.enqueue('{"b":2}', queue_key="signals:acc-b")
        r1 = self.t.dequeue(queue_keys=["signals:acc-a", "signals:acc-b"])
        r2 = self.t.dequeue(queue_keys=["signals:acc-a", "signals:acc-b"])
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)
        payloads = {json.loads(r1[1])["a"], json.loads(r2[1])["b"]}
        self.assertIn(1, payloads)
        self.assertIn(2, payloads)

    def test_backward_compat_roundtrip_unchanged(self):
        """Default enqueue/dequeue still return 'memory_queue' as the key."""
        self.t.enqueue('{"legacy":1}')
        key, data = self.t.dequeue()
        self.assertEqual(key, "memory_queue")
        self.assertEqual(data, '{"legacy":1}')


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: single signal end-to-end
# ═══════════════════════════════════════════════════════════════════════════════

class AccountRoutingIntegrationTests(unittest.TestCase):

    def test_paper_signal_with_no_account_routes_to_default_queue(self):
        transport = InMemoryTransport()
        router = AccountRouter()
        p = {"symbol": "EURUSD", "side": "buy", "run_mode": "PAPER"}

        # API side: resolve + stamp + enqueue
        account_id = router.resolve_account_id(p)
        p["_account_id"] = account_id
        queue_key = router.queue_key_for(account_id)
        transport.enqueue(json.dumps(p), queue_key=queue_key)

        # Should be in default account queue (signals:default)
        self.assertEqual(transport.queue_size_for("signals:default"), 1)
        # Other queues should be empty
        self.assertEqual(transport.queue_size_for("signals:any"), 0)

        # Dequeue from default internal queue should see nothing (partitioned queue used)
        result = transport.dequeue()
        self.assertIsNone(result)

        # Dequeue from the account-specific queue
        result2 = transport.dequeue(queue_keys=[queue_key])
        self.assertIsNotNone(result2)
        data = json.loads(result2[1])
        self.assertEqual(data["_account_id"], DEFAULT_ACCOUNT_ID)

    def test_signal_with_explicit_account_routes_to_named_queue(self):
        transport = InMemoryTransport()
        router = AccountRouter()
        p = {"symbol": "EURUSD", "side": "sell", "run_mode": "PAPER", "account_id": "prop-1"}

        account_id = router.resolve_account_id(p)
        p["_account_id"] = account_id
        queue_key = router.queue_key_for(account_id)
        transport.enqueue(json.dumps(p), queue_key=queue_key)

        self.assertEqual(transport.queue_size_for("signals:prop-1"), 1)
        self.assertEqual(transport.queue_size_for("signals:default"), 0)

    def test_two_accounts_are_isolated(self):
        transport = InMemoryTransport()
        router = AccountRouter()

        for acc in ("acc-a", "acc-b"):
            for i in range(3):
                p = {"symbol": "XAUUSD", "side": "buy", "account_id": acc, "_seq": i}
                account_id = router.resolve_account_id(p)
                transport.enqueue(json.dumps(p), queue_key=router.queue_key_for(account_id))

        self.assertEqual(transport.queue_size_for("signals:acc-a"), 3)
        self.assertEqual(transport.queue_size_for("signals:acc-b"), 3)
        self.assertEqual(transport.queue_size_for("signals:default"), 0)

    def test_worker_subject_stamps_account_id_on_live_payload(self):
        """WorkerSubject with AccountRouter stamps _account_id before SIGNAL_RECEIVED."""
        received_events = []

        class _Cap:
            def on_event(self, ev):
                if ev.event_type == SIGNAL_RECEIVED:
                    received_events.append(ev)

        p = _payload(account_id="eval-1")
        subject = WorkerSubject(process_fn=lambda _: None, account_router=AccountRouter())
        subject.attach(_Cap())
        subject.process_signal(p)

        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].payload.get("_account_id"), "eval-1")
        # Live payload also stamped
        self.assertEqual(p["_account_id"], "eval-1")


# ═══════════════════════════════════════════════════════════════════════════════
# API Accounts endpoints (Supabase mocked)
# ═══════════════════════════════════════════════════════════════════════════════

def _account_row(**overrides):
    base = {
        "account_id": "default",
        "name": "Default Account",
        "broker_type": "paper",
        "status": "active",
        "risk_limits": {},
        "metaapi_account_id": None,
        "tags": [],
        "queue_key": "signals:default",
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


class ApiAccountsListTests(unittest.TestCase):

    def _client(self, rows):
        sb = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=rows)
        chain.order.return_value = chain
        chain.eq.return_value = chain
        sb.table.return_value.select.return_value = chain
        return sb

    def test_list_returns_200(self):
        import src.api_accounts as mod
        rows = [_account_row()]
        with patch.object(mod, "_get_supabase", return_value=self._client(rows)):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(mod.router)
            resp = TestClient(app).get("/api/accounts")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["account_id"], "default")
        self.assertEqual(data[0]["queue_key"], "signals:default")

    def test_list_multiple_accounts(self):
        import src.api_accounts as mod
        rows = [
            _account_row(),
            _account_row(account_id="prop-1", name="Prop Account", queue_key="signals:prop-1"),
        ]
        with patch.object(mod, "_get_supabase", return_value=self._client(rows)):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(mod.router)
            resp = TestClient(app).get("/api/accounts")
        self.assertEqual(len(resp.json()), 2)

    def test_empty_db_returns_empty_list(self):
        import src.api_accounts as mod
        with patch.object(mod, "_get_supabase", return_value=self._client([])):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(mod.router)
            resp = TestClient(app).get("/api/accounts")
        self.assertEqual(resp.json(), [])


class ApiAccountsDetailTests(unittest.TestCase):

    def _client_detail(self, rows):
        sb = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=rows)
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        sb.table.return_value.select.return_value = chain
        return sb

    def test_get_default_account_200(self):
        import src.api_accounts as mod
        with patch.object(mod, "_get_supabase", return_value=self._client_detail([_account_row()])):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(mod.router)
            resp = TestClient(app).get("/api/accounts/default")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["account_id"], "default")

    def test_get_missing_account_404(self):
        import src.api_accounts as mod
        with patch.object(mod, "_get_supabase", return_value=self._client_detail([])):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(mod.router)
            resp = TestClient(app).get("/api/accounts/nonexistent")
        self.assertEqual(resp.status_code, 404)

    def test_risk_limits_returned_as_dict(self):
        import src.api_accounts as mod
        row = _account_row(risk_limits={"max_daily_loss_pct": 3.0, "max_positions": 2})
        with patch.object(mod, "_get_supabase", return_value=self._client_detail([row])):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(mod.router)
            resp = TestClient(app).get("/api/accounts/default")
        limits = resp.json()["risk_limits"]
        self.assertEqual(limits["max_daily_loss_pct"], 3.0)


if __name__ == "__main__":
    unittest.main()
