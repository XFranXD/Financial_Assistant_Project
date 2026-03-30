"""
collectors/market_collector.py — Fetches Dow, S&P 500, Nasdaq snapshots.
Called once per run. Results stored in state['indices_today'].
"""

import yfinance as yf

from utils.logger import get_logger

log = get_logger('market_collector')


def get_index_snapshot() -> dict:
    """
    Returns current readings for the three major US indices.
    Direction label: Rising / Falling / Flat (within 0.1%)
    On any failure, that index returns 'unavailable' — never crashes the run.
    """
    indices = {
        'dow':    '^DJI',
        'sp500':  '^GSPC',
        'nasdaq': '^IXIC',
    }
    result = {}
    for name, ticker in indices.items():
        try:
            d = yf.Ticker(ticker).history(period='2d')
            if d is None or len(d) < 2:
                log.warning(f'Index {name}: insufficient data (len={len(d) if d is not None else 0})')
                result[name] = {'value': None, 'change_pct': None, 'label': 'unavailable'}
                continue

            prev  = float(d['Close'].iloc[-2])
            curr  = float(d['Close'].iloc[-1])
            chg   = ((curr - prev) / prev) * 100 if prev != 0 else 0.0
            label = 'Rising' if chg > 0.1 else 'Falling' if chg < -0.1 else 'Flat'

            log.info(f'Index {name}: {curr:.2f} {label} ({chg:+.2f}%)')
            result[name] = {
                'value':      round(curr, 2),
                'change_pct': round(chg, 2),
                'label':      label,
            }
        except Exception as e:
            log.warning(f'Index {name}: {e}')
            result[name] = {'value': None, 'change_pct': None, 'label': 'unavailable'}

    return result


def format_index_for_email(snapshot: dict) -> str:
    """
    Renders the Market Pulse block for email — plain text lines.

    Example output:
        Dow Jones:  42,150  ▲ +0.8%  Rising
        S&P 500:     5,234  ▲ +0.6%  Rising
        Nasdaq:     18,920  ▼ -0.2%  Falling
    """
    labels = {
        'dow':    'Dow Jones',
        'sp500':  'S&P 500 ',
        'nasdaq': 'Nasdaq  ',
    }
    lines = []
    for key, display in labels.items():
        d = snapshot.get(key, {})
        if d.get('value') is None:
            lines.append(f'{display}: data unavailable')
            continue
        val    = f"{d['value']:,.2f}"
        chg    = d['change_pct']
        arrow  = '▲' if chg >= 0 else '▼'
        sign   = '+' if chg >= 0 else ''
        lines.append(f'{display}: {val:>10}  {arrow} {sign}{chg:.1f}%  {d["label"]}')

    return '\n'.join(lines)


def get_index_history() -> dict:
    """
    Fetch ~30 trading days of daily close prices for DJI, S&P 500, Nasdaq.

    Returns
    -------
    dict with keys 'dow', 'sp500', 'nasdaq', each a list[float] of closing
    prices ordered oldest → newest. On failure for any index, value is [].
    Never raises — failures are logged as warnings.
    """
    indices = {
        'dow':    '^DJI',
        'sp500':  '^GSPC',
        'nasdaq': '^IXIC',
    }
    result = {}
    for name, ticker in indices.items():
        try:
            data = yf.Ticker(ticker).history(period='35d')
            if data is None or len(data) < 2:
                log.warning(f'get_index_history {name}: insufficient data')
                result[name] = []
                continue
            closes = [round(float(v), 2) for v in data['Close'].dropna().tolist()]
            result[name] = closes[-30:] if len(closes) >= 30 else closes
            log.info(f'get_index_history {name}: {len(result[name])} points')
        except Exception as e:
            log.warning(f'get_index_history {name}: {e}')
            result[name] = []
    return result
