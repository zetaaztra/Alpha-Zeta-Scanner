"""
V24: LINEAR REGRESSION ALPHA
Goal: 50%+ ROI using Linear Regression Slope (R-Squared Normalized).
Universe: Nifty 500.
Zero Friction.
"""
import pandas as pd
import numpy as np
import os
import sys
import pickle
from tqdm import tqdm
from scipy.stats import linregress

CACHE_PATH = r"c:\Users\hp\Desktop\Nifty_500\Alpha_Zeta_Super_Scanner\backtest_v4_data.pkl"
INITIAL_CAPITAL = 100000.0

class V24RegressionAlpha:
    def __init__(self):
        self.data_store = {}
        with open(CACHE_PATH, 'rb') as f:
            self.data_store = pickle.load(f)

    def calculate_regression_momentum(self, df, date):
        hist = df[df.index <= date]
        if len(hist) < 90: return None
        
        y = np.log(hist['Close'].iloc[-90:].values)
        x = np.arange(len(y))
        slope, intercept, r_value, p_value, std_err = linregress(x, y)
        
        # Annualized Slope * R-Squared (The "Clenow" Momentum)
        # Penalizes inconsistent trends
        score = (slope * 252) * (r_value ** 2)
        
        return score

    def run(self):
        dates = pd.date_range(start="2025-01-01", end="2025-11-20", freq='W-MON')
        capital = INITIAL_CAPITAL
        
        for dt in tqdm(dates, desc="Regression Alpha Execution"):
            rankings = []
            for sym, df in self.data_store.items():
                if dt not in df.index: continue
                score = self.calculate_regression_momentum(df, dt)
                if score is not None and score > 0:
                    rankings.append((sym, score))
            
            if not rankings: continue
            
            rankings.sort(key=lambda x: x[1], reverse=True)
            top = rankings[:10]
            
            # Calculate return for the next week
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
        print(f"\n📉 V24 REGRESSION ALPHA ROI (Zero Fees): {final_roi:.2f}%")

if __name__ == "__main__":
    V24RegressionAlpha().run()
