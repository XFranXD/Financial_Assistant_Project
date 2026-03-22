"""
module_earnings_consistency.py
Module 6: Earnings Consistency (weight: 10%)

Measures stability and predictability of net income over 8 quarters.
Volatile earnings are harder to model and indicate higher fundamental uncertainty.

EVI formula uses absolute mean to handle near-zero or negative income:
    EVI = std(net_income) / mean(|net_income|)

Using bare mean caused division instability near zero. Absolute mean is stable
regardless of whether earnings are positive, negative, or mixed.

One-time item detection: flag any quarter where NI deviates > 2.5σ from the 8Q mean.
These indicate restructuring charges, write-downs, or one-time gains masking true performance.

Flag trigger: EVI > 0.60 OR more than 2 outlier quarters

Debug logging: [M4] prefix
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)

FLAG = "VOLATILE EARNINGS"
OUTLIER_SIGMA = 2.5


def run(time_series: dict, quarters_available: int) -> dict:
    logger.debug(f"[M4] Running with {quarters_available} quarters")

    net_income = [v for _, v in time_series["net_income"]]
    n = len(net_income)

    if n < 4:
        logger.warning("[M4] Need at least 4 quarters.")
        return _build_result(50, None, "flat", "Insufficient data to assess earnings consistency.", {}, trend_strength=None)

    arr = np.array(net_income, dtype=float)
    mean_ni = float(np.mean(arr))
    std_ni = float(np.std(arr))
    abs_mean = float(np.mean(np.abs(arr)))

    # EVI using absolute mean — stable for negative or near-zero income
    if abs_mean < 1000:
        evi = 1.0
        logger.warning(f"[M4] abs_mean near zero ({abs_mean}). Setting EVI=1.0.")
    else:
        evi = std_ni / abs_mean

    outlier_quarters = []
    if std_ni > 0:
        for i, v in enumerate(net_income):
            if abs(v - mean_ni) > OUTLIER_SIGMA * std_ni:
                outlier_quarters.append(i)
                logger.debug(
                    f"[M4] Outlier Q{i}: val={v:.0f}, "
                    f"z={abs(v - mean_ni)/std_ni:.2f}σ"
                )

    logger.debug(f"[M4] EVI={evi:.3f}, outliers={len(outlier_quarters)}")

    # Trend slope: catches steady decline masked by low variance
    slope = _linear_slope(net_income)
    slope_pct = (slope / abs_mean) if abs_mean > 1000 else 0.0

    logger.debug(f"[M4] slope_pct={slope_pct:.4f} per quarter")

    flag = FLAG if (evi > 0.60 or len(outlier_quarters) > 2) else None
    score = _score(evi, len(outlier_quarters), slope_pct)
    plain_english = _plain_english(evi, len(outlier_quarters), slope_pct, flag)
    trend = "up" if slope_pct > 0.03 else ("down" if slope_pct < -0.03 else "flat")

    return _build_result(score, flag, trend, plain_english, {
        "evi": round(evi, 3),
        "mean_ni": round(mean_ni, 0),
        "std_ni": round(std_ni, 0),
        "abs_mean": round(abs_mean, 0),
        "outlier_count": len(outlier_quarters),
        "outlier_indices": outlier_quarters,
        "slope_pct": round(slope_pct, 4)
    }, trend_strength=None)


def _score(evi: float, outlier_count: int, slope_pct: float = 0.0) -> float:
    if evi < 0.25 and outlier_count == 0:
        base = 85 + min(15, (0.25 - evi) * 60)
    elif evi < 0.25:
        base = 75.0
    elif evi < 0.50:
        base = 55 + (0.50 - evi) / 0.25 * 20
    elif evi < 0.80:
        base = 25 + (0.80 - evi) / 0.30 * 30
    else:
        base = max(0.0, 25 - (evi - 0.80) * 50)

    outlier_penalty = outlier_count * 8
    # Slope penalty: -5 points per 10% per quarter decline in earnings
    slope_penalty = max(0.0, -slope_pct * 50)
    return round(max(0.0, min(100.0, base - outlier_penalty - slope_penalty)), 1)


def _plain_english(evi: float, outlier_count: int, slope_pct: float, flag) -> str:
    if flag:
        return (
            f"Earnings are highly volatile across the measurement window. "
            f"{outlier_count} unusual quarter(s) detected — possible one-time items or structural instability."
        )
    elif slope_pct < -0.05:
        return "Earnings are declining steadily quarter over quarter, even if volatility appears low."
    elif evi < 0.25 and outlier_count == 0:
        return "Earnings are stable and consistent across all measured quarters."
    elif outlier_count == 1:
        return "One unusual quarter detected, likely a one-time item. Underlying earnings are otherwise consistent."
    else:
        return "Earnings show moderate variability. Not disqualifying but adds forecasting uncertainty."


def _linear_slope(values: list) -> float:
    import numpy as np
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    return float(np.polyfit(x, y, 1)[0]) if len(x) >= 2 else 0.0


def _build_result(score, flag, trend, plain_english, debug, trend_strength=None):
    label = _band_label(score)
    logger.info(f"[M4] Score={score}, Label={label}, Flag={flag}, Trend={trend}")
    return {"module_name": "earnings_consistency", "score": score, "label": label,
            "flag": flag, "trend": trend, "plain_english": plain_english,
            "not_applicable": False, "unknown": False, "anomaly_triggered": False,
            "debug": debug, "trend_strength": trend_strength}


def _band_label(score):
    if score >= 75: return "STRONG"
    elif score >= 55: return "ACCEPTABLE"
    elif score >= 35: return "WEAK"
    else: return "POOR"
