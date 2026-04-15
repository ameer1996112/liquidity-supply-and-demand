from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Literal


Venue = Literal["metaapi_mt5", "ctrader", "binance", "bybit"]
Mode = Literal["prop", "personal"]
AssetClass = Literal["forex_cfd", "crypto"]


@dataclass(frozen=True)
class AccountProfile:
    name: str
    venue: Venue
    mode: Mode
    asset_class: AssetClass

    # MetaApi/MT5
    meta_api_account_id: str = ""
    token: str = ""
    region: str = ""

    # Crypto (Binance/Bybit)
    api_key: str = ""
    api_secret: str = ""
    subaccount: str = ""

    # Risk & routing
    risk_pct: float = 1.0
    max_positions: int = 3

    @staticmethod
    def from_dict(row: Dict[str, Any]) -> "AccountProfile":
        name = str(row.get("name") or "profile").strip() or "profile"

        venue_raw = str(row.get("venue") or "").strip().lower()
        venue_raw = venue_raw or "metaapi_mt5"
        if venue_raw == "metaapi":
            venue_raw = "metaapi_mt5"
        if venue_raw not in {"metaapi_mt5", "ctrader", "binance", "bybit"}:
            raise ValueError(f"Unknown venue: {venue_raw}")

        mode_raw = str(row.get("mode") or "personal").strip().lower()
        if mode_raw not in {"prop", "personal"}:
            raise ValueError(f"Unknown mode: {mode_raw}")

        asset_raw = str(
            row.get("asset_class")
            or ("crypto" if venue_raw in {"binance", "bybit"} else "forex_cfd")
        ).strip().lower()
        if asset_raw not in {"forex_cfd", "crypto"}:
            raise ValueError(f"Unknown asset_class: {asset_raw}")

        return AccountProfile(
            name=name,
            venue=venue_raw,  # type: ignore[arg-type]
            mode=mode_raw,  # type: ignore[arg-type]
            asset_class=asset_raw,  # type: ignore[arg-type]
            meta_api_account_id=str(
                row.get("meta_api_account_id") or row.get("account_id") or ""
            ).strip(),
            token=str(row.get("token") or "").strip(),
            region=str(row.get("region") or "").strip(),
            api_key=str(row.get("api_key") or "").strip(),
            api_secret=str(row.get("api_secret") or "").strip(),
            subaccount=str(row.get("subaccount") or "").strip(),
            risk_pct=float(row.get("risk_pct", 1.0)),
            max_positions=int(row.get("max_positions", 3)),
        )


def coerce_profiles(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize profile dicts into a multi-venue shape while keeping existing keys.

    This function is intentionally non-destructive:
    - Preserve original keys/values
    - Add `venue`, `mode`, `asset_class`
    - Ensure expected credential keys exist for each venue
    """
    out: List[Dict[str, Any]] = []
    for row in rows:
        p = AccountProfile.from_dict(row)
        d: Dict[str, Any] = dict(row)

        d.setdefault("name", p.name)
        d["venue"] = p.venue
        d["mode"] = p.mode
        d["asset_class"] = p.asset_class

        if p.venue == "metaapi_mt5":
            d.setdefault("meta_api_account_id", p.meta_api_account_id)
            d.setdefault("token", p.token)
            if p.region:
                d.setdefault("region", p.region)

        if p.venue in {"binance", "bybit"}:
            d.setdefault("api_key", p.api_key)
            d.setdefault("api_secret", p.api_secret)

        out.append(d)

    return out

