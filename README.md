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

## 🔥 Database Options

This project supports **three database backends** that you can switch between with a single configuration change:

1. **SQLite** (Best for local development)
   - ⚡ Zero setup - just works
   - 📁 Single file database
   - 🔧 Perfect for testing and development
   - 💾 Unlimited storage (disk-based)

2. **Firebase Realtime Database** (Best for prototyping)
   - ☁️ Cloud-hosted, zero infrastructure
   - 🔄 Built-in real-time sync
   - 💰 Free tier (1GB storage)
   - 📱 Access from anywhere

3. **PostgreSQL + TimescaleDB** (Best for production)
   - 🚀 Optimized for time-series data
   - 💪 Complex SQL queries
   - ⚡ High performance at scale
   - 🏢 Production-ready

### Quick Switch

Edit `config.yaml`:
```yaml
database_type: "sqlite"  # or "firebase" or "postgresql"
```

Then run:
```bash
python scripts/unified_historical_collection.py
```

**📘 Complete guide:** [DATABASE_SWITCHING.md](DATABASE_SWITCHING.md)
**🔥 Firebase setup:** [FIREBASE_SETUP.md](FIREBASE_SETUP.md)

## 🚀 Quick Start

### Option 0: SQLite Setup (Fastest - Recommended for Getting Started)

The easiest way to get started - no database server required!

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Configure (edit config.yaml)
database_type: "sqlite"

# 3. Run collection
python scripts/unified_historical_collection.py
```

Done! Your data is stored in `data/futures_data.db`.

**📘 See:** [DATABASE_SWITCHING.md](DATABASE_SWITCHING.md) for more options

### Option 1: PostgreSQL Setup (Production)

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

### Option 2: Firebase Setup (Quick & Easy)

For a quick start without setting up PostgreSQL:

### Prerequisites

- Python 3.9+
- Google Account
- Firebase project (free tier available)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Firebase

1. Create Firebase project at [Firebase Console](https://console.firebase.google.com/)
2. Enable Realtime Database
3. Download service account JSON file
4. Configure `config.yaml`:

```yaml
firebase:
  service_account_path: "firebase-service-account.json"
  database_url: "https://your-project.firebaseio.com"
```

See [FIREBASE_SETUP.md](FIREBASE_SETUP.md) for detailed setup instructions.

### 3. Run Data Collection

```bash
# Collect historical data
python scripts/firebase_historical_collection.py

# Start real-time streaming
python scripts/firebase_realtime_stream.py
```

**📘 Complete Firebase guide:** [FIREBASE_SETUP.md](FIREBASE_SETUP.md)

## 📁 Project Structure

```
p1_dataCollection/
├── Claude.md                    # Comprehensive documentation
├── README.md                    # This file
├── FIREBASE_SETUP.md            # Firebase setup guide
├── config.yaml                  # Configuration
├── requirements.txt             # Python dependencies
│
├── data_collector/              # Data collection modules
│   ├── __init__.py
│   ├── binance_client.py        # Binance API client
│   ├── historical_collector.py  # Historical data collector (PostgreSQL)
│   ├── websocket_streamer.py    # Real-time WebSocket streamer (PostgreSQL)
│   ├── firebase_collector.py    # Historical collector (Firebase)
│   └── firebase_websocket.py    # Real-time streamer (Firebase)
│
├── database/                    # Database managers
│   └── firebase_manager.py      # Firebase Realtime Database manager
│
├── data_quality/                # Data validation
│   ├── __init__.py
│   └── validator.py             # Quality checks & monitoring
│
├── schemas/                     # Database schemas
│   └── create_tables.sql        # TimescaleDB table definitions
│
├── scripts/                     # Executable scripts
│   ├── init_database.py                    # Database initialization (PostgreSQL)
│   ├── main_historical_collection.py       # Historical collection (PostgreSQL)
│   ├── start_realtime_stream.py            # Real-time streaming (PostgreSQL)
│   ├── firebase_historical_collection.py   # Historical collection (Firebase)
│   ├── firebase_realtime_stream.py         # Real-time streaming (Firebase)
│   └── health_check.py                     # System health monitoring
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

## 🐳 Docker Deployment

The project includes full Docker support for easy deployment and scalability.

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+

### Quick Start with Docker Compose

The easiest way to run the entire stack:

