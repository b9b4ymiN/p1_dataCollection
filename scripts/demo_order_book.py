"""
Order Book Collection Demo
Demonstrates how to collect and store order book depth data
"""

import asyncio
import yaml
import logging
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collector.binance_client import BinanceFuturesClient
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
    """Demo: Collect and save order book snapshots"""
    print("=" * 80)
    print("📊 ORDER BOOK DEPTH COLLECTION DEMO")
    print("=" * 80)

    # Load configuration
    config_path = 'config.yaml'
    if not os.path.exists(config_path):
        logger.error("❌ config.yaml not found")
        return

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Initialize Binance client
    binance_config = config['binance']
    client = BinanceFuturesClient(
        api_key=binance_config.get('api_key'),
        api_secret=binance_config.get('api_secret'),
        testnet=binance_config.get('testnet', False)
    )

    # Initialize database
    db_manager = DatabaseFactory.create_database(config)

    # Collection parameters
    symbol = config['collection']['symbols'][0]  # First symbol from config
    depth_limit = 20  # Get top 20 levels (20 bids + 20 asks)

    print(f"\n📈 Symbol: {symbol}")
    print(f"📊 Depth Levels: {depth_limit}")
    print(f"💾 Database: {config.get('database_type', 'sqlite').upper()}")
    print("=" * 80)

    try:
        # Fetch order book
        print(f"\n🔍 Fetching order book snapshot...")
        df = await client.fetch_order_book(symbol, limit=depth_limit)

        # Display order book info
        print(f"\n✅ Order Book Retrieved!")
        print(f"   Total Levels: {len(df)}")
        print(f"   Bids: {len(df[df['side'] == 'BID'])}")
        print(f"   Asks: {len(df[df['side'] == 'ASK'])}")

        # Display spread information
        if hasattr(df, 'attrs'):
            print(f"\n📊 Market Spread:")
            print(f"   Best Bid:  ${df.attrs.get('best_bid', 0):.4f}")
            print(f"   Best Ask:  ${df.attrs.get('best_ask', 0):.4f}")
            print(f"   Spread:    ${df.attrs.get('spread', 0):.4f}")
            print(f"   Spread(bps): {df.attrs.get('spread_bps', 0):.2f} bps")
            print(f"   Mid Price: ${df.attrs.get('mid_price', 0):.4f}")

        # Display top 5 bids and asks
        print(f"\n📊 Top 5 Bids (Buy Orders):")
        print(f"{'Level':<8} {'Price':<15} {'Quantity':<15}")
        print("-" * 40)
        bids = df[df['side'] == 'BID'].head(5)
        for _, row in bids.iterrows():
            print(f"{row['level']:<8} ${row['price']:<14.4f} {row['quantity']:<15.2f}")

        print(f"\n📊 Top 5 Asks (Sell Orders):")
        print(f"{'Level':<8} {'Price':<15} {'Quantity':<15}")
        print("-" * 40)
        asks = df[df['side'] == 'ASK'].head(5)
        for _, row in asks.iterrows():
            print(f"{row['level']:<8} ${row['price']:<14.4f} {row['quantity']:<15.2f}")

        # Save to database
        print(f"\n💾 Saving to database...")
        await db_manager.save_order_book_batch(df, symbol)

        # Retrieve back from database
        print(f"\n🔍 Retrieving latest order book from database...")
        latest_df = await db_manager.get_latest_order_book(symbol, limit_levels=5)

        if not latest_df.empty:
            print(f"\n✅ Retrieved {len(latest_df)} levels from database")
            print(f"   Timestamp: {latest_df['time'].iloc[0]}")

            # Display retrieved data
            print(f"\n📊 Retrieved Top 5 from Database:")
            print(f"{'Side':<6} {'Level':<8} {'Price':<15} {'Quantity':<15}")
            print("-" * 45)
            for _, row in latest_df.head(10).iterrows():
                print(f"{row['side']:<6} {row['level']:<8} ${row['price']:<14.4f} {row['quantity']:<15.2f}")

        # Demo: Continuous collection (commented out - uncomment for real-time)
        print(f"\n💡 For continuous real-time collection, run:")
        print(f"   python scripts/collect_order_book_realtime.py")

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)

    finally:
        # Cleanup
        if db_manager:
            db_manager.cleanup()

    print(f"\n{'=' * 80}")
    print("✅ Order Book Collection Demo Complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Demo interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
