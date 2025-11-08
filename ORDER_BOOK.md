# Order Book Depth Collection Guide

Complete guide for collecting and analyzing order book depth data from Binance Futures.

## Overview

Order book depth shows all pending buy (bid) and sell (ask) orders at different price levels. This data is crucial for:
- **Liquidity Analysis** - Understanding market depth
- **Support/Resistance Levels** - Identifying large order walls
- **Market Microstructure** - Analyzing bid-ask spread
- **High-Frequency Trading** - Sub-second price movements
- **Slippage Estimation** - Calculating execution costs

---

## 📊 What is Order Book Depth?

The order book contains:

### Bids (Buy Orders)
Orders to BUY at specified prices (below current price):
```
Level 0: $100.00 x 1,000  ← Best Bid (highest buy price)
Level 1: $99.95  x 500
Level 2: $99.90  x 750
Level 3: $99.85  x 300
...
```

### Asks (Sell Orders)
Orders to SELL at specified prices (above current price):
```
Level 0: $100.05 x 800   ← Best Ask (lowest sell price)
Level 1: $100.10 x 600
Level 2: $100.15 x 450
Level 3: $100.20 x 900
...
```

### Spread
```
Spread = Best Ask - Best Bid = $100.05 - $100.00 = $0.05
```

---

## 🚀 Quick Start

### 1. Fetch Order Book

```python
import asyncio
from data_collector.binance_client import BinanceFuturesClient

async def fetch_order_book_example():
    client = BinanceFuturesClient()

    # Fetch order book (top 100 levels)
    df = await client.fetch_order_book('SOL/USDT', limit=100)

    print(f"Total levels: {len(df)}")
    print(f"Bids: {len(df[df['side'] == 'BID'])}")
    print(f"Asks: {len(df[df['side'] == 'ASK'])}")

    # Access spread information
    print(f"Best Bid: ${df.attrs['best_bid']}")
    print(f"Best Ask: ${df.attrs['best_ask']}")
    print(f"Spread: ${df.attrs['spread']}")
    print(f"Spread (bps): {df.attrs['spread_bps']:.2f}")

    # Show top 5 bids
    print("\nTop 5 Bids:")
    print(df[df['side'] == 'BID'].head(5))

asyncio.run(fetch_order_book_example())
```

### 2. Save to Database

```python
from database.sqlite_manager import SQLiteManager

async def save_order_book_example():
    # Initialize database
    db = SQLiteManager()
    db.initialize()

    # Fetch order book
    client = BinanceFuturesClient()
    df = await client.fetch_order_book('SOL/USDT', limit=50)

    # Save to database
    await db.save_order_book_batch(df, 'SOL/USDT')

    # Retrieve latest
    latest = await db.get_latest_order_book('SOL/USDT', limit_levels=10)
    print(f"Retrieved {len(latest)} levels from database")

asyncio.run(save_order_book_example())
```

---

## 📁 Database Schema

### PostgreSQL / SQLite

```sql
CREATE TABLE order_book (
    time TIMESTAMP NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,        -- 'BID' or 'ASK'
    level INTEGER NOT NULL,     -- 0 = best, 1 = second best, etc.
    price REAL NOT NULL,
    quantity REAL NOT NULL,
    PRIMARY KEY (time, symbol, side, level)
);

-- Indexes for fast queries
CREATE INDEX idx_ob_symbol_time ON order_book (symbol, time DESC);
CREATE INDEX idx_ob_side_level ON order_book (side, level);
```

### Firebase Structure

```json
{
  "futures_data": {
    "SOL_USDT": {
      "order_book": {
        "1699200000000": {  // timestamp
          "bids": {
            "0": {"price": 100.00, "quantity": 1000},
            "1": {"price": 99.95, "quantity": 500},
            ...
          },
          "asks": {
            "0": {"price": 100.05, "quantity": 800},
            "1": {"price": 100.10, "quantity": 600},
            ...
          },
          "best_bid": 100.00,
          "best_ask": 100.05,
          "spread": 0.05,
          "mid_price": 100.025
        }
      }
    }
  }
}
```

---

## 🔧 API Reference

### BinanceFuturesClient.fetch_order_book()

