# Phase 1 → Phase 2 Integration Guide
## Connecting Docker-based Data Collection with ML Feature Engineering

## 🎯 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PHASE 1 (Docker)                             │
│  ┌─────────────────┐    ┌──────────────────┐   ┌────────────────┐  │
│  │  Binance API    │───>│ Data Collectors  │──>│  TimescaleDB   │  │
│  │  (REST/WebSocket)│    │  (async Python)  │   │  (PostgreSQL)  │  │
│  └─────────────────┘    └──────────────────┘   │  Port: 5432    │  │
│                                                 └────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ SQL Queries
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  BRIDGE LAYER (Python)                               │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  features/data_loader.py (from p1_dataCollection)              │ │
│  │  - MarketDataLoader.load_all_data()                            │ │
│  │  - Returns: pd.DataFrame with merged data                      │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ DataFrames
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  PHASE 2 (p2_mlFeature repo)                         │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  FeatureEngineer.engineer_all_features()                       │ │
│  │  Input:  ohlcv, oi, funding, liquidations, ls_ratio DFs       │ │
│  │  Output: 100+ engineered features                              │ │
│  └────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Feature Selection, Target Engineering, Feature Store          │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Prerequisites

### Phase 1 (Already Set Up)
- ✅ Docker Compose stack running (`docker compose up -d`)
- ✅ TimescaleDB container on port 5432
- ✅ Data collectors populating tables: `ohlcv`, `open_interest`, `funding_rate`, `liquidations`, `long_short_ratio`

### Phase 2 (New Setup)
- Clone your p2_mlFeature repository
- Install dependencies: `pip install -r requirements.txt` (pandas, numpy, pandas_ta, scipy, sklearn, etc.)

---

## 🔌 Connection Setup

### Option 1: Connect from Host Machine (Recommended for Development)

Your Phase 1 PostgreSQL container exposes port 5432 to the host. Phase 2 Python code running on the host can connect directly:

```python
# Connection string from host machine
DATABASE_URL = "postgresql://futures_user:futures_pass@localhost:5432/futures_data"
```

### Option 2: Docker Network (If Running Phase 2 in Docker)

If you containerize Phase 2, use Docker network:

```python
# Connection string from within Docker network
DATABASE_URL = "postgresql://futures_user:futures_pass@futures_db:5432/futures_data"
```

---

## 🛠️ Implementation Steps

### Step 1: Use Existing `data_loader.py` from Phase 1

Your Phase 1 repo already has `features/data_loader.py` with `MarketDataLoader` class:

```python
# File: features/data_loader.py (already exists in p1_dataCollection)
from features.data_loader import MarketDataLoader
import yaml

# Load config
with open('config.yaml') as f:
    config = yaml.safe_load(f)

# Initialize loader
loader = MarketDataLoader(config['database'])

# Load data for Phase 2 processing
df = loader.load_all_data(
    symbol='SOL/USDT',
    timeframe='5m',
    start_date='2024-01-01',
    end_date='2024-12-01'
)

# df now contains merged columns:
# - timestamp, open, high, low, close, volume (from ohlcv)
# - open_interest (from open_interest table)
# - funding_rate (from funding_rate table)
# - liq_volume, liq_count (from liquidations table)
# - longShortRatio (from long_short_ratio table)
```

### Step 2: Prepare DataFrames for Phase 2 FeatureEngineer

The `FeatureEngineer` from p2_mlFeature expects separate DataFrames:

