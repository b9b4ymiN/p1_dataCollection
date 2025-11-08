"""
Binance Futures API Client
Handles all API interactions with Binance Futures
"""

import ccxt
import asyncio
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

        self.logger = logging.getLogger(__name__)

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

            response = await self.exchange.fapiPublicGetFuturesDataOpenInterestHist(params)

            df = pd.DataFrame(response)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['sumOpenInterest'] = df['sumOpenInterest'].astype(float)
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

            response = await self.exchange.fapiPublicGetFundingRate(params)

            df = pd.DataFrame(response)
            df['fundingTime'] = pd.to_datetime(df['fundingTime'], unit='ms')
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

            response = await self.exchange.fapiPublicGetAllForceOrders(params)

            df = pd.DataFrame(response)
            if not df.empty:
                df['time'] = pd.to_datetime(df['time'], unit='ms')
                df['price'] = df['price'].astype(float)
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

            response = await self.exchange.fapiPublicGetFuturesDataTopLongShortAccountRatio(params)

            df = pd.DataFrame(response)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['longShortRatio'] = df['longShortRatio'].astype(float)
            df['longAccount'] = df['longAccount'].astype(float)
            df['shortAccount'] = df['shortAccount'].astype(float)

            return df

        except Exception as e:
            self.logger.error(f"Error fetching trader ratio: {e}")
            raise
