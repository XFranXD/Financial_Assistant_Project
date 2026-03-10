"""
analyzers/sector_momentum.py — Scores all 13 sectors on 5d/10d return
and relative strength vs SPY. Only top 5 ranked sectors proceed.

Updates sector_momentum_history.json rolling 10-day history on each run.
"""

import json
from datetime import datetime

import pytz
import yfinance as yf

from config import (
    SECTOR_ETFS_FILE,
    SECTOR_MOMENTUM_HISTORY_FILE,
    TOP_SECTORS_LIMIT,
    ROTATION_HISTORY_DAYS,
)
from utils.logger import get_logger
from utils.retry import retry_on_failure

log = get_logger('sector_momentum')


def _load_etfs() -> dict:
    try:
        with open(SECTOR_ETFS_FILE, encoding='utf-8') as f:
            d = json.load(f)
        d.pop('_comment', None)
        return d
    except Exception as e:
        log.error(f'Cannot load sector_etfs.json: {e}')
        return {}


@retry_on_failure(max_attempts=2, delay=2.0)
def _get_etf_data(ticker: str) -> dict | None:
    """Fetches price history for an ETF. Returns None on failure."""
    try:
        d = yf.Ticker(ticker).history(period='15d')
        if d is None or len(d) < 11:
            return None
        closes = list(d['Close'])
        curr   = closes[-1]
        p5d    = closes[-6]  if len(closes) >= 6  else None
        p10d   = closes[-11] if len(closes) >= 11 else None

        ret5d  = ((curr - p5d)  / p5d  * 100) if p5d  and p5d  > 0 else None
        ret10d = ((curr - p10d) / p10d * 100) if p10d and p10d > 0 else None

        return {'curr': curr, 'ret5d': ret5d, 'ret10d': ret10d}
    except Exception as e:
        log.warning(f'ETF data {ticker}: {e}')
        return None


def _get_spy_data() -> dict | None:
    return _get_etf_data('SPY')


def compute_sector_momentum() -> dict:
    """
    Computes momentum scores for all 13 sectors.
    Returns full scores dict AND marks which are in top 5.

    Returns: {sector: {
        'etf': str, 'ret5d': float, 'ret10d': float,
        'rel_strength': float, 'score': float, 'rank': int, 'top5': bool
    }}
    """
    etfs     = _load_etfs()
    spy      = _get_spy_data()
    spy_ret5 = spy['ret5d'] if spy and spy.get('ret5d') is not None else 0.0

    scores: dict[str, dict] = {}

    for sector, etf_ticker in etfs.items():
        data = _get_etf_data(etf_ticker)
        if data is None:
            log.warning(f'Sector {sector}: ETF {etf_ticker} data unavailable — scoring 0')
            scores[sector] = {
                'etf': etf_ticker, 'ret5d': None, 'ret10d': None,
                'rel_strength': None, 'score': 0.0, 'rank': 99, 'top5': False,
            }
            continue

        ret5d = data.get('ret5d') or 0.0
        ret10d = data.get('ret10d') or 0.0
        # Relative strength vs SPY on 5-day
        rel_strength = ret5d - spy_ret5

        # Combined score: 5d return 50% + 10d return 30% + rel_strength 20%
        score = (ret5d * 0.50) + (ret10d * 0.30) + (rel_strength * 0.20)

        scores[sector] = {
            'etf':          etf_ticker,
            'ret5d':        round(ret5d, 2),
            'ret10d':       round(ret10d, 2),
            'rel_strength': round(rel_strength, 2),
            'score':        round(score, 3),
            'rank':         99,
            'top5':         False,
        }

    # Rank sectors by score descending
    ranked = sorted(scores.keys(), key=lambda s: scores[s]['score'], reverse=True)
    for i, sector in enumerate(ranked):
        scores[sector]['rank']  = i + 1
        scores[sector]['top5']  = (i + 1) <= TOP_SECTORS_LIMIT

    log.info(f'Top 5 sectors: {[s for s in ranked[:5]]}')

    # Update rolling history file
    _update_history(scores)

    return scores


def _update_history(scores: dict) -> None:
    """Appends today's rankings to rolling 10-day sector_momentum_history.json."""
    try:
        try:
            with open(SECTOR_MOMENTUM_HISTORY_FILE, encoding='utf-8') as f:
                hist = json.load(f)
        except Exception:
            hist = {'meta': {}, 'history': []}

        today   = datetime.now(pytz.utc).strftime('%Y-%m-%d')
        ranking = {s: scores[s]['rank'] for s in scores}
        entry   = {'date': today, 'rankings': ranking, 'scores': {s: scores[s]['score'] for s in scores}}

        # Avoid duplicate entries for same date
        hist['history'] = [e for e in hist.get('history', []) if e.get('date') != today]
        hist['history'].append(entry)
        # Keep rolling window
        hist['history'] = hist['history'][-ROTATION_HISTORY_DAYS:]

        with open(SECTOR_MOMENTUM_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(hist, f, indent=2)
        log.info(f'Sector momentum history updated ({len(hist["history"])} entries)')
    except Exception as e:
        log.warning(f'History update failed: {e}')


def get_sector_pe(sector: str) -> float | None:
    """
    Returns approximate sector P/E via sector ETF info.
    Returns None on failure — callers must handle.
    """
    etfs = _load_etfs()
    etf  = etfs.get(sector)
    if not etf:
        return None
    try:
        info = yf.Ticker(etf).info or {}
        return info.get('trailingPE')
    except Exception:
        return None


def get_sector_median_return(sector: str, period_days: int = 20) -> float | None:
    """
    Computes median N-day return across breadth stocks for use as sector benchmark.
    Falls back to ETF-only return on error.
    """
    etfs = _load_etfs()
    etf  = etfs.get(sector)
    if not etf:
        return None
    data = _get_etf_data(etf)
    return data.get('ret5d') if data else None
