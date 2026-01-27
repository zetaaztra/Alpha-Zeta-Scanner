"""
V21: THE MI-50 HYBRID (Rotational Momentum)
Goal: 50%+ ROI based on the acclaimed 'Mi 50' logic.
Universe: Nifty 500.
Selection: Top 50 stocks by Normalized Momentum Score.
Rebalance: Weekly.
Zero Friction as requested.
"""
import pandas as pd
import numpy as np
import os
import sys
import pickle
from tqdm import tqdm

CACHE_PATH = r"c:\Users\hp\Desktop\Nifty_500\Alpha_Zeta_Super_Scanner\backtest_v4_data.pkl"
INITIAL_CAPITAL = 100000.0

class V21Mi50Hybrid:
    def __init__(self):
        self.data_store = {}
        with open(CACHE_PATH, 'rb') as f:
            self.data_store = pickle.load(f)
        logger.info(f"Loaded {len(self.data_store)} stocks.")

    def calculate_momentum_score(self, df, date):
        hist = df[df.index <= date]
        if len(hist) < 252: return None
        
        # 1. 6-Month and 12-Month Returns
        ret_6m = (hist['Close'].iloc[-1] / hist['Close'].iloc[-126]) - 1
        ret_12m = (hist['Close'].iloc[-1] / hist['Close'].iloc[-252]) - 1
        
        # 2. Volatility Normalization (Annualized StdDev)
        vol = hist['Close'].pct_change().iloc[-252:].std() * np.sqrt(252)
        
        # 3. Normalized Momentum Score (Official Nifty 500 Momentum logic)
        score = (0.5 * ret_6m + 0.5 * ret_12m) / (vol + 0.01)
        
        return score

    def run(self):
        # 2025 Simulation
        dates = pd.date_range(start="2025-01-01", end="2025-11-20", freq='W-MON')
        capital = INITIAL_CAPITAL
        portfolio = [] # Stock list
        
        for dt in tqdm(dates, desc="Mi-50 Rotational Execution"):
            # 1. RANK ENTIRE NIFTY 500
            rankings = []
            for sym, df in self.data_store.items():
                if dt not in df.index: continue
                score = self.calculate_momentum_score(df, dt)
                if score is not None:
                    rankings.append((sym, score))
            
            rankings.sort(key=lambda x: x[1], reverse=True)
            new_top_50 = [x[0] for x in rankings[:50]]
            
            # 2. CALCULATE RETURNS OF PREVIOUS WEEK'S TOP 50
            if portfolio:
                rets = []
                for sym in portfolio:
                    df = self.data_store[sym]
                    idx = df.index.get_loc(dt)
                    # We look at the return from PREVIOUS scan to THIS scan
                    prev_dt = dates[dates.get_loc(dt)-1]
                    entry = float(df.loc[prev_dt]['Close'])
                    exit = float(df.loc[dt]['Close'])
                    rets.append(exit/entry - 1)
                
                capital *= (1 + np.mean(rets))
            
            # 3. ROTATE (New Top 50 for next week)
            portfolio = new_top_50

        final_roi = (capital / INITIAL_CAPITAL - 1) * 100
        print(f"\n🌪️ V21 MI-50 HYBRID ROI (Zero Fees): {final_roi:.2f}%")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    V21Mi50Hybrid().run()