```python
# File: phase2_integration.py (new script in p1_dataCollection repo)

import sys
sys.path.insert(0, r'C:\path\to\p2_mlFeature')  # Adjust path

from features import FeatureEngineer, TargetEngineer
from utils import select_features_combined, time_series_split
import pandas as pd
import yaml
from features.data_loader import MarketDataLoader  # From Phase 1

# 1. LOAD DATA FROM PHASE 1 DATABASE
with open('config.yaml') as f:
    config = yaml.safe_load(f)

loader = MarketDataLoader(config['database'])
merged_df = loader.load_all_data('SOL/USDT', '5m', '2024-10-01', '2024-11-09')

# 2. PREPARE DATAFRAMES FOR PHASE 2
# Phase 2 FeatureEngineer expects specific DataFrame formats

# OHLCV DataFrame (required)
ohlcv_df = merged_df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()

# Open Interest DataFrame (optional)
oi_df = None
if 'open_interest' in merged_df.columns:
    oi_df = merged_df[['timestamp', 'open_interest']].copy()
    oi_df = oi_df.dropna()

# Funding Rate DataFrame (optional)
funding_df = None
if 'funding_rate' in merged_df.columns:
    funding_df = merged_df[['timestamp', 'funding_rate']].copy()
    funding_df = funding_df.dropna()

# Liquidations DataFrame (optional)
liq_df = None
if 'liq_volume' in merged_df.columns:
    liq_df = merged_df[['timestamp', 'liq_volume', 'liq_count']].copy()
    liq_df = liq_df.rename(columns={'liq_volume': 'quantity'})
    liq_df = liq_df.dropna()

# Long/Short Ratio DataFrame (optional)
ls_df = None
if 'longShortRatio' in merged_df.columns:
    ls_df = merged_df[['timestamp', 'longShortRatio']].copy()
    ls_df = ls_df.dropna()

# 3. ENGINEER FEATURES USING PHASE 2 CODE
engineer = FeatureEngineer()

features_df = engineer.engineer_all_features(
    ohlcv=ohlcv_df,
    oi=oi_df,
    funding=funding_df,
    liquidations=liq_df,
    ls_ratio=ls_df
)

print(f"✅ Engineered {len(features_df.columns)} features")
print(f"   Shape: {features_df.shape}")

# 4. CREATE TARGET VARIABLES
target_engineer = TargetEngineer()
features_with_target = target_engineer.create_classification_target(
    features_df.reset_index(),
    horizon=48,      # 4 hours ahead
    threshold=0.01,  # 1% price move
    n_classes=3      # LONG, NEUTRAL, SHORT
)

print(f"✅ Created targets. Distribution:")
print(target_engineer.get_target_distribution(features_with_target))

# 5. FEATURE SELECTION
feature_cols = engineer.get_feature_names(features_df)
X = features_with_target[feature_cols]
y = features_with_target['target']

# Remove rows with NaN target
valid_mask = ~y.isna()
X = X[valid_mask]
y = y[valid_mask]

# Time-series split
train_idx = int(len(X) * 0.6)
val_idx = int(len(X) * 0.8)

X_train = X.iloc[:train_idx]
y_train = y.iloc[:train_idx]

# Select best features
X_selected, report = select_features_combined(
    X_train, y_train,
    n_features=50,
    task_type='classification'
)

print(f"\n✅ Selected {len(X_selected.columns)} features")
print(f"\n📊 Top 10 features:")
for idx, row in report['importance_scores'].head(10).iterrows():
    print(f"   {idx+1}. {row['feature']:40s} {row['importance']:.4f}")

# 6. SAVE RESULTS
output_path = 'phase2_features_output.parquet'
features_with_target.to_parquet(output_path, index=False)
print(f"\n✅ Saved features to {output_path}")
```

---

## 📝 Complete Example Script

**File: `examples/phase1_to_phase2_full_pipeline.py`**