```bash
# 1. Clone and navigate to project
cd p1_dataCollection

# 2. Create .env file from example
cp .env.example .env

# 3. Edit .env file with your configuration
nano .env  # or use your preferred editor

# 4. Start all services
docker-compose up -d

# 5. Check status
docker-compose ps

# 6. View logs
docker-compose logs -f collector
```

### Docker Compose Services

The `docker-compose.yml` includes:

1. **postgres** - TimescaleDB database
2. **redis** - Cache layer
3. **collector** - Historical data collection
4. **streamer** - Real-time WebSocket streaming
5. **monitor** - Health monitoring
6. **grafana** - Metrics visualization (optional)

### Service Details

#### 1. Start PostgreSQL + TimescaleDB

```bash
# Start only database
docker-compose up -d postgres

# Wait for database to be ready
docker-compose logs -f postgres
# Wait for: "database system is ready to accept connections"

# Initialize database schema
docker-compose exec postgres psql -U postgres -d futures_db -f /docker-entrypoint-initdb.d/create_tables.sql
```

#### 2. Start Redis Cache

```bash
# Start Redis
docker-compose up -d redis

# Verify Redis is running
docker-compose exec redis redis-cli ping
# Should return: PONG
```

#### 3. Start Data Collector

```bash
# Build and start collector
docker-compose up -d collector

# View logs
docker-compose logs -f collector

# Check collection progress
docker-compose exec collector python scripts/health_check.py
```

#### 4. Start Real-time Streamer

```bash
# Start WebSocket streamer
docker-compose up -d streamer

# View streaming logs
docker-compose logs -f streamer
```

#### 5. Start Health Monitor

```bash
# Start monitoring
docker-compose up -d monitor

# View monitoring dashboard
docker-compose logs -f monitor
```

### Configuration

#### Environment Variables (.env)

Create `.env` file from `.env.example`:

```bash
# Binance API
BINANCE_API_KEY=
BINANCE_API_SECRET=
BINANCE_TESTNET=false

# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=futures_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=changeme_strong_password_here

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=

# Collection Settings
COLLECTION_SYMBOLS=SOL/USDT,BTC/USDT
COLLECTION_TIMEFRAMES=5m,15m,1h,4h,1d
HISTORICAL_DAYS=180
```

#### Volume Mounts

Docker Compose mounts these directories:

```yaml
volumes:
  - ./config.yaml:/app/config.yaml          # Configuration
  - ./logs:/app/logs                        # Application logs
  - postgres_data:/var/lib/postgresql/data  # Database persistence
  - redis_data:/data                        # Redis persistence
```

### Docker Commands Reference

#### Basic Operations

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart a service
docker-compose restart collector

# Stop and remove all containers + volumes (⚠️ deletes data!)
docker-compose down -v
```

#### Monitoring & Logs

```bash
# View all logs
docker-compose logs

# Follow logs for specific service
docker-compose logs -f collector

# View last 100 lines
docker-compose logs --tail=100 collector

# Check service status
docker-compose ps

# View resource usage
docker stats
```

#### Accessing Services

```bash
# Execute command in container
docker-compose exec collector python scripts/health_check.py

# Access PostgreSQL shell
docker-compose exec postgres psql -U postgres -d futures_db

# Access Redis CLI
docker-compose exec redis redis-cli

# Access container bash
docker-compose exec collector bash
```

#### Database Management

```bash
# Backup database
docker-compose exec postgres pg_dump -U postgres futures_db > backup.sql

# Restore database
docker-compose exec -T postgres psql -U postgres futures_db < backup.sql

# View database size
docker-compose exec postgres psql -U postgres -d futures_db -c "SELECT pg_size_pretty(pg_database_size('futures_db'));"

# Run VACUUM
docker-compose exec postgres psql -U postgres -d futures_db -c "VACUUM ANALYZE;"
```

### Building Custom Image

If you modify the code:

```bash
# Rebuild collector image
docker-compose build collector

# Rebuild without cache
docker-compose build --no-cache collector

# Build and restart
docker-compose up -d --build collector
```

### Standalone Docker (without Compose)

#### Build Image

```bash
# Build the image
docker build -t p1-collector:latest .

# Build with specific tag
docker build -t p1-collector:1.0.0 .
```

#### Run Container

```bash
# Run collector (requires external database)
docker run -d \
  --name p1-collector \
  --env-file .env \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v $(pwd)/logs:/app/logs \
  p1-collector:latest \
  python scripts/unified_historical_collection.py

