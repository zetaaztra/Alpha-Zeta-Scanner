import pandas as pd
import yfinance as yf
import requests
from io import StringIO
import datetime
import json
import sys
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

def fetch_all_data(symbols, days=200):
    """Fetch OHLCV data for all symbols"""
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)
    
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
    
    combined = pd.concat(all_data, ignore_index=True)
    print(f"✓ Successfully fetched data for {len(all_data)} stocks")
    return combined

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
    
    # Fetch data
    print(f"\nFetching OHLCV data for {len(symbols)} stocks...")
    df = fetch_all_data(symbols)
    
    # Create metadata
    utc_now = datetime.datetime.utcnow()
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    
    metadata = {
        "last_updated": ist_now.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "IST",
        "total_stocks": len(df['Symbol'].unique()),
        "total_records": len(df),
        "date_range": {
            "start": df['Date'].min().strftime("%Y-%m-%d"),
            "end": df['Date'].max().strftime("%Y-%m-%d")
        }
    }
    
    # Save
    save_data(df, metadata)
    
    print("\n" + "="*50)
    print("✓ Data fetch completed successfully!")
    print("="*50)

if __name__ == "__main__":
    main()
