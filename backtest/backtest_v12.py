"""
V12: THE FINAL WEAPON (Hyper-Growth)
Goal: 50%+ ROI using Daily Risk Management + Weekly Scanning.
"""
import pandas as pd
import numpy as np
import os
import sys
import pickle
import logging
from tqdm import tqdm
import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import TechnicalCore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

CACHE_PATH = r"c:\Users\hp\Desktop\Nifty_500\Alpha_Zeta_Super_Scanner\backtest_v4_data.pkl"
INITIAL_CAPITAL = 100000.0
SLIPPAGE_PCT = 0.005 

class V12Engine:
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

    def generate_market_proxy(self):
        all_rets = []
        for sym, df in self.data_store.items():
            if 'Close' in df.columns:
                all_rets.append(df['Close'].pct_change())
        self.market_index = (1 + pd.concat(all_rets, axis=1).mean(axis=1).fillna(0)).cumprod() * 100

    def get_atr(self, df):
        h, l, c = df['High'], df['Low'], df['Close']
        tr = pd.concat([h-l, abs(h-c.shift()), abs(l-c.shift())], axis=1).max(axis=1)
        return tr.rolling(14).mean().iloc[-1]

    def scan_for_hyper_growth(self, date):
        candidates = []
        for sym, df in self.data_store.items():
            if date not in df.index: continue
            hist = df[df.index <= date]
            if len(hist) < 60: continue
            
            # --- V12 SUPER FILTERS ---
            # 1. RS Rank (Top Outperf)
            mkt_ret = (self.market_index.loc[date] / self.market_index.iloc[self.market_index.index.get_loc(date)-20]) - 1
            stk_ret = (float(hist['Close'].iloc[-1]) / float(hist['Close'].iloc[-21])) - 1
            alpha = stk_ret - mkt_ret
            if alpha < 0.05: continue # Must beat index by 5% in a month
            
            # 2. VCP Tightness (Standard Deviation of close is shrinking)
            volatility = hist['Close'].iloc[-10:].std() / hist['Close'].iloc[-10:].mean()
            if volatility > 0.04: continue # Extremely tight coiling
            
            # 3. Pocket Pivot (Vol Spike)
            if hist['Volume'].iloc[-1] < hist['Volume'].iloc[-20:].mean() * 1.5: continue
            
            # 4. Trend (Price > 50SMA)
            if float(hist['Close'].iloc[-1]) < hist['Close'].rolling(50).mean().iloc[-1]: continue
            
            candidates.append((sym, alpha, float(hist['Close'].iloc[-1])))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates

    def run(self):
        self.load_data()
        self.generate_market_proxy()
        
        # Use existing market days to avoid KeyErrors
        market_days = self.market_index.index[self.market_index.index >= "2025-01-01"]
        mkt_sma50 = self.market_index.rolling(50).mean()
        
        for dt in tqdm(market_days, desc="V12 Daily Execution"):
            # 1. DAILY PORTFOLIO MANAGEMENT
            rem = []
            for p in self.portfolio:
                df = self.data_store[p['sym']]
                if dt not in df.index: rem.append(p); continue
                
                price = float(df.loc[dt]['Close'])
                ret = (price / p['entry']) - 1
                
                # Dynamic Stop (3.0 ATR)
                hist = df[df.index <= dt]
                atr = self.get_atr(hist)
                stop = p['entry'] - (3.0 * atr)
                
                # Peak tracking for trailing
                if price > p['peak']: p['peak'] = price
                mdd = (price / p['peak']) - 1
                
                exit = False
                reason = ""
                
                # EXIT RULES
                if price < stop: exit = True; reason = "ATR Stop"
                elif ret > 0.10 and mdd < -0.10: exit = True; reason = "Trail Profit"
                elif p['days'] > 22 and ret < 0.05: exit = True; reason = "Time Stop"
                
                # PREVENTIVE CRASH FILTER (If stock drops 7% in a DAY, get out)
                if len(hist) > 1:
                    day_change = (price / float(hist['Close'].iloc[-2])) - 1
                    if day_change < -0.07: exit = True; reason = "Circuit/Crash"

                if exit:
                    val = price * (1 - (SLIPPAGE_PCT/2)) * p['shares']
                    self.capital += val
                    self.trade_log.append({'ret': (val/p['cost'])-1, 'reason': reason})
                else:
                    p['days'] += 1
                    rem.append(p)
            self.portfolio = rem

            # 2. WEEKLY SCANNING (Mondays) - WITH MARKET REGIME FILTER
            if dt.weekday() == 0 and len(self.portfolio) < 5:
                # Market Regime: Only buy if Index is above 50-day SMA
                if self.market_index.loc[dt] > mkt_sma50.loc[dt]:
                    cands = self.scan_for_hyper_growth(dt)
                    for sym, alpha, price in cands[:5 - len(self.portfolio)]:
                        alloc = self.capital * 0.2
                        entry = price * (1 + (SLIPPAGE_PCT/2))
                        shares = int(alloc / entry)
                        if shares > 0:
                            cost = shares * entry
                            self.capital -= cost
                            self.portfolio.append({'sym': sym, 'entry': entry, 'shares': shares, 'peak': entry, 'days': 0, 'cost': cost})
                else:
                    pass # logger.info(f"Market Regime BLOCKED entry on {dt}")
            
            # Equity Log
            pos_val = sum(float(self.data_store[p['sym']].loc[dt]['Close']) * p['shares'] for p in self.portfolio if dt in self.data_store[p['sym']].index)
            self.equity_curve.append(self.capital + pos_val)

        # FINAL VERDICT
        roi = (self.equity_curve[-1] / INITIAL_CAPITAL - 1) * 100
        print(f"\n🏆 V12 FINAL ROI: {roi:.2f}%")
        print(f"Max Drawdown: {(pd.Series(self.equity_curve).pct_change().cumsum().min()*100):.2f}%")
        if self.trade_log:
             df_res = pd.DataFrame(self.trade_log)
             wr = len(df_res[df_res['ret']>0]) / len(df_res) * 100
             avg_w = df_res[df_res['ret']>0]['ret'].mean() * 100
             avg_l = df_res[df_res['ret']<0]['ret'].mean() * 100
             print(f"Win Rate:  {wr:.2f}% ({len(df_res)} trades)")
             print(f"Avg Win:   +{avg_w:.2f}%")
             print(f"Avg Loss:  {avg_l:.2f}%")
             print(f"Profit Factor: {abs((wr*avg_w)/((100-wr)*avg_l)):.2f}" if avg_l !=0 else "N/A")

if __name__ == "__main__":
    V12Engine().run()
