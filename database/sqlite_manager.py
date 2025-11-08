"""
SQLite Database Manager
Lightweight local database for cryptocurrency futures data
"""

import sqlite3
import pandas as pd
import logging
from datetime import datetime
from typing import Optional, List
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os

logger = logging.getLogger(__name__)


class SQLiteManager:
    """
    SQLite Database Manager for cryptocurrency futures data

    Lightweight alternative to PostgreSQL for local development and small datasets.
    Uses a single SQLite file with separate tables for each data type.
    """

    def __init__(self, database_path: str = "data/futures_data.db"):
        """
        Initialize SQLite connection

        Args:
            database_path: Path to SQLite database file
        """
        self.database_path = database_path
        self.executor = ThreadPoolExecutor(max_workers=5)
        self._initialized = False

        # Create database directory if it doesn't exist
        os.makedirs(os.path.dirname(database_path), exist_ok=True)

    def initialize(self):
        """Initialize SQLite database and create tables"""
        try:
            if not self._initialized:
                conn = sqlite3.connect(self.database_path)
                cursor = conn.cursor()

                # Create tables
                self._create_tables(cursor)

                conn.commit()
                conn.close()

                self._initialized = True
                logger.info(f"✅ SQLite initialized: {self.database_path}")
        except Exception as e:
            logger.error(f"SQLite initialization error: {e}")
            raise

    def _create_tables(self, cursor):
        """Create all required tables"""

        # OHLCV table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                time TIMESTAMP NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                quote_volume REAL,
                num_trades INTEGER,
                taker_buy_base REAL,
                taker_buy_quote REAL,
                PRIMARY KEY (time, symbol, timeframe)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_time ON ohlcv (symbol, time)")

        # Open Interest table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS open_interest (
                time TIMESTAMP NOT NULL,
                symbol TEXT NOT NULL,
                period TEXT NOT NULL,
                open_interest REAL,
                open_interest_value REAL,
                PRIMARY KEY (time, symbol, period)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_oi_symbol_time ON open_interest (symbol, time)")

        # Funding Rate table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS funding_rate (
                funding_time TIMESTAMP NOT NULL,
                symbol TEXT NOT NULL,
                funding_rate REAL,
                mark_price REAL,
                PRIMARY KEY (funding_time, symbol)
            )
        """)

        # Liquidations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS liquidations (
                time TIMESTAMP NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT,
                price REAL,
                quantity REAL,
                order_id INTEGER UNIQUE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_liq_symbol_time ON liquidations (symbol, time)")

        # Long/Short Ratio table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS long_short_ratio (
                time TIMESTAMP NOT NULL,
                symbol TEXT NOT NULL,
                period TEXT NOT NULL,
                long_short_ratio REAL,
                long_account REAL,
                short_account REAL,
                PRIMARY KEY (time, symbol, period)
            )
        """)

        # Order Book table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_book (
                time TIMESTAMP NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                level INTEGER NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                PRIMARY KEY (time, symbol, side, level)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ob_symbol_time ON order_book (symbol, time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ob_side_level ON order_book (side, level)")

    # =============================================================================
    # OHLCV Operations
    # =============================================================================

    async def save_ohlcv_batch(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """Save OHLCV data to SQLite"""
        if df.empty:
            return

        df = df.copy()
        df['symbol'] = symbol
        df['timeframe'] = timeframe
        df = df.rename(columns={'timestamp': 'time'})

        # Ensure all required columns exist
        for col in ['quote_volume', 'num_trades', 'taker_buy_base', 'taker_buy_quote']:
            if col not in df.columns:
                df[col] = None

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            lambda: df.to_sql('ohlcv', sqlite3.connect(self.database_path),
                             if_exists='append', index=False)
        )

        logger.info(f"✅ Saved {len(df)} OHLCV records to SQLite: {symbol} {timeframe}")

    async def get_ohlcv(self, symbol: str, timeframe: str,
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None) -> pd.DataFrame:
        """Retrieve OHLCV data from SQLite"""
        query = f"SELECT * FROM ohlcv WHERE symbol = '{symbol}' AND timeframe = '{timeframe}'"

        if start_time:
            query += f" AND time >= '{start_time.isoformat()}'"
        if end_time:
            query += f" AND time <= '{end_time.isoformat()}'"

        query += " ORDER BY time"

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            self.executor,
            lambda: pd.read_sql_query(query, sqlite3.connect(self.database_path))
        )

        if not df.empty:
            df['time'] = pd.to_datetime(df['time'])

        return df

    # =============================================================================
    # Open Interest Operations
    # =============================================================================

    async def save_open_interest_batch(self, df: pd.DataFrame, symbol: str, period: str):
        """Save Open Interest data to SQLite"""
        if df.empty:
            return

        df = df.copy()
        df['symbol'] = symbol
        df['period'] = period
        df = df.rename(columns={
            'timestamp': 'time',
            'sumOpenInterest': 'open_interest',
            'sumOpenInterestValue': 'open_interest_value'
        })

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            lambda: df.to_sql('open_interest', sqlite3.connect(self.database_path),
                             if_exists='append', index=False)
        )

        logger.info(f"✅ Saved {len(df)} OI records to SQLite: {symbol} {period}")

    async def get_open_interest(self, symbol: str, period: str,
                                start_time: Optional[datetime] = None,
                                end_time: Optional[datetime] = None) -> pd.DataFrame:
        """Retrieve Open Interest data from SQLite"""
        query = f"SELECT * FROM open_interest WHERE symbol = '{symbol}' AND period = '{period}'"

        if start_time:
            query += f" AND time >= '{start_time.isoformat()}'"
        if end_time:
            query += f" AND time <= '{end_time.isoformat()}'"

        query += " ORDER BY time"

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            self.executor,
            lambda: pd.read_sql_query(query, sqlite3.connect(self.database_path))
        )

        if not df.empty:
            df['time'] = pd.to_datetime(df['time'])

        return df

    # =============================================================================
    # Funding Rate Operations
    # =============================================================================

    async def save_funding_rate_batch(self, df: pd.DataFrame, symbol: str):
        """Save Funding Rate data to SQLite"""
        if df.empty:
            return

        df = df.copy()
        df['symbol'] = symbol

        # Rename columns if needed
        if 'fundingTime' in df.columns:
            df = df.rename(columns={'fundingTime': 'funding_time'})
        if 'fundingRate' in df.columns:
            df = df.rename(columns={'fundingRate': 'funding_rate'})
        if 'markPrice' in df.columns:
            df = df.rename(columns={'markPrice': 'mark_price'})

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            lambda: df.to_sql('funding_rate', sqlite3.connect(self.database_path),
                             if_exists='append', index=False)
        )

        logger.info(f"✅ Saved {len(df)} funding rate records to SQLite: {symbol}")

    async def get_funding_rate(self, symbol: str,
                               start_time: Optional[datetime] = None,
                               end_time: Optional[datetime] = None) -> pd.DataFrame:
        """Retrieve Funding Rate data from SQLite"""
        query = f"SELECT * FROM funding_rate WHERE symbol = '{symbol}'"

        if start_time:
            query += f" AND funding_time >= '{start_time.isoformat()}'"
        if end_time:
            query += f" AND funding_time <= '{end_time.isoformat()}'"

        query += " ORDER BY funding_time"

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            self.executor,
            lambda: pd.read_sql_query(query, sqlite3.connect(self.database_path))
        )

        if not df.empty:
            df['funding_time'] = pd.to_datetime(df['funding_time'])

        return df

    # =============================================================================
    # Liquidations Operations
    # =============================================================================

    async def save_liquidations_batch(self, df: pd.DataFrame, symbol: str):
        """Save Liquidations data to SQLite"""
        if df.empty:
            return

        df = df.copy()
        df['symbol'] = symbol

        # Rename columns if needed
        if 'origQty' in df.columns:
            df = df.rename(columns={'origQty': 'quantity'})
        if 'orderId' in df.columns:
            df = df.rename(columns={'orderId': 'order_id'})

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            lambda: df.to_sql('liquidations', sqlite3.connect(self.database_path),
                             if_exists='append', index=False)
        )

        logger.info(f"✅ Saved {len(df)} liquidation records to SQLite: {symbol}")

    async def get_liquidations(self, symbol: str,
                               start_time: Optional[datetime] = None,
                               end_time: Optional[datetime] = None) -> pd.DataFrame:
        """Retrieve Liquidations data from SQLite"""
        query = f"SELECT * FROM liquidations WHERE symbol = '{symbol}'"

        if start_time:
            query += f" AND time >= '{start_time.isoformat()}'"
        if end_time:
            query += f" AND time <= '{end_time.isoformat()}'"

        query += " ORDER BY time"

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            self.executor,
            lambda: pd.read_sql_query(query, sqlite3.connect(self.database_path))
        )

        if not df.empty:
            df['time'] = pd.to_datetime(df['time'])

        return df

    # =============================================================================
    # Long/Short Ratio Operations
    # =============================================================================

    async def save_long_short_ratio_batch(self, df: pd.DataFrame, symbol: str, period: str):
        """Save Long/Short Ratio data to SQLite"""
        if df.empty:
            return

        df = df.copy()
        df['symbol'] = symbol
        df['period'] = period

        # Rename columns if needed
        if 'timestamp' in df.columns:
            df = df.rename(columns={'timestamp': 'time'})
        if 'longShortRatio' in df.columns:
            df = df.rename(columns={
                'longShortRatio': 'long_short_ratio',
                'longAccount': 'long_account',
                'shortAccount': 'short_account'
            })

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            lambda: df.to_sql('long_short_ratio', sqlite3.connect(self.database_path),
                             if_exists='append', index=False)
        )

        logger.info(f"✅ Saved {len(df)} L/S ratio records to SQLite: {symbol} {period}")

    async def get_long_short_ratio(self, symbol: str, period: str,
                                    start_time: Optional[datetime] = None,
                                    end_time: Optional[datetime] = None) -> pd.DataFrame:
        """Retrieve Long/Short Ratio data from SQLite"""
        query = f"SELECT * FROM long_short_ratio WHERE symbol = '{symbol}' AND period = '{period}'"

        if start_time:
            query += f" AND time >= '{start_time.isoformat()}'"
        if end_time:
            query += f" AND time <= '{end_time.isoformat()}'"

        query += " ORDER BY time"

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            self.executor,
            lambda: pd.read_sql_query(query, sqlite3.connect(self.database_path))
        )

        if not df.empty:
            df['time'] = pd.to_datetime(df['time'])

        return df

    # =============================================================================
    # Order Book Operations
    # =============================================================================

    async def save_order_book_batch(self, df: pd.DataFrame, symbol: str):
        """
        Save Order Book snapshot to SQLite

        Args:
            df: DataFrame with order book data
            symbol: Trading symbol
        """
        if df.empty:
            return

        df = df.copy()
        df['symbol'] = symbol

        # Rename timestamp column if exists
        if 'timestamp' in df.columns:
            df = df.rename(columns={'timestamp': 'time'})

        # Ensure required columns
        required_cols = ['time', 'symbol', 'side', 'level', 'price', 'quantity']
        df = df[required_cols]

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            lambda: df.to_sql('order_book', sqlite3.connect(self.database_path),
                             if_exists='append', index=False)
        )

        logger.info(f"✅ Saved {len(df)} order book records to SQLite: {symbol}")

    async def get_order_book(self, symbol: str,
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None,
                             limit_levels: int = 10) -> pd.DataFrame:
        """
        Retrieve Order Book snapshots from SQLite

        Args:
            symbol: Trading symbol
            start_time: Start datetime
            end_time: End datetime
            limit_levels: Max levels to retrieve per side (default 10)

        Returns:
            DataFrame with order book data
        """
        query = f"SELECT * FROM order_book WHERE symbol = '{symbol}'"

        if start_time:
            query += f" AND time >= '{start_time.isoformat()}'"
        if end_time:
            query += f" AND time <= '{end_time.isoformat()}'"

        # Limit levels
        query += f" AND level < {limit_levels}"
        query += " ORDER BY time, side, level"

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            self.executor,
            lambda: pd.read_sql_query(query, sqlite3.connect(self.database_path))
        )

        if not df.empty:
            df['time'] = pd.to_datetime(df['time'])

        return df

    async def get_latest_order_book(self, symbol: str, limit_levels: int = 10) -> pd.DataFrame:
        """
        Get the most recent order book snapshot

        Args:
            symbol: Trading symbol
            limit_levels: Max levels to retrieve per side

        Returns:
            DataFrame with latest order book
        """
        query = f"""
            SELECT * FROM order_book
            WHERE symbol = '{symbol}'
            AND time = (SELECT MAX(time) FROM order_book WHERE symbol = '{symbol}')
            AND level < {limit_levels}
            ORDER BY side, level
        """

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            self.executor,
            lambda: pd.read_sql_query(query, sqlite3.connect(self.database_path))
        )

        if not df.empty:
            df['time'] = pd.to_datetime(df['time'])

        return df

    # =============================================================================
    # Utility Methods
    # =============================================================================

    async def delete_data(self, symbol: str, data_type: Optional[str] = None):
        """Delete data from SQLite"""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        if data_type:
            cursor.execute(f"DELETE FROM {data_type} WHERE symbol = ?", (symbol,))
        else:
            # Delete from all tables
            for table in ['ohlcv', 'open_interest', 'funding_rate', 'liquidations', 'long_short_ratio']:
                cursor.execute(f"DELETE FROM {table} WHERE symbol = ?", (symbol,))

        conn.commit()
        conn.close()

        logger.info(f"🗑️ Deleted {data_type or 'all'} data for {symbol}")

    async def get_all_symbols(self) -> List[str]:
        """Get list of all symbols in database"""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM ohlcv")
        symbols = [row[0] for row in cursor.fetchall()]
        conn.close()
        return symbols

    def cleanup(self):
        """Cleanup resources"""
        if self.executor:
            self.executor.shutdown(wait=True)
        logger.info("SQLite manager cleaned up")

    def get_database_size(self) -> float:
        """Get database file size in MB"""
        if os.path.exists(self.database_path):
            size_bytes = os.path.getsize(self.database_path)
            return size_bytes / (1024 * 1024)
        return 0.0

    def vacuum(self):
        """Optimize database (reclaim space)"""
        conn = sqlite3.connect(self.database_path)
        conn.execute("VACUUM")
        conn.close()
        logger.info("✅ SQLite database optimized (VACUUM)")
