from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")
    accuracy_block = strategy[
        strategy.index("if isAccuracy") :
        strategy.index("\n            else\n                // Normal zones", strategy.index("if isAccuracy"))
    ]

    required = [
        "bool bearishAccuracySupply = baseClose < baseOpen",
        "zTop := bearishAccuracySupply ? baseOpen : baseHigh",
        "zBottom := bearishAccuracySupply ? baseLow : baseOpen",
        "zTop := baseOpen",
        "zBottom := baseLow",
    ]

    for needle in required:
        if needle not in accuracy_block:
            raise AssertionError(f"Missing accuracy boundary contract: {needle}")

    forbidden = [
        "// Supply Accuracy: Top = HIGH (extreme), Bottom = OPEN (body bottom)\n                    zTop := baseHigh\n                    zBottom := baseOpen",
    ]

    for needle in forbidden:
        if needle in strategy:
            raise AssertionError(f"Stale accuracy supply boundary remains: {needle}")

    print("SND accuracy boundary static contract passed")


if __name__ == "__main__":
    main()
