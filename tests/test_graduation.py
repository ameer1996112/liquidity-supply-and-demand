"""
Sprint 3.4: Strategy graduation pipeline tests.
"""

from __future__ import annotations

import unittest

from src.services.graduation_service import (
    ShadowMetrics,
    check_graduation_readiness,
    _parse_ai_would_have_blocked,
)


class ParseAiWouldHaveBlockedTests(unittest.TestCase):
    def test_ai_would_have_blocked_explicit(self):
        self.assertTrue(_parse_ai_would_have_blocked({"ai_would_have_blocked": True}))
        self.assertFalse(_parse_ai_would_have_blocked({"ai_would_have_blocked": False}))

    def test_ai_would_have_blocked_from_trace(self):
        self.assertTrue(
            _parse_ai_would_have_blocked({
                "decision_trace": {
                    "rules": [{"rule_id": "ai_shadow_override", "passed": True}],
                },
            })
        )
        self.assertFalse(
            _parse_ai_would_have_blocked({
                "decision_trace": {"rules": [{"rule_id": "llm_decision"}]},
            })
        )

    def test_ai_would_have_blocked_string_json(self):
        import json
        self.assertTrue(
            _parse_ai_would_have_blocked(json.dumps({"ai_would_have_blocked": True}))
        )


class CheckGraduationReadinessTests(unittest.TestCase):
    def test_ready_when_thresholds_met(self):
        m = ShadowMetrics(
            sample_size=60,
            sample_size_ai_blocked=20,
            sample_size_ai_allowed=40,
            win_rate_actual=55.0,
            win_rate_if_blocked=40.0,
            win_rate_if_allowed=62.0,
            total_pnl_actual=100.0,
            total_pnl_if_blocked=-50.0,
            total_pnl_if_allowed=150.0,
            edge_pct=22.0,
            pnl_edge_usd=200.0,
        )
        r = check_graduation_readiness(m, min_sample_size=50, min_edge_pct=5.0)
        self.assertTrue(r["ready"])
        self.assertIn("Ready", r["reason"])

    def test_not_ready_sample_too_small(self):
        m = ShadowMetrics(
            sample_size=30,
            sample_size_ai_blocked=10,
            sample_size_ai_allowed=20,
            win_rate_actual=50.0,
            win_rate_if_blocked=0.0,
            win_rate_if_allowed=0.0,
            total_pnl_actual=0.0,
            total_pnl_if_blocked=0.0,
            total_pnl_if_allowed=0.0,
            edge_pct=10.0,
            pnl_edge_usd=0.0,
        )
        r = check_graduation_readiness(m, min_sample_size=50, min_edge_pct=5.0)
        self.assertFalse(r["ready"])
        self.assertIn("Sample size", r["reason"])

    def test_not_ready_edge_too_low(self):
        m = ShadowMetrics(
            sample_size=60,
            sample_size_ai_blocked=20,
            sample_size_ai_allowed=40,
            win_rate_actual=50.0,
            win_rate_if_blocked=48.0,
            win_rate_if_allowed=51.0,
            total_pnl_actual=0.0,
            total_pnl_if_blocked=0.0,
            total_pnl_if_allowed=0.0,
            edge_pct=3.0,
            pnl_edge_usd=0.0,
        )
        r = check_graduation_readiness(m, min_sample_size=50, min_edge_pct=5.0)
        self.assertFalse(r["ready"])
        self.assertIn("edge", r["reason"].lower())
