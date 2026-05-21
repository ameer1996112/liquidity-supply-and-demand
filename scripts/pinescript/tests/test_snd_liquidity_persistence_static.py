from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def _body(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _require(block: str, needle: str, label: str) -> None:
    if needle not in block:
        raise AssertionError(f"{label} missing required persistence marker:\n{needle}")


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")

    demand_scan = _body(strategy, "f_scan_demand_liquidity", "\nf_scan_supply_liquidity")
    supply_scan = _body(strategy, "f_scan_supply_liquidity", "\nf_check_demand_sweeps")
    clear_demand = _body(strategy, "clearDemandLiquidityVisual", "\nupdateDemandLiquidityVisual")
    update_demand = _body(strategy, "updateDemandLiquidityVisual", "\nclearSupplyLiquidityVisual")
    clear_supply = _body(strategy, "clearSupplyLiquidityVisual", "\nupdateSupplyLiquidityVisual")
    update_supply = _body(strategy, "updateSupplyLiquidityVisual", "\ninvalidateDemandZone")

    _require(demand_scan, "array.set(demandZones, zoneArrayIndex, z)", "Demand liquidity scan")
    _require(supply_scan, "array.set(supplyZones, zoneArrayIndex, z)", "Supply liquidity scan")
    _require(clear_demand, "array.set(demandZones, idx, z)", "Demand liquidity visual clear")
    _require(update_demand, "array.set(demandZones, idx, z)", "Demand liquidity visual update")
    _require(clear_supply, "array.set(supplyZones, idx, z)", "Supply liquidity visual clear")
    _require(update_supply, "array.set(supplyZones, idx, z)", "Supply liquidity visual update")

    print("SND liquidity persistence static contract passed")


if __name__ == "__main__":
    main()
