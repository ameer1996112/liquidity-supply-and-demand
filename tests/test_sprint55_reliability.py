"""Sprint 5.5 – Safety & reliability test suite.

Scenarios covered
─────────────────
1) Chaos / integration-style behaviours:
   - RedisTransport reset semantics (simulated Redis restart mid-run)
   - MetaApiAdapter HTTP retry behaviour on temporary failures
   - Worker idempotency on duplicate trade_key (duplicate webhook / crash+replay)

2) Invariants:
   - No double order placement for same client_order_id / trade_key
   - No ACTIVE/OPEN position is created without broker confirmation
   - Every reject/block path includes a reason string and audit entry hook
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

from src.adapters.execution.interfaces import ExecutionResult
from src.adapters.execution.meta_api_adapter import MetaApiAdapter
from src.core.transport import InMemoryTransport, RedisTransport


class RedisChaosTests(unittest.TestCase):
    """Chaos-style checks for Redis transport behaviour."""

    @patch("src.adapters.redis_queue.reset_redis_client")
    def test_redis_transport_reset_delegates_to_helper(self, mock_reset):
        """RedisTransport.reset() must always call reset_redis_client() exactly once."""
        t = RedisTransport()

        t.reset()

        mock_reset.assert_called_once_with()


class WorkerQueueChaosTests(unittest.TestCase):
    """Chaos scenario: worker crash/restart while queue still has messages."""

    def test_worker_restart_drains_remaining_messages_without_duplicates(self):
        """Simulate crash after first message; restarted worker must process the rest exactly once."""
        from src.core.observers.base import WorkerSubject

        transport = InMemoryTransport()

        # Enqueue three distinct payloads identified by trade_key.
        payloads = [
            {"symbol": "XAUUSD", "side": "buy", "size": 0.1, "trade_key": "tk-1"},
            {"symbol": "XAUUSD", "side": "buy", "size": 0.1, "trade_key": "tk-2"},
            {"symbol": "XAUUSD", "side": "buy", "size": 0.1, "trade_key": "tk-3"},
        ]
        for p in payloads:
            transport.enqueue(json.dumps(p))

        processed_keys: list[str] = []

        def _process(payload):
            processed_keys.append(payload.get("trade_key"))

        # First "worker" processes a single message then "crashes".
        subject1 = WorkerSubject(process_fn=_process)
        task = transport.dequeue(timeout=0)
        self.assertIsNotNone(task)
        _key, payload_str = task
        subject1.process_signal(json.loads(payload_str))
        self.assertEqual(processed_keys, ["tk-1"])

        # Simulate crash by discarding subject1 and starting a fresh worker instance.
        subject2 = WorkerSubject(process_fn=_process)

        # Second worker drains the remaining messages from the same transport.
        while True:
            task = transport.dequeue(timeout=0)
            if task is None:
                break
            _key, payload_str = task
            subject2.process_signal(json.loads(payload_str))

        # All messages were processed exactly once; queue is empty.
        self.assertCountEqual(processed_keys, ["tk-1", "tk-2", "tk-3"])
        self.assertEqual(len(processed_keys), 3)
        self.assertEqual(transport.queue_size, 0)

    @patch("src.adapters.redis_queue.blpop_queue")
    def test_redis_transport_recovers_after_temporary_error(self, mock_blpop):
        """Simulate Redis restart: first blpop errors, subsequent call succeeds."""

        # First call raises a connection-style error, second returns a payload.
        mock_blpop.side_effect = [
            ConnectionError("redis down"),
            ("trading_queue", '{"ok":1}'),
        ]

        t = RedisTransport()

        # First dequeue surfaces the connection error to the caller.
        with self.assertRaises(ConnectionError):
            _ = t.dequeue(timeout=1)

        # Caller (e.g. worker.run) is expected to call reset() here in production;
        # we just ensure a subsequent dequeue can succeed once Redis is back.
        mock_blpop.side_effect = [("trading_queue", '{"ok":1}')]
        result = t.dequeue(timeout=1)

        self.assertEqual(result, ("trading_queue", '{"ok":1}'))


class MetaApiRetryChaosTests(unittest.TestCase):
    """Chaos tests around MetaApiAdapter retry / failure handling."""

    @patch("src.adapters.execution.meta_api_adapter.time.sleep")
    @patch("src.adapters.execution.meta_api_adapter.requests.post")
    def test_request_with_retry_recovers_after_timeouts(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
    ):
        """Transient broker failure (timeouts) should trigger retries then succeed."""

        # Two transient failures, then success.
        success_resp = MagicMock(status_code=200)
        mock_post.side_effect = [
            requests.exceptions.Timeout("t1"),
            requests.exceptions.ConnectionError("conn"),
            success_resp,
        ]

        adapter = MetaApiAdapter(token="test-token", account_id="acc-id")

        resp = adapter._request_with_retry(
            "POST",
            "https://example.test/trade",
            timeout=1,
            json={"symbol": "XAUUSD"},
        )

        self.assertIs(resp, success_resp)
        # Should have tried exactly three times.
        self.assertEqual(mock_post.call_count, 3)
        # Backoff sleep must have been invoked at least once for the failures.
        self.assertGreaterEqual(mock_sleep.call_count, 1)

    @patch("src.adapters.execution.meta_api_adapter.time.sleep")
    @patch("src.adapters.execution.meta_api_adapter.requests.post")
    def test_request_with_retry_returns_none_after_exhausted_retries(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
    ):
        """Permanent broker failure should return None after exhausting retries."""

        mock_post.side_effect = requests.exceptions.Timeout("always-timeout")

        adapter = MetaApiAdapter(token="test-token", account_id="acc-id")

        resp = adapter._request_with_retry(
            "POST",
            "https://example.test/trade",
            timeout=1,
            json={"symbol": "XAUUSD"},
        )

        self.assertIsNone(resp)
        # MAX_RETRIES+1 attempts; we just assert multiple calls happened.
        self.assertGreater(mock_post.call_count, 1)
        self.assertGreaterEqual(mock_sleep.call_count, 1)


class IdempotencyAndRestartTests(unittest.TestCase):
    """Idempotency semantics for duplicate webhook bursts / worker restarts."""

    def setUp(self) -> None:
        # Minimal settings stub used by _execute_for_profile.
        self.settings = SimpleNamespace()

    @patch("src.worker._run_account_guards", return_value=None)
    @patch("src.worker.save_result")
    @patch("src.worker.logic.process_trade")
    @patch("src.worker._exists_trade_key", return_value=True)
    def test_existing_trade_key_skips_execution(
        self,
        mock_exists: MagicMock,
        mock_process_trade: MagicMock,
        mock_save_result: MagicMock,
        _mock_guards: MagicMock,
    ):
        """Duplicate trade_key (e.g. replay after crash) must not execute again."""
        import src.worker as worker_mod

        payload = {
            "symbol": "XAUUSD",
            "side": "buy",
            "size": 0.1,
            "run_mode": "PAPER",
            "trade_key": "tk-123",
        }
        profile = {"id": 7, "name": "acc-1"}
        ai_result = {"rf_prob": 0.8, "decision": "GO"}

        worker_mod._execute_for_profile(
            payload=payload,
            profile=profile,
            ai_result=ai_result,
            dry_run=False,
            s=self.settings,
            current_equity_global=100_000.0,
        )

        mock_exists.assert_called_once_with("tk-123", profile["id"])
        mock_process_trade.assert_not_called()
        mock_save_result.assert_not_called()

    @patch("src.worker._run_account_guards", return_value=None)
    @patch("src.worker.save_result")
    @patch("src.worker.logic.process_trade")
    @patch("src.worker._exists_trade_key", side_effect=[False, True])
    def test_first_call_executes_second_call_skipped_for_same_trade_key(
        self,
        mock_exists: MagicMock,
        mock_process_trade: MagicMock,
        mock_save_result: MagicMock,
        _mock_guards: MagicMock,
    ):
        """First delivery executes; duplicate (after restart) is idempotently skipped."""
        import src.worker as worker_mod

        payload = {
            "symbol": "XAUUSD",
            "side": "buy",
            "size": 0.1,
            "run_mode": "PAPER",
            "trade_key": "tk-dup",
        }
        profile = {"id": 3, "name": "acc-main"}
        ai_result = {"rf_prob": 0.9, "decision": "GO"}

        # First processing (no existing row yet).
        worker_mod._execute_for_profile(
            payload=payload.copy(),
            profile=profile,
            ai_result=ai_result,
            dry_run=False,
            s=self.settings,
            current_equity_global=80_000.0,
        )
        # Second processing simulates duplicate webhook or replay after crash.
        worker_mod._execute_for_profile(
            payload=payload.copy(),
            profile=profile,
            ai_result=ai_result,
            dry_run=False,
            s=self.settings,
            current_equity_global=80_000.0,
        )

        # Two idempotency checks, but only one actual execution.
        self.assertEqual(mock_exists.call_count, 2)
        mock_process_trade.assert_called_once()
        # No extra save_result calls should be produced by the skip path.
        # (Any guard failures would still call save_result, but here guards pass.)
        self.assertEqual(mock_save_result.call_count, 0)


class MultiAccountSignalRowTests(unittest.TestCase):
    def test_multi_account_payloads_reuse_receipt_signal_id_only_once(self):
        import src.worker as worker_mod

        payload = {
            "symbol": "XAUUSD",
            "side": "buy",
            "run_mode": "LIVE",
            "_signal_id": 321,
            "_webhook_receipt_id": "receipt-abc",
        }

        profile_payloads = worker_mod._build_multi_account_profile_payloads(payload, 3)

        self.assertEqual(len(profile_payloads), 3)
        self.assertEqual(profile_payloads[0]["_signal_id"], 321)
        self.assertNotIn("_signal_id", profile_payloads[1])
        self.assertNotIn("_signal_id", profile_payloads[2])
        self.assertEqual(profile_payloads[1]["_webhook_receipt_id"], "receipt-abc")
        self.assertEqual(profile_payloads[2]["_webhook_receipt_id"], "receipt-abc")
        self.assertEqual(payload["_signal_id"], 321)


class GuardAuditInvariantTests(unittest.TestCase):
    """Guard / rejection invariants: every block must have reason + audit hook."""

    @patch("src.worker.log_guard_decision")
    @patch("src.worker.save_result")
    def test_symbol_whitelist_block_has_reason_and_audit(
        self,
        mock_save_result: MagicMock,
        mock_log_guard: MagicMock,
    ):
        """Non-whitelisted symbol must be rejected with reason + guard_decision."""
        import src.worker as worker_mod

        payload = {
            "symbol": "UNSUPPORTED_XXX",
            "side": "buy",
            "entry": 1.0,
            "sl": 0.9,
            "tp": 1.1,
            "size": 0.1,
            "run_mode": "PAPER",
            "account_balance": 50_000,
        }

        worker_mod.process_trade(payload)

        # save_result called once with status and non-empty note.
        mock_save_result.assert_called_once()
        _payload_arg, status_arg, note_arg, prob_arg = mock_save_result.call_args[0][:4]
        self.assertEqual(status_arg, "symbol_blacklisted")
        self.assertIsInstance(note_arg, str)
        self.assertTrue(note_arg.strip())
        self.assertEqual(prob_arg, 0.0)

        # log_guard_decision invoked with guard name and same reason.
        mock_log_guard.assert_called_once()
        guard_name, result, reason, symbol = mock_log_guard.call_args[0][:4]
        self.assertEqual(guard_name, "symbol_whitelist")
        self.assertEqual(result, "rejected")
        self.assertEqual(symbol, payload["symbol"])
        self.assertIsInstance(reason, str)
        self.assertTrue(reason.strip())

    @patch("src.worker.log_guard_decision")
    @patch("src.worker.save_result")
    def test_zero_size_rejection_has_detailed_reason(
        self,
        mock_save_result: MagicMock,
        mock_log_guard: MagicMock,
    ):
        """Size <= 0 must be rejected with an explanatory, non-empty note."""
        import src.worker as worker_mod

        payload = {
            "symbol": "XAUUSD",
            "side": "buy",
            "entry": 2500.0,
            "sl": 2490.0,
            "tp": 2530.0,
            "size": 0.0,
            "account_balance": 10_000,
            "run_mode": "PAPER",
        }

        worker_mod.process_trade(payload)

        mock_save_result.assert_called_once()
        _payload_arg, status_arg, note_arg, prob_arg = mock_save_result.call_args[0][:4]
        self.assertEqual(status_arg, "filtered")
        self.assertIsInstance(note_arg, str)
        self.assertIn("size", note_arg)
        self.assertTrue(note_arg.strip())
        self.assertEqual(prob_arg, 0.0)
        # Audit hook must record the guard decision.
        # Note: since DEV-98, size checks are unified under 'global_safety' guard name.
        mock_log_guard.assert_called_once()
        guard_name, result, reason, symbol = mock_log_guard.call_args[0][:4]
        self.assertIn(guard_name, ("size_guard", "global_safety"),
                      "Guard name must be 'global_safety' (new) or 'size_guard' (legacy)")
        self.assertEqual(result, "rejected")
        self.assertEqual(symbol, payload["symbol"])
        self.assertIn("size", reason)

    @patch("src.adapters.execution.router.get_adapter")
    @patch("src.logic.update_alert_status")
    def test_open_status_not_set_when_submitted_without_broker_id(
        self,
        mock_update_status: MagicMock,
        mock_get_adapter: MagicMock,
    ):
        """Submitted execution without broker_order_id must not mark trade as OPEN."""
        from src import logic

        class AdapterWithoutTicket:
            def submit_order(self, request):
                return ExecutionResult(
                    status="submitted",
                    broker_order_id=None,
                    client_order_id=request.client_order_id,
                    message="pending broker confirmation",
                )

        mock_get_adapter.return_value = AdapterWithoutTicket()

        payload = {
            "symbol": "XAUUSD",
            "side": "buy",
            "entry": 2500.0,
            "sl": 2490.0,
            "tp": 2530.0,
            "size": 0.1,
            "run_mode": "LIVE",
        }

        with patch("config.get_settings") as mock_settings, patch(
            "src.logic.save_alert", return_value=1
        ), patch("src.logic.init_supabase"):
            mock_settings.return_value = SimpleNamespace(
                run_mode="LIVE",
                live_trading_enabled=True,
                account_balance=50_000,
                risk_percent=1.0,
                tca_enabled=False,
                kelly_enabled=False,
                min_rr_ratio=0.0,
            )

            logic.process_trade(payload, dry_run=False, ai_result=None, profile=None)

        # update_alert_status must never be called with status="OPEN" without broker confirmation.
        for call in mock_update_status.call_args_list:
            _alert_id, status_arg = call[0][:2]
            self.assertNotEqual(status_arg, "OPEN")

    @patch("src.adapters.execution.router.get_adapter")
    def test_no_open_position_when_execution_fails(
        self,
        mock_get_adapter: MagicMock,
    ):
        """Execution failure must not mark a trade as OPEN in the DB."""
        from src import logic

        # Adapter that always fails execution (e.g. broker outage).
        class FailingAdapter:
            def submit_order(self, request):
                return ExecutionResult(
                    status="failed",
                    broker_order_id=None,
                    client_order_id=request.client_order_id,
                    message="temporary broker failure",
                )

            def close_order(self, request):  # pragma: no cover - not used here
                return ExecutionResult(
                    status="failed",
                    broker_order_id=None,
                    client_order_id=request.client_order_id,
                    message="close failed",
                )

        mock_get_adapter.return_value = FailingAdapter()

        payload = {
            "symbol": "XAUUSD",
            "side": "buy",
            "entry": 2500.0,
            "sl": 2490.0,
            "tp": 2530.0,
            "size": 0.1,
            "run_mode": "LIVE",
            "zone_id": 12345,
            "zone_type": "demand",
            "zone_top": 2502.0,
            "zone_bottom": 2495.0,
            "zone_size_pips": 7.0,
            "liq_swept": True,
            "target_swept": True,
            "caused_sweep": True,
            "is_accuracy": False,
            "score": 90,
            "freshness": 1,
            "session": 2,
            "atr_ratio": 0.7,
            "trend": 1,
            "rsi": 35.0,
            "htf_trend": 1,
            "rvol": 1.2,
            "adx": 28.0,
            "touch_count": 1,
            "base_quality": 100,
            "departure_strength": 70.0,
            "liquidity_distance": 80.0,
            "liquidity_spread": 60.0,
            "return_strength": 95.0,
            "liquidity_distance_pips": 20.0,
            "liquidity_spread_pips": 40.0,
        }

        # Ensure settings.live_trading_enabled is True so logic takes the live path,
        # but stub out save_alert / init_supabase so no real Supabase calls occur.
        with patch("config.get_settings") as mock_settings, patch(
            "src.logic.save_alert", return_value=1
        ), patch("src.logic.init_supabase"):
            mock_settings.return_value = SimpleNamespace(
                run_mode="LIVE",
                live_trading_enabled=True,
                account_balance=50_000,
                risk_percent=1.0,
                tca_enabled=False,
                kelly_enabled=False,
                min_rr_ratio=0.0,
            )

            with patch("src.adapters.supabase.supabase") as supa_mock:
                table_mock = MagicMock()
                supa_mock.table.return_value = table_mock

                logic.process_trade(payload, dry_run=False, ai_result=None, profile=None)

        # We expect alert save, but NO update that sets status="OPEN".
        update_calls = table_mock.update.call_args_list
        for call in update_calls:
            update_payload = call[0][0]
            self.assertNotEqual(update_payload.get("status"), "OPEN")


if __name__ == "__main__":
    unittest.main()
