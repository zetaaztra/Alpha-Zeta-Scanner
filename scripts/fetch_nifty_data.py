import pandas as pd
import yfinance as yf
import requests
from io import StringIO
import datetime
import json
import sys
import os
import time
from pathlib import Path

def get_nifty_symbols():
    """Fetch Nifty 500 symbols from NSE"""
    try:
        # 1. Try fetching from official source with retries
        url = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
        headers = {"User-Agent": "Mozilla/5.0"}
        
        for attempt in range(3):
            try:
                response = requests.get(url, headers=headers, timeout=30, verify=False)
                if response.status_code == 200:
                    df = pd.read_csv(StringIO(response.text))
                    symbols = [f"{s.strip()}.NS" for s in df['Symbol'] if pd.notna(s)]
                    print(f"[OK] Fetched {len(symbols)} symbols from NSE (Attempt {attempt+1})")
                    return symbols
            except Exception as e:
                print(f"  Attempt {attempt+1} failed: {e}")
                time.sleep(2)
        
        # 2. Fallback: Use existing CSV symbols if available
        print("[WARN] Web fetch failed. Trying fallback to existing CSV...")
        existing_csv = Path("data/nifty500_ohlcv.csv")
        if existing_csv.exists():
            df = pd.read_csv(existing_csv)
            symbols = list(df['Symbol'].unique())
            # Ensure .NS suffix
            symbols = [s if s.endswith('.NS') else f"{s}.NS" for s in symbols]
            print(f"[OK] Recovered {len(symbols)} symbols from existing local data")
            return symbols
            
    except Exception as e:
        print(f"[ERROR] Critical failure in symbol fetch: {e}")
        return []
    
    return []

def load_existing_csv():
    """Load existing CSV if it exists"""
    csv_path = Path("data/nifty500_ohlcv.csv")
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
            df['Date'] = pd.to_datetime(df['Date'])
            print(f"[OK] Loaded existing CSV: {len(df)} rows")
            return df
        except Exception as e:
            print(f"[WARN] Could not load existing CSV: {e}")
            return None
    return None

def fetch_all_data(symbols, days=200, existing_df=None):
    """Fetch OHLCV data for all symbols (incremental if existing_df provided)"""
    
    # Determine fetch strategy
    if existing_df is not None and not existing_df.empty:
        # Incremental: Only fetch last 5 days
        last_date = existing_df['Date'].max()
        days_since = (datetime.date.today() - last_date.date()).days
        fetch_days = min(days_since + 2, 10)  # Fetch at most 10 days incrementally
        print(f"[FETCH] Incremental fetch: Last data from {last_date.date()}, fetching {fetch_days} days")
    else:
        # Full fetch: Get all 200 days
        fetch_days = days
        print(f"[FETCH] Full fetch: Getting {fetch_days} days of data")
    
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=fetch_days)
    
    all_data = []
    failed = []
    
    for i, symbol in enumerate(symbols, 1):
        try:
            data = yf.download(symbol, start=start_date, end=end_date, progress=False)
            if data.empty:
                failed.append(symbol)
                continue
            
            # Handle MultiIndex
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            # Reset index to get Date as column
            data.reset_index(inplace=True)
            data['Symbol'] = symbol.replace('.NS', '')
            
            # Select relevant columns
            data = data[['Symbol', 'Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
            all_data.append(data)
            
            if i % 50 == 0:
                print(f"  Progress: {i}/{len(symbols)} stocks fetched...")
                
        except Exception as e:
            failed.append(symbol)
            continue
    
    if failed:
        print(f"[ERROR] Failed to fetch {len(failed)} stocks")
    
    if not all_data:
        print("[ERROR] No data fetched!")
        sys.exit(1)
    
    new_df = pd.concat(all_data, ignore_index=True)
    new_df['Date'] = pd.to_datetime(new_df['Date'])
    
    # If incremental, merge with existing data
    if existing_df is not None:
        print(f"[MERGE] Merging with existing data...")
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        # Remove duplicates (keep newest)
        combined = combined.drop_duplicates(subset=['Symbol', 'Date'], keep='last')
        combined = combined.sort_values(['Symbol', 'Date'])
        
        # Keep only last 200 days per symbol
        cutoff_date = datetime.date.today() - datetime.timedelta(days=200)
        combined = combined[combined['Date'] >= pd.to_datetime(cutoff_date)]
        
        print(f"[OK] Merged: {len(combined)} total rows (removed old data)")
        return combined
    
    print(f"[OK] Fetched data for {len(all_data)} stocks")
    return new_df

def save_data(df, metadata):
    """Save CSV and metadata"""
    # Ensure data directory exists
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Save CSV
    csv_path = data_dir / "nifty500_ohlcv.csv"
    df.to_csv(csv_path, index=False)
    print(f"[OK] Saved CSV: {csv_path} ({len(df)} rows)")
    
    # Save metadata
    meta_path = data_dir / "metadata.json"
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"[OK] Saved metadata: {meta_path}")

def main():
    print("="*50)
    print("Nifty 500 Data Fetch - Automated")
    print("="*50)
    
    # Get symbols
    symbols = get_nifty_symbols()
    if not symbols:
        print("[ERROR] No symbols to fetch. Exiting.")
        sys.exit(1)
    
    # Load existing CSV
    existing_df = load_existing_csv()
    
    # Fetch data (incremental if possible)
    print(f"\nFetching OHLCV data for {len(symbols)} stocks...")
    df = fetch_all_data(symbols, days=200, existing_df=existing_df)
    
    # Create metadata
    ist_now = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=5, minutes=30)
    
    metadata = {
        "last_updated": ist_now.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "IST",
        "total_stocks": len(df['Symbol'].unique()),
        "total_records": len(df),
        "date_range": {
            "start": df['Date'].min().strftime("%Y-%m-%d"),
            "end": df['Date'].max().strftime("%Y-%m-%d")
        },
        "fetch_mode": "incremental" if existing_df is not None else "full"
    }
    
    # Save
    save_data(df, metadata)
    
    print("\n" + "="*50)
    print("[OK] Data fetch completed successfully!")
    print(f"  Mode: {metadata['fetch_mode']}")
    print(f"  Date range: {metadata['date_range']['start']} to {metadata['date_range']['end']}")
    print("="*50)

if __name__ == "__main__":
    main()
