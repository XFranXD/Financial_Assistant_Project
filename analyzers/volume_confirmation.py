"""
analyzers/volume_confirmation.py — §10 NEW
Compares today's volume vs 30-day average. Returns ratio and plain label.
"""

import yfinance as yf
from utils.logger import get_logger
from utils.retry import retry_on_failure

log = get_logger('volume_confirmation')


@retry_on_failure(max_attempts=2, delay=2.0)
def compute_volume_confirmation(ticker: str) -> dict:
    """
    Returns volume_ratio and a plain English label.
    volume_ratio = today_volume / 30_day_average_volume

    Interpretation:
      < 0.8  → fewer people trading than usual (weak participation)
      0.8-1.2 → normal trading activity
      > 1.2  → more people trading than usual (strong interest)
      > 2.0  → unusually high activity (major market attention)

    volume_score is normalised 0.0-1.0 for use in signal_agreement.py
    """
    try:
        d = yf.Ticker(ticker).history(period='35d')
        if d is None or len(d) < 31:
            return {'volume_ratio': None, 'volume_score': 0.5, 'label': 'unavailable'}

        today_vol   = float(d['Volume'].iloc[-1])
        avg_30d_vol = float(d['Volume'].iloc[-31:-1].mean())

        if avg_30d_vol == 0:
            return {'volume_ratio': None, 'volume_score': 0.5, 'label': 'unavailable'}

        ratio = today_vol / avg_30d_vol
        score = min(1.0, ratio / 3.0)   # normalise to 0-1 (ratio 3.0 = score 1.0)

        if ratio < 0.8:   label = 'lower activity than usual'
        elif ratio < 1.2: label = 'normal trading activity'
        elif ratio < 2.0: label = 'higher activity than usual'
        else:             label = 'unusually high trading activity'

        log.info(f'{ticker} volume ratio={ratio:.2f} score={score:.2f} label={label}')
        return {
            'volume_ratio': round(ratio, 2),
            'volume_score': round(score, 3),
            'label':        label,
        }
    except Exception as e:
        log.warning(f'volume_confirmation({ticker}): {e}')
        return {'volume_ratio': None, 'volume_score': 0.5, 'label': 'unavailable'}
