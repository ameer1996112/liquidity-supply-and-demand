"""
Sprint 4.4: Strategy-as-data configuration tests.

Focus: Validation rejects invalid configs with clear errors.
"""

from __future__ import annotations

import unittest
from pydantic import ValidationError

from src.services.strategy_config import (
    StrategyConfig,
    validate_strategy_config,
    format_validation_errors,
)


class StrategyConfigValidationTests(unittest.TestCase):
    def test_invalid_ai_mode_rejected(self):
        raw = {
            "name": "Bad AI Mode",
            "signal_filters": {"symbols": ["XAUUSD"], "sessions": ["london"]},
            "risk": {"name": "balanced", "risk_percent": 0.5, "min_rr_ratio": 2.0},
            "ai": {"mode": "invalid_mode", "debate": {"enabled": True, "rounds": 1, "min_confidence": 60}},
            "execution_routing": [],
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_strategy_config(raw)
        errs = format_validation_errors(ctx.exception)
        fields = {e["field"] for e in errs}
        self.assertIn("ai.mode", fields)

    def test_invalid_session_rejected(self):
        raw = {
            "name": "Bad Session",
            "signal_filters": {"symbols": ["XAUUSD"], "sessions": ["moon"]},
            "risk": {"name": "balanced", "risk_percent": 0.5, "min_rr_ratio": 2.0},
            "ai": {"mode": "shadow", "debate": {"enabled": True, "rounds": 1, "min_confidence": 60}},
            "execution_routing": [],
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_strategy_config(raw)
        errs = format_validation_errors(ctx.exception)
        self.assertTrue(any("sessions" in e["field"] for e in errs))

    def test_negative_risk_percent_rejected(self):
        raw = {
            "name": "Negative Risk",
            "signal_filters": {"symbols": [], "sessions": []},
            "risk": {"name": "bad", "risk_percent": -1.0, "min_rr_ratio": 1.0},
            "ai": {"mode": "shadow", "debate": {"enabled": True, "rounds": 1, "min_confidence": 60}},
            "execution_routing": [],
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_strategy_config(raw)
        errs = format_validation_errors(ctx.exception)
        self.assertTrue(any("risk.risk_percent" in e["field"] for e in errs))

    def test_duplicate_execution_routing_rejected(self):
        raw = {
            "name": "Duplicate Routing",
            "signal_filters": {"symbols": [], "sessions": []},
            "risk": {"name": "balanced", "risk_percent": 0.5, "min_rr_ratio": 0.0},
            "ai": {"mode": "shadow", "debate": {"enabled": True, "rounds": 1, "min_confidence": 60}},
            "execution_routing": [
                {"account_name": "ftmo-main", "run_mode": "LIVE", "enabled": True, "risk_multiplier": 1.0},
                {"account_name": "ftmo-main", "run_mode": "LIVE", "enabled": True, "risk_multiplier": 1.5},
            ],
        }
        with self.assertRaises(ValidationError):
            validate_strategy_config(raw)

    def test_valid_config_passes(self):
        raw = {
            "name": "Balanced XAUUSD",
            "signal_filters": {"symbols": ["XAUUSD"], "sessions": ["london", "ny"]},
            "risk": {"name": "balanced", "risk_percent": 0.5, "min_rr_ratio": 2.0},
            "ai": {"mode": "shadow", "debate": {"enabled": True, "rounds": 1, "min_confidence": 60}},
            "execution_routing": [
                {"account_name": "paper-lab", "run_mode": "PAPER", "enabled": True, "risk_multiplier": 1.0}
            ],
        }
        cfg = validate_strategy_config(raw)
        self.assertIsInstance(cfg, StrategyConfig)
        self.assertEqual(cfg.ai.mode, "shadow")
        self.assertEqual(len(cfg.execution_routing), 1)

