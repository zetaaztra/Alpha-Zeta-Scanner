"""
Alpha-Zeta Super Scanner - Backtest V3 (Realistic Target-Based Exits)
Simulates real trading:
- Split ₹50,000 across top 3 picks per month
- Check price DAILY
- Exit immediately if +1.5% profit target is hit
- Max hold 7 days, then exit at whatever price
"""
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import os
import sys
from tqdm import tqdm
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import DataEngine, TechnicalCore, FormulaFactory, AlphaZetaBrain, TIMEFRAME_CONFIGS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AlphaZetaBacktesterV3:
    """V3: Realistic backtest with daily exit checks and profit targets."""
    
    def __init__(self, capital=50000, min_p=666, max_p=1666, min_v=50*1e6, profit_target=0.015):
        self.capital = capital  # ₹50,000
        self.min_p = min_p
        self.max_p = max_p
        self.min_v = min_v
        self.profit_target = profit_target  # 1.5% = ₹250-400 on ₹16k position
        self.brain = AlphaZetaBrain()
        self.config = TIMEFRAME_CONFIGS['3-7_days']
        
    def prepare_brain(self):
        """Quick brain warmup using late 2024 data."""
        logger.info("🧠 V3 Warming up brain with 2024 data...")
        target_dates = [
            datetime.datetime(2024, 6, 1),
            datetime.datetime(2024, 10, 1),
        ]
        
        symbols = DataEngine.get_nifty_symbols()
        np.random.shuffle(symbols)
        subset = symbols[:60]
        
        all_records = []
        for target_date in target_dates:
            f_start = target_date - datetime.timedelta(days=200)
            f_end = target_date + datetime.timedelta(days=14)
            
            for sym in tqdm(subset, desc=f"Warmup {target_date.strftime('%b %Y')}"):
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
            df.to_csv("backtest_v3_history.csv", index=False)
            self.brain.train("backtest_v3_history.csv")
            logger.info(f"✅ Brain trained on {len(all_records)} records.")

    def simulate_daily_exit(self, prices_series, entry_price, max_days=7):
        """
        Simulate daily price checks. Exit when:
        1. Price hits profit target (+1.5%), OR
        2. Max hold days reached
        
        Returns: (exit_price, days_held, exit_reason)
        """
        for day in range(1, min(max_days + 1, len(prices_series))):
            day_price = float(prices_series.iloc[day])
            day_return = (day_price / entry_price) - 1
            
            if day_return >= self.profit_target:
                return day_price, day, "TARGET_HIT"
        
        # Max days reached, exit at last available price
        exit_idx = min(max_days, len(prices_series) - 1)
        return float(prices_series.iloc[exit_idx]), exit_idx, "MAX_DAYS"

    def run_backtest(self):
        """Simulate month-by-month with realistic exits."""
        logger.info("🚀 V3 BACKTEST: Realistic Daily Exit Simulation")
        
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
        running_capital = self.capital
        
        for scan_date in test_dates:
            logger.info(f"--- Scanning on {scan_date.date()} | Capital: ₹{running_capital:.0f} ---")
            picks = []
            
            scan_start = scan_date - datetime.timedelta(days=120)
            scan_end = scan_date + datetime.timedelta(days=10)
            
            for sym in tqdm(symbols[:200], desc=f"V3 Scanning {scan_date.date().strftime('%b')}"):
                try:
                    data = yf.download(sym, start=scan_start, end=scan_end, progress=False, timeout=10)
                    prices, _ = DataEngine.clean_yf_data(data)
                    if prices is None or len(prices) < 60: continue
                    
                    target_dt_norm = scan_date.date()
                    idx_dates = [d.date() for d in prices.index]
                    if target_dt_norm not in idx_dates: continue
                    
                    hist_mask = [d <= target_dt_norm for d in idx_dates]
                    fut_mask = [d > target_dt_norm for d in idx_dates]
                    
                    hist_prices = prices[hist_mask]
                    fut_prices = prices[fut_mask]
                    
                    if len(hist_prices) < 60 or len(fut_prices) < 3: continue
                    
                    hist_raw = data.iloc[[i for i, m in enumerate(hist_mask) if m]]
                    metrics = TechnicalCore.calculate_indicators(hist_raw, self.config)
                    if not metrics: continue
                    
                    # Filters
                    if not (self.min_p <= metrics['price'] <= self.max_p): continue
                    if metrics['avg_vol'] < self.min_v: continue
                    if metrics['hurst'] < 0.42: continue
                    
                    formulas = FormulaFactory.generate_all(metrics)
                    score = sum(formulas[f'f{i}'] * self.brain.weights[i-1] for i in range(1, 24))
                    
                    picks.append({
                        'Symbol': sym, 'Score': score, 'Entry_Price': metrics['price'],
                        'Future_Prices': fut_prices,
                        'Date': scan_date.date()
                    })
                except: continue
            
            # Take top 3 picks and simulate trades
            if picks:
                top_3 = sorted(picks, key=lambda x: x['Score'], reverse=True)[:3]
                position_size = running_capital / 3  # Split capital
                
                for p in top_3:
                    entry = p['Entry_Price']
                    exit_price, days_held, reason = self.simulate_daily_exit(
                        p['Future_Prices'], entry, max_days=7
                    )
                    ret_pct = (exit_price / entry) - 1
                    profit_rupees = position_size * ret_pct
                    
                    trade = {
                        'Symbol': p['Symbol'].replace('.NS', ''),
                        'Date': p['Date'],
                        'Entry': round(entry, 2),
                        'Exit': round(exit_price, 2),
                        'Days_Held': days_held,
                        'Exit_Reason': reason,
                        'Return_Pct': round(ret_pct * 100, 2),
                        'Profit_Rs': round(profit_rupees, 0)
                    }
                    all_trades.append(trade)
                    running_capital += profit_rupees
                    
                    logger.info(f"   {trade['Symbol']}: {trade['Exit_Reason']} in {trade['Days_Held']}d | {trade['Return_Pct']}% | ₹{trade['Profit_Rs']}")
            else:
                logger.info("   No stocks matched on this date.")

        # FINAL REPORT
        if all_trades:
            df = pd.DataFrame(all_trades)
            win_rate = (df['Return_Pct'] > 0).mean()
            avg_days = df['Days_Held'].mean()
            target_hits = (df['Exit_Reason'] == 'TARGET_HIT').sum()
            
            total_profit = running_capital - self.capital
            total_return = (running_capital / self.capital) - 1
            
            print("\n" + "="*70)
            print("  ALPHA-ZETA V3 BACKTEST REPORT (Realistic Daily Exits)")
            print("="*70)
            print(f"Initial Capital:   ₹{self.capital:,}")
            print(f"Final Capital:     ₹{running_capital:,.0f}")
            print(f"Total Profit:      ₹{total_profit:,.0f}")
            print(f"Total Return:      {round(total_return*100, 2)}%")
            print("-"*70)
            print(f"Total Trades:      {len(df)}")
            print(f"Win Rate:          {round(win_rate*100, 2)}%")
            print(f"Avg Days Held:     {round(avg_days, 1)} days")
            print(f"Target Hits:       {target_hits} / {len(df)} ({round(target_hits/len(df)*100, 1)}%)")
            print("="*70)
            
            os.makedirs('backtest_v3', exist_ok=True)
            df.to_csv("backtest_v3/backtest_2025_results_v3.csv", index=False)
            print(f"Full details saved to: backtest_v3/backtest_2025_results_v3.csv")
        else:
            print("❌ Backtest failed: No trades matched.")

if __name__ == "__main__":
    os.makedirs('backtest_v3', exist_ok=True)
    tester = AlphaZetaBacktesterV3(capital=50000, profit_target=0.015)
    tester.prepare_brain()
    tester.run_backtest()
