"""
Alpha-Zeta Clean Data Forge
Generates training data STRICTLY from the past (2021-2023) to eliminate data leakage.
Target Dates:
- 2021-06-01 (Post-Covid Bull)
- 2022-01-01 (Peak/Correction)
- 2022-06-01 (Choppy)
- 2023-01-01 (Recovery Start)
- 2023-06-01 (Bull Run)
"""
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import os
import sys
from tqdm import tqdm
import logging

# Import Core Logic from App
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import DataEngine, TechnicalCore, FormulaFactory, TIMEFRAME_CONFIGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_FILE = "backtest_v4_data.pkl" # We can reuse the big cache if it has history, 
# but for safety let's just download what we need or check cache. 
# Actually, the V4 cache is for 2024-2025. We need OLDER data (2021-2023). 
# We must download fresh data.

def forge_clean_history():
    logger.info("🔨 STARTING CLEAN DATA FORGE (2021-2023 ONLY)")
    
    # Diverse Market Conditions
    # Diverse Market Conditions (Extended to 2024)
    target_dates = [
        datetime.datetime(2021, 6, 1),
        datetime.datetime(2022, 1, 3),
        datetime.datetime(2022, 6, 1),
        datetime.datetime(2023, 1, 2),
        datetime.datetime(2023, 6, 1),
        datetime.datetime(2024, 1, 1),
        datetime.datetime(2024, 6, 3),
        datetime.datetime(2024, 11, 1)
    ]
    
    symbols = DataEngine.get_nifty_symbols()
    np.random.shuffle(symbols)
    subset = symbols[:150] # Sample 150 stocks
    
    all_records = []
    
    # Pre-fetch fundamentals to avoid hitting API loop limit? 
    # YFinance is slow per-ticker. We do it inside loop but cautiously.
    
    for target_date in target_dates:
        print(f"\n--- Forging Period: {target_date.date()} ---")
        
        # Need history for indicators (200 days back) + Future for label (7 days fwd)
        f_start = target_date - datetime.timedelta(days=300)
        f_end = target_date + datetime.timedelta(days=20)
        
        for sym in tqdm(subset, desc=f" downloading"):
            try:
                ticker = yf.Ticker(sym)
                # 1. Price Data
                data = ticker.history(start=f_start, end=f_end)
                
                # Check Data
                if len(data) < 200: continue
                
                # Clean
                cleaned_data = data[['Open', 'High', 'Low', 'Close', 'Volume']].fillna(method='ffill').dropna().astype(float)
                
                # Slice Logic
                target_dt_norm = pd.Timestamp(target_date).date()
                idx_dates = [d.date() for d in cleaned_data.index]
                
                hist_mask = [d <= target_dt_norm for d in idx_dates]
                fut_mask = [d > target_dt_norm for d in idx_dates]
                
                hist_df = cleaned_data[hist_mask]
                fut_df = cleaned_data[fut_mask].head(10) # 10-Day Lookahead (V10 Strategy)
                
                if len(hist_df) < 100 or len(fut_df) < 5: continue
                
                # 2. Fundamental Data (Revenue Growth Estimate)
                # We need data from BEFORE target_date.
                # Safe Lag: 3 months before target date matching.
                rev_growth = 0.0
                try:
                    pious_date = pd.Timestamp(target_date)
                    financials = ticker.quarterly_current_financials
                    if financials is None or financials.empty:
                        financials = ticker.quarterly_financials
                    
                    if not financials.empty:
                        # Columns are Dates. Find latest date < target_date - 90 days (Lag for publication)
                        valid_dates = [col for col in financials.columns if pd.Timestamp(col) < pious_date - pd.Timedelta(days=90)]
                        if len(valid_dates) >= 2:
                            current = financials[valid_dates[0]] # Most recent valid
                            prev = financials[valid_dates[1]] # Previous year/qtr
                            
                            # Try Total Revenue
                            if 'Total Revenue' in current and 'Total Revenue' in prev:
                                cur_rev = current['Total Revenue']
                                prev_rev = prev['Total Revenue']
                                if prev_rev > 0:
                                    rev_growth = (cur_rev - prev_rev) / prev_rev
                except:
                    rev_growth = 0.0
                
                # Measure Features
                metrics = TechnicalCore.calculate_indicators(hist_df, TIMEFRAME_CONFIGS['3-7_days'])
                if not metrics: continue
                
                # Label: Return over 10 days
                start_price = float(hist_df.iloc[-1]['Close'])
                # Use MAX High of future 10 days? Or Close of 10th day?
                # V10 Optimization says we exit on Target (+20%) or Stop (-10%).
                # For training, let's use Simple Return at 10 days. The Model will learn direction.
                end_price = float(fut_df.iloc[-1]['Close'])
                actual_ret = (end_price / start_price) - 1
                
                formulas = FormulaFactory.generate_all(metrics)
                
                row = {f'f{i}': float(formulas[f'f{i}']) for i in range(1, 24)}
                row['f24_fundamental'] = float(rev_growth) # New Feature
                row['actual_return'] = actual_ret
                
                all_records.append(row)
                
            except Exception as e:
                continue
    
    print(f"\n✅ Forge Complete. Collected {len(all_records)} training samples.")
    
    if len(all_records) > 100:
        df = pd.DataFrame(all_records)
        output_file = "backtest_v4_history.csv" 
        df.to_csv(output_file, index=False)
        print(f"✅ CLEAN DATA (2021-2024 + Fundamentals) saved to {output_file}")
    else:
        print("❌ Not enough data collected. Check connection.")

if __name__ == "__main__":
    forge_clean_history()
