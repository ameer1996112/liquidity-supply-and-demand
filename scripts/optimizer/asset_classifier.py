from __future__ import annotations

import re

FOREX = {
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AUDUSD",
    "NZDUSD",
    "USDCAD",
    "USDCHF",
    "EURJPY",
    "GBPJPY",
    "AUDJPY",
}
METALS = {"XAUUSD", "XAGUSD"}
INDEX_CFDS = {"NAS100", "US100", "US500", "US30", "SPX", "NDX"}
FUTURES_INDEX = {"NQ", "MNQ", "ES", "MES", "YM", "MYM"}
FUTURES_METAL = {"GC", "MGC", "SI", "SIL"}
FUTURES_ENERGY = {"CL", "MCL"}
FUTURES_FX = {"6E", "M6E", "6J", "M6J"}


def _clean_symbol(symbol: str) -> str:
    raw = str(symbol or "").upper().split(":")[-1]
    raw = raw.split(".")[0]
    return re.sub(r"[^A-Z0-9]", "", raw)


def _root(symbol: str) -> str:
    clean = _clean_symbol(symbol)
    for size in (3, 2):
        root = clean[:size]
        if root in FUTURES_INDEX | FUTURES_METAL | FUTURES_ENERGY | FUTURES_FX:
            return root
    return clean


def classify_asset(symbol: str) -> str:
    """
    Return one of:
    forex, metal, index_cfd, crypto, futures_index, futures_metal,
    futures_energy, futures_fx, unknown.
    """
    clean = _clean_symbol(symbol)
    root = _root(clean)
    if clean in FOREX:
        return "forex"
    if clean in METALS:
        return "metal"
    if clean in INDEX_CFDS:
        return "index_cfd"
    if root in FUTURES_INDEX:
        return "futures_index"
    if root in FUTURES_METAL:
        return "futures_metal"
    if root in FUTURES_ENERGY:
        return "futures_energy"
    if root in FUTURES_FX:
        return "futures_fx"
    if clean.endswith("USD") and clean not in FOREX and clean not in METALS:
        return "crypto"
    return "unknown"


def is_futures_asset(symbol: str) -> bool:
    return classify_asset(symbol).startswith("futures_")
