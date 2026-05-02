from scripts.optimizer.daily_candidate_selector import select_daily_candidates


def test_daily_selector_outputs_no_trade_when_no_symbol_passes_all_gates() -> None:
    decision = select_daily_candidates(
        robust_passed={"USDCAD": {}},
        broker_passed={},
        walk_forward_passed={"USDCAD": {}},
        stability_passed={"USDCAD": {}},
        stress_passed={"USDCAD": {}},
        prop_profile_report={"USDCAD": {"status": "passed"}},
        regime_snapshots={},
        portfolio_allowed=["USDCAD"],
        prop_profile={"risk_per_trade_pct": 0.5, "max_trades_per_day": 3},
    )

    assert decision["decision"] == "NO_TRADE"
    assert "USDCAD" in decision["blocked_symbols"]


def test_daily_selector_watch_only_on_low_regime_confidence() -> None:
    decision = select_daily_candidates(
        robust_passed={"USDCAD": {"allowed_regimes": ["RANGING"]}},
        broker_passed={"USDCAD": {}},
        walk_forward_passed={"USDCAD": {}},
        stability_passed={"USDCAD": {}},
        stress_passed={"USDCAD": {}},
        prop_profile_report={"USDCAD": {"status": "passed"}},
        regime_snapshots={"USDCAD": {"regimes": ["RANGING"], "confidence": 0.4}},
        portfolio_allowed=["USDCAD"],
        prop_profile={"risk_per_trade_pct": 0.5, "max_trades_per_day": 3},
    )

    assert decision["decision"] == "WATCH_ONLY"
    assert "USDCAD" in decision["allowed_symbols"]


def test_daily_selector_watch_only_when_regime_snapshot_missing() -> None:
    decision = select_daily_candidates(
        robust_passed={"USDCAD": {"allowed_regimes": ["RANGING"]}},
        broker_passed={"USDCAD": {}},
        walk_forward_passed={"USDCAD": {}},
        stability_passed={"USDCAD": {}},
        stress_passed={"USDCAD": {}},
        prop_profile_report={"USDCAD": {"status": "passed"}},
        regime_snapshots={},
        portfolio_allowed=["USDCAD"],
        prop_profile={"risk_per_trade_pct": 0.5, "max_trades_per_day": 3},
    )

    assert decision["decision"] == "WATCH_ONLY"
    assert decision["allowed_symbols"]["USDCAD"]["current_regime"] == ["UNKNOWN"]


def test_daily_selector_watch_only_when_prop_simulation_is_approximate() -> None:
    decision = select_daily_candidates(
        robust_passed={"USDCAD": {"allowed_regimes": ["RANGING"]}},
        broker_passed={"USDCAD": {}},
        walk_forward_passed={"USDCAD": {}},
        stability_passed={"USDCAD": {}},
        stress_passed={"USDCAD": {}},
        prop_profile_report={"USDCAD": {"status": "watch_only", "simulation_precision": "approximate"}},
        regime_snapshots={"USDCAD": {"regimes": ["RANGING"], "confidence": 0.8}},
        portfolio_allowed=["USDCAD"],
        prop_profile={"risk_per_trade_pct": 0.5, "max_trades_per_day": 3},
    )

    assert decision["decision"] == "WATCH_ONLY"
    assert "prop simulation approximate" in decision["allowed_symbols"]["USDCAD"]["reason"]
