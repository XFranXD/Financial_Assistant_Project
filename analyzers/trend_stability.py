"""
analyzers/trend_stability.py — §16 NEW
Measures smoothness of price trend vs MA50 over 50 days.
Lower average deviation = more stable (higher score).

Formula: avg_deviation = mean(|price - MA50| / MA50) over last 50 days
Score is INVERTED: lower deviation = higher score.
"""

import yfinance as yf
from utils.logger import get_logger
from utils.retry import retry_on_failure

log = get_logger('trend_stability')


@retry_on_failure(max_attempts=2, delay=2.0)
def compute_trend_stability(ticker: str) -> dict:
    """
    Returns trend_stability_score normalised 0.0-1.0 where 1.0 = very stable.
    NOTE: trend_stability_score is computed for report display.
    It is not currently used in opportunity or risk scoring.
    """
    try:
        d = yf.Ticker(ticker).history(period='3mo')
        if d is None or len(d) < 50:
            return {'stability_score': 0.5, 'label': 'unavailable', 'raw_deviation': None}

        closes     = list(d['Close'])
        deviations = []
        for i in range(len(closes) - 50, len(closes)):
            window = closes[i-49:i+1]
            ma50   = sum(window) / 50
            if ma50 > 0:
                deviations.append(abs(closes[i] - ma50) / ma50)

        if not deviations:
            return {'stability_score': 0.5, 'label': 'unavailable', 'raw_deviation': None}

        avg_deviation = sum(deviations) / len(deviations)
        score         = max(0.0, min(1.0, 1.0 - (avg_deviation / 0.10)))  # invert: 0%=1.0, 10%+=0.0

        if score > 0.80:   label = 'very smooth and stable trend'
        elif score > 0.60: label = 'reasonably stable trend'
        elif score > 0.40: label = 'some volatility in the trend'
        else:              label = 'choppy and unstable — treat with caution'

        log.info(f'{ticker} trend stability: dev={avg_deviation:.4f} score={score:.2f}')
        return {
            'stability_score': round(score, 3),
            'raw_deviation':   round(avg_deviation, 4),
            'label':           label,
        }
    except Exception as e:
        log.warning(f'trend_stability({ticker}): {e}')
        return {'stability_score': 0.5, 'label': 'unavailable', 'raw_deviation': None}
