"""
Test Order Book Collection
Quick test to verify order book endpoint and data quality
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_collector.binance_client import BinanceFuturesClient
from data_quality.validator import DataQualityMonitor
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_order_book():
    """Test order book collection and validation"""
    
    # Initialize client (testnet=False for real data)
    client = BinanceFuturesClient(testnet=False)
    validator = DataQualityMonitor()
    
    symbol = "SOL/USDT"
    
    print("=" * 60)
    print("ORDER BOOK COLLECTION TEST")
    print("=" * 60)
    
    try:
        # Test 1: Fetch order book data
        print(f"\n📊 Testing Order Book Fetch for {symbol}...")
        df = await client.fetch_order_book(symbol, limit=20)
        
        if df.empty:
            print("❌ No data returned!")
            return
        
        print(f"✅ Fetched {len(df)} order book entries")
        print(f"\nColumns: {list(df.columns)}")
        print(f"\nFirst few rows:")
        print(df.head(10))
        
        # Test 2: Data validation
        print(f"\n🔍 Running Data Quality Checks...")
        checks = validator.validate_order_book(df)
        
        print(f"\nValidation Results:")
        for check, result in checks.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {check}: {status}")
        
        # Test 3: Statistics
        print(f"\n📈 Order Book Statistics:")
        print(f"  Total entries: {len(df)}")
        
        if 'side' in df.columns:
            bids_count = (df['side'] == 'bid').sum()
            asks_count = (df['side'] == 'ask').sum()
            print(f"  Bids: {bids_count}")
            print(f"  Asks: {asks_count}")
        
        if 'price' in df.columns:
            print(f"  Price range: ${df['price'].min():.2f} - ${df['price'].max():.2f}")
            
            # Best bid and ask
            bids = df[df['side'] == 'bid']
            asks = df[df['side'] == 'ask']
            
            if not bids.empty and not asks.empty:
                best_bid = bids['price'].max()
                best_ask = asks['price'].min()
                spread = best_ask - best_bid
                spread_pct = (spread / best_bid) * 100
                
                print(f"  Best Bid: ${best_bid:.2f}")
                print(f"  Best Ask: ${best_ask:.2f}")
                print(f"  Spread: ${spread:.2f} ({spread_pct:.3f}%)")
        
        if 'quantity' in df.columns:
            print(f"  Total volume on bids: {bids['quantity'].sum():.2f}" if not bids.empty else "")
            print(f"  Total volume on asks: {asks['quantity'].sum():.2f}" if not asks.empty else "")
        
        print("\n" + "=" * 60)
        print("✅ ORDER BOOK TEST COMPLETED SUCCESSFULLY")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 60)
        print("❌ ORDER BOOK TEST FAILED")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_order_book())
