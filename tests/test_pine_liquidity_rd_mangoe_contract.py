from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "pinescript"
    / "strategies"
    / "Liquidity_RD_Mangoe_Strategy.pine"
)


def test_new_liquidity_snd_strategy_contract():
    source = SCRIPT_PATH.read_text()

    required_fragments = [
        '//@version=6',
        'strategy("RD/Mangoe Liquidity Supply Demand Strategy"',
        "type SndZone",
        "CANDIDATE",
        "ACTIVE",
        "LEFT_ZONE",
        "LIQ_VALID",
        "INDUCEMENT_SWEPT",
        "TARGET_BOS_SWEPT",
        "READY_FOR_MITIGATION",
        "MITIGATED_USED_FOR_ENTRY",
        "INVALID_EARLY_RETURN",
        "INVALID_RETURN_BEFORE_PROOF",
        "INVALID_CLOSE_INSIDE_ZONE",
        "INVALID_DISTAL_CLOSE",
        "EXPIRED",
        'enable_initial_backfill_scan_slow',
        'zone_valid_lifetime_hours',
        'min_valid_return_bars',
        'zone_bounds_mode',
        'xloc = xloc.bar_time',
        'alert_message',
        'strategy.entry',
        'strategy.exit',
    ]

    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert missing == []


def test_new_strategy_does_not_mutate_existing_snd_script():
    legacy_path = SCRIPT_PATH.with_name("SND_Strategy.pine")
    assert legacy_path.exists()
    assert SCRIPT_PATH.exists()
    assert SCRIPT_PATH.name != legacy_path.name
