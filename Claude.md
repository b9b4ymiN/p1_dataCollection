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
    # Save to DB...
    
    print("\n" + "=" * 60)
    print("✅ DATA COLLECTION COMPLETE!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
```

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

## 🚀 Next Phase

**Phase 2: ML Feature Engineering**

Once data collection is solid, we'll extract 100+ features from this raw data to feed our ML models.

Ready to proceed? 🎯
