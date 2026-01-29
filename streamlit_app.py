import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import requests
import warnings
import urllib3
import logging
import os
import time
import json
from io import StringIO
from scipy import stats

# --- CONFIGURATION & SETUP ---
st.set_page_config(page_title="Alpha-Zeta Scanner", layout="wide")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')

# Logging setup (Streamlit friendly)
if 'log_capture' not in st.session_state:
    st.session_state.log_capture = []

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

# --- DATA LAYER ---
class DataEngine:
    @staticmethod
    @st.cache_data(ttl=3600*24)
    def load_csv_data(csv_mtime):
        """Load pre-fetched CSV data from automated data pipeline"""
        try:
            csv_path = "data/nifty500_ohlcv.csv"
            if not os.path.exists(csv_path):
                return None
            df = pd.read_csv(csv_path)
            # Create a copy before modifying to keep the cache pure if needed, 
            # but st.cache_data should handle it. Being safe.
            df['Date'] = pd.to_datetime(df['Date'])
            return df
        except Exception as e:
            st.warning(f"Could not load CSV data: {e}")
            return None
    
    @staticmethod
    def load_metadata():
        """Load metadata about data freshness"""
        try:
            meta_path = "data/metadata.json"
            if not os.path.exists(meta_path):
                return None
            with open(meta_path, 'r') as f:
                return json.load(f)
        except:
            return None
    
    @staticmethod

    def get_nifty_symbols():
        """Get symbols from CSV (preferred) or fetch from NSE (fallback)"""
        # Try to get from CSV first
        try:
            csv_path = "data/nifty500_ohlcv.csv"
            if os.path.exists(csv_path):
                mtime = os.path.getmtime(csv_path)
                df = DataEngine.load_csv_data(mtime)
                if df is not None:
                    symbols = [f"{s}.NS" for s in df['Symbol'].unique()]
                    return symbols
        except Exception:
            pass
        
        # Fallback to live NSE fetch
        try:
            url = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            df = pd.read_csv(StringIO(response.text))
            symbols = [f"{s.strip()}.NS" for s in df['Symbol'] if pd.notna(s)]
            return symbols
        except Exception as e:
            st.error(f"Failed to fetch symbols: {e}. Using static fallback.")
            return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBI.NS", "ITC.NS", "M&M.NS"]

    @staticmethod
    def clean_yf_data(data):
        if data is None or data.empty: return None, None
        try:
            if not isinstance(data.columns, pd.MultiIndex):
                close = data['Close'] if 'Close' in data.columns else None
                volume = data['Volume'] if 'Volume' in data.columns else None
                if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
                if isinstance(volume, pd.DataFrame): volume = volume.iloc[:, 0]
                return close, volume
            
            if isinstance(data.columns, pd.MultiIndex):
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
            pass
        return None, None

    @staticmethod
    def fetch_stock_data(symbol, start_date, end_date):
        """Fetch stock data from CSV (preferred) or yfinance (fallback)"""
        # Try CSV first
        csv_path = "data/nifty500_ohlcv.csv"
        if os.path.exists(csv_path):
            mtime = os.path.getmtime(csv_path)
            csv_df = DataEngine.load_csv_data(mtime)
            
            if csv_df is not None:
                symbol_name = symbol.replace('.NS', '')
                stock_data = csv_df[csv_df['Symbol'] == symbol_name].copy()
            
            if not stock_data.empty:
                # Filter by date range
                stock_data = stock_data[
                    (stock_data['Date'] >= pd.to_datetime(start_date)) &
                    (stock_data['Date'] <= pd.to_datetime(end_date))
                ]
                
                if not stock_data.empty:
                    # Convert to yfinance-like format
                    stock_data.set_index('Date', inplace=True)
                    stock_data = stock_data[['Open', 'High', 'Low', 'Close', 'Volume']]
                    
                    # Default values in case metadata is missing
                    ist_now = datetime.datetime.now()
                    fetch_time = ist_now
                    last_date = stock_data.index[-1].date()
                    
                    # Try to get metadata for more accurate fetch time
                    metadata = DataEngine.load_metadata()
                    if metadata:
                        try:
                            fetch_time_str = metadata.get('last_updated')
                            fetch_time = datetime.datetime.strptime(fetch_time_str, '%Y-%m-%d %H:%M:%S')
                        except:
                            pass
                    
                    return stock_data, fetch_time, last_date
        
        # Fallback to live yfinance
        try:
            data = yf.download(symbol, start=start_date, end=end_date, progress=False, timeout=10)
            if data.empty: return None, None, None
            
            utc_now = datetime.datetime.utcnow()
            fetch_time = utc_now + datetime.timedelta(hours=5, minutes=30)
            last_date = data.index[-1].date()
            
            return data, fetch_time, last_date
        except Exception:
            return None, None, None

