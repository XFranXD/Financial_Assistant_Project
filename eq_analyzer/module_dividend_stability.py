"""
module_dividend_stability.py
Module 7: Dividend Stability (weight: 5%)

Measures whether the company's dividend policy is financially sustainable.
A dividend cut is one of the clearest signals of financial stress available —
management resists cuts until they have no choice, so an actual cut is highly informative.

NOT APPLICABLE logic:
    If the company has paid zero dividends in the trailing not_applicable_if_zero_quarters
    (default 8) quarters, the module is marked not_applicable=True.
    Output shows NOT APPLICABLE. Weight redistributes. Not a negative signal.

Data sources (fetched live via yfinance — not from EDGAR time_series):
    yfinance: ticker.dividends         — full dividend history with dates and amounts
    yfinance: ticker.info              — payoutRatio, dividendYield, dividendRate
    EDGAR net_income series (from time_series) — used for payout ratio cross-check only

Three sub-signals (for dividend-paying companies only):
    1. Growth stability  (40% of module score) — consistency of dividend maintenance/growth
    2. Payout ratio risk (40% of module score) — financial sustainability of current dividend
    3. Cut history       (20% of module score) — whether cuts have occurred in trailing 3 years

Flag triggers:
    payout_ratio > 0.90          → HIGH PAYOUT RATIO
    any cut in trailing 3 years  → DIVIDEND CUT DETECTED

Debug logging: [M8] prefix
"""

import logging
import yfinance as yf
import numpy as np
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

FLAG_PAYOUT   = "HIGH PAYOUT RATIO"
FLAG_CUT      = "DIVIDEND CUT DETECTED"


def run(
    time_series: dict,
    quarters_available: int,
    ticker: str = "",
    config: dict = None
) -> dict:
    """
    Run Module 7: Dividend Stability.
    time_series['net_income'] used for payout cross-check only.
    ticker required for yfinance fetch.
    """
    logger.info(f"[M8] Fetching dividend data for {ticker}")

    div_cfg = (config or {}).get("dividend_stability", {})
    na_quarters         = div_cfg.get("not_applicable_if_zero_quarters", 8)
    watch_threshold     = div_cfg.get("payout_ratio_watch", 0.60)
    high_risk_threshold = div_cfg.get("payout_ratio_high_risk", 0.90)
    cut_threshold       = div_cfg.get("cut_detection_threshold", 0.10)
    lookback_quarters   = div_cfg.get("lookback_quarters", 12)

    # Fetch dividend history via yfinance
    div_history, payout_ratio, info_available = _fetch_yfinance(ticker)

    if div_history is None or len(div_history) == 0:
        logger.info(f"[M8] {ticker}: no dividend history found — NOT APPLICABLE")
        return _build_not_applicable(ticker)

    # Filter to trailing lookback_quarters (approx 3 years = 12 quarters)
    cutoff = date.today() - timedelta(days=lookback_quarters * 91)
    recent_divs = [
        (d, amt) for d, amt in div_history
        if d >= cutoff and amt > 0
    ]

    if len(recent_divs) < na_quarters // 2:
        logger.info(f"[M8] {ticker}: insufficient recent dividends ({len(recent_divs)}) — NOT APPLICABLE")
        return _build_not_applicable(ticker)

    # Sub-signal 1: Growth stability
    amounts = [amt for _, amt in recent_divs]
    stable_or_growing = sum(
        1 for i in range(1, len(amounts))
        if amounts[i] >= amounts[i - 1] * (1 - cut_threshold)
    )
    growth_stability = stable_or_growing / max(len(amounts) - 1, 1)
    growth_score = round(growth_stability * 100, 1)

    # Sub-signal 2: Payout ratio risk
    if payout_ratio is not None and 0 < payout_ratio <= 5.0:
        pr = payout_ratio  # yfinance already as decimal (0.52 = 52%)
    else:
        # Compute from EDGAR net income if yfinance payout ratio unavailable or implausible
        net_income_series = time_series.get("net_income", [])
        annual_ni = sum(v for _, v in net_income_series[-4:]) if len(net_income_series) >= 4 else None
        annual_div = sum(amt for _, amt in recent_divs[-4:]) * _shares_estimate(ticker) if annual_ni else None
        pr = (annual_div / annual_ni) if (annual_ni and annual_ni > 0 and annual_div) else None

    if pr is not None:
        if pr < watch_threshold:
            payout_score = 90.0
        elif pr < high_risk_threshold:
            payout_score = 90.0 - ((pr - watch_threshold) / (high_risk_threshold - watch_threshold)) * 50
        else:
            payout_score = max(0.0, 40.0 - (pr - high_risk_threshold) * 200)
        payout_score = round(payout_score, 1)
    else:
        payout_score = 60.0  # Neutral if unable to compute
        pr = None

    # Sub-signal 3: Cut history
    cuts = 0
    for i in range(1, len(amounts)):
        if amounts[i] < amounts[i - 1] * (1 - cut_threshold):
            cuts += 1
    if cuts == 0:
        cut_score = 100.0
    elif cuts == 1:
        cut_score = 40.0
    else:
        cut_score = 0.0

    # Composite module score
    module_score = round(
        growth_score * 0.40 +
        payout_score * 0.40 +
        cut_score    * 0.20,
        1
    )

    # Flags
    flags = []
    if pr is not None and pr > high_risk_threshold:
        flags.append(FLAG_PAYOUT)
    if cuts > 0:
        flags.append(FLAG_CUT)
    flag = flags[0] if flags else None  # Report most severe first

    # Trend: rising dividends = "up", cut detected = "down", stable = "flat"
    trend = "down" if cuts > 0 else ("up" if growth_score >= 80 else "flat")

    plain_english = _plain_english(growth_stability, pr, cuts, watch_threshold, high_risk_threshold, flag)

    logger.info(
        f"[M8] {ticker}: Score={module_score}, Flag={flag}, Trend={trend}, "
        f"growth_stability={growth_stability:.2f}, payout={pr}, cuts={cuts}"
    )

    return {
        "module_name": "dividend_stability",
        "score": module_score,
        "label": _band_label(module_score),
        "flag": flag,
        "trend": trend,
        "plain_english": plain_english,
        "not_applicable": False,
        "unknown": False,
        "anomaly_triggered": False,
        "trend_strength": None,
        "debug": {
            "ticker": ticker,
            "recent_dividend_count": len(recent_divs),
            "growth_stability": round(growth_stability, 3),
            "payout_ratio": round(pr, 3) if pr is not None else None,
            "cut_count": cuts,
            "growth_score": growth_score,
            "payout_score": payout_score,
            "cut_score": cut_score
        }
    }


