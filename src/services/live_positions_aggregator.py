from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

from src.adapters.execution.router import resolve_profile_adapter

logger = logging.getLogger(__name__)

_ELIGIBLE_VENUES = {"metaapi", "metaapi_mt5", "mt5", "ctrader"}


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_venue(value: Any) -> str:
    venue = str(value or "").strip().lower()
    if venue == "metaapi":
        return "metaapi_mt5"
    return venue


def _has_adapter_credentials(row: dict[str, Any], venue: str) -> bool:
    token = str(row.get("token") or "").strip()
    account_id = str(row.get("meta_api_account_id") or row.get("account_id") or "").strip()

    if venue in {"metaapi_mt5", "mt5", "ctrader"}:
        return bool(token and account_id)

    return False


def _normalize_side(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if "BUY" in raw:
        return "buy"
    if "SELL" in raw:
        return "sell"
    return raw.lower()


@dataclass(frozen=True)
class LiveBrokerProfile:
    id: int
    name: str
    venue: str
    run_mode: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class LivePosition:
    profile_id: int
    account_name: str
    venue: str
    broker_position_id: str
    symbol: str
    side: str
    size: Optional[float]
    entry_price: Optional[float]
    current_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    profit: Optional[float]
    swap: Optional[float]
    commission: Optional[float]
    opened_at: Optional[str]
    comment: Optional[str]


@dataclass(frozen=True)
class LiveAccountStatus:
    profile_id: int
    account_name: str
    venue: str
    balance: Optional[float]
    equity: Optional[float]
    margin: Optional[float]
    free_margin: Optional[float]
    margin_level: Optional[float]
    open_positions: int


@dataclass(frozen=True)
class AggregationError:
    profile_id: int
    account_name: str
    venue: str
    operation: str
    message: str


@dataclass(frozen=True)
class PositionsAggregationResult:
    positions: list[LivePosition]
    errors: list[AggregationError]
    healthy_profiles: int
    failed_profiles: int


@dataclass(frozen=True)
class AccountStatusAggregationResult:
    accounts: list[LiveAccountStatus]
    totals: dict[str, float]
    errors: list[AggregationError]
    healthy_profiles: int
    failed_profiles: int


class LivePositionsAggregator:
    def __init__(
        self,
        supabase_client: Any,
        adapter_resolver: Callable[[dict[str, Any]], Any] = resolve_profile_adapter,
    ) -> None:
        self.client = supabase_client
        self.adapter_resolver = adapter_resolver
        self._adapter_cache: dict[int, Any] = {}
        self._open_positions_cache: dict[int, list[dict[str, Any]]] = {}

    def load_eligible_profiles(self) -> list[LiveBrokerProfile]:
        response = (
            self.client.table("broker_profiles")
            .select("*")
            .eq("is_active", True)
            .eq("selected_for_trading", True)
            .eq("run_mode", "LIVE")
            .execute()
        )

        rows = response.data or []
        profiles: list[LiveBrokerProfile] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            venue = _normalize_venue(row.get("venue"))
            if venue not in _ELIGIBLE_VENUES:
                continue
            if not _has_adapter_credentials(row, venue):
                logger.info(
                    "Skipping live aggregation for profile %s (%s): adapter credentials incomplete",
                    row.get("name") or row.get("id"),
                    row.get("id"),
                )
                continue
            profile_id = row.get("id")
            if profile_id is None:
                continue
            try:
                normalized_id = int(profile_id)
            except (TypeError, ValueError):
                continue
            profiles.append(
                LiveBrokerProfile(
                    id=normalized_id,
                    name=str(row.get("name") or f"Profile {normalized_id}"),
                    venue=venue,
                    run_mode=str(row.get("run_mode") or "").upper(),
                    raw=dict(row),
                )
            )

        profiles.sort(key=lambda profile: profile.id)
        return profiles

    def aggregate_open_positions(
        self,
        profiles: Optional[Iterable[LiveBrokerProfile]] = None,
    ) -> PositionsAggregationResult:
        resolved_profiles = list(profiles) if profiles is not None else self.load_eligible_profiles()
        positions: list[LivePosition] = []
        errors: list[AggregationError] = []
        healthy_profiles = 0

        for profile in resolved_profiles:
            try:
                adapter = self._resolve_adapter(profile)
                if not hasattr(adapter, "get_open_positions"):
                    raise ValueError("Adapter does not support open positions")

                raw_positions = self._load_open_positions(profile, adapter)
                if not isinstance(raw_positions, list):
                    raise ValueError("Open positions payload must be a list")

                for payload in raw_positions:
                    if isinstance(payload, dict):
                        positions.append(self._normalize_position(profile, payload))
                healthy_profiles += 1
            except Exception as exc:  # pragma: no cover - exercised via tests
                logger.warning(
                    "Failed to aggregate live positions for profile %s (%s): %s",
                    profile.name,
                    profile.id,
                    exc,
                )
                errors.append(self._build_error(profile, "positions", exc))

        return PositionsAggregationResult(
            positions=positions,
            errors=errors,
            healthy_profiles=healthy_profiles,
            failed_profiles=len(errors),
        )

    def aggregate_account_status(
        self,
        profiles: Optional[Iterable[LiveBrokerProfile]] = None,
    ) -> AccountStatusAggregationResult:
        resolved_profiles = list(profiles) if profiles is not None else self.load_eligible_profiles()
        accounts: list[LiveAccountStatus] = []
        errors: list[AggregationError] = []
        healthy_profiles = 0
        totals = {
            "balance": 0.0,
            "equity": 0.0,
            "margin": 0.0,
            "free_margin": 0.0,
            "open_positions": 0.0,
        }

        for profile in resolved_profiles:
            try:
                adapter = self._resolve_adapter(profile)
                status_payload = self._load_account_status(adapter)
                account = self._normalize_account_status(profile, adapter, status_payload)
                accounts.append(account)
                totals["balance"] += account.balance or 0.0
                totals["equity"] += account.equity or 0.0
                totals["margin"] += account.margin or 0.0
                totals["free_margin"] += account.free_margin or 0.0
                totals["open_positions"] += float(account.open_positions)
                healthy_profiles += 1
            except Exception as exc:  # pragma: no cover - exercised via tests
                logger.warning(
                    "Failed to aggregate account status for profile %s (%s): %s",
                    profile.name,
                    profile.id,
                    exc,
                )
                errors.append(self._build_error(profile, "account_status", exc))

        return AccountStatusAggregationResult(
            accounts=accounts,
            totals=totals,
            errors=errors,
            healthy_profiles=healthy_profiles,
            failed_profiles=len(errors),
        )

    def _resolve_adapter(self, profile: LiveBrokerProfile) -> Any:
        if profile.id in self._adapter_cache:
            return self._adapter_cache[profile.id]

        adapter = self.adapter_resolver(dict(profile.raw))
        if adapter is None:
            raise ValueError("No adapter available for profile")
        self._adapter_cache[profile.id] = adapter
        return adapter

    def _load_open_positions(
        self,
        profile: LiveBrokerProfile,
        adapter: Any,
    ) -> list[dict[str, Any]]:
        if profile.id in self._open_positions_cache:
            return self._open_positions_cache[profile.id]

        positions = adapter.get_open_positions() or []
        positions_fetch_error = getattr(adapter, "last_positions_fetch_error", None)
        if positions_fetch_error:
            raise ValueError(f"Broker positions unavailable ({positions_fetch_error})")
        if isinstance(positions, list):
            self._open_positions_cache[profile.id] = positions
        return positions

    def _load_account_status(self, adapter: Any) -> dict[str, Any]:
        if hasattr(adapter, "get_account_status"):
            payload = adapter.get_account_status()
        elif hasattr(adapter, "get_account_information"):
            payload = adapter.get_account_information()
        else:
            raise ValueError("Adapter does not support account status")

        if not isinstance(payload, dict):
            raise ValueError("Account status payload must be a dict")
        if payload.get("connectionStatus") == "circuit_breaker_open":
            raise ValueError("Broker account status unavailable (circuit_breaker_open)")
        return payload

    def _normalize_position(self, profile: LiveBrokerProfile, payload: dict[str, Any]) -> LivePosition:
        return LivePosition(
            profile_id=profile.id,
            account_name=profile.name,
            venue=profile.venue,
            broker_position_id=str(
                _first_present(
                    payload.get("id"),
                    payload.get("positionId"),
                    payload.get("broker_position_id"),
                )
                or ""
            ),
            symbol=str(_first_present(payload.get("symbol"), payload.get("symbolName")) or ""),
            side=_normalize_side(
                _first_present(payload.get("type"), payload.get("side"), payload.get("tradeSide"))
            ),
            size=_to_float(
                _first_present(
                    payload.get("volume"),
                    payload.get("size"),
                    payload.get("lotSize"),
                    payload.get("quantity"),
                )
            ),
            entry_price=_to_float(
                _first_present(payload.get("openPrice"), payload.get("entryPrice"), payload.get("price"))
            ),
            current_price=_to_float(
                _first_present(payload.get("currentPrice"), payload.get("markPrice"), payload.get("current_price"))
            ),
            stop_loss=_to_float(_first_present(payload.get("sl"), payload.get("stopLoss"))),
            take_profit=_to_float(_first_present(payload.get("tp"), payload.get("takeProfit"))),
            profit=_to_float(
                _first_present(
                    payload.get("profit"),
                    payload.get("unrealizedProfit"),
                    payload.get("netUnrealizedPnL"),
                )
            ),
            swap=_to_float(payload.get("swap")),
            commission=_to_float(payload.get("commission")),
            opened_at=str(
                _first_present(
                    payload.get("time"),
                    payload.get("openTime"),
                    payload.get("createdAt"),
                )
                or ""
            )
            or None,
            comment=str(payload.get("comment")) if payload.get("comment") not in (None, "") else None,
        )

    def _normalize_account_status(
        self,
        profile: LiveBrokerProfile,
        adapter: Any,
        payload: dict[str, Any],
    ) -> LiveAccountStatus:
        return LiveAccountStatus(
            profile_id=profile.id,
            account_name=profile.name,
            venue=profile.venue,
            balance=_to_float(payload.get("balance")),
            equity=_to_float(payload.get("equity")),
            margin=_to_float(payload.get("margin")),
            free_margin=_to_float(_first_present(payload.get("freeMargin"), payload.get("free_margin"))),
            margin_level=_to_float(_first_present(payload.get("marginLevel"), payload.get("margin_level"))),
            open_positions=self._extract_open_positions_count(profile, adapter, payload),
        )

    def _extract_open_positions_count(
        self,
        profile: LiveBrokerProfile,
        adapter: Any,
        payload: dict[str, Any],
    ) -> int:
        embedded = payload.get("open_positions")
        if embedded is None:
            embedded = payload.get("positions")

        if isinstance(embedded, list):
            return len(embedded)
        if embedded not in (None, ""):
            try:
                return int(embedded)
            except (TypeError, ValueError):
                pass

        if hasattr(adapter, "get_open_positions"):
            positions = self._load_open_positions(profile, adapter)
            if isinstance(positions, list):
                return len(positions)

        return 0

    def _build_error(
        self,
        profile: LiveBrokerProfile,
        operation: str,
        exc: Exception,
    ) -> AggregationError:
        return AggregationError(
            profile_id=profile.id,
            account_name=profile.name,
            venue=profile.venue,
            operation=operation,
            message=str(exc),
        )
