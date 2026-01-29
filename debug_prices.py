import pandas as pd
import os
import datetime

# Mock DataEngine logic
def load_csv_data():
    try:
        csv_path = "data/nifty500_ohlcv.csv"
        if not os.path.exists(csv_path):
            return None
        df = pd.read_csv(csv_path)
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    except Exception as e:
        print(f"Error: {e}")
        return None

def fetch_stock_data(symbol, start_date, end_date):
    csv_df = load_csv_data()
    if csv_df is not None:
        symbol_name = symbol.replace('.NS', '')
        stock_data = csv_df[csv_df['Symbol'] == symbol_name].copy()
        
        if not stock_data.empty:
            stock_data = stock_data[
                (stock_data['Date'] >= pd.to_datetime(start_date)) &
                (stock_data['Date'] <= pd.to_datetime(end_date))
            ]
            
            if not stock_data.empty:
                stock_data.set_index('Date', inplace=True)
                # print last price
                return stock_data.iloc[-1]['Close']
    return None

def main():
    start_date = "2025-01-01"
    end_date = "2026-01-29"
    
    print("Checking NAUKRI...")
    price_naukri = fetch_stock_data("NAUKRI.NS", start_date, end_date)
    print(f"NAUKRI Price: {price_naukri}")
    
    print("Checking SONACOMS...")
    price_sona = fetch_stock_data("SONACOMS.NS", start_date, end_date)
    print(f"SONACOMS Price: {price_sona}")
    
    print("Checking INDUSTOWER...")
    price_indus = fetch_stock_data("INDUSTOWER.NS", start_date, end_date)
    print(f"INDUSTOWER Price: {price_indus}")

if __name__ == "__main__":
    main()