```python
async def fetch_order_book(
    self,
    symbol: str,
    limit: int = 100
) -> pd.DataFrame
```

**Parameters:**
- `symbol` (str): Trading pair (e.g., 'SOL/USDT')
- `limit` (int): Depth levels (5, 10, 20, 50, 100, 500, 1000)

**Returns:**
DataFrame with columns:
- `timestamp`: Snapshot timestamp
- `side`: 'BID' or 'ASK'
- `level`: Order book level (0 = best)
- `price`: Order price
- `quantity`: Order quantity

**DataFrame Attributes:**
- `best_bid`: Highest bid price
- `best_ask`: Lowest ask price
- `spread`: Ask - Bid
- `spread_bps`: Spread in basis points
- `mid_price`: (Bid + Ask) / 2

**Example:**
```python
df = await client.fetch_order_book('SOL/USDT', limit=20)

# Access attributes
print(f"Spread: ${df.attrs['spread']:.4f}")
print(f"Mid Price: ${df.attrs['mid_price']:.4f}")

# Filter bids
bids = df[df['side'] == 'BID']
best_5_bids = bids.head(5)
```

---

## 💾 Database Operations

### SQLiteManager / FirebaseManager

#### save_order_book_batch()

```python
async def save_order_book_batch(
    self,
    df: pd.DataFrame,
    symbol: str
) -> None
```

Save order book snapshot to database.

**Example:**
```python
df = await client.fetch_order_book('SOL/USDT', limit=100)
await db_manager.save_order_book_batch(df, 'SOL/USDT')
```

#### get_order_book()

```python
async def get_order_book(
    self,
    symbol: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit_levels: int = 10
) -> pd.DataFrame
```

Retrieve historical order book snapshots.

**Example:**
```python
from datetime import datetime, timedelta

end_time = datetime.now()
start_time = end_time - timedelta(hours=1)

df = await db_manager.get_order_book(
    'SOL/USDT',
    start_time=start_time,
    end_time=end_time,
    limit_levels=20
)
```

#### get_latest_order_book()

```python
async def get_latest_order_book(
    self,
    symbol: str,
    limit_levels: int = 10
) -> pd.DataFrame
```

Get the most recent order book snapshot.

**Example:**
```python
latest = await db_manager.get_latest_order_book('SOL/USDT', limit_levels=10)
print(f"Latest snapshot: {latest['time'].iloc[0]}")
```

---

## 📊 Analysis Examples

### 1. Calculate Order Book Imbalance

```python
async def calculate_imbalance(symbol: str, levels: int = 10):
    """
    Order book imbalance indicates buy/sell pressure
    Positive = more buying pressure, Negative = more selling pressure
    """
    df = await client.fetch_order_book(symbol, limit=levels)

    # Get top N levels
    bids = df[df['side'] == 'BID'].head(levels)
    asks = df[df['side'] == 'ASK'].head(levels)

    # Calculate total volume
    bid_volume = bids['quantity'].sum()
    ask_volume = asks['quantity'].sum()

    # Imbalance ratio
    imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)

    print(f"Bid Volume: {bid_volume:,.0f}")
    print(f"Ask Volume: {ask_volume:,.0f}")
    print(f"Imbalance: {imbalance:.2%}")

    return imbalance
```

### 2. Detect Order Book Walls

```python
async def detect_walls(symbol: str, threshold_multiplier: float = 3.0):
    """
    Detect large orders (walls) that may act as support/resistance
    """
    df = await client.fetch_order_book(symbol, limit=50)

    # Calculate average quantity per level
    avg_qty = df['quantity'].mean()
    threshold = avg_qty * threshold_multiplier

    # Find walls
    walls = df[df['quantity'] > threshold]

    print(f"\n🧱 Order Book Walls (>{threshold:,.0f} units):")
    for _, row in walls.iterrows():
        print(f"{row['side']:4} Level {row['level']:2} @ ${row['price']:.4f}: {row['quantity']:,.0f} units")

    return walls
```

### 3. Estimate Slippage

