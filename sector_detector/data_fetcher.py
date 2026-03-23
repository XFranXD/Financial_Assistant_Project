"""
data_fetcher.py — System 3 Sector Rotation Detector
Fetches ETF and SPY data from yfinance.
Never assigns scores or confidence tiers; only sets availability flags.
"""

import yfinance as yf
import pandas as pd


def fetch_etf_data(etf_ticker: str) -> dict:
    """
    Fetches full history (Fetch A) and timeframe slices (Fetch B) for a sector ETF.
    Returns a structured dict with availability flags set.
    Never passes NaN values downstream.
    """
    result = {
        "full_history": {
            "close": pd.Series(dtype=float),
            "volume": pd.Series(dtype=float),
            "trading_days": 0,
            "ma_available": False,
            "rsi_available": False,
            "slope_available": False,
            "volume_sufficient": False,
        },
        "timeframes": {
            "1M": {"close": pd.Series(dtype=float), "volume": pd.Series(dtype=float),
                   "trading_days": 0, "available": False,
                   "spy_close": pd.Series(dtype=float), "spy_available": False},
            "3M": {"close": pd.Series(dtype=float), "volume": pd.Series(dtype=float),
                   "trading_days": 0, "available": False,
                   "spy_close": pd.Series(dtype=float), "spy_available": False},
            "6M": {"close": pd.Series(dtype=float), "volume": pd.Series(dtype=float),
                   "trading_days": 0, "available": False,
                   "spy_close": pd.Series(dtype=float), "spy_available": False},
        },
    }

    # ── Fetch A — Full History (250 trading days) ──────────────────────────────
    try:
        raw_df = yf.download(
            etf_ticker,
            period="1y",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        # Flatten MultiIndex columns if present (yfinance >= 0.2.40 may add ticker level)
        if isinstance(raw_df.columns, pd.MultiIndex):
            raw_df.columns = raw_df.columns.get_level_values(0)

        if raw_df.empty:
            # SKIP — no data at all
            return result

        # Capture raw volume before dropna to evaluate volume_sufficient
        raw_volume = raw_df["Volume"] if "Volume" in raw_df.columns else pd.Series(dtype=float)
        volume_sufficient = bool(not raw_volume.isnull().any())

        # Apply dropna immediately
        df = raw_df.dropna()

        trading_days = len(df)

        if trading_days == 0:
            # SKIP: return with all defaults (trading_days = 0)
            return result

        result["full_history"]["close"] = df["Close"]
        result["full_history"]["volume"] = df["Volume"]
        result["full_history"]["trading_days"] = trading_days
        result["full_history"]["volume_sufficient"] = volume_sufficient
        result["full_history"]["ma_available"] = trading_days >= 200
        result["full_history"]["rsi_available"] = trading_days >= 14
        result["full_history"]["slope_available"] = trading_days >= 20

    except Exception:
        # On any fetch error leave defaults (trading_days = 0) → SKIP
        return result

    # ── Fetch B — Timeframe Slices ─────────────────────────────────────────────
    timeframe_config = {
        "1M": {"period": "1mo", "min_days": 20},
        "3M": {"period": "3mo", "min_days": 60},
        "6M": {"period": "6mo", "min_days": 120},
    }

    for tf, cfg in timeframe_config.items():
        try:
            tf_raw = yf.download(
                etf_ticker,
                period=cfg["period"],
                interval="1d",
                auto_adjust=True,
                progress=False,
            )
            if isinstance(tf_raw.columns, pd.MultiIndex):
                tf_raw.columns = tf_raw.columns.get_level_values(0)

            tf_df = tf_raw.dropna()
            tf_days = len(tf_df)

            result["timeframes"][tf]["trading_days"] = tf_days

            if tf_days >= cfg["min_days"]:
                result["timeframes"][tf]["available"] = True
                result["timeframes"][tf]["close"] = tf_df["Close"]
                result["timeframes"][tf]["volume"] = tf_df["Volume"] if "Volume" in tf_df.columns else pd.Series(dtype=float)
            else:
                result["timeframes"][tf]["available"] = False

        except Exception:
            result["timeframes"][tf]["available"] = False

        # Fetch SPY for the same timeframe
        try:
            spy_raw = yf.download(
                "SPY",
                period=cfg["period"],
                interval="1d",
                auto_adjust=True,
                progress=False,
            )
            if isinstance(spy_raw.columns, pd.MultiIndex):
                spy_raw.columns = spy_raw.columns.get_level_values(0)

            spy_df = spy_raw.dropna()
            spy_days = len(spy_df)

            if spy_days >= cfg["min_days"]:
                result["timeframes"][tf]["spy_available"] = True
                result["timeframes"][tf]["spy_close"] = spy_df["Close"]
            else:
                result["timeframes"][tf]["spy_available"] = False

        except Exception:
            result["timeframes"][tf]["spy_available"] = False

    return result
