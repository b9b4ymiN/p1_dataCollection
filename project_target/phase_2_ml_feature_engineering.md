# Phase 2: ML Feature Engineering
## Transforming Raw Data into Predictive Features

**Duration:** Week 3-4  
**Goal:** Engineer 100+ high-quality features from OI, Price, Volume, and Funding data

---

## 🎯 Phase Objectives

1. ✅ Design comprehensive feature set (100+ features)
2. ✅ Implement feature calculation pipeline
3. ✅ Create target variables for ML models
4. ✅ Perform feature selection (reduce to top 30-50 features)
5. ✅ Build feature store for fast access
6. ✅ Prepare train/validation/test splits (time-series aware)

---

## 🧩 Feature Categories

### 1. **Open Interest Features** (Primary Signal) — 25 features

#### Basic OI Metrics
```python
# Absolute and Relative Changes
oi_abs_change = oi_current - oi_previous
oi_pct_change = (oi_current - oi_previous) / oi_previous * 100
oi_log_return = np.log(oi_current / oi_previous)

# Velocity (rate of change)
oi_velocity_1h = (oi_current - oi_1h_ago) / oi_1h_ago
oi_velocity_4h = (oi_current - oi_4h_ago) / oi_4h_ago
oi_velocity_24h = (oi_current - oi_24h_ago) / oi_24h_ago

# Acceleration (change in velocity)
oi_acceleration = oi_velocity_1h - oi_velocity_1h_prev
```

#### OI Momentum & Trend
```python
# Moving averages
oi_sma_20 = ta.sma(oi, 20)
oi_sma_50 = ta.sma(oi, 50)
oi_ema_12 = ta.ema(oi, 12)
oi_ema_26 = ta.ema(oi, 26)

# OI MACD (like price MACD)
oi_macd = oi_ema_12 - oi_ema_26
oi_macd_signal = ta.ema(oi_macd, 9)
oi_macd_histogram = oi_macd - oi_macd_signal

# Trend strength
oi_trend_slope = linear_regression_slope(oi, period=20)
oi_r_squared = r_squared(oi, period=20)  # How strong the trend is
```

#### OI Volatility
```python
# Standard deviation
oi_std_20 = ta.std(oi, 20)
oi_std_50 = ta.std(oi, 50)

# OI Bollinger Bands
oi_bb_upper = oi_sma_20 + 2 * oi_std_20
oi_bb_lower = oi_sma_20 - 2 * oi_std_20
oi_bb_position = (oi_current - oi_bb_lower) / (oi_bb_upper - oi_bb_lower)

# Coefficient of Variation
oi_cv = oi_std_20 / oi_sma_20
```

#### OI Divergence (Critical!)
```python
# OI-Price Divergence
# If price up but OI down = bearish divergence
# If price down but OI down = bullish divergence

def calculate_divergence(oi, price, period=20):
    oi_direction = np.sign(oi[-1] - oi[-period])
    price_direction = np.sign(price[-1] - price[-period])
    
    if oi_direction != price_direction:
        if price_direction > 0:
            return -1  # Bearish divergence (price up, OI down)
        else:
            return 1   # Bullish divergence (price down, OI down)
    return 0  # No divergence

divergence_4h = calculate_divergence(oi, price, period=48)  # 4h on 5m data
divergence_1d = calculate_divergence(oi, price, period=288)  # 1d on 5m data
```

#### OI Extremes
```python
# Z-score (how far from mean)
oi_zscore = (oi_current - oi_mean_50) / oi_std_50

# Percentile rank
oi_percentile_100 = percentile_rank(oi_current, oi[-100:])

# Distance from historical high/low
oi_high_100 = max(oi[-100:])
oi_low_100 = min(oi[-100:])
oi_dist_from_high = (oi_current - oi_high_100) / oi_high_100
oi_dist_from_low = (oi_current - oi_low_100) / oi_low_100
```

---

### 2. **Price Action Features** — 30 features

