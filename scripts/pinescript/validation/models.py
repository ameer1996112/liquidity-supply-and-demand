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
