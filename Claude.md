# Phase 1: Data Infrastructure & Collection
## Building the Foundation for AI-Powered OI Trading

**Duration:** Week 1-2  
**Goal:** Establish robust, real-time data pipeline from Binance Futures API

---

## 🎯 Phase Objectives

1. ✅ Connect to Binance Futures API (REST + WebSocket)
2. ✅ Collect historical data (6 months minimum)
3. ✅ Build real-time streaming pipeline
4. ✅ Design optimized database schema
5. ✅ Implement data quality monitoring
6. ✅ Create data versioning system

---

## 📦 Required Data Streams

### 1. **Open Interest (OI)** — Core Signal
```python
# REST API: Historical OI
GET /futures/data/openInterestHist
Parameters:
  - symbol: SOLUSDT
  - period: 5m, 15m, 1h, 4h
  - limit: 500

Response:
  - timestamp
  - symbol
  - sumOpenInterest       # Total OI
  - sumOpenInterestValue  # OI in USD
```

### 2. **Price & Volume (OHLCV)**
```python
# REST API: Klines/Candlesticks
GET /fapi/v1/klines
Parameters:
  - symbol: SOLUSDT
  - interval: 1m, 5m, 15m, 1h, 4h, 1d
  - limit: 1500

Response:
  - timestamp
  - open, high, low, close
  - volume
  - closeTime
  - quoteAssetVolume
  - numberOfTrades
  - takerBuyBaseAssetVolume
  - takerBuyQuoteAssetVolume
```

### 3. **Funding Rate**
```python
# REST API: Funding Rate History
GET /fapi/v1/fundingRate
Parameters:
  - symbol: SOLUSDT
  - limit: 1000

Response:
  - fundingTime
  - fundingRate
  - markPrice
```

### 4. **Order Book Depth**
```python
# REST API: Order Book
GET /fapi/v1/depth
Parameters:
  - symbol: SOLUSDT
  - limit: 100

Response:
  - bids: [[price, quantity], ...]
  - asks: [[price, quantity], ...]
  - lastUpdateId
```

### 5. **Long/Short Ratio** (optional but valuable)
```python
# REST API: Top Trader Long/Short Ratio
GET /futures/data/topLongShortAccountRatio
Parameters:
  - symbol: SOLUSDT
  - period: 5m, 15m, 1h

Response:
  - longShortRatio
  - longAccount
  - shortAccount
```

