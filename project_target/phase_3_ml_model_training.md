# Phase 3: ML Model Training & Ensemble
## Building Intelligent Prediction Models

**Duration:** Week 5-7  
**Goal:** Train, optimize, and ensemble multiple ML models for entry signal prediction

---

## 🎯 Phase Objectives

1. ✅ Train classification models (Entry Signal: LONG/SHORT/NEUTRAL)
2. ✅ Train regression models (Price Target Prediction)
3. ✅ Train time-series models (OI & Price Forecasting with LSTM)
4. ✅ Build ensemble meta-model (Stacking)
5. ✅ Hyperparameter optimization with Optuna
6. ✅ Walk-forward validation
7. ✅ Model interpretability analysis (SHAP)

---

## 🏗️ ML Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                   FEATURE INPUT (50 features)             │
└────────────────────────┬─────────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            │                         │
            ▼                         ▼
┌─────────────────────┐   ┌────────────────────────┐
│ CLASSIFICATION      │   │ REGRESSION             │
│ MODELS              │   │ MODELS                 │
│                     │   │                        │
│ • XGBoost           │   │ • RandomForest         │
│ • LightGBM          │   │ • XGBoost              │
│ • CatBoost          │   │ • Neural Network       │
│ • RandomForest      │   │                        │
└──────────┬──────────┘   └──────────┬─────────────┘
           │                         │
           └────────────┬────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ TIME-SERIES MODELS    │
            │ • LSTM (OI Forecast)  │
            │ • LSTM (Price)        │
            │ • GRU (Alternative)   │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ ENSEMBLE META-MODEL   │
            │ (Stacking Classifier) │
            │                       │
            │ Takes predictions     │
            │ from all models       │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ FINAL PREDICTION      │
            │ • Entry Signal        │
            │ • Confidence Score    │
            │ • Target Price        │
            └───────────────────────┘
```

---

## 🤖 Model 1: Classification (Entry Signal)

### 🎯 Task
Predict if next 4 hours will have:
- **Class 0:** SHORT opportunity (return < -0.5%)
- **Class 1:** NEUTRAL (return between -0.5% and +0.5%)
- **Class 2:** LONG opportunity (return > +0.5%)

### XGBoost Classifier

```python
# models/xgboost_classifier.py

import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, confusion_matrix
import optuna

