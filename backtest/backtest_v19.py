"""
V19: CONCENTRATED POWER (The ROI Stand)
Focus: Concentration of 'Filter 1' logic (The historical winner).
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

class V19ConcentratedPower:
    def __init__(self):
        self.data_store = {}
        with open(CACHE_PATH, 'rb') as f:
            self.data_store = pickle.load(f)
        self.market_index = None

    def calculate_metrics(self, df, date):
        hist = df[df.index <= date]
        if len(hist) < 20: return None
        close = hist['Close']
        curr = float(close.iloc[-1])
        
        # Momentum + RSI
        mom = (curr / float(close.iloc[-20])) - 1
        vol_avg = hist['Volume'].rolling(20).mean().iloc[-1]
        vol_ratio = hist['Volume'].iloc[-1] / (vol_avg + 1)
        
        # Trend
        sma50 = close.rolling(50).mean().iloc[-1]
        
        score = (mom * 100) + (vol_ratio * 2.0)
        
        # RSI 14
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-6)
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        return {
            'score': score,
            'valid': (curr > sma50) and (rsi < 70)
        }

    def run(self):
        dates = pd.date_range(start="2025-01-01", end="2025-11-20", freq='W-MON')
        capital = INITIAL_CAPITAL
        
        for dt in tqdm(dates, desc="Concentration Test"):
            cands = []
            for sym, df in self.data_store.items():
                if dt not in df.index: continue
                m = self.calculate_metrics(df, dt)
                if m and m['valid'] and m['score'] > 0:
                    cands.append((sym, m['score']))
            
            if not cands: continue
            
            # THE CONCENTRATION: Pick only the Top 3
            cands.sort(key=lambda x: x[1], reverse=True)
            top = cands[:3]
            
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
        print(f"\n⚡ V19 CONCENTRATED POWER ROI (Zero Fees): {final_roi:.2f}%")

if __name__ == "__main__":
    V19ConcentratedPower().run()
