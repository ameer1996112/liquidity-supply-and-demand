from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGIES = [
    ROOT / "scripts/pinescript/strategies/SND_Strategy.pine",
    ROOT / "scripts/pinescript/strategies/SND_Strategey_refactor.pine",
]


def _body(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _assert_before(source: str, earlier: str, later: str, label: str) -> None:
    earlier_pos = source.index(earlier)
    later_pos = source.index(later)
    if earlier_pos > later_pos:
        raise AssertionError(f"{label}: expected {earlier!r} before {later!r}")


def main() -> None:
    for path in STRATEGIES:
        strategy = path.read_text(encoding="utf-8")

        validate_entry = _body(
            strategy,
            "validate_entry_conditions(bool isDemand, int idx) =>",
            "float touchTolerance = 0.0",
        )
        _assert_before(
            validate_entry,
            "if not z.liquidityValid",
            "else if not z.liquiditySwept",
            f"{path.name} liquidity validity gate order",
        )
        if "not z.causedSweep" in validate_entry:
            raise AssertionError(f"{path.name}: causedSweep must not mask missing liquidity")
        if "waiting_liquidity_reason(z, isDemand)" not in validate_entry:
            raise AssertionError(f"{path.name}: missing specific waiting-liquidity reason")

        inspector = _body(
            strategy,
            "liqRequired := require_liquidity_sweep ? \"Yes\" : \"No\"",
            "float sweepTol = syminfo.mintick * 20",
        )
        for needle in [
            "Waiting Inducement High",
            "Waiting Inducement Low",
            "Waiting Strong Leg",
        ]:
            if needle not in inspector:
                raise AssertionError(f"{path.name}: inspector missing {needle!r}")

    print("SND liquidity waiting reason static contract passed")


if __name__ == "__main__":
    main()
