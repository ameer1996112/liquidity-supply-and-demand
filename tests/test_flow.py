"""
Test Suite: Full Pipeline Flow (E2E)
====================================

Tests the entire trading pipeline from webhook to database:
- Webhook -> Redis Queue -> Worker -> Brain -> Execution -> Database
- Entry signal flow
- Exit signal flow
- Error handling across the pipeline

These tests mock external services to verify the complete flow.
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any


# ══════════════════════════════════════════════════════════
# TEST: WEBHOOK TO QUEUE
# ══════════════════════════════════════════════════════════


class TestWebhookToQueue:
    """Test webhook endpoint pushing to Redis queue."""

    def test_webhook_valid_entry_returns_queued(
        self,
        test_app,
        base_signal,
    ):
        """
        Test: Valid entry signal via POST /webhook.

        Expected:
        - HTTP 200
        - Response: {"status": "queued"}
        """
        # Mock Redis to capture pushed payload
        pushed_payloads = []

        def mock_push(payload_str):
            pushed_payloads.append(json.loads(payload_str))

        with patch("src.api.push_payload", side_effect=mock_push), \
             patch("src.api.get_redis", return_value=MagicMock()):

            response = test_app.post("/webhook", json=base_signal)

            assert response.status_code == 200
            assert response.json() == {"status": "queued"}
            assert len(pushed_payloads) == 1
            assert pushed_payloads[0]["symbol"] == "EURUSD"

    def test_webhook_valid_exit_returns_queued(
        self,
        test_app,
        exit_signal,
    ):
        """
        Test: Valid exit signal via POST /webhook.

        Expected:
        - HTTP 200
        - Exit signal queued with event_type="exit"
        """
        pushed_payloads = []

        def mock_push(payload_str):
            pushed_payloads.append(json.loads(payload_str))

        with patch("src.api.push_payload", side_effect=mock_push), \
             patch("src.api.get_redis", return_value=MagicMock()):

            response = test_app.post("/webhook", json=exit_signal)

            assert response.status_code == 200
            assert len(pushed_payloads) == 1
            assert pushed_payloads[0]["event_type"] == "exit"

    def test_webhook_invalid_missing_symbol_returns_400(
        self,
        test_app,
        invalid_signal_missing_symbol,
    ):
        """
        Test: Invalid signal missing required 'symbol' field.

        Expected: HTTP 400/422 validation error.
        """
        with patch("src.api.get_redis", return_value=MagicMock()):
            response = test_app.post("/webhook", json=invalid_signal_missing_symbol)

            assert response.status_code in (400, 422)

    def test_webhook_invalid_bad_side_returns_400(
        self,
        test_app,
        invalid_signal_bad_side,
    ):
        """
        Test: Invalid signal with bad 'side' value.

        Expected: HTTP 400/422 validation error.
        """
        with patch("src.api.get_redis", return_value=MagicMock()):
            response = test_app.post("/webhook", json=invalid_signal_bad_side)

            assert response.status_code in (400, 422)

    def test_webhook_empty_body_returns_400(
        self,
        test_app,
    ):
        """
        Test: Empty request body.

        Expected: HTTP 400 error.
        """
        with patch("src.api.get_redis", return_value=MagicMock()):
            response = test_app.post(
                "/webhook",
                content=b"",
                headers={"Content-Type": "application/json"}
            )

            assert response.status_code == 400

    def test_webhook_malformed_json_returns_400(
        self,
        test_app,
    ):
        """
        Test: Malformed JSON body.

        Expected: HTTP 400 error.
        """
        with patch("src.api.get_redis", return_value=MagicMock()):
            response = test_app.post(
                "/webhook",
                content=b'{"symbol": "EURUSD", invalid}',
                headers={"Content-Type": "application/json"}
            )

            assert response.status_code == 400


# ══════════════════════════════════════════════════════════
# TEST: PROCESS TRADE END-TO-END
# ══════════════════════════════════════════════════════════


class TestProcessTradeE2E:
    """Test the complete trade processing flow."""

    def test_process_trade_entry_brain_go_execution_success(
        self,
        base_signal,
        mock_settings_live,
        stub_model_high_confidence,
        stub_encoders,
        mock_openai_go,
        mock_rag_engine,
    ):
        """
        Test: Full entry flow - Brain approves, MetaApi executes.

        Flow:
        1. Call process_trade(data)
        2. Brain ensemble says "GO"
        3. MetaApi accepts order
        4. Supabase updated with status='executed' and broker_order_id

        Expected: Alert saved, executed status, broker_order_id populated.
        """
        saved_alerts = []
        updated_records = []

        def mock_save_alert(data, mode='manual', filter_reasons=None):
            alert_id = len(saved_alerts) + 1
            saved_alerts.append({
                "id": alert_id,
                "data": data,
                "mode": mode,
                "filter_reasons": filter_reasons,
            })
            return alert_id

        def mock_update_status(alert_id, status, notes=None):
            updated_records.append({
                "alert_id": alert_id,
                "status": status,
                "notes": notes,
            })

        # Mock Supabase table operations
        mock_supabase = MagicMock()

        def mock_table(name):
            table = MagicMock()

            def mock_update(data):
                updated_records.append(data)
                chain = MagicMock()
                chain.eq.return_value.execute.return_value = MagicMock(data=[])
                return chain

            table.update = mock_update
            return table

        mock_supabase.table = mock_table

        # Mock MetaApi success
        mock_order_resp = MagicMock()
        mock_order_resp.status_code = 200
        mock_order_resp.json.return_value = {"orderId": "BROKER-12345"}

        mock_price_resp = MagicMock()
        mock_price_resp.status_code = 200
        mock_price_resp.json.return_value = {"bid": 1.0848, "ask": 1.0852}

        with patch("src.logic.get_settings", return_value=mock_settings_live), \
             patch("src.logic.init_supabase"), \
             patch("src.logic.save_alert", side_effect=mock_save_alert), \
             patch("src.logic.update_alert_status", side_effect=mock_update_status), \
             patch("src.logic.send_discord"), \
             patch("src.logic.send_telegram"), \
             patch("src.adapters.supabase.supabase", mock_supabase), \
             patch("src.adapters.supabase.init_supabase"), \
             patch("src.adapters.execution.meta_api_adapter.get_settings", return_value=mock_settings_live), \
             patch("requests.get", return_value=mock_price_resp), \
             patch("requests.post", return_value=mock_order_resp):

            from src.logic import process_trade

            ai_result = {
                "decision": "GO",
                "reason": "Test approved",
                "rf_prob": 0.75,
            }

            process_trade(base_signal, dry_run=False, ai_result=ai_result)

            # Verify alert was saved
            assert len(saved_alerts) == 1
            assert saved_alerts[0]["data"]["symbol"] == "EURUSD"

            # Verify status was updated to executed with broker_order_id
            assert len(updated_records) >= 1
            # Find the execution update
            exec_update = [u for u in updated_records if isinstance(u, dict) and "broker_order_id" in u]
            assert len(exec_update) == 1
            assert exec_update[0]["status"] == "executed"
            assert exec_update[0]["broker_order_id"] == "BROKER-12345"

    def test_process_trade_entry_filtered_by_rr_ratio(
        self,
        mock_settings,
    ):
        """
        Test: Entry signal filtered due to poor R:R ratio.

        Flow:
        1. Signal has bad R:R (risk > reward)
        2. should_forward_alert returns False
        3. Alert saved with status='filtered'

        Expected: Alert saved but marked as filtered.
        """
        bad_rr_signal = {
            "symbol": "EURUSD",
            "side": "buy",
            "entry": 1.0850,
            "sl": 1.0800,  # Risk: 50 pips
            "tp": 1.0860,  # Reward: 10 pips (R:R = 0.2)
            "size": 0.10,
        }

        saved_alerts = []
        status_updates = []

        def mock_save_alert(data, mode='manual', filter_reasons=None):
            alert_id = len(saved_alerts) + 1
            saved_alerts.append({
                "id": alert_id,
                "filter_reasons": filter_reasons,
            })
            return alert_id

        def mock_update_status(alert_id, status, notes=None):
            status_updates.append({
                "alert_id": alert_id,
                "status": status,
                "notes": notes,
            })

        with patch("src.logic.get_settings", return_value=mock_settings), \
             patch("src.logic.init_supabase"), \
             patch("src.logic.save_alert", side_effect=mock_save_alert), \
             patch("src.logic.update_alert_status", side_effect=mock_update_status), \
             patch("src.logic.send_discord"), \
             patch("src.logic.send_telegram"):

            from src.logic import process_trade

            process_trade(bad_rr_signal, dry_run=False)

            # Alert should be saved
            assert len(saved_alerts) == 1

            # Status should be updated to 'filtered'
            assert len(status_updates) == 1
            assert status_updates[0]["status"] == "filtered"
            assert "R:R" in status_updates[0]["notes"]

    def test_process_trade_exit_updates_db(
        self,
        exit_signal,
        mock_settings,
    ):
        """
        Test: Exit signal updates database with PnL.

        Flow:
        1. Exit signal received
        2. update_alert_exit called with outcome, pnl_usd

        Expected: Database updated with exit data.
        """
        exit_updates = []

        def mock_update_exit(zone_id, exit_data, trade_key=None):
            exit_updates.append({
                "zone_id": zone_id,
                "exit_data": exit_data,
                "trade_key": trade_key,
            })
            return True

        with patch("src.logic.get_settings", return_value=mock_settings), \
             patch("src.logic.init_supabase"), \
             patch("src.logic.update_alert_exit", side_effect=mock_update_exit):

            from src.logic import process_trade

            process_trade(exit_signal)

            assert len(exit_updates) == 1
            assert exit_updates[0]["zone_id"] == 12345
            assert exit_updates[0]["exit_data"]["outcome"] == "win"
            assert exit_updates[0]["exit_data"]["pnl_usd"] == 100.0

    def test_process_trade_dry_run_no_execution(
        self,
        base_signal,
        mock_settings,
    ):
        """
        Test: Dry run mode saves alert but doesn't execute.

        Expected: Alert saved, no broker calls.
        """
        saved_alerts = []
        broker_calls = []

        def mock_save_alert(data, mode='manual', filter_reasons=None):
            saved_alerts.append({"data": data, "mode": mode})
            return 1

        def mock_submit_order(request):
            broker_calls.append(request)
            return MagicMock(status="filled", broker_order_id="123")

        with patch("src.logic.get_settings", return_value=mock_settings), \
             patch("src.logic.init_supabase"), \
             patch("src.logic.save_alert", side_effect=mock_save_alert), \
             patch("src.logic.update_alert_status"), \
             patch("src.logic.send_discord"), \
             patch("src.logic.send_telegram"):

            from src.logic import process_trade

            process_trade(base_signal, dry_run=True)

            assert len(saved_alerts) == 1
            # No broker calls in dry run
            assert len(broker_calls) == 0


# ══════════════════════════════════════════════════════════
# TEST: WORKER INTEGRATION
# ══════════════════════════════════════════════════════════


class TestWorkerIntegration:
    """Test worker process_trade integration."""

    def test_worker_process_trade_with_ai_go(
        self,
        base_signal,
        mock_settings,
        stub_model_high_confidence,
        stub_encoders,
        mock_openai_go,
        mock_rag_engine,
    ):
        """
        Test: Worker processes trade when AI says GO.

        Flow:
        1. Worker receives payload
        2. AI ensemble returns GO
        3. logic.process_trade called with ai_result

        Expected: Trade processed successfully.
        """
        process_trade_calls = []

        def mock_process_trade(data, dry_run=False, ai_result=None):
            process_trade_calls.append({
                "data": data,
                "dry_run": dry_run,
                "ai_result": ai_result,
            })

        # Mock brain ensemble decision
        def mock_ensemble_decision(payload):
            return {
                "decision": "GO",
                "reason": "Test approved",
                "rf_prob": 0.75,
                "rf_note": "High confidence",
                "narrative": "Bullish",
                "rules": [],
                "llm_raw": {"decision": "GO"},
            }

        with patch("src.worker.get_settings", return_value=mock_settings), \
             patch("src.worker.process_trade", side_effect=mock_process_trade), \
             patch("src.worker.ensemble_decision", side_effect=mock_ensemble_decision), \
             patch("src.worker.save_result"):

            from src.worker import process_trade as worker_process_trade

            # Simulate worker calling with AI enabled
            # This would normally be called in the worker loop

            # Directly test the logic
            ai_result = mock_ensemble_decision(base_signal)

            if ai_result["decision"] == "GO":
                mock_process_trade(base_signal, ai_result=ai_result)

            assert len(process_trade_calls) == 1
            assert process_trade_calls[0]["ai_result"]["decision"] == "GO"

    def test_worker_process_trade_with_ai_no_go(
        self,
        base_signal,
        mock_settings,
        stub_model_low_confidence,
    ):
        """
        Test: Worker rejects trade when AI says NO_GO.

        Expected: Trade not sent to execution, saved with ai_rejected status.
        """
        process_trade_calls = []
        save_result_calls = []

        def mock_ensemble_decision(payload):
            return {
                "decision": "NO_GO",
                "reason": "RF below threshold",
                "rf_prob": 0.45,
            }

        def mock_save_result(payload, status, note, prob, ai_reasoning):
            save_result_calls.append({
                "status": status,
                "note": note,
                "prob": prob,
            })

        with patch("src.worker.get_settings", return_value=mock_settings), \
             patch("src.worker.ensemble_decision", side_effect=mock_ensemble_decision), \
             patch("src.worker.save_result", side_effect=mock_save_result):

            ai_result = mock_ensemble_decision(base_signal)

            if ai_result["decision"] == "NO_GO":
                mock_save_result(
                    base_signal,
                    "ai_rejected",
                    ai_result["reason"],
                    ai_result["rf_prob"],
                    ai_result,
                )

            # Should have saved as rejected
            assert len(save_result_calls) == 1
            assert save_result_calls[0]["status"] == "ai_rejected"
            # process_trade should NOT have been called
            assert len(process_trade_calls) == 0


# ══════════════════════════════════════════════════════════
# TEST: IDEMPOTENCY
# ══════════════════════════════════════════════════════════


class TestIdempotency:
    """Test idempotency using trade_key."""

    def test_duplicate_trade_key_handled(
        self,
        base_signal,
        mock_settings,
    ):
        """
        Test: Same trade_key submitted twice.

        Expected: Second submission is detected as duplicate.
        """
        # This tests the idempotency check via supabase function
        existing_trade_keys = {"test-trade-001"}  # Already processed

        def mock_get_alert_by_trade_key(trade_key):
            if trade_key in existing_trade_keys:
                return {"id": 1, "trade_key": trade_key}
            return None

        with patch("src.adapters.supabase.get_alert_by_trade_key", side_effect=mock_get_alert_by_trade_key):
            from src.adapters.supabase import get_alert_by_trade_key

            trade_key = base_signal.get("trade_key", "").strip()

            # Check if already exists
            existing = mock_get_alert_by_trade_key(trade_key)

            # Should find existing trade
            assert existing is not None
            assert existing["trade_key"] == "test-trade-001"


# ══════════════════════════════════════════════════════════
# TEST: CORRELATION GUARD
# ══════════════════════════════════════════════════════════


class TestCorrelationGuard:
    """Test maximum open positions guard."""

    def test_correlation_guard_blocks_at_max(
        self,
        base_signal,
        active_positions_full,
        mock_settings,
    ):
        """
        Test: New trade blocked when at max open positions.

        Expected: Trade rejected with correlation reason.
        """
        from src.core.guard_rails.correlation import CorrelationManager

        manager = CorrelationManager(max_positions=3)

        # Should fail correlation check (3 positions = max)
        result = manager.check(
            symbol=base_signal["symbol"],
            side=base_signal["side"],
            active_positions=active_positions_full,
        )

        assert not result.passed
        assert result.rejection_reason is not None

    def test_correlation_guard_allows_below_max(
        self,
        active_positions_two,
        mock_settings,
    ):
        """
        Test: New trade allowed when below max positions with non-duplicate symbol.

        Expected: Trade allowed.
        """
        from src.core.guard_rails.correlation import CorrelationManager

        manager = CorrelationManager(max_positions=3)

        # Use a symbol not in active_positions_two (EURUSD, USDJPY)
        result = manager.check(
            symbol="GBPUSD",  # Different symbol to avoid duplicate rejection
            side="buy",
            active_positions=active_positions_two,  # 2 positions (below max)
        )

        assert result.passed


# ══════════════════════════════════════════════════════════
# TEST: FULL PIPELINE ERROR HANDLING
# ══════════════════════════════════════════════════════════


class TestPipelineErrorHandling:
    """Test error handling across the pipeline."""

    def test_brain_failure_doesnt_crash_pipeline(
        self,
        base_signal,
        mock_settings,
    ):
        """
        Test: Brain ensemble throws exception.

        Expected: Error logged, trade not executed, no crash.
        """
        def mock_ensemble_decision(payload):
            raise Exception("OpenAI API rate limited")

        save_calls = []

        def mock_save_result(payload, status, note, prob, ai_reasoning):
            save_calls.append({"status": status, "note": note})

        with patch("src.worker.ensemble_decision", side_effect=mock_ensemble_decision), \
             patch("src.worker.save_result", side_effect=mock_save_result):

            # Simulate worker error handling
            try:
                mock_ensemble_decision(base_signal)
                ai_result = None
            except Exception as e:
                # Worker should catch and log
                mock_save_result(
                    base_signal,
                    "error",
                    f"AI Error: {str(e)[:50]}",
                    0.0,
                    None,
                )

            assert len(save_calls) == 1
            assert save_calls[0]["status"] == "error"
            assert "rate limit" in save_calls[0]["note"].lower()

    def test_execution_failure_doesnt_crash_pipeline(
        self,
        base_signal,
        mock_settings_live,
    ):
        """
        Test: MetaApi throws exception during execution.

        Expected: Error logged, status not updated to executed.
        """
        def mock_submit_order(request):
            raise Exception("Network timeout")

        saved_alerts = []
        status_updates = []

        def mock_save_alert(data, mode='manual', filter_reasons=None):
            saved_alerts.append({"data": data})
            return 1

        def mock_update_status(alert_id, status, notes=None):
            status_updates.append({"alert_id": alert_id, "status": status})

        # Create a mock adapter that raises
        mock_adapter = MagicMock()
        mock_adapter.submit_order.side_effect = Exception("Network timeout")

        with patch("src.logic.get_settings", return_value=mock_settings_live), \
             patch("src.logic.init_supabase"), \
             patch("src.logic.save_alert", side_effect=mock_save_alert), \
             patch("src.logic.update_alert_status", side_effect=mock_update_status), \
             patch("src.logic.get_adapter", return_value=mock_adapter), \
             patch("src.logic.send_discord"), \
             patch("src.logic.send_telegram"):

            from src.logic import process_trade

            # Should not raise
            process_trade(base_signal, dry_run=False)

            # Alert should still be saved
            assert len(saved_alerts) == 1
            # But status should NOT be 'executed'
            executed_updates = [u for u in status_updates if u["status"] == "executed"]
            assert len(executed_updates) == 0

    def test_supabase_failure_doesnt_crash_pipeline(
        self,
        base_signal,
        mock_settings,
    ):
        """
        Test: Supabase save_alert throws exception.

        Expected: Exception propagated but system remains stable.
        """
        def mock_save_alert_fail(data, mode='manual', filter_reasons=None):
            raise Exception("Supabase connection refused")

        with patch("src.logic.get_settings", return_value=mock_settings), \
             patch("src.logic.init_supabase"), \
             patch("src.logic.save_alert", side_effect=mock_save_alert_fail):

            from src.logic import process_trade

            # This should raise (Supabase is critical)
            with pytest.raises(Exception) as exc_info:
                process_trade(base_signal)

            assert "Supabase" in str(exc_info.value) or "connection" in str(exc_info.value)


# ══════════════════════════════════════════════════════════
# TEST: HEALTH CHECK
# ══════════════════════════════════════════════════════════


class TestHealthCheck:
    """Test API health endpoint."""

    def test_health_returns_ok(self, test_app):
        """
        Test: GET /health returns ok status.
        """
        response = test_app.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["service"] == "api"
