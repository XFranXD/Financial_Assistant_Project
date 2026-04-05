"""Computes volatility state, compression location, and consolidation confirmation."""

import pandas as pd
import numpy as np

def analyze_volatility(df: pd.DataFrame) -> dict:
    if len(df) == 0:
        return {"volatility_state": "NORMAL", "compression_location": "NEUTRAL", "consolidation_confirmed": False}

    normalized_range = (df["High"] - df["Low"]) / df["Close"]
    range_20 = normalized_range.rolling(20, min_periods=1).mean()
    range_5 = normalized_range.rolling(5, min_periods=1).mean()

    # Volatility state
    is_compressing = False
    if len(df) >= 3:
        conds = [range_5.iloc[i] < 0.70 * range_20.iloc[i] for i in [-3, -2, -1]]
        if all(conds):
            is_compressing = True

    is_expanding = False
    if len(df) > 0 and range_5.iloc[-1] > 1.30 * range_20.iloc[-1]:
        is_expanding = True

    if is_compressing:
        volatility_state = "COMPRESSING"
    elif is_expanding:
        volatility_state = "EXPANDING"
    else:
        volatility_state = "NORMAL"

    # compression_location
    if volatility_state == "COMPRESSING" and len(df) > 0:
        high_90 = df["High"].tail(90).max()
        low_90 = df["Low"].tail(90).min()
        if high_90 > low_90:
            range_position = (df["Close"].iloc[-1] - low_90) / (high_90 - low_90)
        else:
            range_position = 0.0
        compression_location = "BULLISH" if range_position >= 0.60 else "NEUTRAL"
    else:
        compression_location = "NEUTRAL"

    # consolidation_confirmed
    consolidation_confirmed = False
    if len(df) >= 10:
        # Precompute 90-day high and low rolling
        high_90_rolling = df["High"].rolling(90, min_periods=1).max()
        low_90_rolling = df["Low"].rolling(90, min_periods=1).min()

        count = 0
        for i in range(-10, 0):
            r5 = range_5.iloc[i]
            r20 = range_20.iloc[i]
            if r5 < 0.70 * r20:
                h90 = high_90_rolling.iloc[i]
                l90 = low_90_rolling.iloc[i]
                c = df["Close"].iloc[i]
                pos = (c - l90) / (h90 - l90) if h90 > l90 else 0.0
                if pos >= 0.60:
                    count += 1

        if count >= 5:
            consolidation_confirmed = True

    return {
        "volatility_state": volatility_state,
        "compression_location": compression_location,
        "consolidation_confirmed": consolidation_confirmed
    }
