"""
V20: ALPHA PULSE (RS Convergence)
Goal: 50%+ ROI by catching the 'Alpha Breakout' before the 'Price Breakout'.
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

class V20AlphaPulse:
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

    def calculate_alpha_pulse(self, sym, df, date):
        hist = df[df.index <= date]
        if len(hist) < 60: return None
        
        # 1. Calculate RS Line
        mkt = self.market_index.loc[hist.index]
        rs_line = hist['Close'] / mkt
        
        # 2. RS BREAKOUT (Leading Indicator)
        # Is RS Line hitting a 20-day high?
        rs_curr = rs_line.iloc[-1]
        rs_high_20 = rs_line.iloc[-21:-1].max()
        
        # 3. PRICE CONFLATION (Lagging Indicator)
        # Is Price still relatively flat? (Within 3% of its 20-day avg)
        price_curr = float(hist['Close'].iloc[-1])
        price_avg_20 = hist['Close'].iloc[-20:].mean()
        price_is_flat = abs(price_curr / price_avg_20 - 1) < 0.03
        
        # 4. VOLATILITY TIGHTNESS
        # Contraction of ATR
        atr = (hist['High'] - hist['Low']).rolling(14).mean()
        atr_is_tight = atr.iloc[-1] < atr.iloc[-20:].mean()
        
        if rs_curr > rs_high_20 and price_is_flat and atr_is_tight:
             # This is a Pulse: Alpha is Leading Price
             return rs_curr / rs_line.iloc[-20] # Return the RS thrust
        return None

    def run(self):
        self.generate_market()
        dates = pd.date_range(start="2025-01-01", end="2025-11-20", freq='W-MON')
        capital = INITIAL_CAPITAL
        
        for dt in tqdm(dates, desc="Alpha Pulse Execution"):
            pulses = []
            for sym, df in self.data_store.items():
                if dt not in df.index: continue
                thrust = self.calculate_alpha_pulse(sym, df, dt)
                if thrust:
                    pulses.append((sym, thrust, float(df.loc[dt]['Close'])))
            
            if not pulses: continue
            
            # Pick strongest pulse
            pulses.sort(key=lambda x: x[1], reverse=True)
            top = pulses[:5]
            
            rets = []
            for sym, thrust, entry in top:
                df = self.data_store[sym]
                idx = df.index.get_loc(dt)
                if idx + 5 < len(df):
                    ret = (df.iloc[idx + 5]['Close'] / entry) - 1
                    rets.append(ret)
            
            if rets:
                capital *= (1 + np.mean(rets))
                
        final_roi = (capital / INITIAL_CAPITAL - 1) * 100
        print(f"\n🌊 V20 ALPHA PULSE ROI (Zero Fees): {final_roi:.2f}%")

if __name__ == "__main__":
    V20AlphaPulse().run()
