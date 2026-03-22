"""
module_long_term_trends.py
Module 4: Long-Term Financial Trends (weight: 16%)

Measures whether the business is genuinely improving, stable, or deteriorating
across four dimensions over the full available history.

The existing five modules measure current state and recent quarters.
This module measures multi-year trajectory — a business can look healthy today
while quietly deteriorating across three years.

All data comes from EDGAR time_series already fetched by edgar_fetcher.py.
No new API calls. Uses the same series as other modules, just the full window.

Four sub-signals:
    1. Revenue trend     — is the business growing?
    2. Margin trend      — is profitability improving or compressing?
    3. Debt trend        — is leverage increasing or decreasing?
    4. FCF trend         — is cash generation trajectory positive?

Each sub-signal uses a slope + recent momentum matrix (v2.3.1):
    Slope +, Recent +  → strong_growth   (score 90)
    Slope +, Recent -  → weakening       (score 65)
    Slope -, Recent +  → recovery        (score 55)
    Slope -, Recent -  → deteriorating   (score 20)

Recent momentum = last 2 quarters vs prior 2 quarters (window from config).

Sub-signal weights (from config): revenue 30%, margin 30%, debt 25%, fcf 15%

Output always states exact quarters analyzed so the human knows the data window.
Runs on available data down to the 6Q floor. Notes if window is shorter than ideal.

Anomaly detection: if any computed ratio exceeds config anomaly caps,
module sets anomaly_triggered=True and reduces its effective weight by 50%.

Flag trigger: 2 or more sub-signals deteriorating → flag MULTI-SIGNAL DETERIORATION

Debug logging: [M4_LT] prefix
"""

import logging
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

FLAG = "MULTI-SIGNAL DETERIORATION"

# 2x2 momentum matrix scores
MOMENTUM_MATRIX = {
    ("positive", "positive"): ("strong_growth",   90.0),
    ("positive", "negative"): ("weakening",        65.0),
    ("negative", "positive"): ("recovery",         55.0),
    ("negative", "negative"): ("deteriorating",    20.0),
    ("flat",     "positive"): ("stable_improving", 70.0),
    ("flat",     "negative"): ("stable_weakening", 50.0),
    ("positive", "flat"):     ("growing_stable",   80.0),
    ("negative", "flat"):     ("declining_stable", 35.0),
    ("flat",     "flat"):     ("stable",           60.0),
}

def _momentum_classify(slope: float, recent_momentum: float,
                        improving_thresh: float, deteriorating_thresh: float) -> tuple[str, float]:
    """Classify using 2x2 matrix: slope direction + recent momentum direction."""
    slope_dir = "positive" if slope >= improving_thresh else (
        "negative" if slope <= deteriorating_thresh else "flat"
    )
    mom_dir = "positive" if recent_momentum >= improving_thresh else (
        "negative" if recent_momentum <= deteriorating_thresh else "flat"
    )
    label, score = MOMENTUM_MATRIX.get((slope_dir, mom_dir), ("stable", 60.0))
    return label, score


