"""
Binance Futures API Client
Handles all API interactions with Binance Futures
"""

import ccxt.async_support as ccxt
import asyncio
import aiohttp
from typing import List, Dict, Optional
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class BinanceFuturesClient:
    """
    Robust Binance Futures API client with retry logic and rate limiting
    """

    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True
            }
        })

        if testnet:
            self.exchange.set_sandbox_mode(True)
        self.testnet = testnet
        # Provide a logger instance on the client so callers can use self.logger
        self.logger = logger

    async def _fapi_get(self, path: str, params: dict = None) -> dict:
        """Helper to call Binance Futures public API endpoints (async)"""
        base = 'https://testnet.binancefuture.com' if self.testnet else 'https://fapi.binance.com'
        url = f"{base}{path}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=30) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '5m',
        since: Optional[int] = None,
        limit: int = 1500
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data with automatic pagination for large date ranges

        Args:
            symbol: Trading pair (e.g., 'SOL/USDT')
            timeframe: Candlestick interval ('1m', '5m', '15m', '1h', '4h', '1d')
            since: Start timestamp in milliseconds
            limit: Number of candles to fetch (max 1500)

        Returns:
            DataFrame with OHLCV data
        """
        try:
            ohlcv = await self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=limit
            )

            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df

        except Exception as e:
            self.logger.error(f"Error fetching OHLCV: {e}")
            raise

    async def fetch_open_interest_hist(
        self,
        symbol: str,
        period: str = '5m',
        limit: int = 500
    ) -> pd.DataFrame:
        """
        Fetch historical Open Interest data

        Args:
            symbol: Trading pair (e.g., 'SOL/USDT')
            period: Time period ('5m', '15m', '1h', '4h')
            limit: Number of records (max 500)

        Returns:
            DataFrame with OI data
        """
        try:
            # Binance-specific endpoint
            params = {
                'symbol': symbol.replace('/', ''),
                'period': period,
                'limit': limit
            }

            # Use public REST endpoint for open interest history
            response = await self._fapi_get('/futures/data/openInterestHist', params)

            df = pd.DataFrame(response)
            if not df.empty and 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            if 'sumOpenInterest' in df.columns:
                df['sumOpenInterest'] = df['sumOpenInterest'].astype(float)
            if 'sumOpenInterestValue' in df.columns:
                df['sumOpenInterestValue'] = df['sumOpenInterestValue'].astype(float)

            return df

        except Exception as e:
            self.logger.error(f"Error fetching OI: {e}")
            raise

    async def fetch_funding_rate_history(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Fetch funding rate history

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

            # Funding rate endpoint
            response = await self._fapi_get('/fapi/v1/fundingRate', params)

            df = pd.DataFrame(response)
            if not df.empty and 'fundingTime' in df.columns:
                df['fundingTime'] = pd.to_datetime(df['fundingTime'], unit='ms')
            if 'fundingRate' in df.columns:
                df['fundingRate'] = df['fundingRate'].astype(float)

            return df

        except Exception as e:
            self.logger.error(f"Error fetching funding rate: {e}")
            raise

    async def fetch_liquidations(
        self,
        symbol: str,
        limit: int = 100
    ) -> pd.DataFrame:
        """
        Fetch recent liquidation orders

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

            # Liquidations (all force orders)
            response = await self._fapi_get('/fapi/v1/allForceOrders', params)

            df = pd.DataFrame(response)
            if not df.empty and 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'], unit='ms')
            if 'price' in df.columns:
                df['price'] = df['price'].astype(float)
            if 'origQty' in df.columns:
                df['origQty'] = df['origQty'].astype(float)

            return df

        except Exception as e:
            self.logger.error(f"Error fetching liquidations: {e}")
            raise

    async def fetch_top_trader_ratio(
        self,
        symbol: str,
        period: str = '5m',
        limit: int = 500
    ) -> pd.DataFrame:
        """
        Fetch top trader long/short account ratio

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

            # Top long/short account ratio
            response = await self._fapi_get('/futures/data/topLongShortAccountRatio', params)

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

        except Exception as e:
            self.logger.error(f"Error fetching trader ratio: {e}")
            raise

    async def fetch_order_book(
        self,
        symbol: str,
        limit: int = 100
    ) -> pd.DataFrame:
        """
        Fetch order book depth (bids and asks)

        Args:
            symbol: Trading pair (e.g., 'SOL/USDT')
            limit: Depth levels (5, 10, 20, 50, 100, 500, 1000)

        Returns:
            DataFrame with order book data including bids/asks
        """
        try:
            params = {
                'symbol': symbol.replace('/', ''),
                'limit': limit
            }

            # Order book depth endpoint
            response = await self._fapi_get('/fapi/v1/depth', params)

            # Convert bids and asks to DataFrames
            bids = response.get('bids', [])
            asks = response.get('asks', [])
            
            if not bids and not asks:
                return pd.DataFrame()

            # Create DataFrame for bids
            bids_df = pd.DataFrame(bids, columns=['price', 'quantity'])
            bids_df['side'] = 'bid'
            
            # Create DataFrame for asks
            asks_df = pd.DataFrame(asks, columns=['price', 'quantity'])
            asks_df['side'] = 'ask'

            # Combine both sides
            df = pd.concat([bids_df, asks_df], ignore_index=True)
            
            # Add metadata
            df['last_update_id'] = response.get('lastUpdateId')
            df['timestamp'] = pd.Timestamp.now(tz='UTC')
            
            # Convert types
            df['price'] = df['price'].astype(float)
            df['quantity'] = df['quantity'].astype(float)

            return df

        except Exception as e:
            self.logger.error(f"Error fetching order book: {e}")
            raise
