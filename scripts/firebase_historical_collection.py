"""
Firebase Historical Data Collection Script
Collects historical cryptocurrency futures data and stores in Firebase
"""

import asyncio
import yaml
import logging
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.firebase_manager import FirebaseManager
from data_collector.firebase_collector import FirebaseDataCollector
from pythonjsonlogger import jsonlogger

# Setup logging
log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
log_handler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)


async def main():
    """Main collection function"""
    # Load configuration
    config_path = 'config.yaml'
    if not os.path.exists(config_path):
        logger.error("❌ config.yaml not found. Please create one from config.yaml.example")
        return

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Load Firebase configuration
    firebase_config = config.get('firebase', {})
    if not firebase_config:
        logger.error("❌ Firebase configuration not found in config.yaml")
        logger.info("Please add Firebase configuration:")
        logger.info("firebase:")
        logger.info("  service_account_path: 'path/to/service-account.json'")
        logger.info("  database_url: 'https://your-project.firebaseio.com'")
        return

    service_account_path = firebase_config.get('service_account_path')
    database_url = firebase_config.get('database_url')

    if not service_account_path or not database_url:
        logger.error("❌ Firebase credentials missing")
        return

    # Initialize Firebase
    firebase = FirebaseManager(service_account_path, database_url)
    firebase.initialize()

    # Initialize collector
    collector = FirebaseDataCollector(config, firebase)
    await collector.initialize()

    # Collection parameters
    collection_config = config['collection']
    symbols = collection_config['symbols']
    historical_days = collection_config.get('historical_days', 180)

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=historical_days)

    logger.info(f"📅 Collection period: {start_date.date()} to {end_date.date()}")
    logger.info(f"📊 Symbols: {symbols}")

    # Collect data for each symbol
    for symbol in symbols:
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 Starting collection for {symbol}")
        logger.info(f"{'='*60}\n")

        try:
            results = await collector.collect_all_data_concurrent(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )

            # Print summary
            logger.info(f"\n📊 Collection Summary for {symbol}:")
            total_records = 0
            for data_type, result in results.items():
                if result['status'] == 'success':
                    records = result['records']
                    total_records += records
                    logger.info(f"  ✅ {data_type}: {records:,} records")
                else:
                    logger.error(f"  ❌ {data_type}: {result['error']}")

            logger.info(f"\n🎉 Total records collected for {symbol}: {total_records:,}")

        except Exception as e:
            logger.error(f"❌ Error collecting {symbol}: {e}")
            continue

    # Cleanup
    await collector.cleanup()

    logger.info("\n✅ Historical data collection completed!")
    logger.info("🔥 Data is now available in Firebase Realtime Database")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️ Collection interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