#### Returns
```python
# Simple returns (different periods)
return_1 = (close - close_1) / close_1
return_5 = (close - close_5) / close_5
return_20 = (close - close_20) / close_20
return_100 = (close - close_100) / close_100

# Log returns
log_return_1 = np.log(close / close_1)
log_return_5 = np.log(close / close_5)

# Volatility (realized)
realized_vol_20 = np.std(log_returns[-20:]) * np.sqrt(288)  # Annualized
```

#### Trend Indicators
```python
# Moving averages
sma_20 = ta.sma(close, 20)
sma_50 = ta.sma(close, 50)
sma_200 = ta.sma(close, 200)
ema_12 = ta.ema(close, 12)
ema_26 = ta.ema(close, 26)

# Price relative to MAs
price_vs_sma20 = (close - sma_20) / sma_20
price_vs_sma50 = (close - sma_50) / sma_50

# MA crossovers
ma_cross = np.sign(sma_20 - sma_50)  # 1 if golden cross, -1 if death cross
```

#### Momentum
```python
# RSI
rsi_14 = ta.rsi(close, 14)
rsi_50 = ta.rsi(close, 50)

# MACD
macd = ema_12 - ema_26
macd_signal = ta.ema(macd, 9)
macd_histogram = macd - macd_signal

# Stochastic
stoch_k, stoch_d = ta.stoch(high, low, close, 14, 3, 3)

# Rate of Change
roc_10 = ta.roc(close, 10)
roc_30 = ta.roc(close, 30)
```

#### Volatility
```python
# ATR (Average True Range)
atr_14 = ta.atr(high, low, close, 14)
atr_50 = ta.atr(high, low, close, 50)

# Normalized ATR
natr = atr_14 / close

# Bollinger Bands
bb_upper, bb_middle, bb_lower = ta.bbands(close, 20, 2)
bb_width = (bb_upper - bb_lower) / bb_middle
bb_position = (close - bb_lower) / (bb_upper - bb_lower)

# Keltner Channels
kc_upper = ema_20 + 2 * atr_14
kc_lower = ema_20 - 2 * atr_14
kc_width = (kc_upper - kc_lower) / ema_20
```

#### Market Structure
```python
# Higher High, Higher Low detection
def detect_market_structure(high, low, lookback=20):
    hh = (high[-1] > max(high[-lookback:-1]))  # Higher high
    hl = (low[-1] > max(low[-lookback:-1]))    # Higher low
    lh = (high[-1] < min(high[-lookback:-1]))  # Lower high
    ll = (low[-1] < min(low[-lookback:-1]))    # Lower low
    
    if hh and hl:
        return 1   # Uptrend
    elif lh and ll:
        return -1  # Downtrend
    else:
        return 0   # Range

market_structure = detect_market_structure(high, low, 50)

# ADX (trend strength)
adx = ta.adx(high, low, close, 14)
```

---

### 3. **Volume Features** — 20 features

#### Volume Metrics
```python
# Volume changes
volume_change = (volume - volume_1) / volume_1
volume_sma_20 = ta.sma(volume, 20)
volume_ratio = volume / volume_sma_20

# Volume momentum
volume_roc = ta.roc(volume, 10)

# Cumulative Volume Delta (CVD)
# Taker buy volume - Taker sell volume
taker_buy_ratio = taker_buy_volume / volume
cvd = cumsum(taker_buy_volume - (volume - taker_buy_volume))

# Volume-Price Correlation
price_volume_corr = rolling_correlation(close, volume, 20)
```

#### Volume-Based Indicators
```python
# OBV (On-Balance Volume)
obv = ta.obv(close, volume)
obv_sma_20 = ta.sma(obv, 20)

# CMF (Chaikin Money Flow)
cmf = ta.cmf(high, low, close, volume, 20)

# MFI (Money Flow Index) - RSI with volume
mfi = ta.mfi(high, low, close, volume, 14)

# VWAP (Volume Weighted Average Price)
vwap = cumsum(close * volume) / cumsum(volume)
price_vs_vwap = (close - vwap) / vwap
```

