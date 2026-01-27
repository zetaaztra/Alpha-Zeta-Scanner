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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AlphaZetaBacktesterV2:
    """V2 Backtester with Multi-Period Training and Reduced Volume"""
    def __init__(self, min_p=666, max_p=1666, min_v=30*1e6): # Volume reduced to 30M
        self.min_p = min_p
        self.max_p = max_p
        self.min_v = min_v
        self.brain = AlphaZetaBrain()
        self.history_file = "backtest_v2_history.csv"
        self.config = TIMEFRAME_CONFIGS['3-7_days']
        
    def prepare_brain_multi_period(self):
        """Train the brain on MULTIPLE periods: 2024 Crash + 2025 Bull."""
        logger.info("🔥 V2 Phase 1: Multi-Period Brain Training...")
        
        target_dates = [
            datetime.datetime(2024, 6, 1),   # 2024 Market Correction
            datetime.datetime(2024, 10, 1),  # 2024 Recovery
            datetime.datetime(2025, 3, 1),   # 2025 Mid-Bull
        ]
        
        symbols = DataEngine.get_nifty_symbols()
        np.random.shuffle(symbols)
        subset = symbols[:80] # Smaller sample for faster training
        
        all_records = []
        
        for target_date in target_dates:
            logger.info(f"--- Forging from {target_date.date()} ---")
            f_start = target_date - datetime.timedelta(days=200)
            f_end = target_date + datetime.timedelta(days=14)
            
            for sym in tqdm(subset, desc=f"Period {target_date.strftime('%b %Y')}"):
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
                    all_records.append(row)
                except: continue
        
        if all_records:
            df = pd.DataFrame(all_records)
            df.to_csv(self.history_file, index=False)
            self.brain.train(self.history_file)
            logger.info(f"✅ V2 Brain Trained on {len(all_records)} multi-period records.")
        else:
            logger.error("❌ Multi-Period Training Failed.")

    def run_backtest_2025(self):
        """Simulate month-by-month scanning in 2025 with V2 improvements."""
        logger.info("🚀 V2 Phase 2: Simulating 2025 Month-by-Month...")
        
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
            
            scan_start = scan_date - datetime.timedelta(days=120)
            scan_end = scan_date + datetime.timedelta(days=10)
            
            for sym in tqdm(symbols[:200], desc=f"Scanning {scan_date.date().strftime('%b')}"):
                try:
                    data = yf.download(sym, start=scan_start, end=scan_end, progress=False, timeout=10)
                    prices, _ = DataEngine.clean_yf_data(data)
                    if prices is None: continue
                    
                    target_dt_norm = scan_date.date()
                    idx_dates = [d.date() for d in prices.index]
                    
                    if target_dt_norm not in idx_dates: continue
                    
                    hist_mask = [d <= target_dt_norm for d in idx_dates]
                    fut_mask = [d > target_dt_norm for d in idx_dates]
                    
                    hist_prices = prices[hist_mask]
                    fut_prices = prices[fut_mask].head(7)
                    
                    if len(hist_prices) < 60 or len(fut_prices) < 3: continue
                    
                    hist_raw = data.iloc[[i for i, m in enumerate(hist_mask) if m]]
                    metrics = TechnicalCore.calculate_indicators(hist_raw, self.config)
                    if not metrics: continue
                    
                    # V2 Filters (30M Volume)
                    if not (self.min_p <= metrics['price'] <= self.max_p): continue
                    if metrics['avg_vol'] < self.min_v: continue
                    if metrics['hurst'] < 0.42: continue
                    
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
                    logger.info(f"   V2 Pick: {p['Symbol']} | Score: {round(p['Score'],2)} | Ret: {round(p['Return_Pct']*100, 2)}%")
            else:
                logger.info("   No stocks matched on this date.")

        # FINAL REPORT
        if all_trades:
            df = pd.DataFrame(all_trades)
            avg_ret = df['Return_Pct'].mean()
            win_rate = (df['Return_Pct'] > 0).mean()
            total_comp = (1 + df['Return_Pct']).prod() - 1
            
            print("\n" + "="*60)
            print("  BRUTAL 2025 BACKTEST V2 REPORT (Multi-Period + Vol 30M)")
            print("="*60)
            print(f"Strategy:    3-7 Days Holding")
            print(f"Filters:     ₹{self.min_p}-₹{self.max_p} | Vol: {self.min_v/1e6}M")
            print(f"Total Trades: {len(df)}")
            print(f"Win Rate:     {round(win_rate*100, 2)}%")
            print(f"Avg Return:   {round(avg_ret*100, 2)}% per trade")
            print(f"Total Return: {round(total_comp*100, 2)}% (Cumulative)")
            print("="*60)
            os.makedirs('backtest_v2', exist_ok=True)
            df.to_csv("backtest_v2/backtest_2025_results_v2.csv", index=False)
            print(f"Full details saved to: backtest_v2/backtest_2025_results_v2.csv")
        else:
            print("❌ Backtest V2 failed: No trades were matched.")

if __name__ == "__main__":
    os.makedirs('backtest_v2', exist_ok=True)
    tester = AlphaZetaBacktesterV2()
    tester.prepare_brain_multi_period()
    tester.run_backtest_2025()
