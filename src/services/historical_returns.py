"""
Historical Returns Service

Fetches historical price data and calculates returns/covariance matrices
for portfolio risk analysis.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import numpy as np
import yfinance as yf
from functools import lru_cache

logger = logging.getLogger(__name__)


class HistoricalReturnsService:
    """Service for fetching and analyzing historical returns."""

    # Symbol mapping: MetaAPI symbols -> yfinance tickers
    SYMBOL_MAP = {
        # Forex pairs
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X",
        "USDCHF": "USDCHF=X",
        "AUDUSD": "AUDUSD=X",
        "NZDUSD": "NZDUSD=X",
        "USDCAD": "USDCAD=X",
        "EURJPY": "EURJPY=X",
        "GBPJPY": "GBPJPY=X",
        "AUDJPY": "AUDJPY=X",
        "EURGBP": "EURGBP=X",

        # Indices
        "US30": "^DJI",
        "NAS100": "^IXIC",
        "SPX500": "^GSPC",
        "UK100": "^FTSE",
        "GER40": "^GDAXI",
        "FRA40": "^FCHI",
        "JPN225": "^N225",

        # Precious metals
        "XAUUSD": "GC=F",  # Gold futures
        "XAGUSD": "SI=F",  # Silver futures

        # Crypto (if needed)
        "BTCUSD": "BTC-USD",
        "ETHUSD": "ETH-USD",
    }

    def __init__(self):
        """Initialize the service."""
        self.cache_duration = timedelta(hours=24)
        self._last_cache_clear = datetime.now(timezone.utc)

    def _get_yfinance_ticker(self, symbol: str) -> str:
        """
        Convert MetaAPI symbol to yfinance ticker.

        Args:
            symbol: MetaAPI symbol (e.g., "EURUSD")

        Returns:
            yfinance ticker (e.g., "EURUSD=X")
        """
        return self.SYMBOL_MAP.get(symbol, symbol)

    @lru_cache(maxsize=128)
    def _fetch_price_data(
        self,
        ticker: str,
        days: int,
        cache_key: str  # For cache invalidation
    ) -> Optional[np.ndarray]:
        """
        Fetch historical price data from yfinance.

        Args:
            ticker: yfinance ticker symbol
            days: Number of days of history
            cache_key: Cache invalidation key (date string)

        Returns:
            Array of closing prices, or None if fetch fails
        """
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days + 10)  # Extra buffer

            data = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                progress=False
            )

            if data.empty:
                logger.warning(f"No data returned for {ticker}")
                return None

            # Get closing prices
            if 'Close' in data.columns:
                prices = data['Close'].values
            elif isinstance(data.columns, tuple):
                # Multi-level columns from yfinance
                prices = data[('Close', ticker)].values
            else:
                logger.warning(f"Cannot find Close column for {ticker}")
                return None

            # Remove NaN values
            prices = prices[~np.isnan(prices)]

            if len(prices) < days:
                logger.warning(f"Insufficient data for {ticker}: {len(prices)} < {days}")
                return None

            return prices[-days:]

        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return None

    def get_returns(
        self,
        symbol: str,
        days: int = 30
    ) -> Optional[List[float]]:
        """
        Get daily returns for a symbol.

        Args:
            symbol: MetaAPI symbol (e.g., "EURUSD")
            days: Number of days of returns to calculate

        Returns:
            List of daily returns (percentage), or None if fetch fails
        """
        ticker = self._get_yfinance_ticker(symbol)
        cache_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        prices = self._fetch_price_data(ticker, days + 1, cache_key)

        if prices is None or len(prices) < 2:
            return None

        # Calculate percentage returns
        returns = np.diff(prices) / prices[:-1] * 100.0

        return returns.tolist()

    def get_returns_matrix(
        self,
        symbols: List[str],
        days: int = 30
    ) -> Optional[np.ndarray]:
        """
        Get returns matrix for multiple symbols (aligned by date).

        Args:
            symbols: List of MetaAPI symbols
            days: Number of days of returns

        Returns:
            2D array of shape (days, n_symbols), or None if any fetch fails
        """
        all_returns = []

        for symbol in symbols:
            returns = self.get_returns(symbol, days)
            if returns is None:
                logger.warning(f"Failed to get returns for {symbol}, skipping")
                return None

            all_returns.append(returns)

        # Stack into matrix (rows = time, cols = symbols)
        try:
            returns_matrix = np.column_stack(all_returns)
            return returns_matrix
        except Exception as e:
            logger.error(f"Error stacking returns matrix: {e}")
            return None

    def get_correlation_matrix(
        self,
        symbols: List[str],
        days: int = 30
    ) -> Optional[np.ndarray]:
        """
        Calculate correlation matrix for multiple symbols.

        Args:
            symbols: List of MetaAPI symbols
            days: Number of days for correlation calculation

        Returns:
            NxN correlation matrix, or None if calculation fails
        """
        returns_matrix = self.get_returns_matrix(symbols, days)

        if returns_matrix is None:
            return None

        try:
            corr_matrix = np.corrcoef(returns_matrix, rowvar=False)
            return corr_matrix
        except Exception as e:
            logger.error(f"Error calculating correlation matrix: {e}")
            return None

    def get_covariance_matrix(
        self,
        symbols: List[str],
        days: int = 30
    ) -> Optional[np.ndarray]:
        """
        Calculate covariance matrix for multiple symbols.

        Args:
            symbols: List of MetaAPI symbols
            days: Number of days for covariance calculation

        Returns:
            NxN covariance matrix, or None if calculation fails
        """
        returns_matrix = self.get_returns_matrix(symbols, days)

        if returns_matrix is None:
            return None

        try:
            cov_matrix = np.cov(returns_matrix, rowvar=False)
            return cov_matrix
        except Exception as e:
            logger.error(f"Error calculating covariance matrix: {e}")
            return None

    def get_volatility(
        self,
        symbol: str,
        days: int = 30
    ) -> Optional[float]:
        """
        Calculate annualized volatility for a symbol.

        Args:
            symbol: MetaAPI symbol
            days: Number of days for volatility calculation

        Returns:
            Annualized volatility (as percentage), or None if calculation fails
        """
        returns = self.get_returns(symbol, days)

        if returns is None:
            return None

        try:
            # Annualized volatility (assuming 252 trading days)
            daily_vol = np.std(returns)
            annual_vol = daily_vol * np.sqrt(252)
            return float(annual_vol)
        except Exception as e:
            logger.error(f"Error calculating volatility for {symbol}: {e}")
            return None

    def clear_cache(self):
        """Clear the LRU cache for fresh data."""
        self._fetch_price_data.cache_clear()
        self._last_cache_clear = datetime.now(timezone.utc)
        logger.info("Historical returns cache cleared")