```python
async def estimate_slippage(symbol: str, order_size: float, side: str = 'BUY'):
    """
    Estimate slippage for a market order of given size
    """
    df = await client.fetch_order_book(symbol, limit=100)

    # Filter by side (BUY uses asks, SELL uses bids)
    book = df[df['side'] == 'ASK'] if side == 'BUY' else df[df['side'] == 'BID']
    book = book.sort_values('level')

    # Calculate execution
    remaining = order_size
    total_cost = 0
    levels_used = 0

    for _, row in book.iterrows():
        if remaining <= 0:
            break

        qty_at_level = min(remaining, row['quantity'])
        total_cost += qty_at_level * row['price']
        remaining -= qty_at_level
        levels_used += 1

    if remaining > 0:
        print(f"⚠️ WARNING: Insufficient liquidity! {remaining:,.2f} units unfilled")
        return None

    avg_price = total_cost / order_size
    mid_price = df.attrs['mid_price']
    slippage = abs(avg_price - mid_price)
    slippage_bps = (slippage / mid_price) * 10000

    print(f"\n💰 Slippage Estimate for {side} {order_size:,.0f} units:")
    print(f"   Mid Price: ${mid_price:.4f}")
    print(f"   Avg Execution Price: ${avg_price:.4f}")
    print(f"   Slippage: ${slippage:.4f} ({slippage_bps:.2f} bps)")
    print(f"   Levels Used: {levels_used}")

    return slippage_bps
```

### 4. Track Spread Over Time

```python
async def track_spread_history(symbol: str, hours: int = 24):
    """
    Analyze spread behavior over time
    """
    from datetime import datetime, timedelta

    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)

    # Get historical snapshots
    df = await db_manager.get_order_book(symbol, start_time=start_time, end_time=end_time)

    # Group by timestamp and calculate spread
    spreads = []
    for time in df['time'].unique():
        snapshot = df[df['time'] == time]

        best_bid = snapshot[snapshot['side'] == 'BID']['price'].max()
        best_ask = snapshot[snapshot['side'] == 'ASK']['price'].min()
        spread = best_ask - best_bid
        spread_bps = (spread / ((best_bid + best_ask) / 2)) * 10000

        spreads.append({
            'time': time,
            'spread': spread,
            'spread_bps': spread_bps
        })

    import pandas as pd
    spread_df = pd.DataFrame(spreads)

    print(f"\n📊 Spread Statistics ({hours}h):")
    print(f"   Average: {spread_df['spread_bps'].mean():.2f} bps")
    print(f"   Min: {spread_df['spread_bps'].min():.2f} bps")
    print(f"   Max: {spread_df['spread_bps'].max():.2f} bps")
    print(f"   Std Dev: {spread_df['spread_bps'].std():.2f} bps")

    return spread_df
```

---

## 🎯 Best Practices

### 1. Choose Appropriate Depth Level

```python
# For quick liquidity check (fastest)
df = await client.fetch_order_book(symbol, limit=5)

# For slippage estimation (moderate)
df = await client.fetch_order_book(symbol, limit=50)

# For deep liquidity analysis (slowest, large data)
df = await client.fetch_order_book(symbol, limit=500)
```

### 2. Sampling Rate

```python
# High-frequency (every 1 second)
# WARNING: Very large data volume!
while True:
    df = await client.fetch_order_book(symbol, limit=20)
    await db_manager.save_order_book_batch(df, symbol)
    await asyncio.sleep(1)

# Medium-frequency (every 10 seconds)
# Good balance between accuracy and storage
await asyncio.sleep(10)

# Low-frequency (every 1 minute)
# Sufficient for most analysis
await asyncio.sleep(60)
```

### 3. Data Retention

```sql
-- Delete old order book data (older than 7 days)
DELETE FROM order_book
WHERE time < NOW() - INTERVAL '7 days';

-- Keep only snapshots at specific intervals (e.g., every hour)
-- For long-term storage
```

### 4. Compression

Since order book data is very large:

```python
# PostgreSQL: Automatic compression after 1 day
SELECT add_compression_policy('order_book', INTERVAL '1 days');

# SQLite: Use VACUUM regularly
db_manager.vacuum()

# Firebase: Delete old snapshots programmatically
await firebase_manager.delete_data(symbol, 'order_book')
```

