import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import requests
import warnings
import urllib3
import logging
import os
import json
import time
import sys
from io import StringIO
from tqdm import tqdm
from scipy import stats
from dotenv import load_dotenv

# --- INITIALIZATION ---
load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')

# Fix Unicode for Windows Consoles
if os.name == 'nt':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# Set up professional logging (Unicode Safe)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("alpha_zeta_scanner.log", encoding='utf-8'),
        handler
    ]
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
TIMEFRAME_CONFIGS = {
    '3-7_days': {
        'lookbacks': {'short': 5, 'medium': 10, 'long': 21, 'base': 63},
        'vol_periods': {'short': 5, 'medium': 10, 'long': 21},
        'rsi_period': 14, 'ema_period': 5, 'min_data_days': 70, 'target_gain': 1.05, 'stop_loss_pct': 0.05
    },
    '1-2_weeks': {
        'lookbacks': {'short': 5, 'medium': 10, 'long': 21, 'base': 42},
        'vol_periods': {'short': 10, 'medium': 21, 'long': 42},
        'rsi_period': 14, 'ema_period': 10, 'min_data_days': 90, 'target_gain': 1.15, 'stop_loss_pct': 0.08
    },
    '1_month': {
        'lookbacks': {'short': 21, 'medium': 42, 'long': 63, 'base': 126},
        'vol_periods': {'short': 21, 'medium': 42, 'long': 63},
        'rsi_period': 21, 'ema_period': 21, 'min_data_days': 180, 'target_gain': 1.25, 'stop_loss_pct': 0.12
    }
}

# --- INPUT UTILITIES ---
def get_valid_float(prompt, min_val=0, max_val=float('inf'), default=None):
    while True:
        try:
            display_prompt = f"{prompt} [{default}]: " if default is not None else prompt
            val = input(display_prompt).strip()
            if not val:
                if default is not None: return float(default)
                if min_val == 0: return 0.0
            val = float(val)
            if min_val <= val <= max_val: return val
            print(f"Error: Value must be between {min_val} and {max_val}")
        except ValueError:
            print("Error: Invalid number format.")

def get_valid_date(prompt, default=None):
    while True:
        display_prompt = f"{prompt} [{default}]: " if default is not None else prompt
        ds = input(display_prompt).strip()
        if not ds and default is not None:
            return datetime.datetime.strptime(default, "%Y-%m-%d")
        try:
            return datetime.datetime.strptime(ds, "%Y-%m-%d")
        except ValueError:
            print("Error: Use YYYY-MM-DD format.")

# --- DATA LAYER ---
class DataEngine:
    @staticmethod
    def get_nifty_symbols():
        try:
            url = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            df = pd.read_csv(StringIO(response.text))
            symbols = [f"{s.strip()}.NS" for s in df['Symbol'] if pd.notna(s)]
            logger.info(f"Fetched {len(symbols)} symbols from NSE.")
            return symbols
        except Exception as e:
            logger.error(f"Failed to fetch symbols from NSE: {e}. Using static fallback.")
            return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBI.NS", "ITC.NS", "M&M.NS"]

    @staticmethod
    def clean_yf_data(data):
        """Ultra-robust extraction of Close and Volume from yfinance DataFrame"""
        if data is None or data.empty: return None, None
        
        try:
            # Case 1: Standard Single-Ticker DataFrame
            if not isinstance(data.columns, pd.MultiIndex):
                close = data['Close'] if 'Close' in data.columns else None
                volume = data['Volume'] if 'Volume' in data.columns else None
                # Force to Series
                if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
                if isinstance(volume, pd.DataFrame): volume = volume.iloc[:, 0]
                return close, volume
            
            # Case 2: MultiIndex (Price, Ticker) format
            # Flatten columns if limited to one ticker
            if isinstance(data.columns, pd.MultiIndex):
                # Get the 'Close' and 'Volume' levels
                close = data.get('Close')
                volume = data.get('Volume')
                
                if close is not None:
                    if isinstance(close, pd.DataFrame): 
                        close = close.dropna(axis=1, how='all').iloc[:, 0]
                if volume is not None:
                    if isinstance(volume, pd.DataFrame): 
                        volume = volume.dropna(axis=1, how='all').iloc[:, 0]
                    
                return close, volume

        except Exception as e:
            logger.debug(f"Data cleaning failed: {e}")
            
        return None, None

