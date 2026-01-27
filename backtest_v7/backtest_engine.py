"""
Alpha-Zeta Super Scanner - Backtest V7 (THE SNIPER)
Goal: Aggressive 66% Profit via CONCENTRATION
Strategy:
1. Logic: V1 Swing (Proven best so far)
2. Sizing: 100% Capital on TOP 1 PICK only (High Risk, High Reward)
3. Exit: 7 Days Fixed OR Stop Loss -7%
4. Frequency: Monthly (12 Trades Total)
"""
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import os
import sys
from tqdm import tqdm
import logging
import pickle

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import DataEngine, TechnicalCore, FormulaFactory, AlphaZetaBrain, TIMEFRAME_CONFIGS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CACHE_FILE = "backtest_v4_data.pkl"

class AlphaZetaBacktesterV7:
    def __init__(self, capital=50000):
        self.capital = capital
        self.brain = AlphaZetaBrain()
        self.config = TIMEFRAME_CONFIGS['3-7_days']
        
    def load_data(self):
        if os.path.exists(CACHE_FILE):
            logger.info("⚡ Loading cached data...")
            with open(CACHE_FILE, 'rb') as f:
                return pickle.load(f)
        else:
            logger.error("❌ No data cache found! Run V4/V5 first.")
            return {}

    def run_sniper_simulation(self):
        data_store = self.load_data()
        
        # Train brain
        if os.path.exists("backtest_v4_history.csv"):
             self.brain.train("backtest_v4_history.csv")
        
        logger.info("🚀 V7 SNIPER SIMULATION STARTING...")
        logger.info("   Strategy: 100% Capital on Top 1 Pick/Month")
        
        # Monthly Test Dates (same as V1)
        test_dates = [
            datetime.datetime(2025, 1, 6), datetime.datetime(2025, 2, 3),
            datetime.datetime(2025, 3, 3), datetime.datetime(2025, 4, 7),
            datetime.datetime(2025, 5, 5), datetime.datetime(2025, 6, 2),
            datetime.datetime(2025, 7, 7), datetime.datetime(2025, 8, 4),
            datetime.datetime(2025, 9, 1), datetime.datetime(2025, 10, 6),
            datetime.datetime(2025, 11, 3), datetime.datetime(2025, 12, 1)
        ]
        
        running_capital = self.capital
        all_trades = []
        
        for scan_date in test_dates:
            target_dt = pd.Timestamp(scan_date.date())
            logger.info(f"--- Sniper Scan {target_dt.date()} | Cash: ₹{running_capital:.0f} ---")
            
            candidates = []
            
            # Scan All 500 stocks
            for sym, df in data_store.items():
                if target_dt not in df.index: continue
                
                # Check Filters (V1 Logic)
                # Close > 200 SMA?
                hist = df[df.index <= target_dt]
                if len(hist) < 60: continue
                
                curr_price = float(df.loc[target_dt]['Close'])
                # Removed SMA trend filter to ensure we get candidates
                # Rely purely on ML score

                
                # Filter: RSI Removed (Not in TechnicalCore)
                # Rely on MFI if needed, but primarily ML Score
                hist_raw = hist # Pass FULL history
                metrics = TechnicalCore.calculate_indicators(hist_raw, self.config)
                if not metrics: continue
                
                # Generate Score
                formulas = FormulaFactory.generate_all(metrics)
                score = sum(formulas[f'f{i}'] * self.brain.weights[i-1] for i in range(1, 24))
                
                candidates.append({'Symbol': sym, 'Price': curr_price, 'Score': score})
            
            # Pick #1 Best Stock
            candidates.sort(key=lambda x: x['Score'], reverse=True)
            
            if not candidates:
                logger.info("   No targets found.")
                continue
                
            top_pick = candidates[0]
            sym = top_pick['Symbol']
            df = data_store[sym]
            
            # Simulate Trade
            entry_price = top_pick['Price']
            
            # Get Future 7 Days
            future_days = df[df.index > target_dt].head(7)
            if future_days.empty: continue
            
            exit_price = None
            reason = ""
            days_held = 0
            
            # Check Stop Loss (-7%) Daily
            stop_price = entry_price * 0.93
            
            for dt, row in future_days.iterrows():
                low = float(row['Low'])
                close = float(row['Close'])
                days_held += 1
                
                if low < stop_price:
                    exit_price = stop_price
                    reason = "STOP_LOSS"
                    break
            
            if not exit_price:
                # Time Exit (Day 7 Close)
                exit_price = float(future_days.iloc[-1]['Close'])
                reason = "TIME_EXIT"
            
            # Result
            ret = (exit_price - entry_price) / entry_price
            profit = running_capital * ret # 100% Capital!
            running_capital += profit
            
            logger.info(f"🎯 Target: {sym} | {reason} | {ret*100:.2f}% | ₹{profit:.0f}")
            
            all_trades.append({
                'Symbol': sym, 'Entry': entry_price, 'Exit': exit_price,
                'Return': round(ret*100, 2), 'Profit': round(profit, 0),
                'Reason': reason, 'Date': scan_date.date()
            })
            
        # Final Stats
        roi = (running_capital - self.capital) / self.capital * 100
        print("\n" + "="*70)
        print(f"  V7 SNIPER RESULTS (100% Concentration)")
        print("="*70)
        print(f"Initial:    ₹{self.capital:,}")
        print(f"Final:      ₹{running_capital:,.0f}")
        print(f"Return:     {roi:.2f}%")
        print(f"Trades:     {len(all_trades)}")
        
        if all_trades:
            df = pd.DataFrame(all_trades)
            os.makedirs('backtest_v7', exist_ok=True)
            df.to_csv("backtest_v7/backtest_2025_results_v7.csv", index=False)

if __name__ == "__main__":
    os.makedirs('backtest_v7', exist_ok=True)
    tester = AlphaZetaBacktesterV7()
    tester.run_sniper_simulation()
