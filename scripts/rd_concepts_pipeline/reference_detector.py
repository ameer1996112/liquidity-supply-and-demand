from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping, Sequence


APPROACH_LOOKBACK_BARS = 20


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
    departure_active: bool = True
    eligibility_state: EligibilityState = EligibilityState.WAITING_FOR_LIQUIDITY
    eligibility_index: int | None = None
    eligibility_time: str | None = None
    eligibility_reason: str = "WAIT_MINIMUM_LIQUIDITY_CANDLES"
    liquidity_qualified: bool = False
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
            "departure_active": self.departure_active,
            "eligibility_state": self.eligibility_state.value,
            "eligibility_index": self.eligibility_index,
            "eligibility_time": self.eligibility_time,
            "eligibility_reason": self.eligibility_reason,
            "liquidity_qualified": self.liquidity_qualified,
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
class LiquidityLevel:
    direction: Direction
    anchor: Decimal
    anchor_index: int
    near_extreme: Decimal
    near_extreme_index: int
    run_start_index: int
    formed_index: int
    taken_index: int | None = None


@dataclass
class _LiquidityTracker:
    run_count: int = 0
    run_anchor: Decimal | None = None
    run_anchor_index: int | None = None
    run_near_extreme: Decimal | None = None
    run_near_extreme_index: int | None = None
    run_start_index: int | None = None


@dataclass(frozen=True)
class DetectionResult:
    zones: tuple[Zone, ...]
    rejections: tuple[Rejection, ...]
    liquidity_levels: tuple[LiquidityLevel, ...]


