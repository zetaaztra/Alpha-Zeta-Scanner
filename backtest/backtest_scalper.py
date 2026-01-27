"""
Alpha-Zeta Super Scanner - V8 Scalper Backtest (The 1% Grind)
Goal: Take ₹500 profit (+1%) on ₹50k capital repeatedly.
Strategy:
1. Capital: 100% on ONE Top Pick.
2. Target: +1% (Absolute Priority).
3. Stop Loss: -5% (To prevent blowout) or 7-Day Timeout.
4. Cycle: Buy -> Sell(1%) -> Scan Next Day -> Repeat.
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

class AlphaZetaScalper:
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

    def run_scalper_simulation(self):
        data_store = self.load_data()
        
        # Train Brain
        if os.path.exists("backtest_v4_history.csv"):
             self.brain.train("backtest_v4_history.csv")
             
        logger.info("🚀 V8 SCALPER SIMULATION (Target +1%) STARTING...")
        
        # Daily Loop
        start_date = pd.Timestamp("2025-01-01")
        end_date = pd.Timestamp("2025-12-01")
        market_days = pd.bdate_range(start_date, end_date)
        
        running_capital = self.capital
        active_position = None # Dict or None
        all_trades = []
        
        for current_date in tqdm(market_days, desc="Scalping 1%"):
            # 1. MANAGE POSITION (If any)
            if active_position:
                sym = active_position['Symbol']
                if sym not in data_store: continue
                df = data_store[sym]
                
                if current_date not in df.index: continue
                
                row = df.loc[current_date]
                high = float(row['High'])
                low = float(row['Low'])
                close = float(row['Close'])
                open_price = float(row['Open'])
                
                entry_price = active_position['Entry']
                target_price = entry_price * 1.01 # +1% Target
                stop_price = entry_price * 0.95   # -5% Stop
                
                exit_price = None
                reason = ""
                
                # Check GAP UP (Open > Target)
                if open_price >= target_price:
                    exit_price = open_price
                    reason = "GAP_UP_TARGET"
                
                # Check INTRADAY HIGH (High > Target)
                elif high >= target_price:
                    exit_price = target_price
                    reason = "TARGET_HIT_1%"
                    
                # Check STOP LOSS
                elif low <= stop_price:
                    exit_price = stop_price
                    reason = "STOP_LOSS"
                
                # Check TIME EXPIRE (7 Days)
                elif (current_date.date() - active_position['Date']).days >= 7:
                    exit_price = close
                    reason = "TIME_EXIT"
                    
                if exit_price:
                    # Execute Sell
                    ret = (exit_price - entry_price) / entry_price
                    profit = active_position['Size'] * ret
                    running_capital += (active_position['Size'] + profit)
                    
                    all_trades.append({
                        'Symbol': sym, 'Entry': entry_price, 'Exit': exit_price,
                        'Return': round(ret*100, 2), 'Profit': round(profit, 0),
                        'Reason': reason, 'Date': current_date.date()
                    })
                    active_position = None # Free to trade again
                else:
                    continue # Hold position
            
            # 2. SCAN & BUY (If Cash Free)
            if active_position is None:
                # Minimum cash check
                if running_capital < 5000: break
                
                candidates = []
                # Random Shuffle Scan Pool for realism
                scan_pool = list(data_store.keys())
                import random
                random.shuffle(scan_pool)
                
                for sym in scan_pool[:200]: # Scan 200 random stocks (simulating user checking screener)
                    if sym not in data_store: continue
                    df = data_store[sym]
                    if current_date not in df.index: continue
                    
                    # Logic: V1 Filters
                    hist = df[df.index <= current_date]
                    if len(hist) < 60: continue
                    
                    hist_raw = hist.tail(100)
                    metrics = TechnicalCore.calculate_indicators(hist_raw, self.config)
                    if not metrics: continue
                    
                    # Essential Filter: Hurst > 0.45 (Trendiness)
                    if metrics['hurst'] < 0.45: continue
                    
                    formulas = FormulaFactory.generate_all(metrics)
                    score = sum(formulas[f'f{i}'] * self.brain.weights[i-1] for i in range(1, 24))
                    
                    curr_price = float(df.loc[current_date]['Close'])
                    candidates.append({'Symbol': sym, 'Price': curr_price, 'Score': score})
                
                # Pick BEST ONE
                candidates.sort(key=lambda x: x['Score'], reverse=True)
                if candidates:
                    top = candidates[0]
                    invest_amt = running_capital # 100%
                    running_capital = 0 # All in
                    
                    active_position = {
                        'Symbol': top['Symbol'],
                        'Entry': top['Price'],
                        'Size': invest_amt, 
                        'Date': current_date.date()
                    }

        # Final Close
        equity = running_capital
        if active_position:
            pos = active_position
            sym = pos['Symbol']
            last_price = float(data_store[sym]['Close'].iloc[-1])
            pnl = (last_price - pos['Entry']) / pos['Entry']
            val = pos['Size'] * (1 + pnl)
            equity += val # Add back value of open position
            
            all_trades.append({
                'Symbol': sym, 'Exit': last_price,
                'Return': round(pnl*100, 2), 'Profit': round(val - pos['Size'], 0),
                'Reason': "FORCE_CLOSE"
            })
            
        roi = (equity - self.capital) / self.capital * 100
        print("\n" + "="*70)
        print(f"  V8 SCALPER RESULTS (Target +1%)")
        print("="*70)
        print(f"Initial:    ₹{self.capital:,}")
        print(f"Final:      ₹{equity:,.0f}")
        print(f"Return:     {roi:.2f}%")
        print(f"Trades:     {len(all_trades)}")
        
        wins = sum(1 for t in all_trades if t['Return'] > 0)
        rate = (wins/len(all_trades))*100 if all_trades else 0
        print(f"Win Rate:   {rate:.1f}%")
        
        if all_trades:
            df = pd.DataFrame(all_trades)
            os.makedirs('backtest', exist_ok=True)
            df.to_csv("backtest/results_scalper_1pct.csv", index=False)

if __name__ == "__main__":
    tester = AlphaZetaScalper()
    tester.run_scalper_simulation()