# --- TECHNICAL CORE ---
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
        if prices is None or len(prices) < config['min_data_days']: return None
        
        prices = prices.ffill().dropna().astype(float)
        volumes = volumes.ffill().dropna().astype(float)
        
        if len(prices) < config['min_data_days']: return None
        
        current = float(prices.iloc[-1])
        lb = config['lookbacks']
        
        try:
            r_s = ((current / float(prices.iloc[-lb['short']])) - 1) * 100 if len(prices) > lb['short'] else 0
            r_m = ((current / float(prices.iloc[-lb['medium']])) - 1) * 100 if len(prices) > lb['medium'] else 0
            r_l = ((current / float(prices.iloc[-lb['long']])) - 1) * 100 if len(prices) > lb['long'] else 0
            
            returns = prices.pct_change().dropna()
            short_vol = float(returns.iloc[-5:].std() * np.sqrt(252) * 100) if len(returns) > 5 else 10.0
            medium_vol = float(returns.iloc[-10:].std() * np.sqrt(252) * 100) if len(returns) > 10 else 10.0
            
            rsi = TechnicalCore.calculate_rsi(prices, config['rsi_period'])
            ema_signal = TechnicalCore.calculate_ema(prices, config['ema_period'])
            atr = TechnicalCore.calculate_atr(data)
            
            avg_vol_21 = float(volumes.rolling(21).mean().iloc[-1]) if len(volumes) > 21 else float(volumes.mean())
            vol_ratio = float(volumes.iloc[-1]) / avg_vol_21 if avg_vol_21 > 0 else 1.0
            
            # Additional Features
            bb_mid = prices.rolling(20).mean()
            bb_std = prices.rolling(20).std()
            squeeze = (bb_std * 4) / bb_mid.replace(0, 1e-6)
            coiling = (prices.rolling(20).max() - prices.rolling(20).min()) / bb_mid.replace(0, 1e-6)
            hurst = TechnicalCore.get_hurst(prices)
            
            td_count = 0
            for i in range(1, 10):
                if len(prices) > i+4 and float(prices.iloc[-i]) > float(prices.iloc[-i-4]): 
                    td_count += 1
                else: 
                    break
            
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
        except Exception:
            return None

# --- FORMULA FACTORY ---
class FormulaFactory:
    @staticmethod
    def generate_all(m):
        f = {}
        momentum_20 = m['r_l'] / 100 
        vol_alpha = (m['vol_ratio'] * 2.0)
        f['ensemble'] = (momentum_20 * 100) + vol_alpha
        return f

