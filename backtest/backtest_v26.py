"""
V26: THE INSTITUTIONAL TITAN (Deep Quant Alpha)
Goal: 50%+ ROI using Institutional persistence filters (Hurst, Fractal, Idiosyncratic Alpha).
Universe: Nifty 500.
Lookback: 6-Month Alpha vs Nifty 50.
Zero Friction as requested.
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

class V26InstitutionalTitan:
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

    def calculate_hurst(self, series):
        """Simple Hurst Exponent estimation via R/S analysis."""
        if len(series) < 64: return 0.5
        lags = range(2, 21)
        tau = [np.sqrt(np.std(np.subtract(series[lag:], series[:-lag]))) for lag in lags]
        # Skip invalid tau
        tau = [t for t in tau if t > 0]
        if len(tau) < 5: return 0.5
        m = np.polyfit(np.log(lags[:len(tau)]), np.log(tau), 1)
        return m[0]*2.0

    def calculate_alpha_momentum(self, sym, df, date):
        hist = df[df.index <= date]
        if len(hist) < 252: return None
        
        # 1. Idiosyncratic Alpha (Stock Return - Market Return)
        mkt = self.market_index.loc[hist.index]
        ret_6m_stock = (hist['Close'].iloc[-1] / hist['Close'].iloc[-126]) - 1
        ret_6m_mkt = (mkt.iloc[-1] / mkt.iloc[-126]) - 1
        alpha_6m = ret_6m_stock - ret_6m_mkt
        
        # 2. Persistence Filter (Hurst Exponent > 0.60)
        # Only trade if the trend is NOT a random walk
        prices = hist['Close'].iloc[-126:].values
        hurst = self.calculate_hurst(prices)
        
        # 3. Chop Filter (Standard Deviation normalized by Price)
        vol = hist['Close'].pct_change().iloc[-20:].std() * np.sqrt(252)
        
        if hurst > 0.58 and vol < 0.40:
            return alpha_6m / (vol + 0.01) # Risk Adjusted Alpha
        return None

    def run(self):
        print("🛠️ Generating Institutional Market Index...")
        self.generate_market()
        
        # Simulation (2025)
        dates = pd.date_range(start="2025-01-01", end="2025-11-20", freq='ME') 
        capital = INITIAL_CAPITAL
        portfolio = []
        
        for dt in tqdm(dates, desc="Titan Institutional Execution"):
            rankings = []
            for sym, df in self.data_store.items():
                if dt not in df.index: continue
                score = self.calculate_alpha_momentum(sym, df, dt)
                if score is not None and score > 0:
                    rankings.append((sym, score))
            
            rankings.sort(key=lambda x: x[1], reverse=True)
            new_top_10 = [x[0] for x in rankings[:10]]
            
            if portfolio:
                rets = []
                for sym in portfolio:
                    df = self.data_store[sym]
                    # Monthly Return
                    idx_now = df.index.asof(dt)
                    prev_dt = dates[dates.get_loc(dt)-1]
                    idx_prev = df.index.asof(prev_dt)
                    
                    if idx_now and idx_prev:
                        entry = float(df.loc[idx_prev]['Close'])
                        exit = float(df.loc[idx_now]['Close'])
                        rets.append(exit/entry - 1)
                if rets:
                    capital *= (1 + np.mean(rets))
            
            portfolio = new_top_10

        final_roi = (capital / INITIAL_CAPITAL - 1) * 100
        print(f"\n🏛️ V26 INSTITUTIONAL TITAN ROI (Zero Fees): {final_roi:.2f}%")

if __name__ == "__main__":
    V26InstitutionalTitan().run()