```python
"""
Complete Phase 1 → Phase 2 Integration Example
Demonstrates end-to-end workflow from Docker database to ML features
"""

import sys
import os
sys.path.insert(0, r'C:\path\to\p2_mlFeature')  # ADJUST THIS PATH

import pandas as pd
import yaml
from datetime import datetime, timedelta

# Phase 1 imports (from this repo)
from features.data_loader import MarketDataLoader

# Phase 2 imports (from p2_mlFeature repo)
from features import FeatureEngineer, TargetEngineer, FeatureStore
from utils import (
    time_series_split,
    select_features_combined,
    analyze_feature_importance
)


def main():
    print("=" * 80)
    print("PHASE 1 → PHASE 2 INTEGRATION PIPELINE")
    print("=" * 80)
    
    # ========== STEP 1: LOAD DATA FROM PHASE 1 (Docker TimescaleDB) ==========
    print("\n[STEP 1] Loading data from Phase 1 database...")
    
    with open('config.yaml') as f:
        config = yaml.safe_load(f)
    
    loader = MarketDataLoader(config['database'])
    
    # Define date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # Last 30 days
    
    # Load merged data
    merged_df = loader.load_all_data(
        symbol='SOL/USDT',
        timeframe='5m',
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )
    
    print(f"✓ Loaded {len(merged_df)} rows from database")
    print(f"  Columns: {list(merged_df.columns)}")
    print(f"  Date range: {merged_df['timestamp'].min()} to {merged_df['timestamp'].max()}")
    
    # ========== STEP 2: PREPARE DATAFRAMES FOR PHASE 2 ==========
    print("\n[STEP 2] Preparing DataFrames for Phase 2 FeatureEngineer...")
    
    # Required: OHLCV
    ohlcv_df = merged_df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
    
    # Optional data sources
    oi_df = merged_df[['timestamp', 'open_interest']].dropna() if 'open_interest' in merged_df.columns else None
    funding_df = merged_df[['timestamp', 'funding_rate']].dropna() if 'funding_rate' in merged_df.columns else None
    ls_df = merged_df[['timestamp', 'longShortRatio']].dropna() if 'longShortRatio' in merged_df.columns else None
    
    # Liquidations (aggregate from your schema if available)
    liq_df = None
    if 'liq_volume' in merged_df.columns and 'liq_count' in merged_df.columns:
        liq_df = merged_df[['timestamp', 'liq_volume', 'liq_count']].dropna()
        liq_df = liq_df.rename(columns={'liq_volume': 'quantity'})
    
    print(f"✓ Prepared DataFrames:")
    print(f"  - OHLCV: {len(ohlcv_df)} rows")
    print(f"  - Open Interest: {len(oi_df) if oi_df is not None else 'N/A'}")
    print(f"  - Funding Rate: {len(funding_df) if funding_df is not None else 'N/A'}")
    print(f"  - Liquidations: {len(liq_df) if liq_df is not None else 'N/A'}")
    print(f"  - L/S Ratio: {len(ls_df) if ls_df is not None else 'N/A'}")
    
    # ========== STEP 3: ENGINEER 100+ FEATURES (PHASE 2) ==========
    print("\n[STEP 3] Engineering features with Phase 2 FeatureEngineer...")
    
    engineer = FeatureEngineer()
    
    features_df = engineer.engineer_all_features(
        ohlcv=ohlcv_df,
        oi=oi_df,
        funding=funding_df,
        liquidations=liq_df,
        ls_ratio=ls_df
    )
    
    print(f"\n✓ Engineered {len(features_df.columns)} total columns")
    print(f"  Shape: {features_df.shape}")
    
    # ========== STEP 4: CREATE TARGET VARIABLES ==========
    print("\n[STEP 4] Creating target variables...")
    
    target_engineer = TargetEngineer()
    
    features_with_target = target_engineer.create_classification_target(
        features_df.reset_index(),
        horizon=48,      # 4 hours = 48 5-min bars
        threshold=0.01,  # 1% price move
        n_classes=3      # LONG, NEUTRAL, SHORT
    )
    
    print(f"✓ Created classification target")
    print(f"  Target distribution:")
    dist = target_engineer.get_target_distribution(features_with_target)
    for idx, row in dist.iterrows():
        class_name = {0: 'SHORT', 1: 'NEUTRAL', 2: 'LONG'}.get(idx, str(idx))
        print(f"    {class_name:10s}: {row['count']:5.0f} ({row['percentage']:5.1f}%)")
    
    # ========== STEP 5: FEATURE SELECTION ==========
    print("\n[STEP 5] Selecting best features...")
    
    feature_cols = engineer.get_feature_names(features_df)
    X = features_with_target[feature_cols]
    y = features_with_target['target']
    
    # Remove NaN targets
    valid_mask = ~y.isna()
    X = X[valid_mask]
    y = y[valid_mask]
    
    # Time-series split (no shuffling!)
    train_idx = int(len(X) * 0.6)
    
    X_train = X.iloc[:train_idx]
    y_train = y.iloc[:train_idx]
    
    # Select top 50 features
    X_selected, selection_report = select_features_combined(
        X_train, y_train,
        n_features=50,
        task_type='classification',
        correlation_threshold=0.9,
        variance_threshold=0.001
    )
    
    selected_features = X_selected.columns.tolist()
    
    print(f"\n✓ Selected {len(selected_features)} features")
    
    # ========== STEP 6: FEATURE IMPORTANCE ANALYSIS ==========
    print("\n[STEP 6] Analyzing feature importance...")
    
    importance_df = analyze_feature_importance(
        X_selected, y_train,
        task_type='classification',
        top_n=10
    )
    
    # ========== STEP 7: SAVE RESULTS ==========
    print("\n[STEP 7] Saving results...")
    
    # Save all features with target
    output_file = 'data/phase2_features_complete.parquet'
    os.makedirs('data', exist_ok=True)
    features_with_target.to_parquet(output_file, index=False)
    print(f"✓ Saved complete features to: {output_file}")
    
    # Save selected features only
    selected_output = 'data/phase2_features_selected.parquet'
    selected_df = features_with_target[['timestamp'] + selected_features + ['target']]
    selected_df.to_parquet(selected_output, index=False)
    print(f"✓ Saved selected features to: {selected_output}")
    
    # Save feature importance
    importance_file = 'data/feature_importance.csv'
    importance_df.to_csv(importance_file, index=False)
    print(f"✓ Saved feature importance to: {importance_file}")
    
    # ========== SUMMARY ==========
    print("\n" + "=" * 80)
    print("PIPELINE SUMMARY")
    print("=" * 80)
    print(f"Total samples:              {len(features_with_target)}")
    print(f"Features engineered:        {len(feature_cols)}")
    print(f"Features selected:          {len(selected_features)}")
    print(f"Training samples:           {len(X_train)}")
    print(f"\nTop 5 Most Important Features:")
    for idx, row in importance_df.head(5).iterrows():
        print(f"  {idx+1}. {row['feature']:40s} {row['importance']:.4f}")
    print("=" * 80)
    print("\n✅ Phase 1 → Phase 2 integration completed successfully!")
    print("\nNext steps:")
    print("  1. Train ML models using selected features")
    print("  2. Evaluate on validation/test sets")
    print("  3. Deploy for live trading")
    print("=" * 80)


if __name__ == '__main__':
    main()
```