#### OI/Volume Interaction
```python
# OI-Volume Ratio (key metric!)
oi_volume_ratio = open_interest / volume_sma_20

# When OI rises with low volume = weak move
# When OI rises with high volume = strong conviction

oi_volume_divergence = np.sign(oi_pct_change) - np.sign(volume_change)
```

---

### 4. **Funding Rate Features** — 10 features

```python
# Current funding rate
funding_rate_current = get_latest_funding()

# Funding rate changes
funding_rate_change = funding_rate_current - funding_rate_prev
funding_rate_change_24h = funding_rate_current - funding_rate_24h_ago

# Cumulative funding
cumulative_funding_7d = sum(funding_rates[-56:])  # 8h intervals

# Funding extremes
funding_zscore = (funding_rate_current - mean(funding_rates[-100:])) / std(funding_rates[-100:])
funding_percentile = percentile_rank(funding_rate_current, funding_rates[-100:])

# Funding thresholds
funding_extreme_positive = (funding_rate_current > 0.05)  # Overleveraged longs
funding_extreme_negative = (funding_rate_current < -0.02)  # Overleveraged shorts

# Time to next funding
minutes_to_funding = (next_funding_time - current_time).total_seconds() / 60
```

---

### 5. **Liquidation Features** — 10 features

```python
# Liquidation volume (sum of liquidated positions)
liquidation_vol_1h = sum(liquidation_quantities[-12:])  # Last 1h on 5m data

# Long vs Short liquidations
long_liq_vol_1h = sum(liquidations[liquidations['side'] == 'SELL']['quantity'][-12:])
short_liq_vol_1h = sum(liquidations[liquidations['side'] == 'BUY']['quantity'][-12:])

# Net liquidation pressure
net_liquidation = short_liq_vol_1h - long_liq_vol_1h  # Positive = more shorts liquidated

# Liquidation rate (count)
liquidation_count_1h = len(liquidations[-12:])

# Average liquidation size
avg_liq_size = liquidation_vol_1h / max(liquidation_count_1h, 1)

# Liquidation cascades (spikes in liquidations)
liq_spike = (liquidation_vol_1h > 2 * mean(liquidation_volumes[-24:]))
```

---

### 6. **Long/Short Ratio Features** — 5 features

```python
# Top trader long/short ratio
ls_ratio_current = get_latest_ls_ratio()

# Changes in ratio
ls_ratio_change_1h = ls_ratio_current - ls_ratio_1h_ago
ls_ratio_change_4h = ls_ratio_current - ls_ratio_4h_ago

# Ratio extremes
ls_ratio_percentile = percentile_rank(ls_ratio_current, ls_ratios[-100:])

# Interpretation:
# High ratio (>1.5) = Too many longs, potential reversal down
# Low ratio (<0.7) = Too many shorts, potential reversal up
```

---

### 7. **Time-Based Features** — 10 features

```python
# Time of day (cyclical encoding)
hour = current_time.hour
hour_sin = np.sin(2 * np.pi * hour / 24)
hour_cos = np.cos(2 * np.pi * hour / 24)

# Day of week
day_of_week = current_time.dayofweek
day_sin = np.sin(2 * np.pi * day_of_week / 7)
day_cos = np.cos(2 * np.pi * day_of_week / 7)

# Market sessions
is_asia_session = (0 <= hour < 8)
is_europe_session = (7 <= hour < 16)
is_us_session = (13 <= hour < 22)

# Funding cycle position (0-8 hours, repeats)
hours_since_funding = (current_time - last_funding_time).total_seconds() / 3600
funding_cycle_sin = np.sin(2 * np.pi * hours_since_funding / 8)
funding_cycle_cos = np.cos(2 * np.pi * hours_since_funding / 8)
```

---

## 🎯 Target Variable Engineering

### For Classification Models

