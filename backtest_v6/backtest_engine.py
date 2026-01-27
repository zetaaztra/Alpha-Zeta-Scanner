"""
Alpha-Zeta Super Scanner - Backtest V6 (TREND RIDER)
Goal: Aggressive 66% Profit
Strategy:
1. Entry: High Quality Breakout (Score > 2.0, Price > 20-Day High)
2. Exit: Trend Following (Hold while Close > 10-Day EMA)
3. Sizing: Concentrated (Max 2 positions, 50% capital each)
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

class AlphaZetaBacktesterV6:
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

    def run_trend_simulation(self):
        data_store = self.load_data()
        
        # Train brain if needed
        if os.path.exists("backtest_v4_history.csv"):
             self.brain.train("backtest_v4_history.csv")
        
        logger.info("🚀 V6 TREND RIDER SIMULATION STARTING...")
        logger.info("   Strategy: Hold until Close < 10-Day EMA")
        
        start_date = pd.Timestamp("2025-01-01")
        end_date = pd.Timestamp("2025-12-01")
        market_days = pd.bdate_range(start_date, end_date)
        
        running_capital = self.capital
        active_positions = []
        all_trades = []
        
        for current_date in tqdm(market_days, desc="Riding Trends"):
            # 1. MANAGE POSITIONS (Trail 10 EMA)
            active_pos_copy = active_positions[:]
            active_positions = []
            
            for pos in active_pos_copy:
                sym = pos['Symbol']
                if sym not in data_store: continue
                df = data_store[sym]
                
                if current_date not in df.index:
                    active_positions.append(pos)
                    continue
                
                # Get Today's Data
                day_row = df.loc[current_date]
                close = float(day_row['Close'])
                
                # Calculate 10 EMA manually for speed or get form data if available
                # Rolling calculation is better done upfront, but let's slice
                # Need last 20 days for EMA calc
                hist = df[df.index <= current_date].tail(20)
                if len(hist) < 15: 
                    active_positions.append(pos)
                    continue
                    
                ema_10 = hist['Close'].ewm(span=10, adjust=False).mean().iloc[-1]
                
                exit_price = None
                reason = ""
                
                # EXIT LOGIC: Close < 10 EMA
                if close < ema_10:
                    exit_price = close
                    reason = "EMA_CROSS"
                
                # Hard Stop: -8% (Safety net)
                elif close < pos['Entry'] * 0.92:
                    exit_price = close
                    reason = "HARD_STOP"
                
                if exit_price:
                    # Execute Sell
                    ret = (exit_price - pos['Entry']) / pos['Entry']
                    profit = pos['Size'] * ret
                    running_capital += (pos['Size'] + profit)
                    
                    days_held = (current_date.date() - pos['EntryDate']).days
                    all_trades.append({
                        'Symbol': sym, 'Entry': pos['Entry'], 'Exit': exit_price,
                        'Return': round(ret*100, 2), 'Profit': round(profit, 0),
                        'Reason': reason, 'Date': current_date.date(),
                        'Days': days_held
                    })
                else:
                    active_positions.append(pos)
            
            # 2. SCAN FOR NEW TRADES
            # Only if we have cash for a slot (Max 2 positions)
            max_pos = 2
            if len(active_positions) >= max_pos: continue
            
            # Cash check
            if running_capital < 10000: continue
            
            candidates = []
            scan_pool = list(data_store.keys()) # Full scan
            
            for sym in scan_pool:
                if sym not in data_store: continue
                df = data_store[sym]
                if current_date not in df.index: continue
                
                curr_price = float(df.loc[current_date]['Close'])
                
                # Strict Filter: Must be > 20 Day High (Breakout)
                hist = df[df.index < current_date].tail(21) # 20 prev + today
                if len(hist) < 20: continue
                
                prev_high = hist['High'].iloc[:-1].max() # High of previous 20 (excluding today)
                
                if curr_price > prev_high:
                    # Score
                    # Simple Momentum Score for speed
                    mom = curr_price / hist['Close'].iloc[0] # 20 day return
                    
                    # 10 EMA Check: Must be > EMA 10
                    ema_10 = hist['Close'].ewm(span=10, adjust=False).mean().iloc[-1]
                    if curr_price > ema_10:
                        candidates.append({'Symbol': sym, 'Price': curr_price, 'Score': mom})
            
            # Sort by Momentum (Buy strongest stocks)
            candidates.sort(key=lambda x: x['Score'], reverse=True)
            
            # Fill open slots
            slots_needed = max_pos - len(active_positions)
            for pick in candidates[:slots_needed]:
                # Position Sizing: Split available cash equally among free slots
                # But simple: half of total capital target?
                # Better: Available / needed
                invest_amt = running_capital / slots_needed 
                
                # Cap size slightly to save buffer? No, aggressive!
                if invest_amt < 10000: break
                
                running_capital -= invest_amt
                active_positions.append({
                    'Symbol': pick['Symbol'],
                    'Entry': pick['Price'],
                    'Size': invest_amt,
                    'EntryDate': current_date.date()
                })
        
        # Close remaining
        equity = running_capital
        for pos in active_positions:
            sym = pos['Symbol']
            last_price = float(data_store[sym]['Close'].iloc[-1])
            pnl = (last_price - pos['Entry']) / pos['Entry']
            val = pos['Size'] * (1 + pnl)
            equity += val
            all_trades.append({
                'Symbol': sym, 'Entry': pos['Entry'], 'Exit': last_price,
                'Return': round(pnl*100, 2), 'Profit': round(val - pos['Size'], 0),
                'Reason': "FORCE_CLOSE", 'Days': 0
            })
            
        roi = (equity - self.capital) / self.capital * 100
        print("\n" + "="*70)
        print(f"  V6 TREND RIDER RESULTS (10-Day EMA Exit)")
        print("="*70)
        print(f"Initial:    ₹{self.capital:,}")
        print(f"Final:      ₹{equity:,.0f}")
        print(f"Return:     {roi:.2f}%")
        print(f"Trades:     {len(all_trades)}")
        
        if all_trades:
            df = pd.DataFrame(all_trades)
            os.makedirs('backtest_v6', exist_ok=True)
            df.to_csv("backtest_v6/backtest_2025_results_v6.csv", index=False)

if __name__ == "__main__":
    os.makedirs('backtest_v6', exist_ok=True)
    tester = AlphaZetaBacktesterV6()
    tester.run_trend_simulation()
