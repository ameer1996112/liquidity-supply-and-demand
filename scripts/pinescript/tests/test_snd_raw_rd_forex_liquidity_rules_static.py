import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
INDICATORS = [
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex.pine",
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine",
    ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine",
]


def _function_body(source: str, name: str, next_name: str) -> str:
    marker = f"{name}("
    if marker not in source:
        return ""
    start = source.index(marker)
    next_marker = f"\n{next_name}("
    if next_marker not in source[start:]:
        return source[start:]
    end = source.index(next_marker, start)
    return source[start:end]


def main() -> None:
    for indicator_path in INDICATORS:
        source = indicator_path.read_text(encoding="utf-8")
        shorttitle_match = re.search(r'shorttitle\s*=\s*"([^"]+)"', source)
        demand_scan = _function_body(source, "f_scan_demand_liquidity", "f_scan_supply_liquidity")
        supply_scan = _function_body(source, "f_scan_supply_liquidity", "clearStrategyLiquidityState")
        wrong_side_body = _function_body(source, "strategyLiquidityWrongSide", "strategyLiquidityGhostData")
        distance_body = _function_body(source, "liquidityMaxDistancePrice", "findDemandTouchLiquidity")
        reference_record_body = _function_body(source, "recordReferenceLiquidityLine", "updateReferenceLiquidityLines")

        if shorttitle_match is None:
            raise AssertionError(f"{indicator_path.name} must define an explicit shorttitle")
        if len(shorttitle_match.group(1)) > 10:
            raise AssertionError(f"{indicator_path.name} shorttitle must fit TradingView's 10-character limit")
        if "const bool enableOneCandleLiquidity = true" not in source:
            raise AssertionError(f"{indicator_path.name} must match the strategy artifact and allow one-candle liquidity by default")
        if "const int referenceLiquidityMaxLines" not in source or "var array<line> referenceLiquidityLines" not in source:
            raise AssertionError(f"{indicator_path.name} must keep a bounded reference-style liquidity candidate pool")
        if "const int referenceLiquidityPivotLen = 2" not in source:
            raise AssertionError(f"{indicator_path.name} reference-style liquidity markers must probe the confirmed two-bar-old candle")
        if "const float referenceLiquidityClusterAtrMultiplier" not in source:
            raise AssertionError(f"{indicator_path.name} reference candidates must use an ATR-relative cluster filter")
        if "const float referenceLiquidityEqualAtrMultiplier" not in source:
            raise AssertionError(f"{indicator_path.name} reference candidates must use an ATR-relative equal-liquidity tolerance")
        if "line.new(" in reference_record_body:
            raise AssertionError(f"{indicator_path.name} reference liquidity candidates must not draw extra chart lines")
        for required in [
            "array.push(referenceLiquidityLines, na)",
            "array.push(referenceLiquidityPrices, price)",
            "array.push(referenceLiquidityBars, x1)",
            "array.push(referenceLiquidityDemand, demand)",
            "array.push(referenceLiquiditySwept, false)",
            "trimReferenceLiquidityLines()",
        ]:
            if required not in reference_record_body:
                raise AssertionError(f"{indicator_path.name} reference candidate recording is incomplete: missing {required}")
        if "referenceLiquidityDedupPrice()" not in source or "atr14 * referenceLiquidityClusterAtrMultiplier" not in source:
            raise AssertionError(f"{indicator_path.name} reference candidate de-duplication must be volatility-relative")
        if "referenceLiquidityEqualPrice()" not in source or "atr14 * referenceLiquidityEqualAtrMultiplier" not in source:
            raise AssertionError(f"{indicator_path.name} reference equal-liquidity matching must be volatility-relative")
        if "recordReferenceLiquidityLine(low[referenceLiquidityPivotLen], referenceLiquidityPivotBar, true)" not in source:
            raise AssertionError(f"{indicator_path.name} must record confirmed pivot-low reference liquidity")
        if "recordReferenceLiquidityLine(high[referenceLiquidityPivotLen], referenceLiquidityPivotBar, false)" not in source:
            raise AssertionError(f"{indicator_path.name} must record confirmed pivot-high reference liquidity")
        if "if referenceLowLiquidityAt(referenceLiquidityPivotLen)" not in source:
            raise AssertionError(f"{indicator_path.name} demand reference candidates must reuse RD liquidity structure rules")
        if "if referenceHighLiquidityAt(referenceLiquidityPivotLen)" not in source:
            raise AssertionError(f"{indicator_path.name} supply reference candidates must reuse RD liquidity structure rules")
        if "rdLowLiquidityAt(offset) or (historicalLocalLowAt(offset) and referenceEqualLowLiquidityAt(offset))" not in source:
            raise AssertionError(f"{indicator_path.name} demand reference candidates must add equal-low clusters")
        if "rdHighLiquidityAt(offset) or (historicalLocalHighAt(offset) and referenceEqualHighLiquidityAt(offset))" not in source:
            raise AssertionError(f"{indicator_path.name} supply reference candidates must add equal-high clusters")
        if "referencePivotLowAt(" in source or "referencePivotHighAt(" in source:
            raise AssertionError(f"{indicator_path.name} reference candidates must not use a separate pivot-only detector")

        if "int referenceCount = array.size(referenceLiquidityPrices)" not in demand_scan:
            raise AssertionError(f"{indicator_path.name} demand scan must search the reference liquidity pool")
        if "int referenceCount = array.size(referenceLiquidityPrices)" not in supply_scan:
            raise AssertionError(f"{indicator_path.name} supply scan must search the reference liquidity pool")
        if "isDemandReference and not isSweptReference" not in demand_scan:
            raise AssertionError(f"{indicator_path.name} demand scan must filter for unswept demand reference liquidity")
        if "not isDemandReference and not isSweptReference" not in supply_scan:
            raise AssertionError(f"{indicator_path.name} supply scan must filter for unswept supply reference liquidity")
        if 'bestSource := "REFERENCE"' not in demand_scan or 'bestSource := "REFERENCE"' not in supply_scan:
            raise AssertionError(f"{indicator_path.name} scans must be able to select a reference liquidity candidate")
        if "isValidLocation := pLow < out.bottom" not in demand_scan:
            raise AssertionError(f"{indicator_path.name} demand liquidity must stay below the zone")
        if "distFromZone := out.bottom - pLow" not in demand_scan:
            raise AssertionError(f"{indicator_path.name} demand liquidity distance must be measured from the demand bottom")
        if "isValidLocation := pHigh > out.top" not in supply_scan:
            raise AssertionError(f"{indicator_path.name} supply liquidity must stay above the zone")
        if "distFromZone := pHigh - out.top" not in supply_scan:
            raise AssertionError(f"{indicator_path.name} supply liquidity distance must be measured from the supply top")
        if "REFERENCE_NOT_CLOSEST" not in demand_scan or "REFERENCE_TOO_FAR" not in demand_scan or "REFERENCE_WRONG_SIDE" not in demand_scan:
            raise AssertionError(f"{indicator_path.name} demand scan must expose rejection reasons for reference candidates")
        if "REFERENCE_NOT_CLOSEST" not in supply_scan or "REFERENCE_TOO_FAR" not in supply_scan or "REFERENCE_WRONG_SIDE" not in supply_scan:
            raise AssertionError(f"{indicator_path.name} supply scan must expose rejection reasons for reference candidates")
        if 'out.liquidityDecisionReason := bestSource == "REFERENCE" ? "SELECTED_REFERENCE_CLOSEST"' not in demand_scan:
            raise AssertionError(f"{indicator_path.name} demand scan must tag closest reference selections explicitly")
        if 'out.liquidityDecisionReason := bestSource == "REFERENCE" ? "SELECTED_REFERENCE_CLOSEST"' not in supply_scan:
            raise AssertionError(f"{indicator_path.name} supply scan must tag closest reference selections explicitly")
        if "if na(bestLiqBar) and enableOneCandleLiquidity" not in demand_scan:
            raise AssertionError(f"{indicator_path.name} demand one-candle fallback must stay explicitly gated")
        if "if na(bestLiqBar) and enableOneCandleLiquidity" not in supply_scan:
            raise AssertionError(f"{indicator_path.name} supply one-candle fallback must stay explicitly gated")
        if "int minLegCandles = enableOneCandleLiquidity ? 1 : 2" not in demand_scan:
            raise AssertionError(f"{indicator_path.name} demand liquidity strength must enforce two candles when one-candle mode is off")
        if "int minLegCandles = enableOneCandleLiquidity ? 1 : 2" not in supply_scan:
            raise AssertionError(f"{indicator_path.name} supply liquidity strength must enforce two candles when one-candle mode is off")
        if "z.liquidityPrice >= z.bottom" not in wrong_side_body:
            raise AssertionError(f"{indicator_path.name} demand wrong-side cleanup must invalidate liquidity inside or above the zone")
        if "z.liquidityPrice <= z.top" not in wrong_side_body:
            raise AssertionError(f"{indicator_path.name} supply wrong-side cleanup must invalidate liquidity inside or below the zone")
        if "const float liq_atr_distance_multiplier" not in source:
            raise AssertionError(f"{indicator_path.name} liquidity distance must use an ATR-relative cap")
        if "atr14 * liq_atr_distance_multiplier" not in distance_body:
            raise AssertionError(f"{indicator_path.name} liquidity max distance must be volatility-relative")
        if "syminfo.mintick" not in distance_body or "effective_liq_max_dist * pip_size" not in distance_body:
            raise AssertionError(f"{indicator_path.name} liquidity max distance must keep tick and symbol fallback caps")
        if "liquidityMaxDistancePrice()" not in demand_scan or "liquidityMaxDistancePrice()" not in supply_scan:
            raise AssertionError(f"{indicator_path.name} scans must use the shared volatility-relative liquidity distance cap")

    print("SND Raw RD Forex liquidity rules static contract passed")


if __name__ == "__main__":
    main()