class XGBoostEntryPredictor:
    """
    XGBoost model for entry signal classification
    """
    
    def __init__(self, params=None):
        self.params = params or self._default_params()
        self.model = None
        self.feature_importance = None
        
    def _default_params(self):
        return {
            'objective': 'multi:softprob',
            'num_class': 3,
            'max_depth': 6,
            'learning_rate': 0.05,
            'n_estimators': 300,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'min_child_weight': 3,
            'gamma': 0.1,
            'reg_alpha': 0.1,
            'reg_lambda': 1.0,
            'random_state': 42,
            'tree_method': 'hist',
            'eval_metric': 'mlogloss'
        }
    
    def train(self, X_train, y_train, X_val, y_val):
        """Train XGBoost model"""
        
        self.model = xgb.XGBClassifier(**self.params)
        
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            early_stopping_rounds=50,
            verbose=50
        )
        
        # Store feature importance
        self.feature_importance = pd.DataFrame({
            'feature': X_train.columns,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        return self.model
    
    def predict(self, X):
        """Predict class (0, 1, 2)"""
        return self.model.predict(X)
    
    def predict_proba(self, X):
        """Predict class probabilities"""
        return self.model.predict_proba(X)
    
    def evaluate(self, X_test, y_test):
        """Evaluate model performance"""
        y_pred = self.predict(X_test)
        y_proba = self.predict_proba(X_test)
        
        # Classification metrics
        report = classification_report(y_test, y_pred, output_dict=True)
        conf_matrix = confusion_matrix(y_test, y_pred)
        
        # Trading-specific metrics
        accuracy = (y_pred == y_test).mean()
        
        # Directional accuracy (ignore NEUTRAL)
        mask = (y_test != 1) & (y_pred != 1)
        directional_acc = (y_pred[mask] == y_test[mask]).mean() if mask.sum() > 0 else 0
        
        return {
            'accuracy': accuracy,
            'directional_accuracy': directional_acc,
            'classification_report': report,
            'confusion_matrix': conf_matrix,
            'feature_importance': self.feature_importance
        }
    
    def optimize_hyperparameters(self, X_train, y_train, X_val, y_val, n_trials=100):
        """Hyperparameter optimization with Optuna"""
        
        def objective(trial):
            params = {
                'objective': 'multi:softprob',
                'num_class': 3,
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'n_estimators': trial.suggest_int('n_estimators', 100, 500),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'gamma': trial.suggest_float('gamma', 0, 0.5),
                'reg_alpha': trial.suggest_float('reg_alpha', 0, 1.0),
                'reg_lambda': trial.suggest_float('reg_lambda', 0, 1.0),
                'random_state': 42,
                'tree_method': 'hist'
            }
            
            model = xgb.XGBClassifier(**params)
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                early_stopping_rounds=30,
                verbose=False
            )
            
            y_pred = model.predict(X_val)
            accuracy = (y_pred == y_val).mean()
            
            return accuracy
        
        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
        
        print(f"Best accuracy: {study.best_value:.4f}")
        print(f"Best params: {study.best_params}")
        
        self.params.update(study.best_params)
        
        return study.best_params
```

### LightGBM Classifier

```python
# models/lightgbm_classifier.py

import lightgbm as lgb

class LightGBMEntryPredictor:
    """
    LightGBM model for entry signal classification
    """
    
    def __init__(self, params=None):
        self.params = params or self._default_params()
        self.model = None
        
    def _default_params(self):
        return {
            'objective': 'multiclass',
            'num_class': 3,
            'metric': 'multi_logloss',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'n_estimators': 300
        }
    
    def train(self, X_train, y_train, X_val, y_val):
        """Train LightGBM model"""
        
        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
        
        self.model = lgb.train(
            self.params,
            train_data,
            valid_sets=[val_data],
            callbacks=[
                lgb.early_stopping(stopping_rounds=50),
                lgb.log_evaluation(period=50)
            ]
        )
        
        return self.model
    
    def predict(self, X):
        """Predict class"""
        proba = self.model.predict(X)
        return np.argmax(proba, axis=1)
    
    def predict_proba(self, X):
        """Predict probabilities"""
        return self.model.predict(X)
```

### CatBoost Classifier

```python
# models/catboost_classifier.py

from catboost import CatBoostClassifier

class CatBoostEntryPredictor:
    """
    CatBoost model for entry signal classification
    """
    
    def __init__(self, params=None):
        self.params = params or self._default_params()
        self.model = None
        
    def _default_params(self):
        return {
            'iterations': 500,
            'learning_rate': 0.05,
            'depth': 6,
            'loss_function': 'MultiClass',
            'eval_metric': 'Accuracy',
            'random_seed': 42,
            'verbose': 50,
            'early_stopping_rounds': 50
        }
    
    def train(self, X_train, y_train, X_val, y_val):
        """Train CatBoost model"""
        
        self.model = CatBoostClassifier(**self.params)
        
        self.model.fit(
            X_train, y_train,
            eval_set=(X_val, y_val),
            use_best_model=True
        )
        
        return self.model
    
    def predict(self, X):
        return self.model.predict(X)
    
    def predict_proba(self, X):
        return self.model.predict_proba(X)
```

---

## 📈 Model 2: Regression (Price Target)

### Task
Predict actual future return (%) for the next 4 hours

### XGBoost Regressor

```python
# models/xgboost_regressor.py

import xgboost as xgb

class XGBoostPricePredictor:
    """
    XGBoost regression model for price target prediction
    """
    
    def __init__(self, params=None):
        self.params = params or self._default_params()
        self.model = None
        
    def _default_params(self):
        return {
            'objective': 'reg:squarederror',
            'max_depth': 5,
            'learning_rate': 0.05,
            'n_estimators': 300,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42,
            'tree_method': 'hist'
        }
    
    def train(self, X_train, y_train, X_val, y_val):
        """Train XGBoost regression model"""
        
        self.model = xgb.XGBRegressor(**self.params)
        
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            early_stopping_rounds=50,
            verbose=50
        )
        
        return self.model
    
    def predict(self, X):
        """Predict future return"""
        return self.model.predict(X)
    
    def evaluate(self, X_test, y_test):
        """Evaluate regression performance"""
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
        
        y_pred = self.predict(X_test)
        
        mse = mean_squared_error(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        # Directional accuracy
        direction_correct = (np.sign(y_pred) == np.sign(y_test)).mean()
        
        return {
            'mse': mse,
            'rmse': np.sqrt(mse),
            'mae': mae,
            'r2': r2,
            'directional_accuracy': direction_correct
        }
```

### Neural Network Regressor

```python
# models/nn_regressor.py

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

class NeuralNetRegressor(nn.Module):
    """
    Deep Neural Network for price prediction
    """
    
    def __init__(self, input_dim, hidden_dims=[128, 64, 32]):
        super(NeuralNetRegressor, self).__init__()
        
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.BatchNorm1d(hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.3))
            prev_dim = hidden_dim
        
        # Output layer
        layers.append(nn.Linear(prev_dim, 1))
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.network(x)

