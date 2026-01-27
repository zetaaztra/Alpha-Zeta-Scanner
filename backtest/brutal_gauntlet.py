"""
BRUTAL GAUNTLET: ALPHA-ZETA PRIME (FILTER 1) STRESS TEST
A high-fidelity backtest with slippage, drawdown analysis, and consistency checks.
"""
import pandas as pd
import numpy as np
import os
import sys
import pickle
import logging
from tqdm import tqdm
import datetime

# Mock the environment to load app.py components if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import TechnicalCore, TIMEFRAME_CONFIGS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

CACHE_PATH = r"c:\Users\hp\Desktop\Nifty_500\Alpha_Zeta_Super_Scanner\backtest_v4_data.pkl"
INITIAL_CAPITAL = 100000.0
SLIPPAGE_PCT = 0.005 # 0.5% total friction (slippage + taxes + brokerage)

class BrutalGauntlet:
    def __init__(self):
        self.data_store = {}
        self.config = TIMEFRAME_CONFIGS['3-7_days']
        self.capital = INITIAL_CAPITAL
        self.equity_curve = []
        self.trade_log = []

    def load_data(self):
        if os.path.exists(CACHE_PATH):
             with open(CACHE_PATH, 'rb') as f:
                 self.data_store = pickle.load(f)
             logger.info(f"Loaded {len(self.data_store)} stocks.")
        else:
             logger.error("Cache not found.")
             sys.exit(1)

    def calculate_ensemble(self, df, date):
        hist = df[df.index <= date]
        if len(hist) < 50: return -100, 0.0
        
        close = hist['Close']
        current = float(close.iloc[-1])
        
        # Performance metrics
        r_s = ((current / float(close.iloc[-6])) - 1) * 100 if len(close) > 5 else 0
        r_m = ((current / float(close.iloc[-21])) - 1) * 100 if len(close) > 20 else 0
        r_l = ((current / float(close.iloc[-64])) - 1) * 100 if len(close) > 63 else 0
        
        # Alpha-Zeta Ensemble (simplified winning audit version)
        # Momentum + Vol Intensity proxy
        stk_ret_1m = (current / float(close.iloc[-21])) - 1
        vol_ratio = hist['Volume'].iloc[-1] / hist['Volume'].iloc[-20:].mean()
        score = (stk_ret_1m * 100) + (1.5 if vol_ratio > 1.2 else -1)
        
        # Filter 2 Logic (The "67%" Candidate)
        sma50 = close.rolling(50).mean().iloc[-1]
        
        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-6)
        rsi_series = 100 - (100 / (1 + rs))
        rsi_val = rsi_series.iloc[-1]
        
        # FILTERS
        f_trend = current > sma50
        f_rsi = rsi_val < 70
        f_logic = score > 0
        f_cooling = (r_s >= 0.0) and (r_s <= 6.0) # THE SECRET SAUCE
        
        is_valid = f_trend and f_rsi and f_logic and f_cooling
        
        return (score if is_valid else -100), current

    def run(self):
        self.load_data()
        test_dates = pd.date_range(start="2025-01-01", end="2025-12-01", freq='W-MON')
        
        logger.info("Starting Brutal Gauntlet Scan...")
        
        for date in tqdm(test_dates):
            candidates = []
            for sym, df in self.data_store.items():
                if date not in df.index: continue
                score, price = self.calculate_ensemble(df, date)
                if score > -50: # Valid signal
                    candidates.append((sym, score, price))
            
            # Execute Weekly Trades (Top 3)
            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                top_3 = candidates[:3]
                
                # Split capital 3 ways (or fewer if fewer candidates)
                allocation = self.capital / len(top_3)
                period_returns = []
                
                for sym, score, entry_price in top_3:
                    df = self.data_store[sym]
                    future_dates = df.index[df.index > date]
                    if len(future_dates) < 5: 
                         period_returns.append(0)
                         continue
                    
                    exit_price = float(df.loc[future_dates[4]]['Close'])
                    
                    # Apply Slippage on BOTH Entry and Exit (0.25% each = 0.5% total)
                    effective_entry = entry_price * (1 + (SLIPPAGE_PCT/2))
                    effective_exit = exit_price * (1 - (SLIPPAGE_PCT/2))
                    
                    raw_ret = (effective_exit / effective_entry) - 1
                    period_returns.append(raw_ret)
                    
                    self.trade_log.append({
                        'Date': date, 'Symbol': sym, 'Score': score,
                        'Entry': effective_entry, 'Exit': effective_exit, 'Return': raw_ret
                    })
                
                # Net capital update for the week
                avg_week_ret = np.mean(period_returns) if period_returns else 0
                self.capital *= (1 + avg_week_ret)
            
            self.equity_curve.append(self.capital)

        self.report()

    def report(self):
        df_equity = pd.Series(self.equity_curve)
        total_return = (self.capital / INITIAL_CAPITAL - 1) * 100
        
        # Drawdown Calculation
        rolling_max = df_equity.cummax()
        drawdowns = (df_equity - rolling_max) / rolling_max
        max_drawdown = drawdowns.min() * 100
        
        # Consistency
        trades_df = pd.DataFrame(self.trade_log)
        win_rate = (trades_df['Return'] > 0).mean() * 100
        
        print("\n" + "="*60)
        print("  💀 THE BRUTAL GAUNTLET: FINAL VERDICT")
        print("="*60)
        print(f"Algorithm:         Zeta Filter 1 (Aggressive Trend)")
        print(f"Friction (Slippage): {SLIPPAGE_PCT*100:.1f}% per cycle")
        print("-" * 60)
        print(f"Final Capital:     ₹{self.capital:,.2f}")
        print(f"Total ROI:         {total_return:+.2f}%")
        print(f"Max Drawdown:      {max_drawdown:+.2f}%")
        print(f"Win Rate:          {win_rate:.1f}%")
        print(f"Calmar Ratio:      {abs(total_return/max_drawdown):.2f}" if max_drawdown != 0 else "N/A")
        print("-" * 60)
        
        # Monthly breakdown
        # Group equity by index (weeks) and show monthly end values
        # (Approximate since we trade weekly)
        print("Consistency Check (Sample Weeks Output):")
        print(df_equity.pct_change().describe())
        print("="*60)
        
        # Save Log
        trades_df.to_csv("backtest/brutal_gauntlet_trades.csv", index=False)
        pd.DataFrame({'Equity': self.equity_curve}).to_csv("backtest/brutal_gauntlet_equity.csv", index=False)

if __name__ == "__main__":
    BrutalGauntlet().run()
