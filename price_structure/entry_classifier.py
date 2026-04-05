"""Classifies entry quality using trend, level, and volatility signals with strict priority rules."""

import pandas as pd

def classify_entry(
    df: pd.DataFrame,
    trend: dict,
    levels: dict,
    volatility: dict
) -> dict:
    if len(df) == 0:
        return {
            "entry_quality": "WEAK", "move_extension_pct": 0.0,
            "support_reaction": False, "base_duration_days": 0,
            "volume_contraction": False, "structure_state": "CONSOLIDATING"
        }

    # move_extension_pct
    low_126 = df["Low"].tail(126).min()
    current_close = df["Close"].iloc[-1]
    move_extension_pct = 0.0
    if low_126 > 0:
        move_extension_pct = (current_close - low_126) / low_126 * 100.0

    # support_reaction
    support_reaction = False
    dist_sup = levels.get("distance_to_support_pct", 0.0)
    if dist_sup == 0.0:
        support_reaction = False
    else:
        support = current_close * (1 - dist_sup / 100.0)
        last_5 = df.tail(5)
        for idx, row in last_5.iterrows():
            if abs(row["Low"] - support) / support <= 0.015 and row["Close"] > row["Open"]:
                support_reaction = True
                break

    # base_duration_days
    avg_range = (df["High"] - df["Low"]).rolling(20, min_periods=1).mean()
    base_duration_days = 0
    n = len(df)
    for i in range(n-1, -1, -1):
        rng = df["High"].iloc[i] - df["Low"].iloc[i]
        ar = avg_range.iloc[i]
        if rng <= 1.5 * ar:
            base_duration_days += 1
        else:
            break

    # volume_contraction
    volume_contraction = False
    if base_duration_days >= 3:
        base_window_vol = df["Volume"].iloc[-base_duration_days:]
        ref_start = max(0, n - base_duration_days - 20)
        ref_end = n - base_duration_days
        ref_window_vol = df["Volume"].iloc[ref_start:ref_end]
        
        if len(ref_window_vol) >= 5:
            if base_window_vol.mean() <= 0.80 * ref_window_vol.mean():
                volume_contraction = True

    # Entry quality rules
    entry_quality = "WEAK"
    
    t_struct = trend.get("trend_structure", "SIDEWAYS")
    t_strength = trend.get("trend_strength", 0)
    v_state = volatility.get("volatility_state", "NORMAL")
    c_loc = volatility.get("compression_location", "NEUTRAL")
    c_conf = volatility.get("consolidation_confirmed", False)
    l_pos = levels.get("key_level_position", "MID_RANGE")
    
    current_vol = df["Volume"].iloc[-1]
    avg_20_vol = df["Volume"].tail(20).mean() if len(df) >= 20 else current_vol

    if move_extension_pct > 50:
        entry_quality = "EXTENDED"
    elif t_struct == "UP" and l_pos == "NEAR_SUPPORT" and support_reaction and move_extension_pct < 50 and t_strength >= 50:
        entry_quality = "GOOD"
    elif t_struct == "UP" and l_pos == "BREAKOUT" and c_conf and base_duration_days >= 3 and current_vol >= 1.20 * avg_20_vol:
        entry_quality = "GOOD"
    elif t_struct == "UP" and l_pos == "MID_RANGE" and 15 <= move_extension_pct <= 45 and v_state != "EXPANDING" and t_strength >= 65:
        entry_quality = "GOOD"
    elif t_struct == "UP" and l_pos == "NEAR_RESISTANCE" and dist_sup > 8:
        entry_quality = "EXTENDED"
    elif t_struct == "SIDEWAYS" and v_state == "COMPRESSING" and c_loc == "BULLISH" and move_extension_pct < 30:
        entry_quality = "EARLY"
    elif t_struct == "DOWN":
        entry_quality = "WEAK"
    elif t_strength < 30:
        entry_quality = "WEAK"
    else:
        entry_quality = "WEAK"

    # structure_state
    if t_struct in ("UP", "DOWN") and t_strength >= 50:
        structure_state = "TRENDING"
    elif v_state == "EXPANDING":
        structure_state = "VOLATILE"
    elif t_struct == "SIDEWAYS" and v_state in ("COMPRESSING", "NORMAL"):
        structure_state = "CONSOLIDATING"
    else:
        structure_state = "CONSOLIDATING"

    return {
        "entry_quality": entry_quality,
        "move_extension_pct": float(move_extension_pct),
        "support_reaction": bool(support_reaction),
        "base_duration_days": int(base_duration_days),
        "volume_contraction": bool(volume_contraction),
        "structure_state": structure_state
    }
