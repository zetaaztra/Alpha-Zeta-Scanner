
import yfinance as yf
import pandas as pd

def check_fundamentals():
    sym = "RELIANCE.NS"
    print(f"Fetching fundamentals for {sym}...")
    ticker = yf.Ticker(sym)
    
    # Check Quarterly Financials
    try:
        q_income = ticker.quarterly_income_stmt
        print("\n--- Quarterly Income Stmt (Columns) ---")
        print(q_income.columns) # Should be dates
        
        if not q_income.empty:
            print("\nSample Data (EBITDA/Total Revenue):")
            # Try to find EBITDA or similar
            rows = [r for r in q_income.index if 'EBITDA' in r or 'Revenue' in r or 'Net Income' in r]
            print(q_income.loc[rows])
            
    except Exception as e:
        print(f"Error fetching income stmt: {e}")
        
    # Check Balance Sheet
    try:
        q_bs = ticker.quarterly_balance_sheet
        print("\n--- Quarterly Balance Sheet (Columns) ---")
        print(q_bs.columns)
    except Exception as e: 
        print(f"Error fetching balance sheet: {e}")

if __name__ == "__main__":
    check_fundamentals()
