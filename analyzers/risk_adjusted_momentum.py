"""
analyzers/risk_adjusted_momentum.py — §11 NEW
Return divided by volatility over 3 months. Rewards steady trends.

Formula: risk_adjusted_momentum = return_3m / volatility_3m
"""

import statistics
import yfinance as yf
from utils.logger import get_logger
from utils.retry import retry_on_failure

log = get_logger('risk_adjusted_momentum')


@retry_on_failure(max_attempts=2, delay=2.0)
def compute_risk_adjusted_momentum(ticker: str) -> dict:
    """
    Output normalised 0.0-1.0 for signal_agreement.py
    Score of 0.5 = neutral / data unavailable
    """
    try:
        d = yf.Ticker(ticker).history(period='4mo')
        if d is None or len(d) < 63:
            return {'ram_score': 0.5, 'raw_value': None, 'label': 'unavailable'}

        closes      = list(d['Close'])
        price_now   = closes[-1]
        price_63d   = closes[-63]
        return_3m   = ((price_now - price_63d) / price_63d) * 100 if price_63d > 0 else 0

        daily_returns = [
            ((closes[i] - closes[i-1]) / closes[i-1]) * 100
            for i in range(1, len(closes))
        ]
        volatility_3m = statistics.stdev(daily_returns[-63:]) if len(daily_returns) >= 63 else None

        if not volatility_3m or volatility_3m == 0:
            return {'ram_score': 0.5, 'raw_value': None, 'label': 'unavailable'}

        raw   = return_3m / volatility_3m
        score = max(0.0, min(1.0, (raw + 10) / 20))   # normalise: raw -10..+10 → 0..1

        if raw > 3:    label = 'very stable upward trend'
        elif raw > 1:  label = 'steady upward trend'
        elif raw > 0:  label = 'mild positive trend'
        elif raw > -1: label = 'flat or slightly declining'
        else:          label = 'declining with instability'

        log.info(f'{ticker} RAM raw={raw:.2f} score={score:.2f}')
        return {
            'ram_score':    round(score, 3),
            'raw_value':    round(raw, 2),
            'return_3m':    round(return_3m, 2),
            'volatility':   round(volatility_3m, 2),
            'label':        label,
        }
    except Exception as e:
        log.warning(f'risk_adjusted_momentum({ticker}): {e}')
        return {'ram_score': 0.5, 'raw_value': None, 'label': 'unavailable'}
