from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def main() -> None:
    first_line = STRATEGY.read_text(encoding="utf-8").splitlines()[0]
    if first_line != "//@version=6":
        raise AssertionError("Pine version directive must be the first line so TradingView enables imports")

    print("SND Pine header static contract passed")


if __name__ == "__main__":
    main()
