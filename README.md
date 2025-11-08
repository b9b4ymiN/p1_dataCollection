# Phase 1: Data Infrastructure & Collection

Building the foundation for AI-powered Open Interest (OI) trading with robust, real-time data collection from Binance Futures API.

## 🎯 Project Overview

This project implements a comprehensive data collection system for cryptocurrency futures trading, focusing on:
- Open Interest (OI) tracking
- Price & Volume (OHLCV) data
- Funding rates
- Liquidation data
- Long/Short ratios

All data is stored in a TimescaleDB database optimized for time-series analysis.

## 📋 Features

- ✅ Real-time data streaming via WebSocket
- ✅ Historical data collection (6+ months)
- ✅ TimescaleDB for efficient time-series storage
- ✅ Redis caching for real-time data
- ✅ Comprehensive data quality monitoring
- ✅ Automatic retry and rate limiting
- ✅ Graceful error handling

## ⚡ Performance Optimizations

- 🚀 **10-50x faster** data collection with concurrent operations
- 🔥 **50-100x faster** database writes with batch inserts
- ⚡ **Sub-millisecond** cache response times (msgpack + Redis)
- 📊 **Real-time monitoring** with performance metrics
- 💾 **40-60% less memory** usage with optimizations

See [PERFORMANCE.md](PERFORMANCE.md) for detailed optimization guide.

## 🛡️ Error Hardening & Resilience

- 🔄 **Automatic retry** with exponential backoff (5 attempts)
- ⚡ **Circuit breakers** prevent cascading failures
- 📊 **Error tracking** with counters and metrics
- 🚨 **Real-time error monitoring** dashboard
- 🔧 **Automatic recovery** from transient failures
- 📈 **Error alerting** when thresholds exceeded

See [ERROR_HARDENING.md](ERROR_HARDENING.md) for complete error handling guide.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   BINANCE API LAYER                     │
│  REST API (Historical) + WebSocket (Real-time)          │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│              DATA COLLECTOR LAYER                       │
│  Historical Collector │ WebSocket Stream │ Validator    │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│                 STORAGE LAYER                           │
│  PostgreSQL + TimescaleDB │ Redis Cache                 │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 14+
- TimescaleDB extension
- Redis server

### 1. Install Dependencies

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt install postgresql postgresql-contrib redis-server

# Install TimescaleDB
sudo add-apt-repository ppa:timescale/timescaledb-ppa
sudo apt update
sudo apt install timescaledb-postgresql-14

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Setup Database

```bash
# Initialize TimescaleDB
sudo timescaledb-tune
sudo systemctl restart postgresql

# Create database
sudo -u postgres psql
CREATE DATABASE futures_db;
\c futures_db
CREATE EXTENSION IF NOT EXISTS timescaledb;
\q

# Create tables
python scripts/init_database.py
```

### 3. Configure

Edit `config.yaml` with your settings:

```yaml
database:
  host: "localhost"
  port: 5432
  database: "futures_db"
  user: "your_username"
  password: "your_password"

collection:
  symbols:
    - "SOL/USDT"
  historical_days: 180
```

### 4. Run Data Collection

```bash
# Collect historical data
python scripts/main_historical_collection.py

# Start real-time streaming (in background)
python scripts/start_realtime_stream.py &

# Run health check
python scripts/health_check.py
```

## 📁 Project Structure

```
p1_dataCollection/
├── Claude.md                    # Comprehensive documentation
├── README.md                    # This file
├── config.yaml                  # Configuration
├── requirements.txt             # Python dependencies
│
├── data_collector/              # Data collection modules
│   ├── __init__.py
│   ├── binance_client.py        # Binance API client
│   ├── historical_collector.py  # Historical data collector
│   └── websocket_streamer.py    # Real-time WebSocket streamer
│
├── data_quality/                # Data validation
│   ├── __init__.py
│   └── validator.py             # Quality checks & monitoring
│
├── schemas/                     # Database schemas
│   └── create_tables.sql        # TimescaleDB table definitions
│
├── scripts/                     # Executable scripts
│   ├── init_database.py         # Database initialization
│   ├── main_historical_collection.py  # Historical data collection
│   ├── start_realtime_stream.py       # Real-time streaming
│   └── health_check.py          # System health monitoring
│
└── logs/                        # Application logs
    └── .gitkeep
```

## 🔧 Usage

### Collect Historical Data

```bash
python scripts/main_historical_collection.py
```

This will:
- Collect OHLCV data for all configured timeframes
- Collect Open Interest data
- Collect funding rates
- Collect liquidation data
- Collect long/short ratios
- Validate all data quality

### Start Real-time Streaming

```bash
python scripts/start_realtime_stream.py
```

Streams real-time data to Redis cache for:
- Latest price updates
- Mark price and funding rates

### Run Health Checks

```bash
# Single check
python scripts/health_check.py

# Continuous monitoring (every 5 minutes)
python scripts/health_check.py --continuous 300
```

## 📊 Database Schema

### Main Tables

- **ohlcv**: Candlestick data (5 timeframes)
- **open_interest**: OI tracking
- **funding_rate**: Funding rate history
- **liquidations**: Forced liquidation orders
- **long_short_ratio**: Top trader sentiment
- **data_versions**: Data collection metadata

All tables use TimescaleDB hypertables for optimized time-series queries.

## 🔍 Data Quality Monitoring

The system includes comprehensive quality checks:

- ✅ Null value detection
- ✅ Duplicate detection
- ✅ OHLC relationship validation
- ✅ Time continuity checking
- ✅ Outlier detection (>10% price spikes)
- ✅ Data freshness monitoring

## 📈 Example Queries

```sql
-- Get latest OHLCV data
SELECT * FROM ohlcv
WHERE symbol = 'SOL/USDT' AND timeframe = '5m'
ORDER BY time DESC
LIMIT 100;

-- Check OI and price correlation
SELECT * FROM oi_price_1h
WHERE symbol = 'SOL/USDT'
ORDER BY bucket DESC
LIMIT 20;

-- Find data gaps
SELECT time, LAG(time) OVER (ORDER BY time) as prev_time,
       time - LAG(time) OVER (ORDER BY time) as gap
FROM ohlcv
WHERE symbol = 'SOL/USDT' AND timeframe = '5m'
ORDER BY time DESC;
```

## 🛠️ Troubleshooting

### Issue: API Rate Limit Exceeded

**Solution:** Adjust rate limiting in `config.yaml`:
```yaml
binance:
  rate_limit: 2000  # Increase if needed
```

### Issue: WebSocket Connection Drops

The streamer automatically reconnects with exponential backoff. Check logs for details.

### Issue: Database Connection Pool Exhausted

Increase pool size in the database connection settings.

For more troubleshooting tips, see [Claude.md](Claude.md).

## 📚 Documentation

- **Claude.md**: Complete technical documentation with code examples
- **schemas/create_tables.sql**: Database schema definitions
- **config.yaml**: Configuration reference

## 🔐 Security Notes

- Store credentials in environment variables or `.env` file
- Never commit API keys to version control
- Use read-only database users for query-only applications

## 🚧 Next Steps: Phase 2

Once data collection is stable:
1. Feature engineering (100+ features)
2. ML model development
3. Backtesting framework
4. Live trading integration

## 📝 License

This project is for educational and research purposes.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## ⚠️ Disclaimer

This software is for educational purposes only. Trading cryptocurrencies carries risk. Always do your own research and never trade with money you can't afford to lose.

---

**Need Help?** Check [Claude.md](Claude.md) for comprehensive documentation and troubleshooting guides.
