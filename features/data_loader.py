"""
Data Loader: Bridge between Phase 1 (Database) and Phase 2 (Feature Engineering)

This module loads data from TimescaleDB tables and merges them into a single
DataFrame ready for feature engineering.
"""

import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class MarketDataLoader:
    """
    Loads market data from TimescaleDB and prepares it for feature engineering
    
    This bridges Phase 1 (data collection) with Phase 2 (feature engineering)
    """
    
    def __init__(self, db_config: dict):
        """
        Initialize database connection
        
        Args:
            db_config: Dictionary with keys: host, port, database, user, password
        """
        from urllib.parse import quote_plus
        
        user_enc = quote_plus(db_config['user'])
        password_enc = quote_plus(db_config['password'])
        
        connection_string = (
            f"postgresql://{user_enc}:{password_enc}@"
            f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
        )
        
        self.engine = create_engine(connection_string)
        logger.info("✅ Database connection established")
    
    def load_ohlcv(
        self, 
        symbol: str, 
        timeframe: str = '5m',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load OHLCV data from database
        
        Returns:
            DataFrame with columns: time, open, high, low, close, volume, etc.
        """
        query = """
            SELECT 
                time,
                open,
                high,
                low,
                close,
                volume,
                quote_volume,
                num_trades,
                taker_buy_base,
                taker_buy_quote
            FROM ohlcv
            WHERE symbol = :symbol
                AND timeframe = :timeframe
        """
        
        params = {'symbol': symbol, 'timeframe': timeframe}
        
        if start_date:
            query += " AND time >= :start_date"
            params['start_date'] = start_date
        
        if end_date:
            query += " AND time <= :end_date"
            params['end_date'] = end_date
        
        query += " ORDER BY time ASC"
        
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
        
        df['time'] = pd.to_datetime(df['time'])
        logger.info(f"Loaded {len(df)} OHLCV records for {symbol} {timeframe}")
        
        return df
    
    def load_open_interest(
        self,
        symbol: str,
        period: str = '5m',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load Open Interest data
        
        Returns:
            DataFrame with columns: time, open_interest, open_interest_value
        """
        query = """
            SELECT 
                time,
                open_interest,
                open_interest_value
            FROM open_interest
            WHERE symbol = :symbol
                AND period = :period
        """
        
        params = {'symbol': symbol, 'period': period}
        
        if start_date:
            query += " AND time >= :start_date"
            params['start_date'] = start_date
        
        if end_date:
            query += " AND time <= :end_date"
            params['end_date'] = end_date
        
        query += " ORDER BY time ASC"
        
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
        
        df['time'] = pd.to_datetime(df['time'])
        logger.info(f"Loaded {len(df)} OI records for {symbol}")
        
        return df
    
    def load_funding_rate(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load Funding Rate data
        
        Returns:
            DataFrame with columns: funding_time, funding_rate, mark_price
        """
        query = """
            SELECT 
                funding_time as time,
                funding_rate,
                mark_price
            FROM funding_rate
            WHERE symbol = :symbol
        """
        
        params = {'symbol': symbol}
        
        if start_date:
            query += " AND funding_time >= :start_date"
            params['start_date'] = start_date
        
        if end_date:
            query += " AND funding_time <= :end_date"
            params['end_date'] = end_date
        
        query += " ORDER BY funding_time ASC"
        
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
        
        df['time'] = pd.to_datetime(df['time'])
        logger.info(f"Loaded {len(df)} funding rate records for {symbol}")
        
        return df
    
    def load_liquidations(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load Liquidation data
        
        Returns:
            DataFrame with columns: time, side, price, quantity
        """
        query = """
            SELECT 
                time,
                side,
                price,
                quantity,
                order_id
            FROM liquidations
            WHERE symbol = :symbol
        """
        
        params = {'symbol': symbol}
        
        if start_date:
            query += " AND time >= :start_date"
            params['start_date'] = start_date
        
        if end_date:
            query += " AND time <= :end_date"
            params['end_date'] = end_date
        
        query += " ORDER BY time ASC"
        
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
        
        df['time'] = pd.to_datetime(df['time'])
        logger.info(f"Loaded {len(df)} liquidation records for {symbol}")
        
        return df
    
    def load_long_short_ratio(
        self,
        symbol: str,
        period: str = '5m',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load Long/Short Ratio data
        
        Returns:
            DataFrame with columns: time, long_short_ratio, long_account, short_account
        """
        query = """
            SELECT 
                time,
                long_short_ratio,
                long_account,
                short_account
            FROM long_short_ratio
            WHERE symbol = :symbol
                AND period = :period
        """
        
        params = {'symbol': symbol, 'period': period}
        
        if start_date:
            query += " AND time >= :start_date"
            params['start_date'] = start_date
        
        if end_date:
            query += " AND time <= :end_date"
            params['end_date'] = end_date
        
        query += " ORDER BY time ASC"
        
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
        
        df['time'] = pd.to_datetime(df['time'])
        logger.info(f"Loaded {len(df)} L/S ratio records for {symbol}")
        
        return df
    
    def load_all_data(
        self,
        symbol: str,
        timeframe: str = '5m',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load and merge all data sources into a single DataFrame
        
        This is the main function that prepares data for Phase 2 feature engineering
        
        Args:
            symbol: Trading pair (e.g., 'SOL/USDT')
            timeframe: OHLCV timeframe (5m, 15m, 1h, etc.)
            start_date: Start date for data loading
            end_date: End date for data loading
        
        Returns:
            Merged DataFrame with all data aligned by timestamp
        """
        logger.info("=" * 60)
        logger.info(f"Loading market data for {symbol} ({timeframe})")
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info("=" * 60)
        
        # Load primary data (OHLCV)
        df = self.load_ohlcv(symbol, timeframe, start_date, end_date)
        df = df.rename(columns={'time': 'timestamp'})
        df = df.set_index('timestamp')
        
        # Load and merge Open Interest
        oi_df = self.load_open_interest(symbol, timeframe, start_date, end_date)
        oi_df = oi_df.rename(columns={'time': 'timestamp'})
        oi_df = oi_df.set_index('timestamp')
        df = df.join(oi_df, how='left')
        
        # Load and merge Funding Rate (forward fill since it's 8h intervals)
        funding_df = self.load_funding_rate(symbol, start_date, end_date)
        funding_df = funding_df.rename(columns={'time': 'timestamp'})
        funding_df = funding_df.set_index('timestamp')
        df = df.join(funding_df, how='left')
        df['funding_rate'] = df['funding_rate'].fillna(method='ffill')
        df['mark_price'] = df['mark_price'].fillna(method='ffill')
        
        # Load and merge Long/Short Ratio
        ls_df = self.load_long_short_ratio(symbol, timeframe, start_date, end_date)
        ls_df = ls_df.rename(columns={'time': 'timestamp'})
        ls_df = ls_df.set_index('timestamp')
        df = df.join(ls_df, how='left')
        
        # Aggregate liquidations (sum by timestamp)
        liq_df = self.load_liquidations(symbol, start_date, end_date)
        if not liq_df.empty:
            liq_df = liq_df.rename(columns={'time': 'timestamp'})
            
            # Separate long and short liquidations
            long_liq = liq_df[liq_df['side'] == 'SELL'].groupby('timestamp')['quantity'].sum()
            short_liq = liq_df[liq_df['side'] == 'BUY'].groupby('timestamp')['quantity'].sum()
            
            df['long_liquidation_volume'] = long_liq
            df['short_liquidation_volume'] = short_liq
            df['total_liquidation_volume'] = df['long_liquidation_volume'].fillna(0) + df['short_liquidation_volume'].fillna(0)
            df['net_liquidation'] = df['short_liquidation_volume'].fillna(0) - df['long_liquidation_volume'].fillna(0)
        
        # Reset index to have timestamp as column
        df = df.reset_index()
        
        # Fill any remaining NaN values
        df = df.fillna(method='ffill').fillna(0)
        
        logger.info(f"✅ Merged dataset ready: {len(df)} rows, {len(df.columns)} columns")
        logger.info(f"Columns: {list(df.columns)}")
        logger.info("=" * 60)
        
        return df
    
    def get_latest_data(
        self,
        symbol: str,
        timeframe: str = '5m',
        lookback_periods: int = 500
    ) -> pd.DataFrame:
        """
        Get most recent N periods of data (for live trading)
        
        Args:
            symbol: Trading pair
            timeframe: OHLCV timeframe
            lookback_periods: Number of periods to look back
        
        Returns:
            DataFrame with latest data
        """
        end_date = datetime.utcnow()
        
        # Calculate start date based on timeframe
        timeframe_minutes = {
            '1m': 1, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '4h': 240, '1d': 1440
        }
        
        minutes = timeframe_minutes.get(timeframe, 5)
        start_date = end_date - timedelta(minutes=minutes * lookback_periods)
        
        return self.load_all_data(symbol, timeframe, start_date, end_date)
