from scripts.optimizer.frozen_validation_runner import build_frozen_validation_commands


def test_frozen_validation_builds_required_windows() -> None:
    commands = build_frozen_validation_commands(
        pairs="USDJPY,XAUUSD",
        broker="vantage",
        source_params_file="approved.json",
        workers=3,
    )

    assert set(commands) == {"365d", "90d", "30d"}
    assert "--custom-start-date" in commands["365d"]
    assert "2025-05-01" in commands["365d"]
    assert "--backtest-range" in commands["90d"]
    assert "30d" in commands["30d"]
