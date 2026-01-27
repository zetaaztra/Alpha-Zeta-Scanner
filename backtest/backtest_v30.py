"""
V30: THE RETAIL HOLY GRAIL (Chartink/TradingView Hybrid)
Goal: Audit the 'viral' retail strategies often seen on YouTube/Chartink.
Universe: Nifty 500.
Logic: Supertrend (10,3) + RSI (14) > 60 + Vol > 1.5x Avg.
Rebalance: Daily (Retail style).
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

class V30RetailHolyGrail:
    def __init__(self):
        self.data_store = {}
        with open(CACHE_PATH, 'rb') as f:
            self.data_store = pickle.load(f)

    def calculate_indicators(self, df):
        # 1. RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 2. Supertrend (Simplified for speed in backtest)
        # Standard: 10, 3
        atr_window = 10
        multiplier = 3
        high = df['High']
        low = df['Low']
        close = df['Close']
        
        # ATR
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(atr_window).mean()
        
        mid = (high + low) / 2
        upper = mid + (multiplier * atr)
        lower = mid - (multiplier * atr)
        
        df['Supertrend_Lower'] = lower
        df['Vol_Avg'] = df['Volume'].rolling(20).mean()
        return df

    def run(self):
        # Simulation (2025)
        dates = pd.date_range(start="2025-01-01", end="2025-11-20", freq='D')
        capital = INITIAL_CAPITAL
        portfolio = {} # sym -> entry_price
        
        # Pre-calculate for all
        for sym in self.data_store:
            self.data_store[sym] = self.calculate_indicators(self.data_store[sym])

        for dt in tqdm(dates, desc="Retail Execution"):
            # Update Portfolio (Close if price falls below Supertrend Lower or RSI drops)
            if portfolio:
                symbols_to_remove = []
                for sym, info in portfolio.items():
                    df = self.data_store[sym]
                    if dt not in df.index: continue
                    curr = df.loc[dt]
                    if curr['Close'] < curr['Supertrend_Lower']:
                        ret = (curr['Close'] / info['entry']) - 1
                        capital *= (1 + ret / 10) # 10% allocation
                        symbols_to_remove.append(sym)
                for s in symbols_to_remove: del portfolio[s]

            # Entry Logic (RSI > 60 and Vol > 1.5x Avg)
            if len(portfolio) < 10:
                candidates = []
                for sym, df in self.data_store.items():
                    if dt not in df.index or sym in portfolio: continue
                    curr = df.loc[dt]
                    if curr['RSI'] > 60 and curr['Volume'] > curr['Vol_Avg'] * 1.5:
                        candidates.append((sym, curr['RSI']))
                
                candidates.sort(key=lambda x: x[1], reverse=True)
                for sym, _ in candidates[:(10-len(portfolio))]:
                    portfolio[sym] = {'entry': float(self.data_store[sym].loc[dt]['Close'])}

        final_roi = (capital / INITIAL_CAPITAL - 1) * 100
        print(f"\n🔮 V30 RETAIL HOLY GRAIL ROI: {final_roi:.2f}%")

if __name__ == "__main__":
    V30RetailHolyGrail().run()
