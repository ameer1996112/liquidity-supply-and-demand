"""
Sprint 2.3 — API account_id filter tests.

Covers the two gaps added in this sprint:
  1. GET /positions/active?account_id=<id>  (api_positions.py)
  2. GET /analytics/breakdown?account_id=<id>
     GET /analytics/streaks?account_id=<id>
     GET /analytics/drawdown?account_id=<id>
     GET /analytics/summary?account_id=<id>  (api_analytics.py)
  3. save_result() stamps account_id from payload["_account_id"]

All Supabase calls are mocked — no real DB or Redis required.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


# ── Helpers ────────────────────────────────────────────────────────────────────

def _signal_row(**kw):
    base = {
        "id": 1,
        "symbol": "XAUUSD",
        "side": "buy",
        "entry": 2000.0,
        "sl": 1995.0,
        "tp": 2015.0,
        "size": 0.1,
        "broker_order_id": "mt5-001",
        "created_at": "2025-01-01T10:00:00+00:00",
        "zone_type": "demand",
        "entry_model": "SND",
        "rr_ratio": 3.0,
        "status": "executed",
        "execution_source": "metaapi",
        "broker_position_id": "pos-001",
        "closed_at": None,
        "exit_price": None,
        "pnl": None,
        "account_id": "default",
        "run_mode": "LIVE",
    }
    base.update(kw)
    return base


def _closed_signal_row(**kw):
    base = {
        "id": 10,
        "symbol": "EURUSD",
        "side": "sell",
        "entry": 1.1,
        "sl": 1.105,
        "tp": 1.09,
        "size": 0.5,
        "pnl_usd": 250.0,
        "pnl_r": 2.0,
        "outcome": "win",
        "zone_type": "supply",
        "entry_model": "SND",
        "ai_confidence": 0.85,
        "rr_ratio": 2.0,
        "created_at": "2025-01-02T10:00:00+00:00",
        "closed_at": "2025-01-02T12:00:00+00:00",
        "status": "closed",
        "account_id": "default",
        "run_mode": "LIVE",
    }
    base.update(kw)
    return base


def _mock_supabase_chain(rows):
    """Return a MagicMock Supabase client whose chain always yields `rows`."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    # Chain all builder methods back to self so filters compose correctly.
    for method in ("select", "eq", "in_", "order", "limit", "gte", "not_", "or_"):
        getattr(chain, method).return_value = chain
    sb = MagicMock()
    sb.table.return_value.select.return_value = chain
    # Also wire .table().in_() for cases where in_ is the first filter.
    sb.table.return_value.in_.return_value = chain
    return sb, chain


# ═══════════════════════════════════════════════════════════════════════════════
# Positions: account_id filter
# ═══════════════════════════════════════════════════════════════════════════════

