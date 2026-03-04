"""Pipeline observer package — see base.py for architecture notes."""

from src.core.observers.base import (
    ERROR,
    ORDER_SUBMITTED,
    POSITION_UPDATED,
    RISK_DECIDED,
    SIGNAL_RECEIVED,
    SIGNAL_VALIDATED,
    Observer,
    TradeEvent,
    WorkerSubject,
)
from src.core.observers.auditor import AuditorObserver
from src.core.observers.executor import ExecutorObserver
from src.core.observers.metrics import MetricsObserver
from src.core.observers.risk_observer import RiskObserver

__all__ = [
    "TradeEvent",
    "Observer",
    "WorkerSubject",
    "SIGNAL_RECEIVED",
    "SIGNAL_VALIDATED",
    "RISK_DECIDED",
    "ORDER_SUBMITTED",
    "POSITION_UPDATED",
    "ERROR",
    "AuditorObserver",
    "RiskObserver",
    "ExecutorObserver",
    "MetricsObserver",
]
