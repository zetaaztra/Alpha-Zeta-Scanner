"""
V22: 12-1 ACADEMIC MOMENTUM
Goal: Outperform in 2025 by avoiding the '1-month reversal' trap.
Universe: Nifty 500.
Selection: Top 20 stocks based on (Price[-20] / Price[-252]).
Rebalance: Monthly.
Zero Friction.
"""
import pandas as pd
import numpy as np
import os
import sys
import pickle
from tqdm import tqdm

CACHE_PATH = r"c:\Users\hp\Desktop\Nifty_500\Alpha_Zeta_Super_Scanner\backtest_v4_data.pkl"
INITIAL_CAPITAL = 100000.0

class V22AcademicMomentum:
    def __init__(self):
        self.data_store = {}
        with open(CACHE_PATH, 'rb') as f:
            self.data_store = pickle.load(f)

    def calculate_12_1_momentum(self, df, date):
        hist = df[df.index <= date]
        if len(hist) < 260: return None
        
        # Price 1 month ago / Price 13 months ago (The leading 12 months)
        # Excludes the most recent month to avoid reversal noise
        p_1m = float(hist['Close'].iloc[-21])
        p_13m = float(hist['Close'].iloc[-252])
        
        return (p_1m / p_13m) - 1

    def run(self):
        dates = pd.date_range(start="2025-01-01", end="2025-11-20", freq='ME')
        capital = INITIAL_CAPITAL
        portfolio = []
        
        for dt in tqdm(dates, desc="12-1 Academic Execution"):
            rankings = []
            for sym, df in self.data_store.items():
                if dt not in df.index: continue
                score = self.calculate_12_1_momentum(df, dt)
                if score is not None:
                    rankings.append((sym, score))
            
            rankings.sort(key=lambda x: x[1], reverse=True)
            new_top_20 = [x[0] for x in rankings[:20]]
            
            if portfolio:
                rets = []
                for sym in portfolio:
                    df = self.data_store[sym]
                    # Use closest trading days
                    idx_now = df.index.asof(dt)
                    prev_dt = dates[dates.get_loc(dt)-1]
                    idx_prev = df.index.asof(prev_dt)
                    
                    if idx_now and idx_prev:
                        entry = float(df.loc[idx_prev]['Close'])
                        exit = float(df.loc[idx_now]['Close'])
                        rets.append(exit/entry - 1)
                if rets:
                    capital *= (1 + np.mean(rets))
            
            portfolio = new_top_20

        final_roi = (capital / INITIAL_CAPITAL - 1) * 100
        print(f"\n🎓 V22 12-1 ACADEMIC MOMENTUM ROI: {final_roi:.2f}%")

if __name__ == "__main__":
    V22AcademicMomentum().run()
