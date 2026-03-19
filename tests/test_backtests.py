"""
Sprint 4.1: Backtest Lab tests.
Sprint 4.2: Look-ahead bias detection tests.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.services.lookahead_bias_detector import (
    LookAheadBiasError,
    check_future_timestamp,
    check_htf_alignment,
    filter_candles_to_time,
    get_decision_ts_from_signal,
)
from src.services.ai_decision_cache import (
    build_cache_key,
    cache_get,
    cache_set,
    signal_hash,
    candle_context_hash,
)
from src.services.backtest_engine import (
    _compute_metrics,
    _paper_fill_from_signal,
    _signal_to_payload,
    run_backtest,
)


class AiDecisionCacheTests(unittest.TestCase):
    def test_signal_hash_deterministic(self):
        p = {"symbol": "XAUUSD", "side": "buy", "entry": 2650, "sl": 2640, "tp": 2670}
        h1 = signal_hash(p)
        h2 = signal_hash(p)
        self.assertEqual(h1, h2)

    def test_signal_hash_different_payloads(self):
        h1 = signal_hash({"symbol": "XAUUSD", "side": "buy"})
        h2 = signal_hash({"symbol": "EURUSD", "side": "sell"})
        self.assertNotEqual(h1, h2)

    def test_build_cache_key(self):
        k = build_cache_key("abc", "def", "gpt-4")
        self.assertIsInstance(k, str)
        self.assertEqual(len(k), 32)

    def test_candle_context_hash_empty(self):
        self.assertEqual(len(candle_context_hash([])), 32)

    def test_cache_set_get(self):
        mock_sb = MagicMock()
        cache_set(mock_sb, "key123", {"decision": "GO", "rf_prob": 0.7})
        mock_sb.table.assert_called_with("ai_decision_cache")
        mock_sb.table.return_value.upsert.assert_called_once()

    def test_cache_get_miss(self):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )
        self.assertIsNone(cache_get(mock_sb, "nonexistent"))

    def test_cache_get_hit(self):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"decision_json": {"decision": "GO", "rf_prob": 0.8}}]
        )
        result = cache_get(mock_sb, "hit_key")
        self.assertIsNotNone(result)
        self.assertEqual(result["decision"], "GO")


class LookaheadBiasDetectorTests(unittest.TestCase):
    """Sprint 4.2: Look-ahead bias detection."""

    def test_check_future_timestamp_raises(self):
        with self.assertRaises(LookAheadBiasError) as ctx:
            check_future_timestamp(1000.0, 500.0, label="candle")
        self.assertIn("Look-ahead bias", str(ctx.exception))
        self.assertIn("1000", str(ctx.exception))
        self.assertIn("500", str(ctx.exception))
        self.assertIn("LOOKAHEAD_BIAS_FUTURE_TIMESTAMP", str(ctx.exception))

    def test_check_future_timestamp_ok(self):
        check_future_timestamp(500.0, 1000.0, label="candle")
        check_future_timestamp(500.0, 500.0, label="candle")

    def test_check_htf_alignment_raises(self):
        # Bar closes at 1000, decision at 999 - bar not yet closed
        with self.assertRaises(LookAheadBiasError) as ctx:
            check_htf_alignment(1000.0, "5m", 999.0)
        self.assertIn("HTF alignment", str(ctx.exception))
        self.assertIn("LOOKAHEAD_BIAS_HTF_ALIGNMENT", str(ctx.exception))

    def test_check_htf_alignment_ok(self):
        check_htf_alignment(1000.0, "5m", 1000.0)
        check_htf_alignment(1000.0, "5m", 1001.0)

    def test_filter_candles_to_time_strict_raises_on_future(self):
        decision_ts = 1000.0
        candles = [
            {"time": 998, "open": 1, "high": 2, "low": 0.5, "close": 1.5},
            {"time": 1005, "open": 1, "high": 2, "low": 0.5, "close": 1.5},  # future
        ]
        with self.assertRaises(LookAheadBiasError) as ctx:
            filter_candles_to_time(candles, decision_ts, strict=True)
        self.assertIn("Look-ahead bias", str(ctx.exception))
        self.assertIn("1005", str(ctx.exception))
        self.assertIn("LOOKAHEAD_BIAS_FUTURE_CANDLE", str(ctx.exception))

    def test_filter_candles_to_time_returns_valid_only(self):
        decision_ts = 1000.0
        candles = [
            {"time": 990, "open": 1, "high": 2, "low": 0.5, "close": 1.5},
            {"time": 995, "open": 1, "high": 2, "low": 0.5, "close": 1.5},
            {"time": 1000, "open": 1, "high": 2, "low": 0.5, "close": 1.5},
        ]
        out = filter_candles_to_time(candles, decision_ts, strict=True)
        self.assertEqual(len(out), 3)

    def test_get_decision_ts_from_signal_iso(self):
        sig = {"created_at": "2025-01-15T10:00:00Z"}
        ts = get_decision_ts_from_signal(sig)
        self.assertIsInstance(ts, float)
        self.assertGreater(ts, 1736930000)  # ~2025-01-15
        self.assertLess(ts, 1737020000)

    def test_get_decision_ts_from_signal_unix(self):
        sig = {"created_at": 1736931600}  # 2025-01-15 10:00 UTC
        ts = get_decision_ts_from_signal(sig)
        self.assertEqual(ts, 1736931600.0)

    def test_get_decision_ts_from_signal_missing_timestamp(self):
        with self.assertRaises(LookAheadBiasError) as ctx:
            get_decision_ts_from_signal({})
        self.assertIn("LOOKAHEAD_BIAS_SIGNAL_NO_TIMESTAMP", str(ctx.exception))
        self.assertIn("no valid timestamp", str(ctx.exception))


class BacktestEngineTests(unittest.TestCase):
    def test_signal_to_payload(self):
        sig = {
            "symbol": "GBPJPY",
            "side": "sell",
            "entry": 188.5,
            "sl": 189,
            "tp": 187,
            "size": 0.1,
            "zone_id": 123,
            "score": 72,
            "entry_model": "FLIP",
        }
        p = _signal_to_payload(sig)
        self.assertEqual(p["symbol"], "GBPJPY")
        self.assertEqual(p["side"], "sell")
        self.assertEqual(p["run_mode"], "PAPER")

    def test_paper_fill_from_signal_with_pnl(self):
        sig = {"pnl_usd": 100.5, "outcome": "win", "exit_price": 190, "closed_at": "2025-01-01"}
        p = {"entry": 188, "tp": 190, "sl": 187}
        fill = _paper_fill_from_signal(sig, p)
        self.assertIsNotNone(fill)
        self.assertEqual(fill["pnl"], 100.5)

    def test_compute_metrics(self):
        trades = [
            {"outcome": "win", "pnl": 100},
            {"outcome": "win", "pnl": 50},
            {"outcome": "loss", "pnl": -60},
        ]
        m = _compute_metrics(
            trades=trades,
            latencies=[10, 20, 15],
            rule_violations=2,
            daily_loss_hits=0,
            initial_cash=10000,
            final_equity=10090,
            peak=10100,
        )
        self.assertEqual(m["total_trades"], 3)
        self.assertEqual(m["winning_trades"], 2)
        self.assertEqual(m["losing_trades"], 1)
        self.assertAlmostEqual(m["win_rate"], 66.67, places=1)
        self.assertGreater(m["avg_latency_ms"], 0)

    @patch("src.services.backtest_engine._load_signals")
    @patch("src.services.backtest_engine._evaluate_with_cache")
    def test_backtest_fails_on_future_candle_data(self, mock_eval, mock_load):
        """Sprint 4.2: Deliberately injected future data causes backtest failure with clear error."""
        decision_ts = 1736931600  # 2025-01-15 10:00 UTC (unix)
        future_ts = 1736935200   # 2025-01-15 11:00 UTC (future bar)

        mock_load.return_value = [
            {
                "id": 1,
                "symbol": "XAUUSD",
                "side": "buy",
                "entry": 2650,
                "sl": 2640,
                "tp": 2670,
                "size": 0.01,
                "created_at": decision_ts,  # Use unix to avoid timezone parsing variance
                "pnl_usd": 100,
                "outcome": "win",
                "exit_price": 2670,
                "closed_at": "2025-01-15T12:00:00Z",
            }
        ]
        mock_eval.return_value = {"decision": "GO", "rf_prob": 0.7}

        config = {
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "initial_cash": 10000,
            "candles": [
                {"time": decision_ts - 300, "open": 2645, "high": 2655, "low": 2640, "close": 2650},
                {"time": future_ts, "open": 2650, "high": 2670, "low": 2648, "close": 2670},
            ],
            "timeframe": "5m",
        }

        with self.assertRaises(LookAheadBiasError) as ctx:
            run_backtest(1, config, MagicMock(), on_progress=None)

        err = ctx.exception
        self.assertIn("Look-ahead bias", str(err))
        self.assertIn(str(future_ts), str(err))
        self.assertIn(str(decision_ts), str(err))
        self.assertIn("LOOKAHEAD_BIAS_FUTURE_CANDLE", str(err))


class BacktestAPITests(unittest.TestCase):
    """Test API endpoints with mocked DB."""

    @patch("src.api_backtests._get_supabase")
    def test_start_backtest_creates_job(self, mock_get_sb):
        from fastapi.testclient import TestClient
        from src.api import app

        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": 42}]
        )
        mock_get_sb.return_value = mock_sb

        with patch("src.api_backtests._run_backtest_job"):
            client = TestClient(app)
            r = client.post(
                "/api/backtests",
                json={
                    "symbol": "XAUUSD",
                    "start_date": "2025-01-01",
                    "end_date": "2025-12-31",
                    "initial_cash": 10000,
                },
            )
            self.assertEqual(r.status_code, 200)
            data = r.json()
            self.assertEqual(data["id"], 42)
            self.assertEqual(data["status"], "pending")

    @patch("src.api_backtests._get_supabase")
    def test_stream_404_for_missing_job(self, mock_get_sb):
        """SSE stream returns 404 for nonexistent job."""
        from fastapi.testclient import TestClient
        from src.api import app

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=None
        )
        mock_get_sb.return_value = mock_sb

        client = TestClient(app)
        r = client.get("/api/backtests/99999/stream")
        self.assertEqual(r.status_code, 404)


class BacktestJobIntegrationTests(unittest.TestCase):
    """Sprint 4.1: Backtest job orchestration + SSE progress."""

    @patch("src.services.backtest_engine.run_backtest")
    @patch("src.api_backtests._get_supabase")
    def test_backtest_job_completes_and_updates_db(self, mock_get_sb, mock_run_backtest):
        """Background job marks row completed and emits final metrics."""
        import queue as queue_mod

        from src.api_backtests import _progress_queues, _run_backtest_job

        mock_sb = MagicMock()
        # SELECT config_snapshot
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data={"config_snapshot": {"symbol": "XAUUSD"}}
        )
        mock_get_sb.return_value = mock_sb

        metrics = {
            "win_rate": 55.0,
            "avg_r": 1.5,
            "max_drawdown_pct": 10.0,
            "total_trades": 10,
        }

        def _fake_run(backtest_id, config, supabase, on_progress=None):
            if on_progress:
                on_progress(50, "Halfway", {"symbol": config.get("symbol")})
            return metrics

        mock_run_backtest.side_effect = _fake_run

        job_id = 123
        q = queue_mod.Queue()
        _progress_queues[job_id] = q

        _run_backtest_job(job_id)

        # DB was updated to completed with metrics_json
        updates = [call[0][0] for call in mock_sb.table.return_value.update.call_args_list]
        self.assertTrue(any(u.get("status") == "completed" for u in updates))
        self.assertTrue(any(u.get("metrics_json") == metrics for u in updates))

        # Progress events flowed through queue, including final 100% Done
        seen_done = False
        while not q.empty():
            ev = q.get_nowait()
            if ev and ev.get("percent") == 100 and ev.get("message") == "Done":
                seen_done = True
        self.assertTrue(seen_done)

    @patch("src.api_backtests._get_supabase")
    def test_stream_emits_progress_events(self, mock_get_sb):
        """SSE endpoint streams queued progress events for existing job."""
        import queue as queue_mod

        from fastapi.testclient import TestClient
        from src.api import app
        from src.api_backtests import _progress_queues

        mock_sb = MagicMock()
        # Job exists
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data={"id": 1}
        )
        mock_get_sb.return_value = mock_sb

        job_id = 1
        q = queue_mod.Queue()
        _progress_queues[job_id] = q

        # Pre-seed queue so generator has data immediately
        q.put_nowait({"percent": 10, "message": "Boot", "extra": {}})
        q.put_nowait({"percent": 100, "message": "Done", "extra": {}})
        q.put_nowait(None)

        client = TestClient(app)
        with client.stream("GET", f"/api/backtests/{job_id}/stream") as response:
            body = b"".join(chunk for chunk in response.iter_bytes())

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"percent": 10', body)
        self.assertIn(b'"percent": 100', body)


class BacktestCacheIntegrationTests(unittest.TestCase):
    """Sprint 4.1: AI decision cache integration with backtest engine."""

    @patch("src.services.ai_decision_cache.cache_get")
    @patch("src.services.ai_decision_cache.cache_set")
    @patch("src.agents.supervisor.Supervisor")
    def test_rerun_hits_cache_no_second_ai_call(
        self,
        MockSupervisor,
        mock_cache_set,
        mock_cache_get,
    ):
        """Second evaluation for same payload/context should use cache."""
        from src.services.backtest_engine import _evaluate_with_cache

        supabase = MagicMock()
        payload = {
            "symbol": "XAUUSD",
            "side": "buy",
            "entry": 2650,
            "sl": 2640,
            "tp": 2670,
            "size": 0.1,
            "zone_id": 123,
            "score": 70,
            "entry_model": "FLIP",
        }
        config = {
            "candles": [
                {"open": 2645, "high": 2655, "low": 2640, "close": 2650},
                {"open": 2650, "high": 2660, "low": 2645, "close": 2655},
            ],
            "timeframe": "5m",
        }

        ai_result = {"decision": "GO", "rf_prob": 0.72}
        mock_cache_get.side_effect = [None, ai_result]
        MockSupervisor.return_value.evaluate.return_value = ai_result

        # First call should miss cache and invoke Supervisor.evaluate once
        out1 = _evaluate_with_cache(supabase, payload, config)
        # Second call should hit cache and not call evaluate again
        out2 = _evaluate_with_cache(supabase, payload, config)

        self.assertEqual(out1, ai_result)
        self.assertEqual(out2, ai_result)
        self.assertEqual(MockSupervisor.return_value.evaluate.call_count, 1)
        self.assertGreaterEqual(mock_cache_set.call_count, 1)

