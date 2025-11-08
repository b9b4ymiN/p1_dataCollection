"""
Health Check Script
Verifies system is collecting data properly
"""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import redis
import yaml
import sys
import logging
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collector.binance_client import BinanceFuturesClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path='config.yaml'):
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)


async def health_check(config):
    """Verify system is collecting data properly"""

    checks = {
        'database': False,
        'redis': False,
        'binance_api': False,
        'data_freshness': False,
        'data_completeness': False
    }

    # Database check
    logger.info("Checking database connection...")
    try:
        db_config = config['database']
        connection_string = (
            f"postgresql://{db_config['user']}:{db_config['password']}@"
            f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
        )
        engine = create_engine(connection_string)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.scalar()
        checks['database'] = True
        logger.info("✅ Database connection: OK")
    except Exception as e:
        logger.error(f"❌ Database check failed: {e}")

    # Redis check
    logger.info("Checking Redis connection...")
    try:
        redis_config = config['redis']
        redis_client = redis.Redis(
            host=redis_config['host'],
            port=redis_config['port'],
            db=redis_config['db'],
            password=redis_config.get('password', None)
        )
        redis_client.ping()
        checks['redis'] = True
        logger.info("✅ Redis connection: OK")
    except Exception as e:
        logger.error(f"❌ Redis check failed: {e}")

    # Binance API check
    logger.info("Checking Binance API connection...")
    try:
        binance_config = config['binance']
        client = BinanceFuturesClient(
            api_key=binance_config.get('api_key'),
            api_secret=binance_config.get('api_secret'),
            testnet=binance_config.get('testnet', False)
        )
        # Try to fetch ticker
        symbol = config['collection']['symbols'][0]
        await client.exchange.fetch_ticker(symbol)
        checks['binance_api'] = True
        logger.info("✅ Binance API connection: OK")
    except Exception as e:
        logger.error(f"❌ Binance API check failed: {e}")

    # Data freshness check (should be < 1 hour old)
    logger.info("Checking data freshness...")
    try:
        symbol = config['collection']['symbols'][0].replace('/', '')
        query = f"""
            SELECT MAX(time) as latest_time
            FROM ohlcv
            WHERE symbol = '{symbol}'
        """
        with engine.connect() as conn:
            result = conn.execute(text(query))
            row = result.fetchone()
            if row and row[0]:
                latest = row[0]
                age = datetime.now() - latest.replace(tzinfo=None)
                checks['data_freshness'] = age < timedelta(hours=1)
                logger.info(f"Latest data timestamp: {latest} (age: {age})")
                if checks['data_freshness']:
                    logger.info("✅ Data freshness: OK")
                else:
                    logger.warning(f"⚠️ Data is {age} old (expected < 1 hour)")
            else:
                logger.warning("⚠️ No data found in database")
    except Exception as e:
        logger.error(f"❌ Data freshness check failed: {e}")

    # Data completeness check
    logger.info("Checking data completeness...")
    try:
        query = """
            SELECT
                table_name,
                COUNT(*) as record_count
            FROM (
                SELECT 'ohlcv' as table_name FROM ohlcv
                UNION ALL
                SELECT 'open_interest' FROM open_interest
                UNION ALL
                SELECT 'funding_rate' FROM funding_rate
            ) as combined
            GROUP BY table_name
        """
        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()

            table_counts = {row[0]: row[1] for row in rows}
            expected_tables = ['ohlcv', 'open_interest', 'funding_rate']

            all_present = all(table in table_counts and table_counts[table] > 0
                            for table in expected_tables)
            checks['data_completeness'] = all_present

            logger.info("Table record counts:")
            for table, count in table_counts.items():
                logger.info(f"  {table}: {count:,} records")

            if checks['data_completeness']:
                logger.info("✅ Data completeness: OK")
            else:
                logger.warning("⚠️ Some tables are missing data")

    except Exception as e:
        logger.error(f"❌ Data completeness check failed: {e}")

    # Report
    all_healthy = all(checks.values())
    status = "✅ HEALTHY" if all_healthy else "⚠️ DEGRADED"

    print("\n" + "=" * 60)
    print(f"SYSTEM HEALTH CHECK - {status}")
    print("=" * 60)

    for check, result in checks.items():
        status_icon = "✅" if result else "❌"
        print(f"{status_icon} {check.replace('_', ' ').title()}: {'PASS' if result else 'FAIL'}")

    print("=" * 60)

    # Cleanup
    if 'engine' in locals():
        engine.dispose()

    return all_healthy


async def continuous_monitoring(config, interval=300):
    """Run health checks continuously"""
    logger.info(f"Starting continuous monitoring (interval: {interval}s)...")

    while True:
        await health_check(config)
        logger.info(f"\nNext check in {interval} seconds...")
        await asyncio.sleep(interval)


def main():
    """Main entry point"""
    config = load_config()

    # Check if continuous mode
    if len(sys.argv) > 1 and sys.argv[1] == '--continuous':
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
        asyncio.run(continuous_monitoring(config, interval))
    else:
        asyncio.run(health_check(config))


if __name__ == "__main__":
    main()
