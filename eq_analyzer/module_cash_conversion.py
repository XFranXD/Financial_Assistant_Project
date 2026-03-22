"""
module_cash_conversion.py
Module 1: Cash Conversion Quality (weight: 23%)

Measures whether reported net income is converting to actual operating cash.
Declining conversion while net income grows = reported profit disconnecting from cash reality.

CCR formula with stabilized denominator (v2.0 fix):
    CCR = OCF / max(|NetIncome|, 0.05 × Revenue)

Using bare NetIncome caused CCR explosion when NI was near zero.
The revenue floor (5% of revenue) provides a size-appropriate minimum denominator.

Scored on: average CCR and 8-quarter trend slope.

Flag trigger: average CCR < 0.6 OR slope decline > 0.05 per quarter

Debug logging: [M1] prefix
"""

import logging
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

FLAG = "LOW CASH CONVERSION"


def run(time_series: dict, quarters_available: int) -> dict:
    """
    Run Module 1: Cash Conversion Quality.
    Requires: net_income, operating_cash_flow, revenue (for denominator floor)
    """
    logger.debug(f"[M1] Running with {quarters_available} quarters")

    net_income = [v for _, v in time_series["net_income"]]
    ocf = [v for _, v in time_series["operating_cash_flow"]]
    revenue = [v for _, v in time_series["revenue"]]

    # All three series are date-aligned — lengths guaranteed equal by edgar_fetcher
    n = len(net_income)

    ccr_values = []
    for i in range(n):
        ni = net_income[i]
        rev = revenue[i]
        # Stabilized denominator: prevents CCR explosion when NI is near zero
        denominator = max(abs(ni), 0.05 * abs(rev)) if rev != 0 else abs(ni)
        if denominator < 1000:
            logger.debug(f"[M1] Q{i}: denominator too small ({denominator}). Skipping quarter.")
            continue
        ccr = ocf[i] / denominator
        ccr_values.append(ccr)
        logger.debug(f"[M1] Q{i}: OCF={ocf[i]:.0f}, NI={ni:.0f}, denom={denominator:.0f}, CCR={ccr:.3f}")

    if len(ccr_values) < 2:
        logger.warning("[M1] Insufficient valid CCR values. Returning neutral score.")
        return _build_result(
            score=50, flag=None, trend="flat",
            plain_english="Insufficient data to assess cash conversion quality.",
            debug={"ccr_values": ccr_values, "avg_ccr": None, "slope": None}
        )

    avg_ccr = float(np.mean(ccr_values))
    slope = _linear_slope(ccr_values)

    logger.debug(f"[M1] avg_ccr={avg_ccr:.3f}, slope={slope:.4f}, n={len(ccr_values)}")

    score = _score(avg_ccr, slope)
    flag = FLAG if (avg_ccr < 0.6 or slope < -0.05) else None
    plain_english = _plain_english(avg_ccr, slope, flag)
    trend = "up" if slope > 0.02 else ("down" if slope < -0.02 else "flat")

    return _build_result(
        score=score, flag=flag, trend=trend, plain_english=plain_english,
        debug={
            "ccr_values": [round(v, 3) for v in ccr_values],
            "avg_ccr": round(avg_ccr, 3),
            "slope": round(slope, 4)
        },
        trend_strength=slope
    )


def _score(avg_ccr: float, slope: float) -> float:
    if avg_ccr >= 1.0 and slope >= 0:
        base = 90 + min(10, (avg_ccr - 1.0) * 20)
    elif avg_ccr >= 0.8 and slope >= -0.02:
        base = 70 + (avg_ccr - 0.8) / 0.2 * 19
    elif avg_ccr >= 0.6:
        base = 40 + (avg_ccr - 0.6) / 0.2 * 29
    else:
        base = max(0.0, avg_ccr / 0.6 * 39)

    slope_penalty = max(0.0, -slope * 100)
    return round(max(0.0, min(100.0, base - slope_penalty)), 1)


def _plain_english(avg_ccr: float, slope: float, flag: Optional[str]) -> str:
    if flag:
        return "Income is not converting to cash at an acceptable rate. Operating cash flow is diverging from reported profit."
    elif avg_ccr >= 1.0:
        return "Cash generation exceeds reported income. Earnings are strongly supported by actual cash flow."
    elif avg_ccr >= 0.8:
        return "Income is converting to cash at a healthy rate. No cash conversion concerns."
    else:
        return "Cash conversion is acceptable but worth monitoring over the coming quarters."


def _linear_slope(values: list) -> float:
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    return float(np.polyfit(x, y, 1)[0]) if len(x) >= 2 else 0.0


def _build_result(score, flag, trend, plain_english, debug, trend_strength=None):
    label = _band_label(score)
    logger.info(f"[M1] Score={score}, Label={label}, Flag={flag}, Trend={trend}")
    return {
        "module_name": "cash_conversion",
        "score": score,
        "label": label,
        "flag": flag,
        "trend": trend,
        "plain_english": plain_english,
        "not_applicable": False,
        "unknown": False,
        "anomaly_triggered": False,
        "debug": debug,
        "trend_strength": trend_strength
    }


def _band_label(score):
    if score >= 75: return "STRONG"
    elif score >= 55: return "ACCEPTABLE"
    elif score >= 35: return "WEAK"
    else: return "POOR"
