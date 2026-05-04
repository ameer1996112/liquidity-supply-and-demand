from __future__ import annotations

import json
from datetime import datetime, timezone

from src.core.guard_rails.approved_pairs_guard import ApprovedPairsGuard


def _write_approved(path, pairs: dict) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "generated_at": "2026-05-04T02:00:00Z",
                "pairs": pairs,
            }
        )
    )


def test_approved_pairs_guard_allows_pair_inside_session(tmp_path) -> None:
    approved_path = tmp_path / "approved_pairs.json"
    _write_approved(
        approved_path,
        {
            "USDJPY": {
                "status": "TRADE_NORMAL_RISK",
                "session_utc": {"start": 0, "end": 9},
                "approved_until": "2026-06-04",
            }
        },
    )
    guard = ApprovedPairsGuard(
        approved_path,
        now_provider=lambda: datetime(2026, 5, 4, 8, 30, tzinfo=timezone.utc),
    )

    passed, reason = guard.check({"symbol": "USDJPY"})

    assert passed is True
    assert reason == ""


def test_approved_pairs_guard_rejects_unapproved_pair(tmp_path) -> None:
    approved_path = tmp_path / "approved_pairs.json"
    _write_approved(approved_path, {"USDJPY": {"status": "TRADE_NORMAL_RISK"}})
    guard = ApprovedPairsGuard(approved_path)

    passed, reason = guard.check({"symbol": "XAUUSD"})

    assert passed is False
    assert "not approved" in reason


def test_approved_pairs_guard_rejects_outside_approved_session(tmp_path) -> None:
    approved_path = tmp_path / "approved_pairs.json"
    _write_approved(
        approved_path,
        {
            "USDJPY": {
                "status": "TRADE_NORMAL_RISK",
                "session_utc": {"start": 0, "end": 9},
                "approved_until": "2026-06-04",
            }
        },
    )
    guard = ApprovedPairsGuard(
        approved_path,
        now_provider=lambda: datetime(2026, 5, 4, 13, 0, tzinfo=timezone.utc),
    )

    passed, reason = guard.check({"symbol": "USDJPY"})

    assert passed is False
    assert "outside approved session" in reason


def test_approved_pairs_guard_sets_reduced_risk_multiplier(tmp_path) -> None:
    approved_path = tmp_path / "approved_pairs.json"
    _write_approved(
        approved_path,
        {
            "NAS100": {
                "status": "TRADE_REDUCED_RISK",
                "session_utc": {"start": 12, "end": 17},
                "approved_until": "2026-06-04",
            }
        },
    )
    guard = ApprovedPairsGuard(
        approved_path,
        now_provider=lambda: datetime(2026, 5, 4, 14, 0, tzinfo=timezone.utc),
    )
    payload = {"symbol": "NAS100"}

    passed, reason = guard.check(payload)

    assert passed is True
    assert reason == ""
    assert payload["_approved_pair_status"] == "TRADE_REDUCED_RISK"
    assert payload["_approved_pair_risk_multiplier"] == 0.5
