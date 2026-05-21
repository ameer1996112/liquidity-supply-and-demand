from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _body(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _require(block: str, needles: list[str], label: str) -> None:
    missing = [needle for needle in needles if needle not in block]
    if missing:
        raise AssertionError(f"{label} missing:\n" + "\n".join(missing))


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")
    demand_scan = _body(strategy, "f_scan_demand_liquidity", "\nf_scan_supply_liquidity")
    supply_scan = _body(strategy, "f_scan_supply_liquidity", "\nf_check_demand_sweeps")

    shared_required = [
        "float bestDist = 1.0e10",
        "bool isCloser =",
        "bool isSameDistance =",
        "bool isMoreRecent = na(bestLiqBar) or pBar > bestLiqBar",
        'z.liqSource := "MAKUCHAKU_PIVOT"',
    ]
    _require(demand_scan, shared_required, "Demand closest liquidity marker selection")
    _require(supply_scan, shared_required, "Supply closest liquidity marker selection")

    _require(
        demand_scan,
        [
            "bool isCloser = distFromZone < bestDist",
            "bool isSameDistance = distFromZone == bestDist",
            "if na(bestLiqBar) or improvesEdgeQuality or (sameEdgeQuality and (isCloser or (isSameDistance and isMoreRecent)))",
            "bestDist := distFromZone",
            "bestLiqPrice := pLow",
            "bestLiqBar := pBar",
            "bool bestLiqNearEdge = false",
            "bool preferAwayFromEdge = use_inducement_linking and zoneHeight >= pip_size * 5.0",
            "bool isNearEdge = preferAwayFromEdge and distFromZone < pip_size * 2.0",
            "bool improvesEdgeQuality = bestLiqNearEdge and not isNearEdge",
            "bool sameEdgeQuality = bestLiqNearEdge == isNearEdge",
            "bestLiqNearEdge := isNearEdge",
        ],
        "Demand per-zone reference liquidity marker selection",
    )
    _require(
        supply_scan,
        [
            "bool isCloser = distFromZoneCheck < bestDist",
            "bool isSameDistance = distFromZoneCheck == bestDist",
            "if isCloser or (isSameDistance and isMoreRecent)",
            "bestDist := distFromZoneCheck",
            "bestLiqPrice := pHigh",
            "bestLiqBar := pBar",
        ],
        "Supply per-zone reference liquidity marker selection",
    )

    forbidden_fallback = [
        "LOCAL_FALLBACK",
        "bestLiqFallback",
    ]
    for needle in forbidden_fallback:
        if needle in demand_scan or needle in supply_scan:
            raise AssertionError(f"Broad fallback liquidity selection must not be reintroduced: {needle}")

    forbidden = [
        "if pLow < bestLiqPrice",
        "if pHigh > bestLiqPrice",
    ]
    for needle in forbidden:
        if needle in demand_scan or needle in supply_scan:
            raise AssertionError(f"Liquidity marker selection must not use stale extreme-price winner: {needle}")

    print("SND liquidity reference marker static contract passed")


if __name__ == "__main__":
    main()
