# TradingView Strategy Validation Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a TradingView-backed validation harness that captures S&D strategy zone evidence, compares it against reference/manual expectations, and saves human plus machine-readable regression artifacts.

**Architecture:** Implement a small Python package under `scripts/pinescript/validation/` with focused modules for models, fixture I/O, normalization, comparison, reporting, and MCP capture. Keep live TradingView calls optional; comparator and report tests must run without TradingView open.

**Tech Stack:** Python 3 standard library, existing `mcp/tradingview-mcp` Node CLI for live chart capture, existing repo convention of executable Python test scripts under `scripts/pinescript/tests/`.

---

## File Structure

- Create `scripts/pinescript/validation/__init__.py`
  - Package marker.
- Create `scripts/pinescript/validation/models.py`
  - Dataclasses and enums: `Zone`, `Scenario`, `Mismatch`, `ValidationResult`.
- Create `scripts/pinescript/validation/fixtures.py`
  - Load/save JSON fixtures and artifacts.
- Create `scripts/pinescript/validation/normalizer.py`
  - Convert raw MCP boxes/labels into normalized `Zone` records.
- Create `scripts/pinescript/validation/comparator.py`
  - Match expected/reference zones against actual strategy zones.
- Create `scripts/pinescript/validation/report.py`
  - Write `report.md` from scenario, zones, and mismatches.
- Create `scripts/pinescript/validation/mcp_capture.py`
  - Optional live TradingView capture wrapper around `mcp/tradingview-mcp`.
- Create `scripts/pinescript/validation/cli.py`
  - CLI entrypoint for fixture comparison and optional live capture.
- Create `scripts/pinescript/validation/fixtures/gbpjpy_invalid_zones.json`
  - First saved sample fixture for comparator tests.
- Create `scripts/pinescript/tests/test_tv_validation_normalizer.py`
- Create `scripts/pinescript/tests/test_tv_validation_comparator.py`
- Create `scripts/pinescript/tests/test_tv_validation_report.py`
- Create `scripts/pinescript/tests/test_tv_validation_cli_static.py`

Do not modify `scripts/pinescript/strategies/SND_Strategy.pine` in this milestone.

---

### Task 1: Models And Fixture I/O

**Files:**
- Create: `scripts/pinescript/validation/__init__.py`
- Create: `scripts/pinescript/validation/models.py`
- Create: `scripts/pinescript/validation/fixtures.py`
- Create: `scripts/pinescript/tests/test_tv_validation_models_fixtures.py`

- [ ] **Step 1: Write the failing model/fixture test**

Create `scripts/pinescript/tests/test_tv_validation_models_fixtures.py`:

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.pinescript.validation.fixtures import load_fixture, save_fixture
from scripts.pinescript.validation.models import Scenario, Zone


