"""
V28: THE WORLDQUANT ALPHA 101 (Hybrid)
Goal: 50%+ ROI using Institutional Intra-day Accumulation (Alpha #101).
Universe: Nifty 500.
Rebalance: Weekly.
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

class V28WorldQuantAlpha:
    def __init__(self):
        self.data_store = {}
        with open(CACHE_PATH, 'rb') as f:
            self.data_store = pickle.load(f)

    def calculate_alpha_101(self, df, date):
        hist = df[df.index <= date]
        if len(hist) < 20: return None
        
        # Alpha #101 formula: (close - open) / ((high - low) + .001)
        # We take the mean over the last 20 days to find persistent accumulation
        c = hist['Close'].iloc[-20:]
        o = hist['Open'].iloc[-20:]
        h = hist['High'].iloc[-20:]
        l = hist['Low'].iloc[-20:]
        
        scores = ((c - o) / ((h - l) + 0.001))
        return scores.mean()

    def run(self):
        # Simulation (2025)
        dates = pd.date_range(start="2025-01-01", end="2025-11-20", freq='W-MON')
        capital = INITIAL_CAPITAL
        
        for dt in tqdm(dates, desc="WorldQuant Alpha Execution"):
            rankings = []
            for sym, df in self.data_store.items():
                if dt not in df.index: continue
                score = self.calculate_alpha_101(df, dt)
                if score is not None:
                    rankings.append((sym, score))
            
            if not rankings: continue
            
            rankings.sort(key=lambda x: x[1], reverse=True)
            top = rankings[:10]
            
            # Predict return for the next week
            rets = []
            for sym, _ in top:
                df = self.data_store[sym]
                idx = df.index.get_loc(dt)
                if idx + 5 < len(df):
                    ret = (df.iloc[idx + 5]['Close'] / df.loc[dt]['Close']) - 1
                    rets.append(ret)
            
            if rets:
                capital *= (1 + np.mean(rets))

        final_roi = (capital / INITIAL_CAPITAL - 1) * 100
        print(f"\n🧬 V28 WORLDQUANT ALPHA 101 ROI: {final_roi:.2f}%")

if __name__ == "__main__":
    V28WorldQuantAlpha().run()
