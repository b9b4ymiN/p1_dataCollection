"""
Unified Historical Data Collection Script
Works with SQLite, Firebase, or PostgreSQL based on configuration
"""

import asyncio
import yaml
import logging
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collector.unified_collector import UnifiedDataCollector
from database.db_factory import DatabaseFactory
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
    print("=" * 80)
    print("🔥 UNIFIED DATA COLLECTOR")
    print("=" * 80)

    # Load configuration
    config_path = 'config.yaml'
    if not os.path.exists(config_path):
        logger.error("❌ config.yaml not found. Please create one from the example")
        return

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Validate configuration
    is_valid, error_msg = DatabaseFactory.validate_config(config)
    if not is_valid:
        logger.error(f"❌ Configuration error: {error_msg}")
        return

    db_type = config.get('database_type', 'sqlite').upper()
    print(f"\n📊 Database Type: {db_type}")
    print("=" * 80)

    # Initialize collector
    collector = UnifiedDataCollector(config)
    await collector.initialize()

    # Display database info
    db_info = collector.get_database_info()
    print(f"\n📁 Database Info:")
    for key, value in db_info.items():
        print(f"  {key}: {value}")

    # Collection parameters
    collection_config = config['collection']
    symbols = collection_config['symbols']
    historical_days = collection_config.get('historical_days', 180)

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=historical_days)

    print(f"\n📅 Collection Period:")
    print(f"  Start: {start_date.date()}")
    print(f"  End: {end_date.date()}")
    print(f"  Days: {historical_days}")
    print(f"\n📊 Symbols: {', '.join(symbols)}")
    print(f"📈 Timeframes: {', '.join(collection_config['timeframes'])}")
    print(f"⏰ OI Periods: {', '.join(collection_config['oi_periods'])}")
    print("=" * 80)

    # Collect data for each symbol
    all_results = {}

    for i, symbol in enumerate(symbols, 1):
        print(f"\n{'=' * 80}")
        print(f"🚀 [{i}/{len(symbols)}] Starting collection for {symbol}")
        print(f"{'=' * 80}\n")

        try:
            results = await collector.collect_all_data_concurrent(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )

            # Store results
            all_results[symbol] = results

            # Print summary
            print(f"\n📊 Collection Summary for {symbol}:")
            print("-" * 80)

            total_records = 0
            success_count = 0
            error_count = 0

            for data_type, result in results.items():
                if result['status'] == 'success':
                    records = result['records']
                    total_records += records
                    success_count += 1
                    print(f"  ✅ {data_type:20s}: {records:>8,} records")
                else:
                    error_count += 1
                    print(f"  ❌ {data_type:20s}: {result['error']}")

            print("-" * 80)
            print(f"  📈 Total Records: {total_records:,}")
            print(f"  ✅ Successful: {success_count}")
            if error_count > 0:
                print(f"  ❌ Errors: {error_count}")

        except Exception as e:
            logger.error(f"❌ Error collecting {symbol}: {e}")
            all_results[symbol] = {'error': str(e)}
            continue

    # Final summary
    print(f"\n{'=' * 80}")
    print("🎉 COLLECTION COMPLETE")
    print(f"{'=' * 80}")

    total_symbols = len(symbols)
    successful_symbols = sum(1 for r in all_results.values() if 'error' not in r)
    grand_total_records = 0

    for symbol, results in all_results.items():
        if 'error' not in results:
            symbol_total = sum(
                r['records'] for r in results.values()
                if r['status'] == 'success'
            )
            grand_total_records += symbol_total

    print(f"\n📊 Overall Statistics:")
    print(f"  Total Symbols: {total_symbols}")
    print(f"  Successful: {successful_symbols}")
    print(f"  Total Records: {grand_total_records:,}")
    print(f"  Database: {db_type}")

    if db_type == 'SQLITE' and hasattr(collector.db_manager, 'get_database_size'):
        size_mb = collector.db_manager.get_database_size()
        print(f"  Database Size: {size_mb:.2f} MB")

    # Cleanup
    await collector.cleanup()

    print(f"\n✅ Historical data collection completed!")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Collection interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
