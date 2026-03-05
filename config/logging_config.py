"""
Shared logging configuration for API and Worker.

Railway (and similar platforms) determine log severity by stream:
- stdout → INFO
- stderr → ERROR

Python's logging writes to stderr by default, so all logs appear as errors.
This module routes INFO/DEBUG to stdout and WARNING/ERROR/CRITICAL to stderr
so Railway correctly classifies severity.
"""

import logging
import sys


class InfoFilter(logging.Filter):
    """Only allow DEBUG and INFO records (for stdout handler)."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno in (logging.DEBUG, logging.INFO)


def configure_logging(
    level: int = logging.INFO,
    format_str: str = "%(asctime)s - %(levelname)s - %(message)s",
) -> None:
    """
    Configure root logger with stream-based severity routing for Railway.

    - INFO/DEBUG → stdout (platform shows as INFO)
    - WARNING/ERROR/CRITICAL → stderr (platform shows as ERROR)
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Remove any existing handlers (e.g. from basicConfig)
    for h in root.handlers[:]:
        root.removeHandler(h)

    formatter = logging.Formatter(format_str)

    h_stdout = logging.StreamHandler(sys.stdout)
    h_stdout.setLevel(logging.DEBUG)
    h_stdout.addFilter(InfoFilter())
    h_stdout.setFormatter(formatter)

    h_stderr = logging.StreamHandler(sys.stderr)
    h_stderr.setLevel(logging.WARNING)
    h_stderr.setFormatter(formatter)

    root.addHandler(h_stdout)
    root.addHandler(h_stderr)
