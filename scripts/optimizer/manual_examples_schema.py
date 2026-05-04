from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MANUAL_EXAMPLE_FIELDS = (
    "symbol",
    "timeframe",
    "date",
    "time",
    "direction",
    "expected_action",
    "expected_zone_type",
    "expected_reason",
    "notes",
)

TAKE_ACTIONS = {"take_trade", "take"}
SKIP_ACTIONS = {"skip_trade", "skip"}


@dataclass(frozen=True)
class ManualTradeExample:
    symbol: str
    timeframe: str
    date: str
    time: str
    direction: str
    expected_action: str
    expected_zone_type: str
    expected_reason: str
    notes: str = ""

    @property
    def timestamp(self) -> datetime:
        time_value = self.time if self.time.count(":") >= 2 else f"{self.time}:00"
        return datetime.fromisoformat(f"{self.date}T{time_value}")

    @property
    def timestamp_iso(self) -> str:
        return self.timestamp.isoformat(timespec="seconds")

    @property
    def expects_trade(self) -> bool:
        return self.expected_action in TAKE_ACTIONS

    @property
    def expects_skip(self) -> bool:
        return self.expected_action in SKIP_ACTIONS


def _clean_row(row: dict[str, str]) -> dict[str, str]:
    return {
        field: str(row.get(field, "") or "").strip()
        for field in MANUAL_EXAMPLE_FIELDS
    }


def load_manual_examples(path: Path) -> list[ManualTradeExample]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(MANUAL_EXAMPLE_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"manual_examples.csv missing fields: {sorted(missing)}")
        examples = [ManualTradeExample(**_clean_row(row)) for row in reader]

    for example in examples:
        if not example.symbol:
            raise ValueError("manual example missing symbol")
        if not example.timeframe:
            raise ValueError(f"{example.symbol} manual example missing timeframe")
        if example.expected_action not in TAKE_ACTIONS | SKIP_ACTIONS:
            raise ValueError(
                f"{example.symbol} has unsupported expected_action={example.expected_action!r}"
            )
        if not example.expects_skip and not example.direction:
            raise ValueError(f"{example.symbol} take_trade example missing direction")
    return examples