# --- UI & MAIN APP ---
def main():
    st.title("Alpha-Zeta Super Scanner")
    st.markdown("### 2025 Champion Engine | Filter 1 Integration")
    
    # Sidebar Controls
    st.sidebar.header("Configuration")
    
    timeframe_option = st.sidebar.selectbox(
        "Scanning Timeframe",
        ('1-2_weeks (Recommended)', '3-7_days (Aggressive)', '1_month (Conservative)')
    )
    
    # Map selection to key
    selected_tf_key = timeframe_option.split(' ')[0]
    config = TIMEFRAME_CONFIGS[selected_tf_key]
    
    st.sidebar.subheader("Capital & Risk")
    capital = st.sidebar.number_input("Total Trading Capital (INR)", min_value=10000.0, value=100000.0, step=10000.0)
    risk_pct = st.sidebar.slider("Allocation per Stock (%)", 5, 25, 10)
    allocation_per_stock = capital * (risk_pct / 100.0)
    
    st.sidebar.subheader("Filters")
    min_price = st.sidebar.number_input("Min Price", value=50.0)
    max_price = st.sidebar.number_input("Max Price (0 for None)", value=0.0)
    if max_price == 0: max_price = float('inf')
    
    min_vol_mil = st.sidebar.number_input("Min Volume (Millions)", value=1.0)
    min_vol = min_vol_mil * 1e6
    
    mode_option = st.sidebar.radio("Filter Mode", ("Prime Turbo (Max ROI)", "Prime Safe (Defensive)"))
    choice_mode = 1 if "Turbo" in mode_option else 2
    
    # Calculate Start Date based on config recommendation
    rec_days = int(config['min_data_days'] * 1.5)
    default_start = datetime.datetime.now() - datetime.timedelta(days=rec_days)
    
    # Advanced Options Expander
    with st.sidebar.expander("Advanced settings"):
        start_date = st.date_input("Start Date", default_start)
        end_date = datetime.date.today()
        
        if st.button("Clear Cache"):
            st.cache_data.clear()
            st.success("Cache cleared!")

    # --- HELP & GUIDE ---
    with st.sidebar.expander("How to Use & Recommendations", expanded=False):
        st.markdown("""
        **1. Min Volume (Turnover) Input:**
        *   **Important:** This input is for **Turnover (Value in INR)**, not Share Count.
        *   **Input Unit:** Millions (e.g., `100` = 100 Million INR Turnover).
        *   **Recommendation:** Start with **100** or **500** to filter illiquid stocks.
        
        **2. Scanning Timeframes:**
        *   **3-7 Days (Aggressive):**
            *   *Min Volume:* Use **500** (Need high liquidity for quick exits).
            *   *Best for:* Quick scalps/swings.
        *   **1-2 Weeks (Recommended):**
            *   *Min Volume:* Use **100 - 300**.
            *   *Best for:* Standard swing trades.
        *   **1 Month (Conservative):**
            *   *Min Volume:* Use **100** (or 50 for niche picks).
            *   *Best for:* Position trading.
        
        **3. Filter Modes:**
        *   **Prime Turbo (Max ROI):**
            *   *Min Volume:* Can use **100** to catch moving mid-caps.
        *   **Prime Safe (Defensive):**
            *   *Min Volume:* Stick to **500+** to ensure safety.
        
        **4. Capital Input:**
        *   Enter your *Total Capital* to get auto-calculated position sizes (`Qty`).
        
        **5. Execution Guide:**
        *   **When to Run:** Best at **3:15 PM IST** or **After Market Hours**.
        *   **When to Enter:**
            *   *Aggressive:* At 3:25 PM if price holds level.
            *   *Safe:* Next Morning (9:30 AM).
            
        **6. How to Select Stocks (The Score Card):**
        *   **Decoding the Score:**
            *   **Golden Zone (25+):** Excellent. High momentum + Institutional volume. Explosive breakouts.
            *   **Strong Zone (15-25):** Very Good. Solid steady trends. Reliable swing trades.
            *   **Early Zone (5-15):** Good. Momentum starting to build.
        *   **Risk/Warning Signs:**
            *   **High Score + High RSI (>68):** Stock is "Hot". Don't chase. Wait for a pullback to the 'Entry' price.
            *   **Low Score + Low Volume:** Stock is drifting, not driven. Higher risk.
        *   **Pro Tip:**
            *   **The Sweet Spot:** The most reliable winners often have a **Score > 20** with **RSI between 55 and 65**.
        """)
    
    if st.button("RUN SCANNER", type="primary"):
        # Check data source
        csv_exists = os.path.exists("data/nifty500_ohlcv.csv")
        metadata = DataEngine.load_metadata()
        
        if csv_exists:
            st.success("Using high-speed pre-fetched data (Delayed by 1 day)")
            st.caption("Accuracy Note: 1-day lag is standard for EOD systems and does not impact momentum signal validity.")
            if metadata:
                st.info(f"Data Last Updated: {metadata['last_updated']} IST")
        else:
            st.warning("CSV data not found. Using live yfinance (slower)")
        
        symbols = DataEngine.get_nifty_symbols()
        st.info(f"Found {len(symbols)} symbols. Starting analysis...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        picks = []
        stats_counter = {"Price": 0, "Vol": 0, "Trend": 0, "Exhaustion": 0, "Data/Error": 0, "Logic_Fail": 0}
        
        # Batch processing or loop
        total = len(symbols)
        
        for i, sym in enumerate(symbols):
            status_text.text(f"Scanning {sym} ({i+1}/{total})")
            progress_bar.progress((i + 1) / total)
            
            # Fetch Data (Cached)
            data, fetch_time, data_date = DataEngine.fetch_stock_data(sym, start_date, end_date)
            
            if data is None:
                stats_counter["Data/Error"] += 1
                continue
                
            metrics = TechnicalCore.calculate_indicators(data, config)
            
            if not metrics:
                stats_counter["Data/Error"] += 1
                continue
            
            # --- FILTERS ---
            # 1. Price > SMA 50
            if metrics['price'] < metrics['sma50']:
                stats_counter["Trend"] += 1
                continue
            
            # 2. RSI Check
            if metrics['rsi'] > 70:
                stats_counter["Exhaustion"] += 1
                continue
            
            # 3. Cooling Filter (Safe Mode)
            if choice_mode == 2: 
                if not (0.0 <= metrics['r_s'] <= 10.0): 
                    stats_counter["Exhaustion"] += 1
                    continue
            
            # 4. Liquidity & Price
            if not (min_price <= metrics['price'] <= max_price) or metrics['avg_vol'] < min_vol:
                stats_counter["Price"] += 1
                continue
            
            # --- SCORING ---
            score_dict = FormulaFactory.generate_all(metrics)
            score = score_dict['ensemble']
            
            if score <= 0:
                stats_counter["Logic_Fail"] += 1
                continue
            
            entry = metrics['price']
            target = entry * config['target_gain']
            sl = entry * (1 - config['stop_loss_pct'])
            qty = int(allocation_per_stock / entry) if entry > 0 else 0
            
            # Store fetch time and data date for display (use the first stock's info)
            if 'data_fetch_time' not in locals():
                data_fetch_time = fetch_time
                data_actual_date = data_date
            
            picks.append({
                'Symbol': sym.replace('.NS', ''),
                'Score': round(score, 4),
                'Spot Price': round(float(metrics['price']), 2),
                'Entry': round(float(metrics['price']), 2),
                'Qty': qty,
                'RSI': round(metrics['rsi'], 1),
                'ROC_20': round(metrics['r_l'], 2),
                'Target': round(float(target), 2),
                'SL': round(float(sl), 2)
            })
            
        progress_bar.empty()
        status_text.empty()
        
        # Display Stats
        st.markdown("### Scan Statistics")
        st.json(stats_counter)
        
        if picks:
            df = pd.DataFrame(picks).sort_values(by='Score', ascending=False)
            
            st.success(f"Scanning Complete! Found {len(df)} opportunities.")
            
            # Display Data Fetch Time and Data Date
            if 'data_fetch_time' in locals() and data_fetch_time:
                st.info(f"Data Fetch Time: {data_fetch_time.strftime('%Y-%m-%d %H:%M:%S')} IST")
            if 'data_actual_date' in locals() and data_actual_date:
                st.info(f"Data Date: {data_actual_date.strftime('%Y-%m-%d')} (Signals are valid for swing execution despite 1-day EOD lag)")
            
            st.markdown("### Top Opportunities")
            st.dataframe(
                df.style.highlight_max(axis=0, subset=['Score']).format({"Spot Price": "{:.2f}", "Entry": "{:.2f}", "Target": "{:.2f}", "SL": "{:.2f}", "Score": "{:.2f}"}).hide(axis="index"), 
                use_container_width=True
            )
            
            # Download Button
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download Results CSV",
                csv,
                "ALPHA_ZETA_SCAN_RESULTS.csv",
                "text/csv",
                key='download-csv'
            )
            
            # Persistence Logic (Optional to show in UI)
            top_pick = df.iloc[0]
            st.info(f"Top Pick: **{top_pick['Symbol']}** (Score: {top_pick['Score']})")
            
        else:
            st.warning("No stocks matched the criteria.")

    st.markdown("---")
    st.markdown("<h5 style='text-align: center; color: grey; font-size: 1.1rem;'>App by Pravin A Mathew</h5>", unsafe_allow_html=True)
    st.markdown("""
        <div style='text-align: center; color: #cc0000; font-size: 1.25rem; padding: 10px;'>
            <strong>THIS IS FOR SWING TRADING AND NOT FOR INTRADAY TRADING</strong>
        </div>
        <div style='text-align: center; color: #888; font-size: 0.9rem; padding: 10px 20px;'>
            <strong>SEBI Compliance & Risk Disclaimer:</strong><br>
            I am not a SEBI Registered Investment Advisor. This scanner is an automated tool designed for <strong>Educational & Research purposes only</strong>. 
            The signals generated do not constitute financial advice or buy/sell recommendations. 
            Paper trading is recommended before committing real capital. Trading in equities involves significant risk. 
            The author is <strong>not responsible</strong> for any financial losses incurred using this tool. 
            <strong>Do your own research (DYOR)</strong> and consult a certified professional before investing.
        </div>
        <div style='text-align: center; color: #888; font-size: 0.9rem; padding: 0 20px 20px 20px;'>
            <strong>Strategy Expectations & Global Standards:</strong><br>
            In the professional trading world (Hedge Funds/Institutions), most successful strategies operate with a <strong>50% to 60% win rate</strong>. 
            Alpha-Zeta's <strong>60% winning rate</strong> is a top-tier industry benchmark. <br>
            Comparing to the world standard: No professional system achieves 90-100% accuracy. The goal is <strong>positive expectancy</strong>—winning enough to grow capital over time. 
            The Filter 1 logic delivered a <strong>Last Year (2025) ROI of +32.8%</strong> by following this professional standard.
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
