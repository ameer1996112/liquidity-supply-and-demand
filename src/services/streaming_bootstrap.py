from __future__ import annotations

from typing import Any, Dict

from src.services.binance_streaming_service import ensure_binance_streaming
from src.services.bybit_streaming_service import ensure_bybit_streaming


def ensure_streaming_for_profile(profile: Dict[str, Any], supabase_client) -> None:  # type: ignore[no-untyped-def]
    venue = (profile.get("venue") or "").strip().lower()
    name = (profile.get("name") or "profile").strip()

    if venue == "binance":
        ensure_binance_streaming(
            api_key=(profile.get("api_key") or "").strip(),
            supabase_client=supabase_client,
            account_name=name,
        )
        return

    if venue == "bybit":
        ensure_bybit_streaming(
            api_key=(profile.get("api_key") or "").strip(),
            api_secret=(profile.get("api_secret") or "").strip(),
            supabase_client=supabase_client,
            account_name=name,
        )
        return

