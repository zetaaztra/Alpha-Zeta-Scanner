"""
Alpha-Zeta Super Scanner - V1 Multi-Timeframe Backtest
Compares performance across 3 distinct timeframes using the proven V1 Logic:
1. Intraday: Exit at Same Day Close
2. Swing (1-2 Weeks): Exit after 10 Days
3. Monthly: Exit after 20 Days
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

class AlphaZetaBacktestMultiTF:
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
            logger.error("❌ No data cache found! Run V4/V5 first or this will fail.")
            # For robustness, we could download, but assuming cache exists from previous steps
            return {}

    def simulate_strategy(self, data_store, holding_days, strategy_name):
        logger.info(f"\n🚀 Simulating: {strategy_name} (Hold {holding_days} Days)")
        
        # Train Brain
        if os.path.exists("backtest_v4_history.csv"):
             self.brain.train("backtest_v4_history.csv")
             
        # Scans on First Monday of each month (V1 Standard)
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
            candidates = []
            
            # Scan
            for sym, df in data_store.items():
                if target_dt not in df.index: continue
                
                # V1 Filters
                hist = df[df.index <= target_dt]
                if len(hist) < 60: continue
                
                curr_price = float(df.loc[target_dt]['Close'])
                
                # Calculate ML Score
                metrics = TechnicalCore.calculate_indicators(hist, self.config)
                if not metrics: continue
                
                # Hurst Filter (V1 Essential)
                if metrics['hurst'] < 0.45: continue
                
                formulas = FormulaFactory.generate_all(metrics)
                score = sum(formulas[f'f{i}'] * self.brain.weights[i-1] for i in range(1, 24))
                
                candidates.append({'Symbol': sym, 'Price': curr_price, 'Score': score})
            
            # Pick Top 3 (V1 Standard)
            candidates.sort(key=lambda x: x['Score'], reverse=True)
            picks = candidates[:3]
            
            if not picks: continue
            
            # Position Size
            pos_size = running_capital / len(picks)
            
            for pick in picks:
                sym = pick['Symbol']
                entry_price = pick['Price']
                df = data_store[sym]
                
                exit_price = None
                reason = "TIME_EXIT"
                
                # Get Future Data
                future = df[df.index > target_dt].head(holding_days)
                
                if holding_days == 0: # Intraday
                    # Buy Open/Vwap? Let's assume Buy at 'Close' of scan day is impossible 
                    # if we run scanner after market.
                    # V1 assumes we buy NEXT day open? 
                    # Or V1 assumes we buy AT scan time prices (simulated close).
                    # For Intraday, we'll assume Entry = Open of Scan Day, Exit = Close of Scan Day
                    # But our data structure has Entry = Close of Scan Day.
                    # So Intraday simulation is tricky with daily bars.
                    # Approximation: Entry = Open, Exit = Close of target_dt
                    row = df.loc[target_dt]
                    entry_price = float(row['Open']) # Override entry
                    exit_price = float(row['Close'])
                    
                else:
                    if future.empty: 
                        exit_price = entry_price # No data, scratch
                    else:
                        exit_price = float(future.iloc[-1]['Close'])
                
                # Calculate PnL
                ret = (exit_price - entry_price) / entry_price
                profit = pos_size * ret
                running_capital += profit
                
                all_trades.append({
                    'Symbol': sym, 'Entry': entry_price, 'Exit': exit_price,
                    'Return': round(ret*100, 2), 'Profit': round(profit, 0),
                    'Date': scan_date.date()
                })
        
        # Stats
        roi = (running_capital - self.capital) / self.capital * 100
        print(f"   Done. Final Capital: ₹{running_capital:,.0f} ({roi:.2f}%)")
        return all_trades, roi

    def run_comparison(self):
        data_store = self.load_data()
        
        # 1. Weekly (5 Days)
        trades_week, roi_week = self.simulate_strategy(data_store, 5, "1 Week (5 Days)")
        
        # 2. Bi-Weekly (10 Days)
        trades_2week, roi_2week = self.simulate_strategy(data_store, 10, "2 Weeks (10 Days)")
        
        # 3. Monthly (20 Days)
        trades_month, roi_month = self.simulate_strategy(data_store, 20, "1 Month (20 Days)")
        
        print("\n" + "="*70)
        print("  V1 TIMEFRAME COMPARISON (Same Logic, Different Holds)")
        print("="*70)
        print(f"{'Timeframe':<20} | {'ROI':<10} | {'Trades':<10} | {'Win Rate':<10}")
        print("-" * 60)
        
        for name, trades, roi in [("1 Week", trades_week, roi_week), 
                                 ("2 Weeks", trades_2week, roi_2week),
                                 ("1 Month", trades_month, roi_month)]:
            win_rate = 0
            if trades:
                wins = sum(1 for t in trades if t['Return'] > 0)
                win_rate = (wins / len(trades)) * 100
            print(f"{name:<20} | {roi:>6.2f}%   | {len(trades):<10} | {win_rate:>6.1f}%")
            
            # Save CSVs
            if trades:
                df = pd.DataFrame(trades)
                fname = f"backtest/results_{name.split()[0].lower()}.csv"
                df.to_csv(fname, index=False)

if __name__ == "__main__":
    tester = AlphaZetaBacktestMultiTF()
    tester.run_comparison()
