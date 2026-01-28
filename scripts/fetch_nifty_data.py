import pandas as pd
import yfinance as yf
import requests
from io import StringIO
import datetime
import json
import sys
import os
from pathlib import Path

def get_nifty_symbols():
    """Fetch Nifty 500 symbols from NSE"""
    try:
        url = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        df = pd.read_csv(StringIO(response.text))
        symbols = [f"{s.strip()}.NS" for s in df['Symbol'] if pd.notna(s)]
        print(f"✓ Fetched {len(symbols)} symbols from NSE")
        return symbols
    except Exception as e:
        print(f"✗ Failed to fetch symbols: {e}")
        return []

def load_existing_csv():
    """Load existing CSV if it exists"""
    csv_path = Path("data/nifty500_ohlcv.csv")
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
            df['Date'] = pd.to_datetime(df['Date'])
            print(f"✓ Loaded existing CSV: {len(df)} rows")
            return df
        except Exception as e:
            print(f"⚠ Could not load existing CSV: {e}")
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
        print(f"📥 Incremental fetch: Last data from {last_date.date()}, fetching {fetch_days} days")
    else:
        # Full fetch: Get all 200 days
        fetch_days = days
        print(f"📥 Full fetch: Getting {fetch_days} days of data")
    
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
        print(f"✗ Failed to fetch {len(failed)} stocks")
    
    if not all_data:
        print("✗ No data fetched!")
        sys.exit(1)
    
    new_df = pd.concat(all_data, ignore_index=True)
    new_df['Date'] = pd.to_datetime(new_df['Date'])
    
    # If incremental, merge with existing data
    if existing_df is not None:
        print(f"🔄 Merging with existing data...")
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        # Remove duplicates (keep newest)
        combined = combined.drop_duplicates(subset=['Symbol', 'Date'], keep='last')
        combined = combined.sort_values(['Symbol', 'Date'])
        
        # Keep only last 200 days per symbol
        cutoff_date = datetime.date.today() - datetime.timedelta(days=200)
        combined = combined[combined['Date'] >= pd.to_datetime(cutoff_date)]
        
        print(f"✓ Merged: {len(combined)} total rows (removed old data)")
        return combined
    
    print(f"✓ Fetched data for {len(all_data)} stocks")
    return new_df

def save_data(df, metadata):
    """Save CSV and metadata"""
    # Ensure data directory exists
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Save CSV
    csv_path = data_dir / "nifty500_ohlcv.csv"
    df.to_csv(csv_path, index=False)
    print(f"✓ Saved CSV: {csv_path} ({len(df)} rows)")
    
    # Save metadata
    meta_path = data_dir / "metadata.json"
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"✓ Saved metadata: {meta_path}")

def main():
    print("="*50)
    print("Nifty 500 Data Fetch - GitHub Actions")
    print("="*50)
    
    # Get symbols
    symbols = get_nifty_symbols()
    if not symbols:
        print("✗ No symbols to fetch. Exiting.")
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
    print("✓ Data fetch completed successfully!")
    print(f"  Mode: {metadata['fetch_mode']}")
    print(f"  Date range: {metadata['date_range']['start']} to {metadata['date_range']['end']}")
    print("="*50)

if __name__ == "__main__":
    main()
