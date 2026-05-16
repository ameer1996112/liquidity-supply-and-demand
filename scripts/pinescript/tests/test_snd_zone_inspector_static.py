from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")

    required = [
        'showZoneInspector     = input.bool(true, "showZoneInspector", group = "🎨 Display")',
        'manual_zone_id_input  = input.string(',
        '"manual_zone_id_input"',
        "var table zoneInspector = na",
        "draw_zone_inspector_table(tbl) =>",
        "manualInputClean = str.trim(manual_zone_id_input)",
        "findDemandZoneIndexByUZID(targetId)",
        "findSupplyZoneIndexByUZID(targetId)",
        "bool manualLookupMissed = false",
        "manualLookupMissed := str.length(manualInputClean) > 0 and not na(targetId) and na(zoneIdx)",
        "bool fallbackToLatestZone = manualLookupMissed",
        "MANUAL_NOT_FOUND_AUTO",
        "string inducementText =",
        "string targetText =",
        'table.cell(result, 0, 0, "Zone #"',
        'zi_row(result, 1, "Zone ID"',
        'zi_row(result, 2, "Type"',
        'zi_row(result, 3, "Manual ID"',
        'zi_row(result, 4, "Found In"',
        'zi_row(result, 5, "Lookup"',
        'zi_row(result, 10, "Liq Required"',
        'zi_row(result, 11, "Liquidity"',
        'zi_row(result, 14, "Liq Distance"',
        'zi_row(result, 15, "Zone Caused Sweep"',
        'zi_row(result, 16, "Wick In Zone"',
        'zi_row(result, 17, "Not Closed In"',
        'zi_row(result, 18, "Close Type"',
        'zi_row(result, 19, "Zone Used"',
        'zi_row(result, 20, "Entry Allowed"',
        'zi_row(result, 22, "Inducement"',
        'zi_row(result, 23, "Target"',
        'zi_row(result, 24, "Liq Source"',
        "zoneInspector := draw_zone_inspector_table(zoneInspector)",
    ]

    missing = [item for item in required if item not in strategy]
    if missing:
        raise AssertionError("Missing zone inspector contract markers:\n" + "\n".join(missing))

    print("SND zone inspector static contract passed")


if __name__ == "__main__":
    main()