class NeuralNetTrainer:
    """
    Trainer for Neural Network
    """
    
    def __init__(self, input_dim):
        self.model = NeuralNetRegressor(input_dim)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        
    def train(self, X_train, y_train, X_val, y_val, epochs=100, batch_size=256):
        """Train neural network"""
        
        # Prepare data
        train_dataset = TensorDataset(
            torch.FloatTensor(X_train.values),
            torch.FloatTensor(y_train.values).unsqueeze(1)
        )
        val_dataset = TensorDataset(
            torch.FloatTensor(X_val.values),
            torch.FloatTensor(y_val.values).unsqueeze(1)
        )
        
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size)
        
        # Loss and optimizer
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=10
        )
        
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(epochs):
            # Training
            self.model.train()
            train_loss = 0
            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)
                
                optimizer.zero_grad()
                outputs = self.model(X_batch)
                loss = criterion(outputs, y_batch)
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
            
            # Validation
            self.model.eval()
            val_loss = 0
            with torch.no_grad():
                for X_batch, y_batch in val_loader:
                    X_batch = X_batch.to(self.device)
                    y_batch = y_batch.to(self.device)
                    outputs = self.model(X_batch)
                    loss = criterion(outputs, y_batch)
                    val_loss += loss.item()
            
            train_loss /= len(train_loader)
            val_loss /= len(val_loader)
            
            scheduler.step(val_loss)
            
            if epoch % 10 == 0:
                print(f"Epoch {epoch}: Train Loss = {train_loss:.6f}, Val Loss = {val_loss:.6f}")
            
            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                # Save best model
                torch.save(self.model.state_dict(), 'best_nn_model.pth')
            else:
                patience_counter += 1
                if patience_counter >= 20:
                    print("Early stopping triggered")
                    break
        
        # Load best model
        self.model.load_state_dict(torch.load('best_nn_model.pth'))
        
    def predict(self, X):
        """Predict future returns"""
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X.values).to(self.device)
            predictions = self.model(X_tensor).cpu().numpy().flatten()
        return predictions
```

---

## 🔮 Model 3: LSTM Time-Series Forecaster

### Task
Forecast next OI value and price using sequential patterns

```python
# models/lstm_forecaster.py

import torch
import torch.nn as nn
import numpy as np

class LSTMForecaster(nn.Module):
    """
    LSTM model for time-series forecasting of OI and Price
    """
    
    def __init__(self, input_dim, hidden_dim=64, num_layers=2, output_dim=1):
        super(LSTMForecaster, self).__init__()
        
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        # LSTM layers
        self.lstm = nn.LSTM(
            input_dim, 
            hidden_dim, 
            num_layers, 
            batch_first=True,
            dropout=0.2
        )
        
        # Fully connected layer
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, output_dim)
        )
    
    def forward(self, x):
        # x shape: (batch, seq_len, input_dim)
        lstm_out, _ = self.lstm(x)
        
        # Take last timestep output
        last_output = lstm_out[:, -1, :]
        
        # Pass through FC layers
        prediction = self.fc(last_output)
        
        return prediction

