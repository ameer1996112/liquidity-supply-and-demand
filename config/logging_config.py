"""
Shared logging configuration for API and Worker.

Railway (and similar platforms) determine log severity by stream:
- stdout → INFO
- stderr → ERROR

Python's logging writes to stderr by default, so all logs appear as errors.
This module routes INFO/DEBUG to stdout and WARNING/ERROR/CRITICAL to stderr
so Railway correctly classifies severity.

Usage:
    from config.logging_config import configure_logging, get_logger, trade_context

    configure_logging()                         # call once at startup
    logger = get_logger("trinity.worker")       # consistent name under trinity.*

    # Attach trade/correlation context for a request:
    with trade_context(trade_id="abc123", symbol="EURUSD"):
        logger.info("Processing signal")        # → "... [trade_id=abc123 symbol=EURUSD] Processing signal"
"""

import logging
import re
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator, Optional

_TOKEN_PATTERN = re.compile(r"(auth-token=)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)

# ── Shared context vars (set per-signal, injected into every log line) ────────
_ctx_trade_id: ContextVar[Optional[str]] = ContextVar("trade_id", default=None)  # type: ignore[assignment]
_ctx_symbol: ContextVar[Optional[str]] = ContextVar("symbol", default=None)  # type: ignore[assignment]
_ctx_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)  # type: ignore[assignment]

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


class _SensitiveDataFilter(logging.Filter):
    """Redact auth tokens and credentials that appear in log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _TOKEN_PATTERN.sub(r"\1[REDACTED]", record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: _TOKEN_PATTERN.sub(r"\1[REDACTED]", v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    _TOKEN_PATTERN.sub(r"\1[REDACTED]", a) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


class _ContextFilter(logging.Filter):
    """Inject trade_id / symbol / correlation_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        parts = []
        for label, var in (
            ("trade_id", _ctx_trade_id),
            ("symbol", _ctx_symbol),
            ("cid", _ctx_correlation_id),
        ):
            val = var.get()
            if val:
                parts.append(f"{label}={val}")
        if parts:
            record.msg = f"[{' '.join(parts)}] {record.msg}"
        return True


class _InfoFilter(logging.Filter):
    """Only allow DEBUG and INFO records (for stdout handler)."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno in (logging.DEBUG, logging.INFO)


def configure_logging(
    level: Optional[int] = None,
    format_str: str = LOG_FORMAT,
) -> None:
    """
    Configure root logger with stream-based severity routing for Railway.

    - INFO/DEBUG → stdout (platform shows as INFO)
    - WARNING/ERROR/CRITICAL → stderr (platform shows as ERROR)

    Pass level=None to read from settings (LOG_LEVEL env var).
    """
    if level is None:
        try:
            from config import get_settings
            level = getattr(logging, get_settings().log_level.upper(), logging.INFO)
        except Exception:
            level = logging.INFO

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any existing handlers (e.g. from basicConfig or previous calls)
    for h in list(root.handlers):
        root.removeHandler(h)

    ctx_filter = _ContextFilter()
    sensitive_filter = _SensitiveDataFilter()
    formatter = logging.Formatter(format_str)

    h_stdout = logging.StreamHandler(sys.stdout)
    h_stdout.setLevel(logging.DEBUG)
    h_stdout.addFilter(sensitive_filter)
    h_stdout.addFilter(_InfoFilter())
    h_stdout.addFilter(ctx_filter)
    h_stdout.setFormatter(formatter)

    h_stderr = logging.StreamHandler(sys.stderr)
    h_stderr.setLevel(logging.WARNING)
    h_stderr.addFilter(sensitive_filter)
    h_stderr.addFilter(ctx_filter)
    h_stderr.setFormatter(formatter)

    root.addHandler(h_stdout)
    root.addHandler(h_stderr)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("hpack").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    # engineio/socketio log full WebSocket URLs including auth-token JWT
    logging.getLogger("engineio").setLevel(logging.WARNING)
    logging.getLogger("engineio.client").setLevel(logging.WARNING)
    logging.getLogger("socketio").setLevel(logging.WARNING)
    logging.getLogger("socketio.client").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger under the 'trinity.*' namespace.

    Accepts either short names ('worker', 'api') or full names ('trinity.worker').
    """
    if not name.startswith("trinity."):
        name = f"trinity.{name}"
    return logging.getLogger(name)


@contextmanager
def trade_context(
    trade_id: Optional[str] = None,
    symbol: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Generator[None, None, None]:
    """
    Context manager that injects trade metadata into all log lines within its scope.

    Example:
        with trade_context(trade_id="t-123", symbol="XAUUSD"):
            logger.info("Executing order")
            # → "... [trade_id=t-123 symbol=XAUUSD] Executing order"
    """
    tokens = []
    if trade_id is not None:
        tokens.append(_ctx_trade_id.set(trade_id))
    if symbol is not None:
        tokens.append(_ctx_symbol.set(symbol))
    if correlation_id is not None:
        tokens.append(_ctx_correlation_id.set(correlation_id))
    try:
        yield
    finally:
        for tok in tokens:
            tok.var.reset(tok)
