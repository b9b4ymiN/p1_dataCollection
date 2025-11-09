"""
Optimized Historical Data Collection Script
High-performance concurrent data collection with monitoring
"""

import asyncio
from datetime import datetime, timedelta
import yaml
import sys
import logging
from logging.handlers import RotatingFileHandler
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collector.optimized_collector import OptimizedDataCollector
from utils.performance_monitor import PerformanceMonitor, Timer
from utils.cache_manager import CacheManager


def setup_logging(config):
    """Setup comprehensive logging"""
    log_config = config.get('logging', {})
    log_level = log_config.get('level', 'INFO')
    log_file = log_config.get('file', 'logs/optimized_collection.log')

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=log_config.get('max_bytes', 10485760),
        backupCount=log_config.get('backup_count', 5)
    )
    file_handler.setLevel(logging.DEBUG)

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
    """Main optimized collection process"""
    # Load configuration
    config = load_config()
    logger = setup_logging(config)

    logger.info("=" * 80)
    logger.info("OPTIMIZED DATA COLLECTION - HIGH PERFORMANCE MODE")
    logger.info("=" * 80)

    # Initialize performance monitor
    perf_monitor = PerformanceMonitor()

    # Initialize cache manager
    cache_manager = CacheManager(config)
    if not cache_manager.health_check():
        logger.warning("Redis is not available - cache disabled")

    # Configuration
    collection_config = config['collection']
    symbols = collection_config['symbols']
    historical_days = collection_config['historical_days']

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=historical_days)

    logger.info(f"Symbols: {', '.join(symbols)}")
    logger.info(f"Date Range: {start_date.date()} to {end_date.date()}")
    logger.info(f"Collection Mode: Concurrent (All data types in parallel)")
    logger.info("=" * 80)

    # Initialize optimized collector
    collector = OptimizedDataCollector(config)
    await collector.initialize()

    # Collect data for each symbol concurrently
    all_start_time = datetime.now()

    # Create tasks for all symbols
    symbol_tasks = []
    for symbol in symbols:
        task = collector.collect_all_data_concurrent(symbol, start_date, end_date)
        symbol_tasks.append((symbol, task))

    # Execute all symbol collections in parallel
    logger.info(f"\n🚀 Starting concurrent collection for {len(symbols)} symbols...")

    with Timer("Total collection") as total_timer:
        results = await asyncio.gather(*[task for _, task in symbol_tasks], return_exceptions=True)

    # Process results
    total_records = 0
    for i, (symbol, _) in enumerate(symbol_tasks):
        result = results[i]
        if isinstance(result, Exception):
            logger.error(f"❌ {symbol}: {result}")
        else:
            logger.info(f"✅ {symbol}: Collection completed")

    all_end_time = datetime.now()
    total_duration = (all_end_time - all_start_time).total_seconds()

    # Print performance summary
    logger.info("\n" + "=" * 80)
    logger.info("COLLECTION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total Duration: {total_duration:.2f} seconds")
    logger.info(f"Average per symbol: {total_duration / len(symbols):.2f} seconds")

    # Cache statistics
    cache_stats = cache_manager.get_stats()
    logger.info(f"\nCache Performance:")
    logger.info(f"  Hit Rate: {cache_stats['hit_rate']}")
    logger.info(f"  Total Hits: {cache_stats['hits']}")
    logger.info(f"  Total Misses: {cache_stats['misses']}")

    # Performance metrics
    logger.info("\nPerformance Metrics:")
    perf_summary = perf_monitor.get_summary()
    if 'rates' in perf_summary:
        logger.info(f"  API Calls/sec: {perf_summary['rates'].get('api_calls_per_second', 0):.2f}")
        logger.info(f"  DB Ops/sec: {perf_summary['rates'].get('db_ops_per_second', 0):.2f}")

    logger.info("=" * 80)

    # Cleanup
    await collector.cleanup()
    cache_manager.close()


if __name__ == "__main__":
    # Run with uvloop for better performance (if available)
    # Ensure a minimal logger is available for the module-level scope so the
    # uvloop message can be logged even before `setup_logging` runs inside
    # `main()` (this prevents NameError: name 'logger' is not defined).
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    try:
        import uvloop
        uvloop.install()
        logger.info("Using uvloop for enhanced performance")
    except ImportError:
        pass

    asyncio.run(main())
