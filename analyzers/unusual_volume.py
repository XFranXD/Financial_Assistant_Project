"""
analyzers/unusual_volume.py — §19 NEW
Detects abnormal trading activity. Reuses volume_ratio from volume_confirmation.
Do NOT re-fetch yfinance data here.

Thresholds:
  ratio > 2.0 → strong attention
  ratio > 3.0 → very unusual
  ratio > 5.0 → extreme
"""

from utils.logger import get_logger

log = get_logger('unusual_volume')

THRESHOLDS = [
    (5.0, 'extreme activity — investigate immediately'),
    (3.0, 'very unusual trading volume'),
    (2.0, 'significantly more active than normal'),
]


def detect_unusual_volume(ticker: str, volume_ratio: float | None) -> dict:
    """
    volume_ratio: output from volume_confirmation.compute_volume_confirmation()
    Reuses volume data — do NOT re-fetch yfinance data here.
    Returns flag dict. unusual_flag=True boosts ranking in zscore_ranker.py.
    """
    if volume_ratio is None:
        return {'unusual_flag': False, 'label': 'volume data unavailable', 'ratio': None}

    for threshold, label in THRESHOLDS:
        if volume_ratio >= threshold:
            log.info(f'{ticker} UNUSUAL VOLUME: ratio={volume_ratio:.1f}x — {label}')
            return {
                'unusual_flag': True,
                'label':        label,
                'ratio':        volume_ratio,
                'severity':     label.split(' ')[0],
            }

    return {
        'unusual_flag': False,
        'label':        'normal volume range',
        'ratio':        volume_ratio,
        'severity':     None,
    }
