"""Execution logic: router and adapters (DRY_RUN, PAPER, LIVE)."""

from src.adapters.execution import get_adapter

__all__ = ["get_adapter"]
