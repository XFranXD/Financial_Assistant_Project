"""
analyzers/drawdown_risk.py — §17 NEW
Measures 90-day peak decline. Higher drawdown = higher risk.
Score is INVERTED: lower drawdown = higher score.

Formula: max_drawdown_90d = (highest_price_in_90d - current_price) / highest_price_in_90d
"""

import yfinance as yf
from utils.logger import get_logger
from utils.retry import retry_on_failure

log = get_logger('drawdown_risk')


@retry_on_failure(max_attempts=2, delay=2.0)
def compute_drawdown_risk(ticker: str) -> dict:
    """
    Returns drawdown_score 0.0-1.0 where 1.0 = no drawdown (near 90-day high).
    drawdown_pct is the raw percentage decline from the 90-day peak.
    Added to risk_model as a 10% weighted component.
    """
    try:
        d = yf.Ticker(ticker).history(period='5mo')
        if d is None or len(d) < 63:
            return {'drawdown_score': 0.5, 'drawdown_pct': None, 'label': 'unavailable'}

        recent      = d['Close'].tail(90)
        current     = float(recent.iloc[-1])
        peak_90d    = float(recent.max())

        if peak_90d == 0:
            return {'drawdown_score': 0.5, 'drawdown_pct': None, 'label': 'unavailable'}

        drawdown_pct = ((peak_90d - current) / peak_90d) * 100
        score        = max(0.0, min(1.0, 1.0 - (drawdown_pct / 40)))  # 0%=1.0, 40%+=0.0

        if drawdown_pct < 10:   label = 'near its recent high — strong position'
        elif drawdown_pct < 20: label = 'moderate dip from recent high — normal'
        elif drawdown_pct < 35: label = 'significant decline from recent high'
        else:                   label = 'major decline — review carefully before research'

        log.info(f'{ticker} drawdown={drawdown_pct:.1f}% score={score:.2f}')
        return {
            'drawdown_score': round(score, 3),
            'drawdown_pct':   round(drawdown_pct, 1),
            'label':          label,
        }
    except Exception as e:
        log.warning(f'drawdown_risk({ticker}): {e}')
        return {'drawdown_score': 0.5, 'drawdown_pct': None, 'label': 'unavailable'}