### 6. **Liquidation Data** (for sentiment)
```python
# REST API: Liquidation Orders
GET /fapi/v1/allForceOrders
Parameters:
  - symbol: SOLUSDT
  - limit: 100

Response:
  - orderId
  - symbol
  - price
  - origQty
  - side  # BUY = short liquidation, SELL = long liquidation
  - time
```

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    BINANCE API LAYER                      │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐   │
│  │ REST API   │  │ WebSocket  │  │  Rate Limiter    │   │
│  │ (Historical│  │ (Real-time)│  │  (1200 req/min)  │   │
│  └──────┬─────┘  └──────┬─────┘  └────────┬─────────┘   │
└─────────┼────────────────┼─────────────────┼─────────────┘
          │                │                 │
          ▼                ▼                 ▼
┌──────────────────────────────────────────────────────────┐
│                  DATA COLLECTOR LAYER                     │
│  ┌────────────────┐  ┌───────────────┐  ┌─────────────┐ │
│  │ Historical     │  │ WebSocket     │  │ Data        │ │
│  │ Collector      │  │ Stream Manager│  │ Validator   │ │
│  │ (Batch Mode)   │  │ (Live Mode)   │  │ (Quality)   │ │
│  └───────┬────────┘  └──────┬────────┘  └──────┬──────┘ │
└──────────┼───────────────────┼──────────────────┼────────┘
           │                   │                  │
           ▼                   ▼                  ▼
┌──────────────────────────────────────────────────────────┐
│                  DATA PROCESSING LAYER                    │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ Normalizer  │  │ Aggregator   │  │ Feature Cache   │ │
│  │ (Clean)     │  │ (Resample)   │  │ (Redis)         │ │
│  └──────┬──────┘  └──────┬───────┘  └────────┬────────┘ │
└─────────┼─────────────────┼──────────────────┼──────────┘
          │                 │                  │
          ▼                 ▼                  ▼
┌──────────────────────────────────────────────────────────┐
│                    STORAGE LAYER                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │  PostgreSQL + TimescaleDB (Hypertables)          │    │
│  │  • Raw data tables (immutable)                   │    │
│  │  • Aggregated views (materialized)               │    │
│  │  • Feature store (preprocessed)                  │    │
│  └──────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Redis (Cache Layer)                              │    │
│  │  • Latest OI values                               │    │
│  │  • Recent price data                              │    │
│  │  • Real-time features                             │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

---

## 💾 Database Schema Design

### TimescaleDB Hypertables

#### Table 1: `ohlcv`
```sql
CREATE TABLE ohlcv (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    open NUMERIC(18, 8),
    high NUMERIC(18, 8),
    low NUMERIC(18, 8),
    close NUMERIC(18, 8),
    volume NUMERIC(20, 8),
    quote_volume NUMERIC(20, 8),
    num_trades INTEGER,
    taker_buy_base NUMERIC(20, 8),
    taker_buy_quote NUMERIC(20, 8),
    PRIMARY KEY (time, symbol, timeframe)
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('ohlcv', 'time');

-- Create indexes for faster queries
CREATE INDEX idx_ohlcv_symbol_time ON ohlcv (symbol, time DESC);
CREATE INDEX idx_ohlcv_timeframe ON ohlcv (timeframe, time DESC);
```

#### Table 2: `open_interest`
```sql
CREATE TABLE open_interest (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    period VARCHAR(5) NOT NULL,
    open_interest NUMERIC(20, 8),
    open_interest_value NUMERIC(20, 2),
    PRIMARY KEY (time, symbol, period)
);

SELECT create_hypertable('open_interest', 'time');
CREATE INDEX idx_oi_symbol_time ON open_interest (symbol, time DESC);
```

#### Table 3: `funding_rate`
```sql
CREATE TABLE funding_rate (
    funding_time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    funding_rate NUMERIC(10, 8),
    mark_price NUMERIC(18, 8),
    PRIMARY KEY (funding_time, symbol)
);

SELECT create_hypertable('funding_rate', 'funding_time');
```

#### Table 4: `liquidations`
```sql
CREATE TABLE liquidations (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10),
    price NUMERIC(18, 8),
    quantity NUMERIC(20, 8),
    order_id BIGINT UNIQUE
);

SELECT create_hypertable('liquidations', 'time');
CREATE INDEX idx_liq_symbol_side ON liquidations (symbol, side, time DESC);
```

#### Table 5: `long_short_ratio`
```sql
CREATE TABLE long_short_ratio (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    period VARCHAR(5) NOT NULL,
    long_short_ratio NUMERIC(10, 6),
    long_account NUMERIC(10, 6),
    short_account NUMERIC(10, 6),
    PRIMARY KEY (time, symbol, period)
);

SELECT create_hypertable('long_short_ratio', 'time');
```

#### Materialized Views for Fast Queries
```sql
-- Aggregated OI with price (for divergence detection)
CREATE MATERIALIZED VIEW oi_price_1h WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', o.time) AS bucket,
    o.symbol,
    AVG(o.open_interest) AS avg_oi,
    LAST(p.close, p.time) AS close_price,
    LAST(o.open_interest, o.time) - FIRST(o.open_interest, o.time) AS oi_change,
    (LAST(p.close, p.time) - FIRST(p.close, p.time)) / FIRST(p.close, p.time) * 100 AS price_change_pct
FROM open_interest o
JOIN ohlcv p ON o.symbol = p.symbol 
    AND o.time >= p.time 
    AND o.time < p.time + INTERVAL '5 minutes'
WHERE p.timeframe = '5m'
GROUP BY bucket, o.symbol;

-- Refresh policy (update every 5 minutes)
SELECT add_continuous_aggregate_policy('oi_price_1h',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes');
```

---

## 🐍 Python Implementation

### 1. **API Connection Manager**
```python
# data_collector/binance_client.py

import ccxt
import asyncio
from typing import List, Dict, Optional
import pandas as pd
from datetime import datetime, timedelta
import logging

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
        """
        try:
            # Binance-specific endpoint
            endpoint = '/futures/data/openInterestHist'
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
        """
        try:
            params = {
                'symbol': symbol.replace('/', ''),
                'limit': limit
            }
            
            response = await self.exchange.fapiPublicGetAllForceOrders(params)
            
            df = pd.DataFrame(response)
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
        """
        try:
            endpoint = '/futures/data/topLongShortAccountRatio'
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
```

### 2. **Historical Data Collector**
```python
# data_collector/historical_collector.py

import asyncio
from datetime import datetime, timedelta
from typing import List
import pandas as pd
from sqlalchemy import create_engine
from tqdm import tqdm

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
                print(f"Error at {current_date}: {e}")
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
                print(f"Error fetching OI batch {i}: {e}")
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
        df['symbol'] = symbol
        df['timeframe'] = timeframe
        df = df.rename(columns={'timestamp': 'time'})
        
        df.to_sql(
            'ohlcv',
            self.engine,
            if_exists='append',
            index=False,
            method='multi'
        )
        print(f"Saved {len(df)} {timeframe} candles for {symbol}")
    
    def _save_oi(self, df: pd.DataFrame, symbol: str, period: str):
        """Save OI to database"""
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
        print(f"Saved {len(df)} OI records for {symbol}")
    
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
```

### 3. **Real-time WebSocket Streamer**
```python
# data_collector/websocket_streamer.py

import websocket
import json
import threading
from datetime import datetime
import redis

class BinanceWebSocketStreamer:
    """
    Real-time data streaming via WebSocket
    """
    
    def __init__(self, symbols: List[str], redis_client: redis.Redis):
        self.symbols = [s.lower().replace('/', '') for s in symbols]
        self.redis = redis_client
        self.ws = None
        self.running = False
        
    def start(self):
        """Start WebSocket connection"""
        self.running = True
        
        # Construct stream URL
        streams = []
        for symbol in self.symbols:
            streams.append(f"{symbol}@kline_5m")      # Price
            streams.append(f"{symbol}@markPrice")     # Mark price
            
        stream_url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"
        
        self.ws = websocket.WebSocketApp(
            stream_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        # Run in separate thread
        ws_thread = threading.Thread(target=self.ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
    
    def on_message(self, ws, message):
        """Handle incoming WebSocket message"""
        data = json.loads(message)
        stream = data.get('stream', '')
        payload = data.get('data', {})
        
        # Cache latest data in Redis
        if '@kline' in stream:
            self._cache_kline(payload)
        elif '@markPrice' in stream:
            self._cache_mark_price(payload)
    
    def _cache_kline(self, data):
        """Cache latest kline data"""
        kline = data['k']
        symbol = kline['s']
        
        key = f"latest_kline:{symbol}"
        value = {
            'time': datetime.fromtimestamp(kline['t'] / 1000).isoformat(),
            'close': float(kline['c']),
            'volume': float(kline['v']),
            'is_closed': kline['x']
        }
        
        self.redis.setex(key, 300, json.dumps(value))  # TTL 5 minutes
    
    def _cache_mark_price(self, data):
        """Cache mark price and funding rate"""
        symbol = data['s']
        
        key = f"latest_mark:{symbol}"
        value = {
            'time': datetime.fromtimestamp(data['E'] / 1000).isoformat(),
            'mark_price': float(data['p']),
            'funding_rate': float(data['r']),
            'next_funding': datetime.fromtimestamp(data['T'] / 1000).isoformat()
        }
        
        self.redis.setex(key, 300, json.dumps(value))
    
    def on_error(self, ws, error):
        print(f"WebSocket Error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        print("WebSocket connection closed")
        if self.running:
            # Auto-reconnect
            print("Reconnecting...")
            self.start()
    
    def on_open(self, ws):
        print("WebSocket connection opened")
    
    def stop(self):
        """Stop WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()
```

---

## 🧪 Data Quality Monitoring

```python
# data_quality/validator.py

class DataQualityMonitor:
    """
    Monitors data quality and detects anomalies
    """
    
    def validate_ohlcv(self, df: pd.DataFrame) -> Dict[str, bool]:
        """Validate OHLCV data integrity"""
        checks = {}
        
        # Check for nulls
        checks['no_nulls'] = not df.isnull().any().any()
        
        # Check OHLC relationship
        checks['valid_ohlc'] = (
            (df['high'] >= df['low']).all() and
            (df['high'] >= df['open']).all() and
            (df['high'] >= df['close']).all() and
            (df['low'] <= df['open']).all() and
            (df['low'] <= df['close']).all()
        )
        
        # Check for duplicates
        checks['no_duplicates'] = not df.duplicated(subset=['timestamp']).any()
        
        # Check time continuity (no large gaps)
        time_diffs = df['timestamp'].diff().dt.total_seconds()
        expected_diff = self._get_expected_diff(df.attrs.get('timeframe', '5m'))
        checks['continuous_time'] = (time_diffs[1:] <= expected_diff * 1.5).all()
        
        # Check for outliers (price spikes > 10%)
        returns = df['close'].pct_change()
        checks['no_extreme_spikes'] = (returns.abs() < 0.10).all()
        
        return checks
    
    def validate_oi(self, df: pd.DataFrame) -> Dict[str, bool]:
        """Validate OI data"""
        checks = {}
        
        checks['no_nulls'] = not df.isnull().any().any()
        checks['positive_oi'] = (df['open_interest'] >= 0).all()
        checks['no_duplicates'] = not df.duplicated(subset=['timestamp']).any()
        
        # OI shouldn't change more than 50% in one period (unless exceptional event)
        oi_pct_change = df['open_interest'].pct_change().abs()
        checks['reasonable_changes'] = (oi_pct_change < 0.50).all()
        
        return checks
    
    @staticmethod
    def _get_expected_diff(timeframe: str) -> float:
        """Get expected time difference in seconds"""
        mapping = {'1m': 60, '5m': 300, '15m': 900, '1h': 3600, '4h': 14400}
        return mapping.get(timeframe, 300)
```

---

## 📊 Main Collection Script

```python
# main_historical_collection.py

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import create_engine
import redis

from data_collector.binance_client import BinanceFuturesClient
from data_collector.historical_collector import HistoricalDataCollector
from data_quality.validator import DataQualityMonitor

async def main():
    # Configuration
    SYMBOL = 'SOL/USDT'
    TIMEFRAMES = ['5m', '15m', '1h', '4h', '1d']
    OI_PERIODS = ['5m', '15m', '1h']
    
    # Date range: 6 months back
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    
    # Initialize
    db_engine = create_engine('postgresql://user:pass@localhost/futures_db')
    client = BinanceFuturesClient(testnet=False)
    collector = HistoricalDataCollector(client, db_engine)
    validator = DataQualityMonitor()
    
    print("=" * 60)
    print("HISTORICAL DATA COLLECTION")
    print(f"Symbol: {SYMBOL}")
    print(f"Date Range: {start_date.date()} to {end_date.date()}")
    print("=" * 60)
    
    # Collect OHLCV for all timeframes
    for tf in TIMEFRAMES:
        print(f"\n📊 Collecting {tf} OHLCV data...")
        df = await collector.collect_ohlcv_range(SYMBOL, tf, start_date, end_date)
        
        # Validate
        checks = validator.validate_ohlcv(df)
        print(f"✅ Quality checks: {checks}")
    
    # Collect OI data
    for period in OI_PERIODS:
        print(f"\n📈 Collecting {period} OI data...")
        df = await collector.collect_oi_range(SYMBOL, period, start_date, end_date)
        
        # Validate
        checks = validator.validate_oi(df)
        print(f"✅ Quality checks: {checks}")
    
    # Collect funding rate
    print(f"\n💰 Collecting Funding Rate data...")
    df = await client.fetch_funding_rate_history(SYMBOL)
    df = df[(df['fundingTime'] >= start_date) & (df['fundingTime'] <= end_date)]
    df['symbol'] = SYMBOL
    df.to_sql(
        'funding_rate',
        db_engine,
        if_exists='append',
        index=False,
        method='multi'
    )
    print(f"Saved {len(df)} funding rate records")

    # Collect liquidation data
    print(f"\n🔥 Collecting Liquidation data...")
    liq_df = await client.fetch_liquidations(SYMBOL, limit=1000)
    liq_df = liq_df[(liq_df['time'] >= start_date) & (liq_df['time'] <= end_date)]
    liq_df['symbol'] = SYMBOL
    liq_df = liq_df.rename(columns={'origQty': 'quantity', 'orderId': 'order_id'})
    liq_df.to_sql(
        'liquidations',
        db_engine,
        if_exists='append',
        index=False,
        method='multi'
    )
    print(f"Saved {len(liq_df)} liquidation records")

    # Collect long/short ratio
    for period in OI_PERIODS:
        print(f"\n⚖️ Collecting Long/Short Ratio {period} data...")
        ls_df = await client.fetch_top_trader_ratio(SYMBOL, period=period)
        ls_df = ls_df[(ls_df['timestamp'] >= start_date) & (ls_df['timestamp'] <= end_date)]
        ls_df['symbol'] = SYMBOL
        ls_df['period'] = period
        ls_df = ls_df.rename(columns={
            'timestamp': 'time',
            'longShortRatio': 'long_short_ratio',
            'longAccount': 'long_account',
            'shortAccount': 'short_account'
        })
        ls_df.to_sql(
            'long_short_ratio',
            db_engine,
            if_exists='append',
            index=False,
            method='multi'
        )
        print(f"Saved {len(ls_df)} long/short ratio records")

    print("\n" + "=" * 60)
    print("✅ DATA COLLECTION COMPLETE!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🔧 Environment Setup & Configuration

### Prerequisites

```bash
# Python 3.9+
python --version

# Install required packages
pip install ccxt pandas sqlalchemy psycopg2-binary timescaledb redis websocket-client tqdm asyncio
```

### Database Setup

```bash
# Install PostgreSQL and TimescaleDB
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib
sudo add-apt-repository ppa:timescale/timescaledb-ppa
sudo apt update
sudo apt install timescaledb-postgresql-14

# Initialize TimescaleDB
sudo timescaledb-tune
sudo systemctl restart postgresql

# Create database
sudo -u postgres psql
CREATE DATABASE futures_db;
\c futures_db
CREATE EXTENSION IF NOT EXISTS timescaledb;
\q
```

### Redis Setup

```bash
# Install Redis
sudo apt install redis-server

# Start Redis
sudo systemctl start redis
sudo systemctl enable redis

# Test connection
redis-cli ping  # Should return "PONG"
```

### Configuration File

Create a `config.yaml` file:

```yaml
# config.yaml

binance:
  api_key: "YOUR_API_KEY"  # Optional for public data
  api_secret: "YOUR_API_SECRET"
  testnet: false
  rate_limit: 1200  # requests per minute

database:
  host: "localhost"
  port: 5432
  database: "futures_db"
  user: "your_username"
  password: "your_password"

redis:
  host: "localhost"
  port: 6379
  db: 0

collection:
  symbols:
    - "SOL/USDT"
    - "BTC/USDT"  # Add more symbols as needed
  timeframes:
    - "5m"
    - "15m"
    - "1h"
    - "4h"
    - "1d"
  oi_periods:
    - "5m"
    - "15m"
    - "1h"
  historical_days: 180  # 6 months

logging:
  level: "INFO"
  file: "logs/data_collection.log"
```

### Initialize Database Schema

```python
# scripts/init_database.py

from sqlalchemy import create_engine, text
import yaml

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Create engine
db_config = config['database']
engine = create_engine(
    f"postgresql://{db_config['user']}:{db_config['password']}@"
    f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
)

# Execute schema creation
with open('schemas/create_tables.sql', 'r') as f:
    sql_script = f.read()

with engine.connect() as conn:
    conn.execute(text(sql_script))
    print("✅ Database schema created successfully!")
```

### Project Structure

```
p1_dataCollection/
├── config.yaml
├── requirements.txt
├── .env
├── data_collector/
│   ├── __init__.py
│   ├── binance_client.py
│   ├── historical_collector.py
│   └── websocket_streamer.py
├── data_quality/
│   ├── __init__.py
│   └── validator.py
├── schemas/
│   └── create_tables.sql
├── scripts/
│   ├── init_database.py
│   ├── main_historical_collection.py
│   └── start_realtime_stream.py
├── logs/
│   └── .gitkeep
└── README.md
```

### Running the Data Collection

**Step 1: Initialize Database**
```bash
python scripts/init_database.py
```

**Step 2: Collect Historical Data**
```bash
python scripts/main_historical_collection.py
```

**Step 3: Start Real-time Streaming**
```bash
python scripts/start_realtime_stream.py &
```

### Monitoring & Maintenance

**Check Data Quality**
```sql
-- Check latest data timestamps
SELECT
    'ohlcv' as table_name,
    symbol,
    timeframe,
    MAX(time) as latest_timestamp,
    COUNT(*) as record_count
FROM ohlcv
GROUP BY symbol, timeframe
ORDER BY latest_timestamp DESC;

-- Check for data gaps
SELECT
    time,
    LAG(time) OVER (ORDER BY time) as prev_time,
    time - LAG(time) OVER (ORDER BY time) as gap
FROM ohlcv
WHERE symbol = 'SOL/USDT' AND timeframe = '5m'
ORDER BY time DESC
LIMIT 100;

-- Check OI and Price correlation
SELECT * FROM oi_price_1h
WHERE symbol = 'SOL/USDT'
ORDER BY bucket DESC
LIMIT 20;
```

**Database Maintenance**
```sql
-- Vacuum and analyze
VACUUM ANALYZE ohlcv;
VACUUM ANALYZE open_interest;

-- Check table sizes
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## 📈 Monitoring Dashboard (Optional)

### Grafana Integration

```yaml
# docker-compose.yml
version: '3.8'

services:
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-storage:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources

volumes:
  grafana-storage:
```

**Key Metrics to Monitor:**
- Data ingestion rate (records/minute)
- API rate limit usage
- Database write latency
- WebSocket connection status
- Data quality check results
- Gap detection alerts

---

## ✅ Phase 1 Deliverables Checklist

- [ ] Binance API connection working (both REST and WebSocket)
- [ ] Historical data collected: 6 months of OHLCV (5 timeframes)
- [ ] Historical OI data collected (3 periods)
- [ ] Funding rate history collected
- [ ] PostgreSQL + TimescaleDB setup complete
- [ ] All tables created with proper indexes
- [ ] Data quality validation passing
- [ ] Redis caching layer operational
- [ ] WebSocket real-time streaming working
- [ ] Documentation written

---

## 🔍 Troubleshooting & Common Issues

### Issue 1: API Rate Limit Exceeded

**Symptoms:** `429 Too Many Requests` error

**Solution:**
```python
# Adjust rate limiting in client
self.exchange = ccxt.binance({
    'enableRateLimit': True,
    'rateLimit': 100  # Increase delay between requests (ms)
})

# Add exponential backoff
import time
from functools import wraps

def retry_with_backoff(max_retries=3):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if '429' in str(e) and attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"Rate limited. Waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        raise
        return wrapper
    return decorator
```

### Issue 2: WebSocket Connection Drops

**Symptoms:** Stream stops receiving data

**Solution:**
```python
# Add ping/pong keepalive
def on_ping(self, ws, message):
    ws.pong(message)

# Implement reconnection with exponential backoff
def on_close(self, ws, close_status_code, close_msg):
    if self.running:
        backoff = min(60, 2 ** self.reconnect_attempts)
        print(f"Reconnecting in {backoff}s...")
        time.sleep(backoff)
        self.reconnect_attempts += 1
        self.start()
```

### Issue 3: Database Connection Pool Exhausted

**Symptoms:** `QueuePool limit exceeded` error

**Solution:**
```python
# Increase pool size
engine = create_engine(
    connection_string,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True  # Verify connections before use
)

# Use connection context managers
with engine.connect() as conn:
    conn.execute(...)
```

### Issue 4: Data Gaps in Historical Collection

**Symptoms:** Missing timestamps in data

**Solution:**
```sql
-- Detect gaps
WITH time_series AS (
    SELECT generate_series(
        (SELECT MIN(time) FROM ohlcv WHERE symbol = 'SOL/USDT'),
        (SELECT MAX(time) FROM ohlcv WHERE symbol = 'SOL/USDT'),
        INTERVAL '5 minutes'
    ) AS expected_time
)
SELECT ts.expected_time
FROM time_series ts
LEFT JOIN ohlcv o ON ts.expected_time = o.time AND o.symbol = 'SOL/USDT'
WHERE o.time IS NULL
ORDER BY ts.expected_time;
```

```python
# Re-collect missing periods
async def fill_gaps(symbol, timeframe, gaps):
    for gap_start, gap_end in gaps:
        await collector.collect_ohlcv_range(
            symbol, timeframe, gap_start, gap_end
        )
```

### Issue 5: Memory Issues with Large DataFrames

**Symptoms:** `MemoryError` or process killed

**Solution:**
```python
# Process in smaller chunks
async def collect_in_chunks(symbol, timeframe, start, end, chunk_days=7):
    current = start
    while current < end:
        chunk_end = min(current + timedelta(days=chunk_days), end)
        df = await collector.collect_ohlcv_range(symbol, timeframe, current, chunk_end)

        # Save immediately
        save_to_db(df)

        # Clear memory
        del df
        gc.collect()

        current = chunk_end
```

---

## 💡 Best Practices

### 1. **Data Validation Before Storage**

```python
def validate_before_insert(df, table_name):
    """Validate data quality before database insertion"""

    # Check for nulls
    null_counts = df.isnull().sum()
    if null_counts.any():
        logger.warning(f"Nulls detected in {table_name}: {null_counts[null_counts > 0]}")

    # Check for duplicates
    duplicates = df.duplicated().sum()
    if duplicates > 0:
        logger.warning(f"Removing {duplicates} duplicates from {table_name}")
        df = df.drop_duplicates()

    # Check data types
    for col in df.columns:
        if df[col].dtype == 'object' and col not in ['symbol', 'side', 'period']:
            logger.error(f"Column {col} has invalid type: object")

    return df
```

### 2. **Implement Data Versioning**

```python
# Add metadata table
CREATE TABLE data_versions (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(50),
    version VARCHAR(20),
    collection_date TIMESTAMPTZ,
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    record_count BIGINT,
    checksum VARCHAR(64)
);

# Track versions
def create_version_record(table_name, df, start_date, end_date):
    checksum = hashlib.sha256(df.to_csv().encode()).hexdigest()
    version = datetime.now().strftime("%Y%m%d_%H%M%S")

    metadata = {
        'table_name': table_name,
        'version': version,
        'collection_date': datetime.now(),
        'start_date': start_date,
        'end_date': end_date,
        'record_count': len(df),
        'checksum': checksum
    }

    save_metadata(metadata)
```

### 3. **Implement Graceful Shutdown**

```python
import signal
import sys

class DataCollector:
    def __init__(self):
        self.running = True
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def shutdown(self, signum, frame):
        print("\n🛑 Graceful shutdown initiated...")
        self.running = False

        # Close connections
        if self.ws:
            self.ws.close()
        if self.engine:
            self.engine.dispose()
        if self.redis:
            self.redis.close()

        print("✅ Cleanup complete. Exiting.")
        sys.exit(0)
```

### 4. **Log Everything**

```python
import logging
from logging.handlers import RotatingFileHandler

# Setup comprehensive logging
def setup_logging():
    logger = logging.getLogger('data_collector')
    logger.setLevel(logging.INFO)

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)

    # File handler (rotate at 10MB)
    file_handler = RotatingFileHandler(
        'logs/collector.log',
        maxBytes=10*1024*1024,
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)

    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console)
    logger.addHandler(file_handler)

    return logger
```

### 5. **Implement Health Checks**

```python
# health_check.py
import asyncio
from datetime import datetime, timedelta

async def health_check():
    """Verify system is collecting data properly"""

    checks = {
        'database': False,
        'redis': False,
        'binance_api': False,
        'data_freshness': False,
        'websocket': False
    }

    # Check database
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks['database'] = True
    except Exception as e:
        logger.error(f"Database check failed: {e}")

    # Check Redis
    try:
        redis_client.ping()
        checks['redis'] = True
    except Exception as e:
        logger.error(f"Redis check failed: {e}")

    # Check API
    try:
        await client.exchange.fetch_ticker('SOL/USDT')
        checks['binance_api'] = True
    except Exception as e:
        logger.error(f"Binance API check failed: {e}")

    # Check data freshness (should be < 10 minutes old)
    try:
        query = "SELECT MAX(time) FROM ohlcv WHERE symbol = 'SOL/USDT'"
        latest = pd.read_sql(query, engine).iloc[0, 0]
        age = datetime.now() - latest
        checks['data_freshness'] = age < timedelta(minutes=10)
    except Exception as e:
        logger.error(f"Data freshness check failed: {e}")

    # Report
    all_healthy = all(checks.values())
    status = "✅ HEALTHY" if all_healthy else "⚠️ DEGRADED"

    print(f"\n{status}")
    for check, result in checks.items():
        print(f"  {check}: {'✅' if result else '❌'}")

    return all_healthy

# Run health checks every 5 minutes
async def monitor():
    while True:
        await health_check()
        await asyncio.sleep(300)
```

---

## 🚀 Next Phase

**Phase 2: ML Feature Engineering**

Once data collection is solid, we'll extract 100+ features from this raw data to feed our ML models.

Ready to proceed? 🎯
