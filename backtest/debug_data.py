
import pickle
import pandas as pd
import os

CACHE_FILE = "backtest_v4_data.pkl"

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, 'rb') as f:
        data = pickle.load(f)
    
    print(f"Loaded {len(data)} symbols.")
    
    sample_sym = list(data.keys())[0]
    df = data[sample_sym]
    
    print(f"Sample: {sample_sym}")
    print(f"Start: {df.index[0]}")
    print(f"End: {df.index[-1]}")
    
    target_date = pd.Timestamp("2025-01-06")
    hist = df[df.index <= target_date]
    print(f"History len on {target_date.date()}: {len(hist)}")
    
    # Check how many have > 90 days
    count_valid = 0
    for sym, d in data.items():
        if target_date in d.index:
            h = d[d.index <= target_date]
            if len(h) >= 90:
                count_valid += 1
    
    print(f"Symbols with >= 90 days history on Jan 6: {count_valid}/{len(data)}")
else:
    print("Cache not found.")
