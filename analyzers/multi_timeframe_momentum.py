"""
analyzers/multi_timeframe_momentum.py — §12 NEW
Combines 1m/3m/6m returns with weighted formula. Steady multi-timeframe
trends are more convincing than single-timeframe spikes.

Formula: momentum_score = (return_3m * 0.5) + (return_6m * 0.3) + (return_1m * 0.2)
"""

import yfinance as yf
from utils.logger import get_logger
from utils.retry import retry_on_failure

log = get_logger('multi_timeframe_momentum')


@retry_on_failure(max_attempts=2, delay=2.0)
def compute_mtf_momentum(ticker: str) -> dict:
    """
    Returns combined_momentum_score normalised 0.0-1.0.
    If a timeframe is unavailable, weight is redistributed.
    """
    try:
        d = yf.Ticker(ticker).history(period='7mo')
        if d is None or len(d) < 21:
            return {'mtf_score': 0.5, 'label': 'unavailable', 'r1m': None, 'r3m': None, 'r6m': None}

        closes = list(d['Close'])
        curr   = closes[-1]

        def ret(n):
            if len(closes) < n + 1: return None
            p = closes[-(n+1)]
            return ((curr - p) / p) * 100 if p > 0 else None

        r1m = ret(21)    # ~1 month trading days
        r3m = ret(63)    # ~3 months
        r6m = ret(126)   # ~6 months

        available    = [(r3m, 0.5), (r6m, 0.3), (r1m, 0.2)]
        valid        = [(r, w) for r, w in available if r is not None]
        if not valid:
            return {'mtf_score': 0.5, 'label': 'unavailable', 'r1m': None, 'r3m': None, 'r6m': None}

        total_weight  = sum(w for _, w in valid)
        weighted_sum  = sum(r * (w / total_weight) for r, w in valid)
        score         = max(0.0, min(1.0, (weighted_sum + 30) / 60))  # -30%..+30% → 0..1

        if weighted_sum > 15:   label = 'strong upward trend across all timeframes'
        elif weighted_sum > 5:  label = 'positive trend building over time'
        elif weighted_sum > 0:  label = 'mildly positive — early stage'
        elif weighted_sum > -5: label = 'flat — no clear direction'
        else:                   label = 'declining across multiple timeframes'

        log.info(f'{ticker} MTF 1m={r1m} 3m={r3m} 6m={r6m} score={score:.2f}')
        return {
            'mtf_score':  round(score, 3),
            'raw_score':  round(weighted_sum, 2),
            'r1m':        round(r1m, 2) if r1m is not None else None,
            'r3m':        round(r3m, 2) if r3m is not None else None,
            'r6m':        round(r6m, 2) if r6m is not None else None,
            'label':      label,
        }
    except Exception as e:
        log.warning(f'mtf_momentum({ticker}): {e}')
        return {'mtf_score': 0.5, 'label': 'unavailable', 'r1m': None, 'r3m': None, 'r6m': None}
