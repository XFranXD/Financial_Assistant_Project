"""
module_earnings_timing.py
Module 8: Earnings Timing Risk (post-score modifier — NOT composite)

Measures how close the next earnings report is.
This is NOT a measure of business quality — it is a near-term information risk modifier.
A candidate with earnings in 3 days may have all current financial signals invalidated
by new disclosures within 48 hours.

Data sources (fetched live — not from EDGAR time_series):
    Primary:  Finnhub free tier earnings calendar
    Fallback: Alpha Vantage earnings calendar (25 calls/day limit)

Staleness: earnings dates change. Re-fetch if cached date is older than 24 hours.
Cache behavior: earnings date stored in debug dict. Not persisted between runs
(would require additional cache file — not implemented in v2.3).

UNKNOWN handling: if no future earnings date found within look_ahead_days window,
module returns unknown=True, score=None, trend="flat", weight redistributes.
UNKNOWN is NOT a FAILED condition.

Scoring:
    0–3 days:   10–25  HIGH     EARNINGS IMMINENT
    4–10 days:  40–55  MODERATE
    11–30 days: 65–75  LOW-MODERATE
    31–90 days: 80–95  LOW
    UNKNOWN:    None   flag EARNINGS DATE UNKNOWN

Flag trigger: days_to_earnings <= 3 → EARNINGS IMMINENT

Debug logging: [M7] prefix
"""

import logging
import requests
import os
from datetime import date, datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

FLAG_IMMINENT = "EARNINGS IMMINENT"
FLAG_UNKNOWN  = "EARNINGS DATE UNKNOWN"


def run(
    time_series: dict,
    quarters_available: int,
    ticker: str = "",
    config: dict = None
) -> dict:
    """
    Run Module 8: Earnings Timing Risk.
    time_series and quarters_available are unused — present for interface consistency.
    ticker and config are required for the live API fetch.
    """
    logger.info(f"[M7] Fetching earnings timing for {ticker}")

    et_cfg = (config or {}).get("earnings_timing", {})
    look_ahead = et_cfg.get("look_ahead_days", 90)
    high_risk_days = et_cfg.get("high_risk_days", 3)
    moderate_risk_days = et_cfg.get("moderate_risk_days", 10)
    low_moderate_risk_days = et_cfg.get("low_moderate_risk_days", 30)

    finnhub_key = os.environ.get(et_cfg.get("finnhub_env_var", "FINNHUB_API_KEY"), "")
    av_key      = os.environ.get(et_cfg.get("alphavantage_env_var", "ALPHAVANTAGE_API_KEY"), "")

    days_to_earnings = None
    next_earnings_date = None
    source_used = None

    # Attempt Finnhub first
    if finnhub_key and ticker:
        days_to_earnings, next_earnings_date = _fetch_finnhub(ticker, finnhub_key, look_ahead)
        if days_to_earnings is not None:
            source_used = "Finnhub"

    # Fallback to Alpha Vantage
    if days_to_earnings is None and av_key and ticker:
        days_to_earnings, next_earnings_date = _fetch_alphavantage(ticker, av_key, look_ahead)
        if days_to_earnings is not None:
            source_used = "AlphaVantage"

    if days_to_earnings is None:
        logger.warning(f"[M7] {ticker}: earnings date unavailable from all sources")
        return _build_unknown(ticker)

    logger.info(f"[M7] {ticker}: next earnings in {days_to_earnings} days ({next_earnings_date}) via {source_used}")

    score, risk_label, flag = _score_and_classify(
        days_to_earnings, high_risk_days, moderate_risk_days, low_moderate_risk_days
    )

    # Trend: risk is rising (down) as earnings approach, falling (up) just after
    trend = "down" if days_to_earnings <= moderate_risk_days else "flat"

    plain_english = _plain_english(days_to_earnings, risk_label, flag)

    return {
        "module_name": "earnings_timing",
        "score": score,
        "label": _band_label(score),
        "flag": flag,
        "trend": trend,
        "plain_english": plain_english,
        "not_applicable": False,
        "unknown": False,
        "anomaly_triggered": False,
        "debug": {
            "ticker": ticker,
            "days_to_earnings": days_to_earnings,
            "next_earnings_date": str(next_earnings_date),
            "risk_label": risk_label,
            "source": source_used
        }
    }


