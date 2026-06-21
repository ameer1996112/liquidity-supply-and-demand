from pathlib import Path


INDICATORS = [
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex.pine"),
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine"),
    Path("scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine"),
]


def _function_body(source: str, name: str) -> str:
    start = source.index(f"{name}(")
    next_function = source.index("\ncountConsecutiveOppCandles", start)
    return source[start:next_function]


def test_liquidity_candle_count_scans_from_newer_offset_to_older_offset() -> None:
    for path in INDICATORS:
        body = _function_body(path.read_text(), "countOppCandlesInLiquidityRange")

        assert "int offStart = bar_index - endBarAbs" in body
        assert "int offEnd   = bar_index - startBarAbs" in body
        assert "for i = offStart to offEnd" in body
        assert "for i = offEnd to offStart" not in body


def test_liquidity_candle_count_still_counts_only_opposite_candles() -> None:
    for path in INDICATORS:
        body = _function_body(path.read_text(), "countOppCandlesInLiquidityRange")

        assert "isDemand ? (close[i] < open[i]) : (close[i] > open[i])" in body
        assert "count += 1" in body