```python
# Future return thresholds
future_return_4h = (close_4h_future - close_current) / close_current

# Classification labels
def create_classification_target(future_return, threshold=0.005):
    """
    Predict if there will be a significant move in the next 4h
    
    Returns:
        2: LONG (price will rise > threshold)
        1: NEUTRAL (price within ±threshold)
        0: SHORT (price will fall < -threshold)
    """
    if future_return > threshold:
        return 2  # LONG
    elif future_return < -threshold:
        return 0  # SHORT
    else:
        return 1  # NEUTRAL

target_class = create_classification_target(future_return_4h, threshold=0.005)

# Alternative: Binary classification (Long vs Not Long)
target_binary = (future_return_4h > 0.005).astype(int)
```

### For Regression Models

```python
# Predict actual future returns
target_return_1h = (close_1h_future - close_current) / close_current
target_return_4h = (close_4h_future - close_current) / close_current
target_return_24h = (close_24h_future - close_current) / close_current

# Predict future OI
target_oi_change_4h = (oi_4h_future - oi_current) / oi_current
```

### For RL Environment

```python
# State (current market conditions) = all features above
# Action = {LONG, SHORT, EXIT, HOLD}
# Reward = PnL - risk penalty - transaction costs (computed after action taken)
```

---

## 🔬 Feature Engineering Pipeline