class LSTMTrainer:
    """
    Trainer for LSTM model
    """
    
    def __init__(self, input_dim, lookback=50):
        self.lookback = lookback
        self.model = LSTMForecaster(input_dim)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        
    def create_sequences(self, data, target, lookback):
        """
        Create sequences for LSTM
        
        For each sample, take previous 'lookback' timesteps as input
        """
        X, y = [], []
        
        for i in range(lookback, len(data)):
            X.append(data[i-lookback:i])
            y.append(target[i])
        
        return np.array(X), np.array(y)
    
    def train(self, X_train, y_train, X_val, y_val, epochs=50, batch_size=64):
        """Train LSTM model"""
        
        # Create sequences
        X_train_seq, y_train_seq = self.create_sequences(
            X_train.values, y_train.values, self.lookback
        )
        X_val_seq, y_val_seq = self.create_sequences(
            X_val.values, y_val.values, self.lookback
        )
        
        # Convert to tensors
        train_dataset = TensorDataset(
            torch.FloatTensor(X_train_seq),
            torch.FloatTensor(y_train_seq).unsqueeze(1)
        )
        val_dataset = TensorDataset(
            torch.FloatTensor(X_val_seq),
            torch.FloatTensor(y_val_seq).unsqueeze(1)
        )
        
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=False)
        val_loader = DataLoader(val_dataset, batch_size=batch_size)
        
        # Loss and optimizer
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5)
        
        best_val_loss = float('inf')
        
        for epoch in range(epochs):
            # Training
            self.model.train()
            train_loss = 0
            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)
                
                optimizer.zero_grad()
                outputs = self.model(X_batch)
                loss = criterion(outputs, y_batch)
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
            
            # Validation
            self.model.eval()
            val_loss = 0
            with torch.no_grad():
                for X_batch, y_batch in val_loader:
                    X_batch = X_batch.to(self.device)
                    y_batch = y_batch.to(self.device)
                    outputs = self.model(X_batch)
                    loss = criterion(outputs, y_batch)
                    val_loss += loss.item()
            
            train_loss /= len(train_loader)
            val_loss /= len(val_loader)
            
            scheduler.step(val_loss)
            
            if epoch % 10 == 0:
                print(f"Epoch {epoch}: Train={train_loss:.6f}, Val={val_loss:.6f}")
            
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                torch.save(self.model.state_dict(), 'best_lstm_model.pth')
        
        self.model.load_state_dict(torch.load('best_lstm_model.pth'))
    
    def predict(self, X):
        """Predict future values"""
        X_seq, _ = self.create_sequences(X.values, np.zeros(len(X)), self.lookback)
        
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X_seq).to(self.device)
            predictions = self.model(X_tensor).cpu().numpy().flatten()
        
        # Pad predictions to match original length
        predictions = np.concatenate([np.full(self.lookback, np.nan), predictions])
        
        return predictions
```

---

## 🎭 Model 4: Ensemble Meta-Model

### Stacking Classifier

```python
# models/ensemble.py

from sklearn.ensemble import StackingClassifier, StackingRegressor
from sklearn.linear_model import LogisticRegression, Ridge