class RawZoneDetector:
    def __init__(self) -> None:
        self._bars: list[Bar] = []
        self._zones: list[Zone] = []
        self._rejections: list[Rejection] = []
        self._liquidity_levels: list[LiquidityLevel] = []
        self._pending_liquidity_levels: list[LiquidityLevel] = []
        self._liquidity_trackers = {
            Direction.DEMAND: _LiquidityTracker(),
            Direction.SUPPLY: _LiquidityTracker(),
        }
        self._last_one_candle_liquidity: dict[Direction, tuple[int, int]] = {}
        self._demand_candidate: _Candidate | None = None
        self._supply_candidate: _Candidate | None = None

    @property
    def result(self) -> DetectionResult:
        return DetectionResult(
            tuple(self._zones),
            tuple(self._rejections),
            tuple(self._liquidity_levels),
        )

    def update(self, bar: Bar) -> DetectionResult:
        index = len(self._bars)
        self._bars.append(bar)
        self._update_global_liquidity(index, bar)
        self._update_zone_lifecycle(index, bar)
        self._update_zone_eligibility(index, bar)
        self._update_setup_state(index, bar)

        if bar.bullish:
            self._advance_candidate(self._demand_candidate, index)
            rebased_supply = self._rebase_inside_formation(
                self._supply_candidate, index
            )
            if rebased_supply is None:
                self._interrupt_candidate(self._supply_candidate, index)
                self._supply_candidate = _Candidate(Direction.SUPPLY, index)
            else:
                self._supply_candidate = rebased_supply
        elif bar.bearish:
            self._advance_candidate(self._supply_candidate, index)
            rebased_demand = self._rebase_inside_formation(
                self._demand_candidate, index
            )
            if rebased_demand is None:
                self._interrupt_candidate(self._demand_candidate, index)
                self._demand_candidate = _Candidate(Direction.DEMAND, index)
            else:
                self._demand_candidate = rebased_demand
        else:
            self._interrupt_candidate(self._demand_candidate, index)
            self._interrupt_candidate(self._supply_candidate, index)
            self._demand_candidate = None
            self._supply_candidate = None
        return self.result

    def _rebase_inside_formation(
        self, candidate: _Candidate | None, index: int
    ) -> _Candidate | None:
        if candidate is None or candidate.first_departure_index is None:
            return None
        origin = self._bars[candidate.origin_index]
        bar = self._bars[index]
        if bar.high > origin.high or bar.low < origin.low:
            return None
        distal = bar.low if candidate.direction is Direction.DEMAND else bar.high
        return _Candidate(candidate.direction, index, distal=distal)

    def _advance_candidate(
        self, candidate: _Candidate | None, departure_index: int
    ) -> None:
        if candidate is None:
            return
        departure = self._bars[departure_index]
        origin = self._bars[candidate.origin_index]
        if candidate.first_departure_index is None:
            candidate.first_departure_index = departure_index
            if candidate.direction is Direction.DEMAND:
                candidate.distal = (
                    departure.low
                    if candidate.distal is None
                    else min(candidate.distal, departure.low)
                )
            else:
                candidate.distal = (
                    departure.high
                    if candidate.distal is None
                    else max(candidate.distal, departure.high)
                )
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
        approach = None
        first_index = max(-1, candidate.origin_index - APPROACH_LOOKBACK_BARS - 1)
        for index in range(candidate.origin_index - 1, first_index, -1):
            candidate_bar = self._bars[index]
            if candidate_bar.bullish or candidate_bar.bearish:
                approach = candidate_bar
                break
        if approach is None:
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
            if candidate.direction is Direction.DEMAND:
                top = origin.body_high
                bottom = origin.low
            else:
                top = origin.high
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
            if zone.departure_active:
                same_direction = (
                    bar.bullish
                    if zone.direction is Direction.DEMAND
                    else bar.bearish
                )
                if same_direction:
                    continue
                zone.departure_active = False
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

            primary = self._primary_liquidity(zone)
            if primary is None:
                one_candle = self._last_one_candle_liquidity.get(zone.direction)
                if (
                    one_candle is not None
                    and one_candle[0] > zone.confirmation_index
                    and one_candle[1] == index
                ):
                    zone.eligibility_reason = "REJECT_ONE_CANDLE_LIQUIDITY"
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
                zone.liquidity_qualified = True

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

    def _update_global_liquidity(self, index: int, bar: Bar) -> None:
        if index == 0:
            return
        if bar.bearish:
            self._extend_liquidity_run(Direction.DEMAND, index, bar)
            self._complete_liquidity_run(Direction.SUPPLY, index, bar)
        elif bar.bullish:
            self._extend_liquidity_run(Direction.SUPPLY, index, bar)
            self._complete_liquidity_run(Direction.DEMAND, index, bar)
        else:
            self._complete_liquidity_run(Direction.DEMAND, index, bar)
            self._complete_liquidity_run(Direction.SUPPLY, index, bar)

        still_pending: list[LiquidityLevel] = []
        for level in self._pending_liquidity_levels:
            taken = (
                index > level.formed_index
                and (
                    bar.high > level.anchor
                    if level.direction is Direction.DEMAND
                    else bar.low < level.anchor
                )
            )
            if taken:
                level.taken_index = index
            else:
                still_pending.append(level)
        self._pending_liquidity_levels = still_pending

    def _extend_liquidity_run(
        self, direction: Direction, index: int, bar: Bar
    ) -> None:
        tracker = self._liquidity_trackers[direction]
        if tracker.run_count == 0:
            previous = self._bars[index - 1]
            if direction is Direction.DEMAND:
                prior_is_anchor = previous.high >= bar.high
                tracker.run_anchor = max(previous.high, bar.high)
                tracker.run_near_extreme = bar.low
            else:
                prior_is_anchor = previous.low <= bar.low
                tracker.run_anchor = min(previous.low, bar.low)
                tracker.run_near_extreme = bar.high
            tracker.run_anchor_index = index - 1 if prior_is_anchor else index
            tracker.run_near_extreme_index = index
            tracker.run_start_index = index
        elif direction is Direction.DEMAND:
            if bar.high > tracker.run_anchor:
                tracker.run_anchor = bar.high
                tracker.run_anchor_index = index
            if bar.low < tracker.run_near_extreme:
                tracker.run_near_extreme = bar.low
                tracker.run_near_extreme_index = index
        else:
            if bar.low < tracker.run_anchor:
                tracker.run_anchor = bar.low
                tracker.run_anchor_index = index
            if bar.high > tracker.run_near_extreme:
                tracker.run_near_extreme = bar.high
                tracker.run_near_extreme_index = index
        tracker.run_count += 1

    def _complete_liquidity_run(
        self, direction: Direction, decision_index: int, decision: Bar
    ) -> None:
        tracker = self._liquidity_trackers[direction]
        if tracker.run_count >= 2:
            if direction is Direction.DEMAND:
                decision_extends = decision.low < tracker.run_near_extreme
                near_extreme = min(tracker.run_near_extreme, decision.low)
            else:
                decision_extends = decision.high > tracker.run_near_extreme
                near_extreme = max(tracker.run_near_extreme, decision.high)
            level = LiquidityLevel(
                direction=direction,
                anchor=tracker.run_anchor,
                anchor_index=tracker.run_anchor_index,
                near_extreme=near_extreme,
                near_extreme_index=(
                    decision_index
                    if decision_extends
                    else tracker.run_near_extreme_index
                ),
                run_start_index=tracker.run_start_index,
                formed_index=decision_index - 1,
            )
            self._liquidity_levels.append(level)
            self._pending_liquidity_levels.append(level)
        elif tracker.run_count == 1:
            self._last_one_candle_liquidity[direction] = (
                tracker.run_start_index,
                decision_index,
            )
        tracker.run_count = 0
        tracker.run_anchor = None
        tracker.run_anchor_index = None
        tracker.run_near_extreme = None
        tracker.run_near_extreme_index = None
        tracker.run_start_index = None

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

    def _primary_liquidity(self, zone: Zone) -> LiquidityLevel | None:
        candidates = [
            candidate
            for candidate in self._liquidity_levels
            if candidate.direction is zone.direction
            and candidate.run_start_index > zone.confirmation_index
            and (
                candidate.near_extreme > zone.top
                if zone.direction is Direction.DEMAND
                else candidate.near_extreme < zone.bottom
            )
        ]
        if not candidates:
            return None
        if zone.direction is Direction.DEMAND:
            return min(
                candidates,
                key=lambda candidate: (
                    candidate.near_extreme,
                    -candidate.formed_index,
                ),
            )
        return max(
            candidates,
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