def run(time_series: dict, quarters_available: int, config: dict = None) -> dict:
    """
    Run Module 4: Long-Term Financial Trends.
    Requires: revenue, net_income, total_assets (long_term_debt optional but preferred for debt trend)
    config: used to read long_term_trends and anomaly_detection thresholds.
    """
    logger.debug(f"[M4_LT] Running with {quarters_available} quarters")

    lt_cfg    = (config or {}).get("long_term_trends", {})
    anom_cfg  = (config or {}).get("anomaly_detection", {})
    improving_threshold      = lt_cfg.get("improving_slope_threshold", 0.02)
    deteriorating_threshold  = lt_cfg.get("deteriorating_slope_threshold", -0.02)
    momentum_quarters        = lt_cfg.get("recent_momentum_quarters", 2)
    sub_weights = lt_cfg.get("sub_weights", {"revenue": 0.30, "margin": 0.30, "debt": 0.25, "fcf": 0.15})
    margin_cap   = anom_cfg.get("margin_ratio_cap", 2.0)
    growth_cap   = anom_cfg.get("growth_ratio_cap", 5.0)
    anomaly_flag = anom_cfg.get("flag_label", "DATA ANOMALY — VERIFY MANUALLY")

    revenue    = [v for _, v in time_series["revenue"]]
    net_income = [v for _, v in time_series["net_income"]]
    assets     = [v for _, v in time_series["total_assets"]]
    n = len(revenue)
    anomaly_triggered = False
    anomaly_details = []

    window_note = (
        f"Based on {n} quarters (3 years)" if n >= 12
        else f"Based on {n} quarters (limited history — interpret with caution)"
    )
    logger.info(f"[M4_LT] {window_note}")

    def recent_momentum(series: list, q: int) -> float:
        """Compare mean of last q quarters vs prior q quarters as slope proxy."""
        if len(series) < q * 2:
            return 0.0
        recent_mean = float(np.mean(series[-q:]))
        prior_mean  = float(np.mean(series[-q*2:-q]))
        base = abs(prior_mean) if abs(prior_mean) > 1 else 1.0
        return (recent_mean - prior_mean) / base

    # Sub-signal 1: Revenue trend
    rev_slope_pct  = _slope_pct(revenue)
    rev_recent_mom = recent_momentum(revenue, momentum_quarters)
    if abs(rev_slope_pct) > growth_cap:
        anomaly_triggered = True
        anomaly_details.append(f"revenue_slope_pct={rev_slope_pct:.2f} exceeds cap {growth_cap}")
        rev_slope_pct = growth_cap * (1 if rev_slope_pct > 0 else -1)
    rev_label, rev_score = _momentum_classify(rev_slope_pct, rev_recent_mom, improving_threshold, deteriorating_threshold)
    logger.debug(f"[M4_LT] Revenue: slope={rev_slope_pct:.4f}, mom={rev_recent_mom:.4f}, label={rev_label}, score={rev_score}")

    # Sub-signal 2: Margin trend
    margins = []
    for i in range(n):
        if revenue[i] != 0:
            m = net_income[i] / revenue[i]
            if abs(m) > margin_cap:
                anomaly_triggered = True
                anomaly_details.append(f"margin Q{i}={m:.2f} exceeds cap {margin_cap}")
                m = margin_cap * (1 if m > 0 else -1)
            margins.append(m)
    margin_slope  = _linear_slope(margins) if len(margins) >= 2 else 0.0
    margin_recent = recent_momentum(margins, momentum_quarters)
    margin_label, margin_score = _momentum_classify(margin_slope, margin_recent, 0.005, -0.005)
    logger.debug(f"[M4_LT] Margin: slope={margin_slope:.5f}, mom={margin_recent:.5f}, label={margin_label}")

    # Sub-signal 3: Debt trend
    if "long_term_debt" in time_series:
        debt = [v for _, v in time_series["long_term_debt"]]
        n_debt = min(len(debt), n)
        debt_ratios = []
        for i in range(n_debt):
            if assets[i] > 0:
                debt_ratios.append(debt[i] / assets[i])
        debt_slope  = _linear_slope(debt_ratios) if len(debt_ratios) >= 2 else 0.0
        debt_recent = recent_momentum(debt_ratios, momentum_quarters)
        # Rising debt = deteriorating, invert sign
        debt_label, debt_score = _momentum_classify(-debt_slope, -debt_recent, 0.005, -0.005)
    else:
        asset_slope = _slope_pct(assets)
        divergence  = asset_slope - rev_slope_pct
        debt_label, debt_score = _momentum_classify(-divergence, 0.0, 0.01, -0.01)
    logger.debug(f"[M4_LT] Debt: label={debt_label}, score={debt_score}")

    # Sub-signal 4: FCF trend
    if "operating_cash_flow" in time_series and "capex" in time_series:
        ocf   = [v for _, v in time_series["operating_cash_flow"]]
        capex = [abs(v) for _, v in time_series["capex"]]
        n_fcf = min(len(ocf), len(capex), n)
        fcf_margins = []
        for i in range(n_fcf):
            if revenue[i] > 0:
                fcf_margins.append((ocf[i] - capex[i]) / revenue[i])
        fcf_slope  = _linear_slope(fcf_margins) if len(fcf_margins) >= 2 else 0.0
        fcf_recent = recent_momentum(fcf_margins, momentum_quarters)
        fcf_label, fcf_score = _momentum_classify(fcf_slope, fcf_recent, 0.002, -0.002)
    else:
        fcf_label, fcf_score = "stable", 60.0
        logger.warning("[M4_LT] OCF/capex not available — FCF sub-signal defaulting to STABLE")
    logger.debug(f"[M4_LT] FCF: label={fcf_label}, score={fcf_score}")

    # Composite module score (reduce by 50% if anomaly triggered)
    raw_score = round(
        rev_score    * sub_weights["revenue"] +
        margin_score * sub_weights["margin"]  +
        debt_score   * sub_weights["debt"]    +
        fcf_score    * sub_weights["fcf"],
        1
    )
    module_score = round(raw_score * 0.5, 1) if anomaly_triggered else raw_score

    # Count deteriorating signals
    deteriorating_labels = {"deteriorating", "declining_stable", "stable_weakening"}
    improving_labels     = {"strong_growth",  "growing_stable",  "stable_improving", "recovery"}
    deteriorating_count  = sum(1 for lbl in [rev_label, margin_label, debt_label, fcf_label] if lbl in deteriorating_labels)
    improving_count      = sum(1 for lbl in [rev_label, margin_label, debt_label, fcf_label] if lbl in improving_labels)

    flag = anomaly_flag if anomaly_triggered else (FLAG if deteriorating_count >= 2 else None)

    trend = "up" if improving_count > deteriorating_count else (
        "down" if deteriorating_count > improving_count else "flat"
    )

    plain_english = _plain_english(rev_label, margin_label, debt_label, fcf_label, window_note, flag, anomaly_triggered)

    logger.info(f"[M4_LT] Score={module_score}, Flag={flag}, Trend={trend}, anomaly={anomaly_triggered}")

    return {
        "module_name": "long_term_trends",
        "score": module_score,
        "label": _band_label(module_score),
        "flag": flag,
        "trend": trend,
        "plain_english": plain_english,
        "not_applicable": False,
        "unknown": False,
        "anomaly_triggered": anomaly_triggered,
        "trend_strength": rev_slope_pct,
        "debug": {
            "quarters_analyzed": n,
            "window_note": window_note,
            "revenue_label": rev_label,
            "margin_label": margin_label,
            "debt_label": debt_label,
            "fcf_label": fcf_label,
            "deteriorating_count": deteriorating_count,
            "improving_count": improving_count,
            "anomaly_details": anomaly_details,
            "raw_score_before_anomaly": raw_score
        }
    }


