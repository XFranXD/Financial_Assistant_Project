"""
portfolio/position_sizer.py
Layer 3: Inverse-volatility position weights, normalized to sum to 100%.
Receives returns_data from correlation_engine — no second yfinance fetch.
"""

import logging
import numpy as np

log = logging.getLogger(__name__)


def compute_weights(
    selected_tickers: list[str],
    candidates:       list[dict],
    returns_data:     dict,
) -> dict[str, float]:
    """
    Input:
        selected_tickers: list[str]
        candidates:       list[dict] — unused directly, reserved for future metadata
        returns_data:     dict[str, pd.Series] — daily log returns from correlation_engine

    Output:
        dict[str, float] — weights in %, guaranteed sum == 100.0 (±0.0001)

    Algorithm:
        vol[t]     = std(returns_data[t])
        inv_vol[t] = 1 / vol[t]
        weight[t]  = (inv_vol[t] / sum(inv_vol)) * 100

    Edge cases:
        vol == 0 or NaN → assign fallback = mean of valid inv_vols, or 1.0 if none valid
    """
    if not selected_tickers:
        return {}

    inv_vols: dict[str, float | None] = {}

    for ticker in selected_tickers:
        series = returns_data.get(ticker)
        try:
            if series is None or len(series) < 5:
                raise ValueError('insufficient data')
            vol = float(series.std())
            if vol == 0 or np.isnan(vol):
                raise ValueError('zero or NaN vol')
            inv_vols[ticker] = 1.0 / vol
        except Exception as e:
            log.info(f'[PL] {ticker}: vol edge case ({e}) — will use fallback weight')
            inv_vols[ticker] = None

    valid_vals = [v for v in inv_vols.values() if v is not None]
    fallback = float(np.mean(valid_vals)) if valid_vals else 1.0
    for ticker in selected_tickers:
        if inv_vols[ticker] is None:
            inv_vols[ticker] = fallback

    total = sum(inv_vols.values())
    if total == 0 or np.isnan(total):
        eq = round(100.0 / len(selected_tickers), 2)
        weights = {t: eq for t in selected_tickers}
    else:
        weights = {
            t: round((inv_vols[t] / total) * 100, 2)
            for t in selected_tickers
        }

    # Floating-point normalization — force exact 100.0
    diff = round(100.0 - sum(weights.values()), 2)
    if diff != 0 and weights:
        largest = max(weights, key=lambda t: weights[t])
        weights[largest] = round(weights[largest] + diff, 2)

    log.info(f'[PL] Weights computed: {weights} | Sum: {sum(weights.values())}')
    return weights
