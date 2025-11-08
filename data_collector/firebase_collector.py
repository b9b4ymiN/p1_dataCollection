"""
Firebase Data Collector
Collects cryptocurrency futures data and stores in Firebase Realtime Database
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
import logging

from data_collector.binance_client import BinanceFuturesClient
from database.firebase_manager import FirebaseManager

logger = logging.getLogger(__name__)


class FirebaseDataCollector:
    """
    Data collector that uses Firebase Realtime Database for storage

    Features:
    - Concurrent data collection for all timeframes and data types
    - Automatic retry and error handling
    - Progress tracking
    - Duplicate prevention
    """

    def __init__(self, config: dict, firebase_manager: FirebaseManager):
        """
        Initialize Firebase collector

        Args:
            config: Configuration dictionary
            firebase_manager: Initialized FirebaseManager instance
        """
        self.config = config
        self.firebase = firebase_manager
        self.client = None

    async def initialize(self):
        """Initialize async resources"""
        # Initialize Binance client
        binance_config = self.config['binance']
        self.client = BinanceFuturesClient(
            api_key=binance_config.get('api_key'),
            api_secret=binance_config.get('api_secret'),
            testnet=binance_config.get('testnet', False)
        )

        logger.info("✅ Firebase collector initialized")

    async def collect_all_data_concurrent(self, symbol: str, start_date: datetime, end_date: datetime):
        """
        Collect all data types concurrently for maximum speed

        Args:
            symbol: Trading symbol (e.g., 'SOL/USDT')
            start_date: Start date for collection
            end_date: End date for collection

        Returns:
            Dictionary with collection results
        """
        collection_config = self.config['collection']
        timeframes = collection_config['timeframes']
        oi_periods = collection_config['oi_periods']

        tasks = []

        # Create tasks for OHLCV data (all timeframes in parallel)
        for tf in timeframes:
            task = self.collect_ohlcv(symbol, tf, start_date, end_date)
            tasks.append(('OHLCV', tf, task))

        # Create tasks for OI data (all periods in parallel)
        for period in oi_periods:
            task = self.collect_open_interest(symbol, period, start_date, end_date)
            tasks.append(('OI', period, task))

        # Create tasks for other data types
        tasks.append(('Funding', None, self.collect_funding_rate(symbol, start_date, end_date)))
        tasks.append(('Liquidations', None, self.collect_liquidations(symbol, start_date, end_date)))
        tasks.append(('LS_Ratio', None, self.collect_long_short_ratio(symbol, start_date, end_date)))

        # Execute all tasks concurrently
        logger.info(f"🚀 Starting concurrent collection of {len(tasks)} data streams for {symbol}...")
        start_time = datetime.now()

        results = await asyncio.gather(*[task for _, _, task in tasks], return_exceptions=True)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Log results
        summary = {}
        for i, (data_type, period, _) in enumerate(tasks):
            result = results[i]
            key = f"{data_type}_{period}" if period else data_type

            if isinstance(result, Exception):
                logger.error(f"❌ {data_type} {period or ''}: {result}")
                summary[key] = {'status': 'error', 'error': str(result)}
            else:
                logger.info(f"✅ {data_type} {period or ''}: {result} records")
                summary[key] = {'status': 'success', 'records': result}

        logger.info(f"⚡ Concurrent collection completed in {duration:.2f}s")
        return summary

    async def collect_ohlcv(self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime) -> int:
        """
        Collect OHLCV data and save to Firebase

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., '5m', '1h')
            start_date: Start date
            end_date: End date

        Returns:
            Number of records collected
        """
        all_data = []
        current_date = start_date

        # Calculate optimal batch size
        tf_minutes = self._timeframe_to_minutes(timeframe)
        batch_size = min(1500, int((1440 / tf_minutes) * 30))

        while current_date < end_date:
            since = int(current_date.timestamp() * 1000)

            try:
                df = await self.client.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=since,
                    limit=batch_size
                )

                if df.empty:
                    break

                all_data.append(df)
                last_timestamp = df['timestamp'].iloc[-1]
                current_date = last_timestamp + timedelta(minutes=tf_minutes)

            except Exception as e:
                logger.error(f"Error fetching {symbol} {timeframe}: {e}")
                await asyncio.sleep(1)
                continue

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            final_df = final_df.drop_duplicates(subset=['timestamp'])
            final_df = final_df[final_df['timestamp'] <= end_date]

            # Save to Firebase
            await self.firebase.save_ohlcv_batch(final_df, symbol, timeframe)
            return len(final_df)

        return 0

    async def collect_open_interest(self, symbol: str, period: str, start_date: datetime, end_date: datetime) -> int:
        """
        Collect Open Interest data and save to Firebase

        Args:
            symbol: Trading symbol
            period: Period (e.g., '5m', '1h')
            start_date: Start date
            end_date: End date

        Returns:
            Number of records collected
        """
        try:
            df = await self.client.fetch_open_interest_hist(symbol=symbol, period=period, limit=500)

            if not df.empty:
                df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]

                # Save to Firebase
                await self.firebase.save_open_interest_batch(df, symbol, period)
                return len(df)
        except Exception as e:
            logger.error(f"Error fetching OI {symbol} {period}: {e}")

        return 0

    async def collect_funding_rate(self, symbol: str, start_date: datetime, end_date: datetime) -> int:
        """
        Collect Funding Rate data and save to Firebase

        Args:
            symbol: Trading symbol
            start_date: Start date
            end_date: End date

        Returns:
            Number of records collected
        """
        try:
            df = await self.client.fetch_funding_rate_history(symbol)

            if not df.empty:
                df = df[(df['fundingTime'] >= start_date) & (df['fundingTime'] <= end_date)]

                # Save to Firebase
                await self.firebase.save_funding_rate_batch(df, symbol)
                return len(df)
        except Exception as e:
            logger.error(f"Error fetching funding rate {symbol}: {e}")

        return 0

    async def collect_liquidations(self, symbol: str, start_date: datetime, end_date: datetime) -> int:
        """
        Collect Liquidations data and save to Firebase

        Args:
            symbol: Trading symbol
            start_date: Start date
            end_date: End date

        Returns:
            Number of records collected
        """
        try:
            df = await self.client.fetch_liquidations(symbol, limit=1000)

            if not df.empty:
                df = df[(df['time'] >= start_date) & (df['time'] <= end_date)]

                # Save to Firebase
                await self.firebase.save_liquidations_batch(df, symbol)
                return len(df)
        except Exception as e:
            logger.error(f"Error fetching liquidations {symbol}: {e}")

        return 0

    async def collect_long_short_ratio(self, symbol: str, start_date: datetime, end_date: datetime) -> int:
        """
        Collect Long/Short Ratio data and save to Firebase

        Args:
            symbol: Trading symbol
            start_date: Start date
            end_date: End date

        Returns:
            Number of records collected
        """
        oi_periods = self.config['collection']['oi_periods']
        total = 0

        for period in oi_periods:
            try:
                df = await self.client.fetch_top_trader_ratio(symbol, period=period)

                if not df.empty:
                    df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]

                    # Save to Firebase
                    await self.firebase.save_long_short_ratio_batch(df, symbol, period)
                    total += len(df)
            except Exception as e:
                logger.error(f"Error fetching LS ratio {symbol} {period}: {e}")

        return total

    @staticmethod
    def _timeframe_to_minutes(tf: str) -> int:
        """Convert timeframe string to minutes"""
        mapping = {'1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440}
        return mapping.get(tf, 5)

    async def cleanup(self):
        """Cleanup resources"""
        self.firebase.cleanup()
        logger.info("Firebase collector cleaned up")
