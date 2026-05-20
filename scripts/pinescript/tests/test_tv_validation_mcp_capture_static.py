from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CAPTURE = ROOT / "scripts/pinescript/validation/mcp_capture.py"
CLI = ROOT / "scripts/pinescript/validation/cli.py"


def main() -> None:
    source = CAPTURE.read_text(encoding="utf-8")
    required = [
        "TRADINGVIEW_MCP_CLI",
        "TV_TARGET_ID",
        "capture_chart_evidence",
        "subprocess.run(",
        '"data", "boxes"',
        '"data", "labels"',
        "screenshot",
    ]
    for needle in required:
        if needle not in source:
            raise AssertionError(f"Missing MCP capture contract marker: {needle}")

    cli_source = CLI.read_text(encoding="utf-8")
    for needle in ["capture-live", "capture_chart_evidence", "--output-dir"]:
        if needle not in cli_source:
            raise AssertionError(f"Missing CLI live capture marker: {needle}")

    print("TradingView validation MCP capture static contract passed")


if __name__ == "__main__":
    main()
