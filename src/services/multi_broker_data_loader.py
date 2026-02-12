"""
Multi-Broker Data Loader

Fetches historical data from multiple brokers based on symbol type.
Routes symbols to the best broker for optimal spreads and data quality.

Example:
    - Forex (EURUSD, GBPUSD) → Vantage
    - Gold/Metals (XAUUSD, XAGUSD) → FXCM or Vantage
    - Indices (NAS100, US30) → FXCM or IC Markets

Usage:
    from src.services.multi_broker_data_loader import MultiBrokerDataLoader

    loader = MultiBrokerDataLoader(
        default_token="vantage-token",
        default_account_id="vantage-account-id",
        broker_routes={
            "XAUUSD": {"token": "fxcm-token", "account_id": "fxcm-account"},
            "NAS100": {"token": "fxcm-token", "account_id": "fxcm-account"},
        }
    )

    # Automatically routes to correct broker
    df_eurusd = loader.fetch_candles("EURUSD", "2024-01-01", "2024-12-31")  # → Vantage
    df_gold = loader.fetch_candles("XAUUSD", "2024-01-01", "2024-12-31")    # → FXCM
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd

from src.services.data_loader import MetaApiDataLoader

logger = logging.getLogger(__name__)


class MultiBrokerDataLoader:
    """
    Multi-broker historical data loader with intelligent symbol routing.

    Routes symbols to optimal broker based on:
    - Symbol type (forex, metals, indices, crypto)
    - Data quality and spread
    - Broker specialization
    """

    # Default symbol routing rules (can be overridden)
    DEFAULT_ROUTES = {
        # Metals → Often better on specialized brokers
        "XAUUSD": "metals_broker",
        "XAGUSD": "metals_broker",
        "Gold": "metals_broker",
        "Silver": "metals_broker",

        # Indices → Often on CFD/index specialists
        "NAS100": "indices_broker",
        "US30": "indices_broker",
        "US500": "indices_broker",
        "DE40": "indices_broker",
        "UK100": "indices_broker",

        # Crypto → Specialized crypto brokers
        "BTCUSD": "crypto_broker",
        "ETHUSD": "crypto_broker",

        # Forex → Default broker (usually best spreads)
        # All other symbols use default_broker
    }

    def __init__(
        self,
        default_token: str = None,
        default_account_id: str = None,
        default_region: str = "new-york",
        broker_routes: Dict[str, Dict[str, str]] = None,
        symbol_type_routes: Dict[str, Dict[str, str]] = None,
    ) -> None:
        """
        Initialize multi-broker data loader.

        Args:
            default_token: Default MetaApi token (e.g., Vantage)
            default_account_id: Default MetaApi account ID
            default_region: Default MetaApi region
            broker_routes: Symbol-specific broker config
                Example: {
                    "XAUUSD": {"token": "...", "account_id": "...", "region": "london"},
                    "NAS100": {"token": "...", "account_id": "..."},
                }
            symbol_type_routes: Broker config by symbol type
                Example: {
                    "metals_broker": {"token": "...", "account_id": "..."},
                    "indices_broker": {"token": "...", "account_id": "..."},
                }
        """
        # Default credentials (Vantage)
        self.default_token = default_token or os.getenv("META_API_TOKEN")
        self.default_account_id = default_account_id or os.getenv("META_API_ACCOUNT_ID")
        self.default_region = default_region

        if not self.default_token or not self.default_account_id:
            raise ValueError(
                "Default MetaApi credentials missing. Provide default_token and "
                "default_account_id or set META_API_TOKEN and META_API_ACCOUNT_ID env vars."
            )

        # Symbol-specific routing
        self.broker_routes = broker_routes or {}

        # Broker type routing (metals_broker, indices_broker, etc.)
        self.symbol_type_routes = symbol_type_routes or {}

        # Cache of MetaApiDataLoader instances (one per broker)
        self._loaders: Dict[str, MetaApiDataLoader] = {}

        # Initialize default loader
        self._loaders["default"] = MetaApiDataLoader(
            token=self.default_token,
            account_id=self.default_account_id,
            region=self.default_region,
        )

        logger.info(
            "MultiBrokerDataLoader initialized with %d broker routes",
            len(self.broker_routes),
        )

    def _get_loader_for_symbol(self, symbol: str) -> MetaApiDataLoader:
        """
        Get the appropriate MetaApiDataLoader for a given symbol.

        Args:
            symbol: Trading symbol (e.g., "EURUSD", "XAUUSD")

        Returns:
            MetaApiDataLoader instance for this symbol's broker
        """
        # 1. Check if symbol has explicit routing
        if symbol in self.broker_routes:
            config = self.broker_routes[symbol]
            cache_key = f"{config['account_id']}"

            if cache_key not in self._loaders:
                self._loaders[cache_key] = MetaApiDataLoader(
                    token=config["token"],
                    account_id=config["account_id"],
                    region=config.get("region", self.default_region),
                )
                logger.info(
                    "Created loader for symbol %s → broker %s",
                    symbol,
                    cache_key,
                )

            return self._loaders[cache_key]

        # 2. Check if symbol matches default routing rules
        broker_type = self.DEFAULT_ROUTES.get(symbol)
        if broker_type and broker_type in self.symbol_type_routes:
            config = self.symbol_type_routes[broker_type]
            cache_key = f"{config['account_id']}"

            if cache_key not in self._loaders:
                self._loaders[cache_key] = MetaApiDataLoader(
                    token=config["token"],
                    account_id=config["account_id"],
                    region=config.get("region", self.default_region),
                )
                logger.info(
                    "Created loader for symbol %s (type: %s) → broker %s",
                    symbol,
                    broker_type,
                    cache_key,
                )

            return self._loaders[cache_key]

        # 3. Use default broker
        logger.debug("Using default broker for symbol %s", symbol)
        return self._loaders["default"]

    def fetch_candles(
        self,
        symbol: str,
        start_time: str | datetime,
        end_time: str | datetime | None = None,
        timeframe: str = "5m",
        limit: int = 10000,
    ) -> pd.DataFrame:
        """
        Fetch historical candles with automatic broker routing.

        Args:
            symbol: Trading symbol (e.g., "EURUSD", "XAUUSD")
            start_time: Start time (ISO 8601 string or datetime)
            end_time: End time (ISO 8601 string, datetime, or None)
            timeframe: Candle timeframe (e.g., "5m", "1h", "1d")
            limit: Maximum number of candles to fetch

        Returns:
            pandas DataFrame with OHLCV data
        """
        loader = self._get_loader_for_symbol(symbol)

        logger.info(
            "Fetching %s candles via broker %s",
            symbol,
            loader.account_id,
        )

        return loader.fetch_candles(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            timeframe=timeframe,
            limit=limit,
        )

    def get_latest_price(self, symbol: str) -> Dict[str, float]:
        """
        Get current bid/ask prices with automatic broker routing.

        Args:
            symbol: Trading symbol (e.g., "EURUSD")

        Returns:
            Dict with keys: bid, ask, time
        """
        loader = self._get_loader_for_symbol(symbol)
        return loader.get_latest_price(symbol)

    @classmethod
    def from_env(cls) -> MultiBrokerDataLoader:
        """
        Create MultiBrokerDataLoader from environment variables.

        Expected env vars:
        - META_API_TOKEN (default broker - Vantage)
        - META_API_ACCOUNT_ID
        - META_API_TOKEN_VANTAGE (optional, same as default)
        - META_API_ACCOUNT_ID_VANTAGE
        - META_API_TOKEN_FXCM (optional, for metals/indices)
        - META_API_ACCOUNT_ID_FXCM
        - META_API_REGION (optional, default: "new-york")

        Returns:
            MultiBrokerDataLoader instance
        """
        # Default broker (Vantage)
        default_token = os.getenv("META_API_TOKEN")
        default_account_id = os.getenv("META_API_ACCOUNT_ID")
        default_region = os.getenv("META_API_REGION", "new-york")

        # FXCM broker (for metals/indices)
        fxcm_token = os.getenv("META_API_TOKEN_FXCM")
        fxcm_account_id = os.getenv("META_API_ACCOUNT_ID_FXCM")

        # Vantage broker (explicit)
        vantage_token = os.getenv("META_API_TOKEN_VANTAGE") or default_token
        vantage_account_id = os.getenv("META_API_ACCOUNT_ID_VANTAGE") or default_account_id

        # Build broker type routes
        symbol_type_routes = {}

        if fxcm_token and fxcm_account_id:
            symbol_type_routes["metals_broker"] = {
                "token": fxcm_token,
                "account_id": fxcm_account_id,
                "region": default_region,
            }
            symbol_type_routes["indices_broker"] = {
                "token": fxcm_token,
                "account_id": fxcm_account_id,
                "region": default_region,
            }
            logger.info("FXCM broker configured for metals and indices")

        # Use Vantage for forex (default already handles this)
        logger.info("Vantage broker configured for forex")

        return cls(
            default_token=default_token,
            default_account_id=default_account_id,
            default_region=default_region,
            symbol_type_routes=symbol_type_routes,
        )


# Convenience function for quick usage
def create_multi_broker_loader() -> MultiBrokerDataLoader:
    """
    Create MultiBrokerDataLoader with automatic env var detection.

    Returns:
        MultiBrokerDataLoader instance
    """
    return MultiBrokerDataLoader.from_env()
