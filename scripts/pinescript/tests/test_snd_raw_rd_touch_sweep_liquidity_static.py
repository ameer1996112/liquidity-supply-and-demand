from pathlib import Path


INDICATORS = [
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex.pine"),
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine"),
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine"),
]


def _function_body(source: str, name: str, next_name: str) -> str:
    start = source.index(f"{name}(")
    end = source.index(f"\n{next_name}(", start)
    return source[start:end]


def test_touch_sweep_liquidity_is_one_candle_valid_like_strategy() -> None:
    for path in INDICATORS:
        source = path.read_text()

        for name, next_name in [
            ("applyDemandTouchSweepLiquidity", "applySupplyTouchSweepLiquidity"),
            ("applySupplyTouchSweepLiquidity", "linkLiquidityAndTargets"),
        ]:
            body = _function_body(source, name, next_name)

            assert "out.liquidityValid := true" in body
            assert "out.liquiditySwept := true" in body
            assert "out.liquiditySweepBar := bar_index" in body
            assert "out.liquidityLineSweepBar := bar_index" in body
            assert "out.liquidityCandleCount := 1" in body
            assert "out.legCandles := 1" in body
            assert 'out.liquidityDecisionReason := "SELECTED_TOUCH_SWEEP"' in body
            assert "WAITING_STRONG_TOUCH_SWEEP" not in body
