from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = PROJECT_ROOT / "scripts" / "optimization_results"
DEFAULT_APPROVED_CANDIDATES_PATH = RESULTS_DIR / "approved_candidates.json"
DEFAULT_DAILY_PERMISSIONS_PATH = RESULTS_DIR / "daily_trade_permissions.json"
DEFAULT_EMERGENCY_STOP_PATH = RESULTS_DIR / "emergency_stop.json"

TRADEABLE = {"TRADE_NORMAL_RISK", "TRADE_REDUCED_RISK"}


class TradingPermissionGuard:
    """Fail-closed guard backed by research candidates and daily trade permissions."""

    def __init__(
        self,
        *,
        approved_candidates_path: str | Path = DEFAULT_APPROVED_CANDIDATES_PATH,
        daily_permissions_path: str | Path = DEFAULT_DAILY_PERMISSIONS_PATH,
        emergency_stop_path: str | Path = DEFAULT_EMERGENCY_STOP_PATH,
        ttl_seconds: int = 30,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.approved_candidates_path = Path(approved_candidates_path)
        self.daily_permissions_path = Path(daily_permissions_path)
        self.emergency_stop_path = Path(emergency_stop_path)
        self.ttl_seconds = ttl_seconds
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._cache: dict[Path, tuple[float, dict[str, Any]]] = {}
        self.rejections: list[dict[str, Any]] = []

    def check(self, payload: dict[str, Any]) -> tuple[bool, str]:
        symbol = self._normalize_symbol(str(payload.get("symbol") or payload.get("ticker") or ""))
        if not symbol:
            return self._reject("", "missing_symbol")
        emergency = self._load_optional(self.emergency_stop_path, {"active": False})
        if emergency.get("active"):
            return self._reject(symbol, "emergency_stop_active")
        approved, reason = self._load_required(self.approved_candidates_path)
        if approved is None:
            return self._reject(symbol, reason)
        daily, reason = self._load_required(self.daily_permissions_path)
        if daily is None:
            return self._reject(symbol, reason)

        candidates = approved.get("candidates")
        if not isinstance(candidates, dict) or symbol not in candidates:
            return self._reject(symbol, "missing_approved_candidate")
        candidate = candidates[symbol]
        permissions = daily.get("permissions")
        if not isinstance(permissions, dict) or symbol not in permissions:
            return self._reject(symbol, "missing_daily_permission")
        permission = permissions[symbol]
        status = str(permission.get("status") or "")
        if status not in TRADEABLE:
            return self._reject(symbol, f"permission_status_not_tradeable:{status or 'missing'}")
        if not self._inside_session(permission):
            return self._reject(symbol, "outside_permission_session")
        expected_hash = str(candidate.get("params_hash") or "")
        actual_hash = str(payload.get("params_hash") or payload.get("strategy_params_hash") or "")
        if not expected_hash or actual_hash != expected_hash:
            return self._reject(symbol, "stale_params_hash")
        requested_risk = self._num(payload.get("risk_per_trade_pct", payload.get("risk_pct", 0.0)))
        allowed_risk = self._num(permission.get("risk_per_trade_pct"))
        if requested_risk > allowed_risk:
            return self._reject(symbol, "requested_risk_exceeds_permission")
        if int(payload.get("trades_today", 0) or 0) >= int(permission.get("max_trades_today", 1) or 1):
            return self._reject(symbol, "max_trades_today_exceeded")
        for key, reason_name in (
            ("account_buffer_safe", "account_daily_loss_buffer_not_safe"),
            ("spread_acceptable", "spread_not_acceptable"),
            ("latency_acceptable", "latency_not_acceptable"),
            ("news_blackout_inactive", "news_blackout_active"),
        ):
            if key in payload and not bool(payload[key]):
                return self._reject(symbol, reason_name)
        payload["_trading_permission_status"] = status
        payload["_trading_permission_risk_pct"] = allowed_risk
        return True, ""

    def _load_required(self, path: Path) -> tuple[dict[str, Any] | None, str]:
        try:
            payload = self._load_optional(path, None)
        except json.JSONDecodeError as exc:
            return None, f"permission_file_invalid:{path.name}:{exc}"
        if payload is None:
            return None, f"permission_file_missing:{path.name}"
        if not isinstance(payload, dict):
            return None, f"permission_file_invalid:{path.name}"
        return payload, ""

    def _load_optional(self, path: Path, default: dict[str, Any] | None) -> dict[str, Any] | None:
        now = time.monotonic()
        cached = self._cache.get(path)
        if cached is not None and now - cached[0] < self.ttl_seconds:
            return cached[1]
        if not path.exists():
            return default
        payload = json.loads(path.read_text())
        if isinstance(payload, dict):
            self._cache[path] = (now, payload)
            return payload
        return default

    def _inside_session(self, permission: dict[str, Any]) -> bool:
        expires_at = permission.get("expires_at")
        if expires_at:
            try:
                if self._now() >= datetime.fromisoformat(str(expires_at).replace("Z", "+00:00")):
                    return False
            except ValueError:
                return False
        session = permission.get("session_utc")
        if not isinstance(session, dict):
            return False
        start = self._num(session.get("start"))
        end = self._num(session.get("end"), 24.0)
        hour = self._now().hour + self._now().minute / 60.0
        if start <= end:
            return start <= hour < end
        return hour >= start or hour < end

    def _reject(self, symbol: str, reason: str) -> tuple[bool, str]:
        self.rejections.append(
            {
                "symbol": symbol,
                "decision": "BLOCK_TRADE",
                "reason": reason,
                "timestamp": self._now().isoformat(),
            }
        )
        return False, reason

    def _now(self) -> datetime:
        now = self._now_provider()
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    @staticmethod
    def _num(value: object, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.upper().strip()
        if ":" in normalized:
            normalized = normalized.split(":", 1)[1]
        return normalized.replace("/", "").replace("-", "")
