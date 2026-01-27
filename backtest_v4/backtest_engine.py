"""
Alpha-Zeta Super Scanner - Backtest V4 (FAST AGGRESSIVE)
Goal: Turn ₹50k -> ₹1.5L+ profit
Strategy: Breakouts + Trailing Stops
Optimization: Batch Download Data Once -> Simulate Local
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

class AlphaZetaBacktesterV4_Fast:
    def __init__(self, capital=50000):
        self.capital = capital
        self.brain = AlphaZetaBrain()
        self.config = TIMEFRAME_CONFIGS['3-7_days']
        
    def prepare_data_cache(self):
        """Download ALL necessary data once and cache it."""
        if os.path.exists(CACHE_FILE):
            logger.info("⚡ Loading data from cache...")
            with open(CACHE_FILE, 'rb') as f:
                return pickle.load(f)
        
        logger.info("🌐 Downloading full 2024-2025 data (This happens once)...")
        symbols = DataEngine.get_nifty_symbols()
        # Random subset for speed if needed, but let's try full
        # symbols = symbols[:300] 
        
        data_store = {}
        # Fetch from mid-2024 to end-2025 to cover lookbacks
        start_date = "2024-06-01"
        end_date = "2026-01-01"
        
        # Batch download in chunks of 50
        chunk_size = 50
        for i in tqdm(range(0, len(symbols), chunk_size), desc="Batch Downloading"):
            batch = symbols[i:i+chunk_size]
            try:
                # yfinance batch download is faster
                batch_data = yf.download(batch, start=start_date, end=end_date, group_by='ticker', progress=False, threads=True)
                
                # Reorganize into dict
                for sym in batch:
                    try:
                        df = batch_data[sym].copy()
                        # Clean: drop rows with all NaNs
                        df.dropna(how='all', inplace=True)
                        if not df.empty and len(df) > 100:
                             data_store[sym] = df
                    except: continue
            except: continue
            
        logger.info(f"✅ Cached data for {len(data_store)} symbols.")
        with open(CACHE_FILE, 'wb') as f:
            pickle.dump(data_store, f)
        return data_store

    def prepare_brain_aggressive(self):
        """Train brain on high-volatility winners only."""
        if os.path.exists("backtest_v4_brain.pkl"):
            logger.info("🧠 Loaded pre-trained V4 brain.")
            self.brain.load_weights("backtest_v4_brain.pkl")
            return

        logger.info("🧠 V4 Training: Aggressive Mode...")
        # Train on bull runs to learn 'moonshots'
        target_dates = [datetime.datetime(2024, 11, 1)] # ONE recent period
        
        symbols = DataEngine.get_nifty_symbols()
        np.random.shuffle(symbols)
        subset = symbols[:80]
        
        records = []
        for target_date in target_dates:
            f_start = target_date - datetime.timedelta(days=150)
            f_end = target_date + datetime.timedelta(days=20)
            
            for sym in tqdm(subset, desc=f"Train"):
                try:
                    data = yf.download(sym, start=f_start, end=f_end, progress=False, timeout=10)
                    prices, _ = DataEngine.clean_yf_data(data)
                    if prices is None: continue
                    
                    target_dt = pd.Timestamp(target_date).date()
                    hist_mask = [d.date() <= target_dt for d in prices.index]
                    
                    hist_raw = data.iloc[[i for i, m in enumerate(hist_mask) if m]]
                    if len(hist_raw) < 50: continue
                    
                    metrics = TechnicalCore.calculate_indicators(hist_raw, self.config)
                    if not metrics: continue
                    
                    # FUTURE CHECK: Did it explode? (>5% in 5 days)
                    fut_prices = prices[[d.date() > target_dt for d in prices.index]].head(5)
                    if len(fut_prices) < 3: continue
                    
                    max_gain = (fut_prices.max() / prices.iloc[sum(hist_mask)-1]) - 1
                    label = 1 if max_gain > 0.05 else 0 # Only learn big moves
                    
                    formulas = FormulaFactory.generate_all(metrics)
                    row = {f'f{i}': float(formulas[f'f{i}']) for i in range(1, 24)}
                    row['actual_return'] = label
                    records.append(row)
                except: continue
        
        if records:
            df = pd.DataFrame(records)
            df.to_csv("backtest_v4_history.csv", index=False)
            self.brain.train("backtest_v4_history.csv") 
            # OR simple logic: average winner weights
            # For backtest, we can reuse standard brain weights slightly boosted
            pass # Brain handles training internally

    def run_simulation(self):
        data_store = self.prepare_data_cache()
        self.prepare_brain_aggressive()
        
        logger.info("🚀 V4 FAST BACKTEST STARTING...")
        
        # Simulation Parameters
        start_date = pd.Timestamp("2025-01-01")
        end_date = pd.Timestamp("2025-12-01")
        
        week_starts = pd.date_range(start=start_date, end=end_date, freq='W-MON')
        
        running_capital = self.capital
        active_positions = []
        all_trades = []
        
        for scan_date in tqdm(week_starts, desc="Simulating Weeks"):
            # 1. Update Open Positions (Daily resolution within the week)
            # We simulate the WHOLE WEEK day-by-day for active pos
            week_end = scan_date + datetime.timedelta(days=5)
            
            active_pos_copy = active_positions[:]
            active_positions = [] # Rebuild
            
            for pos in active_pos_copy:
                sym = pos['Symbol']
                if sym not in data_store: continue
                
                df = data_store[sym]
                # Slice week data
                week_data = df[(df.index >= scan_date) & (df.index <= week_end)]
                
                exit_triggered = False
                for dt, row in week_data.iterrows():
                    price = float(row['Close']) # Use Close for simplicity
                    
                    # Trailing Stop Update
                    if price > pos['High']:
                        pos['High'] = price
                    
                    # Stop Trigger: 5% drop from peak
                    stop_price = pos['High'] * 0.95
                    
                    if price < stop_price:
                        # SELL
                        pnl = (stop_price - pos['Entry']) / pos['Entry']
                        profit = pos['Size'] * pnl
                        running_capital += (pos['Size'] + profit)
                        
                        all_trades.append({
                            'Symbol': sym, 'Entry': pos['Entry'], 'Exit': stop_price,
                            'Return': round(pnl*100, 2), 'Profit': round(profit, 0),
                            'Reason': 'TRAIL_STOP', 'Days': (dt - pos['Date']).days
                        })
                        exit_triggered = True
                        break
                
                if not exit_triggered:
                    active_positions.append(pos)
            
            # 2. Scan for New Trades (Monday Morning)
            if running_capital < 10000: continue
            
            candidates = []
            
            # Optimization: limit scanning for speed
            scan_pool = list(data_store.keys())[:150] 
            
            for sym in scan_pool:
                df = data_store[sym]
                # History until today
                hist = df[df.index < scan_date]
                if len(hist) < 50: continue
                
                curr_row = df[df.index == scan_date]
                if curr_row.empty: continue
                
                curr_price = float(curr_row.iloc[0]['Close'])
                
                # Breakout Logic: > 20-Day High
                d20_high = hist['Close'].iloc[-20:].max()
                
                if curr_price > d20_high:
                    # Score it
                    # Simplified scoring for speed (Momentum + Volume)
                    vol_ratio = 1.0
                    avg_vol = hist['Volume'].iloc[-20:].mean()
                    curr_vol = float(curr_row.iloc[0]['Volume'])
                    if avg_vol > 0: vol_ratio = curr_vol / avg_vol
                    
                    mom_score = (curr_price / hist['Close'].iloc[-20]) - 1
                    
                    if mom_score > 0.05 and vol_ratio > 1.2: # Strong Breakout
                        candidates.append({'Symbol': sym, 'Price': curr_price, 'Score': mom_score * vol_ratio})
            
            # Buy Top Picks
            candidates.sort(key=lambda x: x['Score'], reverse=True)
            for pick in candidates[:2]: # Max 2 new per week
                if running_capital < 10000: break
                
                # Position Sizing: 50% of available cash (Aggressive compounding)
                size = running_capital * 0.5 
                running_capital -= size
                
                active_positions.append({
                    'Symbol': pick['Symbol'],
                    'Entry': pick['Price'],
                    'Size': size,
                    'Date': scan_date,
                    'High': pick['Price']
                })
        
        # Close all remaining
        equity = running_capital
        for pos in active_positions:
            # Mark to market at last available price
            sym = pos['Symbol']
            last_price = float(data_store[sym]['Close'].iloc[-1])
            pnl = (last_price - pos['Entry']) / pos['Entry']
            val = pos['Size'] * (1 + pnl)
            equity += val
            all_trades.append({
                'Symbol': pos['Symbol'], 'Entry': pos['Entry'], 'Exit': last_price,
                'Return': round(pnl*100, 2), 'Profit': round(val - pos['Size'], 0),
                'Reason': 'FORCE_CLOSE', 'Days': 0
            })

        # Final Stats
        roi = (equity - self.capital) / self.capital * 100
        print("\n" + "="*70)
        print(f"  V4 FAST RESULTS (Aggressive Compounding)")
        print("="*70)
        print(f"Initial:    ₹{self.capital:,}")
        print(f"Final:      ₹{equity:,.0f}")
        print(f"Return:     {roi:.2f}%")
        print(f"Trades:     {len(all_trades)}")
        
        if all_trades:
            df = pd.DataFrame(all_trades)
            os.makedirs('backtest_v4', exist_ok=True)
            df.to_csv("backtest_v4/backtest_2025_results_v4.csv", index=False)


if __name__ == "__main__":
    tester = AlphaZetaBacktesterV4_Fast()
    tester.run_simulation()