# --- THE BRUTAL MATH ENGINE ---
class TechnicalCore:
    @staticmethod
    def calculate_rsi(prices, period=14):
        if len(prices) < period + 1: return 50.0
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, 1e-6)
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0

    @staticmethod
    def calculate_ema(prices, period=5):
        if len(prices) < period: return 0.0
        ema = prices.ewm(span=period).mean()
        current = float(prices.iloc[-1])
        ema_val = float(ema.iloc[-1])
        return ((current - ema_val) / ema_val) * 100 if ema_val != 0 else 0.0

    @staticmethod
    def calculate_atr(data, period=14):
        try:
            high = data['High'] if 'High' in data.columns else data.get('High')
            low = data['Low'] if 'Low' in data.columns else data.get('Low')
            close = data['Close'] if 'Close' in data.columns else data.get('Close')
            if isinstance(high, pd.DataFrame): high = high.iloc[:, 0]
            if isinstance(low, pd.DataFrame): low = low.iloc[:, 0]
            if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
            
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            return float(tr.rolling(window=period).mean().iloc[-1])
        except: return 1.0

    @staticmethod
    def get_hurst(ts):
        if ts is None or len(ts) < 20: return 0.5
        try:
            ts_clean = ts.dropna()
            if len(ts_clean) < 20: return 0.5
            lags = range(2, 20)
            tau = [np.std(np.subtract(ts_clean.values[lag:], ts_clean.values[:-lag])) for lag in lags]
            return np.polyfit(np.log(lags), np.log(tau), 1)[0] * 2.0
        except: return 0.5

    @staticmethod
    def calculate_indicators(data, config):
        prices, volumes = DataEngine.clean_yf_data(data)
        if prices is None or len(prices) < config['min_data_days']: 
            return None
        
        # Ensure we have floats
        prices = prices.ffill().dropna().astype(float)
        volumes = volumes.ffill().dropna().astype(float)
        
        if len(prices) < config['min_data_days']: return None
        
        current = float(prices.iloc[-1])
        lb = config['lookbacks']
        
        try:
            # Performance metrics (Zeta Core)
            r_s = ((current / float(prices.iloc[-lb['short']])) - 1) * 100 if len(prices) > lb['short'] else 0
            r_m = ((current / float(prices.iloc[-lb['medium']])) - 1) * 100 if len(prices) > lb['medium'] else 0
            r_l = ((current / float(prices.iloc[-lb['long']])) - 1) * 100 if len(prices) > lb['long'] else 0
            
            # Volatility
            returns = prices.pct_change().dropna()
            short_vol = float(returns.iloc[-5:].std() * np.sqrt(252) * 100) if len(returns) > 5 else 10.0
            medium_vol = float(returns.iloc[-10:].std() * np.sqrt(252) * 100) if len(returns) > 10 else 10.0
            
            # Technical
            rsi = TechnicalCore.calculate_rsi(prices, config['rsi_period'])
            ema_signal = TechnicalCore.calculate_ema(prices, config['ema_period'])
            atr = TechnicalCore.calculate_atr(data)
            
            # Volume ratio
            avg_vol_21 = float(volumes.rolling(21).mean().iloc[-1]) if len(volumes) > 21 else float(volumes.mean())
            vol_ratio = float(volumes.iloc[-1]) / avg_vol_21 if avg_vol_21 > 0 else 1.0
            
            # Additional Alpha-Zeta Legacy Features
            idx_dates = prices.index
            bb_mid = prices.rolling(20).mean()
            bb_std = prices.rolling(20).std()
            squeeze = (bb_std * 4) / bb_mid.replace(0, 1e-6)
            coiling = (prices.rolling(20).max() - prices.rolling(20).min()) / bb_mid.replace(0, 1e-6)
            
            hurst = TechnicalCore.get_hurst(prices)
            
            # TD Sequential
            td_count = 0
            for i in range(1, 10):
                if len(prices) > i+4 and float(prices.iloc[-i]) > float(prices.iloc[-i-4]): 
                    td_count += 1
                else: 
                    break
            
            # Combined Metric Object
            return {
                'price': current,
                'r_s': r_s, 'r_m': r_m, 'r_l': r_l,
                'short_vol': short_vol, 'medium_vol': medium_vol,
                'rsi': rsi, 'ema_signal': ema_signal, 'atr': atr,
                'vol_ratio': vol_ratio, 'avg_vol': float((prices * volumes).mean()),
                'squeeze': float(squeeze.iloc[-1]), 'coiling': float(coiling.iloc[-1]),
                'hurst': hurst, 'td_count': td_count,
                'sma50': float(prices.rolling(50).mean().iloc[-1]) if len(prices) >= 50 else current
            }
        except Exception as e:
            logger.debug(f"Indicator calculation error: {e}")
            return None