def _classify(slope: float, improving_thresh: float, deteriorating_thresh: float) -> str:
    """Simple 3-way classify (kept for backward compat — momentum matrix preferred)."""
    if slope >= improving_thresh:
        return "improving"
    elif slope <= deteriorating_thresh:
        return "deteriorating"
    else:
        return "stable"


def _slope_pct(values: list) -> float:
    """Slope normalized by mean value — comparable across companies of different sizes."""
    if not values or abs(float(np.mean(values))) < 1:
        return 0.0
    slope = _linear_slope(values)
    return slope / abs(float(np.mean(values)))


def _linear_slope(values: list) -> float:
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    return float(np.polyfit(x, y, 1)[0]) if len(x) >= 2 else 0.0


def _plain_english(
    rev: str, margin: str, debt: str, fcf: str,
    window_note: str, flag, anomaly_triggered: bool = False
) -> str:
    if anomaly_triggered:
        return (
            f"{window_note}: Extreme data values detected in one or more metrics. "
            f"Results should be verified manually before acting on this signal."
        )
    deteriorating_labels = {"deteriorating", "declining_stable", "stable_weakening"}
    improving_labels     = {"strong_growth", "growing_stable", "stable_improving", "recovery"}
    if flag == "MULTI-SIGNAL DETERIORATION":
        return (
            f"{window_note}: Multiple business dimensions deteriorating simultaneously. "
            f"Revenue: {rev}, margins: {margin}, debt: {debt}, FCF: {fcf}."
        )
    weakening = [
        name for name, lbl in
        [("revenue", rev), ("margins", margin), ("debt trend", debt), ("FCF", fcf)]
        if lbl in deteriorating_labels
    ]
    strong = [
        name for name, lbl in
        [("revenue", rev), ("margins", margin), ("FCF", fcf)]
        if lbl in improving_labels
    ]
    if weakening:
        warn_str = " and ".join(weakening)
        return f"{window_note}: {warn_str.capitalize()} showing deterioration or weakening trend."
    elif strong:
        pos_str = " and ".join(strong)
        return f"{window_note}: {pos_str.capitalize()} on a positive trajectory. Business quality is improving."
    else:
        return f"{window_note}: All four business dimensions are stable. No significant trend detected."


def _band_label(score: float) -> str:
    if score >= 75: return "STRONG"
    elif score >= 55: return "ACCEPTABLE"
    elif score >= 35: return "WEAK"
    else: return "POOR"
