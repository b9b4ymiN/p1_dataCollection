# Phase 4: Reinforcement Learning Execution Engine
## Training an Autonomous Trading Agent

**Duration:** Week 8-10  
**Goal:** Build and train an RL agent that makes optimal trading decisions using ML predictions

---

## 🎯 Phase Objectives

1. ✅ Design RL environment (OpenAI Gym compatible)
2. ✅ Define state space (market conditions + ML signals)
3. ✅ Define action space (Entry/Exit/Hold/Scale)
4. ✅ Design reward function (risk-adjusted PnL)
5. ✅ Train PPO/A2C agent with Stable-Baselines3
6. ✅ Backtest RL agent performance
7. ✅ Compare RL vs Fixed-Rule baseline

---

## 🏗️ RL Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    MARKET STATE                          │
│  • Current Position                                      │
│  • ML Predictions (signal, confidence, target)          │
│  • OI Signals (divergence, momentum)                    │
│  • Price Action (RSI, ATR, trend)                       │
│  • Account Status (PnL, equity, drawdown)               │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
            ┌────────────────────────┐
            │   RL AGENT (PPO/A2C)   │
            │                        │
            │  Neural Network Policy │
            │  • Actor (Action)      │
            │  • Critic (Value)      │
            └────────────┬───────────┘
                         │
                         ▼
            ┌────────────────────────┐
            │   ACTION SELECTION     │
            │  • HOLD                │
            │  • ENTER_LONG          │
            │  • ENTER_SHORT         │
            │  • EXIT_POSITION       │
            │  • SCALE_IN            │
            │  • SCALE_OUT           │
            └────────────┬───────────┘
                         │
                         ▼
            ┌────────────────────────┐
            │   EXECUTE IN MARKET    │
            └────────────┬───────────┘
                         │
                         ▼
            ┌────────────────────────┐
            │   COMPUTE REWARD       │
            │  • PnL                 │
            │  • Risk Penalty        │
            │  • Transaction Costs   │
            │  • Sharpe Improvement  │
            └────────────┬───────────┘
                         │
                         ▼
            ┌────────────────────────┐
            │   UPDATE POLICY        │
            │  (Learn from feedback) │
            └────────────────────────┘
```

---

## 🌍 Trading Environment Design

### Custom Gym Environment

```python
# rl/trading_env.py

import gym
from gym import spaces
import numpy as np
import pandas as pd
from typing import Dict, Tuple

