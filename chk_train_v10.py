from app import AlphaZetaScanner
import os

def train():
    scanner = AlphaZetaScanner()
    # Ensure it uses the correct history file
    # In app.py, scanner.history_file defaults to "trade_history.csv" 
    # but we saved clean data to "backtest_v4_history.csv"
    
    scanner.history_file = "backtest_v4_history.csv"
    print(f"Training V10 Brain from: {scanner.history_file}")
    
    scanner.run_trainer()

if __name__ == "__main__":
    train()