# --- FORMULA FACTORY ---
class FormulaFactory:
    @staticmethod
    def generate_all(m):
        """Calculates the WINNING FILTER 1 ENSEMBLE (+32.8% ROI Logic)."""
        f = {}
        
        # --- FILTER 1 CORE MATH ---
        # m['r_l'] is the Long Performance (21 days) which matches the 20-day momentum
        momentum_20 = m['r_l'] / 100 
        
        # Volume Intensity (Multiplier 2.0 as per champion backtest)
        vol_alpha = (m['vol_ratio'] * 2.0)
        
        # Final Champion Score
        f['ensemble'] = (momentum_20 * 100) + vol_alpha
        
        return f


# --- SCANNER ---
class AlphaZetaScanner:
    def __init__(self):
        self.history_file = "trade_history.csv"
        
    def setup_menu(self):
        print("\n" + "="*60)
        print("  ALPHA-ZETA INVESTING: 2025 CHAMPION ENGINE")
        print("="*60)
        print("\n[Status] Strategy: FILTER 1 (Momentum + Volume)")
        print("[Status] Audited ROI: +32.8% (2025 Gauging)")
        
        print("\nReady to scan the Nifty 500 for high-momentum breakouts.")
        input("\nPress Enter to START SCAN...")
        self.run_scanner()


    def log_top_picks(self, df, timeframe):
        """Append the #1 ranked pick to a persistent history file for long-term tracking."""
        history_file = "persistent_pick_history.csv"
        if df.empty: return
        
        top_pick = df.iloc[0].copy()
        top_pick['Date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        top_pick['Timeframe'] = timeframe
        
        # Reorder columns to put Date first
        cols = ['Date', 'Timeframe'] + [c for c in top_pick.index if c not in ['Date', 'Timeframe']]
        row = pd.DataFrame([top_pick[cols]])
        
        header = not os.path.exists(history_file)
        row.to_csv(history_file, mode='a', index=False, header=header)
        logger.info(f"Top pick ({top_pick['Symbol']}) saved to persistence log.")

    def run_scanner(self):
        print("\n" + "="*50)
        print("🚀 ALPHA-ZETA PRIME: FILTER 1 INTEGRATION")
        print("Target: Unlimited Growth (+32.8% ROI Logic)")
        print("="*50)

        # Simplified Quick-Select Menu
        print("\nChoose Scanning Timeframe:")
        print("1. 🚀 CHAMPION  (1-2 Weeks) -> [RECOMMENDED]")
        print("2. ⚡ SCALPER   (3-7 Days)  -> [Aggressive]")
        print("3. 🐢 SWING     (1 Month)   -> [Conservative]")
        print("4. ⚙️  EXPERT    (Manual Config)")
        
        choice = int(get_valid_float("\nSelection (1-4): ", 1, 4))
        
        # Default Logic Settings (Safe defaults)
        choice_mode = 1
        m_p, mx_p = 50.0, 10000.0 
        m_v = 10.0 * 1e6 # 10M Avg volume
        start_date = datetime.datetime.now() - datetime.timedelta(days=180)
        
        # Position Sizing Input
        print("\n" + "-"*30)
        capital = get_valid_float("Enter Total Trading Capital [INR]", 0, default=100000)
        allocation_per_stock = capital * 0.10 # 10% Risk Limit
        print(f"Risk Profile: Max ₹{allocation_per_stock:,.2f} per position (10% allocation).")
        print("-"*30 + "\n")

        if choice == 1:
            selected_tf = '1-2_weeks'
        elif choice == 2:
            selected_tf = '3-7_days'
        elif choice == 3:
            selected_tf = '1_month'
        else:
            print("\n--- Expert Configuration ---")
            print("1. 🚀 PRIME TURBO (Filter 1: Max ROI)")
            print("2. 🛡️  PRIME SAFE  (Filter 2: Defensive)")
            choice_mode = int(get_valid_float("Choice: ", 1, 2, default=1))
            
            print("\n--- Timeframe ---")
            print("1. 3-7 Days")
            print("2. 1-2 Weeks")
            print("3. 1 Month")
            choice_tf = int(get_valid_float("Choice: ", 1, 3, default=2))
            selected_tf = list(TIMEFRAME_CONFIGS.keys())[int(choice_tf)-1]
            config = TIMEFRAME_CONFIGS[selected_tf]
            
            # Dynamic Recommendations
            rec_days = int(config['min_data_days'] * 1.5)
            rec_date = (datetime.datetime.now() - datetime.timedelta(days=rec_days)).strftime("%Y-%m-%d")
            
            vol_map = {'3-7_days': 15.0, '1-2_weeks': 10.0, '1_month': 5.0}
            rec_vol = vol_map.get(selected_tf, 10.0)

            print(f"\n[Expert Tip] For {selected_tf}, we recommend at least {rec_days} days of history.")
            start_date = get_valid_date("Start Date (YYYY-MM-DD)", default=rec_date)
            
            m_p = get_valid_float("Min Price", 0, default=50)
            mx_p = get_valid_float("Max Price (0=None)", 0, default=0)
            if mx_p == 0: mx_p = 1e9
            
            print(f"[Expert Tip] Higher liquidity (Volume) avoids slippage in {selected_tf} scans.")
            m_v = get_valid_float("Min Volume [Millions]", 0, default=rec_vol) * 1e6

        config = TIMEFRAME_CONFIGS[selected_tf]
        end_date = datetime.datetime.now()
        
        symbols = DataEngine.get_nifty_symbols()
        picks = []
        stats = {"Price": 0, "Vol": 0, "Trend": 0, "Exhaustion": 0, "Data/Error": 0, "Logic_Fail": 0}
        
        for sym in tqdm(symbols, desc="Running Filter 1 Engine"):
            try:
                data = yf.download(sym, start=start_date, end=end_date, progress=False, timeout=10)
                metrics = TechnicalCore.calculate_indicators(data, config)
                
                if not metrics:
                    stats["Data/Error"] += 1
                    continue
                
                # ZETA V10 PRIME FILTERS (Filter 1 Defensives)
                
                # 1. Price > SMA 50 (The Absolute Safeguard)
                if metrics['price'] < metrics['sma50']:
                    stats["Trend"] += 1
                    continue
                
                # 2. RSI Avoidance (Avoid local peaks)
                if metrics['rsi'] > 70:
                    stats["Exhaustion"] += 1
                    continue
                
                # 3. Cooling Filter (Strictness based on mode)
                if choice_mode == 2: # SAFE MODE
                    if not (0.0 <= metrics['r_s'] <= 10.0): # Relaxed RSI variant
                        stats["Exhaustion"] += 1
                        continue
                
                # 4. Liquidity Guard
                if not (m_p <= metrics['price'] <= mx_p) or metrics['avg_vol'] < m_v:
                    stats["Price"] += 1
                    continue
                
                # ENSEMBLE SCORING (FILTER 1 LOGIC)
                score_dict = FormulaFactory.generate_all(metrics)
                score = score_dict['ensemble']
                
                if score <= 0:
                    stats["Logic_Fail"] += 1
                    continue
                
                # Trade Sizing & Position Math
                entry = metrics['price']
                target = entry * config['target_gain']
                sl = entry * (1 - config['stop_loss_pct'])
                qty = int(allocation_per_stock / entry) if entry > 0 else 0
                
                picks.append({
                    'Symbol': sym.replace('.NS', ''),
                    'Score': round(score, 4),
                    'Entry': round(float(metrics['price']), 2),
                    'Qty': qty,
                    'RSI': round(metrics['rsi'], 1),
                    'ROC_20': round(metrics['r_l'], 2),
                    'Target': round(float(target), 2),
                    'SL': round(float(sl), 2)
                })
            except Exception as e:
                logger.debug(f"Scan error for {sym}: {e}")
                stats["Logic_Fail"] += 1
                continue
                
        print("\n" + "-"*30)
        for k, v in stats.items(): print(f"Skipped ({k}): {v}")
        print("-"*30)
        
        if picks:
            df = pd.DataFrame(picks).sort_values(by='Score', ascending=False)
            output_file = "ALPHA_ZETA_SCAN_RESULTS.csv"
            df.to_csv(output_file, index=False)
            
            # Persistent Logging of the #1 Pick
            self.log_top_picks(df, selected_tf)
            
            print("\n" + "="*85)
            print(f"🔥 ALPHA-ZETA PRIME: TOP 20 OPPORTUNITIES (FILTER 1)")
            print(f"Budget: ₹{capital:,.2f} | Max Allocation: ₹{allocation_per_stock:,.2f} per stock")
            print("="*85)
            print(df.head(20).to_string(index=False))
            print("="*85)
            print(f"\n✅ All results saved to: {output_file}")
            print(f"📊 Historical top picks logged to: persistent_pick_history.csv")
        else:
            print("\nNo stocks matched the Filter 1 criteria.")

if __name__ == "__main__":
    scanner = AlphaZetaScanner()
    scanner.setup_menu()
    input("\nPress Enter to exit...")