class FuturesTradingEnv(gym.Env):
    """
    Custom OpenAI Gym environment for Futures trading with OI signals
    """
    
    metadata = {'render.modes': ['human']}
    
    def __init__(
        self,
        df: pd.DataFrame,
        ml_predictions: pd.DataFrame,
        initial_balance: float = 2000.0,
        leverage: float = 5.0,
        fee_rate: float = 0.0004,
        slippage: float = 0.0002
    ):
        super(FuturesTradingEnv, self).__init__()
        
        self.df = df.reset_index(drop=True)
        self.ml_predictions = ml_predictions.reset_index(drop=True)
        self.initial_balance = initial_balance
        self.leverage = leverage
        self.fee_rate = fee_rate
        self.slippage = slippage
        
        # Episode tracking
        self.current_step = 0
        self.max_steps = len(df) - 1
        
        # Trading state
        self.balance = initial_balance
        self.equity = initial_balance
        self.position = 0  # 0 = flat, 1 = long, -1 = short
        self.entry_price = 0
        self.position_size = 0  # in contracts
        self.unrealized_pnl = 0
        self.realized_pnl = 0
        self.total_pnl = 0
        
        # Risk tracking
        self.max_equity = initial_balance
        self.drawdown = 0
        self.max_drawdown = 0
        
        # Trade tracking
        self.trades = []
        self.current_trade_duration = 0
        self.total_trades = 0
        self.winning_trades = 0
        
        # Performance tracking
        self.equity_curve = [initial_balance]
        self.sharpe_window = []
        
        # Define action space
        # 0: HOLD
        # 1: ENTER_LONG
        # 2: ENTER_SHORT
        # 3: EXIT_POSITION
        # 4: SCALE_IN (increase position by 50%)
        # 5: SCALE_OUT (decrease position by 50%)
        self.action_space = spaces.Discrete(6)
        
        # Define observation space (state)
        # We'll have ~20 key features
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(20,),
            dtype=np.float32
        )
    
    def reset(self) -> np.ndarray:
        """Reset environment to initial state"""
        self.current_step = 50  # Start after enough history for indicators
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.position = 0
        self.entry_price = 0
        self.position_size = 0
        self.unrealized_pnl = 0
        self.realized_pnl = 0
        self.total_pnl = 0
        
        self.max_equity = self.initial_balance
        self.drawdown = 0
        self.max_drawdown = 0
        
        self.trades = []
        self.current_trade_duration = 0
        self.total_trades = 0
        self.winning_trades = 0
        
        self.equity_curve = [self.initial_balance]
        self.sharpe_window = []
        
        return self._get_observation()
    
    def _get_observation(self) -> np.ndarray:
        """
        Get current state observation
        
        State includes:
        - Position status (3 features)
        - ML predictions (3 features)
        - Market conditions (8 features)
        - Account status (6 features)
        """
        row = self.df.iloc[self.current_step]
        ml_pred = self.ml_predictions.iloc[self.current_step]
        
        # Position status
        position_encoding = self.position  # -1, 0, 1
        position_pnl_pct = self.unrealized_pnl / self.equity if self.equity > 0 else 0
        time_in_position_norm = min(self.current_trade_duration / 100, 1.0)
        
        # ML predictions (from Phase 3 models)
        ml_signal = ml_pred.get('signal', 1) - 1  # Convert 0,1,2 to -1,0,1
        ml_confidence = ml_pred.get('confidence', 0.5)
        ml_target = ml_pred.get('target', 0)
        
        # Market conditions
        price_momentum = row.get('return_20', 0)
        volatility = row.get('natr', 0.02)
        rsi = row.get('rsi_14', 50) / 100  # Normalize to [0, 1]
        oi_divergence = row.get('oi_price_divergence_20', 0)
        oi_change = row.get('oi_change_20', 0)
        funding_rate = row.get('funding_rate', 0) * 100  # Scale up
        volume_ratio = row.get('volume_ratio', 1)
        bb_position = row.get('bb_position', 0.5)
        
        # Account status
        equity_ratio = self.equity / self.initial_balance
        drawdown_pct = self.drawdown
        balance_ratio = self.balance / self.initial_balance
        
        # Recent Sharpe (rolling)
        recent_sharpe = self._calculate_recent_sharpe()
        
        # Distance to liquidation (if in position)
        distance_to_liq = self._calculate_liquidation_distance()
        
        # Win rate
        win_rate = self.winning_trades / max(self.total_trades, 1)
        
        # Construct observation vector
        obs = np.array([
            # Position (3)
            position_encoding,
            position_pnl_pct,
            time_in_position_norm,
            
            # ML Predictions (3)
            ml_signal,
            ml_confidence,
            ml_target,
            
            # Market Conditions (8)
            price_momentum,
            volatility,
            rsi,
            oi_divergence,
            oi_change,
            funding_rate,
            volume_ratio,
            bb_position,
            
            # Account Status (6)
            equity_ratio,
            drawdown_pct,
            balance_ratio,
            recent_sharpe,
            distance_to_liq,
            win_rate
        ], dtype=np.float32)
        
        # Clip extreme values
        obs = np.clip(obs, -10, 10)
        
        return obs
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        Execute action and return next state
        
        Returns:
            observation: next state
            reward: reward for this action
            done: whether episode is finished
            info: additional information
        """
        current_price = self.df.iloc[self.current_step]['close']
        
        # Execute action
        action_executed = self._execute_action(action, current_price)
        
        # Move to next step
        self.current_step += 1
        
        # Update unrealized PnL if in position
        if self.position != 0:
            self._update_unrealized_pnl()
            self.current_trade_duration += 1
        
        # Update equity and drawdown
        self.equity = self.balance + self.unrealized_pnl
        self.equity_curve.append(self.equity)
        
        if self.equity > self.max_equity:
            self.max_equity = self.equity
            self.drawdown = 0
        else:
            self.drawdown = (self.max_equity - self.equity) / self.max_equity
            self.max_drawdown = max(self.max_drawdown, self.drawdown)
        
        # Calculate reward
        reward = self._calculate_reward(action_executed)
        
        # Check if episode done
        done = self.current_step >= self.max_steps or self.equity <= self.initial_balance * 0.5
        
        # Get next observation
        next_obs = self._get_observation()
        
        # Info
        info = {
            'equity': self.equity,
            'position': self.position,
            'total_pnl': self.total_pnl,
            'total_trades': self.total_trades,
            'win_rate': self.winning_trades / max(self.total_trades, 1),
            'max_drawdown': self.max_drawdown
        }
        
        return next_obs, reward, done, info
    
    def _execute_action(self, action: int, current_price: float) -> bool:
        """
        Execute trading action
        
        Returns True if action was executed
        """
        executed = False
        
        if action == 0:  # HOLD
            pass
        
        elif action == 1:  # ENTER_LONG
            if self.position == 0:
                self._open_position(1, current_price)
                executed = True
        
        elif action == 2:  # ENTER_SHORT
            if self.position == 0:
                self._open_position(-1, current_price)
                executed = True
        
        elif action == 3:  # EXIT_POSITION
            if self.position != 0:
                self._close_position(current_price)
                executed = True
        
        elif action == 4:  # SCALE_IN
            if self.position != 0:
                self._scale_position(1.5, current_price)
                executed = True
        
        elif action == 5:  # SCALE_OUT
            if self.position != 0:
                self._scale_position(0.5, current_price)
                executed = True
        
        return executed
    
    def _open_position(self, direction: int, price: float):
        """Open new position"""
        # Position sizing: 2% risk per trade
        risk_per_trade = self.equity * 0.02
        atr = self.df.iloc[self.current_step].get('atr_14', price * 0.02)
        stop_distance = 1.5 * atr
        
        # Calculate position size
        position_value = (risk_per_trade / (stop_distance / price)) * self.leverage
        position_value = min(position_value, self.equity * self.leverage * 0.5)  # Max 50% of capital
        
        self.position_size = position_value / price
        self.position = direction
        self.entry_price = price * (1 + self.slippage * direction)  # Slippage
        self.current_trade_duration = 0
        
        # Deduct fees
        fee = position_value * self.fee_rate
        self.balance -= fee
        
        self.total_trades += 1
    
    def _close_position(self, price: float):
        """Close current position"""
        if self.position == 0:
            return
        
        # Calculate PnL
        exit_price = price * (1 - self.slippage * self.position)
        pnl = self.position_size * (exit_price - self.entry_price) * self.position
        
        # Deduct fees
        position_value = self.position_size * price
        fee = position_value * self.fee_rate
        
        net_pnl = pnl - fee
        
        # Update balance
        self.balance += net_pnl
        self.realized_pnl += net_pnl
        self.total_pnl += net_pnl
        
        # Track winning trades
        if net_pnl > 0:
            self.winning_trades += 1
        
        # Record trade
        self.trades.append({
            'entry_price': self.entry_price,
            'exit_price': exit_price,
            'direction': self.position,
            'size': self.position_size,
            'pnl': net_pnl,
            'duration': self.current_trade_duration,
            'exit_step': self.current_step
        })
        
        # Reset position
        self.position = 0
        self.entry_price = 0
        self.position_size = 0
        self.unrealized_pnl = 0
        self.current_trade_duration = 0
    
    def _scale_position(self, scale_factor: float, price: float):
        """Scale position up or down"""
        new_size = self.position_size * scale_factor
        size_change = new_size - self.position_size
        
        # Update entry price (weighted average)
        if size_change > 0:  # Scaling in
            total_value_old = self.position_size * self.entry_price
            total_value_new = size_change * price
            self.entry_price = (total_value_old + total_value_new) / new_size
        
        self.position_size = new_size
        
        # Deduct fees
        fee = abs(size_change * price) * self.fee_rate
        self.balance -= fee
    
    def _update_unrealized_pnl(self):
        """Update unrealized PnL for open position"""
        if self.position == 0:
            self.unrealized_pnl = 0
            return
        
        current_price = self.df.iloc[self.current_step]['close']
        self.unrealized_pnl = self.position_size * (current_price - self.entry_price) * self.position
    
    def _calculate_reward(self, action_executed: bool) -> float:
        """
        Calculate reward for this step
        
        Reward components:
        1. PnL change
        2. Risk penalty (volatility, drawdown)
        3. Transaction cost penalty
        4. Sharpe improvement bonus
        """
        # Base reward: Change in equity
        equity_change = self.equity_curve[-1] - self.equity_curve[-2] if len(self.equity_curve) > 1 else 0
        reward = equity_change / self.initial_balance * 100  # Normalize
        
        # Penalty for high drawdown
        drawdown_penalty = -self.drawdown * 5
        
        # Penalty for excessive volatility (if in position)
        if self.position != 0:
            volatility = self.df.iloc[self.current_step].get('natr', 0.02)
            volatility_penalty = -volatility * 2
        else:
            volatility_penalty = 0
        
        # Penalty for holding too long
        if self.current_trade_duration > 50:  # More than 50 periods
            duration_penalty = -0.1
        else:
            duration_penalty = 0
        
        # Penalty for transaction if action was executed
        if action_executed:
            transaction_penalty = -0.05
        else:
            transaction_penalty = 0
        
        # Bonus for improving Sharpe ratio
        sharpe_bonus = 0
        if len(self.sharpe_window) > 10:
            current_sharpe = self._calculate_recent_sharpe()
            if current_sharpe > 0.5:
                sharpe_bonus = 0.2
        
        # Penalty if approaching liquidation
        if self.position != 0:
            distance_to_liq = self._calculate_liquidation_distance()
            if distance_to_liq < 0.15:  # Within 15%
                liq_penalty = -1.0
            else:
                liq_penalty = 0
        else:
            liq_penalty = 0
        
        # Total reward
        total_reward = (
            reward +
            drawdown_penalty +
            volatility_penalty +
            duration_penalty +
            transaction_penalty +
            sharpe_bonus +
            liq_penalty
        )
        
        return total_reward
    
    def _calculate_liquidation_distance(self) -> float:
        """
        Calculate distance to liquidation price
        
        Returns percentage distance (0 = at liquidation, 1 = far away)
        """
        if self.position == 0:
            return 1.0
        
        current_price = self.df.iloc[self.current_step]['close']
        
        # Simplified liquidation calculation
        margin = (self.position_size * self.entry_price) / self.leverage
        maintenance_margin = margin * 0.5  # 50% of initial margin
        
        if self.position == 1:  # Long
            liq_price = self.entry_price * (1 - (margin - maintenance_margin) / (self.position_size * self.entry_price))
            distance = (current_price - liq_price) / current_price
        else:  # Short
            liq_price = self.entry_price * (1 + (margin - maintenance_margin) / (self.position_size * self.entry_price))
            distance = (liq_price - current_price) / current_price
        
        return max(0, min(1, distance))
    
    def _calculate_recent_sharpe(self, window=20) -> float:
        """Calculate recent Sharpe ratio"""
        if len(self.equity_curve) < window + 1:
            return 0
        
        recent_equity = self.equity_curve[-window:]
        returns = np.diff(recent_equity) / recent_equity[:-1]
        
        if len(returns) == 0 or returns.std() == 0:
            return 0
        
        sharpe = returns.mean() / returns.std() * np.sqrt(252 * 288)  # Annualized (5m data)
        
        return sharpe
    
    def render(self, mode='human'):
        """Render environment state"""
        if mode == 'human':
            print(f"Step: {self.current_step}/{self.max_steps}")
            print(f"Equity: ${self.equity:.2f}")
            print(f"Position: {self.position}")
            print(f"Total PnL: ${self.total_pnl:.2f}")
            print(f"Trades: {self.total_trades} (Win Rate: {self.winning_trades/max(self.total_trades, 1):.2%})")
            print(f"Max DD: {self.max_drawdown:.2%}")
            print("-" * 40)
```

---

## 🤖 RL Agent Training

### PPO (Proximal Policy Optimization)

```python
# rl/train_agent.py

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import EvalCallback, CheckpointCallback
import torch

class RLAgentTrainer:
    """
    Train RL agent using PPO algorithm
    """
    
    def __init__(self, env: FuturesTradingEnv):
        self.env = env
        self.model = None
        
    def train(
        self,
        total_timesteps: int = 1_000_000,
        eval_freq: int = 10000,
        save_path: str = "./models/ppo_agent"
    ):
        """
        Train PPO agent
        """
        # Wrap environment
        vec_env = DummyVecEnv([lambda: self.env])
        
        # Create evaluation environment
        eval_env = DummyVecEnv([lambda: FuturesTradingEnv(
            self.env.df,
            self.env.ml_predictions,
            initial_balance=self.env.initial_balance,
            leverage=self.env.leverage
        )])
        
        # Callbacks
        eval_callback = EvalCallback(
            eval_env,
            best_model_save_path=save_path,
            log_path='./logs/',
            eval_freq=eval_freq,
            deterministic=True,
            render=False
        )
        
        checkpoint_callback = CheckpointCallback(
            save_freq=50000,
            save_path=save_path,
            name_prefix='ppo_checkpoint'
        )
        
        # Create PPO model
        self.model = PPO(
            policy='MlpPolicy',
            env=vec_env,
            learning_rate=3e-4,
            n_steps=2048,
            batch_size=64,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.01,
            vf_coef=0.5,
            max_grad_norm=0.5,
            verbose=1,
            tensorboard_log='./tensorboard/',
            device='cuda' if torch.cuda.is_available() else 'cpu'
        )
        
        # Train
        print("Starting PPO training...")
        self.model.learn(
            total_timesteps=total_timesteps,
            callback=[eval_callback, checkpoint_callback]
        )
        
        print("Training complete!")
        self.model.save(f"{save_path}/final_model")
        
        return self.model
    
    def load_model(self, path: str):
        """Load trained model"""
        self.model = PPO.load(path)
        return self.model
    
    def evaluate(self, n_episodes: int = 100):
        """
        Evaluate trained agent
        """
        episode_rewards = []
        episode_lengths = []
        final_equities = []
        
        for episode in range(n_episodes):
            obs = self.env.reset()
            done = False
            episode_reward = 0
            episode_length = 0
            
            while not done:
                action, _states = self.model.predict(obs, deterministic=True)
                obs, reward, done, info = self.env.step(action)
                episode_reward += reward
                episode_length += 1
            
            episode_rewards.append(episode_reward)
            episode_lengths.append(episode_length)
            final_equities.append(info['equity'])
        
        # Calculate metrics
        avg_reward = np.mean(episode_rewards)
        avg_length = np.mean(episode_lengths)
        avg_equity = np.mean(final_equities)
        win_rate = np.mean([e > self.env.initial_balance for e in final_equities])
        
        print("\n" + "="*60)
        print("RL AGENT EVALUATION")
        print("="*60)
        print(f"Episodes: {n_episodes}")
        print(f"Average Reward: {avg_reward:.2f}")
        print(f"Average Episode Length: {avg_length:.0f}")
        print(f"Average Final Equity: ${avg_equity:.2f}")
        print(f"Win Rate: {win_rate:.2%}")
        print("="*60)
        
        return {
            'avg_reward': avg_reward,
            'avg_equity': avg_equity,
            'win_rate': win_rate
        }
```

### Alternative: A2C (Advantage Actor-Critic)

```python
# rl/a2c_agent.py

from stable_baselines3 import A2C

class A2CAgentTrainer:
    """
    Train RL agent using A2C algorithm (faster than PPO)
    """
    
    def __init__(self, env: FuturesTradingEnv):
        self.env = env
        self.model = None
        
    def train(self, total_timesteps: int = 500_000):
        """Train A2C agent"""
        
        vec_env = DummyVecEnv([lambda: self.env])
        
        self.model = A2C(
            policy='MlpPolicy',
            env=vec_env,
            learning_rate=7e-4,
            n_steps=5,
            gamma=0.99,
            gae_lambda=1.0,
            ent_coef=0.01,
            vf_coef=0.5,
            max_grad_norm=0.5,
            verbose=1,
            tensorboard_log='./tensorboard/'
        )
        
        print("Starting A2C training...")
        self.model.learn(total_timesteps=total_timesteps)
        
        self.model.save("./models/a2c_agent")
        
        return self.model
```

---

## 📊 RL Agent Backtesting

```python
# backtesting/rl_backtest.py

import pandas as pd
import matplotlib.pyplot as plt

class RLBacktester:
    """
    Backtest RL agent on historical data
    """
    
    def __init__(self, agent, env: FuturesTradingEnv):
        self.agent = agent
        self.env = env
        
    def run_backtest(self) -> Dict:
        """
        Run full backtest
        """
        obs = self.env.reset()
        done = False
        
        # Tracking
        equity_curve = []
        actions_taken = []
        timestamps = []
        
        step = 0
        while not done:
            # Get agent action
            action, _states = self.agent.predict(obs, deterministic=True)
            
            # Execute action
            obs, reward, done, info = self.env.step(action)
            
            # Track
            equity_curve.append(info['equity'])
            actions_taken.append(action)
            timestamps.append(self.env.df.iloc[self.env.current_step]['timestamp'])
            
            step += 1
        
        # Get all trades
        trades_df = pd.DataFrame(self.env.trades)
        
        # Calculate metrics
        metrics = self._calculate_metrics(equity_curve, trades_df)
        
        # Visualize
        self._plot_results(timestamps, equity_curve, actions_taken, trades_df)
        
        return {
            'metrics': metrics,
            'trades': trades_df,
            'equity_curve': equity_curve
        }
    
    def _calculate_metrics(self, equity_curve, trades_df) -> Dict:
        """Calculate performance metrics"""
        
        equity_series = pd.Series(equity_curve)
        returns = equity_series.pct_change().dropna()
        
        # Total return
        total_return = (equity_curve[-1] - self.env.initial_balance) / self.env.initial_balance
        
        # Sharpe ratio (annualized)
        sharpe = returns.mean() / returns.std() * np.sqrt(252 * 288) if returns.std() > 0 else 0
        
        # Max drawdown
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax
        max_dd = drawdown.min()
        
        # Win rate
        if len(trades_df) > 0:
            win_rate = (trades_df['pnl'] > 0).mean()
            avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean()
            avg_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].mean())
            profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
        else:
            win_rate = 0
            profit_factor = 0
        
        # Calmar ratio
        calmar = total_return / abs(max_dd) if max_dd != 0 else 0
        
        return {
            'total_return': total_return,
            'final_equity': equity_curve[-1],
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'calmar_ratio': calmar,
            'total_trades': len(trades_df),
            'win_rate': win_rate,
            'profit_factor': profit_factor
        }
    
    def _plot_results(self, timestamps, equity_curve, actions, trades_df):
        """Plot backtest results"""
        
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 12))
        
        # Equity curve
        ax1.plot(timestamps, equity_curve, linewidth=2)
        ax1.axhline(y=self.env.initial_balance, color='r', linestyle='--', label='Initial Balance')
        ax1.set_title('Equity Curve', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Equity ($)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Drawdown
        equity_series = pd.Series(equity_curve)
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax
        
        ax2.fill_between(range(len(drawdown)), drawdown, 0, alpha=0.3, color='red')
        ax2.set_title('Drawdown', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Drawdown (%)')
        ax2.grid(True, alpha=0.3)
        
        # Action distribution
        action_counts = pd.Series(actions).value_counts().sort_index()
        action_labels = ['HOLD', 'LONG', 'SHORT', 'EXIT', 'SCALE_IN', 'SCALE_OUT']
        
        ax3.bar(action_counts.index, action_counts.values)
        ax3.set_title('Action Distribution', fontsize=14, fontweight='bold')
        ax3.set_xlabel('Action')
        ax3.set_ylabel('Count')
        ax3.set_xticks(range(6))
        ax3.set_xticklabels(action_labels, rotation=45)
        ax3.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('rl_backtest_results.png', dpi=300)
        plt.close()
        
        print("✅ Backtest visualization saved!")
```

---

## 📈 Compare RL vs Fixed-Rule Baseline

```python
# comparison/baseline_strategy.py

class BaselineStrategy:
    """
    Fixed-rule baseline strategy for comparison
    """
    
    def __init__(self, df, ml_predictions):
        self.df = df
        self.ml_predictions = ml_predictions
        
    def generate_signals(self):
        """
        Generate entry/exit signals using fixed rules
        
        Rules:
        - LONG: ML signal = 2 AND confidence > 0.6 AND OI divergence > 0
        - SHORT: ML signal = 0 AND confidence > 0.6 AND OI divergence < 0
        - EXIT: Position held > 20 periods OR PnL > 1% OR PnL < -0.5%
        """
        signals = []
        
        for i in range(len(self.df)):
            ml_sig = self.ml_predictions.iloc[i]['signal']
            ml_conf = self.ml_predictions.iloc[i]['confidence']
            oi_div = self.df.iloc[i].get('oi_price_divergence_20', 0)
            
            if ml_sig == 2 and ml_conf > 0.6 and oi_div > 0:
                signals.append(1)  # LONG
            elif ml_sig == 0 and ml_conf > 0.6 and oi_div < 0:
                signals.append(-1)  # SHORT
            else:
                signals.append(0)  # HOLD
        
        return signals
    
    def backtest(self):
        """Backtest baseline strategy"""
        # Similar to RL backtesting but using fixed rules
        # ...implementation...
        pass

def compare_rl_vs_baseline(rl_results, baseline_results):
    """
    Compare RL agent vs baseline
    """
    comparison = pd.DataFrame({
        'Metric': ['Total Return', 'Sharpe Ratio', 'Max Drawdown', 'Win Rate', 'Profit Factor', 'Total Trades'],
        'RL Agent': [
            f"{rl_results['total_return']:.2%}",
            f"{rl_results['sharpe_ratio']:.2f}",
            f"{rl_results['max_drawdown']:.2%}",
            f"{rl_results['win_rate']:.2%}",
            f"{rl_results['profit_factor']:.2f}",
            rl_results['total_trades']
        ],
        'Baseline': [
            f"{baseline_results['total_return']:.2%}",
            f"{baseline_results['sharpe_ratio']:.2f}",
            f"{baseline_results['max_drawdown']:.2%}",
            f"{baseline_results['win_rate']:.2%}",
            f"{baseline_results['profit_factor']:.2f}",
            baseline_results['total_trades']
        ]
    })
    
    print("\n" + "="*60)
    print("RL AGENT VS BASELINE COMPARISON")
    print("="*60)
    print(comparison.to_string(index=False))
    print("="*60)
    
    return comparison
```

---

## ✅ Phase 4 Deliverables Checklist

- [ ] Gym environment implemented
- [ ] State space designed (20 features)
- [ ] Action space designed (6 actions)
- [ ] Reward function implemented
- [ ] PPO agent trained (1M timesteps)
- [ ] A2C agent trained (500K timesteps)
- [ ] RL agent backtested on validation set
- [ ] Baseline strategy implemented
- [ ] RL vs Baseline comparison completed
- [ ] Visualizations generated
- [ ] Best model saved

---

## 🎯 Expected Performance Targets

| Metric | Baseline | RL Agent Target |
|--------|----------|-----------------|
| **Sharpe Ratio** | 1.2 | > 1.5 |
| **Max Drawdown** | -25% | < -20% |
| **Win Rate** | 52% | > 55% |
| **Profit Factor** | 1.5 | > 1.8 |
| **Total Return (6mo)** | +15% | > +20% |

---

## 🚀 Next Phase

**Phase 5: Live Deployment & Production System**

Final phase! We'll:
- Deploy the complete system (ML + RL)
- Implement real-time inference
- Set up monitoring dashboards
- Add safety kill-switches
- Start paper trading, then live

Ready to go LIVE? 🚀
