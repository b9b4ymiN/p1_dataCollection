-- Phase 1 Data Collection Schema
-- TimescaleDB Hypertables for Time-Series Data

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Table 1: OHLCV (Candlestick Data)
CREATE TABLE IF NOT EXISTS ohlcv (
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
SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_time ON ohlcv (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_ohlcv_timeframe ON ohlcv (timeframe, time DESC);

-- Table 2: Open Interest
CREATE TABLE IF NOT EXISTS open_interest (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    period VARCHAR(5) NOT NULL,
    open_interest NUMERIC(20, 8),
    open_interest_value NUMERIC(20, 2),
    PRIMARY KEY (time, symbol, period)
);

-- Convert to hypertable
SELECT create_hypertable('open_interest', 'time', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_oi_symbol_time ON open_interest (symbol, time DESC);

-- Table 3: Funding Rate
CREATE TABLE IF NOT EXISTS funding_rate (
    funding_time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    funding_rate NUMERIC(10, 8),
    mark_price NUMERIC(18, 8),
    PRIMARY KEY (funding_time, symbol)
);

-- Convert to hypertable
SELECT create_hypertable('funding_rate', 'funding_time', if_not_exists => TRUE);

-- Table 4: Liquidations
CREATE TABLE IF NOT EXISTS liquidations (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10),
    price NUMERIC(18, 8),
    quantity NUMERIC(20, 8),
    order_id BIGINT UNIQUE
);

-- Convert to hypertable
SELECT create_hypertable('liquidations', 'time', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_liq_symbol_side ON liquidations (symbol, side, time DESC);

-- Table 5: Long/Short Ratio
CREATE TABLE IF NOT EXISTS long_short_ratio (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    period VARCHAR(5) NOT NULL,
    long_short_ratio NUMERIC(10, 6),
    long_account NUMERIC(10, 6),
    short_account NUMERIC(10, 6),
    PRIMARY KEY (time, symbol, period)
);

-- Convert to hypertable
SELECT create_hypertable('long_short_ratio', 'time', if_not_exists => TRUE);

-- Table 6: Order Book Snapshots
CREATE TABLE IF NOT EXISTS order_book (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(3) NOT NULL,  -- BID or ASK
    level INTEGER NOT NULL,    -- 0 = best bid/ask, 1 = second level, etc.
    price NUMERIC(18, 8) NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    PRIMARY KEY (time, symbol, side, level)
);

-- Convert to hypertable
SELECT create_hypertable('order_book', 'time', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_ob_symbol_time ON order_book (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_ob_side_level ON order_book (side, level);

-- Table 7: Data Versions (for tracking)
CREATE TABLE IF NOT EXISTS data_versions (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(50),
    version VARCHAR(20),
    collection_date TIMESTAMPTZ,
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    record_count BIGINT,
    checksum VARCHAR(64)
);

-- Materialized View: OI and Price Correlation (1 hour aggregation)
CREATE MATERIALIZED VIEW IF NOT EXISTS oi_price_1h AS
SELECT
    time_bucket('1 hour', o.time) AS bucket,
    o.symbol,
    AVG(o.open_interest) AS avg_oi,
    LAST(p.close, p.time) AS close_price,
    LAST(o.open_interest, o.time) - FIRST(o.open_interest, o.time) AS oi_change,
    (LAST(p.close, p.time) - FIRST(p.close, p.time)) / NULLIF(FIRST(p.close, p.time), 0) * 100 AS price_change_pct
FROM open_interest o
JOIN ohlcv p ON o.symbol = p.symbol
    AND o.time >= p.time
    AND o.time < p.time + INTERVAL '5 minutes'
WHERE p.timeframe = '5m'
GROUP BY bucket, o.symbol;

-- Create index on materialized view
CREATE INDEX IF NOT EXISTS idx_oi_price_1h_bucket ON oi_price_1h (bucket DESC, symbol);

-- Add continuous aggregate policy (refresh every 5 minutes)
-- Note: This requires the continuous aggregate to be created first
-- Uncomment if you want automatic refreshing:
-- SELECT add_continuous_aggregate_policy('oi_price_1h',
--     start_offset => INTERVAL '2 hours',
--     end_offset => INTERVAL '5 minutes',
--     schedule_interval => INTERVAL '5 minutes');

-- Compression policy (compress data older than 7 days)
SELECT add_compression_policy('ohlcv', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('open_interest', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('funding_rate', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('liquidations', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('long_short_ratio', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('order_book', INTERVAL '1 days', if_not_exists => TRUE);  -- Compress sooner (large data)

-- Retention policy (optional - uncomment to auto-delete old data)
-- SELECT add_retention_policy('ohlcv', INTERVAL '1 year', if_not_exists => TRUE);
-- SELECT add_retention_policy('open_interest', INTERVAL '1 year', if_not_exists => TRUE);

COMMENT ON TABLE ohlcv IS 'OHLCV candlestick data for multiple timeframes';
COMMENT ON TABLE open_interest IS 'Open interest data from Binance Futures';
COMMENT ON TABLE funding_rate IS 'Funding rate history';
COMMENT ON TABLE liquidations IS 'Liquidation orders (forced closures)';
COMMENT ON TABLE long_short_ratio IS 'Top trader long/short account ratio';
COMMENT ON TABLE order_book IS 'Order book depth snapshots (bids and asks)';
COMMENT ON TABLE data_versions IS 'Metadata for tracking data collection versions';