def _fetch_finnhub(ticker: str, api_key: str, look_ahead: int) -> tuple[Optional[int], Optional[date]]:
    """Fetch next earnings date from Finnhub earnings calendar."""
    today = date.today()
    end_date = today + timedelta(days=look_ahead)
    url = (
        f"https://finnhub.io/api/v1/calendar/earnings"
        f"?from={today}&to={end_date}&symbol={ticker}&token={api_key}"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        earnings_list = data.get("earningsCalendar", [])
        for item in sorted(earnings_list, key=lambda x: x.get("date", "")):
            try:
                d = datetime.strptime(item["date"], "%Y-%m-%d").date()
                if d >= today:
                    days = (d - today).days
                    return days, d
            except (ValueError, KeyError):
                continue
    except Exception as e:
        logger.warning(f"[M7] Finnhub fetch failed for {ticker}: {e}")
    return None, None


def _fetch_alphavantage(ticker: str, api_key: str, look_ahead: int) -> tuple[Optional[int], Optional[date]]:
    """Fetch next earnings date from Alpha Vantage earnings calendar as fallback."""
    url = (
        f"https://www.alphavantage.co/query"
        f"?function=EARNINGS_CALENDAR&symbol={ticker}&horizon=3month&apikey={api_key}"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        # AV returns CSV for this endpoint
        lines = resp.text.strip().split("\n")
        today = date.today()
        end_date = today + timedelta(days=look_ahead)
        for line in lines[1:]:  # skip header
            parts = line.split(",")
            if len(parts) < 3:
                continue
            try:
                d = datetime.strptime(parts[2].strip(), "%Y-%m-%d").date()
                if today <= d <= end_date:
                    days = (d - today).days
                    return days, d
            except ValueError:
                continue
    except Exception as e:
        logger.warning(f"[M7] AlphaVantage fetch failed for {ticker}: {e}")
    return None, None


def _score_and_classify(
    days: int, high_risk: int, moderate_risk: int, low_moderate_risk: int
) -> tuple[float, str, Optional[str]]:
    if days <= high_risk:
        score = max(10.0, 25.0 - (high_risk - days) * 5)
        return score, "HIGH", FLAG_IMMINENT
    elif days <= moderate_risk:
        score = 40.0 + (days - high_risk) / (moderate_risk - high_risk) * 15
        return round(score, 1), "MODERATE", None
    elif days <= low_moderate_risk:
        score = 65.0 + (days - moderate_risk) / (low_moderate_risk - moderate_risk) * 10
        return round(score, 1), "LOW-MODERATE", None
    else:
        score = min(95.0, 80.0 + (days - low_moderate_risk) / 60 * 15)
        return round(score, 1), "LOW", None


def _build_unknown(ticker: str) -> dict:
    return {
        "module_name": "earnings_timing",
        "score": None,
        "label": "UNKNOWN",
        "flag": FLAG_UNKNOWN,
        "trend": "flat",
        "plain_english": "Earnings date unavailable. Confirm the next report date before acting on this candidate.",
        "not_applicable": False,
        "unknown": True,
        "anomaly_triggered": False,
        "debug": {"ticker": ticker, "source": None}
    }


def _plain_english(days: int, risk_label: str, flag: Optional[str]) -> str:
    if flag == FLAG_IMMINENT:
        return f"Earnings report due in {days} day(s). All current financial signals may change significantly within 48–72 hours."
    elif risk_label == "MODERATE":
        return f"Earnings report due in {days} days. Current analysis reflects pre-announcement data only."
    elif risk_label == "LOW-MODERATE":
        return f"Earnings report due in {days} days. No immediate event risk but approaching within the month."
    else:
        return f"No earnings event in the near term ({days} days out). Financial signals are stable."


def _band_label(score: Optional[float]) -> str:
    if score is None:
        return "UNKNOWN"
    if score >= 75: return "STRONG"
    elif score >= 55: return "ACCEPTABLE"
    elif score >= 35: return "WEAK"
    else: return "POOR"
