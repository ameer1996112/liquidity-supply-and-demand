from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY_FILES = [
    ROOT / "scripts/pinescript/strategies/SND_Strategy.pine",
    ROOT / "scripts/pinescript/strategies/SND_Strategey_refactor.pine",
]


def _require(source: str, needles: list[str], label: str) -> None:
    missing = [needle for needle in needles if needle not in source]
    if missing:
        raise AssertionError(f"{label} missing:\n" + "\n".join(missing))


def _forbid(source: str, needles: list[str], label: str) -> None:
    present = [needle for needle in needles if needle in source]
    if present:
        raise AssertionError(f"{label} must not contain:\n" + "\n".join(present))


def main() -> None:
    for path in STRATEGY_FILES:
        strategy = path.read_text(encoding="utf-8")
        create_zone = strategy[
            strategy.index("createZone(int baseIdx, bool isDemand") :
            strategy.index("\nremove_zone_all_arrays(", strategy.index("createZone(int baseIdx, bool isDemand"))
        ]

        _require(
            strategy,
            [
                "resolve_canonical_origin(int displacementStartIdx, bool isDemand) =>",
                "int firstOriginIdx = displacementStartIdx + 1",
                "int scanIdx = displacementStartIdx + j",
                "bool scanOppositeOrigin = isDemand ? scan_close < scan_open : scan_close > scan_open",
                "if scanOppositeOrigin",
                "result := scanIdx",
                "int originIdx = resolve_canonical_origin(baseIdx - 1, isDemand)",
                "bool foundOrigin = not na(originIdx)",
                "float originHigh = high[originIdx]",
                "float originLow  = low[originIdx]",
                "float originOpen = open[originIdx]",
                "float originClose = close[originIdx]",
                "int originBarIdx = bar_index - originIdx",
                "zTop := originHigh",
                "zBottom := originLow",
                "proceed_creation := proceed_creation and foundOrigin",
                "proceed_creation := proceed_creation and not alreadyUsed",
                "createRejectReason := REJECTED_OLDER_ORIGIN_IN_SAME_DISPLACEMENT",
                "int legIdx = originIdx - legScan",
                "if legBullish and legLow < zBottom",
                "zBottom := legLow",
                "if legBearish and legHigh > zTop",
                "zTop := legHigh",
                "REJECTED_OLDER_ORIGIN_IN_SAME_DISPLACEMENT",
            ],
            f"{path.name} origin selection",
        )

        _forbid(
            create_zone,
            [
                "if scanOppositeOrigin\n                originIdx := scanIdx",
                "if not foundOrigin and scanOppositeOrigin",
            ],
            f"{path.name} far-cluster origin overwrite",
        )

        _forbid(
            strategy,
            [
                "zoneDebug",
                "debug_upsert_zone_origin",
                "debug_find_zone_origin_index",
                "originDirection",
                "displacementStartBarIdx",
                "formationWickExtended",
            ],
            f"{path.name} token-heavy temporary origin debug storage",
        )

        _forbid(
            create_zone,
            [
                "zTop := clusterHigh",
                "zBottom := clusterLow",
                "int maxDepartureWickScan = 4",
                "foundDemandReclaim",
                "foundSupplyReclaim",
            ],
            f"{path.name} cluster/early-reclaim boundary behavior",
        )

        _forbid(
            strategy,
            [
                '"Origin Bar"',
                '"Origin Dir"',
                '"Disp Start"',
                '"Wick Extend"',
                '"Final Range"',
            ],
            f"{path.name} verbose origin debug table",
        )

        force_full_wick = create_zone[
            create_zone.index("bool forceFullWickSymbol") :
            create_zone.index("float zTop = na", create_zone.index("bool forceFullWickSymbol"))
        ]
        if "is_gold" not in force_full_wick:
            raise AssertionError(f"{path.name} must keep gold in force-full-wick symbol handling")

    print("SND origin selection static contract passed")


if __name__ == "__main__":
    main()
