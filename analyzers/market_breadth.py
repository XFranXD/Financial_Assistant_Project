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