def _fetch_yfinance(ticker: str) -> tuple[Optional[list], Optional[float], bool]:
    """Fetch dividend history and payout ratio from yfinance."""
    try:
        t = yf.Ticker(ticker)
        divs = t.dividends
        info = t.info
        if divs is not None and len(divs) > 0:
            # Convert to list of (date, amount) tuples
            div_list = [(d.date(), float(v)) for d, v in divs.items()]
            payout = info.get("payoutRatio")
            return div_list, payout, True
        return [], None, True
    except Exception as e:
        logger.warning(f"[M8] yfinance fetch failed for {ticker}: {e}")
        return None, None, False


def _shares_estimate(ticker: str) -> float:
    """Get shares outstanding for payout ratio cross-check. Returns 1.0 on failure."""
    try:
        info = yf.Ticker(ticker).info
        return float(info.get("sharesOutstanding", 1.0))
    except Exception:
        return 1.0


def _build_not_applicable(ticker: str) -> dict:
    return {
        "module_name": "dividend_stability",
        "score": None,
        "label": "N/A",
        "flag": None,
        "trend": "flat",
        "plain_english": "This company does not pay dividends. Module skipped with no score impact.",
        "not_applicable": True,
        "unknown": False,
        "anomaly_triggered": False,
        "trend_strength": None,
        "debug": {"ticker": ticker, "reason": "no_dividends"}
    }


def _plain_english(
    growth_stability: float, payout: Optional[float],
    cuts: int, watch_thresh: float, high_thresh: float, flag: Optional[str]
) -> str:
    if flag == FLAG_CUT:
        return f"Dividend cut detected in the trailing 3 years ({cuts} cut(s)). This is a significant financial stress signal."
    elif flag == FLAG_PAYOUT:
        pr_pct = round(payout * 100) if payout else "?"
        return f"Payout ratio of {pr_pct}% is above sustainable levels. Dividend is consuming most of reported earnings."
    elif payout is not None and payout > watch_thresh:
        pr_pct = round(payout * 100)
        return f"Dividend is maintained but payout ratio of {pr_pct}% warrants monitoring."
    elif growth_stability >= 0.90:
        return "Dividend has been maintained or grown consistently. Payout appears financially sustainable."
    else:
        return "Dividend policy shows some variability but no severe signals detected."


def _band_label(score: Optional[float]) -> str:
    if score is None:
        return "N/A"
    if score >= 75: return "STRONG"
    elif score >= 55: return "ACCEPTABLE"
    elif score >= 35: return "WEAK"
    else: return "POOR"