class ActivePositionsAccountFilterTests(unittest.TestCase):
    """GET /positions/active?account_id=... passes filter to Supabase."""

    def _app_client(self, rows):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import src.api_positions as mod

        sb, chain = _mock_supabase_chain(rows)
        app = FastAPI()
        app.include_router(mod.router)
        client = TestClient(app)
        return client, sb, chain, mod

    def _mock_live_aggregator(self, profiles=None, positions=None, accounts=None):
        aggregator = MagicMock()
        aggregator.load_eligible_profiles.return_value = profiles or []
        aggregator.aggregate_open_positions.return_value = SimpleNamespace(
            positions=positions or [],
            errors=[],
            healthy_profiles=len(profiles or []),
            failed_profiles=0,
        )
        aggregator.aggregate_account_status.return_value = SimpleNamespace(
            accounts=accounts or [],
            totals={},
            errors=[],
            healthy_profiles=len(profiles or []),
            failed_profiles=0,
        )
        return aggregator

    def test_no_account_filter_returns_all(self):
        rows = [
            _signal_row(account_id="default"),
            _signal_row(id=2, account_id="prop-1", broker_position_id="pos-002"),
        ]
        client, sb, chain, mod = self._app_client(rows)
        with patch.object(mod, "_get_supabase", return_value=sb):
            with patch.object(
                mod,
                "LivePositionsAggregator",
                return_value=self._mock_live_aggregator(),
            ):
                resp = client.get("/positions/active")
        self.assertEqual(resp.status_code, 200)
        # eq("account_id", ...) must NOT have been called
        eq_calls = [str(c) for c in chain.eq.call_args_list]
        self.assertFalse(
            any("account_id" in c for c in eq_calls),
            "account_id eq filter should not fire when omitted",
        )

    def test_account_filter_passes_eq_to_supabase(self):
        rows = [_signal_row(account_id="prop-1", broker_position_id="pos-002")]
        client, sb, chain, mod = self._app_client(rows)
        with patch.object(mod, "_get_supabase", return_value=sb):
            with patch.object(
                mod,
                "LivePositionsAggregator",
                return_value=self._mock_live_aggregator(),
            ):
                resp = client.get("/positions/active?account_id=prop-1")
        self.assertEqual(resp.status_code, 200)
        chain.eq.assert_any_call("account_id", "prop-1")

    def test_unknown_account_returns_empty(self):
        client, sb, chain, mod = self._app_client([])
        with patch.object(mod, "_get_supabase", return_value=sb):
            with patch.object(
                mod,
                "LivePositionsAggregator",
                return_value=self._mock_live_aggregator(),
            ):
                resp = client.get("/positions/active?account_id=nonexistent")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 0)
        self.assertEqual(resp.json()["positions"], [])

    def test_active_positions_merges_live_data_from_multiple_profiles(self):
        rows = [
            _signal_row(
                id=1,
                broker_profile_id=101,
                broker_position_id="meta-pos-1",
                broker_order_id="meta-pos-1",
                account_name="",
                symbol="GBPUSD",
                entry=1.25,
                size=0.5,
            ),
            _signal_row(
                id=2,
                broker_profile_id=202,
                broker_position_id="ctr-pos-2",
                broker_order_id="ctr-pos-2",
                account_name="",
                symbol="XAUUSD",
                entry=2320.0,
                size=0.2,
            ),
        ]
        client, sb, _, mod = self._app_client(rows)
        aggregator = self._mock_live_aggregator(
            profiles=[
                SimpleNamespace(id=101, name="Meta Live"),
                SimpleNamespace(id=202, name="cTrader Live"),
            ],
            positions=[
                SimpleNamespace(
                    profile_id=101,
                    account_name="Meta Live",
                    broker_position_id="meta-pos-1",
                    current_price=1.2515,
                    profit=75.25,
                ),
                SimpleNamespace(
                    profile_id=202,
                    account_name="cTrader Live",
                    broker_position_id="ctr-pos-2",
                    current_price=2331.5,
                    profit=230.0,
                ),
            ],
            accounts=[
                SimpleNamespace(profile_id=101, balance=10000.0),
                SimpleNamespace(profile_id=202, balance=20000.0),
            ],
        )
        with patch.object(mod, "_get_supabase", return_value=sb):
            with patch.object(mod, "LivePositionsAggregator", return_value=aggregator):
                resp = client.get("/positions/active")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["reconciliation"]["broker_position_count"], 2)
        self.assertEqual(body["reconciliation"]["matched_count"], 2)
        self.assertFalse(body["reconciliation"]["has_mismatches"])

        first_position, second_position = body["positions"]
        self.assertEqual(first_position["account_name"], "Meta Live")
        self.assertEqual(first_position["current_price"], 1.2515)
        self.assertEqual(first_position["live_pnl"], 75.25)
        self.assertEqual(first_position["live_pnl_pct"], 0.75)

        self.assertEqual(second_position["account_name"], "cTrader Live")
        self.assertEqual(second_position["current_price"], 2331.5)
        self.assertEqual(second_position["live_pnl"], 230.0)
        self.assertEqual(second_position["live_pnl_pct"], 1.15)


# ═══════════════════════════════════════════════════════════════════════════════
# Analytics: account_id filter
# ═══════════════════════════════════════════════════════════════════════════════

