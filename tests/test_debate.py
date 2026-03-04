"""
Sprint 3.3: Debate guardrail (Bull vs Bear) tests.

Deterministic mocked responses — no real LLM calls.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.ai.debate import run_debate, _build_trade_context, ChairOutput


# ── Deterministic mock responses ──────────────────────────────────────────────

BULL_RESPONSE = '{"argument": "Strong zone, liquidity swept, favorable R:R.", "vote": "allow"}'
BEAR_RESPONSE = '{"argument": "Session overlap risk, weak departure.", "vote": "block"}'
CHAIR_RESPONSE = (
    '{"recommendation": "allow", "confidence": 72, '
    '"reason_codes": ["zone_quality", "risk_ok"], '
    '"memo": "Bull and Risk approve; Bear concerns noted. Proceed.", '
    '"votes": {"bull": "allow", "bear": "block", "risk": "allow", "chair": "allow"}}'
)


def _mock_call_agent(client: object, role: str, prompt: str, system: str, model: str) -> str | None:
    """Deterministic mock: return fixed JSON per role."""
    if role == "bull":
        return BULL_RESPONSE
    if role == "bear":
        return BEAR_RESPONSE
    if role == "chair":
        return CHAIR_RESPONSE
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# _build_trade_context
# ═══════════════════════════════════════════════════════════════════════════════


class BuildTradeContextTests(unittest.TestCase):
    def test_basic_context(self):
        payload = {
            "symbol": "EURUSD",
            "side": "buy",
            "entry": 1.0850,
            "sl": 1.0820,
            "tp": 1.0920,
            "size": 0.5,
        }
        ctx = _build_trade_context(payload)
        self.assertIn("EURUSD", ctx)
        self.assertIn("BUY", ctx)
        self.assertIn("1.085", ctx)

    def test_context_with_zone(self):
        payload = {
            "symbol": "GBPJPY",
            "side": "sell",
            "entry": 188.50,
            "sl": 189.00,
            "tp": 187.00,
            "size": 0.1,
            "zone_id": 12345,
            "zone_grade": "B+",
            "entry_model": "FLIP",
            "score": 72,
        }
        ctx = _build_trade_context(payload)
        self.assertIn("12345", ctx)
        self.assertIn("B+", ctx)
        self.assertIn("72", ctx)


# ═══════════════════════════════════════════════════════════════════════════════
# run_debate (mocked)
# ═══════════════════════════════════════════════════════════════════════════════


class RunDebateTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "symbol": "XAUUSD",
            "side": "buy",
            "entry": 2650.0,
            "sl": 2640.0,
            "tp": 2670.0,
            "size": 0.1,
            "zone_id": 100,
            "zone_grade": "A",
            "score": 85,
        }

    @patch("src.ai.debate._call_agent", side_effect=_mock_call_agent)
    @patch("src.ai.debate._run_risk")
    def test_run_debate_returns_structured_output(self, mock_risk, mock_call):
        mock_risk.return_value = ("Drawdown OK, exposure within limits", "allow")

        result = run_debate(self.payload, client=MagicMock(), supabase=None)

        self.assertIn("recommendation", result)
        self.assertIn("confidence", result)
        self.assertIn("reason_codes", result)
        self.assertIn("memo", result)
        self.assertIn("votes", result)
        self.assertIn("transcript", result)

        self.assertIn(result["recommendation"], ("allow", "block"))
        self.assertGreaterEqual(result["confidence"], 0)
        self.assertLessEqual(result["confidence"], 100)
        self.assertIsInstance(result["reason_codes"], list)
        self.assertIsInstance(result["votes"], dict)
        self.assertIsInstance(result["transcript"], list)
        self.assertGreaterEqual(len(result["transcript"]), 4)

    @patch("src.ai.debate._call_agent", side_effect=_mock_call_agent)
    @patch("src.ai.debate._run_risk")
    def test_run_debate_deterministic_mock(self, mock_risk, mock_call):
        mock_risk.return_value = ("All clear", "allow")

        result = run_debate(self.payload, client=MagicMock(), supabase=None)

        self.assertEqual(result["recommendation"], "allow")
        self.assertEqual(result["confidence"], 72)
        self.assertIn("zone_quality", result["reason_codes"])
        self.assertIn("Bull and Risk approve", result["memo"])
        self.assertEqual(result["votes"].get("bull"), "allow")
        self.assertEqual(result["votes"].get("bear"), "block")
        self.assertEqual(result["votes"].get("risk"), "allow")
        self.assertEqual(result["votes"].get("chair"), "allow")

    @patch("src.ai.debate._call_agent", return_value=None)
    @patch("src.ai.debate._run_risk")
    def test_run_debate_fail_open_on_llm_error(self, mock_risk, mock_call):
        mock_risk.return_value = ("No DB", "allow")

        result = run_debate(self.payload, client=None, supabase=None)

        self.assertIn("recommendation", result)
        self.assertIn(result["recommendation"], ("allow", "block"))
        self.assertIsInstance(result["transcript"], list)


# ═══════════════════════════════════════════════════════════════════════════════
# ChairOutput schema
# ═══════════════════════════════════════════════════════════════════════════════


class ChairOutputTests(unittest.TestCase):
    def test_chair_output_valid(self):
        out = ChairOutput(
            recommendation="allow",
            confidence=80,
            reason_codes=["zone_ok", "risk_ok"],
            memo="Proceed.",
            votes={"bull": "allow", "bear": "block", "risk": "allow", "chair": "allow"},
        )
        self.assertEqual(out.recommendation, "allow")
        self.assertEqual(out.confidence, 80)
        self.assertEqual(len(out.reason_codes), 2)
