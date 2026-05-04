from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_APPROVED_PAIRS_PATH = PROJECT_ROOT / "scripts" / "optimization_results" / "approved_pairs.json"

_ALLOWED_STATUSES = {"TRADE_NORMAL_RISK", "TRADE_REDUCED_RISK", "WATCH_ONLY"}
_RISK_MULTIPLIERS = {
    "TRADE_NORMAL_RISK": 1.0,
    "TRADE_REDUCED_RISK": 0.5,
    "WATCH_ONLY": 0.25,
}


class ApprovedPairsGuard:
    """Fail-closed allow-list guard backed by optimizer-approved pair discovery."""

    def __init__(
        self,
        path: str | Path = DEFAULT_APPROVED_PAIRS_PATH,
        *,
        ttl_seconds: int = 300,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path)
        self.ttl_seconds = ttl_seconds
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._cached_payload: dict | None = None
        self._loaded_at_monotonic = 0.0

    def check(self, payload: dict) -> tuple[bool, str]:
        symbol = self._normalize_symbol(str(payload.get("symbol") or payload.get("ticker") or ""))
        if not symbol:
            return False, "APPROVED_PAIR_MISSING_SYMBOL: signal did not include a symbol"

        approved, reason = self._load()
        if approved is None:
            return False, reason

        pairs = approved.get("pairs")
        if not isinstance(pairs, dict):
            return False, f"APPROVED_PAIR_FILE_INVALID: {self.path} missing pairs object"

        entry = pairs.get(symbol)
        if not isinstance(entry, dict):
            return False, f"APPROVED_PAIR_BLOCKED: {symbol} is not approved for trading"

        status = str(entry.get("status") or "").upper()
        if status not in _ALLOWED_STATUSES:
            return False, f"APPROVED_PAIR_STATUS_BLOCKED: {symbol} has status {status or 'UNKNOWN'}"

        if self._is_expired(entry):
            return False, f"APPROVED_PAIR_EXPIRED: {symbol} approval expired on {entry.get('approved_until')}"

        if not self._inside_session(entry, payload):
            session = entry.get("session_utc") or {}
            return (
                False,
                f"APPROVED_PAIR_SESSION_BLOCKED: {symbol} outside approved session "
                f"{session.get('start')}..{session.get('end')} UTC",
            )

        payload["_approved_pair_status"] = status
        payload["_approved_pair_risk_multiplier"] = _RISK_MULTIPLIERS[status]
        return True, ""

    def _load(self) -> tuple[dict | None, str]:
        now = time.monotonic()
        if self._cached_payload is not None and now - self._loaded_at_monotonic < self.ttl_seconds:
            return self._cached_payload, ""
        try:
            payload = json.loads(self.path.read_text())
        except FileNotFoundError:
            return None, f"APPROVED_PAIR_FILE_MISSING: {self.path}"
        except json.JSONDecodeError as exc:
            return None, f"APPROVED_PAIR_FILE_INVALID: {self.path} is not valid JSON ({exc})"
        if not isinstance(payload, dict):
            return None, f"APPROVED_PAIR_FILE_INVALID: {self.path} must contain a JSON object"
        self._cached_payload = payload
        self._loaded_at_monotonic = now
        return payload, ""

    def _is_expired(self, entry: dict) -> bool:
        approved_until = entry.get("approved_until")
        if not approved_until:
            return True
        try:
            expiry = datetime.fromisoformat(str(approved_until)).date()
        except ValueError:
            return True
        return self._now().date() > expiry

    def _inside_session(self, entry: dict, payload: dict) -> bool:
        session = entry.get("session_utc")
        if not isinstance(session, dict):
            return False
        try:
            start = float(session["start"])
            end = float(session["end"])
        except (KeyError, TypeError, ValueError):
            return False
        current = self._signal_time(payload)
        hour = current.hour + current.minute / 60.0 + current.second / 3600.0
        if start <= end:
            return start <= hour < end
        return hour >= start or hour < end

    def _signal_time(self, payload: dict) -> datetime:
        raw = payload.get("bar_time") or payload.get("timestamp")
        if isinstance(raw, str) and raw:
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except ValueError:
                pass
        return self._now()

    def _now(self) -> datetime:
        now = self._now_provider()
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.upper().strip()
        if ":" in normalized:
            normalized = normalized.split(":", 1)[1]
        return normalized.replace("/", "").replace("-", "")
