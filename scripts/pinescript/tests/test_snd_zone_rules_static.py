import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"
CORE = ROOT / "scripts/pinescript/libraries/SND_Core.pine"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"Missing {label}: {needle}")


def reject(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"Forbidden {label}: {needle}")


def reject_pattern(text: str, pattern: str, label: str) -> None:
    if re.search(pattern, text):
        raise AssertionError(f"Forbidden {label}: {pattern}")


def main() -> None:
    strategy = read(STRATEGY)
    core = read(CORE)

    for field in [
        "int   state",
        "string stateReason",
        "int   originBarIndex",
        "int   departureEndBarIndex",
        "int   firstInvalidBarIndex",
        "int   liquiditySwingBarIndex",
        "int   structureBreakBarIndex",
        "int   entryEligibleBarIndex",
    ]:
        require(core, field, "Core.Zone lifecycle field")

    for field in [
        "int   state",
        "string stateReason",
    ]:
        require(core, field, "Core.ZoneDBEntry lifecycle field")

    for helper in [
        "const int ZONE_STATE_CANDIDATE",
        "const int ZONE_STATE_ARMED",
        "zone_state_name(int state)",
        "zone_set_state(Core.Zone z, int state, string reason)",
        "youtube_zone_bounds(bool isDemand, int originIdx, int reactionIdx)",
        "zone_is_armed_for_entry(Core.Zone z)",
        "zone_pre_entry_invalidated(Core.Zone z, bool isDemand)",
        "zone_update_expiry(Core.Zone z)",
        "zone_update_liquidity_and_bos(Core.Zone z, bool isDemand)",
    ]:
        require(strategy, helper, "strategy lifecycle helper")

    for needle in [
        "entry.state := z.state",
        "entry.stateReason := z.stateReason",
        "updated.state < ZONE_STATE_ARMED",
        "int i = cached_demand_size - 1 - demandScan",
        "int i = cached_supply_size - 1 - supplyScan",
    ]:
        require(strategy, needle, "Task 6 lifecycle safety guard")

    for needle in [
        "not zone_is_armed_for_entry(z)",
        "ZONE_STATE_USED, \"Long entry opened\"",
        "ZONE_STATE_USED, \"Short entry opened\"",
        "debug_enabled or zone_is_visible_clean(z)",
        "zone_state_name(z.state) + \": \" + z.stateReason",
    ]:
        require(strategy, needle, "Task 7 entry/drawing lifecycle gate")

    for needle in [
        "clear_zone_visual_objects(Core.Zone z, bool includeTargetLine)",
        "z := clear_zone_visual_objects(z, false)",
        "z := clear_zone_visual_objects(z, true)",
        "while demandInvalidScanIdx >= 0",
        "while supplyInvalidScanIdx >= 0",
    ]:
        require(strategy, needle, "Task 8 runtime safety guard")

    reject(strategy, "to 0 by -1", "negative Pine loop step")
    reject(strategy, " by -", "negative Pine loop step")
    reject(strategy, "SND_Core/26", "stale Core import without lifecycle fields")
    reject_pattern(strategy, r"for\\s+\\w+\\s*=\\s*[^\\n]+\\s+to\\s+0\\b", "reverse Pine for loop")

    print("SND zone rule static contract passed")


if __name__ == "__main__":
    main()
