"""
analyzers/spy_sma.py
Fetches SPY current price and its 200-day simple moving average via yfinance.
Used by the Market Regime Classifier (2A) to determine broad market trend.
Non-fatal — returns all-None dict on any error.
"""

import yfinance as yf
from utils.logger import get_logger

log = get_logger('spy_sma')


def get_spy_vs_200d() -> dict:
    """
    Fetches SPY history and computes its 200-day SMA.

    Returns:
        {
            'spy_price':      float | None  — latest closing price
            'spy_sma_200':    float | None  — mean of last 200 closing prices
            'spy_above_200d': bool  | None  — True if spy_price > spy_sma_200
        }
    On any exception: returns all-None dict. Never raises.
    """
    _default = {'spy_price': None, 'spy_sma_200': None, 'spy_above_200d': None}
    try:
        data = yf.Ticker('SPY').history(period='1y')
        if data is None or len(data) < 200:
            log.warning(f'[SPY] Insufficient history: {0 if data is None else len(data)} rows (need 200)')
            return _default

        spy_price   = float(data['Close'].iloc[-1])
        spy_sma_200 = float(data['Close'].tail(200).mean())
        spy_above   = spy_price > spy_sma_200

        log.info(f'[SPY] price={spy_price:.2f} sma200={spy_sma_200:.2f} above={spy_above}')
        return {
            'spy_price':      round(spy_price,   2),
            'spy_sma_200':    round(spy_sma_200, 2),
            'spy_above_200d': spy_above,
        }
    except Exception as e:
        log.warning(f'[SPY] get_spy_vs_200d failed: {e}')
        return _default