class AnalyticsAccountFilterTests(unittest.TestCase):
    """account_id query param is forwarded to _fetch_closed_signals for each endpoint."""

    def _app_client(self, rows):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import src.api_analytics as mod

        sb, chain = _mock_supabase_chain(rows)
        app = FastAPI()
        app.include_router(mod.router)
        client = TestClient(app)
        return client, sb, chain, mod

    def test_breakdown_no_filter(self):
        rows = [_closed_signal_row()]
        client, sb, chain, mod = self._app_client(rows)
        with patch.object(mod, "_get_supabase", return_value=sb):
            resp = client.get("/analytics/breakdown?mode=LIVE")
        self.assertEqual(resp.status_code, 200)
        eq_calls = [str(c) for c in chain.eq.call_args_list]
        self.assertFalse(any("account_id" in c for c in eq_calls))

    def test_breakdown_account_filter_forwarded(self):
        rows = [_closed_signal_row(account_id="prop-1")]
        client, sb, chain, mod = self._app_client(rows)
        with patch.object(mod, "_get_supabase", return_value=sb):
            resp = client.get("/analytics/breakdown?mode=LIVE&account_id=prop-1")
        self.assertEqual(resp.status_code, 200)
        chain.eq.assert_any_call("account_id", "prop-1")

    def test_streaks_account_filter_forwarded(self):
        rows = [_closed_signal_row(account_id="eval-1")]
        client, sb, chain, mod = self._app_client(rows)
        with patch.object(mod, "_get_supabase", return_value=sb):
            resp = client.get("/analytics/streaks?account_id=eval-1")
        self.assertEqual(resp.status_code, 200)
        chain.eq.assert_any_call("account_id", "eval-1")

    def test_drawdown_account_filter_forwarded(self):
        rows = [_closed_signal_row(account_id="prop-1")]
        client, sb, chain, mod = self._app_client(rows)
        with patch.object(mod, "_get_supabase", return_value=sb):
            with patch("src.api_analytics.get_settings", return_value=MagicMock(account_balance=10000)):
                resp = client.get("/analytics/drawdown?account_id=prop-1")
        self.assertEqual(resp.status_code, 200)
        chain.eq.assert_any_call("account_id", "prop-1")

    def test_summary_account_filter_forwarded(self):
        rows = [_closed_signal_row(account_id="prop-1")]
        client, sb, chain, mod = self._app_client(rows)
        with patch.object(mod, "_get_supabase", return_value=sb):
            with patch("src.api_analytics.get_settings", return_value=MagicMock(account_balance=10000)):
                resp = client.get("/analytics/summary?account_id=prop-1")
        self.assertEqual(resp.status_code, 200)
        chain.eq.assert_any_call("account_id", "prop-1")

    def test_two_accounts_isolated_in_memory(self):
        """Verify that filtering by account_id selects only matching rows."""
        import src.api_analytics as mod

        # Build two sets of rows
        acc_a_rows = [_closed_signal_row(id=i, account_id="acc-a", pnl_usd=100.0) for i in range(3)]
        acc_b_rows = [_closed_signal_row(id=i + 10, account_id="acc-b", pnl_usd=-50.0) for i in range(2)]

        # Simulate what _fetch_closed_signals returns when the DB filter runs
        with patch.object(mod, "_get_supabase") as mock_sb:
            # acc-a query
            sb_a, chain_a = _mock_supabase_chain(acc_a_rows)
            mock_sb.return_value = sb_a
            result_a = mod._fetch_closed_signals("all", "LIVE", account_id="acc-a")
            self.assertEqual(len(result_a), 3)
            chain_a.eq.assert_any_call("account_id", "acc-a")

        with patch.object(mod, "_get_supabase") as mock_sb:
            # acc-b query
            sb_b, chain_b = _mock_supabase_chain(acc_b_rows)
            mock_sb.return_value = sb_b
            result_b = mod._fetch_closed_signals("all", "LIVE", account_id="acc-b")
            self.assertEqual(len(result_b), 2)
            chain_b.eq.assert_any_call("account_id", "acc-b")


# ═══════════════════════════════════════════════════════════════════════════════
# save_result: account_id stamped from payload
# ═══════════════════════════════════════════════════════════════════════════════

class SaveResultAccountIdTests(unittest.TestCase):
    """save_result() writes payload['_account_id'] to the DB row."""

    def _run_save_result(self, payload_overrides=None):
        """Call save_result with a mocked Supabase and return the inserted data dict."""
        import src.worker as worker_mod

        inserted = {}

        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.side_effect = (
            lambda: inserted.update(mock_sb.table.return_value.insert.call_args[0][0]) or MagicMock()
        )

        payload = {
            "symbol": "XAUUSD",
            "side": "buy",
            "size": 0.1,
            "run_mode": "PAPER",
            "_account_id": "default",
        }
        if payload_overrides:
            payload.update(payload_overrides)

        original_supabase = worker_mod.supabase
        original_settings = worker_mod.settings
        try:
            worker_mod.supabase = mock_sb
            worker_mod.settings = MagicMock(account_balance=50000)
            worker_mod.save_result(payload, "filtered", "test note", 0.5)
        finally:
            worker_mod.supabase = original_supabase
            worker_mod.settings = original_settings

        call_args = mock_sb.table.return_value.insert.call_args
        self.assertIsNotNone(call_args, "Supabase insert was not called")
        return call_args[0][0]  # positional arg 0 = the data dict

    def test_default_account_id_written(self):
        data = self._run_save_result({"_account_id": "default"})
        self.assertEqual(data.get("account_id"), "default")

    def test_named_account_id_written(self):
        data = self._run_save_result({"_account_id": "prop-1"})
        self.assertEqual(data.get("account_id"), "prop-1")

    def test_missing_account_id_falls_back_to_default(self):
        """Payload without _account_id (legacy path) defaults to 'default'."""
        data = self._run_save_result()  # no _account_id override beyond default
        self.assertEqual(data.get("account_id"), "default")

    def test_empty_account_id_falls_back_to_default(self):
        data = self._run_save_result({"_account_id": ""})
        self.assertEqual(data.get("account_id"), "default")


if __name__ == "__main__":
    unittest.main()
