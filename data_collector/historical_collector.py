"""
Historical Data Collector
Collects historical data in batches and stores in database
"""

import asyncio
from datetime import datetime, timedelta
from typing import List
import pandas as pd
from sqlalchemy import create_engine
from tqdm import tqdm
import logging

from data_collector.binance_client import BinanceFuturesClient

logger = logging.getLogger(__name__)


class HistoricalDataCollector:
    """
    Collects historical data in batches and stores in database
    """

    def __init__(self, client: BinanceFuturesClient, db_engine):
        self.client = client
        self.engine = db_engine

    async def collect_ohlcv_range(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ):
        """
        Collect OHLCV data for a date range with pagination

        Args:
            symbol: Trading pair
            timeframe: Candlestick interval
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with collected data
        """
        all_data = []
        current_date = start_date

        # Determine how many candles per batch based on timeframe
        tf_minutes = self._timeframe_to_minutes(timeframe)
        candles_per_day = 1440 / tf_minutes
        batch_size = min(1500, int(candles_per_day * 30))  # Max 30 days per batch

        pbar = tqdm(total=(end_date - start_date).days, desc=f"Fetching {symbol} {timeframe}")

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

                # Move to next batch
                last_timestamp = df['timestamp'].iloc[-1]
                current_date = last_timestamp + timedelta(minutes=tf_minutes)

                days_progress = (current_date - start_date).days
                pbar.update(days_progress - pbar.n)

                # Rate limiting
                await asyncio.sleep(0.2)

            except Exception as e:
                logger.error(f"Error at {current_date}: {e}")
                await asyncio.sleep(2)
                continue

        pbar.close()

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            final_df = final_df.drop_duplicates(subset=['timestamp'])
            final_df = final_df[final_df['timestamp'] <= end_date]

            # Save to database
            self._save_ohlcv(final_df, symbol, timeframe)
            return final_df

        return pd.DataFrame()

    async def collect_oi_range(
        self,
        symbol: str,
        period: str,
        start_date: datetime,
        end_date: datetime
    ):
        """
        Collect Open Interest data for a date range

        Args:
            symbol: Trading pair
            period: OI period
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with collected data
        """
        all_data = []

        # OI data: max 500 per call
        num_batches = int((end_date - start_date).total_seconds() / (self._period_to_seconds(period) * 500)) + 1

        for i in tqdm(range(num_batches), desc=f"Fetching OI {symbol} {period}"):
            try:
                df = await self.client.fetch_open_interest_hist(
                    symbol=symbol,
                    period=period,
                    limit=500
                )

                if df.empty:
                    break

                # Filter by date range
                df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]

                if not df.empty:
                    all_data.append(df)

                await asyncio.sleep(0.3)

            except Exception as e:
                logger.error(f"Error fetching OI batch {i}: {e}")
                await asyncio.sleep(2)

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            final_df = final_df.drop_duplicates(subset=['timestamp'])

            # Save to database
            self._save_oi(final_df, symbol, period)
            return final_df

        return pd.DataFrame()

    def _save_ohlcv(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """Save OHLCV to database"""
        df = df.copy()
        df['symbol'] = symbol
        df['timeframe'] = timeframe
        df = df.rename(columns={'timestamp': 'time'})

        # Add missing columns with None values
        df['quote_volume'] = None
        df['num_trades'] = None
        df['taker_buy_base'] = None
        df['taker_buy_quote'] = None

        df.to_sql(
            'ohlcv',
            self.engine,
            if_exists='append',
            index=False,
            method='multi'
        )
        logger.info(f"Saved {len(df)} {timeframe} candles for {symbol}")

    def _save_oi(self, df: pd.DataFrame, symbol: str, period: str):
        """Save OI to database"""
        df = df.copy()
        df['symbol'] = symbol
        df['period'] = period
        df = df.rename(columns={
            'timestamp': 'time',
            'sumOpenInterest': 'open_interest',
            'sumOpenInterestValue': 'open_interest_value'
        })

        df.to_sql(
            'open_interest',
            self.engine,
            if_exists='append',
            index=False,
            method='multi'
        )
        logger.info(f"Saved {len(df)} OI records for {symbol}")

    @staticmethod
    def _timeframe_to_minutes(tf: str) -> int:
        """Convert timeframe string to minutes"""
        mapping = {'1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440}
        return mapping.get(tf, 5)

    @staticmethod
    def _period_to_seconds(period: str) -> int:
        """Convert period to seconds"""
        mapping = {'5m': 300, '15m': 900, '1h': 3600, '4h': 14400}
        return mapping.get(period, 300)