def main() -> None:
    scenario = Scenario(
        name="GBPJPY invalid zones",
        symbol="GBPJPY",
        timeframe="5",
        comparison_mode="manual",
        expected_scripts=["S&D Pro"],
        price_tolerance=0.001,
        time_tolerance_bars=1,
    )
    zones = [
        Zone(
            source="S&D Pro",
            side="demand",
            top=212.900,
            bottom=212.880,
            left_time="2026-05-20T12:30:00+03:00",
            right_time="2026-05-20T13:00:00+03:00",
            label="D-13856",
        )
    ]
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "fixture.json"
        save_fixture(path, scenario=scenario, zones=zones)
        loaded = load_fixture(path)
        assert loaded.scenario.name == scenario.name
        assert loaded.scenario.symbol == "GBPJPY"
        assert loaded.zones[0].label == "D-13856"
        assert loaded.zones[0].bottom == 212.880

    print("TradingView validation models/fixtures contract passed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_models_fixtures.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.pinescript.validation'`.

- [ ] **Step 3: Create package marker**

Create `scripts/pinescript/validation/__init__.py`:

```python
"""TradingView S&D strategy validation harness."""
```

- [ ] **Step 4: Implement models**

Create `scripts/pinescript/validation/models.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


ZoneSide = Literal["demand", "supply"]
MismatchKind = Literal[
    "missing_expected_zone",
    "extra_unexpected_zone",
    "wrong_zone_high",
    "wrong_zone_low",
    "wrong_side",
    "invalid_zone_still_visible",
    "inconclusive",
]


@dataclass(frozen=True)
class Scenario:
    name: str
    symbol: str
    timeframe: str
    comparison_mode: str
    expected_scripts: list[str]
    price_tolerance: float
    time_tolerance_bars: int
    replay_at: str | None = None
    visible_from: str | None = None
    visible_to: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Scenario":
        return cls(
            name=str(data["name"]),
            symbol=str(data["symbol"]),
            timeframe=str(data["timeframe"]),
            comparison_mode=str(data["comparison_mode"]),
            expected_scripts=list(data.get("expected_scripts", [])),
            price_tolerance=float(data["price_tolerance"]),
            time_tolerance_bars=int(data["time_tolerance_bars"]),
            replay_at=data.get("replay_at"),
            visible_from=data.get("visible_from"),
            visible_to=data.get("visible_to"),
        )


@dataclass(frozen=True)
class Zone:
    source: str
    side: ZoneSide
    top: float
    bottom: float
    left_time: str | None
    right_time: str | None
    label: str
    id: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Zone":
        return cls(
            source=str(data["source"]),
            side=str(data["side"]),  # type: ignore[arg-type]
            top=float(data["top"]),
            bottom=float(data["bottom"]),
            left_time=data.get("left_time"),
            right_time=data.get("right_time"),
            label=str(data.get("label", "")),
            id=data.get("id"),
        )


@dataclass(frozen=True)
class Mismatch:
    kind: MismatchKind
    message: str
    expected: Zone | None = None
    actual: Zone | None = None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "message": self.message,
            "expected": self.expected.to_dict() if self.expected else None,
            "actual": self.actual.to_dict() if self.actual else None,
        }


@dataclass(frozen=True)
class ValidationFixture:
    scenario: Scenario
    zones: list[Zone]


@dataclass(frozen=True)
class ValidationResult:
    scenario: Scenario
    expected_zones: list[Zone]
    actual_zones: list[Zone]
    mismatches: list[Mismatch]
    screenshot_path: str | None = None

    @property
    def passed(self) -> bool:
        return len(self.mismatches) == 0
```

- [ ] **Step 5: Implement fixture I/O**

Create `scripts/pinescript/validation/fixtures.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from scripts.pinescript.validation.models import Scenario, ValidationFixture, Zone


def save_fixture(path: Path, *, scenario: Scenario, zones: list[Zone]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scenario": scenario.to_dict(),
        "zones": [zone.to_dict() for zone in zones],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_fixture(path: Path) -> ValidationFixture:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenario = Scenario.from_dict(payload["scenario"])
    zones = [Zone.from_dict(item) for item in payload.get("zones", [])]
    return ValidationFixture(scenario=scenario, zones=zones)
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_models_fixtures.py
```

Expected: PASS with `TradingView validation models/fixtures contract passed`.

- [ ] **Step 7: Commit**

```bash
git add scripts/pinescript/validation/__init__.py \
  scripts/pinescript/validation/models.py \
  scripts/pinescript/validation/fixtures.py \
  scripts/pinescript/tests/test_tv_validation_models_fixtures.py
git commit -m "DEV-610: add validation harness models"
```

---

### Task 2: Normalize Raw TradingView Zones

**Files:**
- Create: `scripts/pinescript/validation/normalizer.py`
- Create: `scripts/pinescript/tests/test_tv_validation_normalizer.py`

- [ ] **Step 1: Write the failing normalizer test**

Create `scripts/pinescript/tests/test_tv_validation_normalizer.py`:

```python
from scripts.pinescript.validation.normalizer import normalize_zones


def main() -> None:
    raw_boxes = [
        {
            "id": "box-1",
            "top": 4496.0,
            "bottom": 4492.0,
            "leftTime": "2026-05-20T03:45:00+03:00",
            "rightTime": "2026-05-20T13:00:00+03:00",
            "study": "S&D Pro",
        },
        {
            "id": "box-2",
            "top": 212.900,
            "bottom": 212.880,
            "left_time": "2026-05-20T12:30:00+03:00",
            "right_time": "2026-05-20T13:00:00+03:00",
            "study": "Zones Liq S/D v23 - Myrtille",
        },
    ]
    raw_labels = [
        {"text": " S-19396 ", "boxId": "box-1", "study": "S&D Pro"},
        {"text": "D-13856", "boxId": "box-2", "study": "Zones Liq S/D v23 - Myrtille"},
    ]

    zones = normalize_zones(raw_boxes=raw_boxes, raw_labels=raw_labels)
    assert len(zones) == 2
    assert zones[0].source == "S&D Pro"
    assert zones[0].side == "supply"
    assert zones[0].label == "S-19396"
    assert zones[1].side == "demand"
    assert zones[1].left_time == "2026-05-20T12:30:00+03:00"

    print("TradingView validation normalizer contract passed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_normalizer.py
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `normalizer`.

- [ ] **Step 3: Implement normalizer**

Create `scripts/pinescript/validation/normalizer.py`:

```python
from __future__ import annotations

from collections.abc import Iterable

from scripts.pinescript.validation.models import Zone


def _first_value(data: dict, keys: Iterable[str]) -> object | None:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _label_for_box(raw_labels: list[dict], box_id: str | None, source: str) -> str:
    for label in raw_labels:
        label_box_id = _first_value(label, ["boxId", "box_id", "parentId", "parent_id"])
        label_source = str(_first_value(label, ["study", "source", "script", "owner"]) or "")
        if box_id and label_box_id == box_id:
            return str(_first_value(label, ["text", "label", "name"]) or "").strip()
        if not box_id and label_source == source:
            text = str(_first_value(label, ["text", "label", "name"]) or "").strip()
            if text.startswith(("D-", "S-", "ACC D-", "ACC S-")):
                return text
    return ""


def _side_from_label(label: str) -> str:
    clean = label.strip().upper()
    if clean.startswith("ACC D-") or clean.startswith("D-"):
        return "demand"
    if clean.startswith("ACC S-") or clean.startswith("S-"):
        return "supply"
    return "demand"


def normalize_zones(*, raw_boxes: list[dict], raw_labels: list[dict]) -> list[Zone]:
    zones: list[Zone] = []
    for box in raw_boxes:
        box_id_value = _first_value(box, ["id", "boxId", "box_id"])
        box_id = str(box_id_value) if box_id_value is not None else None
        source = str(_first_value(box, ["study", "source", "script", "owner"]) or "unknown")
        label = _label_for_box(raw_labels, box_id, source)
        top = float(_first_value(box, ["top", "high", "zoneHigh"]) or 0.0)
        bottom = float(_first_value(box, ["bottom", "low", "zoneLow"]) or 0.0)
        zones.append(
            Zone(
                source=source,
                side=_side_from_label(label),  # type: ignore[arg-type]
                top=max(top, bottom),
                bottom=min(top, bottom),
                left_time=_first_value(box, ["leftTime", "left_time", "startTime", "start_time"]),  # type: ignore[arg-type]
                right_time=_first_value(box, ["rightTime", "right_time", "endTime", "end_time"]),  # type: ignore[arg-type]
                label=label,
                id=box_id,
            )
        )
    return zones
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_normalizer.py
```

Expected: PASS with `TradingView validation normalizer contract passed`.

- [ ] **Step 5: Run previous model test**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_models_fixtures.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/pinescript/validation/normalizer.py scripts/pinescript/tests/test_tv_validation_normalizer.py
git commit -m "DEV-610: normalize TradingView zone objects"
```

---

### Task 3: Compare Expected And Actual Zones

**Files:**
- Create: `scripts/pinescript/validation/comparator.py`
- Create: `scripts/pinescript/tests/test_tv_validation_comparator.py`

- [ ] **Step 1: Write the failing comparator test**

Create `scripts/pinescript/tests/test_tv_validation_comparator.py`:

```python
from scripts.pinescript.validation.comparator import compare_zones
from scripts.pinescript.validation.models import Scenario, Zone


def _scenario() -> Scenario:
    return Scenario(
        name="GBPJPY invalid zones",
        symbol="GBPJPY",
        timeframe="5",
        comparison_mode="manual",
        expected_scripts=["S&D Pro"],
        price_tolerance=0.001,
        time_tolerance_bars=1,
    )


def main() -> None:
    expected = [
        Zone("manual", "supply", 213.130, 213.080, None, None, "S-11134"),
        Zone("manual", "demand", 212.900, 212.880, None, None, "D-13856"),
    ]
    actual = [
        Zone("S&D Pro", "supply", 213.130, 213.080, None, None, "S-11134"),
        Zone("S&D Pro", "demand", 212.900, 212.870, None, None, "D-13856"),
        Zone("S&D Pro", "demand", 212.820, 212.740, None, None, "D-invalid"),
    ]

    result = compare_zones(_scenario(), expected_zones=expected, actual_zones=actual)
    kinds = [mismatch.kind for mismatch in result.mismatches]
    assert "wrong_zone_low" in kinds
    assert "extra_unexpected_zone" in kinds
    assert not result.passed

    clean = compare_zones(_scenario(), expected_zones=expected, actual_zones=expected)
    assert clean.passed
    assert clean.mismatches == []

    print("TradingView validation comparator contract passed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_comparator.py
```

Expected: FAIL with missing `comparator`.

- [ ] **Step 3: Implement comparator**

Create `scripts/pinescript/validation/comparator.py`:

```python
from __future__ import annotations

from scripts.pinescript.validation.models import Mismatch, Scenario, ValidationResult, Zone


def _price_close(left: float, right: float, tolerance: float) -> bool:
    return abs(left - right) <= tolerance


def _zone_candidate(expected: Zone, actual: Zone, tolerance: float) -> bool:
    if expected.side != actual.side:
        return False
    if expected.label and actual.label and expected.label == actual.label:
        return True
    top_near = _price_close(expected.top, actual.top, tolerance * 4)
    bottom_near = _price_close(expected.bottom, actual.bottom, tolerance * 4)
    return top_near or bottom_near


def _find_match(expected: Zone, actual_zones: list[Zone], used_actual: set[int], tolerance: float) -> tuple[int, Zone] | None:
    for idx, actual in enumerate(actual_zones):
        if idx in used_actual:
            continue
        if _zone_candidate(expected, actual, tolerance):
            return idx, actual
    return None


def compare_zones(
    scenario: Scenario,
    *,
    expected_zones: list[Zone],
    actual_zones: list[Zone],
    screenshot_path: str | None = None,
) -> ValidationResult:
    mismatches: list[Mismatch] = []
    used_actual: set[int] = set()

    for expected in expected_zones:
        match = _find_match(expected, actual_zones, used_actual, scenario.price_tolerance)
        if match is None:
            mismatches.append(
                Mismatch(
                    kind="missing_expected_zone",
                    message=f"Missing expected {expected.side} zone {expected.label}",
                    expected=expected,
                )
            )
            continue

        idx, actual = match
        used_actual.add(idx)
        if not _price_close(expected.top, actual.top, scenario.price_tolerance):
            mismatches.append(
                Mismatch(
                    kind="wrong_zone_high",
                    message=f"{expected.label} high expected {expected.top}, got {actual.top}",
                    expected=expected,
                    actual=actual,
                )
            )
        if not _price_close(expected.bottom, actual.bottom, scenario.price_tolerance):
            mismatches.append(
                Mismatch(
                    kind="wrong_zone_low",
                    message=f"{expected.label} low expected {expected.bottom}, got {actual.bottom}",
                    expected=expected,
                    actual=actual,
                )
            )

    for idx, actual in enumerate(actual_zones):
        if idx not in used_actual:
            mismatches.append(
                Mismatch(
                    kind="extra_unexpected_zone",
                    message=f"Unexpected {actual.side} zone {actual.label}",
                    actual=actual,
                )
            )

    return ValidationResult(
        scenario=scenario,
        expected_zones=expected_zones,
        actual_zones=actual_zones,
        mismatches=mismatches,
        screenshot_path=screenshot_path,
    )
```

- [ ] **Step 4: Run comparator test**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_comparator.py
```

Expected: PASS with `TradingView validation comparator contract passed`.

- [ ] **Step 5: Run all validation tests so far**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_models_fixtures.py
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_normalizer.py
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_comparator.py
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/pinescript/validation/comparator.py scripts/pinescript/tests/test_tv_validation_comparator.py
git commit -m "DEV-610: compare expected and actual zones"
```

---

### Task 4: Write Human Reports

**Files:**
- Create: `scripts/pinescript/validation/report.py`
- Create: `scripts/pinescript/tests/test_tv_validation_report.py`

- [ ] **Step 1: Write the failing report test**

Create `scripts/pinescript/tests/test_tv_validation_report.py`:

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.pinescript.validation.comparator import compare_zones
from scripts.pinescript.validation.models import Scenario, Zone
from scripts.pinescript.validation.report import write_report


def main() -> None:
    scenario = Scenario(
        name="XAUUSD normal supply",
        symbol="XAUUSD",
        timeframe="5",
        comparison_mode="manual",
        expected_scripts=["S&D Pro", "Zones Liq S/D v23 - Myrtille"],
        price_tolerance=0.25,
        time_tolerance_bars=1,
    )
    expected = [Zone("manual", "supply", 4496.0, 4492.0, None, None, "S-manual")]
    actual = [Zone("S&D Pro", "supply", 4495.0, 4492.0, None, None, "S-19396")]
    result = compare_zones(scenario, expected_zones=expected, actual_zones=actual, screenshot_path="screenshot.png")

    with TemporaryDirectory() as tmp:
        report_path = write_report(Path(tmp), result)
        text = report_path.read_text(encoding="utf-8")
        assert "# TradingView Validation Report" in text
        assert "XAUUSD normal supply" in text
        assert "wrong_zone_high" in text
        assert "screenshot.png" in text

    print("TradingView validation report contract passed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_report.py
```

Expected: FAIL with missing `report`.

- [ ] **Step 3: Implement report writer**

Create `scripts/pinescript/validation/report.py`:

```python
from __future__ import annotations

from pathlib import Path

from scripts.pinescript.validation.models import ValidationResult, Zone


def _zone_line(zone: Zone) -> str:
    return f"- `{zone.label}` {zone.side} {zone.bottom:g} - {zone.top:g} from `{zone.source}`"


def write_report(output_dir: Path, result: ValidationResult) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "report.md"
    lines = [
        "# TradingView Validation Report",
        "",
        f"**Scenario:** {result.scenario.name}",
        f"**Symbol:** {result.scenario.symbol}",
        f"**Timeframe:** {result.scenario.timeframe}",
        f"**Status:** {'PASS' if result.passed else 'FAIL'}",
        f"**Screenshot:** {result.screenshot_path or 'not captured'}",
        "",
        "## Expected Zones",
        "",
        *[_zone_line(zone) for zone in result.expected_zones],
        "",
        "## Actual Zones",
        "",
        *[_zone_line(zone) for zone in result.actual_zones],
        "",
        "## Mismatches",
        "",
    ]
    if result.mismatches:
        for mismatch in result.mismatches:
            lines.append(f"- `{mismatch.kind}`: {mismatch.message}")
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
```

- [ ] **Step 4: Run report test**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_report.py
```

Expected: PASS with `TradingView validation report contract passed`.

- [ ] **Step 5: Run all validation tests so far**

Run:

```bash
for test in \
  scripts/pinescript/tests/test_tv_validation_models_fixtures.py \
  scripts/pinescript/tests/test_tv_validation_normalizer.py \
  scripts/pinescript/tests/test_tv_validation_comparator.py \
  scripts/pinescript/tests/test_tv_validation_report.py
do
  PYTHONPATH=. python3 "$test"
done
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/pinescript/validation/report.py scripts/pinescript/tests/test_tv_validation_report.py
git commit -m "DEV-610: write TradingView validation reports"
```

---

### Task 5: Add Fixture-Based CLI

**Files:**
- Create: `scripts/pinescript/validation/cli.py`
- Create: `scripts/pinescript/validation/fixtures/gbpjpy_invalid_zones.json`
- Create: `scripts/pinescript/tests/test_tv_validation_cli_static.py`

- [ ] **Step 1: Write the fixture file**

Create `scripts/pinescript/validation/fixtures/gbpjpy_invalid_zones.json`:

```json
{
  "scenario": {
    "comparison_mode": "manual",
    "expected_scripts": ["S&D Pro"],
    "name": "GBPJPY invalid zones after wick and close breaches",
    "price_tolerance": 0.001,
    "symbol": "GBPJPY",
    "time_tolerance_bars": 1,
    "timeframe": "5"
  },
  "zones": [
    {
      "bottom": 213.080,
      "id": "manual-supply",
      "label": "S-11134",
      "left_time": "2026-05-20T03:00:00+03:00",
      "right_time": "2026-05-20T13:00:00+03:00",
      "side": "supply",
      "source": "manual",
      "top": 213.130
    },
    {
      "bottom": 212.880,
      "id": "manual-demand",
      "label": "D-13856",
      "left_time": "2026-05-20T12:30:00+03:00",
      "right_time": "2026-05-20T13:00:00+03:00",
      "side": "demand",
      "source": "manual",
      "top": 212.900
    }
  ]
}
```

- [ ] **Step 2: Write the failing CLI static test**

Create `scripts/pinescript/tests/test_tv_validation_cli_static.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_cli_static.py
```

Expected: FAIL because `cli.py` does not exist.

- [ ] **Step 4: Implement CLI**

Create `scripts/pinescript/validation/cli.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.pinescript.validation.comparator import compare_zones
from scripts.pinescript.validation.fixtures import load_fixture
from scripts.pinescript.validation.models import Zone
from scripts.pinescript.validation.report import write_report


def _load_actual(path: Path) -> list[Zone]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Zone.from_dict(item) for item in payload.get("zones", [])]


def compare_fixtures(args: argparse.Namespace) -> int:
    expected = load_fixture(Path(args.expected))
    actual_zones = _load_actual(Path(args.actual))
    result = compare_zones(
        expected.scenario,
        expected_zones=expected.zones,
        actual_zones=actual_zones,
    )
    report_path = write_report(Path(args.output_dir), result)
    summary = {
        "passed": result.passed,
        "report": str(report_path),
        "mismatches": [mismatch.to_dict() for mismatch in result.mismatches],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.passed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TradingView S&D validation harness")
    subcommands = parser.add_subparsers(dest="command", required=True)
    compare = subcommands.add_parser("compare-fixtures")
    compare.add_argument("--expected", required=True)
    compare.add_argument("--actual", required=True)
    compare.add_argument("--output-dir", required=True)
    compare.set_defaults(func=compare_fixtures)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run CLI static test**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_cli_static.py
```

Expected: PASS with `TradingView validation CLI static contract passed`.

- [ ] **Step 6: Run all validation tests**

Run:

```bash
for test in scripts/pinescript/tests/test_tv_validation_*.py; do
  PYTHONPATH=. python3 "$test"
done
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/pinescript/validation/cli.py \
  scripts/pinescript/validation/fixtures/gbpjpy_invalid_zones.json \
  scripts/pinescript/tests/test_tv_validation_cli_static.py
git commit -m "DEV-610: add fixture validation CLI"
```

---

### Task 6: Add Optional MCP Capture

**Files:**
- Create: `scripts/pinescript/validation/mcp_capture.py`
- Modify: `scripts/pinescript/validation/cli.py`
- Create: `scripts/pinescript/tests/test_tv_validation_mcp_capture_static.py`

- [ ] **Step 1: Write the static MCP capture test**

Create `scripts/pinescript/tests/test_tv_validation_mcp_capture_static.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_mcp_capture_static.py
```

Expected: FAIL because `mcp_capture.py` does not exist.

- [ ] **Step 3: Implement MCP capture wrapper**

Create `scripts/pinescript/validation/mcp_capture.py`:

```python
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TRADINGVIEW_MCP_CLI = ROOT / "mcp/tradingview-mcp/src/cli/index.js"


def _run_tv(args: list[str]) -> dict:
    env = os.environ.copy()
    if env.get("TV_TARGET_ID"):
        env["TV_TARGET_ID"] = env["TV_TARGET_ID"]
    proc = subprocess.run(
        ["node", str(TRADINGVIEW_MCP_CLI), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"TradingView MCP command failed: {' '.join(args)}\n{proc.stderr}\n{proc.stdout}")
    return json.loads(proc.stdout)


def capture_chart_evidence(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    boxes = _run_tv(["data", "boxes"])
    labels = _run_tv(["data", "labels"])
    screenshot = _run_tv(["screenshot", "--region", "chart"])
    payload = {
        "boxes": boxes,
        "labels": labels,
        "screenshot": screenshot,
    }
    (output_dir / "raw_mcp.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
```

- [ ] **Step 4: Extend CLI with live capture command**

Modify `scripts/pinescript/validation/cli.py`:

```python
from scripts.pinescript.validation.mcp_capture import capture_chart_evidence
```

Add this function before `build_parser()`:

```python
def capture_live(args: argparse.Namespace) -> int:
    payload = capture_chart_evidence(Path(args.output_dir))
    print(json.dumps({"captured": True, "keys": sorted(payload.keys())}, indent=2, sort_keys=True))
    return 0
```

Add this subcommand inside `build_parser()`:

```python
    capture = subcommands.add_parser("capture-live")
    capture.add_argument("--output-dir", required=True)
    capture.set_defaults(func=capture_live)
```

- [ ] **Step 5: Run static MCP capture test**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_tv_validation_mcp_capture_static.py
```

Expected: PASS with `TradingView validation MCP capture static contract passed`.

- [ ] **Step 6: Run optional live smoke only when TradingView is open**

Run only if TradingView Desktop is running with CDP:

```bash
PYTHONPATH=. python3 scripts/pinescript/validation/cli.py capture-live --output-dir artifacts/tradingview-validation/smoke
```

Expected when TradingView is available: exit `0` and `artifacts/tradingview-validation/smoke/raw_mcp.json` exists.

Expected when TradingView is unavailable: explicit `RuntimeError` mentioning the failed TradingView MCP command. Do not treat unavailable TradingView as a CI failure.

- [ ] **Step 7: Run all non-live validation tests**

Run:

```bash
for test in scripts/pinescript/tests/test_tv_validation_*.py; do
  PYTHONPATH=. python3 "$test"
done
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add scripts/pinescript/validation/mcp_capture.py \
  scripts/pinescript/validation/cli.py \
  scripts/pinescript/tests/test_tv_validation_mcp_capture_static.py
git commit -m "DEV-610: add optional TradingView MCP capture"
```

---

### Task 7: Final Verification And Handoff

**Files:**
- No new files.
- Verify all files created in Tasks 1-6.

- [ ] **Step 1: Run validation harness tests**

Run:

```bash
for test in scripts/pinescript/tests/test_tv_validation_*.py; do
  PYTHONPATH=. python3 "$test"
done
```

Expected: all PASS.

- [ ] **Step 2: Run Pine-focused regression tests touched by recent strategy work**

Run:

```bash
PYTHONPATH=. python3 scripts/pinescript/tests/test_snd_live_replay_invalidation_static.py
PYTHONPATH=. python3 scripts/pinescript/tests/test_snd_zone_invalidation_static.py
PYTHONPATH=. python3 scripts/pinescript/tests/test_snd_zone_visual_persistence_static.py
PYTHONPATH=. python3 scripts/pinescript/tests/test_snd_zone_rules_static.py
PYTHONPATH=. python3 scripts/pinescript/tests/test_snd_liquidity_waiting_reason_static.py
```

Expected: all PASS. If a pre-existing stale Pine contract fails, document it in the final handoff instead of changing strategy code in this milestone.

- [ ] **Step 3: Run formatting/diff checks**

Run:

```bash
git diff --check
```

Expected: no output and exit `0`.

- [ ] **Step 4: Inspect final status**

Run:

```bash
git status --short
```

Expected: only intended validation harness files are modified/staged. If `scripts/pinescript/strategies/SND_Strategy.pine` is still unstaged from the user, leave it unstaged.

- [ ] **Step 5: Commit final cleanup if needed**

If Task 7 required documentation-only cleanup, run:

```bash
git add docs/superpowers/plans/2026-05-20-tradingview-strategy-validation-harness.md
git commit -m "DEV-610: document validation harness execution"
```

If no cleanup was needed, skip this commit.

---

## Notes For Implementers

- Keep live TradingView usage optional. Unit, fixture, and report tests must run without TradingView open.
- Do not touch Pine strategy logic in this milestone.
- Do not include generated `artifacts/tradingview-validation/*` files in commits unless the user explicitly asks for an evidence bundle.
- The current repo may contain an unstaged `scripts/pinescript/strategies/SND_Strategy.pine` change. Treat it as user-owned unless the user explicitly includes it.
