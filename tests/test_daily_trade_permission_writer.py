from scripts.optimizer.daily_trade_permission_writer import build_daily_permissions


NO_TRADE_REASONS = [
    "no_research_approved_candidates",
    "strategy_fidelity_not_proven",
    "result_truth_not_available",
    "trade_level_stress_not_available",
    "prop_survival_not_available",
]


def _approved_candidates() -> dict:
    return {
        "schema_version": 1,
        "candidates": {
            "USDJPY": {
                "candidate_status": "RESEARCH_APPROVED",
                "params_hash": "abc123",
                "allowed_sessions_utc": [{"name": "asia_london", "start": 0, "end": 9}],
                "risk": {
                    "normal_risk_per_trade_pct": 0.25,
                    "reduced_risk_per_trade_pct": 0.125,
                    "max_trades_per_day": 1,
                },
            }
        },
    }


def test_approved_candidate_does_not_create_permission_when_news_blocks() -> None:
    permissions = build_daily_permissions(
        _approved_candidates(),
        account_profile="alpha_50k_safe",
        generated_at="2026-05-05T06:00:00Z",
        spread_state={"USDJPY": "normal"},
        news_state={"USDJPY": "blocked"},
        account_state={"buffer_status": "safe"},
        regime_state={"USDJPY": "acceptable"},
        decay_state={"USDJPY": "fresh"},
        execution_health={"status": "healthy"},
    )

    assert permissions["global_decision"] == "NO_TRADE"
    assert permissions["permissions"] == {}
    assert permissions["blocked"]["USDJPY"] == ["news_blackout_active"]


def test_recent_decay_reduces_risk_but_still_allows_trade() -> None:
    permissions = build_daily_permissions(
        _approved_candidates(),
        account_profile="alpha_50k_safe",
        generated_at="2026-05-05T06:00:00Z",
        spread_state={"USDJPY": "normal"},
        news_state={"USDJPY": "clear"},
        account_state={"buffer_status": "safe"},
        regime_state={"USDJPY": "acceptable"},
        decay_state={"USDJPY": "weak_recent_performance"},
        execution_health={"status": "healthy"},
    )

    assert permissions["global_decision"] == "TRADE_REDUCED_RISK"
    assert permissions["permissions"]["USDJPY"]["status"] == "TRADE_REDUCED_RISK"
    assert permissions["permissions"]["USDJPY"]["risk_per_trade_pct"] == 0.125


def test_empty_approved_candidates_writes_no_trade_reasons() -> None:
    permissions = build_daily_permissions(
        {"schema_version": 1, "candidates": {}},
        account_profile="alpha_50k_safe",
        generated_at="2026-05-05T06:00:00Z",
    )

    assert permissions == {
        "schema_version": 1,
        "generated_at": "2026-05-05T06:00:00Z",
        "account_profile": "alpha_50k_safe",
        "global_decision": "NO_TRADE",
        "permissions": {},
        "blocked": {},
        "watch_only": {},
        "reasons": NO_TRADE_REASONS,
    }
