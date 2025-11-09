# Phase 1 + Phase 2 Integration - Quick Start Guide

## 🎯 Overview

Your Phase 1 system collects data in Docker → TimescaleDB.  
Your Phase 2 system (p2_mlFeature repo) generates ML features.  
**This guide connects them together.**

---

## ✅ Prerequisites

### Phase 1 (Already Running)
- Docker containers running:
  ```powershell
  docker ps
  # Should show: futures_db, futures_collector, futures_streamer, redis
  ```
-- Database has data:
  ```powershell
  docker exec -it futures_db psql -U futures_user -d futures_db -c "SELECT COUNT(*) FROM ohlcv;"
  ```

### Phase 2 (Need to Set Up)
1. Clone your p2_mlFeature repo:
   ```powershell
   cd C:\Programing\ByAI\claude-code
   git clone https://github.com/b9b4ymiN/p2_mlFeature.git
   ```

2. Install Phase 2 dependencies:
   ```powershell
   cd p2_mlFeature
   pip install -r requirements.txt
   ```

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Update Config

Edit `p1_dataCollection/config.yaml`:

```yaml
phase2:
  repo_path: "C:/Programing/ByAI/claude-code/p2_mlFeature"  # <-- UPDATE THIS!
```

### Step 2: Update Demo Script

Edit `p1_dataCollection/examples/phase1_to_phase2_integration_demo.py`:

```python
# Line ~25
P2_REPO_PATH = r"C:\Programing\ByAI\claude-code\p2_mlFeature"  # <-- UPDATE THIS!
```

### Step 3: Run Integration Demo

```powershell
cd p1_dataCollection
python examples\phase1_to_phase2_integration_demo.py
```

**Expected Output:**
```
================================================================================
PHASE 1 (Docker) → PHASE 2 (ML Features) INTEGRATION DEMO
================================================================================

[STEP 1] Loading data from Phase 1 TimescaleDB (Docker)...
  Symbol: SOL/USDT
  Timeframe: 5m
  Date range: 2024-10-10 to 2024-11-09

✓ Loaded 8,640 rows from database
  Columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'open_interest', ...]

[STEP 2] Preparing DataFrames for Phase 2 FeatureEngineer...
  ✓ OHLCV: 8,640 rows
  ✓ Open Interest: 8,640 rows
  ✓ Funding Rate: 2,160 rows
  ...

[STEP 3] Engineering features with Phase 2 FeatureEngineer...
Engineering OI features...
Engineering price features...
Engineering volume features...
...

✓ Feature engineering complete!
  Total columns: 132
  Engineered features: 115

[STEP 4] Creating target variables...
✓ Target variable created
  Target distribution:
    SHORT     : 2,450 samples (30.2%)
    NEUTRAL   : 3,210 samples (39.6%)
    LONG      : 2,450 samples (30.2%)

[STEP 5] Selecting best features...
COMBINED FEATURE SELECTION PIPELINE
Step 1: Removing low-variance features...
Step 2: Removing highly correlated features...
Step 3: Selecting top features by importance...

✓ Feature selection complete
  Selected 50 features from 115

[STEP 6] Analyzing feature importance...
FEATURE IMPORTANCE ANALYSIS
Top 10 Most Important Features:
  1. oi_price_divergence_48          0.0487
  2. rsi_14                           0.0412
  3. oi_macd_histogram                0.0389
  ...

[STEP 7] Saving results...
✓ Saved complete features: data\phase2_features_complete.parquet
✓ Saved selected features: data\phase2_features_selected.parquet
✓ Saved feature importance: data\feature_importance.csv

================================================================================
✅ Integration completed successfully!

Next Steps:
  1. Train ML models using selected features in data/phase2_features_selected.parquet
  2. Evaluate model performance on validation/test sets
  3. Implement live trading with Phase 1 data stream + Phase 2 features
================================================================================
```

---

## 📊 What Just Happened?

### Data Flow

```
Phase 1 Docker TimescaleDB
         ↓
   MarketDataLoader
         ↓
   Merged DataFrame (ohlcv + oi + funding + liquidations + ls_ratio)
         ↓
   Split into separate DataFrames
         ↓
   Phase 2 FeatureEngineer.engineer_all_features()
         ↓
   115+ engineered features
         ↓
   Phase 2 Feature Selection
         ↓
   Top 50 features
         ↓
   Saved to data/phase2_features_selected.parquet
```

### Output Files

**`data/phase2_features_complete.parquet`** (Large ~10-50MB)
- All 115+ engineered features
- Use for feature analysis/exploration

**`data/phase2_features_selected.parquet`** (Small ~2-5MB)
- Top 50 selected features + target
- **Use this for ML model training**