class EnsembleModel:
    """
    Ensemble model that combines predictions from multiple models
    """
    
    def __init__(self, base_classifiers, base_regressors):
        """
        base_classifiers: List of (name, model) tuples for classification
        base_regressors: List of (name, model) tuples for regression
        """
        
        # Stacking Classifier
        self.stacking_classifier = StackingClassifier(
            estimators=base_classifiers,
            final_estimator=LogisticRegression(max_iter=1000),
            cv=5,
            stack_method='predict_proba'
        )
        
        # Stacking Regressor
        self.stacking_regressor = StackingRegressor(
            estimators=base_regressors,
            final_estimator=Ridge(alpha=1.0),
            cv=5
        )
    
    def train_classifier(self, X_train, y_train):
        """Train ensemble classifier"""
        print("Training ensemble classifier...")
        self.stacking_classifier.fit(X_train, y_train)
        print("Ensemble classifier trained!")
        
    def train_regressor(self, X_train, y_train):
        """Train ensemble regressor"""
        print("Training ensemble regressor...")
        self.stacking_regressor.fit(X_train, y_train)
        print("Ensemble regressor trained!")
    
    def predict_signal(self, X):
        """Predict entry signal (classification)"""
        return self.stacking_classifier.predict(X)
    
    def predict_signal_proba(self, X):
        """Predict signal probabilities"""
        return self.stacking_classifier.predict_proba(X)
    
    def predict_target(self, X):
        """Predict price target (regression)"""
        return self.stacking_regressor.predict(X)
    
    def get_trading_decision(self, X):
        """
        Get complete trading decision with confidence
        
        Returns:
            signal: 0 (SHORT), 1 (NEUTRAL), 2 (LONG)
            confidence: probability of predicted class
            target: predicted return
        """
        signal_proba = self.predict_signal_proba(X)
        signal = np.argmax(signal_proba, axis=1)
        confidence = np.max(signal_proba, axis=1)
        target = self.predict_target(X)
        
        return {
            'signal': signal,
            'confidence': confidence,
            'target': target,
            'signal_proba': signal_proba
        }
```

---

## 📊 Walk-Forward Validation

```python
# validation/walk_forward.py

from sklearn.model_selection import TimeSeriesSplit
import pandas as pd

class WalkForwardValidator:
    """
    Walk-forward validation for time-series models
    """
    
    def __init__(self, n_splits=5):
        self.n_splits = n_splits
        self.tscv = TimeSeriesSplit(n_splits=n_splits)
        
    def validate(self, model, X, y):
        """
        Perform walk-forward validation
        
        Returns performance metrics for each fold
        """
        fold_metrics = []
        
        for fold, (train_idx, test_idx) in enumerate(self.tscv.split(X)):
            print(f"\n--- Fold {fold + 1}/{self.n_splits} ---")
            
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            # Train model on this fold
            model.train(X_train, y_train, X_test, y_test)
            
            # Evaluate
            metrics = model.evaluate(X_test, y_test)
            metrics['fold'] = fold
            metrics['train_size'] = len(train_idx)
            metrics['test_size'] = len(test_idx)
            
            fold_metrics.append(metrics)
            
            print(f"Fold {fold + 1} Accuracy: {metrics.get('accuracy', 'N/A')}")
        
        # Aggregate results
        results_df = pd.DataFrame(fold_metrics)
        
        print("\n" + "="*60)
        print("WALK-FORWARD VALIDATION RESULTS")
        print("="*60)
        print(results_df[['fold', 'accuracy', 'directional_accuracy']].to_string())
        print(f"\nMean Accuracy: {results_df['accuracy'].mean():.4f} ± {results_df['accuracy'].std():.4f}")
        
        return results_df
```

---

## 🔍 Model Interpretability with SHAP

```python
# interpretability/shap_analysis.py

import shap
import matplotlib.pyplot as plt

