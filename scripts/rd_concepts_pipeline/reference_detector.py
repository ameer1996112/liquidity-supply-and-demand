from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping, Sequence


class Direction(str, Enum):
    DEMAND = "DEMAND"
    SUPPLY = "SUPPLY"


class Formation(str, Enum):
    REVERSAL = "REVERSAL"
    CONTINUATION = "CONTINUATION"


class Geometry(str, Enum):
    STANDARD = "STANDARD"
    ACCURACY = "ACCURACY"


class ZoneState(str, Enum):
    CONFIRMED_FRESH = "CONFIRMED_FRESH"
    TAPPED = "TAPPED"
    INVALIDATED = "INVALIDATED"


class EligibilityState(str, Enum):
    WAITING_FOR_LIQUIDITY = "WAITING_FOR_LIQUIDITY"
    ELIGIBLE = "ELIGIBLE"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class Bar:
    time: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    def __post_init__(self) -> None:
        if self.high < max(self.open, self.close):
            raise ValueError("bar high is below its body")
        if self.low > min(self.open, self.close):
            raise ValueError("bar low is above its body")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> Bar:
        return cls(
            time=str(mapping["time"]),
            open=Decimal(str(mapping["open"])),
            high=Decimal(str(mapping["high"])),
            low=Decimal(str(mapping["low"])),
            close=Decimal(str(mapping["close"])),
        )

    @property
    def bullish(self) -> bool:
        return self.close > self.open

    @property
    def bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_high(self) -> Decimal:
        return max(self.open, self.close)

    @property
    def body_low(self) -> Decimal:
        return min(self.open, self.close)


@dataclass
class Zone:
    zone_id: str
    direction: Direction
    formation: Formation
    geometry: Geometry
    origin_index: int
    origin_time: str
    confirmation_index: int
    confirmation_time: str
    top: Decimal
    bottom: Decimal
    state: ZoneState = ZoneState.CONFIRMED_FRESH
    state_index: int | None = None
    state_time: str | None = None
    reason: str = "CONFIRM_CLOSE_BEYOND_ORIGIN"
    eligibility_state: EligibilityState = EligibilityState.WAITING_FOR_LIQUIDITY
    eligibility_index: int | None = None
    eligibility_time: str | None = None
    eligibility_reason: str = "WAIT_MINIMUM_LIQUIDITY_CANDLES"
    liquidity_anchor: Decimal | None = None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "direction": self.direction.value,
            "formation": self.formation.value,
            "geometry": self.geometry.value,
            "origin_index": self.origin_index,
            "origin_time": self.origin_time,
            "confirmation_index": self.confirmation_index,
            "confirmation_time": self.confirmation_time,
            "top": str(self.top),
            "bottom": str(self.bottom),
            "state": self.state.value,
            "state_index": self.state_index,
            "state_time": self.state_time,
            "reason": self.reason,
            "eligibility_state": self.eligibility_state.value,
            "eligibility_index": self.eligibility_index,
            "eligibility_time": self.eligibility_time,
            "eligibility_reason": self.eligibility_reason,
            "liquidity_anchor": (
                str(self.liquidity_anchor)
                if self.liquidity_anchor is not None
                else None
            ),
        }


@dataclass(frozen=True)
class Rejection:
    direction: Direction
    origin_index: int
    origin_time: str
    decision_index: int
    decision_time: str
    reason: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "direction": self.direction.value,
            "origin_index": self.origin_index,
            "origin_time": self.origin_time,
            "decision_index": self.decision_index,
            "rejection_time": self.decision_time,
            "reason": self.reason,
        }


@dataclass
class _Candidate:
    direction: Direction
    origin_index: int
    first_departure_index: int | None = None
    distal: Decimal | None = None


@dataclass(frozen=True)
class _LiquidityCandidate:
    anchor: Decimal
    formed_index: int


@dataclass
class _LiquidityTracker:
    run_count: int = 0
    run_anchor: Decimal | None = None
    candidates: list[_LiquidityCandidate] = field(default_factory=list)


@dataclass(frozen=True)
class DetectionResult:
    zones: tuple[Zone, ...]
    rejections: tuple[Rejection, ...]


