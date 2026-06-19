from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
INDICATOR = ROOT / "scripts/pinescript/indicators/SND_Raw_RD_Forex.pine"


def _function_body(source: str, name: str) -> str:
    start = source.index(f"{name}(")
    next_function = source.index("\n\n", start)
    return source[start:next_function]


def main() -> None:
    indicator = INDICATOR.read_text(encoding="utf-8")
    body = _function_body(indicator, "preferFirstZone")
    continuation_body = _function_body(indicator, "isContinuationZone")

    newer_origin = "else if first.originBar != other.originBar\n            keepFirst := first.originBar > other.originBar"
    size_tiebreak = "math.abs(firstSize - otherSize)"
    older_origin = "keepFirst := first.originBar < other.originBar"
    same_family_origin_gate = "sameFamily and first.originBar != other.originBar"

    if newer_origin not in body:
        raise AssertionError("Overlapping same-side zones must prefer the newer origin candle")
    if older_origin in body:
        raise AssertionError("Overlapping same-side zones must not prefer the older origin candle")
    if same_family_origin_gate in body:
        raise AssertionError("Origin recency must not be limited to the same model family")
    if body.index(newer_origin) > body.index(size_tiebreak):
        raise AssertionError("Origin recency must beat zone size/model priority for overlapping zones")
    if "const bool enableContinuationZones = true" not in indicator:
        raise AssertionError("Continuation zones must be enabled so later continuation origins can be created")
    if "bool reversalApproach = demand ? isBearish(baseIdx + 1) : isBullish(baseIdx + 1)" not in continuation_body:
        raise AssertionError("Continuation zones must accept the strategy reference reversal approach")
    if "bool validApproach = (continuationApproach and shallowPullback) or (reversalApproach and reversalExtreme)" not in continuation_body:
        raise AssertionError("Continuation approach logic must include both shallow continuation and reversal extreme cases")

    print("SND Raw RD Forex zone origin preference static contract passed")


if __name__ == "__main__":
    main()
