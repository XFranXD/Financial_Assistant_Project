"""
module_fcf_sustainability.py
Module 5: Free Cash Flow Sustainability (weight: 11%)

Measures whether the business generates more free cash than it spends sustaining operations.
Compressing FCF margin while reporting stable net income is a significant warning sign.

FCF = Operating Cash Flow − |Capital Expenditures|
FCF Margin = FCF / Revenue

Investment phase detection (v2.3.1):
    If FCF < 0 AND capex/revenue > investment_threshold for 2+ consecutive quarters,
    classify as INVESTMENT PHASE rather than deterioration.
    Threshold and required quarters read from config.json fcf_investment_phase block.

Capex sign normalization: abs(capex) always used regardless of filing sign convention.

Flag trigger: FCF margin negative in 3+ of last 6 quarters AND not in investment phase
             → FCF DETERIORATION

Debug logging: [M5] prefix
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)

FLAG = "FCF DETERIORATION"
FLAG_INVESTMENT = "INVESTMENT PHASE — HIGH CAPEX"


def run(time_series: dict, quarters_available: int, config: dict = None) -> dict:
    logger.debug(f"[M5] Running with {quarters_available} quarters")

    inv_cfg  = (config or {}).get("fcf_investment_phase", {})
    anom_cfg = (config or {}).get("anomaly_detection", {})
    capex_rev_threshold   = inv_cfg.get("capex_revenue_threshold", 0.15)
    consec_required       = inv_cfg.get("consecutive_quarters_required", 2)
    growth_cap            = anom_cfg.get("growth_ratio_cap", 5.0)
    anomaly_flag_label    = anom_cfg.get("flag_label", "DATA ANOMALY — VERIFY MANUALLY")

    ocf       = [v for _, v in time_series["operating_cash_flow"]]
    capex_raw = [v for _, v in time_series["capex"]]
    revenue   = [v for _, v in time_series["revenue"]]
    n = len(ocf)

    if n < 4:
        logger.warning("[M5] Need at least 4 quarters.")
        return _build_result(50, None, "flat",
                             "Insufficient data to assess FCF sustainability.", {},
                             anomaly_triggered=False)

    capex = [abs(v) for v in capex_raw]

    fcf_values, fcf_margins, capex_rev_ratios = [], [], []
    anomaly_triggered = False
    for i in range(n):
        fcf = ocf[i] - capex[i]
        fcf_values.append(fcf)
        if revenue[i] > 0:
            margin = fcf / revenue[i]
            if abs(margin) > growth_cap:
                anomaly_triggered = True
                logger.warning(f"[M5] Q{i}: FCF margin {margin:.2f} exceeds anomaly cap {growth_cap}")
                margin = growth_cap * (1 if margin > 0 else -1)
            fcf_margins.append(margin)
            capex_rev_ratios.append(capex[i] / revenue[i])
        else:
            fcf_margins.append(None)
            capex_rev_ratios.append(None)

    valid_margins = [m for m in fcf_margins if m is not None]
    if not valid_margins:
        return _build_result(50, None, "flat",
                             "Insufficient revenue data to compute FCF margins.", {},
                             anomaly_triggered=False)

    current_fcf_margin = valid_margins[-1]
    avg_fcf_margin     = float(np.mean(valid_margins))
    slope              = _linear_slope(valid_margins)

    # Trailing 6Q flag check
    trailing_valid  = [m for m in fcf_margins[-6:] if m is not None]
    negative_count  = sum(1 for m in trailing_valid if m < 0)

    # Investment phase detection: count consecutive recent quarters with high capex AND negative FCF
    investment_phase = False
    consec = 0
    for i in range(n - 1, max(n - 7, -1), -1):
        cr = capex_rev_ratios[i]
        fm = fcf_margins[i]
        if cr is not None and fm is not None and fm < 0 and cr > capex_rev_threshold:
            consec += 1
        else:
            break
    if consec >= consec_required:
        investment_phase = True
        logger.info(f"[M5] Investment phase detected: {consec} consecutive quarters of high capex + negative FCF")

    logger.debug(
        f"[M5] current={current_fcf_margin:.3f}, slope={slope:.5f}, "
        f"neg_last_6q={negative_count}, investment_phase={investment_phase}"
    )

    if anomaly_triggered:
        flag = anomaly_flag_label
    elif investment_phase and negative_count >= 3:
        flag = FLAG_INVESTMENT
    elif negative_count >= 3:
        flag = FLAG
    else:
        flag = None

    score = _score(current_fcf_margin, avg_fcf_margin, slope, investment_phase)
    if anomaly_triggered:
        score = round(score * 0.5, 1)
    trend = "up" if slope > 0.002 else ("down" if slope < -0.002 else "flat")
    plain_english = _plain_english(current_fcf_margin, slope, negative_count,
                                   flag, investment_phase, anomaly_triggered)

    return _build_result(score, flag, trend, plain_english, {
        "fcf_margins": [round(m, 4) if m is not None else None for m in fcf_margins],
        "current_fcf_margin": round(current_fcf_margin, 4),
        "avg_fcf_margin": round(avg_fcf_margin, 4),
        "slope": round(slope, 5),
        "negative_last_6q": negative_count,
        "investment_phase": investment_phase,
        "consecutive_high_capex_negative_fcf": consec
    }, anomaly_triggered=anomaly_triggered, trend_strength=slope)


def _score(current: float, avg: float, slope: float, investment_phase: bool) -> float:
    # Investment phase: score based on capex productivity assumption, not raw FCF
    if investment_phase and current < 0:
        base = 55.0  # neutral — negative FCF explained by known investment
    elif current > 0.10 and slope >= 0:
        base = 90.0
    elif current > 0.10:
        base = 80.0
    elif current > 0.05:
        base = 65 + (current - 0.05) / 0.05 * 15
    elif current > 0:
        base = 40 + current / 0.05 * 25
    else:
        base = max(0.0, 40 + current * 200)
    slope_penalty = max(0.0, -slope * 500) if not investment_phase else 0.0
    return round(max(0.0, min(100.0, base - slope_penalty)), 1)


def _plain_english(current: float, slope: float, negative_count: int,
                   flag, investment_phase: bool, anomaly_triggered: bool) -> str:
    if anomaly_triggered:
        return "Extreme FCF margin values detected. Data should be verified manually."
    if investment_phase and flag == FLAG_INVESTMENT:
        return (
            f"Negative FCF in {negative_count} of the last 6 quarters is likely driven by "
            f"sustained high capital investment. Monitor when investment cycle ends."
        )
    if flag == FLAG:
        return (
            f"Free cash flow was negative in {negative_count} of the last 6 quarters. "
            f"The business is consuming more cash than it generates after sustaining operations."
        )
    if current > 0.10 and slope >= 0:
        return "Strong and stable free cash flow margin. The business is self-funding with room to spare."
    if current > 0.05:
        return "Positive free cash flow with adequate margin. No sustainability concerns at current levels."
    if current > 0:
        return "FCF margin is positive but thin. Any operational headwind could push it negative."
    return "FCF margin is currently negative. The business is spending more on operations than it generates."


def _linear_slope(values: list) -> float:
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    return float(np.polyfit(x, y, 1)[0]) if len(x) >= 2 else 0.0


def _build_result(score, flag, trend, plain_english, debug, anomaly_triggered=False, trend_strength=None):
    label = _band_label(score)
    logger.info(f"[M5] Score={score}, Label={label}, Flag={flag}, Trend={trend}")
    return {
        "module_name": "fcf_sustainability", "score": score, "label": label,
        "flag": flag, "trend": trend, "plain_english": plain_english,
        "not_applicable": False, "unknown": False,
        "anomaly_triggered": anomaly_triggered, "debug": debug,
        "trend_strength": trend_strength
    }


def _band_label(score):
    if score >= 75: return "STRONG"
    elif score >= 55: return "ACCEPTABLE"
    elif score >= 35: return "WEAK"
    else: return "POOR"
