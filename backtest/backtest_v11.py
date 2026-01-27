"""
V11 HYPER-GROWTH ENGINE (Operation 50)
Goal: Target 50% ROI using "Super-Performance" Filters.
Concepts:
1. Relative Strength (RS) > 80th Percentile
2. VCP (Volatility Contraction) < Threadhold
3. Volume Pocket Pivot (Vol > 2x Avg)
"""
import pandas as pd
import numpy as np
import os
import sys
import pickle
import logging
from tqdm import tqdm

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import TIMEFRAME_CONFIGS, TechnicalCore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
CACHE_PATH = r"c:\Users\hp\Desktop\Nifty_500\Alpha_Zeta_Super_Scanner\backtest_v4_data.pkl"
INITIAL_CAPITAL = 100000.0
SLIPPAGE_PCT = 0.005 # 0.5% total friction (slippage + taxes + brokerage)

class V11HyperGrowth:
    def __init__(self):
        self.data_store = {}
        self.universe_index = None # Synthetic Market Proxy
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
             logger.error(f"Cache not found: {CACHE_PATH}")
             sys.exit(1)

    def generate_universe_index(self):
        """Creates a synthetic Nifty 500 Index for RS calculation."""
        logger.info("Generating Synthetic Nifty 500 Index...")
        all_rets = []
        for sym, df in self.data_store.items():
            if 'Close' in df.columns:
                rets = df['Close'].pct_change()
                all_rets.append(rets)
        
        if not all_rets: return
        
        # Mean of returns = Market Return Proxy
        df_rets = pd.concat(all_rets, axis=1)
        market_rets = df_rets.mean(axis=1)
        # Reconstruct Index from returns
        self.universe_index = (1 + market_rets.fillna(0)).cumprod() * 100
        logger.info("Synthetic Index Created.")

    def calculate_v11_score(self, df, date):
        hist = df[df.index <= date]
        if len(hist) < 50: return -100, 0.0
        
        prices = hist['Close']
        volumes = hist['Volume']
        current = float(prices.iloc[-1])
        
        # 1. Relative Strength (vs Index)
        idx_now = self.universe_index.loc[date]
        idx_lb = self.universe_index.iloc[self.universe_index.index.get_loc(date) - 20]
        idx_ret = (idx_now / idx_lb) - 1
        
        stk_lb = float(prices.iloc[-21])
        stk_ret = (current / stk_lb) - 1
        
        # ALPHA = Outperformance
        rs_score = stk_ret - idx_ret
        if rs_score < 0.02: return -100, current # Must outperform by at least 2% in a month
        
        # 2. VCP (Volatility Contraction)
        # Loosening slightly: we look for recent tightening vs historical
        daily_ranges = (hist['High'] - hist['Low']) / hist['Close']
        avg_range_5 = daily_ranges.iloc[-5:].mean()
        avg_range_20 = daily_ranges.iloc[-20:].mean()
        
        # Consolidation signature: Avg range is < 15% of price, and tightening
        vcp_tight = (avg_range_5 < 0.10) and (avg_range_5 < avg_range_20)
        if not vcp_tight: return -100, current
        
        # 3. Volume Pocket Pivot
        avg_vol_20 = volumes.iloc[-20:].mean()
        vol_shock = volumes.iloc[-1] > (avg_vol_20 * 1.5)
        if not vol_shock: return -100, current
        
        # 4. Trend Filter (Minervini rule: Price > 50SMA > 150SMA)
        sma50 = prices.rolling(50).mean().iloc[-1]
        if current < sma50: return -100, current
        
        return rs_score * 100, current

    def calculate_indicators(self, df):
        # Calculate ATR for dynamic stops
        high = df['High']
        low = df['Low']
        close = df['Close']
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        return atr

    def run_simulation(self):
        self.load_data()
        self.generate_universe_index()
        
        # Testing Year: 2025 (Weekly Steps for Stability)
        test_dates = pd.date_range(start="2025-01-01", end="2025-12-01", freq='W-MON')
        
        for date in tqdm(test_dates, desc="V11 Pro Simulation"):
            # 1. WEEKLY EXIT MANAGEMENT
            remaining_portfolio = []
            for pos in self.portfolio:
                sym = pos['symbol']
                df = self.data_store[sym]
                if date not in df.index:
                    remaining_portfolio.append(pos); continue
                
                curr_price = float(df.loc[date]['Close'])
                ret = (curr_price / pos['entry_price']) - 1
                
                # Dynamic ATR Stop
                hist_up_to_date = df[df.index <= date]
                atr = self.calculate_indicators(hist_up_to_date).iloc[-1]
                stop_val = pos['entry_price'] - (2.0 * atr) # 2.0 ATR buffer
                
                # Update High Water Mark
                if curr_price > pos['high_water']: pos['high_water'] = curr_price
                mdd_from_peak = (curr_price / pos['high_water']) - 1
                
                exit = False
                reason = ""
                
                # Rule 1: Dynamic ATR Stop
                if curr_price < stop_val:
                    exit = True; reason = "ATR Stop"
                # Rule 2: Trailing Profit (if up > 15%, follow with 10% trail)
                elif ret > 0.15 and mdd_from_peak < -0.10:
                    exit = True; reason = "Trailing Profit"
                # Rule 3: Time Stop for non-performers
                elif pos['weeks'] > 6 and ret < 0.05:
                    exit = True; reason = "Time Stop (Laggard)"
                
                if exit:
                    net_exit = curr_price * (1 - (SLIPPAGE_PCT/2))
                    self.capital += net_exit * pos['shares']
                    self.trade_log.append({'Date': date, 'Symbol': sym, 'Return': (net_exit/pos['entry_price'])-1, 'Reason': reason})
                else:
                    pos['weeks'] += 1
                    remaining_portfolio.append(pos)
            
            self.portfolio = remaining_portfolio
            
            # 2. WEEKLY SCANNING & PYRAMIDING
            if len(self.portfolio) < 8:
                candidates = []
                for sym, df in self.data_store.items():
                    if date not in df.index: continue
                    score, price = self.calculate_v11_score(df, date)
                    if score > 0:
                        # Check if already in portfolio for pyramiding
                        in_port = any(p['symbol'] == sym for p in self.portfolio)
                        candidates.append((sym, score, price, in_port))
                
                candidates.sort(key=lambda x: x[1], reverse=True)
                
                for sym, score, entry_price, in_port in candidates:
                    if len(self.portfolio) >= 8: break
                    
                    # Allocate 12.5% per position
                    alloc = INITIAL_CAPITAL * 0.125
                    
                    if in_port:
                        # Pyramid: Add 5% more if stock is already up 10%
                        pos_in_port = next(p for p in self.portfolio if p['symbol'] == sym)
                        if (entry_price / pos_in_port['entry_price'] - 1) > 0.10 and pos_in_port['shares'] < (alloc * 1.5 / entry_price):
                            pyramid_alloc = INITIAL_CAPITAL * 0.05
                            if self.capital >= pyramid_alloc:
                                net_entry = entry_price * (1 + (SLIPPAGE_PCT/2))
                                addon_shares = int(pyramid_alloc / net_entry)
                                self.capital -= addon_shares * net_entry
                                pos_in_port['shares'] += addon_shares
                                # logger.info(f"Pyramiding into {sym}")
                    elif self.capital >= alloc:
                        # Fresh Entry
                        net_entry = entry_price * (1 + (SLIPPAGE_PCT/2))
                        shares = int(alloc / net_entry)
                        self.capital -= shares * net_entry
                        self.portfolio.append({
                            'symbol': sym, 'entry_price': net_entry, 'shares': shares, 
                            'weeks': 0, 'high_water': net_entry
                        })
            
            # Record Equity
            val_positions = sum(float(self.data_store[p['symbol']].loc[date]['Close']) * p['shares'] for p in self.portfolio if date in self.data_store[p['symbol']].index)
            self.equity_curve.append(self.capital + val_positions)

        self.report()

    def report(self):
        df_equity = pd.Series(self.equity_curve)
        total_roi = (self.equity_curve[-1] / INITIAL_CAPITAL - 1) * 100
        
        # Max Drawdown
        rolling_max = df_equity.cummax()
        drawdowns = (df_equity - rolling_max) / rolling_max
        max_dd = drawdowns.min() * 100
        
        # Trades
        df_trades = pd.DataFrame(self.trade_log)
        win_rate = (df_trades['Return'] > 0).mean() * 100 if not df_trades.empty else 0
        
        print("\n" + "="*60)
        print("  🚀 V11 HYPER-GROWTH: BRUTAL VERDICT")
        print("="*60)
        print(f"Algorithm:         RS + VCP + PocketPivot")
        print(f"Holding Period:    2-4 Weeks")
        print(f"Friction modeled:  {SLIPPAGE_PCT*100:.1f}%")
        print("-" * 60)
        print(f"FINAL EQUITY:      ₹{self.equity_curve[-1]:,.2f}")
        print(f"TOTAL ROI:         {total_roi:+.2f}%")
        print(f"MAX DRAWDOWN:      {max_dd:.2f}%")
        print(f"WIN RATE:          {win_rate:.1f}% ({len(df_trades)} trades)")
        print(f"CALMAR RATIO:      {abs(total_roi/max_dd):.2f}" if max_dd != 0 else "N/A")
        print("="*60)
        
        # Monthly consistency check
        df_equity.to_csv("backtest/v11_equity_brutal.csv")

if __name__ == "__main__":
    eng = V11HyperGrowth()
    eng.run_simulation()
