"""Detects pivot-based support and resistance zones with a three-tier confidence fallback."""

import pandas as pd
import numpy as np

def detect_levels(df: pd.DataFrame, consolidation_confirmed: bool) -> dict:
    if len(df) == 0:
        return {
            "key_level_position": "MID_RANGE",
            "distance_to_support_pct": 0.0,
            "distance_to_resistance_pct": 0.0,
            "level_confidence_tier": 3,
            "nearest_support":    None,
            "nearest_resistance": None,
        }

    tail_df = df.tail(90)
    highs = tail_df["High"].values
    lows = tail_df["Low"].values
    closes = tail_df["Close"].values
    
    n = len(tail_df)
    swing_highs = []
    swing_lows = []

    for i in range(3, n - 3):
        before_highs = highs[i-3:i]
        after_highs = highs[i+1:i+4]
        if highs[i] > np.max(before_highs) and highs[i] > np.max(after_highs):
            swing_highs.append(highs[i])
            
        before_lows = lows[i-3:i]
        after_lows = lows[i+1:i+4]
        if lows[i] < np.min(before_lows) and lows[i] < np.min(after_lows):
            swing_lows.append(lows[i])

    def cluster_pivots(pivots):
        if not pivots:
            return []
        pivots = sorted(pivots)
        clusters = [[pivots[0]]]
        for p in pivots[1:]:
            current_mean = np.mean(clusters[-1])
            if abs(p - current_mean) / current_mean <= 0.015:
                clusters[-1].append(p)
            else:
                clusters.append([p])
        return [np.mean(c) for c in clusters]

    res_zones = sorted(cluster_pivots(swing_highs))
    sup_zones = sorted(cluster_pivots(swing_lows))

    current_close = df["Close"].iloc[-1]

    # ── Minimum resistance distance filter ───────────────────────────────────
    # Resistance zones less than MIN_RESIST_DIST_PCT above current price are
    # rejected as non-tradeable targets. In strongly trending stocks, the pivot
    # detector routinely identifies the most recent swing high — which may be
    # only 0.2–0.6% above current price — as "nearest resistance". Using that
    # as price_target produces R:R values of 0.02–0.05 that are geometrically
    # correct but financially meaningless. A real resistance level must be far
    # enough away to represent a genuine price objective.
    # 1.5% chosen as the minimum: below this threshold a target offers less
    # reward than a single day's typical noise for most mid/large-cap stocks.
    MIN_RESIST_DIST_PCT = 0.015

    sups_below = [s for s in sup_zones if s < current_close]
    res_above_raw = [r for r in res_zones if r > current_close]

    # Filter out resistance levels too close to current price to be meaningful
    res_above = [
        r for r in res_above_raw
        if (r - current_close) / current_close >= MIN_RESIST_DIST_PCT
    ]

    nearest_support = max(sups_below) if sups_below else None
    nearest_resistance = min(res_above) if res_above else None

    if len(sups_below) >= 2 and len(res_above) >= 2:
        tier = 1
    elif len(sup_zones) >= 1 or len(res_zones) >= 1:
        tier = 2
        if nearest_support is None:
            if len(df) >= 20:
                nearest_support = df["Low"].tail(20).min()
            else:
                nearest_support = df["Low"].min()
        if nearest_resistance is None:
            # All pivot-based resistance zones were filtered out as too close —
            # fall back to the 20-bar high as a structural ceiling. This is the
            # same fallback tier 3 uses and always produces a level at least as
            # far as the recent trading range high.
            if len(df) >= 20:
                nearest_resistance = df["High"].tail(20).max()
            else:
                nearest_resistance = df["High"].max()
    else:
        tier = 3
        if len(df) >= 20:
            nearest_support = df["Low"].tail(20).min()
            nearest_resistance = df["High"].tail(20).max()
        else:
            nearest_support = df["Low"].min()
            nearest_resistance = df["High"].max()

    key_level_position = "MID_RANGE"
    
    if nearest_resistance is not None and current_close > nearest_resistance and consolidation_confirmed:
        key_level_position = "BREAKOUT"
    elif nearest_resistance is not None and current_close > nearest_resistance and not consolidation_confirmed:
        key_level_position = "NEAR_RESISTANCE"
    elif nearest_support is not None and (current_close - nearest_support) / current_close <= 0.03:
        key_level_position = "NEAR_SUPPORT"
    elif nearest_resistance is not None and (nearest_resistance - current_close) / current_close <= 0.03:
        key_level_position = "NEAR_RESISTANCE"
        
    distance_to_support_pct = 0.0
    distance_to_resistance_pct = 0.0
    
    if nearest_support is not None and current_close > 0:
        distance_to_support_pct = (current_close - nearest_support) / current_close * 100.0
    if nearest_resistance is not None and current_close > 0:
        distance_to_resistance_pct = (nearest_resistance - current_close) / current_close * 100.0
         
    return {
        "key_level_position": key_level_position,
        "distance_to_support_pct": float(distance_to_support_pct),
        "distance_to_resistance_pct": float(distance_to_resistance_pct),
        "level_confidence_tier": tier,
        "nearest_support":    float(nearest_support)    if nearest_support    is not None else None,
        "nearest_resistance": float(nearest_resistance) if nearest_resistance is not None else None,
    }