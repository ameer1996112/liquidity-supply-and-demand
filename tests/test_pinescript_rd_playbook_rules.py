"""Static regression checks for RD 5m Pine playbook wiring."""

from pathlib import Path


STRATEGY_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "pinescript"
    / "strategies"
    / "SND_Strategy.pine"
)
UTILS_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "pinescript"
    / "libraries"
    / "SND_Utils.pine"
)


def test_rd_tp_mode_can_route_gold_and_gj_tables() -> None:
    source = STRATEGY_PATH.read_text()

    assert "use_custom_rr" in source
    assert "[g_tp, g_bet, g_bes, g_mbe] = get_gold_tp_rules(sl_pips)" in source
    assert "[f_tp, f_bet, f_bes, f_mbe] = get_forex_tp_rules(sl_pips)" in source
    assert "else if is_gold or is_xpt\n        base_ratio := 4.0" in source


def test_rd_5m_entry_gates_are_enforced() -> None:
    source = STRATEGY_PATH.read_text()

    assert "useOneCandleLiquidity = true" in source
    assert "z.touchedPreSweep" in source
    assert "closes_inside" in source
    assert "f_get_session_id" in source
    assert 'hour(time, "UTC")' in source


def test_backend_next_wick_execution_fields_are_in_webhook_payload() -> None:
    utils_source = UTILS_PATH.read_text()

    assert ',"execution_mode":"' in utils_source
    assert ',"entry_reference_price":' in utils_source
    assert ',"wick_entry_pullback_pips":' in utils_source
    assert ',"max_entry_delay_seconds":' in utils_source
    assert ',"max_spread_pips":' in utils_source


def test_strategy_imports_published_utils_and_avoids_risk_shadowing() -> None:
    source = STRATEGY_PATH.read_text()

    assert "import ameer_1996112/SND_Utils/25 as Utils" in source
    assert "import ameer_1996112/SND_Utils/24 as Utils" not in source
    assert "float risk_pct = risk_per_trade_pct" in source