class RawZoneDetector:
    def __init__(self) -> None:
        self._bars: list[Bar] = []
        self._zones: list[Zone] = []
        self._rejections: list[Rejection] = []
        self._liquidity_trackers: dict[str, _LiquidityTracker] = {}
        self._demand_candidate: _Candidate | None = None
        self._supply_candidate: _Candidate | None = None

    @property
    def result(self) -> DetectionResult:
        return DetectionResult(tuple(self._zones), tuple(self._rejections))

    def update(self, bar: Bar) -> DetectionResult:
        index = len(self._bars)
        self._bars.append(bar)
        self._update_zone_lifecycle(index, bar)
        self._update_zone_eligibility(index, bar)

        if bar.bullish:
            self._advance_candidate(self._demand_candidate, index)
            self._interrupt_candidate(self._supply_candidate, index)
            self._supply_candidate = _Candidate(Direction.SUPPLY, index)
        elif bar.bearish:
            self._advance_candidate(self._supply_candidate, index)
            self._interrupt_candidate(self._demand_candidate, index)
            self._demand_candidate = _Candidate(Direction.DEMAND, index)
        else:
            self._interrupt_candidate(self._demand_candidate, index)
            self._interrupt_candidate(self._supply_candidate, index)
            self._demand_candidate = None
            self._supply_candidate = None
        return self.result

    def _advance_candidate(
        self, candidate: _Candidate | None, departure_index: int
    ) -> None:
        if candidate is None:
            return
        departure = self._bars[departure_index]
        origin = self._bars[candidate.origin_index]
        if candidate.first_departure_index is None:
            candidate.first_departure_index = departure_index
            candidate.distal = departure.low if candidate.direction is Direction.DEMAND else departure.high
        elif candidate.direction is Direction.DEMAND:
            candidate.distal = min(candidate.distal, departure.low)
        else:
            candidate.distal = max(candidate.distal, departure.high)

        confirmed = (
            departure.close > origin.high
            if candidate.direction is Direction.DEMAND
            else departure.close < origin.low
        )
        if not confirmed:
            return

        formation = self._classify_formation(candidate)
        if formation is None:
            self._reject(candidate, departure_index, "REJECT_UNKNOWN_APPROACH")
        else:
            self._zones.append(
                self._confirmed_zone(candidate, departure_index, formation)
            )
        if candidate.direction is Direction.DEMAND:
            self._demand_candidate = None
        else:
            self._supply_candidate = None

    def _interrupt_candidate(
        self, candidate: _Candidate | None, decision_index: int
    ) -> None:
        if candidate is None:
            return
        if candidate.first_departure_index is not None:
            self._reject(candidate, decision_index, "REJECT_FORMATION_INTERRUPTED")
        if candidate.direction is Direction.DEMAND:
            self._demand_candidate = None
        else:
            self._supply_candidate = None

    def _classify_formation(self, candidate: _Candidate) -> Formation | None:
        if candidate.origin_index == 0:
            return None
        approach = self._bars[candidate.origin_index - 1]
        if not approach.bullish and not approach.bearish:
            return None
        if candidate.direction is Direction.DEMAND:
            return Formation.CONTINUATION if approach.bullish else Formation.REVERSAL
        return Formation.CONTINUATION if approach.bearish else Formation.REVERSAL

    def _confirmed_zone(
        self,
        candidate: _Candidate,
        confirmation_index: int,
        formation: Formation,
    ) -> Zone:
        origin = self._bars[candidate.origin_index]
        first_departure = self._bars[candidate.first_departure_index]
        if candidate.direction is Direction.DEMAND:
            accuracy = origin.high > first_departure.high
        else:
            accuracy = origin.low < first_departure.low
        geometry = Geometry.ACCURACY if accuracy else Geometry.STANDARD

        if geometry is Geometry.ACCURACY:
            top = origin.body_high
            bottom = origin.body_low
        else:
            top = origin.high
            bottom = origin.low
        if candidate.direction is Direction.DEMAND:
            bottom = min(bottom, candidate.distal)
        else:
            top = max(top, candidate.distal)

        direction_code = "D" if candidate.direction is Direction.DEMAND else "S"
        return Zone(
            zone_id=(
                f"{direction_code}:{origin.time}:{self._bars[confirmation_index].time}:"
                f"{geometry.value}"
            ),
            direction=candidate.direction,
            formation=formation,
            geometry=geometry,
            origin_index=candidate.origin_index,
            origin_time=origin.time,
            confirmation_index=confirmation_index,
            confirmation_time=self._bars[confirmation_index].time,
            top=top,
            bottom=bottom,
        )

    def _reject(
        self, candidate: _Candidate, decision_index: int, reason: str
    ) -> None:
        origin = self._bars[candidate.origin_index]
        decision = self._bars[decision_index]
        self._rejections.append(
            Rejection(
                direction=candidate.direction,
                origin_index=candidate.origin_index,
                origin_time=origin.time,
                decision_index=decision_index,
                decision_time=decision.time,
                reason=reason,
            )
        )

    def _update_zone_lifecycle(self, index: int, bar: Bar) -> None:
        for zone in self._zones:
            if zone.state is not ZoneState.CONFIRMED_FRESH:
                continue
            if index <= zone.confirmation_index:
                continue
            overlaps = bar.high >= zone.bottom and bar.low <= zone.top
            if not overlaps:
                continue
            invalidated = (
                bar.close < zone.bottom
                if zone.direction is Direction.DEMAND
                else bar.close > zone.top
            )
            zone.state = ZoneState.INVALIDATED if invalidated else ZoneState.TAPPED
            zone.state_index = index
            zone.state_time = bar.time
            zone.reason = (
                "INVALIDATE_CLOSE_BEYOND_DISTAL"
                if invalidated
                else "TAP_POST_CONFIRM_OVERLAP"
            )

    def _update_zone_eligibility(self, index: int, bar: Bar) -> None:
        for zone in self._zones:
            if zone.eligibility_state is EligibilityState.ELIGIBLE:
                continue
            if zone.state is not ZoneState.CONFIRMED_FRESH:
                zone.eligibility_state = EligibilityState.EXPIRED
                zone.eligibility_index = index
                zone.eligibility_time = bar.time
                zone.eligibility_reason = "EXPIRE_ZONE_NOT_FRESH"
                continue
            if index <= zone.confirmation_index:
                continue

            tracker = self._liquidity_trackers.setdefault(
                zone.zone_id, _LiquidityTracker()
            )
            required_candle = (
                bar.bearish
                if zone.direction is Direction.DEMAND
                else bar.bullish
            )
            if required_candle:
                self._extend_liquidity_run(zone, tracker, index, bar)
            else:
                self._complete_liquidity_run(zone, tracker, index)

            broken = [
                candidate
                for candidate in tracker.candidates
                if (
                    bar.high > candidate.anchor
                    if zone.direction is Direction.DEMAND
                    else bar.low < candidate.anchor
                )
            ]
            if not broken:
                continue

            candidate = broken[-1]
            zone.eligibility_state = EligibilityState.ELIGIBLE
            zone.eligibility_index = index
            zone.eligibility_time = bar.time
            zone.eligibility_reason = "LIQUIDITY_OWN_EXTREME_TAKEN"
            zone.liquidity_anchor = candidate.anchor

    def _extend_liquidity_run(
        self,
        zone: Zone,
        tracker: _LiquidityTracker,
        index: int,
        bar: Bar,
    ) -> None:
        if tracker.run_count == 0:
            previous = self._bars[index - 1]
            tracker.run_anchor = (
                max(previous.high, bar.high)
                if zone.direction is Direction.DEMAND
                else min(previous.low, bar.low)
            )
        elif zone.direction is Direction.DEMAND:
            tracker.run_anchor = max(tracker.run_anchor, bar.high)
        else:
            tracker.run_anchor = min(tracker.run_anchor, bar.low)
        tracker.run_count += 1
        zone.eligibility_reason = "WAIT_MINIMUM_LIQUIDITY_CANDLES"

    @staticmethod
    def _complete_liquidity_run(
        zone: Zone, tracker: _LiquidityTracker, decision_index: int
    ) -> None:
        if tracker.run_count >= 2:
            tracker.candidates.append(
                _LiquidityCandidate(
                    anchor=tracker.run_anchor,
                    formed_index=decision_index - 1,
                )
            )
            zone.eligibility_reason = "WAIT_LIQUIDITY_OWN_EXTREME"
        elif tracker.run_count == 1:
            zone.eligibility_reason = "REJECT_ONE_CANDLE_LIQUIDITY"
        tracker.run_count = 0
        tracker.run_anchor = None


def detect_zones(bars: Sequence[Bar]) -> DetectionResult:
    detector = RawZoneDetector()
    for bar in bars:
        detector.update(bar)
    return detector.result
