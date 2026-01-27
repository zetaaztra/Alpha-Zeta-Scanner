"""
V13: THE PHANTOM RAIDER (Master Blueprint)
Focus: Stage 2 Uptrends + 20-Day Breakouts + Tight Risk Control.
Target: 50%+ ROI by catching massive trend extensions.
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
SLIPPAGE_PCT = 0.005 

class V13Engine:
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

    def scan_for_raiders(self, date):
        candidates = []
        for sym, df in self.data_store.items():
            if date not in df.index: continue
            hist = df[df.index <= date]
            if len(hist) < 200: continue
            
            prices = hist['Close']
            curr = float(prices.iloc[-1])
            
            # --- V13 PHANTOM FILTERS (Minervini Stage 2) ---
            sma50 = prices.rolling(50).mean().iloc[-1]
            sma150 = prices.rolling(150).mean().iloc[-1]
            sma200 = prices.rolling(200).mean().iloc[-1]
            
            # Stage 2 Trend Check
            is_stage_2 = (curr > sma50 > sma150 > sma200) and (sma200 > prices.rolling(200).mean().iloc[-20])
            if not is_stage_2: continue
            
            # 2. Momentum Burst (20-Day High Breakout)
            high_20 = prices.iloc[-21:-1].max()
            if curr <= high_20: continue
            
            # 3. RS Outperformance (Alpha)
            mkt_ret = (self.market_index.loc[date] / self.market_index.iloc[self.market_index.index.get_loc(date)-20]) - 1
            stk_ret = (curr / float(prices.iloc[-21])) - 1
            alpha = stk_ret - mkt_ret
            if alpha < 0.03: continue # 3% Alpha is enough if trend is Stage 2
            
            # 4. Volatility Check (Avoid parabolic moves)
            if stk_ret > 0.30: continue # Don't buy if up > 30% in a month (already extended)
            
            candidates.append((sym, alpha, curr))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates

    def run(self):
        self.load_data()
        self.generate_market_proxy()
        
        market_days = self.market_index.index[self.market_index.index >= "2025-01-01"]
        mkt_sma50 = self.market_index.rolling(50).mean()
        
        for dt in tqdm(market_days, desc="V13 Phantom Scan"):
            # 1. DAILY PORTFOLIO MANAGEMENT
            rem = []
            for p in self.portfolio:
                df = self.data_store[p['sym']]
                if dt not in df.index: rem.append(p); continue
                
                curr_price = float(df.loc[dt]['Close'])
                ret = (curr_price / p['entry']) - 1
                
                # Dynamic Stop (2.0 ATR - Tightened for V13)
                hist = df[df.index <= dt]
                atr = self.get_atr(hist)
                stop = p['entry'] - (2.0 * atr)
                
                # Peak tracking
                if curr_price > p['peak']: p['peak'] = curr_price
                mdd = (curr_price / p['peak']) - 1
                
                exit = False
                reason = ""
                
                # EXIT RULES
                if curr_price < stop: exit = True; reason = "Hard ATR Stop"
                elif ret > 0.20 and mdd < -0.10: exit = True; reason = "Trail Winner"
                elif p['days'] > 30 and ret < 0.02: exit = True; reason = "Dead Money"
                
                # Crash Filter
                if len(hist) > 1:
                    day_change = (curr_price / float(hist['Close'].iloc[-2])) - 1
                    if day_change < -0.06: exit = True; reason = "Crash Protection"

                if exit:
                    val = curr_price * (1 - (SLIPPAGE_PCT/2)) * p['shares']
                    self.capital += val
                    self.trade_log.append({'ret': (val/p['cost'])-1, 'reason': reason})
                else:
                    p['days'] += 1
                    rem.append(p)
            self.portfolio = rem

            # 2. WEEKLY SCANNING (Mondays)
            if dt.weekday() == 0 and len(self.portfolio) < 5:
                # Market Regime (Only buy in uptrend)
                if self.market_index.loc[dt] > mkt_sma50.loc[dt]:
                    cands = self.scan_for_raiders(dt)
                    for sym, alpha, price in cands[:5 - len(self.portfolio)]:
                        alloc = self.capital * 0.2
                        entry = price * (1 + (SLIPPAGE_PCT/2))
                        shares = int(alloc / entry)
                        if shares > 0:
                            cost = shares * entry
                            self.capital -= cost
                            self.portfolio.append({'sym': sym, 'entry': entry, 'shares': shares, 'peak': entry, 'days': 0, 'cost': cost})
            
            # Equity Log
            pos_val = sum(float(self.data_store[p['sym']].loc[dt]['Close']) * p['shares'] for p in self.portfolio if dt in self.data_store[p['sym']].index)
            self.equity_curve.append(self.capital + pos_val)

        # FINAL VERDICT
        roi = (self.equity_curve[-1] / INITIAL_CAPITAL - 1) * 100
        print(f"\n👻 V13 PHANTOM ROI: {roi:.2f}%")
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
    V13Engine().run()
