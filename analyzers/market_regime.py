"""
analyzers/market_regime.py — VIX-based market regime classification.
Called once per run. Returns regime dict with risk_mult and opp_mult.
On VIX unavailable → uses 'normal' regime.
"""

import yfinance as yf
from utils.logger import get_logger
from config import VIX_REGIMES, RISK_CAPS

log = get_logger('market_regime')


def get_regime() -> dict:
    """
    Fetches VIX (^VIX) and classifies the current market regime.

    Returns:
        {
            'regime':    'normal',
            'vix':       18.4,
            'risk_mult': 1.0,
            'opp_mult':  1.0,
            'risk_cap':  70,
            'label':     'Normal market',
        }
    """
    vix_value = _fetch_vix()

    if vix_value is None:
        log.warning('VIX unavailable — defaulting to normal regime')
        regime_key = 'normal'
    elif vix_value < 15:
        regime_key = 'low_vol'
    elif vix_value < 25:
        regime_key = 'normal'
    elif vix_value < 35:
        regime_key = 'elevated'
    else:
        regime_key = 'crisis'

    cfg = VIX_REGIMES[regime_key]
    out = {
        'regime':    regime_key,
        'vix':       vix_value,
        'risk_mult': cfg['risk_mult'],
        'opp_mult':  cfg['opp_mult'],
        'risk_cap':  RISK_CAPS[regime_key],
        'label':     cfg['label'],
    }
    log.info(f'Regime: {regime_key} vix={vix_value} risk_mult={cfg["risk_mult"]} opp_mult={cfg["opp_mult"]}')
    return out


def _fetch_vix() -> float | None:
    try:
        d = yf.Ticker('^VIX').history(period='2d')
        if d is None or d.empty:
            return None
        val = float(d['Close'].iloc[-1])
        log.info(f'VIX fetched: {val:.2f}')
        return round(val, 2)
    except Exception as e:
        log.warning(f'VIX fetch error: {e}')
        return None
