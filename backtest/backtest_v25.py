"""
V25: THE 2023 TIME MACHINE
Goal: Test Filter 1 on the 2023 Bull Run to see if it explains the "67%+" memories.
Universe: Nifty 500.
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

class V25TimeMachine:
    def __init__(self):
        self.data_store = {}
        with open(CACHE_PATH, 'rb') as f:
            self.data_store = pickle.load(f)

    def calculate_filter1(self, df, date):
        hist = df[df.index <= date]
        if len(hist) < 60: return None
        close = hist['Close']
        curr = float(close.iloc[-1])
        
        # Simple Momentum
        r_s = (curr / float(close.iloc[-20])) - 1
        return r_s if curr > close.rolling(50).mean().iloc[-1] else None

    def run(self):
        # 2023 FULL YEAR
        dates = pd.date_range(start="2023-01-01", end="2023-12-31", freq='W-MON')
        capital = INITIAL_CAPITAL
        
        for dt in tqdm(dates, desc="2023 Time Machine"):
            rankings = []
            for sym, df in self.data_store.items():
                if dt not in df.index: continue
                score = self.calculate_filter1(df, dt)
                if score is not None:
                    rankings.append((sym, score))
            
            if not rankings: continue
            
            rankings.sort(key=lambda x: x[1], reverse=True)
            top = rankings[:10]
            
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
        print(f"\n🚀 V25 (2023) ROI: {final_roi:.2f}%")

if __name__ == "__main__":
    V25TimeMachine().run()
