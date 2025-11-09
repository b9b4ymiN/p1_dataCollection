"""
Phase 1 → Phase 2 Integration Demo
===================================

Demonstrates complete workflow:
1. Load data from Phase 1 Docker TimescaleDB
2. Prepare DataFrames for Phase 2 FeatureEngineer
3. Engineer 100+ features using p2_mlFeature code
4. Create targets, select features, analyze importance
5. Save results for model training

Prerequisites:
- Phase 1 Docker containers running
- p2_mlFeature repo cloned
- Update P2_REPO_PATH below
"""

import sys
import os
from pathlib import Path
import pandas as pd
import yaml
from datetime import datetime, timedelta

# ============================================================
# CONFIGURATION - UPDATE THIS PATH
# ============================================================
P2_REPO_PATH = r"C:\Programing\ByAI\claude-code\p2_mlFeature"
# Recommended Phase 1 DB name (matches container config)
P1_DB_NAME = "futures_db"


# Add p2_mlFeature to Python path FIRST
if os.path.exists(P2_REPO_PATH):
    sys.path.insert(0, P2_REPO_PATH)
    print(f"✓ Added p2_mlFeature to path: {P2_REPO_PATH}")
else:
    print(f"❌ ERROR: p2_mlFeature repo not found at: {P2_REPO_PATH}")
    print("Please clone the repo and update P2_REPO_PATH in this script.")
    sys.exit(1)

# Fix typing imports for Phase 2 (Python 3.12 compatibility)
import typing
if not hasattr(typing, 'Dict'):
    typing.Dict = dict
if not hasattr(typing, 'Tuple'):
    typing.Tuple = tuple
if not hasattr(typing, 'List'):
    typing.List = list

# Phase 2 imports (from p2_mlFeature repo) - import and save before adding Phase 1 path
try:
    import features as p2_features
    import utils as p2_utils
    FeatureEngineer = p2_features.feature_engineer.FeatureEngineer
    TargetEngineer = p2_features.target_engineer.TargetEngineer
    select_features_combined = p2_utils.feature_selection.select_features_combined
    # analyze_feature_importance might not exist in Phase 2, we'll create a simple version
    try:
        analyze_feature_importance = p2_utils.feature_analysis.analyze_feature_importance
    except AttributeError:
        # Create a simple fallback
        def analyze_feature_importance(X, y, task_type='classification', top_n=10):
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
            model.fit(X, y)
            importance_df = pd.DataFrame({
                'feature': X.columns,
                'importance': model.feature_importances_
            }).sort_values('importance', ascending=False).reset_index(drop=True)
            print("\nFEATURE IMPORTANCE ANALYSIS")
            print(f"Top {top_n} Most Important Features:")
            for idx, row in importance_df.head(top_n).iterrows():
                print(f"  {idx+1}. {row['feature']:40s} {row['importance']:.4f}")
            return importance_df
        analyze_feature_importance = analyze_feature_importance
    print("✓ Phase 2 modules imported successfully")
except Exception as e:
    print(f"❌ ERROR importing Phase 2 modules: {e}")
    print("Make sure p2_mlFeature repo is properly set up with dependencies installed.")
    print("Run: pip install pandas-ta scikit-learn scipy")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Now import Phase 1's MarketDataLoader using absolute path
p1_repo_path = str(Path(__file__).parent.parent)
sys.path.append(p1_repo_path)  # Add to end, not beginning
# Import MarketDataLoader from absolute file path
import importlib.util
spec = importlib.util.spec_from_file_location("p1_features.data_loader", 
                                                os.path.join(p1_repo_path, "features", "data_loader.py"))
p1_data_loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p1_data_loader)
MarketDataLoader = p1_data_loader.MarketDataLoader
print("✓ Phase 1 MarketDataLoader imported successfully")


