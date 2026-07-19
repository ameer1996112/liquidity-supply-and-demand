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


class SetupState(str, Enum):
    WAITING_FOR_ELIGIBILITY = "WAITING_FOR_ELIGIBILITY"
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"
    REJECTED = "REJECTED"


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
    liquidity_extreme: Decimal | None = None
    liquidity_formed_index: int | None = None
    route_blocker_zone_id: str | None = None
    setup_state: SetupState = SetupState.WAITING_FOR_ELIGIBILITY
    setup_index: int | None = None
    setup_time: str | None = None
    setup_reason: str = "WAIT_SETUP_ELIGIBILITY"

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
            "liquidity_extreme": (
                str(self.liquidity_extreme)
                if self.liquidity_extreme is not None
                else None
            ),
            "liquidity_formed_index": self.liquidity_formed_index,
            "route_blocker_zone_id": self.route_blocker_zone_id,
            "setup_state": self.setup_state.value,
            "setup_index": self.setup_index,
            "setup_time": self.setup_time,
            "setup_reason": self.setup_reason,
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


@dataclass
class _LiquidityCandidate:
    anchor: Decimal
    near_extreme: Decimal
    formed_index: int
    taken_index: int | None = None


@dataclass
class _LiquidityTracker:
    run_count: int = 0
    run_anchor: Decimal | None = None
    run_near_extreme: Decimal | None = None
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
        self._update_setup_state(index, bar)

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
            if zone.eligibility_state is EligibilityState.EXPIRED:
                continue
            if zone.state is not ZoneState.CONFIRMED_FRESH:
                if zone.eligibility_state is not EligibilityState.ELIGIBLE:
                    zone.eligibility_state = EligibilityState.EXPIRED
                    zone.eligibility_index = index
                    zone.eligibility_time = bar.time
                    zone.eligibility_reason = "EXPIRE_ZONE_NOT_FRESH"
                continue
            if index <= zone.confirmation_index:
                continue

            route_blocker = self._route_blocker(zone, index)
            if route_blocker is not None:
                zone.eligibility_state = EligibilityState.EXPIRED
                zone.eligibility_index = index
                zone.eligibility_time = bar.time
                zone.eligibility_reason = "EXPIRE_OPPOSITE_ZONE_RETRACE"
                zone.route_blocker_zone_id = route_blocker.zone_id
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

            for candidate in tracker.candidates:
                if candidate.taken_index is not None:
                    continue
                taken = (
                    bar.high > candidate.anchor
                    if zone.direction is Direction.DEMAND
                    else bar.low < candidate.anchor
                )
                if taken:
                    candidate.taken_index = index

            primary = self._primary_liquidity(zone, tracker)
            if primary is None:
                continue

            next_state = (
                EligibilityState.WAITING_FOR_LIQUIDITY
                if primary.taken_index is None
                else EligibilityState.ELIGIBLE
            )
            primary_changed = zone.liquidity_formed_index != primary.formed_index
            state_changed = zone.eligibility_state is not next_state
            zone.liquidity_anchor = primary.anchor
            zone.liquidity_extreme = primary.near_extreme
            zone.liquidity_formed_index = primary.formed_index
            if primary_changed or state_changed:
                zone.eligibility_index = index
                zone.eligibility_time = bar.time
            if primary.taken_index is None:
                zone.eligibility_state = next_state
                zone.eligibility_reason = "WAIT_LIQUIDITY_OWN_EXTREME"
            else:
                zone.eligibility_state = next_state
                zone.eligibility_reason = "LIQUIDITY_OWN_EXTREME_TAKEN"

    def _update_setup_state(self, index: int, bar: Bar) -> None:
        for zone in self._zones:
            if zone.setup_state in (SetupState.TRIGGERED, SetupState.REJECTED):
                continue

            if zone.state is ZoneState.INVALIDATED:
                self._transition_setup(
                    zone,
                    SetupState.REJECTED,
                    index,
                    bar.time,
                    "REJECT_TARGET_INVALIDATED_ON_RETURN",
                )
                continue

            if zone.state is ZoneState.TAPPED:
                blocker = self._same_bar_route_blocker(zone, index)
                if blocker is not None:
                    zone.eligibility_state = EligibilityState.EXPIRED
                    zone.eligibility_index = index
                    zone.eligibility_time = bar.time
                    zone.eligibility_reason = "EXPIRE_OPPOSITE_ZONE_RETRACE"
                    zone.route_blocker_zone_id = blocker.zone_id
                    self._transition_setup(
                        zone,
                        SetupState.REJECTED,
                        index,
                        bar.time,
                        "REJECT_AMBIGUOUS_SAME_BAR_ROUTE",
                    )
                elif zone.eligibility_state is EligibilityState.ELIGIBLE:
                    self._transition_setup(
                        zone,
                        SetupState.TRIGGERED,
                        index,
                        bar.time,
                        "TRIGGER_FIRST_FRESH_TAP_AFTER_LIQUIDITY",
                    )
                else:
                    self._transition_setup(
                        zone,
                        SetupState.REJECTED,
                        index,
                        bar.time,
                        "REJECT_TARGET_TAP_WITHOUT_ELIGIBILITY",
                    )
                continue

            if zone.eligibility_state is EligibilityState.EXPIRED:
                self._transition_setup(
                    zone,
                    SetupState.REJECTED,
                    index,
                    bar.time,
                    zone.eligibility_reason,
                )
            elif zone.eligibility_state is EligibilityState.ELIGIBLE:
                if zone.setup_state is not SetupState.ARMED:
                    self._transition_setup(
                        zone,
                        SetupState.ARMED,
                        index,
                        bar.time,
                        "ARM_SETUP_AFTER_LIQUIDITY",
                    )
            elif zone.setup_state is SetupState.ARMED:
                self._transition_setup(
                    zone,
                    SetupState.WAITING_FOR_ELIGIBILITY,
                    index,
                    bar.time,
                    "WAIT_SETUP_ELIGIBILITY",
                )

    @staticmethod
    def _transition_setup(
        zone: Zone,
        state: SetupState,
        index: int,
        time: str,
        reason: str,
    ) -> None:
        zone.setup_state = state
        zone.setup_index = index
        zone.setup_time = time
        zone.setup_reason = reason

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
            tracker.run_near_extreme = (
                bar.low
                if zone.direction is Direction.DEMAND
                else bar.high
            )
        elif zone.direction is Direction.DEMAND:
            tracker.run_anchor = max(tracker.run_anchor, bar.high)
            tracker.run_near_extreme = min(tracker.run_near_extreme, bar.low)
        else:
            tracker.run_anchor = min(tracker.run_anchor, bar.low)
            tracker.run_near_extreme = max(tracker.run_near_extreme, bar.high)
        tracker.run_count += 1
        if zone.eligibility_state is not EligibilityState.ELIGIBLE:
            zone.eligibility_reason = "WAIT_MINIMUM_LIQUIDITY_CANDLES"

    def _complete_liquidity_run(
        self, zone: Zone, tracker: _LiquidityTracker, decision_index: int
    ) -> None:
        if tracker.run_count >= 2:
            decision = self._bars[decision_index]
            near_extreme = (
                min(tracker.run_near_extreme, decision.low)
                if zone.direction is Direction.DEMAND
                else max(tracker.run_near_extreme, decision.high)
            )
            tracker.candidates.append(
                _LiquidityCandidate(
                    anchor=tracker.run_anchor,
                    near_extreme=near_extreme,
                    formed_index=decision_index - 1,
                )
            )
            zone.eligibility_reason = "WAIT_LIQUIDITY_OWN_EXTREME"
        elif tracker.run_count == 1:
            zone.eligibility_reason = "REJECT_ONE_CANDLE_LIQUIDITY"
        tracker.run_count = 0
        tracker.run_anchor = None
        tracker.run_near_extreme = None

    def _route_blocker(self, zone: Zone, index: int) -> Zone | None:
        if zone.eligibility_state is not EligibilityState.ELIGIBLE:
            return None
        if zone.eligibility_index is None or index <= zone.eligibility_index:
            return None

        return self._opposite_tapped_route_blocker(zone, index)

    def _same_bar_route_blocker(self, zone: Zone, index: int) -> Zone | None:
        if zone.eligibility_state is not EligibilityState.ELIGIBLE:
            return None
        if zone.eligibility_index is None or index <= zone.eligibility_index:
            return None
        if zone.state is not ZoneState.TAPPED or zone.state_index != index:
            return None

        return self._opposite_tapped_route_blocker(zone, index)

    def _opposite_tapped_route_blocker(
        self, zone: Zone, index: int
    ) -> Zone | None:

        blockers = [
            candidate
            for candidate in self._zones
            if candidate.direction is not zone.direction
            and candidate.state is ZoneState.TAPPED
            and candidate.state_index == index
            and (
                candidate.bottom > zone.top
                if zone.direction is Direction.DEMAND
                else candidate.top < zone.bottom
            )
        ]
        if not blockers:
            return None
        if zone.direction is Direction.DEMAND:
            return min(blockers, key=lambda candidate: candidate.bottom - zone.top)
        return min(blockers, key=lambda candidate: zone.bottom - candidate.top)

    @staticmethod
    def _primary_liquidity(
        zone: Zone, tracker: _LiquidityTracker
    ) -> _LiquidityCandidate | None:
        if not tracker.candidates:
            return None
        if zone.direction is Direction.DEMAND:
            return min(
                tracker.candidates,
                key=lambda candidate: (
                    candidate.near_extreme,
                    -candidate.formed_index,
                ),
            )
        return max(
            tracker.candidates,
            key=lambda candidate: (
                candidate.near_extreme,
                candidate.formed_index,
            ),
        )


def detect_zones(bars: Sequence[Bar]) -> DetectionResult:
    detector = RawZoneDetector()
    for bar in bars:
        detector.update(bar)
    return detector.result
