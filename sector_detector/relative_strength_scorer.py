"""
relative_strength_scorer.py — System 3 Sector Rotation Detector
Computes relative_strength_score (0–100) by comparing ETF returns against SPY.
"""


def compute_relative_strength_score(timeframes: dict) -> float:
    """
    Returns relative_strength_score (0–100).

    Parameters
    ----------
    timeframes : dict
        Timeframe slices dict from data_fetcher, keyed "1M","3M","6M".
        Each entry has: close, available, spy_close, spy_available.
    """
    base_weights = {"1M": 0.25, "3M": 0.50, "6M": 0.25}

    weighted_sum = 0.0
    available_weights = 0.0

    for tf, base_w in base_weights.items():
        tf_data = timeframes[tf]

        if not tf_data["available"]:
            continue

        etf_close_series = tf_data["close"]
        spy_available = tf_data["spy_available"]
        spy_close_series = tf_data["spy_close"]

        # Both ETF and SPY must have at least 2 data points
        if len(etf_close_series) < 2 or not spy_available or len(spy_close_series) < 2:
            continue  # exclude from weighted sum

        # ETF return
        etf_first = etf_close_series.iloc[0]
        etf_last = etf_close_series.iloc[-1]
        etf_return = (etf_last - etf_first) / etf_first

        # SPY return
        spy_first = spy_close_series.iloc[0]
        spy_last = spy_close_series.iloc[-1]
        spy_return = (spy_last - spy_first) / spy_first

        # Relative return
        relative_return = etf_return - spy_return

        # Apply ±15% cap
        relative_return = max(-0.15, min(0.15, relative_return))

        # Normalize: +6% → 100, 0% → 50, -6% → 0 (linear)
        score = 50 + (relative_return / 0.06) * 50
        score = max(0.0, min(100.0, score))

        weighted_sum += score * base_w
        available_weights += base_w

    if available_weights == 0:
        return 50.0

    # Renormalize across available timeframes
    relative_strength_score = weighted_sum / available_weights
    return relative_strength_score
