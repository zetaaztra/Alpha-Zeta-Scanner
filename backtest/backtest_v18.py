"""
V18: THE ALCHEMIST (Smart Alpha Quest)
Goal: 50%+ ROI by finding Anticipatory VCP (Volatility Contraction).
Innovation: Buying the 'Coil' before the 'Breakout'.
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
SLIPPAGE_PCT = 0.0 # User said "dont worry about the fees" for now

class V18Alchemist:
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

    def calculate_vcp_tightness(self, prices):
        """Measures contraction cycles."""
        std_20 = float(prices.iloc[-20:].std())
        std_40_20 = float(prices.iloc[-40:-20].std())
        std_60_40 = float(prices.iloc[-60:-40].std())
        
        # Is Volatility Decreasing? (The VCP Cycle)
        if std_20 < std_40_20 < std_60_40:
            return True
        return False

    def get_rs_acceleration(self, sym, df, date):
        """Measures if Relative Strength is speeding up."""
        hist = df[df.index <= date]
        if len(hist) < 40: return 0
        
        # Stock vs Market
        mkt = self.market_index.loc[hist.index]
        rs_line = hist['Close'] / mkt
        
        # Slope of RS line (RS Acceleration)
        rs_today = rs_line.iloc[-1]
        rs_14 = rs_line.iloc[-14]
        return (rs_today / rs_14) - 1

    def run(self):
        self.load_data()
        self.generate_market_proxy()
        
        market_days = self.market_index.index[self.market_index.index >= "2025-01-01"]
        mkt_sma50 = self.market_index.rolling(50).mean()
        
        for dt in tqdm(market_days, desc="V18 Alchemist Execution"):
            # 1. DAILY EXIT MANAGEMENT
            rem = []
            for p in self.portfolio:
                df = self.data_store[p['sym']]
                if dt not in df.index: rem.append(p); continue
                
                curr_price = float(df.loc[dt]['Close'])
                ret = (curr_price / p['entry']) - 1
                
                # Dynamic Stop (20-EMA)
                ema_20 = df['Close'].ewm(span=20, adjust=False).mean().loc[dt]
                
                exit = False
                if curr_price < ema_20: exit = True # Simple Trend Exit
                
                if exit:
                    val = curr_price * (1 - (SLIPPAGE_PCT/2)) * p['shares']
                    self.capital += val
                    self.trade_log.append({'Symbol': p['sym'], 'Ret': (val/p['cost'])-1})
                else:
                    rem.append(p)
            self.portfolio = rem

            # 2. SCANNING (Mondays)
            if dt.weekday() == 0 and len(self.portfolio) < 10:
                # Only scan if market is healthy
                if self.market_index.loc[dt] > mkt_sma50.loc[dt]:
                    candidates = []
                    for sym, df in self.data_store.items():
                        if dt not in df.index: continue
                        hist = df[df.index <= dt]
                        if len(hist) < 100: continue
                        
                        # ALCHEMIST FILTERS:
                        # 1. Zero-Breakout VCP (Buying before the peak)
                        is_tight = self.calculate_vcp_tightness(hist['Close'])
                        if not is_tight: continue
                        
                        # 2. Volume Dry-up (Calm before the explosion)
                        vol_avg = hist['Volume'].rolling(21).mean().iloc[-2]
                        if hist['Volume'].iloc[-1] > vol_avg * 0.8: continue
                        
                        # 3. RS Acceleration (Alpha is coming)
                        accel = self.get_rs_acceleration(sym, df, dt)
                        if accel <= 0: continue
                        
                        candidates.append((sym, accel, float(hist['Close'].iloc[-1])))
                    
                    # Sort by Acceleration
                    candidates.sort(key=lambda x: x[1], reverse=True)
                    for sym, accel, price in candidates[:10 - len(self.portfolio)]:
                        if any(pos['sym'] == sym for pos in self.portfolio): continue
                        
                        alloc = self.capital * 0.1 # 10% Slot
                        entry = price * (1 + (SLIPPAGE_PCT/2))
                        shares = int(alloc / entry)
                        if shares > 0:
                            cost = shares * entry
                            self.capital -= cost
                            self.portfolio.append({'sym': sym, 'entry': entry, 'shares': shares, 'cost': cost})

            # Record Equity
            pos_val = sum(float(self.data_store[p['sym']].loc[dt]['Close']) * p['shares'] for p in self.portfolio if dt in self.data_store[p['sym']].index)
            self.equity_curve.append(self.capital + pos_val)

        # REPORTING
        final_roi = (self.equity_curve[-1] / INITIAL_CAPITAL - 1) * 100
        print(f"\n🧪 V18 ALCHEMIST FINAL ROI (Zero Fees): {final_roi:.2f}%")
        if self.trade_log:
             df_res = pd.DataFrame(self.trade_log)
             wr = (df_res['Ret'] > 0).mean() * 100
             print(f"Total Trades: {len(df_res)}")
             print(f"Win Rate:     {wr:.1f}%")
             print(f"Avg Trade:    {df_res['Ret'].mean()*100:.2f}%")
        
        # Save results
        pd.DataFrame(self.equity_curve, columns=['Equity']).to_csv("backtest/v18_alchemist_equity.csv", index=False)

if __name__ == "__main__":
    V18Alchemist().run()
