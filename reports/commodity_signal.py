"""
reports/commodity_signal.py
Fetches 5-day momentum for WTI crude (CL=F) and natural gas (NG=F) via yfinance.
Returns a plain English summary string for report injection.
Does not modify any score. Fails silently — returns empty string on any error.
"""

import yfinance as yf
from utils.logger import get_logger

log = get_logger('commodity_signal')


def get_commodity_signal() -> dict:
    """
    Returns:
        crude_trend: 'positive' | 'neutral' | 'negative'
        gas_trend:   'positive' | 'neutral' | 'negative'
        crude_pct:   float  (5-day return %)
        gas_pct:     float
        summary:     str    (plain English, empty string on failure)
    """
    default = {
        'crude_trend': 'neutral',
        'gas_trend':   'neutral',
        'crude_pct':   0.0,
        'gas_pct':     0.0,
        'summary':     '',
    }

    try:
        crude_hist = yf.Ticker('CL=F').history(period='7d')
        gas_hist   = yf.Ticker('NG=F').history(period='7d')

        if crude_hist.empty or len(crude_hist) < 2:
            log.warning('commodity_signal: CL=F history empty or insufficient')
            return default

        if gas_hist.empty or len(gas_hist) < 2:
            log.warning('commodity_signal: NG=F history empty or insufficient')
            return default

        crude_pct = round(
            (crude_hist['Close'].iloc[-1] - crude_hist['Close'].iloc[0])
            / crude_hist['Close'].iloc[0] * 100,
            1,
        )
        gas_pct = round(
            (gas_hist['Close'].iloc[-1] - gas_hist['Close'].iloc[0])
            / gas_hist['Close'].iloc[0] * 100,
            1,
        )

        def classify(pct: float) -> str:
            if pct >= 1.5:
                return 'positive'
            if pct <= -1.5:
                return 'negative'
            return 'neutral'

        crude_trend = classify(crude_pct)
        gas_trend   = classify(gas_pct)

        parts = []
        if crude_trend == 'positive':
            parts.append(f'WTI crude up {crude_pct}% over 5 days')
        elif crude_trend == 'negative':
            parts.append(f'WTI crude down {abs(crude_pct)}% over 5 days')
        else:
            parts.append(f'WTI crude flat ({crude_pct:+.1f}%)')

        if gas_trend == 'positive':
            parts.append(f'natural gas up {gas_pct}% over 5 days')
        elif gas_trend == 'negative':
            parts.append(f'natural gas down {abs(gas_pct)}% over 5 days')
        else:
            parts.append(f'natural gas flat ({gas_pct:+.1f}%)')

        summary = 'Commodity momentum: ' + ' · '.join(parts) + '.'
        log.debug(f'commodity_signal: {summary}')

        return {
            'crude_trend': crude_trend,
            'gas_trend':   gas_trend,
            'crude_pct':   crude_pct,
            'gas_pct':     gas_pct,
            'summary':     summary,
        }

    except Exception as e:
        log.error(f'commodity_signal: failed — {e}')
        return default