**`data/feature_importance.csv`**
- Feature importance scores
- Use to understand which features matter most

---

## 🔧 Troubleshooting

### Problem: "p2_mlFeature repo not found"
**Fix:**
```powershell
cd C:\Programing\ByAI\claude-code
git clone https://github.com/b9b4ymiN/p2_mlFeature.git
```
Update paths in:
- `config.yaml` → `phase2.repo_path`
- `examples/phase1_to_phase2_integration_demo.py` → `P2_REPO_PATH`

### Problem: "No data returned from database"
**Causes:**
- Phase 1 collectors not running
- No data for requested date range
- Wrong symbol format

**Fix:**
```powershell
# Check collectors are running
docker ps | grep collector

# Check data exists
docker exec -it futures_db psql -U futures_user -d futures_db -c "SELECT COUNT(*) FROM ohlcv WHERE symbol='SOL/USDT';"

# Restart collectors if needed
docker compose restart futures_collector
```

### Problem: "ModuleNotFoundError: No module named 'pandas_ta'"
**Fix:**
```powershell
pip install pandas-ta scikit-learn scipy
```

### Problem: "Connection refused to database"
**Fix:**
```powershell
# Check database container
docker ps | grep futures_db

# Check port exposure
docker port futures_db
# Should show: 5432/tcp -> 0.0.0.0:5432

# Test connection
docker exec -it futures_db psql -U futures_user -d futures_db -c "SELECT 1;"
```

---

## 📖 Next Steps

### 1. Explore Features

```python
import pandas as pd

# Load selected features
df = pd.read_parquet('data/phase2_features_selected.parquet')

print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print(df.describe())

# Check target distribution
print(df['target'].value_counts())
```

### 2. Train ML Models

Use Phase 2 example code from `p2_mlFeature/example_usage.py`:

```python
# Load your features
df = pd.read_parquet('data/phase2_features_selected.parquet')

# Split data
from utils import time_series_split
train, val, test = time_series_split(df, 0.6, 0.2)

# Train model (e.g., XGBoost)
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(train.drop(['timestamp', 'target'], axis=1), train['target'])

# Evaluate
from sklearn.metrics import classification_report
pred = model.predict(val.drop(['timestamp', 'target'], axis=1))
print(classification_report(val['target'], pred))
```

### 3. Implement Live Trading

Combine Phase 1 real-time stream with Phase 2 feature engineering:

```python
# Pseudo-code
while True:
    # 1. Get latest data from Phase 1 websocket
    latest_data = loader.get_latest_data('SOL/USDT', lookback=200)
    
    # 2. Engineer features
    features = engineer.engineer_all_features(latest_data)
    
    # 3. Make prediction
    prediction = model.predict(features.iloc[[-1]])
    
    # 4. Execute trade if signal strong
    if prediction == 2 and confidence > 0.7:  # LONG
        place_order('SOL/USDT', 'BUY', quantity)
```

---

## 📂 File Structure

```
p1_dataCollection/
├── config.yaml                                    # ← Phase 2 settings added
├── features/
│   └── data_loader.py                            # ← Bridge to Phase 1 DB
├── examples/
│   └── phase1_to_phase2_integration_demo.py     # ← Run this!
├── data/
│   ├── phase2_features_complete.parquet         # ← All features
│   ├── phase2_features_selected.parquet         # ← Use this for training
│   └── feature_importance.csv                    # ← Feature rankings
└── P1_TO_P2_INTEGRATION_GUIDE.md                # ← Detailed guide

p2_mlFeature/                                      # ← Clone this repo
├── features/
│   ├── feature_engineer.py                       # ← 100+ features
│   ├── target_engineer.py
│   └── feature_store.py
├── utils/
│   ├── feature_selection.py
│   └── data_split.py
└── example_usage.py
```

---

## ✅ Verification Checklist

- [ ] Phase 1 Docker containers running
- [ ] TimescaleDB has data (`SELECT COUNT(*) FROM ohlcv;` returns > 0)
- [ ] p2_mlFeature repo cloned
- [ ] Phase 2 dependencies installed (`pip install -r requirements.txt`)
- [ ] `config.yaml` updated with p2_mlFeature path
- [ ] Demo script runs without errors
- [ ] Output files created in `data/` directory
- [ ] Feature importance shows valid scores

---

## 🆘 Need Help?

1. **Check logs:** `logs/data_collection.log`
2. **Docker status:** `docker ps` and `docker logs futures_collector`
3. **Database query:** `docker exec -it futures_db psql -U futures_user -d futures_db`
4. **Python errors:** Read stack trace carefully, usually import or path issues

---

**Ready to build ML models! 🚀**

Your Phase 1 → Phase 2 pipeline is now connected. Next: train ML models and implement live trading strategies!
