import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    fixture = ROOT / "scripts/pinescript/validation/fixtures/gbpjpy_invalid_zones.json"
    actual_payload = {
        "scenario": json.loads(fixture.read_text(encoding="utf-8"))["scenario"],
        "zones": [
            {
                "source": "S&D Pro",
                "side": "supply",
                "top": 213.130,
                "bottom": 213.080,
                "left_time": None,
                "right_time": None,
                "label": "S-11134",
                "id": "actual-supply",
            },
            {
                "source": "S&D Pro",
                "side": "demand",
                "top": 212.900,
                "bottom": 212.870,
                "left_time": None,
                "right_time": None,
                "label": "D-13856",
                "id": "actual-demand",
            },
        ],
    }
    with TemporaryDirectory() as tmp:
        actual_path = Path(tmp) / "actual.json"
        output_dir = Path(tmp) / "out"
        actual_path.write_text(json.dumps(actual_payload), encoding="utf-8")
        proc = subprocess.run(
            [
                "python3",
                str(ROOT / "scripts/pinescript/validation/cli.py"),
                "compare-fixtures",
                "--expected",
                str(fixture),
                "--actual",
                str(actual_path),
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert proc.returncode == 1
        assert "wrong_zone_low" in proc.stdout
        assert (output_dir / "report.md").exists()

    print("TradingView validation CLI static contract passed")


if __name__ == "__main__":
    main()
