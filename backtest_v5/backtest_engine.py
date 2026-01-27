"""
Alpha-Zeta Super Scanner - Backtest V5 (HYPER-ACTIVE DAILY COMPOUNDING)
Goal: Turn ₹50k -> ₹1L+ (100% Return)
Strategy:
1. Scan EVERY DAY (not just Mondays)
2. Daily Compounding: Re-invest profits immediately
3. Max Activity: Take multiple trades per week
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

CACHE_FILE = "backtest_v4_data.pkl" # Re-use V4 data cache

class AlphaZetaBacktesterV5:
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
            logger.error("❌ No data cache found! Run V4 first.")
            return {}

    def run_daily_simulation(self):
        data_store = self.load_data()
        
        # Load pre-trained brain weights manually if file exists
        if os.path.exists("backtest_v4_history.csv"):
             self.brain.train("backtest_v4_history.csv")
        
        logger.info("🚀 V5 HYPER-ACTIVE SIMULATION STARTING...")
        
        # Daily simulation range
        start_date = pd.Timestamp("2025-01-01")
        end_date = pd.Timestamp("2025-12-01")
        market_days = pd.bdate_range(start_date, end_date) # Business days
        
        running_capital = self.capital
        active_positions = []
        all_trades = []
        
        # Convert cache to look-up friendly format
        # Pre-calculate indicators for speed? No, do it on fly for accuracy
        
        for current_date in tqdm(market_days, desc="Simulating Days"):
            # 1. MORNING & INTRADAY: Manage Open Positions
            active_pos_copy = active_positions[:]
            active_positions = []
            
            for pos in active_pos_copy:
                sym = pos['Symbol']
                if sym not in data_store: continue
                
                df = data_store[sym]
                if current_date not in df.index: 
                    active_positions.append(pos) # Market closed? Keep
                    continue
                
                # Get day's OHLC
                day_row = df.loc[current_date]
                high = float(day_row['High'])
                low = float(day_row['Low'])
                close = float(day_row['Close'])
                
                # Check Trailing Stop
                # Did price hit new high?
                if high > pos['High']:
                    pos['High'] = high
                
                # Stop is 4% below peak (Tightened for active trading)
                stop_price = pos['High'] * 0.96
                
                exit_price = None
                reason = ""
                
                # Did we hit stop today?
                if low < stop_price:
                    exit_price = stop_price # Conservative execution
                    reason = "TRAIL_STOP"
                # Or did we hit profit target? (+8% quick exit)
                elif high > pos['Entry'] * 1.08:
                    exit_price = pos['Entry'] * 1.08
                    reason = "PROFIT_TAKE"
                # Max hold time (5 days for hyper active)
                elif (current_date - pos['EntryDate']).days > 7:
                    exit_price = close
                    reason = "TIME_EXIT"
                
                if exit_price:
                    # Execute Sell
                    ret = (exit_price - pos['Entry']) / pos['Entry']
                    profit = pos['Size'] * ret
                    running_capital += (pos['Size'] + profit)
                    
                    all_trades.append({
                        'Symbol': sym, 'Entry': pos['Entry'], 'Exit': exit_price,
                        'Return': round(ret*100, 2), 'Profit': round(profit, 0),
                        'Reason': reason, 'Date': current_date.date()
                    })
                else:
                    active_positions.append(pos)
            
            # 2. EVENING SCAN: Look for setups for NEXT DAY
            # Only if we have cash (keep 5k buffer)
            if running_capital < 10000: continue
            
            candidates = []
            
            # Random shuffle to avoid alphabet bias
            scan_pool = list(data_store.keys()) # Full scan!
            import random
            random.shuffle(scan_pool)
            
            for sym in scan_pool[:200]: # Scan 200 random stocks daily
                if sym not in data_store: continue
                df = data_store[sym]
                
                # Need history UP TO current_date
                if current_date not in df.index: continue
                
                # Fast Breakout Check: Close > 10 Day High
                hist = df[df.index < current_date].tail(20)
                if len(hist) < 20: continue
                
                curr_price = float(df.loc[current_date]['Close'])
                d10_high = hist['High'].iloc[-10:].max()
                
                if curr_price > d10_high:
                    # Basic filters
                    vol_avg = hist['Volume'].mean()
                    if vol_avg < 500000: continue # Min 500k volume
                    
                    # Score it
                    mom = curr_price / hist['Close'].iloc[-10]
                    candidates.append({'Symbol': sym, 'Price': curr_price, 'Score': mom})
            
            # Buy Top Picks
            candidates.sort(key=lambda x: x['Score'], reverse=True)
            
            # Max positions = 5
            open_slots = 5 - len(active_positions)
            
            for pick in candidates[:open_slots]:
                invest_amt = running_capital / max(1, open_slots) # Split remaining cash dynamically
                if invest_amt < 8000: continue # Min trade size
                
                running_capital -= invest_amt
                active_positions.append({
                    'Symbol': pick['Symbol'],
                    'Entry': pick['Price'],
                    'Size': invest_amt,
                    'EntryDate': current_date,
                    'High': pick['Price']
                })

        # Final Close
        equity = running_capital
        for pos in active_positions:
            # Mark to market
            sym = pos['Symbol']
            last_price = float(data_store[sym]['Close'].iloc[-1])
            pnl = (last_price - pos['Entry']) / pos['Entry']
            val = pos['Size'] * (1 + pnl)
            equity += val
            
        roi = (equity - self.capital) / self.capital * 100
        print("\n" + "="*70)
        print(f"  V5 HYPER-ACTIVE RESULTS (Daily Scanning)")
        print("="*70)
        print(f"Initial:    ₹{self.capital:,}")
        print(f"Final:      ₹{equity:,.0f}")
        print(f"Return:     {roi:.2f}%")
        print(f"Trades:     {len(all_trades)}")
        
        if all_trades:
            df = pd.DataFrame(all_trades)
            os.makedirs('backtest_v5', exist_ok=True)
            df.to_csv("backtest_v5/backtest_2025_results_v5.csv", index=False)

if __name__ == "__main__":
    os.makedirs('backtest_v5', exist_ok=True)
    tester = AlphaZetaBacktesterV5()
    tester.run_daily_simulation()
