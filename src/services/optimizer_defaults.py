from __future__ import annotations

"""
Shared optimizer defaults used by both the backend API and local scripts.

Keep these values backend-safe: no imports from the `scripts/` package here.
"""

DEFAULT_PAIRS = [
    # Major USD Pairs
    "EURUSD",
    "GBPUSD",
    "AUDUSD",
    "NZDUSD",
    "USDCAD",
    "USDCHF",
    # JPY Pairs
    "USDJPY",
    "GBPJPY",
    "EURJPY",
    "NZDJPY",
    "CADJPY",
    "AUDJPY",
    "CHFJPY",
    # GBP Crosses
    "EURGBP",
    "GBPAUD",
    "GBPCAD",
    "GBPCHF",
    "GBPNZD",
    # EUR Crosses
    "EURAUD",
    "EURCAD",
    "EURCHF",
    "EURNZD",
    # AUD/NZD Crosses
    "AUDNZD",
    "AUDCAD",
    "AUDCHF",
    # CAD/CHF Crosses
    "CADCHF",
    "NZDCAD",
    "NZDCHF",
    # Gold & Metals
    "XAUUSD",
    "XAGUSD",
    # Indices
    "NAS100",
    "US30",
    "US500",
]
