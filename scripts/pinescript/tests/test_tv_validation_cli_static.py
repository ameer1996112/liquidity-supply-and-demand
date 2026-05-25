import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "scripts/pinescript/validation/fixtures/gbpjpy_invalid_zones.json"


def _fixture_scenario() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["scenario"]


def _mismatched_actual_payload() -> dict:
    return {
        "scenario": _fixture_scenario(),
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


def _run_compare(
    actual_payload: dict,
    actual_path: Path,
    output_dir: Path,
) -> subprocess.CompletedProcess[str]:
    actual_path.write_text(json.dumps(actual_payload), encoding="utf-8")
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [
            "python3",
            "-m",
            "scripts.pinescript.validation.cli",
            "compare-fixtures",
            "--expected",
            str(FIXTURE),
            "--actual",
            str(actual_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_reports_zone_mismatch_and_writes_report() -> None:
    with TemporaryDirectory() as tmp:
        actual_path = Path(tmp) / "actual.json"
        output_dir = Path(tmp) / "out"
        proc = _run_compare(_mismatched_actual_payload(), actual_path, output_dir)
        assert proc.returncode == 1
        assert "wrong_zone_low" in proc.stdout
        assert (output_dir / "report.md").exists()


def test_cli_rejects_actual_payload_without_zones() -> None:
    with TemporaryDirectory() as tmp:
        actual_path = Path(tmp) / "actual.json"
        output_dir = Path(tmp) / "out"
        proc = _run_compare({"scenario": _fixture_scenario()}, actual_path, output_dir)
        assert proc.returncode == 2
        assert "actual payload must include a 'zones' list" in proc.stderr
        assert proc.stdout == ""
        assert not (output_dir / "report.md").exists()


def main() -> None:
    test_cli_reports_zone_mismatch_and_writes_report()
    test_cli_rejects_actual_payload_without_zones()

    print("TradingView validation CLI static contract passed")


if __name__ == "__main__":
    main()
