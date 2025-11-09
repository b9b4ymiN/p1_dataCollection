"""
Example: Phase 1 → Phase 2 Integration
Shows how to use collected data for feature engineering

This demonstrates the complete pipeline:
1. Load data from Phase 1 database
2. Engineer features using Phase 2 methods
3. Prepare for ML model training
"""

import yaml
from datetime import datetime, timedelta
import pandas as pd

from features.data_loader import MarketDataLoader
# Note: feature_engineer.py will be created next

def main():
    """
    Example workflow: From raw data to ML-ready features
    """
    
    # Load configuration
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    print("=" * 70)
    print("PHASE 1 → PHASE 2 INTEGRATION EXAMPLE")
    print("=" * 70)
    
    # Step 1: Initialize Data Loader (connects to Phase 1 database)
    print("\n📊 Step 1: Loading data from Phase 1 database...")
    loader = MarketDataLoader(config['database'])
    
    # Step 2: Load historical data for a symbol
    symbol = 'SOL/USDT'
    timeframe = '5m'
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)  # Last 30 days
    
    print(f"\n🔄 Step 2: Fetching {symbol} data ({timeframe})...")
    print(f"   Date range: {start_date.date()} to {end_date.date()}")
    
    # This merges all Phase 1 tables into one DataFrame
    df = loader.load_all_data(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date
    )
    
    print(f"\n✅ Data loaded successfully!")
    print(f"   Total rows: {len(df):,}")
    print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"\n📋 Available columns from Phase 1:")
    for col in df.columns:
        print(f"   • {col}")
    
    # Step 3: Basic data quality check
    print(f"\n🔍 Step 3: Data quality check...")
    print(f"   Missing values:")
    missing = df.isnull().sum()
    for col in missing[missing > 0].index:
        print(f"      {col}: {missing[col]} ({missing[col]/len(df)*100:.2f}%)")
    
    if missing.sum() == 0:
        print(f"   ✅ No missing values!")
    
    # Step 4: Quick statistics
    print(f"\n📈 Step 4: Quick statistics...")
    print(f"\n   Price Stats:")
    print(f"      Close: ${df['close'].iloc[-1]:.2f}")
    print(f"      Range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    print(f"      Change: {(df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100:+.2f}%")
    
    print(f"\n   Open Interest Stats:")
    print(f"      Current: {df['open_interest'].iloc[-1]:,.0f}")
    print(f"      Range: {df['open_interest'].min():,.0f} - {df['open_interest'].max():,.0f}")
    print(f"      Change: {(df['open_interest'].iloc[-1] - df['open_interest'].iloc[0]) / df['open_interest'].iloc[0] * 100:+.2f}%")
    
    print(f"\n   Funding Rate Stats:")
    print(f"      Current: {df['funding_rate'].iloc[-1]:.6f}")
    print(f"      Mean: {df['funding_rate'].mean():.6f}")
    print(f"      Extremes: {df['funding_rate'].min():.6f} to {df['funding_rate'].max():.6f}")
    
    # Step 5: Preview data structure
    print(f"\n📊 Step 5: Data preview (last 5 rows)...")
    print(df[['timestamp', 'close', 'volume', 'open_interest', 'funding_rate']].tail())
    
    # Step 6: Ready for Phase 2!
    print(f"\n" + "=" * 70)
    print("✅ DATA READY FOR PHASE 2 FEATURE ENGINEERING!")
    print("=" * 70)
    print(f"\nNext steps:")
    print(f"  1. Create FeatureEngineer class (see phase2_example_full.py)")
    print(f"  2. Engineer 100+ features from this data")
    print(f"  3. Create target variables")
    print(f"  4. Perform feature selection")
    print(f"  5. Train ML models!")
    print(f"\n" + "=" * 70)
    
    return df


if __name__ == '__main__':
    # Run the example
    df = main()
    
    # Save to CSV for inspection
    output_file = 'data/merged_market_data_example.csv'
    df.to_csv(output_file, index=False)
    print(f"\n💾 Data saved to: {output_file}")
