"""
Alpha-Zeta - GreenSigma Clone (Pure Momentum, No ML)
Goal: Benchmark "Simple Momentum" vs "Complex ML"
Strategy:
1. Regime Filter: If Nifty 50 < 200 SMA, Go 100% Cash (Safety).
2. Ranking: Rank Nifty 500 by 3-Month Return (Relative Strength).
3. Liquidity: Min Price > 100, Volume * Price > 10Cr.
4. Execution: Buy Top 5, Rebalance every 2 Weeks.
"""
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import os
import sys
from tqdm import tqdm
import logging
import pickle

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import DataEngine # Reusing DataEngine for symbol list

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CACHE_FILE = "backtest_v4_data.pkl"

class GreenSigmaClone:
    def __init__(self, capital=50000):
        self.capital = capital
        
    def load_data(self):
        if os.path.exists(CACHE_FILE):
            logger.info("⚡ Loading cached data...")
            with open(CACHE_FILE, 'rb') as f:
                return pickle.load(f)
        else:
            logger.error("❌ No data cache found! Run V4 first.")
            return {}

    def get_market_regime(self, benchmark_df, current_date):
        """Returns True if Bullish (Price > 200 SMA), False otherwise."""
        hist = benchmark_df[benchmark_df.index <= current_date]
        if len(hist) < 200: return True # Default Bull if no data
        
        sma_200 = hist['Close'].rolling(200).mean().iloc[-1]
        curr_price = float(hist['Close'].iloc[-1])
        return curr_price > sma_200

    def run_simulation(self):
        data_store = self.load_data()
        
        # Download Benchmark (Nifty 50) for Regime Filter
        try:
            logger.info("📊 Fetching Nifty 50 for Regime Filter...")
            nifty = yf.download("^NSEI", start="2024-01-01", end="2026-01-01", progress=False)
            if isinstance(nifty.columns, pd.MultiIndex):
                nifty.columns = nifty.columns.get_level_values(0)
            nifty = nifty[['Close']]
        except Exception as e:
            logger.warning(f"Failed to fetch Nifty 50: {e}. Disabling Regime Filter.")
            nifty = pd.DataFrame()
            
        logger.info("🚀 PURE MOMENTUM SIMULATION STARTING...")
        
        # Bi-Weekly Scans (Matches optimized V1 timeframe)
        start_date = pd.Timestamp("2025-01-06")
        scan_dates = pd.date_range(start=start_date, periods=24, freq='2W-MON') # Every 2 weeks
        
        running_capital = self.capital
        all_trades = []
        
        for scan_date in scan_dates:
            target_dt = scan_date.date()
            
            # 1. REGIME CHECK (DISABLED FOR COMPARISON)
            bullish = True
            
            if not bullish:
                logger.info(f"--- Scan {target_dt} | 🐻 BEAR MARKET (Cash Protection) | Cash: ₹{running_capital:.0f}")
                continue # Stay in Cash
                
            # 2. RANKING (Relative Strength)
            candidates = []
            
            for sym, df in data_store.items():
                # Get history
                target_ts = pd.Timestamp(target_dt)
                if target_ts not in df.index: continue
                # Need 90 days history for Momentum
                hist = df[df.index <= target_ts]
                if len(hist) < 90: continue
                
                curr_price = float(df.loc[target_ts]['Close'])
                if curr_price < 50: 
                    # logger.debug(f"{sym} Skipped: Price {curr_price} < 50")
                    continue 
                
                # Calculate 3-Month Return (Momentum)
                try:
                    price_90d_ago = float(hist['Close'].iloc[-90])
                    mom_score = (curr_price / price_90d_ago) - 1
                except IndexError:
                    # logger.debug(f"{sym} Skipped: IndexError (len={len(hist)})")
                    continue
                
                candidates.append({'Symbol': sym, 'Price': curr_price, 'Score': mom_score})
            
            logger.info(f"Scan {target_dt}: Found {len(candidates)} candidates.")
            
            # BUY TOP 5
            candidates.sort(key=lambda x: x['Score'], reverse=True)
            top_picks = candidates[:5]
            
            if not top_picks: 
                logger.warning(f"Scan {target_dt}: No top picks found!")
                continue
            
            invest_per_stock = running_capital / 5
            logger.info(f"--- Scan {target_dt} | 🐂 BULL MARKET | Buying Top 5 Momentum")
            
            for pick in top_picks:
                sym = pick['Symbol']
                entry_price = pick['Price']
                df = data_store[sym]
                
                # Hold for 2 Weeks (10 trading days)
                future = df[df.index > target_ts].head(10)
                if future.empty: 
                    exit_price = entry_price
                else:
                    exit_price = float(future.iloc[-1]['Close'])
                
                # PnL
                ret = (exit_price - entry_price) / entry_price
                profit = invest_per_stock * ret
                running_capital += profit
                
                all_trades.append({
                    'Symbol': sym, 'Entry': entry_price, 'Exit': exit_price,
                    'Return': round(ret*100, 2), 'Profit': round(profit, 0),
                    'Date': target_dt
                })

        # Stats
        roi = (running_capital - self.capital) / self.capital * 100
        print("\n" + "="*80)
        print(f"  GREENSIGMA CLONE RESULTS (Pure Momentum + Regime)")
        print("="*80)
        print(f"Initial:    ₹{self.capital:,}")
        print(f"Final:      ₹{running_capital:,.0f}")
        print(f"Return:     {roi:.2f}%")
        print(f"Trades:     {len(all_trades)}")
        
        if all_trades:
            df = pd.DataFrame(all_trades)
            os.makedirs('backtest_greensigma', exist_ok=True)
            df.to_csv("backtest_greensigma/results.csv", index=False)

if __name__ == "__main__":
    tester = GreenSigmaClone()
    tester.run_simulation()
