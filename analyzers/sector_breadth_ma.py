"""
analyzers/sector_breadth_ma.py — §13 NEW
Structural breadth: % of sector stocks trading above their 50-day MA.
Measures weeks-long trend health, not just today's movement.
"""

import json
import yfinance as yf
from utils.logger import get_logger
from utils.retry import retry_on_failure
from config import SECTOR_BREADTH_STOCKS_FILE

log = get_logger('sector_breadth_ma')


@retry_on_failure(max_attempts=2, delay=2.0)
def _above_ma50(ticker: str) -> bool | None:
    try:
        d = yf.Ticker(ticker).history(period='3mo')
        if d is None or len(d) < 50: return None
        return float(d['Close'].iloc[-1]) > float(d['Close'].tail(50).mean())
    except Exception as e:
        log.warning(f'MA50 check {ticker}: {e}')
        return None


def compute_sector_breadth_ma(sector_breadth_stocks: dict) -> dict:
    """
    Returns dict: {sector: {'breadth_ma_score': 0-1, 'label': str, 'pct': float}}
    Called once per run. Results stored in state['sector_breadth_ma_today'].
    """
    results = {}
    for sector, tickers in sector_breadth_stocks.items():
        above = 0; checked = 0
        for ticker in tickers:
            r = _above_ma50(ticker)
            if r is None: continue
            checked += 1
            if r: above += 1

        if checked == 0:
            results[sector] = {'breadth_ma_score': 0.5, 'label': 'unavailable', 'pct': None}
            continue

        pct   = above / checked
        score = pct   # already 0-1

        if pct > 0.70:    label = 'sector is genuinely strong'
        elif pct > 0.50:  label = 'healthy participation'
        elif pct >= 0.30: label = 'mixed signals'
        else:             label = 'sector is structurally weak'

        log.info(f'Sector breadth MA {sector}: {above}/{checked} = {pct:.2f} ({label})')
        results[sector] = {
            'breadth_ma_score': round(score, 3),
            'pct':              round(pct * 100, 1),
            'label':            label,
        }
    return results
