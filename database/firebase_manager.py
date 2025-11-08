"""
Firebase Realtime Database Manager
Handles all Firebase database operations for cryptocurrency futures data
"""

import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json

logger = logging.getLogger(__name__)


class FirebaseManager:
    """
    Firebase Realtime Database Manager for cryptocurrency futures data

    Data Structure:
    /futures_data/
      /{symbol}/
        /ohlcv/
          /{timeframe}/
            /{timestamp}/
              {open, high, low, close, volume, ...}
        /open_interest/
          /{period}/
            /{timestamp}/
              {open_interest, open_interest_value}
        /funding_rate/
          /{timestamp}/
            {funding_rate, mark_price}
        /liquidations/
          /{timestamp}/
            {side, price, quantity, order_id}
        /long_short_ratio/
          /{period}/
            /{timestamp}/
              {long_short_ratio, long_account, short_account}
    """

    def __init__(self, service_account_path: str, database_url: str):
        """
        Initialize Firebase connection

        Args:
            service_account_path: Path to Firebase service account JSON file
            database_url: Firebase Realtime Database URL
        """
        self.service_account_path = service_account_path
        self.database_url = database_url
        self.executor = ThreadPoolExecutor(max_workers=10)
        self._initialized = False

    def initialize(self):
        """Initialize Firebase Admin SDK"""
        try:
            if not self._initialized:
                cred = credentials.Certificate(self.service_account_path)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': self.database_url
                })
                self._initialized = True
                logger.info(f"✅ Firebase initialized: {self.database_url}")
        except Exception as e:
            logger.error(f"Firebase initialization error: {e}")
            raise

    def _get_ref(self, path: str):
        """Get database reference for a given path"""
        return db.reference(path)

    # =============================================================================
    # OHLCV Data Operations
    # =============================================================================

    async def save_ohlcv_batch(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """
        Save OHLCV data to Firebase in batch

        Args:
            df: DataFrame with OHLCV data
            symbol: Trading symbol (e.g., 'SOL/USDT')
            timeframe: Timeframe (e.g., '5m', '1h')
        """
        if df.empty:
            return

        # Sanitize symbol for Firebase path (replace / with _)
        safe_symbol = symbol.replace('/', '_')
        base_path = f'futures_data/{safe_symbol}/ohlcv/{timeframe}'

        # Prepare batch data
        batch_data = {}
        for _, row in df.iterrows():
            timestamp = int(row['timestamp'].timestamp() * 1000)
            batch_data[str(timestamp)] = {
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']),
                'quote_volume': float(row.get('quote_volume', 0)),
                'num_trades': int(row.get('num_trades', 0)),
                'taker_buy_base': float(row.get('taker_buy_base', 0)),
                'taker_buy_quote': float(row.get('taker_buy_quote', 0)),
            }

        # Execute batch update
        await self._async_batch_update(base_path, batch_data)
        logger.info(f"✅ Saved {len(batch_data)} OHLCV records to Firebase: {symbol} {timeframe}")

    async def get_ohlcv(self, symbol: str, timeframe: str, start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None) -> pd.DataFrame:
        """
        Retrieve OHLCV data from Firebase

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            start_time: Start datetime (optional)
            end_time: End datetime (optional)

        Returns:
            DataFrame with OHLCV data
        """
        safe_symbol = symbol.replace('/', '_')
        path = f'futures_data/{safe_symbol}/ohlcv/{timeframe}'

        data = await self._async_get(path)
        if not data:
            return pd.DataFrame()

        # Convert to DataFrame
        records = []
        for timestamp, values in data.items():
            record = values.copy()
            record['timestamp'] = pd.to_datetime(int(timestamp), unit='ms')
            records.append(record)

        df = pd.DataFrame(records)

        # Filter by time range if provided
        if start_time:
            df = df[df['timestamp'] >= start_time]
        if end_time:
            df = df[df['timestamp'] <= end_time]

        return df.sort_values('timestamp')

    # =============================================================================
    # Open Interest Operations
    # =============================================================================

    async def save_open_interest_batch(self, df: pd.DataFrame, symbol: str, period: str):
        """Save Open Interest data to Firebase"""
        if df.empty:
            return

        safe_symbol = symbol.replace('/', '_')
        base_path = f'futures_data/{safe_symbol}/open_interest/{period}'

        batch_data = {}
        for _, row in df.iterrows():
            timestamp = int(row['timestamp'].timestamp() * 1000)
            batch_data[str(timestamp)] = {
                'open_interest': float(row.get('open_interest', row.get('sumOpenInterest', 0))),
                'open_interest_value': float(row.get('open_interest_value', row.get('sumOpenInterestValue', 0))),
            }

        await self._async_batch_update(base_path, batch_data)
        logger.info(f"✅ Saved {len(batch_data)} OI records to Firebase: {symbol} {period}")

    async def get_open_interest(self, symbol: str, period: str, start_time: Optional[datetime] = None,
                                end_time: Optional[datetime] = None) -> pd.DataFrame:
        """Retrieve Open Interest data from Firebase"""
        safe_symbol = symbol.replace('/', '_')
        path = f'futures_data/{safe_symbol}/open_interest/{period}'

        data = await self._async_get(path)
        if not data:
            return pd.DataFrame()

        records = []
        for timestamp, values in data.items():
            record = values.copy()
            record['timestamp'] = pd.to_datetime(int(timestamp), unit='ms')
            records.append(record)

        df = pd.DataFrame(records)

        if start_time:
            df = df[df['timestamp'] >= start_time]
        if end_time:
            df = df[df['timestamp'] <= end_time]

        return df.sort_values('timestamp')

    # =============================================================================
    # Funding Rate Operations
    # =============================================================================

    async def save_funding_rate_batch(self, df: pd.DataFrame, symbol: str):
        """Save Funding Rate data to Firebase"""
        if df.empty:
            return

        safe_symbol = symbol.replace('/', '_')
        base_path = f'futures_data/{safe_symbol}/funding_rate'

        batch_data = {}
        for _, row in df.iterrows():
            timestamp_col = 'fundingTime' if 'fundingTime' in row else 'funding_time'
            timestamp = int(row[timestamp_col].timestamp() * 1000)
            batch_data[str(timestamp)] = {
                'funding_rate': float(row.get('fundingRate', row.get('funding_rate', 0))),
                'mark_price': float(row.get('markPrice', row.get('mark_price', 0))),
            }

        await self._async_batch_update(base_path, batch_data)
        logger.info(f"✅ Saved {len(batch_data)} funding rate records to Firebase: {symbol}")

    async def get_funding_rate(self, symbol: str, start_time: Optional[datetime] = None,
                               end_time: Optional[datetime] = None) -> pd.DataFrame:
        """Retrieve Funding Rate data from Firebase"""
        safe_symbol = symbol.replace('/', '_')
        path = f'futures_data/{safe_symbol}/funding_rate'

        data = await self._async_get(path)
        if not data:
            return pd.DataFrame()

        records = []
        for timestamp, values in data.items():
            record = values.copy()
            record['fundingTime'] = pd.to_datetime(int(timestamp), unit='ms')
            records.append(record)

        df = pd.DataFrame(records)

        if start_time:
            df = df[df['fundingTime'] >= start_time]
        if end_time:
            df = df[df['fundingTime'] <= end_time]

        return df.sort_values('fundingTime')

    # =============================================================================
    # Liquidations Operations
    # =============================================================================

    async def save_liquidations_batch(self, df: pd.DataFrame, symbol: str):
        """Save Liquidations data to Firebase"""
        if df.empty:
            return

        safe_symbol = symbol.replace('/', '_')
        base_path = f'futures_data/{safe_symbol}/liquidations'

        batch_data = {}
        for _, row in df.iterrows():
            timestamp = int(row['time'].timestamp() * 1000)
            order_id = str(row.get('order_id', row.get('orderId', timestamp)))

            # Use order_id as key to prevent duplicates
            batch_data[order_id] = {
                'timestamp': timestamp,
                'side': str(row['side']),
                'price': float(row['price']),
                'quantity': float(row.get('quantity', row.get('origQty', 0))),
                'order_id': order_id,
            }

        await self._async_batch_update(base_path, batch_data)
        logger.info(f"✅ Saved {len(batch_data)} liquidation records to Firebase: {symbol}")

    async def get_liquidations(self, symbol: str, start_time: Optional[datetime] = None,
                               end_time: Optional[datetime] = None) -> pd.DataFrame:
        """Retrieve Liquidations data from Firebase"""
        safe_symbol = symbol.replace('/', '_')
        path = f'futures_data/{safe_symbol}/liquidations'

        data = await self._async_get(path)
        if not data:
            return pd.DataFrame()

        records = []
        for order_id, values in data.items():
            record = values.copy()
            record['time'] = pd.to_datetime(int(values['timestamp']), unit='ms')
            records.append(record)

        df = pd.DataFrame(records)

        if start_time:
            df = df[df['time'] >= start_time]
        if end_time:
            df = df[df['time'] <= end_time]

        return df.sort_values('time')

    # =============================================================================
    # Long/Short Ratio Operations
    # =============================================================================

    async def save_long_short_ratio_batch(self, df: pd.DataFrame, symbol: str, period: str):
        """Save Long/Short Ratio data to Firebase"""
        if df.empty:
            return

        safe_symbol = symbol.replace('/', '_')
        base_path = f'futures_data/{safe_symbol}/long_short_ratio/{period}'

        batch_data = {}
        for _, row in df.iterrows():
            timestamp_col = 'time' if 'time' in row else 'timestamp'
            timestamp = int(row[timestamp_col].timestamp() * 1000)
            batch_data[str(timestamp)] = {
                'long_short_ratio': float(row.get('long_short_ratio', row.get('longShortRatio', 0))),
                'long_account': float(row.get('long_account', row.get('longAccount', 0))),
                'short_account': float(row.get('short_account', row.get('shortAccount', 0))),
            }

        await self._async_batch_update(base_path, batch_data)
        logger.info(f"✅ Saved {len(batch_data)} L/S ratio records to Firebase: {symbol} {period}")

    async def get_long_short_ratio(self, symbol: str, period: str, start_time: Optional[datetime] = None,
                                    end_time: Optional[datetime] = None) -> pd.DataFrame:
        """Retrieve Long/Short Ratio data from Firebase"""
        safe_symbol = symbol.replace('/', '_')
        path = f'futures_data/{safe_symbol}/long_short_ratio/{period}'

        data = await self._async_get(path)
        if not data:
            return pd.DataFrame()

        records = []
        for timestamp, values in data.items():
            record = values.copy()
            record['time'] = pd.to_datetime(int(timestamp), unit='ms')
            records.append(record)

        df = pd.DataFrame(records)

        if start_time:
            df = df[df['time'] >= start_time]
        if end_time:
            df = df[df['time'] <= end_time]

        return df.sort_values('time')

    # =============================================================================
    # Order Book Operations
    # =============================================================================

    async def save_order_book_batch(self, df: pd.DataFrame, symbol: str):
        """
        Save Order Book snapshot to Firebase

        Args:
            df: DataFrame with order book data
            symbol: Trading symbol
        """
        if df.empty:
            return

        safe_symbol = symbol.replace('/', '_')

        # Get timestamp from first row
        if 'timestamp' in df.columns:
            timestamp = int(df['timestamp'].iloc[0].timestamp() * 1000)
        elif 'time' in df.columns:
            timestamp = int(df['time'].iloc[0].timestamp() * 1000)
        else:
            timestamp = int(datetime.now().timestamp() * 1000)

        base_path = f'futures_data/{safe_symbol}/order_book/{timestamp}'

        # Prepare batch data - separate bids and asks
        bids_data = {}
        asks_data = {}

        for _, row in df.iterrows():
            level = int(row['level'])
            record = {
                'price': float(row['price']),
                'quantity': float(row['quantity'])
            }

            if row['side'] == 'BID':
                bids_data[str(level)] = record
            elif row['side'] == 'ASK':
                asks_data[str(level)] = record

        # Save bids and asks
        batch_data = {
            'bids': bids_data,
            'asks': asks_data,
            'timestamp': timestamp
        }

        # Add spread info if available in df attributes
        if hasattr(df, 'attrs'):
            if 'best_bid' in df.attrs:
                batch_data['best_bid'] = float(df.attrs['best_bid'])
            if 'best_ask' in df.attrs:
                batch_data['best_ask'] = float(df.attrs['best_ask'])
            if 'spread' in df.attrs:
                batch_data['spread'] = float(df.attrs['spread'])
            if 'mid_price' in df.attrs:
                batch_data['mid_price'] = float(df.attrs['mid_price'])

        await self._async_batch_update(base_path, batch_data)
        logger.info(f"✅ Saved order book snapshot to Firebase: {symbol}")

    async def get_order_book(self, symbol: str,
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None,
                             limit_levels: int = 10) -> pd.DataFrame:
        """
        Retrieve Order Book snapshots from Firebase

        Args:
            symbol: Trading symbol
            start_time: Start datetime
            end_time: End datetime
            limit_levels: Max levels to retrieve per side

        Returns:
            DataFrame with order book data
        """
        safe_symbol = symbol.replace('/', '_')
        path = f'futures_data/{safe_symbol}/order_book'

        data = await self._async_get(path)
        if not data:
            return pd.DataFrame()

        all_records = []

        for timestamp_key, snapshot in data.items():
            timestamp = pd.to_datetime(int(timestamp_key), unit='ms')

            # Skip if outside time range
            if start_time and timestamp < start_time:
                continue
            if end_time and timestamp > end_time:
                continue

            # Process bids
            if 'bids' in snapshot:
                for level_str, record in snapshot['bids'].items():
                    level = int(level_str)
                    if level < limit_levels:
                        all_records.append({
                            'time': timestamp,
                            'side': 'BID',
                            'level': level,
                            'price': record['price'],
                            'quantity': record['quantity']
                        })

            # Process asks
            if 'asks' in snapshot:
                for level_str, record in snapshot['asks'].items():
                    level = int(level_str)
                    if level < limit_levels:
                        all_records.append({
                            'time': timestamp,
                            'side': 'ASK',
                            'level': level,
                            'price': record['price'],
                            'quantity': record['quantity']
                        })

        df = pd.DataFrame(all_records)

        if not df.empty:
            df = df.sort_values(['time', 'side', 'level'])

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
        safe_symbol = symbol.replace('/', '_')
        path = f'futures_data/{safe_symbol}/order_book'

        data = await self._async_get(path)
        if not data:
            return pd.DataFrame()

        # Get latest timestamp
        latest_timestamp = max(data.keys(), key=lambda x: int(x))
        snapshot = data[latest_timestamp]
        timestamp = pd.to_datetime(int(latest_timestamp), unit='ms')

        records = []

        # Process bids
        if 'bids' in snapshot:
            for level_str, record in snapshot['bids'].items():
                level = int(level_str)
                if level < limit_levels:
                    records.append({
                        'time': timestamp,
                        'side': 'BID',
                        'level': level,
                        'price': record['price'],
                        'quantity': record['quantity']
                    })

        # Process asks
        if 'asks' in snapshot:
            for level_str, record in snapshot['asks'].items():
                level = int(level_str)
                if level < limit_levels:
                    records.append({
                        'time': timestamp,
                        'side': 'ASK',
                        'level': level,
                        'price': record['price'],
                        'quantity': record['quantity']
                    })

        df = pd.DataFrame(records)

        if not df.empty:
            df = df.sort_values(['side', 'level'])

            # Add spread info if available
            if 'best_bid' in snapshot:
                df.attrs['best_bid'] = snapshot['best_bid']
            if 'best_ask' in snapshot:
                df.attrs['best_ask'] = snapshot['best_ask']
            if 'spread' in snapshot:
                df.attrs['spread'] = snapshot['spread']
            if 'mid_price' in snapshot:
                df.attrs['mid_price'] = snapshot['mid_price']

        return df

    # =============================================================================
    # Utility Methods
    # =============================================================================

    async def _async_batch_update(self, path: str, data: Dict):
        """Execute batch update asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            lambda: self._get_ref(path).update(data)
        )

    async def _async_get(self, path: str) -> Optional[Dict]:
        """Execute get operation asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: self._get_ref(path).get()
        )

    async def delete_data(self, symbol: str, data_type: Optional[str] = None):
        """
        Delete data from Firebase

        Args:
            symbol: Trading symbol
            data_type: Specific data type to delete (ohlcv, open_interest, etc.)
                      If None, deletes all data for symbol
        """
        safe_symbol = symbol.replace('/', '_')

        if data_type:
            path = f'futures_data/{safe_symbol}/{data_type}'
        else:
            path = f'futures_data/{safe_symbol}'

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            lambda: self._get_ref(path).delete()
        )
        logger.info(f"🗑️ Deleted {data_type or 'all'} data for {symbol}")

    async def get_all_symbols(self) -> List[str]:
        """Get list of all symbols in database"""
        data = await self._async_get('futures_data')
        if not data:
            return []

        # Convert safe symbol names back to normal (e.g., SOL_USDT -> SOL/USDT)
        return [key.replace('_', '/') for key in data.keys()]

    def cleanup(self):
        """Cleanup resources"""
        if self.executor:
            self.executor.shutdown(wait=True)
        logger.info("Firebase manager cleaned up")
