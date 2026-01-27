"""
V16: THE GREED ENGINE (Zero-Friction Alpha)
Focus: Maximum Theoretical ROI. 
Zero Slippage. Zero Taxes. Zero Churn Concern.
"""
import pandas as pd
import numpy as np
import os
import sys
import pickle
import logging
from tqdm import tqdm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

CACHE_PATH = r"c:\Users\hp\Desktop\Nifty_500\Alpha_Zeta_Super_Scanner\backtest_v4_data.pkl"
INITIAL_CAPITAL = 100000.0

class V16GreedEngine:
    def __init__(self):
        self.data_store = {}
        self.market_index = None
        self.capital = INITIAL_CAPITAL
        self.portfolio = []
        self.trade_log = []
        self.equity_curve = []

    def load_data(self):
        if os.path.exists(CACHE_PATH):
             with open(CACHE_PATH, 'rb') as f:
                 self.data_store = pickle.load(f)
        else:
             sys.exit(1)

    def calculate_metrics(self, df, date):
        hist = df[df.index <= date]
        if len(hist) < 60: return None
        
        close = hist['Close']
        vol = hist['Volume']
        curr = float(close.iloc[-1])
        
        # Hyper Momentum
        r_s = ((curr / float(close.iloc[-6])) - 1) * 100 # 1 week
        r_m = ((curr / float(close.iloc[-22])) - 1) * 100 # 1 month
        
        # RS Proxy
        mkt_at_date = self.market_index.loc[date]
        mkt_at_prev = self.market_index.iloc[self.market_index.index.get_loc(date)-22]
        mkt_ret = (mkt_at_date / mkt_at_prev) - 1
        stk_ret = (curr / float(close.iloc[-22])) - 1
        alpha = stk_ret - mkt_ret
        
        # Vol Ratio
        vol_ratio = vol.iloc[-1] / vol.rolling(20).mean().iloc[-1]
        
        score = (r_s * 2) + (r_m * 1) + (vol_ratio * 5)
        
        return {
            'score': score,
            'price': curr,
            'alpha': alpha,
            'rsi': self.calculate_rsi(close)
        }

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, 1e-6)
        return 100 - (100 / (1 + rs)).iloc[-1]

    def run(self):
        self.load_data()
        all_rets = []
        for sym, df in self.data_store.items():
            if 'Close' in df.columns:
                all_rets.append(df['Close'].pct_change())
        self.market_index = (1 + pd.concat(all_rets, axis=1).mean(axis=1).fillna(0)).cumprod() * 100
        
        market_days = self.market_index.index[self.market_index.index >= "2025-01-01"]
        
        for dt in tqdm(market_days, desc="V16 Greed Execution"):
            # 1. THEORETICAL EXIT (Weekly swap regardless of cost)
            if dt.weekday() == 0: # Monday Swap
                for p in self.portfolio:
                    df = self.data_store[p['sym']]
                    if dt in df.index:
                        exit_p = float(df.loc[dt]['Close'])
                        self.capital += exit_p * p['shares']
                        self.trade_log.append((exit_p/p['entry'])-1)
                self.portfolio = []

                # 2. HYPER SELECTION
                cands = []
                for sym, df in self.data_store.items():
                    if dt not in df.index: continue
                    m = self.calculate_metrics(df, dt)
                    if m and m['alpha'] > 0:
                        cands.append((sym, m['score'], m['price']))
                
                cands.sort(key=lambda x: x[1], reverse=True)
                for sym, score, price in cands[:10]:
                    alloc = self.capital * 0.1
                    shares = alloc / price
                    self.capital -= alloc
                    self.portfolio.append({'sym': sym, 'entry': price, 'shares': shares})
            
            # Equity Curve
            pos_val = sum(float(self.data_store[p['sym']].loc[dt]['Close']) * p['shares'] for p in self.portfolio if dt in self.data_store[p['sym']].index)
            self.equity_curve.append(self.capital + pos_val)

        final_roi = (self.equity_curve[-1] / INITIAL_CAPITAL - 1) * 100
        print(f"\n🚀 V16 GREED ENGINE ROI: {final_roi:.2f}%")
        print(f"Total Trades: {len(self.trade_log)}")

if __name__ == "__main__":
    V16GreedEngine().run()