def main():
    """
    Main integration pipeline
    """
    print("\n" + "=" * 80)
    print("PHASE 1 (Docker) → PHASE 2 (ML Features) INTEGRATION DEMO")
    print("=" * 80)
    
    # ========== STEP 1: LOAD DATA FROM PHASE 1 DATABASE ==========
    print("\n[STEP 1] Loading data from Phase 1 TimescaleDB (Docker)...")
    
    # Load config
    config_path = Path(__file__).parent.parent / 'config.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Override database host for host machine access (Docker exposes on localhost:5432)
    db_config = config['database'].copy()
    if db_config.get('host') == 'postgres':
        db_config['host'] = 'localhost'
        print("  (Using localhost to connect to Docker DB from host machine)")
    
    # Initialize data loader
    loader = MarketDataLoader(db_config)
    
    # Define date range (last 30 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    symbol = 'SOL/USDT'
    timeframe = '5m'
    
    print(f"  Symbol: {symbol}")
    print(f"  Timeframe: {timeframe}")
    print(f"  Date range: {start_date.date()} to {end_date.date()}")
    print(f"  Database: {P1_DB_NAME}")
    
    try:
        # Load merged data from all Phase 1 tables
        merged_df = loader.load_all_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
        
        if merged_df.empty:
            print("\n❌ WARNING: No data returned from database!")
            print("   Possible reasons:")
            print("   1. Phase 1 collectors haven't populated data yet")
            print("   2. Date range doesn't match collected data")
            print("   3. Symbol format mismatch")
            print("\n   Please run Phase 1 collectors first to populate the database.")
            return
        
        print(f"\n✓ Loaded {len(merged_df):,} rows from database")
        print(f"  Columns: {list(merged_df.columns)}")
        print(f"  Actual date range: {merged_df['timestamp'].min()} to {merged_df['timestamp'].max()}")
        
    except Exception as e:
        print(f"\n❌ ERROR loading data from database: {e}")
        print("   Make sure Phase 1 Docker containers are running:")
        print("   docker ps | grep futures_db")
        return
    
    # ========== STEP 2: PREPARE DATAFRAMES FOR PHASE 2 ==========
    print("\n[STEP 2] Preparing DataFrames for Phase 2 FeatureEngineer...")
    
    # Required: OHLCV DataFrame
    ohlcv_df = merged_df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
    print(f"  ✓ OHLCV: {len(ohlcv_df):,} rows")
    
    # Optional: Open Interest
    oi_df = None
    if 'open_interest' in merged_df.columns:
        oi_df = merged_df[['timestamp', 'open_interest']].dropna().copy()
        if not oi_df.empty:
            print(f"  ✓ Open Interest: {len(oi_df):,} rows")
        else:
            oi_df = None
            print(f"  ⊘ Open Interest: No data")
    else:
        print(f"  ⊘ Open Interest: Column not found")
    
    # Optional: Funding Rate
    funding_df = None
    if 'funding_rate' in merged_df.columns:
        funding_df = merged_df[['timestamp', 'funding_rate']].dropna().copy()
        if not funding_df.empty:
            print(f"  ✓ Funding Rate: {len(funding_df):,} rows")
        else:
            funding_df = None
            print(f"  ⊘ Funding Rate: No data")
    else:
        print(f"  ⊘ Funding Rate: Column not found")
    
    # Optional: Liquidations
    liq_df = None
    if 'liq_volume' in merged_df.columns and 'liq_count' in merged_df.columns:
        liq_df = merged_df[['timestamp', 'liq_volume', 'liq_count']].dropna().copy()
        if not liq_df.empty:
            # Rename to match Phase 2 expectations
            liq_df = liq_df.rename(columns={'liq_volume': 'quantity'})
            print(f"  ✓ Liquidations: {len(liq_df):,} rows")
        else:
            liq_df = None
            print(f"  ⊘ Liquidations: No data")
    else:
        print(f"  ⊘ Liquidations: Columns not found")
    
    # Optional: Long/Short Ratio
    ls_df = None
    if 'longShortRatio' in merged_df.columns:
        ls_df = merged_df[['timestamp', 'longShortRatio']].dropna().copy()
        if not ls_df.empty:
            print(f"  ✓ Long/Short Ratio: {len(ls_df):,} rows")
        else:
            ls_df = None
            print(f"  ⊘ Long/Short Ratio: No data")
    else:
        print(f"  ⊘ Long/Short Ratio: Column not found")
    
    # ========== STEP 3: ENGINEER FEATURES (PHASE 2) ==========
    print("\n[STEP 3] Engineering features with Phase 2 FeatureEngineer...")
    print("  (This may take 30-60 seconds...)")
    
    try:
        engineer = FeatureEngineer()
        
        features_df = engineer.engineer_all_features(
            ohlcv=ohlcv_df,
            oi=oi_df,
            funding=funding_df,
            liquidations=liq_df,
            ls_ratio=ls_df
        )
        
        print(f"\n✓ Feature engineering complete!")
        print(f"  Total columns: {len(features_df.columns)}")
        print(f"  Shape: {features_df.shape}")
        
        # Show sample of engineered features
        feature_cols = engineer.get_feature_names(features_df)
        print(f"  Engineered features: {len(feature_cols)}")
        print(f"  Sample features: {feature_cols[:10]}")
        
    except Exception as e:
        print(f"\n❌ ERROR during feature engineering: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ========== STEP 4: CREATE TARGET VARIABLES ==========
    print("\n[STEP 4] Creating target variables...")
    
    try:
        target_engineer = TargetEngineer()
        
        # Create classification target (predict 4-hour ahead price moves)
        features_with_target = target_engineer.create_classification_target(
            features_df.reset_index(),
            horizon=48,      # 4 hours = 48 5-min bars
            threshold=0.01,  # 1% price move threshold
            n_classes=3      # LONG (2), NEUTRAL (1), SHORT (0)
        )
        
        print(f"✓ Target variable created")
        
        # Show target distribution
        dist = target_engineer.get_target_distribution(features_with_target)
        print(f"  Target distribution:")
        class_names = {0: 'SHORT', 1: 'NEUTRAL', 2: 'LONG'}
        for idx, row in dist.iterrows():
            class_name = class_names.get(idx, str(idx))
            print(f"    {class_name:10s}: {int(row['count']):6,} samples ({row['percentage']:5.1f}%)")
        
    except Exception as e:
        print(f"\n❌ ERROR creating targets: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ========== STEP 5: FEATURE SELECTION ==========
    print("\n[STEP 5] Selecting best features...")
    
    try:
        # Prepare feature matrix and target
        X = features_with_target[feature_cols]
        y = features_with_target['target']
        
        # Remove rows with NaN target (from horizon lookback)
        valid_mask = ~y.isna()
        X = X[valid_mask]
        y = y[valid_mask]
        
        print(f"  Valid samples: {len(X):,}")
        
        # Clean data: replace inf/-inf with NaN, then forward-fill and fill remaining with 0
        print("  Cleaning infinity and NaN values...")
        X = X.replace([float('inf'), float('-inf')], pd.NA)
        X = X.ffill().fillna(0)
        
        print(f"  After cleaning: {len(X):,} samples, {len(X.columns)} features")
        
        # Time-series split (first 60% for training)
        train_idx = int(len(X) * 0.6)
        
        X_train = X.iloc[:train_idx]
        y_train = y.iloc[:train_idx]
        
        print(f"  Training samples: {len(X_train):,}")
        
        # Select top 50 features using combined pipeline
        X_selected, selection_report = select_features_combined(
            X_train, y_train,
            n_features=50,
            task_type='classification',
            correlation_threshold=0.9,
            variance_threshold=0.001
        )
        
        selected_features = X_selected.columns.tolist()
        
        print(f"\n✓ Feature selection complete")
        print(f"  Selected {len(selected_features)} features from {len(feature_cols)}")
        
    except Exception as e:
        print(f"\n❌ ERROR during feature selection: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ========== STEP 6: FEATURE IMPORTANCE ANALYSIS ==========
    print("\n[STEP 6] Analyzing feature importance...")
    
    try:
        importance_df = analyze_feature_importance(
            X_selected, y_train,
            task_type='classification',
            top_n=10
        )
        
    except Exception as e:
        print(f"\n❌ ERROR analyzing feature importance: {e}")
        importance_df = None
    
    # ========== STEP 7: SAVE RESULTS ==========
    print("\n[STEP 7] Saving results...")
    
    output_dir = Path(__file__).parent.parent / 'data'
    output_dir.mkdir(exist_ok=True)
    
    try:
        # Save complete features with target
        output_file = output_dir / 'phase2_features_complete.parquet'
        features_with_target.to_parquet(output_file, index=False)
        print(f"✓ Saved complete features: {output_file}")
        
        # Save selected features only
        selected_output = output_dir / 'phase2_features_selected.parquet'
        selected_df = features_with_target[['timestamp'] + selected_features + ['target']]
        selected_df.to_parquet(selected_output, index=False)
        print(f"✓ Saved selected features: {selected_output}")
        
        # Save feature importance
        if importance_df is not None:
            importance_file = output_dir / 'feature_importance.csv'
            importance_df.to_csv(importance_file, index=False)
            print(f"✓ Saved feature importance: {importance_file}")
        
    except Exception as e:
        print(f"\n❌ ERROR saving results: {e}")
    
    # ========== SUMMARY ==========
    print("\n" + "=" * 80)
    print("INTEGRATION SUMMARY")
    print("=" * 80)
    print(f"Data Source:                Phase 1 Docker TimescaleDB")
    print(f"Symbol:                     {symbol}")
    print(f"Timeframe:                  {timeframe}")
    print(f"Total samples:              {len(features_with_target):,}")
    print(f"Features engineered:        {len(feature_cols)}")
    print(f"Features selected:          {len(selected_features)}")
    print(f"Training samples:           {len(X_train):,}")
    
    if importance_df is not None:
        print(f"\nTop 5 Most Important Features:")
        for idx, row in importance_df.head(5).iterrows():
            print(f"  {idx+1}. {row['feature']:40s} {row['importance']:.4f}")
    
    print("\n" + "=" * 80)
    print("✅ Integration completed successfully!")
    print("\nNext Steps:")
    print("  1. Train ML models using selected features in data/phase2_features_selected.parquet")
    print("  2. Evaluate model performance on validation/test sets")
    print("  3. Implement live trading with Phase 1 data stream + Phase 2 features")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    main()
