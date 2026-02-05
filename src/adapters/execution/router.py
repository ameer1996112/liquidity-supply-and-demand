"""Execution router: choose adapter by RUN_MODE and settings."""

from typing import Any

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
) -> ExecutionAdapter:
    s = settings or get_settings()

    # Explicit override: external execution via MetaApi
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
