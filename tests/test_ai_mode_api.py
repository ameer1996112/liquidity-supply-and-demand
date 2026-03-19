"""
Sprint 4.3: Shadow → Enforce graduation API + audit log tests.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class AiModeApiTests(unittest.TestCase):
    """Tests for /config/ai/mode and /config/ai/mode-toggles endpoints."""

    @patch("src.api._get_effective_ai_mode", return_value="shadow")
    @patch("src.services.graduation_service.compute_shadow_metrics")
    @patch("src.services.graduation_service.check_graduation_readiness")
    def test_set_enforce_blocked_when_not_ready(self, mock_check_ready, mock_compute, mock_get_effective):
        """Enforce mode is rejected with 403 when graduation not ready."""
        from fastapi.testclient import TestClient
        from src.api import app

        # Graduation readiness: not ready
        mock_compute.return_value = MagicMock()
        mock_check_ready.return_value = {
            "ready": False,
            "reason": "Sample size too small",
            "metrics": {"sample_size": 10, "edge_pct": 1.0},
            "thresholds": {"min_sample_size": 50, "min_edge_pct": 5.0},
        }

        client = TestClient(app)
        resp = client.patch(
            "/config/ai/mode",
            json={"mode": "enforce", "reason": "force"},
        )
        assert resp.status_code == 403
        body = resp.json()
        assert body["detail"]["message"].startswith("Cannot enable enforce")
        assert "Sample size too small" in body["detail"]["reason"]

    @patch("src.services.ai_mode_override.set_ai_mode")
    @patch("src.services.ai_mode_override.get_ai_mode_override")
    @patch("src.services.graduation_service.compute_shadow_metrics")
    @patch("src.services.graduation_service.check_graduation_readiness")
    def test_set_enforce_allowed_when_ready(
        self,
        mock_check_ready,
        mock_compute,
        mock_get_override,
        mock_set_mode,
    ):
        """Enforce mode can be enabled when graduation thresholds are met."""
        from fastapi.testclient import TestClient
        from src.api import app

        # Current mode is shadow
        mock_get_override.return_value = "shadow"

        # Graduation readiness: ready
        mock_compute.return_value = MagicMock()
        mock_check_ready.return_value = {
            "ready": True,
            "reason": "Ready to graduate",
            "metrics": {"sample_size": 80, "edge_pct": 10.0},
            "thresholds": {"min_sample_size": 50, "min_edge_pct": 5.0},
        }
        mock_set_mode.return_value = True

        client = TestClient(app)
        resp = client.patch(
            "/config/ai/mode",
            json={"mode": "enforce", "reason": "graduation_ready"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "enforce"
        mock_set_mode.assert_called_once()
        # from_mode should be shadow, to_mode enforce
        kwargs = mock_set_mode.call_args.kwargs
        assert kwargs["from_mode"] == "shadow"

    @patch("src.services.ai_mode_override.set_ai_mode")
    @patch("src.services.ai_mode_override.get_ai_mode_override")
    def test_set_shadow_always_allowed(self, mock_get_override, mock_set_mode):
        """Switching back to shadow does not require graduation readiness."""
        from fastapi.testclient import TestClient
        from src.api import app

        mock_get_override.return_value = "enforce"
        mock_set_mode.return_value = True

        client = TestClient(app)
        resp = client.patch(
            "/config/ai/mode",
            json={"mode": "shadow", "reason": "manual"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "shadow"
        mock_set_mode.assert_called_once()


class AiModeOverrideTests(unittest.TestCase):
    """Direct tests for ai_mode_override persistence + audit logging."""

    @patch("src.services.ai_mode_override._get_supabase")
    def test_set_ai_mode_writes_state_and_toggle(self, mock_get_sb):
        from src.services.ai_mode_override import set_ai_mode

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        ok = set_ai_mode(
            "enforce",
            from_mode="shadow",
            reason="graduation_ready",
            created_by="test-suite",
        )
        assert ok is True
        # ai_mode_state upsert
        mock_sb.table.assert_any_call("ai_mode_state")
        mock_sb.table.return_value.upsert.assert_called_once()
        # ai_mode_toggles insert
        mock_sb.table.assert_any_call("ai_mode_toggles")
        mock_sb.table.return_value.insert.assert_called()

