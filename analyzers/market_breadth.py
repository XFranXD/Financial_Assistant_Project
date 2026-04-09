"""
analyzers/market_breadth.py — Daily advance/decline breadth across sector_breadth_stocks.
Score > 0.6 = strong, 0.4-0.6 = neutral, < 0.4 = weak.
Result used as opportunity score multiplier.
"""

import json
import yfinance as yf
from utils.logger import get_logger
from config import SECTOR_BREADTH_STOCKS_FILE

log = get_logger('market_breadth')


def _load_breadth_stocks() -> dict:
    try:
        with open(SECTOR_BREADTH_STOCKS_FILE, encoding='utf-8') as f:
            d = json.load(f)
        d.pop('_comment', None)
        return d
    except Exception as e:
        log.error(f'Cannot load sector_breadth_stocks.json: {e}')
        return {}


def _is_advancing(ticker: str) -> bool | None:
    """Returns True if today's close > yesterday's close. None on data error."""
    try:
        d = yf.Ticker(ticker).history(period='2d')
        if d is None or len(d) < 2:
            return None
        return float(d['Close'].iloc[-1]) > float(d['Close'].iloc[-2])
    except Exception as e:
        log.warning(f'Breadth check {ticker}: {e}')
        return None


def compute_market_breadth() -> dict:
    """
    Computes advance/decline ratio across all breadth stocks.
    Returns breadth dict with score, label, and opp_multiplier.
    """
    breadth_stocks = _load_breadth_stocks()
    all_tickers    = [t for tickers in breadth_stocks.values() for t in tickers]

    advancing = 0
    checked   = 0

    for ticker in all_tickers:
        result = _is_advancing(ticker)
        if result is None:
            continue
        checked   += 1
        if result:
            advancing += 1

    if checked == 0:
        log.warning('Market breadth: no data available — returning neutral')
        return {
            'breadth_score':   0.5,
            'advancing':       0,
            'declining':       0,
            'total':           0,
            'label':           'unavailable',
            'opp_multiplier':  1.0,
        }

    score = advancing / checked

    if score > 0.6:
        label = 'strong breadth — most stocks rising'
        opp_mult = 1.15
    elif score >= 0.4:
        label = 'neutral breadth — mixed market movement'
        opp_mult = 1.0
    else:
        label = 'weak breadth — most stocks declining'
        opp_mult = 0.85

    log.info(f'Market breadth: {advancing}/{checked} advancing ({score:.2f}) — {label}')
    return {
        'breadth_score':  round(score, 3),
        'advancing':      advancing,
        'declining':      checked - advancing,
        'total':          checked,
        'label':          label,
        'opp_multiplier': opp_mult,
    }


def compute_breadth_200d() -> dict:
    """
    Computes the percentage of basket stocks currently trading above their
    200-day simple moving average.

    Used by the Market Regime Classifier (2A). Independent of
    compute_market_breadth() which measures advance/decline.

    Returns:
        {
            'breadth_pct':  float | None  — 0.0 to 100.0 (e.g. 62.5 = 62.5% above)
            'above_200d':   int           — count of tickers above 200d SMA
            'checked_200d': int           — count of tickers with sufficient data
        }
    On any exception or zero data: returns safe default. Never raises.
    """
    _default = {'breadth_pct': None, 'above_200d': 0, 'checked_200d': 0}

    try:
        breadth_stocks = _load_breadth_stocks()
        if not breadth_stocks:
            log.warning('[B200] Basket empty — returning default')
            return _default

        # Flatten all tickers, deduplicate preserving order
        all_tickers = []
        seen        = set()
        for tickers in breadth_stocks.values():
            for t in tickers:
                if t not in seen:
                    all_tickers.append(t)
                    seen.add(t)

        if not all_tickers:
            return _default

        above_count   = 0
        checked_count = 0

        # ── Batch download ────────────────────────────────────────────────
        # Single yfinance call for all tickers. Fall back to per-ticker on error.
        try:
            import pandas as pd
            batch = yf.download(
                tickers      = all_tickers,
                period       = '1y',
                auto_adjust  = True,
                progress     = False,
                group_by     = 'ticker',
            )

            for ticker in all_tickers:
                try:
                    # Multi-ticker download returns MultiIndex columns
                    if isinstance(batch.columns, pd.MultiIndex):
                        if ticker not in batch.columns.get_level_values(0):
                            continue
                        closes = batch[ticker]['Close'].dropna()
                    else:
                        # Single-ticker fallback (only one ticker in list)
                        closes = batch['Close'].dropna()

                    if len(closes) < 200:
                        continue

                    current_price = float(closes.iloc[-1])
                    sma_200       = float(closes.tail(200).mean())
                    checked_count += 1
                    if current_price > sma_200:
                        above_count += 1

                except Exception as _ticker_err:
                    log.debug(f'[B200] {ticker}: skip — {_ticker_err}')
                    continue

        except Exception as _batch_err:
            log.warning(f'[B200] Batch download failed, falling back to per-ticker: {_batch_err}')
            # Per-ticker fallback
            for ticker in all_tickers:
                try:
                    data = yf.Ticker(ticker).history(period='1y')
                    if data is None or len(data) < 200:
                        continue
                    current_price = float(data['Close'].iloc[-1])
                    sma_200       = float(data['Close'].tail(200).mean())
                    checked_count += 1
                    if current_price > sma_200:
                        above_count += 1
                except Exception as _t_err:
                    log.debug(f'[B200] {ticker}: per-ticker error — {_t_err}')
                    continue

        if checked_count == 0:
            log.warning('[B200] No tickers had sufficient data — returning default')
            return _default

        breadth_pct = round((above_count / checked_count) * 100, 1)
        log.info(f'[B200] {above_count}/{checked_count} above 200d SMA = {breadth_pct}%')

        return {
            'breadth_pct':  breadth_pct,
            'above_200d':   above_count,
            'checked_200d': checked_count,
        }

    except Exception as e:
        log.warning(f'[B200] compute_breadth_200d failed: {e}')
        return _default
