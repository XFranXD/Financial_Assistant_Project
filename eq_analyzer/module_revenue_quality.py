"""
module_revenue_quality.py
Module 3: Revenue Quality (weight: 16%)

Detects whether revenue growth is backed by real cash collections or
inflated by extending credit to customers (accounts receivable expansion).

Metric 1 — AR/Revenue divergence:
    AR Growth = (AR_now − AR_4Q_ago) / max(|AR_4Q_ago|, 0.01 × trailing_4Q_revenue)
    Rev Growth = (Rev_now − Rev_4Q_ago) / max(|Rev_4Q_ago|, 1)
    Divergence = AR Growth − Rev Growth
    Safe denominator prevents division-by-zero on near-zero AR base.

Metric 2 — DSO (Days Sales Outstanding) trend:
    DSO = (Accounts Receivable / Revenue) × 91.25
    Rising DSO = collections are taking longer = revenue quality deteriorating.

Flag trigger: divergence > 0.15 OR DSO slope > 3 days/quarter

Debug logging: [M3] prefix
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)

FLAG = "AGGRESSIVE AR GROWTH"
DAYS_PER_QUARTER = 91.25


def run(time_series: dict, quarters_available: int) -> dict:
    logger.debug(f"[M3] Running with {quarters_available} quarters")

    revenue = [v for _, v in time_series["revenue"]]
    ar = [v for _, v in time_series["accounts_receivable"]]

    n = len(revenue)  # Date-aligned, equal lengths

    if n < 4:
        logger.warning("[M3] Need at least 4 quarters for YoY comparison.")
        return _build_result(50, None, "flat", "Insufficient data to assess revenue quality.", {})

    trailing_4q_revenue = sum(abs(v) for v in revenue[-4:])

    # YoY comparison: most recent quarter vs same quarter one year ago
    lookback = min(4, n - 1)
    ar_past = ar[-(lookback + 1)]
    rev_past = revenue[-(lookback + 1)]

    ar_floor = max(abs(ar_past), 0.01 * trailing_4q_revenue)
    rev_floor = max(abs(rev_past), 1.0)

    ar_growth = (ar[-1] - ar_past) / ar_floor
    rev_growth = (revenue[-1] - rev_past) / rev_floor
    divergence = ar_growth - rev_growth

    logger.debug(
        f"[M3] ar_growth={ar_growth:.3f}, rev_growth={rev_growth:.3f}, "
        f"divergence={divergence:.3f}"
    )

    # DSO per quarter
    dso_values = []
    for i in range(n):
        if revenue[i] > 0:
            dso_values.append((ar[i] / revenue[i]) * DAYS_PER_QUARTER)

    dso_slope = _linear_slope(dso_values) if len(dso_values) >= 2 else 0.0
    avg_dso = float(np.mean(dso_values)) if dso_values else 0.0

    logger.debug(f"[M3] dso_slope={dso_slope:.3f} days/qtr, avg_dso={avg_dso:.1f} days")

    flag = FLAG if (divergence > 0.15 or dso_slope > 3.0) else None
    score = _score(divergence, dso_slope)
    plain_english = _plain_english(divergence, dso_slope, flag)
    # Trend: falling DSO = improving collections = "up"
    trend = "up" if dso_slope < -0.5 else ("down" if dso_slope > 0.5 else "flat")

    return _build_result(score, flag, trend, plain_english, {
        "ar_growth": round(ar_growth, 3),
        "rev_growth": round(rev_growth, 3),
        "divergence": round(divergence, 3),
        "dso_slope": round(dso_slope, 3),
        "avg_dso": round(avg_dso, 1)
    }, trend_strength=divergence)


def _score(divergence: float, dso_slope: float) -> float:
    if divergence < 0.05 and dso_slope <= 0:
        base = 90.0
    elif divergence < 0.05:
        base = 80.0
    elif divergence < 0.10:
        base = 65.0 - (divergence - 0.05) / 0.05 * 10
    elif divergence < 0.20:
        base = 40.0 - (divergence - 0.10) / 0.10 * 15
    else:
        base = max(0.0, 25.0 - (divergence - 0.20) * 50)

    dso_penalty = max(0.0, dso_slope * 3)
    return round(max(0.0, min(100.0, base - dso_penalty)), 1)


def _plain_english(divergence: float, dso_slope: float, flag) -> str:
    if flag:
        return "Accounts receivable is growing significantly faster than revenue, suggesting aggressive recognition or deteriorating collections."
    elif divergence < 0.05 and dso_slope <= 1.0:
        return "Revenue growth is well-supported by collections. No receivables concerns."
    elif divergence < 0.10:
        return "Receivables growing slightly faster than revenue. Worth monitoring."
    else:
        return "Moderate receivables expansion relative to revenue. Collections efficiency has declined."


def _linear_slope(values: list) -> float:
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    return float(np.polyfit(x, y, 1)[0]) if len(x) >= 2 else 0.0


def _build_result(score, flag, trend, plain_english, debug, trend_strength=None):
    label = _band_label(score)
    logger.info(f"[M3] Score={score}, Label={label}, Flag={flag}, Trend={trend}")
    return {"module_name": "revenue_quality", "score": score, "label": label,
            "flag": flag, "trend": trend, "plain_english": plain_english,
            "not_applicable": False, "unknown": False, "anomaly_triggered": False,
            "debug": debug, "trend_strength": trend_strength}


def _band_label(score):
    if score >= 75: return "STRONG"
    elif score >= 55: return "ACCEPTABLE"
    elif score >= 35: return "WEAK"
    else: return "POOR"
