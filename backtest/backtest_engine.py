import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import os
import sys
from tqdm import tqdm
import logging

# Import logic from the main app by adding parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import DataEngine, TechnicalCore, FormulaFactory, AlphaZetaBrain, TIMEFRAME_CONFIGS

# Set up logging for backtest
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AlphaZetaBacktester:
    def __init__(self, min_p=666, max_p=1666, min_v=50*1e6):
        self.min_p = min_p
        self.max_p = max_p
        self.min_v = min_v
        self.brain = AlphaZetaBrain()
        self.history_file = "backtest_history.csv"
        self.config = TIMEFRAME_CONFIGS['3-7_days']
        
    def prepare_brain(self):
        """Train the brain using 2024 data to be ready for 2025."""
        logger.info("🧠 Phase 1: Warming up the Brain with 2024 data...")
        # Simulating a Forge/Train from late 2024
        target_date = datetime.datetime(2024, 11, 1)
        symbols = DataEngine.get_nifty_symbols()
        np.random.shuffle(symbols)
        subset = symbols[:100]
        
        f_start = target_date - datetime.timedelta(days=200)
        f_end = target_date + datetime.timedelta(days=14)
        
        records = []
        for sym in tqdm(subset, desc="Warm-up Forge"):
            try:
                data = yf.download(sym, start=f_start, end=f_end, progress=False, timeout=10)
                prices, _ = DataEngine.clean_yf_data(data)
                if prices is None or prices.empty: continue
                
                target_dt_norm = pd.Timestamp(target_date).date()
                idx_dates = [d.date() for d in prices.index]
                hist_mask = [d <= target_dt_norm for d in idx_dates]
                fut_mask = [d > target_dt_norm for d in idx_dates]
                
                hist_prices = prices[hist_mask]
                fut_prices = prices[fut_mask].head(7)
                
                if len(hist_prices) < 60 or len(fut_prices) < 3: continue
                
                hist_raw = data.iloc[[i for i, m in enumerate(hist_mask) if m]]
                metrics = TechnicalCore.calculate_indicators(hist_raw, self.config)
                if not metrics: continue
                
                f_ret = (float(fut_prices.iloc[-1]) / float(hist_prices.iloc[-1])) - 1
                formulas = FormulaFactory.generate_all(metrics)
                row = {f'f{i}': float(formulas[f'f{i}']) for i in range(1, 24)}
                row['actual_return'] = float(f_ret)
                records.append(row)
            except: continue
            
        if records:
            df = pd.DataFrame(records)
            df.to_csv(self.history_file, index=False)
            self.brain.train(self.history_file)
            logger.info("✅ Brain Warmed Up and Ready for 2025.")
        else:
            logger.error("❌ Warm-up Failed. Using default weights.")

    def run_backtest_2025(self):
        """Simulate month-by-month scanning in 2025."""
        logger.info("🚀 Phase 2: Simulating 2025 Month-by-Month...")
        
        # Test Dates: First Monday of each month in 2025
        test_dates = [
            datetime.datetime(2025, 1, 6), datetime.datetime(2025, 2, 3),
            datetime.datetime(2025, 3, 3), datetime.datetime(2025, 4, 7),
            datetime.datetime(2025, 5, 5), datetime.datetime(2025, 6, 2),
            datetime.datetime(2025, 7, 7), datetime.datetime(2025, 8, 4),
            datetime.datetime(2025, 9, 1), datetime.datetime(2025, 10, 6),
            datetime.datetime(2025, 11, 3), datetime.datetime(2025, 12, 1)
        ]
        
        all_trades = []
        symbols = DataEngine.get_nifty_symbols()
        
        for scan_date in test_dates:
            logger.info(f"--- Scanning on {scan_date.date()} ---")
            picks = []
            
            # 1. SCANNING
            scan_start = scan_date - datetime.timedelta(days=120)
            scan_end = scan_date + datetime.timedelta(days=10) # Buffer to see future
            
            for sym in tqdm(symbols[:200], desc=f"Scanning {scan_date.date().strftime('%b')}"): # Subset for speed
                try:
                    data = yf.download(sym, start=scan_start, end=scan_end, progress=False, timeout=10)
                    prices, _ = DataEngine.clean_yf_data(data)
                    if prices is None: continue
                    
                    target_dt_norm = scan_date.date()
                    idx_dates = [d.date() for d in prices.index]
                    
                    # Ensure the scan date exists in data or find closest previous
                    if target_dt_norm not in idx_dates: continue
                    
                    hist_mask = [d <= target_dt_norm for d in idx_dates]
                    fut_mask = [d > target_dt_norm for d in idx_dates]
                    
                    hist_prices = prices[hist_mask]
                    fut_prices = prices[fut_mask].head(7)
                    
                    if len(hist_prices) < 60 or len(fut_prices) < 3: continue
                    
                    # Calculate Metrics on Scan Day
                    hist_raw = data.iloc[[i for i, m in enumerate(hist_mask) if m]]
                    metrics = TechnicalCore.calculate_indicators(hist_raw, self.config)
                    if not metrics: continue
                    
                    # Apply User Filters
                    if not (self.min_p <= metrics['price'] <= self.max_p): continue
                    if metrics['avg_vol'] < self.min_v: continue
                    if metrics['hurst'] < 0.42: continue
                    
                    # Score
                    formulas = FormulaFactory.generate_all(metrics)
                    score = sum(formulas[f'f{i}'] * self.brain.weights[i-1] for i in range(1, 24))
                    
                    picks.append({
                        'Symbol': sym, 'Score': score, 'Scan_Price': metrics['price'],
                        'Exit_Price': float(fut_prices.iloc[-1]),
                        'Date': scan_date.date()
                    })
                except: continue
            
            if picks:
                top_3 = sorted(picks, key=lambda x: x['Score'], reverse=True)[:3]
                for p in top_3:
                    p['Return_Pct'] = (p['Exit_Price'] / p['Scan_Price']) - 1
                    all_trades.append(p)
                    logger.info(f"   Pick: {p['Symbol']} | Score: {round(p['Score'],2)} | Ret: {round(p['Return_Pct']*100, 2)}%")
            else:
                logger.info("   No stocks matched on this date.")

        # FINAL REPORTing
        if all_trades:
            df = pd.DataFrame(all_trades)
            avg_ret = df['Return_Pct'].mean()
            win_rate = (df['Return_Pct'] > 0).mean()
            total_comp = (1 + df['Return_Pct']).prod() - 1
            
            print("\n" + "="*60)
            print("  BRUTAL 2025 BACKTEST REPORT")
            print("="*60)
            print(f"Strategy:    3-7 Days Holding")
            print(f"Filters:     ₹{self.min_p}-₹{self.max_p} | Vol: {self.min_v/1e6}M")
            print(f"Total Trades: {len(df)}")
            print(f"Win Rate:     {round(win_rate*100, 2)}%")
            print(f"Avg Return:   {round(avg_ret*100, 2)}% per trade")
            print(f"Total Return: {round(total_comp*100, 2)}% (Cumulative)")
            print("="*60)
            df.to_csv("backtest/backtest_2025_results.csv", index=False)
            print(f"Full details saved to: backtest/backtest_2025_results.csv")
        else:
            print("❌ Backtest failed: No trades were matched across the simulation.")

if __name__ == "__main__":
    if not os.path.exists('backtest'): os.makedirs('backtest')
    tester = AlphaZetaBacktester()
    tester.prepare_brain()
    tester.run_backtest_2025()
