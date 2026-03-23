"""
volume_scorer.py — System 3 Sector Rotation Detector
Computes volume_score (0–100) using full_history data.
Receives full_history dict and availability flags as parameters.
Never assigns data_confidence.
"""
from statistics import mean


def compute_volume_score(full_history: dict, slope_available: bool, volume_sufficient: bool) -> float:
    """
    Returns volume_score (0–100).

    Hard exits must all pass before any data access.
    """

    # Hard exit guard 1
    if full_history["trading_days"] < 30:
        return 50.0

    # Hard exit guard 2
    if not slope_available or not volume_sufficient:
        return 50.0

    price_today = full_history["close"].iloc[-1]
    price_20_days_ago = full_history["close"].iloc[-20]

    # Hard exit guard 3 — division-by-zero protection (local guard only)
    valid_slope = price_20_days_ago != 0
    if not valid_slope:
        return 50.0

    # ── Price trend (20-day slope) ─────────────────────────────────────────────
    slope = (price_today - price_20_days_ago) / price_20_days_ago
    trend = "uptrend" if slope > 0 else "downtrend"

    # ── Volume trend ───────────────────────────────────────────────────────────
    volume_series = list(full_history["volume"].iloc[-30:])
    vol_10d_avg = mean(volume_series[-10:])
    vol_30d_avg = mean(volume_series[-30:])
    volume_direction = "increasing" if vol_10d_avg > vol_30d_avg else "decreasing"

    # ── Four explicit states ───────────────────────────────────────────────────
    if trend == "uptrend" and volume_direction == "increasing":
        return 100.0
    elif trend == "uptrend" and volume_direction == "decreasing":
        return 50.0
    elif trend == "downtrend" and volume_direction == "increasing":
        return 0.0
    else:  # downtrend + decreasing
        return 40.0
