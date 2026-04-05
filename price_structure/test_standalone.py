"""Standalone test script. Run via run_test.sh. Visual inspection only — no assertions."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from price_structure_analyzer import analyze

def run_tests():
    tickers = ["AAPL", "CVX", "MRK"]

    for ticker in tickers:
        print("=" * 50)
        print(f"{ticker}")
        result = analyze(ticker)
        for k, v in result.items():
            print(f"  {k}: {v}")
        print("")

if __name__ == "__main__":
    run_tests()
