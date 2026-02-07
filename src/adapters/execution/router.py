"""Execution router: choose adapter by RUN_MODE, settings, or broker profile (multi-account)."""

from typing import Any, Dict

from config import get_settings
from config.settings import Settings

from src.adapters.execution.dry_run_adapter import DryRunAdapter
from src.adapters.execution.interfaces import ExecutionAdapter
from src.adapters.execution.live_adapter import LiveAdapter
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

    # Multi-account: profile carries token and account_id
    if profile and isinstance(profile, dict):
        token = (profile.get("token") or "").strip()
        account_id = (profile.get("meta_api_account_id") or profile.get("account_id") or "").strip()
        if token and account_id:
            return MetaApiAdapter(token=token, account_id=account_id)
        # Fall through to single-account

    # Explicit override: external execution via MetaApi (single-account)
    if getattr(s, "execution_mode", "").upper() == "METAAPI":
        return MetaApiAdapter(token=s.meta_api_token, account_id=s.meta_api_account_id)

    mode = (run_mode or s.run_mode).upper()
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