---

## 📈 Storage Requirements

Order book data is the **largest** data type:

### Size Estimates

| Sampling Rate | Levels | Size per Symbol per Day |
|---------------|--------|-------------------------|
| 1 second | 20 | ~150 MB |
| 10 seconds | 20 | ~15 MB |
| 1 minute | 20 | ~2.5 MB |
| 5 minutes | 20 | ~500 KB |
| 1 second | 100 | ~750 MB |
| 10 seconds | 100 | ~75 MB |

**Recommendation:**
- **Development**: 1 minute, 20 levels
- **Production (analysis)**: 10 seconds, 50 levels
- **Production (HFT)**: 1 second, 100 levels

---

## 🔍 Querying Examples

### Get Order Book at Specific Time

```sql
SELECT *
FROM order_book
WHERE symbol = 'SOL/USDT'
  AND time = '2024-01-15 14:30:00'
  AND level < 10
ORDER BY side, level;
```

### Calculate Average Spread (Last Hour)

```sql
WITH spreads AS (
    SELECT
        time,
        MAX(CASE WHEN side = 'BID' THEN price END) as best_bid,
        MIN(CASE WHEN side = 'ASK' THEN price END) as best_ask
    FROM order_book
    WHERE symbol = 'SOL/USDT'
      AND time > NOW() - INTERVAL '1 hour'
      AND level = 0
    GROUP BY time
)
SELECT
    AVG(best_ask - best_bid) as avg_spread,
    MIN(best_ask - best_bid) as min_spread,
    MAX(best_ask - best_bid) as max_spread
FROM spreads;
```

### Find Large Order Changes

```sql
-- Detect when large orders appear/disappear
WITH current_book AS (
    SELECT * FROM order_book WHERE symbol = 'SOL/USDT' AND time = (SELECT MAX(time) FROM order_book)
),
previous_book AS (
    SELECT * FROM order_book WHERE symbol = 'SOL/USDT' AND time = (
        SELECT MAX(time) FROM order_book WHERE time < (SELECT MAX(time) FROM order_book)
    )
)
SELECT
    c.side,
    c.level,
    c.price,
    c.quantity - COALESCE(p.quantity, 0) as quantity_change
FROM current_book c
LEFT JOIN previous_book p ON c.side = p.side AND c.level = p.level
WHERE ABS(c.quantity - COALESCE(p.quantity, 0)) > 1000  -- Large changes
ORDER BY ABS(c.quantity - COALESCE(p.quantity, 0)) DESC;
```

---

## ⚡ Performance Tips

1. **Use Appropriate Limits**
   - Don't fetch 1000 levels if you only need 10
   - Each level adds to response time and storage

2. **Batch Processing**
   - Collect multiple snapshots before saving
   - Reduces database write overhead

3. **Indexes**
   - Always index `(symbol, time)` for fast queries
   - Index `(side, level)` for order book reconstruction

4. **Partition Tables** (PostgreSQL)
   ```sql
   -- Partition by date for better performance
   CREATE TABLE order_book_2024_01 PARTITION OF order_book
   FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
   ```

5. **Use Materialized Views**
   ```sql
   -- Pre-calculate best bid/ask
   CREATE MATERIALIZED VIEW best_prices AS
   SELECT
       symbol,
       time,
       MAX(CASE WHEN side = 'BID' AND level = 0 THEN price END) as best_bid,
       MIN(CASE WHEN side = 'ASK' AND level = 0 THEN price END) as best_ask
   FROM order_book
   GROUP BY symbol, time;
   ```

---

## 🎓 Summary

✅ **Completed Features:**
- Order book depth collection from Binance
- Storage in SQLite, Firebase, and PostgreSQL
- Spread calculation and analysis
- Flexible depth levels (5 to 1000)
- Query and retrieval functions
- Demo script and documentation

**Next Steps:**
- Run `python scripts/demo_order_book.py` to test
- Integrate with your analysis pipeline
- Experiment with different sampling rates
- Build real-time dashboards

**Need Help?**
- Check examples in this guide
- Review `binance_client.py` source code
- Run the demo script for live examples

Happy Trading! 📊🚀
