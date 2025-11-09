"""
Hardened Binance Futures API Client
Enhanced with error tracking, circuit breakers, and retry logic
"""

import ccxt.async_support as ccxt
import asyncio
import aiohttp
from typing import List, Dict, Optional
import pandas as pd
from datetime import datetime, timedelta
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.error_tracker import get_error_tracker
from utils.circuit_breaker import circuit_breaker, CircuitBreakerError
from utils.retry_handler import async_retry_api_call

logger = logging.getLogger(__name__)


class HardenedBinanceFuturesClient:
    """
    Production-ready Binance Futures API client with:
    - Automatic retry with exponential backoff
    - Circuit breaker pattern
    - Error tracking and metrics
    - Rate limiting
    - Comprehensive error handling
    """

    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
                'recvWindow': 60000  # Longer receive window
            }
        })

        if testnet:
            self.exchange.set_sandbox_mode(True)
        self.testnet = testnet

    async def _fapi_get(self, path: str, params: dict = None) -> dict:
        """Helper to call Binance Futures public API endpoints (async)"""
        base = 'https://testnet.binancefuture.com' if self.testnet else 'https://fapi.binance.com'
        url = f"{base}{path}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=30) as resp:
                resp.raise_for_status()
                return await resp.json()
        self.error_tracker = get_error_tracker()
        self.logger = logging.getLogger(__name__)

    @async_retry_api_call(max_retries=5, initial_delay=2.0)
    @circuit_breaker(name='binance_ohlcv', failure_threshold=10, recovery_timeout=120)
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '5m',
        since: Optional[int] = None,
        limit: int = 1500
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data with error hardening

        Includes:
        - Automatic retry (up to 5 attempts)
        - Circuit breaker (opens after 10 failures)
        - Error tracking and logging

        Args:
            symbol: Trading pair (e.g., 'SOL/USDT')
            timeframe: Candlestick interval
            since: Start timestamp in milliseconds
            limit: Number of candles to fetch

        Returns:
            DataFrame with OHLCV data

        Raises:
            CircuitBreakerError: If circuit is open
            RetryError: If all retries exhausted
        """
        try:
            ohlcv = await self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=limit
            )

            if not ohlcv:
                raise ValueError("Empty OHLCV response from exchange")

            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            return df

        except CircuitBreakerError:
            # Circuit breaker is open, don't track as error
            raise

        except Exception as e:
            # Track error
            self.error_tracker.record_error(
                error_type='api_ohlcv_error',
                error=e,
                context={'symbol': symbol, 'timeframe': timeframe},
                severity='ERROR'
            )
            raise

    @async_retry_api_call(max_retries=5, initial_delay=2.0)
    @circuit_breaker(name='binance_oi', failure_threshold=10, recovery_timeout=120)
    async def fetch_open_interest_hist(
        self,
        symbol: str,
        period: str = '5m',
        limit: int = 500
    ) -> pd.DataFrame:
        """
        Fetch historical Open Interest data with error hardening

        Args:
            symbol: Trading pair
            period: Time period ('5m', '15m', '1h', '4h')
            limit: Number of records (max 500)

        Returns:
            DataFrame with OI data
        """
        try:
            params = {
                'symbol': symbol.replace('/', ''),
                'period': period,
                'limit': limit
            }

            response = await self._fapi_get('/futures/data/openInterestHist', params)

            if not response:
                raise ValueError("Empty OI response from exchange")

            df = pd.DataFrame(response)
            if not df.empty and 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            if 'sumOpenInterest' in df.columns:
                df['sumOpenInterest'] = df['sumOpenInterest'].astype(float)
            if 'sumOpenInterestValue' in df.columns:
                df['sumOpenInterestValue'] = df['sumOpenInterestValue'].astype(float)

            return df

        except CircuitBreakerError:
            raise

        except Exception as e:
            self.error_tracker.record_error(
                error_type='api_oi_error',
                error=e,
                context={'symbol': symbol, 'period': period},
                severity='ERROR'
            )
            raise

    @async_retry_api_call(max_retries=5, initial_delay=2.0)
    @circuit_breaker(name='binance_funding', failure_threshold=10, recovery_timeout=120)
    async def fetch_funding_rate_history(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Fetch funding rate history with error hardening

        Args:
            symbol: Trading pair
            start_time: Start timestamp in milliseconds
            limit: Number of records (max 1000)

        Returns:
            DataFrame with funding rate data
        """
        try:
            params = {
                'symbol': symbol.replace('/', ''),
                'limit': limit
            }
            if start_time:
                params['startTime'] = start_time

            response = await self._fapi_get('/fapi/v1/fundingRate', params)

            if not response:
                raise ValueError("Empty funding rate response")

            df = pd.DataFrame(response)
            if not df.empty and 'fundingTime' in df.columns:
                df['fundingTime'] = pd.to_datetime(df['fundingTime'], unit='ms')
            if 'fundingRate' in df.columns:
                df['fundingRate'] = df['fundingRate'].astype(float)

            return df

        except CircuitBreakerError:
            raise

        except Exception as e:
            self.error_tracker.record_error(
                error_type='api_funding_error',
                error=e,
                context={'symbol': symbol},
                severity='ERROR'
            )
            raise

    @async_retry_api_call(max_retries=3, initial_delay=1.0)
    @circuit_breaker(name='binance_liquidations', failure_threshold=10, recovery_timeout=120)
    async def fetch_liquidations(
        self,
        symbol: str,
        limit: int = 100
    ) -> pd.DataFrame:
        """
        Fetch recent liquidation orders with error hardening

        Args:
            symbol: Trading pair
            limit: Number of records (max 1000)

        Returns:
            DataFrame with liquidation data
        """
        try:
            params = {
                'symbol': symbol.replace('/', ''),
                'limit': limit
            }

            response = await self._fapi_get('/fapi/v1/allForceOrders', params)

            df = pd.DataFrame(response) if response else pd.DataFrame()

            if not df.empty and 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'], unit='ms')
            if 'price' in df.columns:
                df['price'] = df['price'].astype(float)
            if 'origQty' in df.columns:
                df['origQty'] = df['origQty'].astype(float)

            return df

        except CircuitBreakerError:
            raise

        except Exception as e:
            self.error_tracker.record_error(
                error_type='api_liquidation_error',
                error=e,
                context={'symbol': symbol},
                severity='WARNING'  # Lower severity for liquidations
            )
            raise

    @async_retry_api_call(max_retries=5, initial_delay=2.0)
    @circuit_breaker(name='binance_trader_ratio', failure_threshold=10, recovery_timeout=120)
    async def fetch_top_trader_ratio(
        self,
        symbol: str,
        period: str = '5m',
        limit: int = 500
    ) -> pd.DataFrame:
        """
        Fetch top trader long/short account ratio with error hardening

        Args:
            symbol: Trading pair
            period: Time period ('5m', '15m', '1h')
            limit: Number of records (max 500)

        Returns:
            DataFrame with long/short ratio data
        """
        try:
            params = {
                'symbol': symbol.replace('/', ''),
                'period': period,
                'limit': limit
            }

            response = await self._fapi_get('/futures/data/topLongShortAccountRatio', params)

            if not response:
                raise ValueError("Empty trader ratio response")

            df = pd.DataFrame(response)
            if not df.empty and 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            if 'longShortRatio' in df.columns:
                df['longShortRatio'] = df['longShortRatio'].astype(float)
            if 'longAccount' in df.columns:
                df['longAccount'] = df['longAccount'].astype(float)
            if 'shortAccount' in df.columns:
                df['shortAccount'] = df['shortAccount'].astype(float)

            return df

        except CircuitBreakerError:
            raise

        except Exception as e:
            self.error_tracker.record_error(
                error_type='api_trader_ratio_error',
                error=e,
                context={'symbol': symbol, 'period': period},
                severity='ERROR'
            )
            raise

    def get_error_summary(self) -> dict:
        """Get error summary for this client"""
        return self.error_tracker.get_error_summary()

    def print_error_summary(self):
        """Print error summary"""
        self.error_tracker.print_summary()
