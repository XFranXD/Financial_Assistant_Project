"""
analyzers/sector_validator.py — 3-signal ETF confirmation + multi-timeframe gate.
A sector must pass 2 of 3 signals AND 5d/10d must align with 1d direction.
"""

import json
import yfinance as yf
from utils.logger import get_logger
from utils.retry import retry_on_failure
from config import SECTOR_ETFS_FILE

log = get_logger('sector_validator')


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
def _fetch_etf_prices(etf_ticker: str) -> dict | None:
    """Fetches multi-period price data for 3-signal validation."""
    try:
        d = yf.Ticker(etf_ticker).history(period='15d')
        if d is None or len(d) < 11:
            return None

        closes = list(d['Close'])
        volumes = list(d['Volume'])
        curr   = closes[-1]
        prev   = closes[-2]
        p5d    = closes[-6]  if len(closes) >= 6  else None
        p10d   = closes[-11] if len(closes) >= 11 else None
        ma5    = sum(closes[-5:]) / 5 if len(closes) >= 5 else None

        # Average volume over 10 days vs today
        avg_vol_10 = sum(volumes[-11:-1]) / 10 if len(volumes) >= 11 else None
        today_vol  = volumes[-1]

        return {
            'curr':       curr,
            'prev':       prev,
            'p5d':        p5d,
            'p10d':       p10d,
            'ma5':        ma5,
            'today_vol':  today_vol,
            'avg_vol_10': avg_vol_10,
        }
    except Exception as e:
        log.warning(f'ETF fetch {etf_ticker}: {e}')
        return None


def validate_sector(sector: str, expected_direction: str = 'positive') -> dict:
    """
    3-signal validation for a confirmed sector:
      Signal 1 — Price direction: today's ETF close vs yesterday (1d)
      Signal 2 — MA trend: price > 5-day moving average
      Signal 3 — Volume confirmation: today volume > 10-day average

    Timeframe gate: 5d AND 10d returns must align with expected_direction.
    Passes if: signals_passed >= 2 AND timeframe gate passes.

    Returns:
        {'confirmed': bool, 'signals_passed': int, 'timeframe_ok': bool, 'details': dict}
    """
    etfs      = _load_etfs()
    etf       = etfs.get(sector)
    if not etf:
        log.warning(f'No ETF configured for sector: {sector}')
        return _fail(sector, 'no ETF configured')

    data = _fetch_etf_prices(etf)
    if data is None:
        log.warning(f'Sector {sector}: ETF {etf} data unavailable')
        return _fail(sector, 'ETF data unavailable')

    curr  = data['curr']
    prev  = data['prev']
    p5d   = data.get('p5d')
    p10d  = data.get('p10d')
    ma5   = data.get('ma5')

    # --- Signal 1: 1-day price direction ---
    is_positive_1d = curr > prev
    signal1 = (is_positive_1d == (expected_direction == 'positive'))

    # --- Signal 2: Price above 5-day MA ---
    signal2 = (curr > ma5) if ma5 else False

    # --- Signal 3: Volume above 10-day average ---
    avg_vol = data.get('avg_vol_10')
    signal3 = (data['today_vol'] > avg_vol) if avg_vol else False

    signals_passed = sum([signal1, signal2, signal3])

    # --- Timeframe gate: 5d and 10d must align ---
    ret5d_ok  = True
    ret10d_ok = True
    if p5d and p5d > 0:
        ret5d  = (curr - p5d) / p5d * 100
        if expected_direction == 'positive':
            ret5d_ok = ret5d > 0
        else:
            ret5d_ok = ret5d < 0
    if p10d and p10d > 0:
        ret10d = (curr - p10d) / p10d * 100
        if expected_direction == 'positive':
            ret10d_ok = ret10d > 0
        else:
            ret10d_ok = ret10d < 0

    timeframe_ok = ret5d_ok and ret10d_ok
    confirmed    = (signals_passed >= 2) and timeframe_ok

    log.info(
        f'Sector {sector}/{etf}: sig1={signal1} sig2={signal2} sig3={signal3} '
        f'tf_ok={timeframe_ok} → {"CONFIRMED" if confirmed else "REJECTED"}'
    )

    return {
        'confirmed':      confirmed,
        'signals_passed': signals_passed,
        'timeframe_ok':   timeframe_ok,
        'direction':      expected_direction,
        'etf':            etf,
        'details': {
            'price_direction_ok': signal1,
            'above_ma5':         signal2,
            'volume_up':         signal3,
            '5d_aligned':        ret5d_ok,
            '10d_aligned':       ret10d_ok,
        },
    }


def _fail(sector: str, reason: str) -> dict:
    log.info(f'Sector {sector} validation failed: {reason}')
    return {
        'confirmed':      False,
        'signals_passed': 0,
        'timeframe_ok':   False,
        'direction':      'unknown',
        'etf':            None,
        'details':        {'reason': reason},
    }
