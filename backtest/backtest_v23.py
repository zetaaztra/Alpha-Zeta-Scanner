"""
V23: GOLDEN CROSS MOMENTUM (The Viral Viral)
Goal: 50%+ ROI by combining Golden Cross with RS 1-Year Highs.
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

class V23GoldenMomentum:
    def __init__(self):
        self.data_store = {}
        with open(CACHE_PATH, 'rb') as f:
            self.data_store = pickle.load(f)
        self.market_index = None

    def generate_market(self):
        rets = []
        for sym, df in self.data_store.items():
            if 'Close' in df.columns:
                rets.append(df['Close'].pct_change())
        self.market_index = (1 + pd.concat(rets, axis=1).mean(axis=1).fillna(0)).cumprod() * 100

    def calculate_golden_momentum(self, sym, df, date):
        hist = df[df.index <= date]
        if len(hist) < 200: return None
        
        close = hist['Close']
        sma50 = close.rolling(50).mean()
        sma200 = close.rolling(200).mean()
        
        # 1. GOLDEN CROSS
        is_golden = sma50.iloc[-1] > sma200.iloc[-1] and close.iloc[-1] > sma50.iloc[-1]
        
        # 2. RS 1-YEAR HIGH
        mkt = self.market_index.loc[hist.index]
        rs = close / mkt
        rs_curr = rs.iloc[-1]
        rs_high_1y = rs.iloc[-252:-1].max()
        
        if is_golden and rs_curr > rs_high_1y:
            return rs_curr / rs_high_1y # Pulse strength
        return None

    def run(self):
        self.generate_market()
        dates = pd.date_range(start="2025-01-01", end="2025-11-20", freq='W-MON')
        capital = INITIAL_CAPITAL
        
        for dt in tqdm(dates, desc="Golden Momentum Execution"):
            cands = []
            for sym, df in self.data_store.items():
                if dt not in df.index: continue
                strength = self.calculate_golden_momentum(sym, df, dt)
                if strength:
                    cands.append((sym, strength, float(df.loc[dt]['Close'])))
            
            if not cands: continue
            
            cands.sort(key=lambda x: x[1], reverse=True)
            top = cands[:5]
            
            rets = []
            for sym, strg, entry in top:
                df = self.data_store[sym]
                idx = df.index.get_loc(dt)
                if idx + 5 < len(df):
                    ret = (df.iloc[idx + 5]['Close'] / entry) - 1
                    rets.append(ret)
            
            if rets:
                capital *= (1 + np.mean(rets))
                
        final_roi = (capital / INITIAL_CAPITAL - 1) * 100
        print(f"\n✨ V23 GOLDEN MOMENTUM ROI (Zero Fees): {final_roi:.2f}%")

if __name__ == "__main__":
    V23GoldenMomentum().run()