# Run with network access to host database
docker run -d \
  --name p1-collector \
  --network host \
  --env-file .env \
  -v $(pwd)/config.yaml:/app/config.yaml \
  p1-collector:latest
```

#### Manage Container

```bash
# View logs
docker logs -f p1-collector

# Execute command
docker exec p1-collector python scripts/health_check.py

# Access bash
docker exec -it p1-collector bash

# Stop container
docker stop p1-collector

# Remove container
docker rm p1-collector
```

### Production Deployment

#### 1. Security Hardening

```bash
# Use secrets instead of environment variables
docker secret create db_password /path/to/password.txt

# Run as non-root user (already configured in Dockerfile)
# The image uses USER 1000:1000
```

#### 2. Resource Limits

Edit `docker-compose.yml`:

```yaml
services:
  collector:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

#### 3. Auto-Restart Policy

```yaml
services:
  collector:
    restart: unless-stopped  # or 'always'
```

#### 4. Health Checks

Already configured in `docker-compose.yml`:

```yaml
healthcheck:
  test: ["CMD", "python", "scripts/health_check.py", "--once"]
  interval: 5m
  timeout: 30s
  retries: 3
  start_period: 40s
```

#### 5. Log Rotation

Configure Docker daemon (`/etc/docker/daemon.json`):

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

### Multi-Server Deployment

#### Using Docker Swarm

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml p1-stack

# List services
docker service ls

# Scale collector
docker service scale p1-stack_collector=3

# View logs
docker service logs p1-stack_collector
```

#### Using Kubernetes

See `k8s/` directory for Kubernetes manifests (if available).

### Troubleshooting Docker

#### Container Won't Start

```bash
# Check logs
docker-compose logs collector

# Check if image built correctly
docker images | grep p1-collector

# Rebuild from scratch
docker-compose build --no-cache collector
```

#### Database Connection Fails

```bash
# Check if postgres is running
docker-compose ps postgres

# Check network
docker-compose exec collector ping postgres

# Check environment variables
docker-compose exec collector env | grep POSTGRES
```

#### Out of Disk Space

```bash
# Clean up unused resources
docker system prune -a

# Remove old volumes
docker volume prune

# Check disk usage
docker system df
```

#### Permission Denied

```bash
# Fix ownership of mounted volumes
sudo chown -R 1000:1000 logs/ data/

# Or run with correct user
docker-compose run --user $(id -u):$(id -g) collector bash
```

### Monitoring with Grafana

If you enabled Grafana in `docker-compose.yml`:

```bash
# Start Grafana
docker-compose up -d grafana

# Access Grafana
# URL: http://localhost:3000
# Default: admin/admin

# Import dashboards from grafana/dashboards/
```

### Backup and Restore

#### Full System Backup

```bash
# Stop services
docker-compose down

# Backup volumes
docker run --rm -v p1_datacollection_postgres_data:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres_backup.tar.gz /data

# Backup configuration
tar czf config_backup.tar.gz config.yaml .env docker-compose.yml

# Restart services
docker-compose up -d
```

#### Restore from Backup

```bash
# Stop services
docker-compose down

# Restore volume
docker run --rm -v p1_datacollection_postgres_data:/data -v $(pwd):/backup ubuntu tar xzf /backup/postgres_backup.tar.gz -C /

# Restore configuration
tar xzf config_backup.tar.gz

# Start services
docker-compose up -d
```

### Performance Tuning

#### 1. Optimize PostgreSQL

```bash
# Edit docker-compose.yml
services:
  postgres:
    command:
      - postgres
      - -c
      - shared_buffers=2GB
      - -c
      - effective_cache_size=6GB
      - -c
      - work_mem=50MB
```

#### 2. Optimize Redis

```bash
services:
  redis:
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
```

#### 3. Use tmpfs for Logs

```yaml
services:
  collector:
    tmpfs:
      - /tmp
      - /app/logs:size=1G
```

### Quick Reference Commands

```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f

# Restart collector
docker-compose restart collector

# Stop everything
docker-compose down

# Clean everything (⚠️ deletes data)
docker-compose down -v && docker system prune -a

# Backup database
docker-compose exec postgres pg_dump -U postgres futures_db > backup_$(date +%Y%m%d).sql

# Check health
docker-compose exec collector python scripts/health_check.py

# Scale services
docker-compose up -d --scale collector=2
```

---

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
