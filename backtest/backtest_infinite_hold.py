"""
Alpha-Zeta Super Scanner - V9 Infinite Hold Backtest (The Bag Holder)
Goal: Take ₹500 Profit. NEVER book a loss.
Strategy:
1. Capital: ₹50,000 split into 2 Slots (₹25,000 each).
2. Entry: Top Stock from Scanner (when slot is empty).
3. Exit: ONLY if Profit >= ₹500.
4. Stop Loss: NONE. Hold forever if red.
5. Scenarios: Weekly, Bi-Weekly, Monthly Configs.
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

class AlphaZetaInfiniteHold:
    def __init__(self, capital=50000):
        self.capital = capital
        self.brain = AlphaZetaBrain()
        self.configs = {
            'Weekly (3-7 Days)': {'scan_freq': 5, 'config': TIMEFRAME_CONFIGS['3-7_days']},
            'Bi-Weekly (2 Weeks)': {'scan_freq': 10, 'config': TIMEFRAME_CONFIGS['1-2_weeks']},
            'Monthly (1 Month)': {'scan_freq': 20, 'config': TIMEFRAME_CONFIGS['1_month']}
        }
        
    def load_data(self):
        if os.path.exists(CACHE_FILE):
            logger.info("⚡ Loading cached data...")
            with open(CACHE_FILE, 'rb') as f:
                return pickle.load(f)
        else:
            logger.error("❌ No data cache found! Run V4/V5 first.")
            return {}

    def run_simulation(self):
        data_store = self.load_data()
        
        # Train Brain
        if os.path.exists("backtest_v4_history.csv"):
             self.brain.train("backtest_v4_history.csv")
             
        logger.info("🚀 V9 INFINITE HOLD SIMULATION STARTING...")
        
        results = []
        
        for name, settings in self.configs.items():
            freq = settings['scan_freq']
            tf_config = settings['config']
            
            logger.info(f"\n--- Testing: {name} ---")
            
            # Simulation Loop
            start_date = pd.Timestamp("2025-01-01")
            end_date = pd.Timestamp("2025-12-01")
            market_days = pd.bdate_range(start_date, end_date)
            
            # Portfolio State
            slots = [
                {'status': 'EMPTY', 'cash': 25000, 'stock': None},
                {'status': 'EMPTY', 'cash': 25000, 'stock': None}
            ]
            
            realized_profit = 0
            trades_closed = 0
            
            # Helper to check if we should scan today
            # We scan if ANY slot is EMPTY. 
            # But "run scanner" usually implies a specific day?
            # User said "run this scanner", implying we act when we run it.
            # But if a slot frees up on Tuesday, do we wait for next Weekly Scan?
            # To be efficient: We scan ONLY on intended scan days (Day 0, 5, 10...).
            # If a slot frees up mid-week, it waits.
            
            scan_days = [start_date + datetime.timedelta(days=i) for i in range(0, 365, freq)]
            # Normalize to business days? Close enough check
            
            for current_date in tqdm(market_days, desc=f"Simulating {name}"):
                
                # 1. CHECK POSITIONS (Daily)
                for i, slot in enumerate(slots):
                    if slot['status'] == 'BUSY':
                        sym = slot['stock']['Symbol']
                        entry_price = slot['stock']['Entry']
                        shares = slot['stock']['Shares']
                        
                        if sym not in data_store: continue
                        df = data_store[sym]
                        if current_date not in df.index: continue
                        
                        # Check High for Profit Target
                        # Intraday High allows us to exit mid-day
                        row = df.loc[current_date]
                        high = float(row['High'])
                        close = float(row['Close'])
                        
                        # Target: ₹500 Profit per slot
                        # 500 / 25000 = 2%
                        target_price = entry_price + (500 / shares)
                        
                        if high >= target_price:
                            # SOLD!
                            exit_price = target_price
                            pnl = 500
                            realized_profit += pnl
                            trades_closed += 1
                            
                            # Reset Slot
                            slots[i] = {'status': 'EMPTY', 'cash': 25000 + pnl, 'stock': None} # Original cash recycled?
                            # User said "split 50000 into 2... 25000 each".
                            # "if one stock shows 500 rs i will take profit"
                            # The ₹500 is pocketed (Profit). 
                            # Does the ₹25k base grow? Usually "Capital Recycling" implies yes.
                            # But strictly, let's keep base 25k to be safe or re-invest full?
                            # "25000 into each stock".
                            # I will reinvest the base 25k but BANK the 500 profit separately.
                            # So slot cash resets to 25k. Profit goes to 'realized_profit'.
                             
                            slots[i] = {'status': 'EMPTY', 'cash': 25000, 'stock': None}
                            
                        # Else: HOLD FOREVER. No Stop Loss.
                
                # 2. SCAN & FILL EMPTY SLOTS (Only on Scan Days)
                # Check if current_date matches a Scan Day (approx)
                is_scan_day = False
                for sd in scan_days:
                   if abs((sd - current_date).days) < 1: # Same day match
                       is_scan_day = True
                       break
                
                empty_slots_indices = [i for i, s in enumerate(slots) if s['status'] == 'EMPTY']
                
                if is_scan_day and empty_slots_indices:
                    # Run Scanner Logic
                    candidates = []
                    
                    # Optimization: Scan only subset for speed
                    import random
                    scan_pool = list(data_store.keys())
                    random.shuffle(scan_pool)
                    
                    for sym in scan_pool[:150]:
                        if sym not in data_store: continue
                        df = data_store[sym]
                        
                        # Need history
                        hist = df[df.index <= current_date]
                        if len(hist) < 60: continue
                        
                        metrics = TechnicalCore.calculate_indicators(hist, tf_config)
                        if not metrics: continue
                        
                        # V1 Filters for logic match
                        if metrics['hurst'] < 0.4: continue
                        
                        formulas = FormulaFactory.generate_all(metrics)
                        score = sum(formulas[f'f{i}'] * self.brain.weights[i-1] for i in range(1, 24))
                        
                        if current_date not in df.index: continue
                        last_price = float(df.loc[current_date]['Close'])
                        candidates.append({'Symbol': sym, 'Price': last_price, 'Score': score})
                    
                    # Sort by Score
                    candidates.sort(key=lambda x: x['Score'], reverse=True)
                    
                    # Fill Slots
                    for idx in empty_slots_indices:
                        if not candidates: break
                        
                        pick = candidates.pop(0) # Top 1, then Top 2
                        cash = slots[idx]['cash']
                        shares = cash / pick['Price']
                        
                        slots[idx] = {
                            'status': 'BUSY',
                            'cash': 0,
                            'stock': {
                                'Symbol': pick['Symbol'],
                                'Entry': pick['Price'],
                                'Shares': shares,
                                'Date': current_date
                            }
                        }
            
            # End of Year: Mark to Market
            # Calculate value of Stuck Stocks
            unrealized_pnl = 0
            stuck_stocks = []
            
            for slot in slots:
                if slot['status'] == 'BUSY':
                    sym = slot['stock']['Symbol']
                    shares = slot['stock']['Shares']
                    entry = slot['stock']['Entry']
                    
                    last_price = float(data_store[sym]['Close'].iloc[-1])
                    val = shares * last_price
                    pnl = val - 25000
                    unrealized_pnl += pnl
                    
                    stuck_stocks.append(f"{sym} ({pnl:.0f})")
            
            total_net = realized_profit + unrealized_pnl
            
            results.append({
                'Name': name,
                'Realized Profit': realized_profit,
                'Unrealized PnL': unrealized_pnl,
                'Total Net': total_net,
                'Closed Trades': trades_closed,
                'Stuck Stocks': ", ".join(stuck_stocks)
            })
            
        # Print Comparison
        print("\n" + "="*80)
        print(f"  V9 INFINITE HOLD RESULTS (Target ₹500, No Stop Loss)")
        print("="*80)
        print(f"{'Config':<20} | {'Banked Profit':<15} | {'Unrealized Loss':<15} | {'Net Result':<10}")
        print("-" * 75)
        
        for r in results:
            print(f"{r['Name']:<20} | ₹{r['Realized Profit']:<14,.0f} | ₹{r['Unrealized PnL']:<14,.0f} | ₹{r['Total Net']:<9,.0f}")
            if r['Stuck Stocks']:
                print(f"   ⚠️ Bag Holding: {r['Stuck Stocks']}")
        
        # Save
        if results:
            df = pd.DataFrame(results)
            os.makedirs('backtest', exist_ok=True)
            df.to_csv("backtest/results_infinite_hold.csv", index=False)

if __name__ == "__main__":
    tester = AlphaZetaInfiniteHold()
    tester.run_simulation()