---

## 🔑 Key Configuration Updates

### Update `config.yaml` to support both Phase 1 and Phase 2:

```yaml
# Database config (Phase 1 - Docker)
database:
  host: localhost        # From host machine
  port: 5432
  dbname: futures_data
  user: futures_user
  password: futures_pass

# Phase 2 settings (optional)
phase2:
  p2_repo_path: "C:/path/to/p2_mlFeature"  # Path to your p2_mlFeature repo
  feature_selection:
    n_features: 50
    correlation_threshold: 0.9
    variance_threshold: 0.001
  target_engineering:
    horizon: 48          # 4 hours for 5-min bars
    threshold: 0.01      # 1% price move
    n_classes: 3         # LONG, NEUTRAL, SHORT
```

---

## 🐳 Docker Network Access (Optional)

If you want to run Phase 2 code inside a Docker container that connects to Phase 1 database:

### Add to `docker-compose.yml`:

```yaml
services:
  # ... existing services (futures_db, collector, streamer, redis)
  
  ml_feature_engineer:
    build:
      context: .
      dockerfile: Dockerfile.phase2
    container_name: ml_feature_engineer
    networks:
      - futures-network
    environment:
      - DATABASE_URL=postgresql://futures_user:futures_pass@futures_db:5432/futures_data
      - PYTHONPATH=/app/p2_mlFeature:/app/p1_dataCollection
    volumes:
      - ./:/app/p1_dataCollection
      - /path/to/p2_mlFeature:/app/p2_mlFeature:ro
    depends_on:
      - futures_db
    command: python /app/p1_dataCollection/examples/phase1_to_phase2_full_pipeline.py
```

