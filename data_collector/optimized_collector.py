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
from sqlalchemy import create_engine as create_sync_engine
from urllib.parse import quote_plus
import logging
from concurrent.futures import ThreadPoolExecutor
import aiohttp
from sqlalchemy.exc import IntegrityError

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
        # URL-encode username/password to support special characters
        user_enc = quote_plus(db_config['user'])
        password_enc = quote_plus(db_config['password'])

        connection_string = (
            f"postgresql+asyncpg://{user_enc}:{password_enc}@"
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

        # Create a separate synchronous engine for pandas.to_sql operations
        # Pandas uses synchronous DB drivers; running to_sql in a threadpool
        # against a sync engine avoids async/sync interoperability errors
        # such as "greenlet_spawn has not been called".
        sync_connection_string = (
            f"postgresql+psycopg2://{user_enc}:{password_enc}@"
            f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
        )
        self.sync_engine = create_sync_engine(sync_connection_string, pool_size=20, max_overflow=40)

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
        
        # Add order book collection if enabled
        if collection_config.get('collect_order_book', False):
            tasks.append(('OrderBook', None, self.collect_order_book_optimized(symbol, start_date, end_date)))

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
            # Support both API-style 'fundingTime' and normalized 'funding_time'
            if 'fundingTime' in df.columns:
                df['funding_time'] = pd.to_datetime(df['fundingTime'])
            if 'funding_time' in df.columns:
                df = df[(df['funding_time'] >= start_date) & (df['funding_time'] <= end_date)]
            else:
                # Fallback: try original column (if present)
                if 'fundingTime' in df.columns:
                    df = df[(df['fundingTime'] >= start_date) & (df['fundingTime'] <= end_date)]
                else:
                    df = pd.DataFrame()

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

    async def collect_order_book_optimized(self, symbol: str, start_date: datetime, end_date: datetime):
        """
        Optimized order book collection
        
        Note: Order book data is high-frequency. This collects periodic snapshots
        rather than continuous streaming (which would be handled by WebSocket).
        """
        order_book_config = self.config['collection'].get('order_book', {})
        limit = order_book_config.get('limit', 100)
        interval_seconds = order_book_config.get('interval_seconds', 60)  # Default: 1 snapshot per minute
        
        total = 0
        
        try:
            # For historical range, collect snapshots at regular intervals
            current_time = start_date
            
            while current_time <= end_date:
                try:
                    df = await self.client.fetch_order_book(symbol, limit=limit)
                    
                    if not df.empty:
                        df['symbol'] = symbol
                        # Use the current_time for historical consistency
                        df['time'] = current_time
                        await self._batch_insert_order_book(df)
                        total += len(df)
                    
                    # Move to next interval
                    current_time += timedelta(seconds=interval_seconds)
                    
                    # Rate limiting
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.warning(f"Error fetching order book snapshot at {current_time}: {e}")
                    current_time += timedelta(seconds=interval_seconds)
                    continue
            
        except Exception as e:
            logger.error(f"Error in order book collection: {e}")
        
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
        df = df.copy()
        # Normalize columns to match DB schema: funding_time, symbol, funding_rate, mark_price
        if 'fundingTime' in df.columns and 'funding_time' not in df.columns:
            df['funding_time'] = pd.to_datetime(df['fundingTime'])
        if 'fundingRate' in df.columns and 'funding_rate' not in df.columns:
            df['funding_rate'] = df['fundingRate'].astype(float)
        if 'markPrice' in df.columns and 'mark_price' not in df.columns:
            df['mark_price'] = df['markPrice']

        # Ensure required columns exist
        for col in ['funding_time', 'symbol', 'funding_rate', 'mark_price']:
            if col not in df.columns:
                df[col] = None

        # Rename to DB-friendly names if necessary (to_sql will use these column names)
        df = df.rename(columns={
            'funding_time': 'funding_time',
            'funding_rate': 'funding_rate',
            'mark_price': 'mark_price'
        })

        # Remove any raw/camelCase API columns to avoid duplicate columns in SQL INSERT
        for raw_col in ('fundingTime', 'fundingRate', 'markPrice'):
            if raw_col in df.columns:
                df.drop(columns=[raw_col], inplace=True)

        await self._execute_batch_insert('funding_rate', df)

    async def _batch_insert_liquidations(self, df: pd.DataFrame):
        """High-speed batch insert for liquidations"""
        await self._execute_batch_insert('liquidations', df)

    async def _batch_insert_ls_ratio(self, df: pd.DataFrame):
        """High-speed batch insert for long/short ratio"""
        await self._execute_batch_insert('long_short_ratio', df)

    async def _batch_insert_order_book(self, df: pd.DataFrame):
        """High-speed batch insert for order book"""
        df = df.copy()
        
        # Ensure all required columns are present
        required_columns = ['time', 'symbol', 'side', 'price', 'quantity', 'last_update_id']
        for col in required_columns:
            if col not in df.columns:
                logger.warning(f"Missing column {col} in order book data")
                df[col] = None
        
        await self._execute_batch_insert('order_book', df)

    async def _execute_batch_insert(self, table_name: str, df: pd.DataFrame):
        """
        Execute optimized batch insert using COPY for maximum speed
        """
        if df.empty:
            return

        # Restrict DataFrame to only the columns that exist in the DB schema for the target table.
        # This prevents accidental INSERT attempts for unexpected API fields (e.g. CamelCase or 3rd-party fields)
        # which cause UndefinedColumn errors.
        allowed_columns_map = {
            'ohlcv': [
                'time', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 'volume',
                'quote_volume', 'num_trades', 'taker_buy_base', 'taker_buy_quote'
            ],
            'open_interest': ['time', 'symbol', 'period', 'open_interest', 'open_interest_value'],
            'funding_rate': ['funding_time', 'symbol', 'funding_rate', 'mark_price'],
            'liquidations': ['time', 'symbol', 'side', 'price', 'quantity', 'order_id'],
            'long_short_ratio': ['time', 'symbol', 'period', 'long_short_ratio', 'long_account', 'short_account'],
            'order_book': ['time', 'symbol', 'side', 'price', 'quantity', 'last_update_id']
        }

        allowed = allowed_columns_map.get(table_name)
        if allowed:
            # Keep only columns that are present in the DataFrame and in the allowed list
            cols_to_keep = [c for c in allowed if c in df.columns]
            df = df[cols_to_keep].copy()

        # Remove duplicate rows within the batch based on likely primary-key columns
        pk_map = {
            'ohlcv': ['time', 'symbol', 'timeframe'],
            'open_interest': ['time', 'symbol', 'period'],
            'funding_rate': ['funding_time', 'symbol'],
            'liquidations': ['time', 'symbol', 'order_id'],
            'long_short_ratio': ['time', 'symbol', 'period'],
            'order_book': ['time', 'symbol', 'side', 'price']
        }

        pk_cols = pk_map.get(table_name, [])
        present_pk_cols = [c for c in pk_cols if c in df.columns]
        if present_pk_cols:
            df = df.drop_duplicates(subset=present_pk_cols, keep='first')

        # If possible, query DB for existing primary-key tuples inside this batch time/window
        # and filter them out to avoid UniqueViolation on bulk insert.
        if present_pk_cols:
            try:
                # Build where clauses for time range and symbol set to limit scan
                where_clauses = []
                params = {}
                if 'time' in present_pk_cols or 'funding_time' in present_pk_cols:
                    time_col = 'time' if 'time' in present_pk_cols else 'funding_time'
                    min_time = df[time_col].min()
                    max_time = df[time_col].max()
                    where_clauses.append(f"{time_col} >= :min_time AND {time_col} <= :max_time")
                    params['min_time'] = min_time
                    params['max_time'] = max_time

                if 'symbol' in present_pk_cols and 'symbol' in df.columns:
                    symbols = df['symbol'].unique().tolist()
                    # Use an array parameter for symbols
                    where_clauses.append("symbol = ANY(:symbols)")
                    params['symbols'] = symbols

                if where_clauses:
                    where_sql = ' AND '.join(where_clauses)
                    cols_select = ', '.join(present_pk_cols)
                    query = text(f"SELECT {cols_select} FROM {table_name} WHERE {where_sql}")

                    async with self.session_factory() as session:
                        result = await session.execute(query, params)
                        existing = result.fetchall()

                    if existing:
                        # existing is list of tuples in same order as present_pk_cols
                        existing_set = set(existing)
                        # Build boolean mask to keep rows not present in DB
                        tuples = list(df[present_pk_cols].itertuples(index=False, name=None))
                        mask = [t not in existing_set for t in tuples]
                        df = df[mask]
            except Exception:
                # If anything goes wrong querying DB, continue and rely on fallback handling below
                logger.debug(f"Could not pre-check existing keys for {table_name}; will rely on safe insert fallback")

        if df.empty:
            logger.debug(f"No new rows to insert into {table_name} after dedupe/existing-filter")
            return

        # Insert in chunks and provide a fallback path to avoid bulk UniqueViolation failures.
        chunk_size = 500
        try:
            for start in range(0, len(df), chunk_size):
                chunk = df.iloc[start:start + chunk_size]
                await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    lambda c=chunk: c.to_sql(
                        table_name,
                        self.sync_engine,
                        if_exists='append',
                        index=False,
                        method='multi',
                        chunksize=250
                    )
                )

            logger.debug(f"Inserted {len(df)} records into {table_name}")
        except IntegrityError as ie:
            # Fall back to inserting row-by-row and ignore duplicates that conflict
            logger.warning(f"IntegrityError during bulk insert on {table_name}: {ie}; falling back to row-wise insert")
            for _, row in df.iterrows():
                try:
                    single_df = pd.DataFrame([row])
                    await asyncio.get_event_loop().run_in_executor(
                        self.executor,
                        lambda c=single_df: c.to_sql(
                            table_name,
                            self.sync_engine,
                            if_exists='append',
                            index=False,
                            method='multi'
                        )
                    )
                except IntegrityError:
                    # Likely a duplicate; ignore
                    continue
                except Exception as e:
                    logger.error(f"Row-wise insert failed for {table_name}: {e}")
            logger.info(f"Completed fallback insert for {table_name}")
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
