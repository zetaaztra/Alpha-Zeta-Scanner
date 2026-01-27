"""
V14: THE TITAN SHIFT (Operation 50)
Goal: 50%+ ROI by catching Macro Trends (RS > 95, 3-Month Hold).
Friction: 0.5% total per trade.
"""
import pandas as pd
import numpy as np
import os
import sys
import pickle
import logging
from tqdm import tqdm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import TechnicalCore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

CACHE_PATH = r"c:\Users\hp\Desktop\Nifty_500\Alpha_Zeta_Super_Scanner\backtest_v4_data.pkl"
INITIAL_CAPITAL = 100000.0
SLIPPAGE_PCT = 0.005 

class V14TitanShift:
    def __init__(self):
        self.data_store = {}
        self.market_index = None
        self.capital = INITIAL_CAPITAL
        self.portfolio = []
        self.trade_log = []
        self.equity_curve = []

    def load_data(self):
        if os.path.exists(CACHE_PATH):
             with open(CACHE_PATH, 'rb') as f:
                 self.data_store = pickle.load(f)
             logger.info(f"Loaded {len(self.data_store)} stocks.")
        else:
             logger.error("Cache not found.")
             sys.exit(1)

    def generate_market_proxy(self):
        """Creates a synthetic Nifty 500 Index for RS calculation."""
        logger.info("Generating Synthetic Nifty 500 Index...")
        all_rets = []
        for sym, df in self.data_store.items():
            if 'Close' in df.columns:
                all_rets.append(df['Close'].pct_change())
        self.market_index = (1 + pd.concat(all_rets, axis=1).mean(axis=1).fillna(0)).cumprod() * 100

    def calculate_rs_rank(self, date):
        """Calculates RS percentile rank for all stocks on a given date."""
        rs_scores = []
        for sym, df in self.data_store.items():
            if date not in df.index: continue
            hist = df[df.index <= date]
            if len(hist) < 125: continue # 6 months data
            
            # 6-Month Return (Macro Strength)
            ret_6m = (float(hist['Close'].iloc[-1]) / float(hist['Close'].iloc[-126])) - 1
            rs_scores.append((sym, ret_6m))
        
        if not rs_scores: return {}
        
        # Rankings
        df_rs = pd.DataFrame(rs_scores, columns=['sym', 'score'])
        df_rs['rank'] = df_rs['score'].rank(pct=True) * 100
        return dict(zip(df_rs['sym'], df_rs['rank']))

    def run(self):
        self.load_data()
        self.generate_market_proxy()
        
        # Quarter-based Scan (Hold for 60 business days / ~3 months)
        test_dates = pd.date_range(start="2025-01-01", end="2025-10-01", freq='QS') # Quarterly Start
        
        for date in tqdm(test_dates, desc="V14 Titan Quarter Execution"):
            # 1. Selection (RS > 95)
            # Find a valid market date if holiday
            actual_date = date
            while actual_date not in self.market_index.index and actual_date < self.market_index.index[-1]:
                actual_date += pd.Timedelta(days=1)
            
            rs_ranks = self.calculate_rs_rank(actual_date)
            titans = [sym for sym, rank in rs_ranks.items() if rank >= 95]
            
            if not titans: continue
            
            # Allocation (Top 10 Titans)
            # Limit to 10 stocks for risk diversification
            top_titans = titans[:10]
            
            # Calculate Quarterly Performance for these titans
            for sym in top_titans:
                df = self.data_store[sym]
                if actual_date not in df.index: continue
                
                entry_price = float(df.loc[actual_date]['Close'])
                # Entry with Slippage
                net_entry = entry_price * (1 + (SLIPPAGE_PCT/2))
                
                # Find exit date (60 days later)
                exit_idx = df.index.get_loc(actual_date) + 60
                if exit_idx >= len(df): exit_idx = len(df) - 1
                exit_date = df.index[exit_idx]
                exit_price = float(df.loc[exit_date]['Close'])
                # Exit with Slippage
                net_exit = exit_price * (1 - (SLIPPAGE_PCT/2))
                
                ret = (net_exit / net_entry) - 1
                self.trade_log.append({'Symbol': sym, 'Entry': actual_date, 'Exit': exit_date, 'Return': ret})
        
        # Reporting
        if self.trade_log:
            df_t = pd.DataFrame(self.trade_log)
            # We assume equal weight per quarter
            # Group by entry quarter and average
            df_t['Quarter'] = pd.to_datetime(df_t['Entry']).dt.to_period('Q')
            q_rets = df_t.groupby('Quarter')['Return'].mean()
            
            total_roi = (np.prod(q_rets + 1) - 1) * 100
            win_rate = (df_t['Return'] > 0).mean() * 100
            
            print("\n" + "="*60)
            print("  🪐 V14 TITAN SHIFT: MACRO VERDICT")
            print("="*60)
            print(f"Algorithm:         RS > 95 + 3M Macro Hold")
            print(f"Total Trades:      {len(df_t)}")
            print(f"Win Rate:          {win_rate:.1f}%")
            print(f"Avg Trade:         {df_t['Return'].mean()*100:.2f}%")
            print("-" * 60)
            print(f"ANNUALIZED ROI:   {total_roi:.2f}%")
            print("="*60)
            
            df_t.to_csv("backtest/v14_titan_results.csv", index=False)
        else:
            print("❌ No trades executed.")

if __name__ == "__main__":
    V14TitanShift().run()
