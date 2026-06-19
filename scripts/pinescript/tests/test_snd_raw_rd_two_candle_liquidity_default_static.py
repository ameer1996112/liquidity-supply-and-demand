from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"
INDICATORS = [
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex.pine",
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine",
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine",
]


def test_raw_rd_matches_strategy_one_candle_liquidity_default() -> None:
    strategy_source = STRATEGY.read_text(encoding="utf-8")
    assert "useOneCandleLiquidity = true" in strategy_source, (
        "SND_Strategy must keep one-candle liquidity enabled in the TradingView artifact"
    )

    for indicator_path in INDICATORS:
        source = indicator_path.read_text(encoding="utf-8")

        assert "const bool enableOneCandleLiquidity = true" in source, (
            f"{indicator_path.name} must match the strategy artifact and allow one-candle liquidity by default"
        )