### Create `Dockerfile.phase2`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies for both Phase 1 and Phase 2
COPY requirements.txt /app/p1_requirements.txt
RUN pip install --no-cache-dir -r /app/p1_requirements.txt

# Install Phase 2 dependencies
RUN pip install --no-cache-dir \
    pandas-ta \
    scikit-learn \
    shap \
    lightgbm \
    xgboost

CMD ["bash"]
```

---

## 📊 Data Flow Summary

1. **Phase 1 Collectors** → TimescaleDB (Running in Docker)
2. **MarketDataLoader** → Queries TimescaleDB → Returns merged DataFrame
3. **Data Preparation** → Split merged DF into separate DataFrames (ohlcv, oi, funding, etc.)
4. **Phase 2 FeatureEngineer** → 100+ features
5. **Phase 2 TargetEngineer** → Create prediction targets
6. **Phase 2 Feature Selection** → Top 50 features
7. **Ready for ML Model Training**

---

## ✅ Validation Checklist

- [ ] Phase 1 Docker containers running (`docker ps`)
- [ ] TimescaleDB accessible from host (`psql -h localhost -U futures_user -d futures_data`)
- [ ] Data exists in tables (`SELECT COUNT(*) FROM ohlcv;`)
- [ ] `features/data_loader.py` tested and returns data
- [ ] p2_mlFeature repo cloned and dependencies installed
- [ ] Example script runs without errors
- [ ] Output files created (`phase2_features_complete.parquet`)
- [ ] Feature importance report generated

---

## 🚨 Troubleshooting

### Issue: "Connection refused to database"
**Solution:** 
- Check Docker container: `docker ps | grep futures_db`
- Verify port mapping: `docker port futures_db`
- Test connection: `psql -h localhost -U futures_user -d futures_data`

### Issue: "ModuleNotFoundError: No module named 'features'"
**Solution:**
- Add p2_mlFeature to Python path: `sys.path.insert(0, '/path/to/p2_mlFeature')`
- Or install as package: `cd p2_mlFeature && pip install -e .`

### Issue: "Empty DataFrame returned from loader"
**Solution:**
- Check date range (data may not exist for requested dates)
- Verify symbol format ('SOL/USDT' vs 'SOLUSDT')
- Check Phase 1 collectors are running and populating DB

### Issue: "NaN values in features"
**Solution:**
- Normal for rolling calculations at start of window
- Use `features_df.fillna(method='ffill')` or filter first N rows
- FeatureEngineer already handles this internally

---

## 📖 Related Documentation

- Phase 1 Architecture: `DATABASE_SWITCHING.md`
- Phase 1→2 Data Mapping: `PHASE1_TO_PHASE2_INTEGRATION.md`
- Phase 2 Feature List: `p2_mlFeature/README.md`
- Docker Setup: `docker-compose.yml`

---

**Ready to start ML model training! 🚀**

With Phase 1 data collection automated in Docker and Phase 2 feature engineering integrated, you now have a complete pipeline from live market data to ML-ready features.