```python
# features/feature_engineer.py

import pandas as pd
import numpy as np
import pandas_ta as ta
from typing import Dict, List

class FeatureEngineer:
    """
    Comprehensive feature engineering for OI trading
    """
    
    def __init__(self):
        self.feature_names = []
        
    def engineer_all_features(
        self, 
        ohlcv: pd.DataFrame, 
        oi: pd.DataFrame,
        funding: pd.DataFrame,
        liquidations: pd.DataFrame,
        ls_ratio: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Main function to engineer all features
        """
        df = ohlcv.copy()
        
        # Merge OI data
        df = df.merge(oi, on='timestamp', how='left', suffixes=('', '_oi'))
        
        # Merge funding rate
        df = df.merge(funding, on='timestamp', how='left', suffixes=('', '_fund'))
        
        # Engineer features by category
        df = self._oi_features(df)
        df = self._price_features(df)
        df = self._volume_features(df)
        df = self._funding_features(df)
        df = self._liquidation_features(df, liquidations)
        df = self._ls_ratio_features(df, ls_ratio)
        df = self._time_features(df)
        df = self._interaction_features(df)
        
        # Fill NaN (from rolling calculations)
        df = df.fillna(method='bfill').fillna(0)
        
        return df
    
    def _oi_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """OI-based features"""
        oi = df['open_interest']
        price = df['close']
        
        # Basic changes
        df['oi_change_1'] = oi.pct_change(1)
        df['oi_change_5'] = oi.pct_change(5)
        df['oi_change_20'] = oi.pct_change(20)
        
        # Velocity
        df['oi_velocity_12'] = (oi - oi.shift(12)) / oi.shift(12)  # 1h
        df['oi_velocity_48'] = (oi - oi.shift(48)) / oi.shift(48)  # 4h
        
        # Moving averages
        df['oi_sma_20'] = oi.rolling(20).mean()
        df['oi_sma_50'] = oi.rolling(50).mean()
        df['oi_ema_12'] = oi.ewm(span=12).mean()
        df['oi_ema_26'] = oi.ewm(span=26).mean()
        
        # MACD
        df['oi_macd'] = df['oi_ema_12'] - df['oi_ema_26']
        df['oi_macd_signal'] = df['oi_macd'].ewm(span=9).mean()
        df['oi_macd_hist'] = df['oi_macd'] - df['oi_macd_signal']
        
        # Volatility
        df['oi_std_20'] = oi.rolling(20).std()
        df['oi_bb_upper'] = df['oi_sma_20'] + 2 * df['oi_std_20']
        df['oi_bb_lower'] = df['oi_sma_20'] - 2 * df['oi_std_20']
        df['oi_bb_position'] = (oi - df['oi_bb_lower']) / (df['oi_bb_upper'] - df['oi_bb_lower'])
        
        # Divergence
        df['oi_price_divergence_20'] = self._calculate_divergence(
            oi, price, period=20
        )
        df['oi_price_divergence_50'] = self._calculate_divergence(
            oi, price, period=50
        )
        
        # Z-score
        df['oi_zscore'] = (oi - df['oi_sma_50']) / df['oi_std_20']
        
        return df
    
    def _price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Price action features"""
        close = df['close']
        high = df['high']
        low = df['low']
        
        # Returns
        for period in [1, 5, 10, 20, 50]:
            df[f'return_{period}'] = close.pct_change(period)
        
        # MAs
        df['sma_20'] = close.rolling(20).mean()
        df['sma_50'] = close.rolling(50).mean()
        df['sma_200'] = close.rolling(200).mean()
        df['ema_12'] = close.ewm(span=12).mean()
        df['ema_26'] = close.ewm(span=26).mean()
        
        # Price vs MAs
        df['price_vs_sma20'] = (close - df['sma_20']) / df['sma_20']
        df['price_vs_sma50'] = (close - df['sma_50']) / df['sma_50']
        
        # RSI
        df['rsi_14'] = ta.rsi(close, 14)
        df['rsi_50'] = ta.rsi(close, 50)
        
        # MACD
        macd = ta.macd(close)
        df = pd.concat([df, macd], axis=1)
        
        # ATR
        df['atr_14'] = ta.atr(high, low, close, 14)
        df['natr'] = df['atr_14'] / close
        
        # Bollinger Bands
        bbands = ta.bbands(close, 20, 2)
        df = pd.concat([df, bbands], axis=1)
        df['bb_width'] = (df['BBU_20_2.0'] - df['BBL_20_2.0']) / df['BBM_20_2.0']
        df['bb_position'] = (close - df['BBL_20_2.0']) / (df['BBU_20_2.0'] - df['BBL_20_2.0'])
        
        # ADX
        adx = ta.adx(high, low, close, 14)
        df = pd.concat([df, adx], axis=1)
        
        return df
    
    def _volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Volume features"""
        volume = df['volume']
        close = df['close']
        
        # Volume changes
        df['volume_change'] = volume.pct_change(1)
        df['volume_sma_20'] = volume.rolling(20).mean()
        df['volume_ratio'] = volume / df['volume_sma_20']
        
        # OBV
        df['obv'] = ta.obv(close, volume)
        
        # CMF
        df['cmf'] = ta.cmf(df['high'], df['low'], close, volume, 20)
        
        # MFI
        df['mfi'] = ta.mfi(df['high'], df['low'], close, volume, 14)
        
        # VWAP
        df['vwap'] = (close * volume).cumsum() / volume.cumsum()
        df['price_vs_vwap'] = (close - df['vwap']) / df['vwap']
        
        return df
    
    def _funding_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Funding rate features"""
        funding = df['funding_rate']
        
        # Changes
        df['funding_change'] = funding.diff(1)
        df['funding_change_24h'] = funding.diff(288)  # 8h * 3
        
        # Cumulative
        df['cumulative_funding_7d'] = funding.rolling(56).sum()
        
        # Z-score
        df['funding_zscore'] = (funding - funding.rolling(100).mean()) / funding.rolling(100).std()
        
        # Extremes
        df['funding_extreme_positive'] = (funding > 0.05).astype(int)
        df['funding_extreme_negative'] = (funding < -0.02).astype(int)
        
        return df
    
    def _liquidation_features(self, df: pd.DataFrame, liq_df: pd.DataFrame) -> pd.DataFrame:
        """Liquidation features"""
        # This would require aggregating liquidation data by timestamp
        # For simplicity, assume we have pre-aggregated liquidation metrics
        
        # Merge liquidation data
        liq_agg = liq_df.groupby('timestamp').agg({
            'quantity': 'sum',
            'order_id': 'count'
        }).rename(columns={'quantity': 'liq_volume', 'order_id': 'liq_count'})
        
        df = df.merge(liq_agg, on='timestamp', how='left').fillna(0)
        
        # Rolling aggregations
        df['liq_volume_1h'] = df['liq_volume'].rolling(12).sum()
        df['liq_count_1h'] = df['liq_count'].rolling(12).sum()
        
        return df
    
    def _ls_ratio_features(self, df: pd.DataFrame, ls_df: pd.DataFrame) -> pd.DataFrame:
        """Long/Short ratio features"""
        df = df.merge(ls_df[['timestamp', 'longShortRatio']], on='timestamp', how='left')
        
        ls_ratio = df['longShortRatio']
        
        # Changes
        df['ls_ratio_change_1h'] = ls_ratio.diff(12)
        df['ls_ratio_change_4h'] = ls_ratio.diff(48)
        
        # Percentile
        df['ls_ratio_percentile'] = ls_ratio.rolling(100).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1]
        )
        
        return df
    
    def _time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Time-based features"""
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        
        # Cyclical encoding
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        
        # Market sessions
        df['is_asia_session'] = ((df['hour'] >= 0) & (df['hour'] < 8)).astype(int)
        df['is_europe_session'] = ((df['hour'] >= 7) & (df['hour'] < 16)).astype(int)
        df['is_us_session'] = ((df['hour'] >= 13) & (df['hour'] < 22)).astype(int)
        
        return df
    
    def _interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Interaction features between different categories"""
        
        # OI-Volume ratio
        df['oi_volume_ratio'] = df['open_interest'] / df['volume_sma_20']
        
        # OI-Volume divergence
        df['oi_volume_divergence'] = (
            np.sign(df['oi_change_1']) - np.sign(df['volume_change'])
        )
        
        # RSI * Funding
        df['rsi_funding_interaction'] = df['rsi_14'] * df['funding_rate']
        
        # OI change * Price momentum
        df['oi_price_momentum'] = df['oi_change_20'] * df['return_20']
        
        return df
    
    @staticmethod
    def _calculate_divergence(series1, series2, period):
        """Calculate divergence between two series"""
        dir1 = np.sign(series1.diff(period))
        dir2 = np.sign(series2.diff(period))
        divergence = (dir1 != dir2).astype(int) * np.sign(dir2 - dir1)
        return divergence
```

