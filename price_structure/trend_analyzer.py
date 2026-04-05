"""Computes trend structure and strength using linear regression slope percentile normalization."""

import pandas as pd
import numpy as np

def analyze_trend(df: pd.DataFrame) -> dict:
    if len(df) == 0:
        return {"trend_structure": "SIDEWAYS", "trend_strength": 0, "recent_crossover": False}

    # Rolling 20-day and 50-day MA
    ma20 = df["Close"].rolling(20, min_periods=1).mean()
    ma50 = df["Close"].rolling(50, min_periods=1).mean()

    closes = df["Close"].values
    n = len(closes)
    slopes = []

    for i in range(n):
        if i < 19:
            slopes.append(np.nan)
        else:
            window = closes[i-19:i+1]
            x = np.arange(20)
            slope, _ = np.polyfit(x, window, 1)
            slopes.append(slope)

    slope_series = pd.Series(slopes, index=df.index)

    if slope_series.dropna().empty:
        trend_strength = 0
    else:
        ranked = slope_series.dropna().rank(pct=True)
        current_percentile_rank = ranked.iloc[-1]
        trend_strength = int(np.clip(round(current_percentile_rank * 100), 0, 100))

    current_close = df["Close"].iloc[-1]
    current_ma50 = ma50.iloc[-1]

    if trend_strength >= 55 and current_close > current_ma50:
        trend_structure = "UP"
    elif trend_strength <= 45 and current_close < current_ma50:
        trend_structure = "DOWN"
    else:
        trend_structure = "SIDEWAYS"

    diff = ma20 - ma50
    if len(diff) < 10:
        recent_crossover = False
    else:
        sign_today = np.sign(diff.iloc[-1])
        sign_10_ago = np.sign(diff.iloc[-10])
        if sign_today != 0 and sign_10_ago != 0 and sign_today != sign_10_ago:
            recent_crossover = True
        else:
            recent_crossover = False

    return {
        "trend_structure": trend_structure,
        "trend_strength": trend_strength,
        "recent_crossover": recent_crossover
    }
