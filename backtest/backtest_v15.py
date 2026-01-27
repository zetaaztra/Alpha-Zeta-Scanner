"""
V15: THE SURVIVOR (Ultimate ROI Quest)
Focus: Stage 2 + Volume Confirmation + 3-Step Hyper-Stop.
Goal: 50%+ ROI by catching the strongest trends and locking profit early.
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

class V15Survivor:
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
             logger.info(f"Loaded {len(self.data_store)} stocks.")
        else:
             logger.error("Cache not found.")
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

    def scan_for_survivors(self, date):
        candidates = []
        
        # Calculate RS Ranks for high productivity
        rs_scores = []
        for sym, df in self.data_store.items():
            if date not in df.index: continue
            hist = df[df.index <= date]
            if len(hist) < 200: continue
            ret_6m = (float(hist['Close'].iloc[-1]) / float(hist['Close'].iloc[-126])) - 1
            rs_scores.append((sym, ret_6m))
        
        if not rs_scores: return []
        df_rs = pd.DataFrame(rs_scores, columns=['sym', 'score'])
        df_rs['rank'] = df_rs['score'].rank(pct=True) * 100
        rs_dict = dict(zip(df_rs['sym'], df_rs['rank']))

        for sym, df in self.data_store.items():
            if sym not in rs_dict or rs_dict[sym] < 90: continue # Top 10% Only
            
            hist = df[df.index <= date]
            prices = hist['Close']
            curr = float(prices.iloc[-1])
            
            # 1. Stage 2 Trend Check
            sma50 = prices.rolling(50).mean().iloc[-1]
            sma150 = prices.rolling(150).mean().iloc[-1]
            sma200 = prices.rolling(200).mean().iloc[-1]
            if not (curr > sma50 > sma150 > sma200): continue
            
            # 2. Volume Confirmation (Volume > 1.5x Avg)
            vol_avg = hist['Volume'].rolling(20).mean().iloc[-2]
            if hist['Volume'].iloc[-1] < vol_avg * 1.5: continue
            
            # 3. 20-Day High Breakout
            high_20 = prices.iloc[-21:-1].max()
            if curr <= high_20: continue
            
            candidates.append((sym, rs_dict[sym], curr))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates

    def run(self):
        self.load_data()
        self.generate_market_proxy()
        
        market_days = self.market_index.index[self.market_index.index >= "2025-01-01"]
        mkt_sma50 = self.market_index.rolling(50).mean()
        
        for dt in tqdm(market_days, desc="V15 Survivor Execution"):
            # 1. DAILY PORTFOLIO MANAGEMENT (Hyper-Stop Logic)
            rem = []
            for p in self.portfolio:
                df = self.data_store[p['sym']]
                if dt not in df.index: rem.append(p); continue
                
                curr_price = float(df.loc[dt]['Close'])
                ret = (curr_price / p['entry']) - 1
                
                if curr_price > p['high']: p['high'] = curr_price
                mdd_from_peak = (curr_price / p['high']) - 1
                
                # --- 3-STEP TRAILING STOP ---
                # Default ATR Stop
                atr = self.get_atr(df[df.index <= dt])
                stop_val = p['entry'] - (2.0 * atr)
                
                # Step 1: Breakeven (Up 10%)
                if ret >= 0.10 and stop_val < p['entry']:
                    stop_val = p['entry']
                    p['mode'] = "Breakeven"
                
                # Step 2: Aggressive Trail (Up 25%)
                if ret >= 0.25:
                    step2_stop = p['high'] * 0.92 # 8% Trail
                    if step2_stop > stop_val:
                        stop_val = step2_stop
                        p['mode'] = "Trailing (8%)"
                
                # Step 3: Titan Lock (Up 50%)
                if ret >= 0.50:
                    step3_stop = p['high'] * 0.95 # 5% Trail
                    if step3_stop > stop_val:
                        stop_val = step3_stop
                        p['mode'] = "Titan Lock (5%)"

                exit = False
                reason = ""
                
                if curr_price < stop_val:
                    exit = True; reason = p.get('mode', 'ATR Stop')
                elif p['days'] > 60 and ret < 0.05: # Time stop for laggards
                    exit = True; reason = "Time Laggard"
                
                if exit:
                    val = curr_price * (1 - (SLIPPAGE_PCT/2)) * p['shares']
                    self.capital += val
                    self.trade_log.append({
                        'Symbol': p['sym'], 'Ret': (val/p['cost'])-1, 
                        'Reason': reason, 'Days': p['days']
                    })
                else:
                    p['days'] += 1
                    rem.append(p)
            self.portfolio = rem

            # 2. WEEKLY SCANNING (Mondays)
            if dt.weekday() == 0 and len(self.portfolio) < 5:
                if self.market_index.loc[dt] > mkt_sma50.loc[dt]:
                    cands = self.scan_for_survivors(dt)
                    for sym, rank, price in cands[:5 - len(self.portfolio)]:
                        if any(pos['sym'] == sym for pos in self.portfolio): continue
                        
                        alloc = self.capital * 0.2
                        entry = price * (1 + (SLIPPAGE_PCT/2))
                        shares = int(alloc / entry)
                        if shares > 0:
                            cost = shares * entry
                            self.capital -= cost
                            self.portfolio.append({
                                'sym': sym, 'entry': entry, 'shares': shares, 
                                'high': entry, 'days': 0, 'cost': cost, 'mode': 'Initial'
                            })
            
            # Equity Curve
            pos_val = sum(float(self.data_store[p['sym']].loc[dt]['Close']) * p['shares'] for p in self.portfolio if dt in self.data_store[p['sym']].index)
            self.equity_curve.append(self.capital + pos_val)

        # FINAL VERDICT
        roi = (self.equity_curve[-1] / INITIAL_CAPITAL - 1) * 100
        print(f"\n🦾 V15 SURVIVOR FINAL ROI: {roi:.2f}%")
        if self.trade_log:
             df_res = pd.DataFrame(self.trade_log)
             wr = (df_res['Ret'] > 0).mean() * 100
             avg_w = df_res[df_res['Ret'] > 0]['Ret'].mean() * 100
             avg_l = df_res[df_res['Ret'] < 0]['Ret'].mean() * 100
             print(f"Win Rate:      {wr:.2f}% ({len(df_res)} trades)")
             print(f"Avg Win:       +{avg_w:.2f}%")
             print(f"Avg Loss:      {avg_l:.2f}%")
             print(f"Profit Factor: {abs((wr*avg_w)/((100-wr)*avg_l)):.2f}" if avg_l !=0 else "N/A")
             print(f"Max Drawdown:  {(pd.Series(self.equity_curve).pct_change().cumsum().min()*100):.2f}%")
             
             df_res.to_csv("backtest/v15_survivor_stats.csv", index=False)

if __name__ == "__main__":
    V15Survivor().run()