---

## 🎯 Feature Selection

### Method 1: Correlation-Based Filtering
```python
def remove_highly_correlated_features(df: pd.DataFrame, threshold=0.9):
    """Remove features that are too correlated"""
    corr_matrix = df.corr().abs()
    upper_triangle = corr_matrix.where(
        np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
    )
    
    to_drop = [
        column for column in upper_triangle.columns 
        if any(upper_triangle[column] > threshold)
    ]
    
    return df.drop(columns=to_drop)
```

### Method 2: Feature Importance (Tree-based)
```python
from sklearn.ensemble import RandomForestClassifier
import shap

def select_top_features_by_importance(X, y, n_features=50):
    """Select top N features by importance"""
    
    # Train a quick RF model
    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    rf.fit(X, y)
    
    # Get feature importances
    importances = pd.DataFrame({
        'feature': X.columns,
        'importance': rf.feature_importances_
    }).sort_values('importance', ascending=False)
    
    # Select top N
    top_features = importances.head(n_features)['feature'].tolist()
    
    return X[top_features], importances

# Alternative: SHAP values (more accurate but slower)
def select_features_by_shap(X, y, n_features=50):
    model = RandomForestClassifier(n_estimators=100)
    model.fit(X, y)
    
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    
    # Mean absolute SHAP value per feature
    shap_importance = np.abs(shap_values).mean(axis=0)
    
    feature_importance = pd.DataFrame({
        'feature': X.columns,
        'shap_importance': shap_importance
    }).sort_values('shap_importance', ascending=False)
    
    top_features = feature_importance.head(n_features)['feature'].tolist()
    
    return X[top_features], feature_importance
```

