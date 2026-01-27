"""
V27: THE SECTOR SOVEREIGN (Prop Firm Alpha)
Goal: 50%+ ROI using Sector Rotation and 'Institutional Accumulation' (Closing Range).
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

class V27SectorSovereign:
    def __init__(self):
        self.data_store = {}
        with open(CACHE_PATH, 'rb') as f:
            self.data_store = pickle.load(f)
        self.sectors = {} # sym -> sector name (mocked or extracted)

    def calculate_prop_momentum(self, df, date):
        hist = df[df.index <= date]
        if len(hist) < 60: return None
        
        # 1. Weekly Return (Short term momentum)
        ret_1w = (hist['Close'].iloc[-1] / hist['Close'].iloc[-5]) - 1
        
        # 2. Institutional Footprint: Closing Range (High - Low vs Close)
        # CR = (Close - Low) / (High - Low)
        # CR > 0.8 means institutions bought all day and closed it at the top.
        day_high = hist['High'].iloc[-1]
        day_low = hist['Low'].iloc[-1]
        day_close = hist['Close'].iloc[-1]
        
        closing_range = (day_close - day_low) / (day_high - day_low + 1e-6)
        
        # 3. Volume Surge (Relative to 20-day mean)
        vol_surge = hist['Volume'].iloc[-1] / hist['Volume'].rolling(20).mean().iloc[-1]
        
        # Combined Prop Score
        if closing_range > 0.7 and vol_surge > 1.2:
            return ret_1w * closing_range * vol_surge
        return None

    def run(self):
        # Simulation (2025)
        dates = pd.date_range(start="2025-01-01", end="2025-11-20", freq='W-MON')
        capital = INITIAL_CAPITAL
        
        for dt in tqdm(dates, desc="Sector Sovereign Execution"):
            rankings = []
            for sym, df in self.data_store.items():
                if dt not in df.index: continue
                score = self.calculate_prop_momentum(df, dt)
                if score is not None and score > 0:
                    rankings.append((sym, score))
            
            if not rankings: continue
            
            rankings.sort(key=lambda x: x[1], reverse=True)
            top = rankings[:10]
            
            # Predict return for the next week
            rets = []
            for sym, score in top:
                df = self.data_store[sym]
                idx = df.index.get_loc(dt)
                if idx + 5 < len(df):
                    ret = (df.iloc[idx + 5]['Close'] / df.loc[dt]['Close']) - 1
                    rets.append(ret)
            
            if rets:
                capital *= (1 + np.mean(rets))

        final_roi = (capital / INITIAL_CAPITAL - 1) * 100
        print(f"\n🛸 V27 SECTOR SOVEREIGN ROI (Zero Fees): {final_roi:.2f}%")

if __name__ == "__main__":
    V27SectorSovereign().run()
