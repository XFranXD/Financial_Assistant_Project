"""
module_accruals.py
Module 2: Accruals Quality (weight: 19%)

Measures how much of reported earnings consists of non-cash accounting entries.
High accruals relative to total assets is one of the strongest empirical predictors
of future earnings deterioration (Sloan 1996, Journal of Accounting Research).

Correct Sloan formula:
    Total Accruals = Net Income − Operating Cash Flow
    BSAR = Total Accruals / Average Total Assets

Note: Investing cash flow is NOT included. It was in v1.0 by mistake.
Including investing CF would penalize companies for normal capex and acquisitions.
The correct formula uses only NI minus OCF.

Scored on: trailing 4-quarter average BSAR.

Flag trigger: trailing 4Q avg BSAR > 0.08

Debug logging: [M2] prefix
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)

FLAG = "HIGH ACCRUALS"


def run(time_series: dict, quarters_available: int) -> dict:
    logger.debug(f"[M2] Running with {quarters_available} quarters")

    net_income = [v for _, v in time_series["net_income"]]
    ocf = [v for _, v in time_series["operating_cash_flow"]]
    assets = [v for _, v in time_series["total_assets"]]

    n = len(net_income)  # All series date-aligned, lengths equal

    if n < 2:
        logger.warning("[M2] Insufficient data.")
        return _build_result(50, None, "flat", "Insufficient data to assess accruals quality.", {}, trend_strength=None)

    bsar_values = []
    for i in range(1, n):
        avg_assets = (assets[i] + assets[i - 1]) / 2
        if avg_assets <= 0:
            logger.debug(f"[M2] Q{i}: avg_assets={avg_assets} — skipping")
            continue
        accruals = net_income[i] - ocf[i]
        bsar = accruals / avg_assets
        bsar_values.append(bsar)
        logger.debug(f"[M2] Q{i}: accruals={accruals:.0f}, avg_assets={avg_assets:.0f}, BSAR={bsar:.4f}")

    if not bsar_values:
        return _build_result(50, None, "flat", "Insufficient data to assess accruals quality.", {}, trend_strength=None)

    trailing = bsar_values[-4:]
    avg_bsar = float(np.mean(trailing))
    all_avg = float(np.mean(bsar_values))

    # Trend: falling BSAR = improving quality = "up", rising BSAR = "down"
    bsar_slope = _linear_slope(bsar_values) if len(bsar_values) >= 2 else 0.0
    trend = "up" if bsar_slope < -0.001 else ("down" if bsar_slope > 0.001 else "flat")

    logger.debug(f"[M2] trailing_4Q_avg={avg_bsar:.4f}, all_time_avg={all_avg:.4f}, bsar_slope={bsar_slope:.5f}")

    score = _score(avg_bsar)
    flag = FLAG if avg_bsar > 0.08 else None
    plain_english = _plain_english(avg_bsar, flag)

    return _build_result(score, flag, trend, plain_english, {
        "bsar_values": [round(v, 4) for v in bsar_values],
        "trailing_4q_avg": round(avg_bsar, 4),
        "all_time_avg": round(all_avg, 4),
        "bsar_slope": round(bsar_slope, 5)
    }, trend_strength=bsar_slope)


def _score(avg_bsar: float) -> float:
    if avg_bsar < 0.02:
        base = 85 + min(15, (0.02 - avg_bsar) * 500)
    elif avg_bsar < 0.05:
        base = 65 + (0.05 - avg_bsar) / 0.03 * 20
    elif avg_bsar < 0.10:
        base = 35 + (0.10 - avg_bsar) / 0.05 * 30
    else:
        base = max(0.0, 35 - (avg_bsar - 0.10) * 200)
    return round(max(0.0, min(100.0, base)), 1)


def _plain_english(avg_bsar: float, flag) -> str:
    if flag:
        return "A large portion of reported earnings is non-cash accounting entries. Reported profit may overstate economic reality."
    elif avg_bsar < 0.02:
        return "Very low non-cash entries. Reported profit is strongly backed by real cash transactions."
    elif avg_bsar < 0.05:
        return "Low accruals. Earnings quality is healthy with minimal non-cash distortion."
    else:
        return "Moderate non-cash entries present. Worth monitoring for further increase."


def _build_result(score, flag, trend, plain_english, debug, trend_strength=None):
    label = _band_label(score)
    logger.info(f"[M2] Score={score}, Label={label}, Flag={flag}, Trend={trend}")
    return {"module_name": "accruals", "score": score, "label": label,
            "flag": flag, "trend": trend, "plain_english": plain_english,
            "not_applicable": False, "unknown": False, "anomaly_triggered": False,
            "debug": debug, "trend_strength": trend_strength}


def _linear_slope(values: list) -> float:
    import numpy as np
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    return float(np.polyfit(x, y, 1)[0]) if len(x) >= 2 else 0.0


def _band_label(score):
    if score >= 75: return "STRONG"
    elif score >= 55: return "ACCEPTABLE"
    elif score >= 35: return "WEAK"
    else: return "POOR"