class ModelInterpreter:
    """
    Analyze and visualize model decisions using SHAP
    """
    
    def __init__(self, model, X_train):
        """
        Initialize SHAP explainer
        """
        if hasattr(model, 'model'):  # XGBoost/LightGBM wrapper
            self.explainer = shap.TreeExplainer(model.model)
        else:
            self.explainer = shap.Explainer(model, X_train)
        
        self.X_train = X_train
        
    def explain_predictions(self, X_test, max_display=20):
        """
        Generate SHAP values and visualizations
        """
        # Calculate SHAP values
        shap_values = self.explainer.shap_values(X_test)
        
        # Summary plot (feature importance)
        plt.figure(figsize=(10, 8))
        shap.summary_plot(
            shap_values, 
            X_test, 
            max_display=max_display,
            show=False
        )
        plt.title("SHAP Feature Importance")
        plt.tight_layout()
        plt.savefig('shap_summary.png', dpi=300)
        plt.close()
        
        # Feature importance bar plot
        plt.figure(figsize=(10, 8))
        shap.summary_plot(
            shap_values, 
            X_test, 
            plot_type="bar",
            max_display=max_display,
            show=False
        )
        plt.title("SHAP Feature Importance (Bar)")
        plt.tight_layout()
        plt.savefig('shap_importance_bar.png', dpi=300)
        plt.close()
        
        # Get feature importance dataframe
        if isinstance(shap_values, list):  # Multi-class
            # Average across classes
            shap_values_avg = np.abs(shap_values).mean(axis=0)
        else:
            shap_values_avg = shap_values
        
        feature_importance = pd.DataFrame({
            'feature': X_test.columns,
            'importance': np.abs(shap_values_avg).mean(axis=0)
        }).sort_values('importance', ascending=False)
        
        return feature_importance
    
    def explain_single_prediction(self, X_instance, class_idx=None):
        """
        Explain a single prediction with force plot
        """
        shap_values = self.explainer.shap_values(X_instance)
        
        if isinstance(shap_values, list):  # Multi-class
            if class_idx is None:
                class_idx = np.argmax(shap_values, axis=0).flatten()[0]
            shap_values = shap_values[class_idx]
        
        shap.force_plot(
            self.explainer.expected_value[class_idx] if isinstance(self.explainer.expected_value, np.ndarray) else self.explainer.expected_value,
            shap_values[0],
            X_instance.iloc[0],
            matplotlib=True,
            show=False
        )
        plt.savefig('shap_force_plot.png', dpi=300, bbox_inches='tight')
        plt.close()
```

---

## 🎯 Complete Training Pipeline

```python
# training/pipeline.py

import joblib

