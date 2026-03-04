"""
Symbol Mapper Service - TradingView to MT5 Broker Symbol Translation

Purpose:
--------
TradingView and MT5 brokers often use different symbol naming conventions:
- TradingView: NAS100, SPX500, XAUUSD
- MT5 Broker: USTEC, US500, GOLD (varies by broker!)

This service provides:
1. Built-in mappings for common symbols
2. Database-driven custom overrides (per broker)
3. Instrument specifications (contract size, tick size)

Usage:
------
    from src.services.symbol_mapper import SymbolMapper

    # Translate symbol
    broker_symbol = SymbolMapper.to_broker_symbol("NAS100")  # -> "USTEC"

    # Get instrument specs
    specs = SymbolMapper.get_instrument_specs("NAS100")
    # -> {"contract_size": 1, "tick_size": 0.1, "instrument_type": "indices"}

Database Setup:
---------------
Run migration: migrations/025_symbol_mappings.sql

Author: Claude Code (v5.1)
Date: 2026-02-10
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SymbolMapper:
    """Maps TradingView symbols to MT5 broker symbols."""

    # ============================================================================
    # BUILT-IN SYMBOL MAPPINGS (TradingView -> MT5 Standard)
    # ============================================================================
    # These are common mappings but may vary by broker. Use database overrides
    # for broker-specific symbols.

    SYMBOL_MAP = {
        # ── US Indices ──
        "NAS100": "USTEC",      # Nasdaq 100 (some brokers: NAS100, US100)
        "SPX500": "US500",      # S&P 500 (some brokers: SPX500, US500)
        "US30": "US30",         # Dow Jones (usually same)
        "US2000": "US2000",     # Russell 2000

        # ── European Indices ──
        "GER40": "GER40",       # DAX (some brokers: DAX40, DE40)
        "UK100": "UK100",       # FTSE 100 (some brokers: FTSE)
        "FRA40": "FRA40",       # CAC 40
        "ESP35": "ESP35",       # IBEX 35

        # ── Metals ──
        "XAUUSD": "XAUUSD",     # Gold (usually same, some: GOLD)
        "XAGUSD": "XAGUSD",     # Silver (usually same, some: SILVER)

        # ── Forex (usually identical, but some brokers add suffixes) ──
        "EURUSD": "EURUSD.raw",
        "GBPUSD": "GBPUSD",
        "USDJPY": "USDJPY",
        "GBPJPY": "GBPJPY",
        "AUDUSD": "AUDUSD",
        "USDCAD": "USDCAD",
        "NZDUSD": "NZDUSD",
        "USDCHF": "USDCHF",

        # ── Crypto ──
        "BTCUSD": "BTCUSD",     # Bitcoin
        "ETHUSD": "ETHUSD",     # Ethereum

        # ── Commodities ──
        "USOIL": "USOIL",       # WTI Crude
        "UKOIL": "UKOIL",       # Brent Crude
    }

    # ============================================================================
    # CUSTOM OVERRIDES (loaded from database at runtime)
    # ============================================================================
    # Format: {tv_symbol: broker_symbol}
    # Example: {"NAS100": "NQ=F"} for broker using NQ=F instead of USTEC

    _custom_overrides: Dict[str, str] = {}

    @classmethod
    def set_custom_map(cls, tv_symbol: str, broker_symbol: str):
        """
        Add a custom symbol mapping (typically loaded from database).

        Args:
            tv_symbol: TradingView symbol (e.g., "NAS100")
            broker_symbol: Broker's MT5 symbol (e.g., "USTEC" or "NQ=F")

        Example:
            SymbolMapper.set_custom_map("NAS100", "NQ=F")
        """
        cls._custom_overrides[tv_symbol.upper()] = broker_symbol
        logger.info(f"Custom symbol mapping added: {tv_symbol} -> {broker_symbol}")

    @classmethod
    def clear_custom_maps(cls):
        """Clear all custom symbol mappings (useful for testing)."""
        cls._custom_overrides.clear()
        logger.info("All custom symbol mappings cleared")

    @classmethod
    def to_broker_symbol(cls, tv_symbol: str) -> str:
        """
        Translate TradingView symbol to broker symbol.

        Priority:
        1. Custom overrides (from database)
        2. Built-in map
        3. Passthrough (return original)

        Args:
            tv_symbol: Symbol from TradingView (e.g., "NAS100")

        Returns:
            Broker symbol (e.g., "USTEC")

        Example:
            >>> SymbolMapper.to_broker_symbol("NAS100")
            'USTEC'

            >>> SymbolMapper.set_custom_map("NAS100", "NQ=F")
            >>> SymbolMapper.to_broker_symbol("NAS100")
            'NQ=F'
        """
        symbol_upper = tv_symbol.upper()

        # Priority 1: Custom overrides (database)
        if symbol_upper in cls._custom_overrides:
            broker_symbol = cls._custom_overrides[symbol_upper]
            logger.debug(f"Symbol mapped (custom): {tv_symbol} -> {broker_symbol}")
            return broker_symbol

        # Priority 2: Built-in map
        if symbol_upper in cls.SYMBOL_MAP:
            broker_symbol = cls.SYMBOL_MAP[symbol_upper]
            if broker_symbol != tv_symbol:
                logger.debug(f"Symbol mapped (built-in): {tv_symbol} -> {broker_symbol}")
            return broker_symbol

        # Priority 3: Passthrough (no mapping needed)
        logger.debug(f"Symbol passthrough: {tv_symbol} (no mapping found)")
        return tv_symbol

    @classmethod
    def get_instrument_specs(cls, symbol: str) -> Dict[str, any]:
        """
        Get instrument specifications for position sizing calculations.

        Args:
            symbol: TradingView or broker symbol

        Returns:
            dict with:
            - contract_size: Units per lot (100k for forex, 100 for gold, 1 for indices)
            - tick_size: Minimum price movement (pip size)
            - instrument_type: "forex", "metals", "indices", "crypto", or "unknown"

        Example:
            >>> SymbolMapper.get_instrument_specs("NAS100")
            {
                "contract_size": 1,
                "tick_size": 0.1,
                "instrument_type": "indices"
            }

            >>> SymbolMapper.get_instrument_specs("XAUUSD")
            {
                "contract_size": 100,
                "tick_size": 0.01,
                "instrument_type": "metals"
            }
        """
        # Translate to broker symbol first
        broker_symbol = cls.to_broker_symbol(symbol)
        symbol_upper = broker_symbol.upper()

        # ========================================================================
        # CRITICAL: Check metals and crypto FIRST before forex currencies
        # to prevent XAUUSD/BTCUSD from matching the forex condition
        # ========================================================================

        # Metals (Gold, Silver)
        if any(metal in symbol_upper for metal in ["XAU", "XAG", "GOLD", "SILVER"]):
            return {
                "contract_size": 100,  # 1 lot = 100 troy ounces
                "tick_size": 0.01,     # $0.01 per ounce
                "instrument_type": "metals"
            }

        # Cryptocurrencies
        elif any(crypto in symbol_upper for crypto in ["BTC", "ETH", "BCH", "LTC"]):
            return {
                "contract_size": 1,    # 1 lot = 1 coin
                "tick_size": 0.01,     # $0.01 per coin
                "instrument_type": "crypto"
            }

        # Indices (check AFTER metals/crypto to prevent false matches)
        elif any(idx in symbol_upper for idx in ["USTEC", "US500", "US30", "NAS", "SPX", "GER", "UK100", "FRA", "ESP"]):
            return {
                "contract_size": 1,    # 1 lot = 1 contract (varies by broker!)
                "tick_size": 0.1,      # Index points
                "instrument_type": "indices"
            }

        # Forex (check LAST to avoid false positives)
        elif any(curr in symbol_upper for curr in ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"]):
            # JPY pairs have different pip size
            tick_size = 0.01 if "JPY" in symbol_upper else 0.0001
            return {
                "contract_size": 100_000,  # 1 lot = 100k units
                "tick_size": tick_size,
                "instrument_type": "forex"
            }

        # Unknown instrument type
        else:
            logger.warning(f"Unknown instrument type for {symbol} (broker: {broker_symbol}), using forex defaults")
            return {
                "contract_size": 100_000,
                "tick_size": 0.0001,
                "instrument_type": "unknown"
            }

    @classmethod
    def load_from_database(cls, supabase_client):
        """
        Load custom symbol mappings from Supabase.

        Args:
            supabase_client: Initialized Supabase client

        Example:
            from src.adapters.supabase import init_supabase
            init_supabase()
            from src.adapters.supabase import supabase

            SymbolMapper.load_from_database(supabase)
        """
        if not supabase_client:
            logger.warning("Supabase client not provided, skipping custom symbol mappings")
            return

        try:
            result = supabase_client.table("symbol_mappings").select("*").eq("enabled", True).execute()

            count = 0
            for row in result.data:
                tv_symbol = row.get("tv_symbol")
                broker_symbol = row.get("broker_symbol")
                if tv_symbol and broker_symbol:
                    cls.set_custom_map(tv_symbol, broker_symbol)
                    count += 1

            logger.info(f"Loaded {count} custom symbol mappings from database")

        except Exception as e:
            logger.error(f"Failed to load custom symbol mappings from database: {e}")


# ============================================================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# ============================================================================

def translate_symbol(tv_symbol: str) -> str:
    """
    Convenience function for symbol translation.

    Args:
        tv_symbol: TradingView symbol

    Returns:
        Broker symbol
    """
    return SymbolMapper.to_broker_symbol(tv_symbol)


def get_specs(symbol: str) -> Dict[str, any]:
    """
    Convenience function for instrument specs.

    Args:
        symbol: Symbol (TradingView or broker)

    Returns:
        Instrument specifications dict
    """
    return SymbolMapper.get_instrument_specs(symbol)


__all__ = ["SymbolMapper", "translate_symbol", "get_specs"]
