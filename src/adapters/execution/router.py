"""Execution router: choose adapter by RUN_MODE, settings, or broker profile (multi-account)."""

from typing import Any, Dict

from config import get_settings
from config.settings import Settings

from src.adapters.execution.dry_run_adapter import DryRunAdapter
from src.adapters.execution.interfaces import ExecutionAdapter
from src.adapters.execution.live_adapter import LiveAdapter
from src.adapters.execution.binance_adapter import BinanceAdapter
from src.adapters.execution.bybit_adapter import BybitAdapter
from src.adapters.execution.ctrader_adapter import CTraderAdapter
from src.adapters.execution.meta_api_adapter import MetaApiAdapter
from src.adapters.execution.paper_adapter import PaperAdapter


def get_adapter(
    run_mode: str | None = None,
    settings: Settings | None = None,
    paper_trader: Any = None,
    profile: Dict[str, Any] | None = None,
) -> ExecutionAdapter:
    """
    Return execution adapter. When profile is provided (multi-account), use its token/account_id
    for MetaApi. Otherwise use settings (single-account).
    """
    s = settings or get_settings()

    # Normalize env-driven strings to avoid leading/trailing whitespace issues
    # (we've seen EXECUTION_MODE set as "\tMETAAPI" in production).
    env_exec_mode = (getattr(s, "execution_mode", "") or "").strip().upper()
    env_run_mode = (run_mode or s.run_mode or "DRY_RUN").strip().upper()

    # Multi-account: profile carries token, account_id, and optional name
    if profile and isinstance(profile, dict):
        venue = (profile.get("venue") or "").strip().lower() or "metaapi_mt5"
        if venue == "metaapi":
            venue = "metaapi_mt5"

        if venue == "binance":
            return BinanceAdapter(
                api_key=(profile.get("api_key") or "").strip(),
                api_secret=(profile.get("api_secret") or "").strip(),
                account_name=(profile.get("name") or "").strip() or None,
            )
        if venue == "bybit":
            return BybitAdapter(
                api_key=(profile.get("api_key") or "").strip(),
                api_secret=(profile.get("api_secret") or "").strip(),
                account_name=(profile.get("name") or "").strip() or None,
            )

        if venue == "ctrader":
            refresh_token = (profile.get("token") or "").strip()
            ctid = (profile.get("meta_api_account_id") or profile.get("account_id") or "").strip()
            is_live = (profile.get("run_mode") or "").strip().upper() == "LIVE"
            if refresh_token and ctid:
                return CTraderAdapter(
                    refresh_token=refresh_token,
                    ctid_trader_account_id=ctid,
                    account_name=(profile.get("name") or "").strip() or None,
                    is_live=is_live,
                )
            # Fall through to single-account if missing credentials

        token = (profile.get("token") or "").strip()
        account_id = (profile.get("meta_api_account_id") or profile.get("account_id") or "").strip()
        account_name = (profile.get("name") or "").strip() or None
        region = (profile.get("region") or "").strip() or None
        if token and account_id:
            return MetaApiAdapter(token=token, account_id=account_id, account_name=account_name, region=region)
        # Fall through to single-account

    # Explicit override: external execution via MetaApi (single-account, DB-first)
    if env_exec_mode == "METAAPI":
        try:
            from src.core.metaapi_credentials import get_primary_credentials
            token, account_id, _ = get_primary_credentials()
        except Exception:
            token, account_id = "", ""
        if not token or not account_id:
            raise ValueError(
                "EXECUTION_MODE=METAAPI but no active broker profile found with credentials. "
                "Go to the Accounts page and select an account for trading."
            )
        return MetaApiAdapter(token=token, account_id=account_id)

    mode = env_run_mode
    if mode == "DRY_RUN":
        return DryRunAdapter()
    if mode == "PAPER":
        if paper_trader is None:
            raise ValueError("PaperAdapter requires paper_trader")
        return PaperAdapter(paper_trader)
    if mode == "LIVE":
        if not s.live_trading_enabled:
            return DryRunAdapter()
        return LiveAdapter()
    return DryRunAdapter()
