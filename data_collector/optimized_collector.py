"""
Optimized Async Data Collector
High-performance concurrent data collection with connection pooling
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
import logging
from concurrent.futures import ThreadPoolExecutor
import aiohttp

from data_collector.binance_client import BinanceFuturesClient

logger = logging.getLogger(__name__)


class OptimizedDataCollector:
    """
    High-performance data collector with async operations and connection pooling
    """

    def __init__(self, config: dict):
        self.config = config
        self.client = None
        self.engine = None
        self.session_factory = None
        self.executor = ThreadPoolExecutor(max_workers=10)

    async def initialize(self):
        """Initialize async resources"""
        # Create async database engine with connection pooling
        db_config = self.config['database']
        connection_string = (
            f"postgresql+asyncpg://{db_config['user']}:{db_config['password']}@"
            f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
        )

        self.engine = create_async_engine(
            connection_string,
            pool_size=20,  # Larger pool for concurrent operations
            max_overflow=40,
            pool_pre_ping=True,
            pool_recycle=3600,  # Recycle connections every hour
            echo=False
        )

        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Initialize Binance client
        binance_config = self.config['binance']
        self.client = BinanceFuturesClient(
            api_key=binance_config.get('api_key'),
            api_secret=binance_config.get('api_secret'),
            testnet=binance_config.get('testnet', False)
        )

        logger.info("✅ Optimized collector initialized with connection pooling")

    async def collect_all_data_concurrent(self, symbol: str, start_date: datetime, end_date: datetime):
        """
        Collect all data types concurrently for maximum speed

        This method runs all data collection tasks in parallel
        """
        collection_config = self.config['collection']
        timeframes = collection_config['timeframes']
        oi_periods = collection_config['oi_periods']

        tasks = []

        # Create tasks for OHLCV data (all timeframes in parallel)
        for tf in timeframes:
            task = self.collect_ohlcv_optimized(symbol, tf, start_date, end_date)
            tasks.append(('OHLCV', tf, task))

        # Create tasks for OI data (all periods in parallel)
        for period in oi_periods:
            task = self.collect_oi_optimized(symbol, period, start_date, end_date)
            tasks.append(('OI', period, task))

        # Create tasks for other data types
        tasks.append(('Funding', None, self.collect_funding_optimized(symbol, start_date, end_date)))
        tasks.append(('Liquidations', None, self.collect_liquidations_optimized(symbol, start_date, end_date)))
        tasks.append(('LS_Ratio', None, self.collect_ls_ratio_optimized(symbol, start_date, end_date)))

        # Execute all tasks concurrently
        logger.info(f"🚀 Starting concurrent collection of {len(tasks)} data streams...")
        start_time = datetime.now()

        results = await asyncio.gather(*[task for _, _, task in tasks], return_exceptions=True)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Log results
        for i, (data_type, period, _) in enumerate(tasks):
            result = results[i]
            if isinstance(result, Exception):
                logger.error(f"❌ {data_type} {period or ''}: {result}")
            else:
                logger.info(f"✅ {data_type} {period or ''}: {result} records")

        logger.info(f"⚡ Concurrent collection completed in {duration:.2f}s")
        return results

    async def collect_ohlcv_optimized(self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime):
        """Optimized OHLCV collection with batching"""
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

                # No sleep - let rate limiter handle it
            except Exception as e:
                logger.error(f"Error fetching {symbol} {timeframe}: {e}")
                await asyncio.sleep(1)
                continue

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            final_df = final_df.drop_duplicates(subset=['timestamp'])
            final_df = final_df[final_df['timestamp'] <= end_date]

            # Batch insert with async session
            await self._batch_insert_ohlcv(final_df, symbol, timeframe)
            return len(final_df)

        return 0

    async def collect_oi_optimized(self, symbol: str, period: str, start_date: datetime, end_date: datetime):
        """Optimized OI collection"""
        all_data = []

        # Fetch data
        try:
            df = await self.client.fetch_open_interest_hist(symbol=symbol, period=period, limit=500)

            if not df.empty:
                df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
                all_data.append(df)
        except Exception as e:
            logger.error(f"Error fetching OI {symbol} {period}: {e}")
            return 0

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            final_df = final_df.drop_duplicates(subset=['timestamp'])

            await self._batch_insert_oi(final_df, symbol, period)
            return len(final_df)

        return 0

    async def collect_funding_optimized(self, symbol: str, start_date: datetime, end_date: datetime):
        """Optimized funding rate collection"""
        try:
            df = await self.client.fetch_funding_rate_history(symbol)
            df = df[(df['fundingTime'] >= start_date) & (df['fundingTime'] <= end_date)]

            if not df.empty:
                df['symbol'] = symbol
                await self._batch_insert_funding(df)
                return len(df)
        except Exception as e:
            logger.error(f"Error fetching funding rate: {e}")

        return 0

    async def collect_liquidations_optimized(self, symbol: str, start_date: datetime, end_date: datetime):
        """Optimized liquidations collection"""
        try:
            df = await self.client.fetch_liquidations(symbol, limit=1000)

            if not df.empty:
                df = df[(df['time'] >= start_date) & (df['time'] <= end_date)]
                df['symbol'] = symbol
                df = df.rename(columns={'origQty': 'quantity', 'orderId': 'order_id'})
                await self._batch_insert_liquidations(df)
                return len(df)
        except Exception as e:
            logger.error(f"Error fetching liquidations: {e}")

        return 0

    async def collect_ls_ratio_optimized(self, symbol: str, start_date: datetime, end_date: datetime):
        """Optimized long/short ratio collection"""
        oi_periods = self.config['collection']['oi_periods']
        total = 0

        for period in oi_periods:
            try:
                df = await self.client.fetch_top_trader_ratio(symbol, period=period)
                df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]

                if not df.empty:
                    df['symbol'] = symbol
                    df['period'] = period
                    df = df.rename(columns={
                        'timestamp': 'time',
                        'longShortRatio': 'long_short_ratio',
                        'longAccount': 'long_account',
                        'shortAccount': 'short_account'
                    })
                    await self._batch_insert_ls_ratio(df)
                    total += len(df)
            except Exception as e:
                logger.error(f"Error fetching LS ratio: {e}")

        return total

    async def _batch_insert_ohlcv(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """High-speed batch insert for OHLCV"""
        df = df.copy()
        df['symbol'] = symbol
        df['timeframe'] = timeframe
        df = df.rename(columns={'timestamp': 'time'})

        # Add missing columns
        for col in ['quote_volume', 'num_trades', 'taker_buy_base', 'taker_buy_quote']:
            if col not in df.columns:
                df[col] = None

        await self._execute_batch_insert('ohlcv', df)

    async def _batch_insert_oi(self, df: pd.DataFrame, symbol: str, period: str):
        """High-speed batch insert for OI"""
        df = df.copy()
        df['symbol'] = symbol
        df['period'] = period
        df = df.rename(columns={
            'timestamp': 'time',
            'sumOpenInterest': 'open_interest',
            'sumOpenInterestValue': 'open_interest_value'
        })

        await self._execute_batch_insert('open_interest', df)

    async def _batch_insert_funding(self, df: pd.DataFrame):
        """High-speed batch insert for funding rate"""
        await self._execute_batch_insert('funding_rate', df)

    async def _batch_insert_liquidations(self, df: pd.DataFrame):
        """High-speed batch insert for liquidations"""
        await self._execute_batch_insert('liquidations', df)

    async def _batch_insert_ls_ratio(self, df: pd.DataFrame):
        """High-speed batch insert for long/short ratio"""
        await self._execute_batch_insert('long_short_ratio', df)

    async def _execute_batch_insert(self, table_name: str, df: pd.DataFrame):
        """
        Execute optimized batch insert using COPY for maximum speed
        """
        if df.empty:
            return

        async with self.session_factory() as session:
            try:
                # Use pandas to_sql with method='multi' for batch insert
                # Note: For even faster inserts, consider using COPY command
                await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    lambda: df.to_sql(
                        table_name,
                        self.engine.sync_engine,
                        if_exists='append',
                        index=False,
                        method='multi',
                        chunksize=1000
                    )
                )
                logger.debug(f"Inserted {len(df)} records into {table_name}")
            except Exception as e:
                logger.error(f"Batch insert error for {table_name}: {e}")
                raise

    @staticmethod
    def _timeframe_to_minutes(tf: str) -> int:
        """Convert timeframe string to minutes"""
        mapping = {'1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440}
        return mapping.get(tf, 5)

    async def cleanup(self):
        """Cleanup resources"""
        if self.engine:
            await self.engine.dispose()
        if self.executor:
            self.executor.shutdown(wait=True)
        logger.info("Cleaned up resources")
