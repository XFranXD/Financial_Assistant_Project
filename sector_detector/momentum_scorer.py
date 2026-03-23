"""
momentum_scorer.py — System 3 Sector Rotation Detector
Computes momentum_score (0–100) for a sector ETF.
"""


def _compute_rsi(close_series) -> float:
    """
    Compute 14-period RSI using Wilder's smoothing method.
    Requires at least 15 data points (14 initial deltas + smoothing period).
    """
    close = list(close_series)

    # Initialization: first 14 gains/losses
    gains = [max(close[i] - close[i - 1], 0) for i in range(1, 15)]
    losses = [max(close[i - 1] - close[i], 0) for i in range(1, 15)]
    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14

    # Wilder smoothing for remaining periods
    for i in range(15, len(close)):
        current_gain = max(close[i] - close[i - 1], 0)
        current_loss = max(close[i - 1] - close[i], 0)
        avg_gain = (avg_gain * 13 + current_gain) / 14
        avg_loss = (avg_loss * 13 + current_loss) / 14

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_momentum_score(full_history: dict, timeframes: dict) -> float:
    """
    Returns momentum_score (0–100) for the given ETF data.

    Parameters
    ----------
    full_history : dict
        Full history dict from data_fetcher (Fetch A).
    timeframes : dict
        Timeframe slices dict from data_fetcher (Fetch B), keyed "1M","3M","6M".
    """

    # ── Step 1: MA Alignment Score ─────────────────────────────────────────────
    if full_history["ma_available"]:
        close = full_history["close"]
        price = close.iloc[-1]
        ma50 = close.iloc[-50:].mean()
        ma200 = close.mean()  # 200-day full window mean used as 200MA proxy
        # more accurate: compute from last 200 closing prices
        ma50 = close.iloc[-50:].mean()
        ma200 = close.iloc[-200:].mean()

        if price > ma50 and ma50 > ma200:
            ma_alignment = 100
        elif price > ma50 and ma50 <= ma200:
            ma_alignment = 60
        elif price <= ma50 and ma50 > ma200:
            ma_alignment = 40
        else:  # price <= ma50 and ma50 <= ma200
            ma_alignment = 0
    else:
        ma_alignment = 50

    # ── Step 2: Return Score (weighted across timeframes) ─────────────────────
    base_weights = {"1M": 0.25, "3M": 0.50, "6M": 0.25}

    weighted_sum = 0.0
    available_weights = 0.0

    for tf, base_w in base_weights.items():
        tf_data = timeframes[tf]
        if not tf_data["available"]:
            continue
        close_series = tf_data["close"]
        if len(close_series) < 2:
            continue  # treat as unavailable

        first_close = close_series.iloc[0]
        last_close = close_series.iloc[-1]
        raw_return = (last_close - first_close) / first_close

        # Apply ±15% cap
        capped_return = max(-0.15, min(0.15, raw_return))

        # Normalize: +10% → 100, 0% → 50, -10% → 0 (linear)
        score = 50 + (capped_return / 0.10) * 50
        score = max(0.0, min(100.0, score))

        weighted_sum += score * base_w
        available_weights += base_w

    if available_weights == 0:
        return_score = 50.0
    else:
        # Renormalize across available timeframes
        return_score = weighted_sum / available_weights

    # ── Step 3: RSI Modifier ───────────────────────────────────────────────────
    if full_history["rsi_available"]:
        close = full_history["close"]
        rsi = _compute_rsi(close)
        if rsi > 60:
            rsi_modifier = 10
        elif rsi < 40:
            rsi_modifier = -10
        else:
            rsi_modifier = 0
    else:
        rsi_modifier = 0

    # ── Step 4: Final Momentum Score ───────────────────────────────────────────
    momentum_score = (ma_alignment * 0.6) + (return_score * 0.4) + rsi_modifier
    momentum_score = max(0.0, min(100.0, momentum_score))

    return momentum_score