### Method 3: Permutation Importance
```python
from sklearn.inspection import permutation_importance

def select_features_by_permutation(model, X, y, n_features=50):
    """Select features by permutation importance"""
    
    result = permutation_importance(
        model, X, y, 
        n_repeats=10, 
        random_state=42, 
        n_jobs=-1
    )
    
    perm_importance = pd.DataFrame({
        'feature': X.columns,
        'importance': result.importances_mean
    }).sort_values('importance', ascending=False)
    
    top_features = perm_importance.head(n_features)['feature'].tolist()
    
    return X[top_features], perm_importance
```

---

## 📦 Feature Store Implementation

```python
# features/feature_store.py

import pickle
import redis
import json
from typing import Dict, List
import pandas as pd

class FeatureStore:
    """
    Fast feature access via Redis for live trading
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        
    def save_features(self, symbol: str, timestamp: pd.Timestamp, features: Dict):
        """Save computed features to Redis"""
        key = f"features:{symbol}:{timestamp.isoformat()}"
        
        # Serialize to JSON
        value = json.dumps(features)
        
        # Save with TTL (keep for 7 days)
        self.redis.setex(key, 7 * 24 * 3600, value)
    
    def get_features(self, symbol: str, timestamp: pd.Timestamp) -> Dict:
        """Retrieve features from Redis"""
        key = f"features:{symbol}:{timestamp.isoformat()}"
        value = self.redis.get(key)
        
        if value:
            return json.loads(value)
        return None
    
    def get_latest_features(self, symbol: str) -> Dict:
        """Get most recent features for a symbol"""
        pattern = f"features:{symbol}:*"
        keys = self.redis.keys(pattern)
        
        if not keys:
            return None
        
        # Get the most recent key
        latest_key = sorted(keys)[-1]
        value = self.redis.get(latest_key)
        
        return json.loads(value) if value else None
    
    def save_feature_metadata(self, feature_names: List[str], feature_types: Dict):
        """Save feature metadata (names, types, selection status)"""
        metadata = {
            'feature_names': feature_names,
            'feature_types': feature_types,
            'timestamp': pd.Timestamp.now().isoformat()
        }
        
        self.redis.set('feature_metadata', json.dumps(metadata))
    
    def get_feature_metadata(self) -> Dict:
        """Retrieve feature metadata"""
        value = self.redis.get('feature_metadata')
        return json.loads(value) if value else None
```

---

## 📊 Train/Val/Test Split Strategy

```python
def time_series_split(df: pd.DataFrame, train_ratio=0.6, val_ratio=0.2):
    """
    Time-series aware split (no shuffling!)
    """
    n = len(df)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))
    
    train = df.iloc[:train_end]
    val = df.iloc[train_end:val_end]
    test = df.iloc[val_end:]
    
    return train, val, test

# Example usage
train_df, val_df, test_df = time_series_split(features_df)

print(f"Train: {train_df['timestamp'].min()} to {train_df['timestamp'].max()}")
print(f"Val:   {val_df['timestamp'].min()} to {val_df['timestamp'].max()}")
print(f"Test:  {test_df['timestamp'].min()} to {test_df['timestamp'].max()}")
```

---

## ✅ Phase 2 Deliverables Checklist

- [ ] Feature engineering pipeline implemented (100+ features)
- [ ] OI features: 25+ features calculated
- [ ] Price features: 30+ features calculated
- [ ] Volume features: 20+ features calculated
- [ ] Funding & liquidation features: 15+ features
- [ ] Time & interaction features: 15+ features
- [ ] Target variables created (classification & regression)
- [ ] Feature selection performed (reduced to top 30-50)
- [ ] Feature store implemented (Redis)
- [ ] Train/Val/Test splits created (time-series aware)
- [ ] Feature importance analysis completed
- [ ] Documentation written

---

## 🚀 Next Phase

**Phase 3: ML Model Training**

With features ready, we'll train multiple ML models:
- XGBoost/LightGBM for classification
- Neural Networks for regression
- LSTM for time-series forecasting
- Ensemble meta-model

Ready to build AI models? 🧠
