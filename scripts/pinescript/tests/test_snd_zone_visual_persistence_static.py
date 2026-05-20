from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGIES = [
    ROOT / "scripts/pinescript/strategies/SND_Strategy.pine",
    ROOT / "scripts/pinescript/strategies/SND_Strategey_refactor.pine",
]


def _body(source: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in source:
        return ""
    start = source.index(start_marker)
    if end_marker not in source[start:]:
        return source[start:]
    end = source.index(end_marker, start)
    return source[start:end]


def _require(source: str, needles: list[str], label: str) -> None:
    missing = [needle for needle in needles if needle not in source]
    if missing:
        raise AssertionError(f"{label} missing:\n" + "\n".join(missing))


def main() -> None:
    for path in STRATEGIES:
        strategy = path.read_text(encoding="utf-8")

        delete_helper = _body(
            strategy,
            "delete_zone_visual_objects(Core.Zone z, bool isDemand) =>",
            "zone_should_show_visual(Core.Zone z, bool isDemand) =>",
        )
        _require(
            delete_helper,
            [
                "box.delete(z.boxId)",
                "z.boxId := na",
                "label.delete(z.idLabel)",
                "z.idLabel := na",
                "z",
            ],
            f"{path.name}: visual delete helper",
        )

        apply_visual = _body(
            strategy,
            "apply_zone_visual(Core.Zone z, bool isDemand) =>",
            "zone_overlap_pct(float topA, float bottomA, float topB, float bottomB) =>",
        )
        _require(
            apply_visual,
            [
                "delete_zone_visual_objects(z, isDemand)",
            ],
            f"{path.name}: apply_zone_visual hidden invalid cleanup",
        )

        demand_display = _body(
            strategy,
            "if show_zones and show_demand_zones",
            "if show_zones and show_supply_zones",
        )
        _require(
            demand_display,
            [
                "not na(z.boxId) or not na(z.idLabel)",
                "bool zoneVisible = apply_zone_visual(z, true)",
                "array.set(demandZones, i, z)",
            ],
            f"{path.name}: demand display visual state persistence",
        )
        demand_apply = demand_display.index("bool zoneVisible = apply_zone_visual(z, true)")
        demand_persist = demand_display.index("array.set(demandZones, i, z)")
        if not demand_apply < demand_persist:
            raise AssertionError(f"{path.name}: demand display must persist z after apply_zone_visual")

        supply_display = _body(
            strategy,
            "if show_zones and show_supply_zones",
            "\n\nif barstate.isconfirmed and cached_demand_size > 0 and allow_long_trades",
        )
        _require(
            supply_display,
            [
                "not na(z.boxId) or not na(z.idLabel)",
                "bool zoneVisible = apply_zone_visual(z, false)",
                "array.set(supplyZones, i, z)",
            ],
            f"{path.name}: supply display visual state persistence",
        )
        supply_apply = supply_display.index("bool zoneVisible = apply_zone_visual(z, false)")
        supply_persist = supply_display.index("array.set(supplyZones, i, z)")
        if not supply_apply < supply_persist:
            raise AssertionError(f"{path.name}: supply display must persist z after apply_zone_visual")

    print("SND zone visual persistence static contract passed")


if __name__ == "__main__":
    main()