class MLTrainingPipeline:
    """
    Complete ML training pipeline
    """
    
    def __init__(self):
        self.models = {}
        self.ensemble = None
        
    def run_full_pipeline(
        self,
        X_train, y_train_class, y_train_reg,
        X_val, y_val_class, y_val_reg,
        X_test, y_test_class, y_test_reg
    ):
        """
        Run complete training pipeline
        """
        
        print("="*60)
        print("STARTING ML TRAINING PIPELINE")
        print("="*60)
        
        # 1. Train classifiers
        print("\n[1/5] Training Classification Models...")
        self.train_classifiers(X_train, y_train_class, X_val, y_val_class)
        
        # 2. Train regressors
        print("\n[2/5] Training Regression Models...")
        self.train_regressors(X_train, y_train_reg, X_val, y_val_reg)
        
        # 3. Train LSTM
        print("\n[3/5] Training LSTM Models...")
        self.train_lstm(X_train, y_train_reg, X_val, y_val_reg)
        
        # 4. Build ensemble
        print("\n[4/5] Building Ensemble Model...")
        self.build_ensemble(X_train, y_train_class, y_train_reg)
        
        # 5. Final evaluation on test set
        print("\n[5/5] Final Evaluation on Test Set...")
        self.evaluate_all_models(X_test, y_test_class, y_test_reg)
        
        # 6. Save models
        print("\n[6/6] Saving Models...")
        self.save_models()
        
        print("\n" + "="*60)
        print("✅ TRAINING PIPELINE COMPLETE!")
        print("="*60)
    
    def train_classifiers(self, X_train, y_train, X_val, y_val):
        """Train all classification models"""
        
        # XGBoost
        print("\nTraining XGBoost Classifier...")
        xgb_clf = XGBoostEntryPredictor()
        xgb_clf.train(X_train, y_train, X_val, y_val)
        self.models['xgb_classifier'] = xgb_clf
        
        # LightGBM
        print("\nTraining LightGBM Classifier...")
        lgb_clf = LightGBMEntryPredictor()
        lgb_clf.train(X_train, y_train, X_val, y_val)
        self.models['lgb_classifier'] = lgb_clf
        
        # CatBoost
        print("\nTraining CatBoost Classifier...")
        cat_clf = CatBoostEntryPredictor()
        cat_clf.train(X_train, y_train, X_val, y_val)
        self.models['cat_classifier'] = cat_clf
    
    def train_regressors(self, X_train, y_train, X_val, y_val):
        """Train all regression models"""
        
        # XGBoost Regressor
        print("\nTraining XGBoost Regressor...")
        xgb_reg = XGBoostPricePredictor()
        xgb_reg.train(X_train, y_train, X_val, y_val)
        self.models['xgb_regressor'] = xgb_reg
        
        # Neural Network
        print("\nTraining Neural Network Regressor...")
        nn_reg = NeuralNetTrainer(input_dim=X_train.shape[1])
        nn_reg.train(X_train, y_train, X_val, y_val, epochs=100)
        self.models['nn_regressor'] = nn_reg
    
    def train_lstm(self, X_train, y_train, X_val, y_val):
        """Train LSTM models"""
        
        print("\nTraining LSTM Forecaster...")
        lstm = LSTMTrainer(input_dim=X_train.shape[1], lookback=50)
        lstm.train(X_train, y_train, X_val, y_val, epochs=50)
        self.models['lstm'] = lstm
    
    def build_ensemble(self, X_train, y_train_class, y_train_reg):
        """Build ensemble model"""
        
        base_classifiers = [
            ('xgb', self.models['xgb_classifier'].model),
            ('lgb', self.models['lgb_classifier'].model),
            ('cat', self.models['cat_classifier'].model)
        ]
        
        base_regressors = [
            ('xgb', self.models['xgb_regressor'].model),
            ('nn', self.models['nn_regressor'].model)
        ]
        
        self.ensemble = EnsembleModel(base_classifiers, base_regressors)
        self.ensemble.train_classifier(X_train, y_train_class)
        self.ensemble.train_regressor(X_train, y_train_reg)
    
    def evaluate_all_models(self, X_test, y_test_class, y_test_reg):
        """Evaluate all models on test set"""
        
        results = {}
        
        # Classification models
        for name in ['xgb_classifier', 'lgb_classifier', 'cat_classifier']:
            metrics = self.models[name].evaluate(X_test, y_test_class)
            results[name] = metrics['accuracy']
            print(f"{name}: Accuracy = {metrics['accuracy']:.4f}")
        
        # Ensemble
        y_pred = self.ensemble.predict_signal(X_test)
        ensemble_acc = (y_pred == y_test_class).mean()
        results['ensemble'] = ensemble_acc
        print(f"Ensemble: Accuracy = {ensemble_acc:.4f}")
        
        return results
    
    def save_models(self):
        """Save all trained models"""
        
        # Save sklearn-compatible models
        joblib.dump(self.models['xgb_classifier'].model, 'xgb_classifier.pkl')
        joblib.dump(self.models['xgb_regressor'].model, 'xgb_regressor.pkl')
        joblib.dump(self.ensemble, 'ensemble_model.pkl')
        
        # PyTorch models already saved during training
        
        print("✅ All models saved!")
```

---

## ✅ Phase 3 Deliverables Checklist

- [ ] XGBoost classifier trained (accuracy > 55%)
- [ ] LightGBM classifier trained
- [ ] CatBoost classifier trained
- [ ] XGBoost regressor trained (directional accuracy > 55%)
- [ ] Neural Network regressor trained
- [ ] LSTM forecaster trained
- [ ] Ensemble meta-model built
- [ ] Hyperparameter optimization completed (Optuna)
- [ ] Walk-forward validation performed (5 folds)
- [ ] SHAP interpretability analysis done
- [ ] All models saved to disk
- [ ] Performance report generated

---

## 🎯 Expected Performance Targets

| Model | Metric | Target |
|-------|--------|--------|
| **XGBoost Classifier** | Accuracy | > 55% |
| | Directional Accuracy (excl. NEUTRAL) | > 60% |
| **Ensemble Classifier** | Accuracy | > 58% |
| **XGBoost Regressor** | Directional Accuracy | > 58% |
| | R² Score | > 0.10 |
| **LSTM** | RMSE | < 0.015 |
| | Directional Accuracy | > 55% |

---

## 🚀 Next Phase

**Phase 4: RL Execution Engine**

Now that we have predictive models, we'll train a Reinforcement Learning agent that:
- Uses ML predictions as part of its state
- Learns optimal entry/exit timing
- Manages position sizing dynamically
- Adapts to market conditions

Ready for advanced AI? 🤖
