"""
Main Historical Data Collection Script
Collects historical data for all configured symbols and timeframes
"""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import create_engine
import yaml
import sys
import logging
from logging.handlers import RotatingFileHandler
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collector.binance_client import BinanceFuturesClient
from data_collector.historical_collector import HistoricalDataCollector
from data_quality.validator import DataQualityMonitor


def setup_logging(config):
    """Setup comprehensive logging"""
    log_config = config.get('logging', {})
    log_level = log_config.get('level', 'INFO')
    log_file = log_config.get('file', 'logs/data_collection.log')

    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)

    # File handler (rotate at 10MB)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=log_config.get('max_bytes', 10485760),
        backupCount=log_config.get('backup_count', 5)
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


def load_config(config_path='config.yaml'):
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Configuration file not found: {config_path}")
        sys.exit(1)


async def main():
    # Load configuration
    config = load_config()

    # Setup logging
    logger = setup_logging(config)
    logger.info("Starting historical data collection...")

    # Configuration
    collection_config = config['collection']
    symbols = collection_config['symbols']
    timeframes = collection_config['timeframes']
    oi_periods = collection_config['oi_periods']
    historical_days = collection_config['historical_days']

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=historical_days)

    # Initialize database connection
    db_config = config['database']
    connection_string = (
        f"postgresql://{db_config['user']}:{db_config['password']}@"
        f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
    )
    db_engine = create_engine(connection_string)

    # Initialize Binance client
    binance_config = config['binance']
    client = BinanceFuturesClient(
        api_key=binance_config.get('api_key'),
        api_secret=binance_config.get('api_secret'),
        testnet=binance_config.get('testnet', False)
    )

    # Initialize collector and validator
    collector = HistoricalDataCollector(client, db_engine)
    validator = DataQualityMonitor()

    logger.info("=" * 60)
    logger.info("HISTORICAL DATA COLLECTION")
    logger.info(f"Symbols: {', '.join(symbols)}")
    logger.info(f"Date Range: {start_date.date()} to {end_date.date()}")
    logger.info(f"Timeframes: {', '.join(timeframes)}")
    logger.info("=" * 60)

    # Collect data for each symbol
    for symbol in symbols:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {symbol}")
        logger.info(f"{'='*60}")

        # Collect OHLCV for all timeframes
        for tf in timeframes:
            logger.info(f"\n📊 Collecting {tf} OHLCV data for {symbol}...")
            try:
                df = await collector.collect_ohlcv_range(symbol, tf, start_date, end_date)

                if not df.empty:
                    # Validate
                    checks = validator.validate_ohlcv(df, tf)
                    report = validator.generate_quality_report(checks)
                    logger.info(report)
                else:
                    logger.warning(f"No data collected for {symbol} {tf}")

            except Exception as e:
                logger.error(f"Error collecting {symbol} {tf} OHLCV: {e}")
                continue

        # Collect OI data
        for period in oi_periods:
            logger.info(f"\n📈 Collecting {period} OI data for {symbol}...")
            try:
                df = await collector.collect_oi_range(symbol, period, start_date, end_date)

                if not df.empty:
                    # Validate
                    checks = validator.validate_oi(df)
                    report = validator.generate_quality_report(checks)
                    logger.info(report)
                else:
                    logger.warning(f"No OI data collected for {symbol} {period}")

            except Exception as e:
                logger.error(f"Error collecting {symbol} {period} OI: {e}")
                continue

        # Collect funding rate
        logger.info(f"\n💰 Collecting Funding Rate data for {symbol}...")
        try:
            df = await client.fetch_funding_rate_history(symbol)
            df = df[(df['fundingTime'] >= start_date) & (df['fundingTime'] <= end_date)]

            if not df.empty:
                df['symbol'] = symbol
                df.to_sql(
                    'funding_rate',
                    db_engine,
                    if_exists='append',
                    index=False,
                    method='multi'
                )
                logger.info(f"Saved {len(df)} funding rate records")

                # Validate
                checks = validator.validate_funding_rate(df)
                report = validator.generate_quality_report(checks)
                logger.info(report)

        except Exception as e:
            logger.error(f"Error collecting {symbol} funding rate: {e}")

        # Collect liquidation data
        logger.info(f"\n🔥 Collecting Liquidation data for {symbol}...")
        try:
            liq_df = await client.fetch_liquidations(symbol, limit=1000)

            if not liq_df.empty:
                liq_df = liq_df[(liq_df['time'] >= start_date) & (liq_df['time'] <= end_date)]
                liq_df['symbol'] = symbol
                liq_df = liq_df.rename(columns={'origQty': 'quantity', 'orderId': 'order_id'})
                liq_df.to_sql(
                    'liquidations',
                    db_engine,
                    if_exists='append',
                    index=False,
                    method='multi'
                )
                logger.info(f"Saved {len(liq_df)} liquidation records")

        except Exception as e:
            logger.error(f"Error collecting {symbol} liquidations: {e}")

        # Collect long/short ratio
        for period in oi_periods:
            logger.info(f"\n⚖️ Collecting Long/Short Ratio {period} data for {symbol}...")
            try:
                ls_df = await client.fetch_top_trader_ratio(symbol, period=period)
                ls_df = ls_df[(ls_df['timestamp'] >= start_date) & (ls_df['timestamp'] <= end_date)]

                if not ls_df.empty:
                    ls_df['symbol'] = symbol
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
                    logger.info(f"Saved {len(ls_df)} long/short ratio records")

            except Exception as e:
                logger.error(f"Error collecting {symbol} {period} long/short ratio: {e}")

    logger.info("\n" + "=" * 60)
    logger.info("✅ DATA COLLECTION COMPLETE!")
    logger.info("=" * 60)

    # Cleanup
    db_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
