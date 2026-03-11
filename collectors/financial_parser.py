"""
collectors/financial_parser.py — ONLY file allowed to call yf.Ticker() for financials.
No other module may import yfinance DataFrames directly.

Always returns a dict with all keys. Missing values are None, never errors.
Handles both DataFrame orientations (metrics as rows OR as columns).
"""

import json
import os
from datetime import datetime

import pytz
import yfinance as yf

from utils.logger import get_logger
from utils.retry import retry_on_failure

log = get_logger('financial_parser')

FUNDAMENTALS_CACHE_DIR = 'data/fundamentals_cache'
CACHE_TTL_DAYS         = 7

# ── Empty result template — always returned, even on failure ───────────────
EMPTY_RESULT: dict = {
    'ticker':              None,
    'current_price':       None,
    'market_cap':          None,
    'avg_volume':          None,
    'beta':                None,
    'revenue_ttm':         None,
    'revenue_prev_year':   None,
    'net_income_ttm':      None,
    'eps_ttm':             None,
    'eps_quarterly':       [],
    'profit_margin':       None,
    'debt_to_equity':      None,
    'operating_cash_flow': None,
    'pe_ratio':            None,
    'earnings_date':       None,
    'industry':            None,
    'sector':              None,
    'data_source':         'unavailable',
    'cross_validated':     False,
}


# ── Cache helpers ──────────────────────────────────────────────────────────

def _cache_path(ticker: str) -> str:
    os.makedirs(FUNDAMENTALS_CACHE_DIR, exist_ok=True)
    return os.path.join(FUNDAMENTALS_CACHE_DIR, f'{ticker}.json')


def _load_cache(ticker: str) -> dict | None:
    path = _cache_path(ticker)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as f:
            cached = json.load(f)
        cached_date = datetime.fromisoformat(cached.get('_cached_at', '1970-01-01'))
        age_days    = (datetime.now(pytz.utc) - cached_date.replace(tzinfo=pytz.utc)).days
        if age_days <= CACHE_TTL_DAYS:
            log.info(f'{ticker}: using cached financials ({age_days}d old)')
            return cached
        log.info(f'{ticker}: cache expired ({age_days}d old) — refreshing')
    except Exception as e:
        log.warning(f'{ticker}: cache read error ({e})')
    return None


def _save_cache(ticker: str, data: dict) -> None:
    path  = _cache_path(ticker)
    store = {**data, '_cached_at': datetime.now(pytz.utc).isoformat()}
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(store, f, indent=2, default=str)
    except Exception as e:
        log.warning(f'{ticker}: cache write error ({e})')


# ── DataFrame orientation helper ───────────────────────────────────────────

def _get_metric(df, metric_name: str):
    """
    Reads a metric from a yfinance financial DataFrame.
    Handles both orientations: metrics-as-rows (index) and metrics-as-columns.
    Returns the most recent value or None.
    """
    if df is None or df.empty:
        return None
    try:
        # Orientation 1: metric is in the index (most common)
        if metric_name in df.index:
            row = df.loc[metric_name]
            val = row.iloc[0] if hasattr(row, 'iloc') else row
            return float(val) if val is not None and str(val) != 'nan' else None
        # Orientation 2: metric is a column
        if metric_name in df.columns:
            val = df[metric_name].iloc[0]
            return float(val) if val is not None and str(val) != 'nan' else None
    except Exception:
        pass
    return None


# ── Main fetch function ────────────────────────────────────────────────────

@retry_on_failure(max_attempts=2, delay=3.0)
def get_financials(ticker: str) -> dict:
    """
    Primary entry point. Returns enriched financial dict.
    Tries cache first. On cache miss, fetches live from yfinance.
    """
    cached = _load_cache(ticker)
    if cached:
        return cached

    result = _fetch_from_yfinance(ticker)
    if result.get('data_source') != 'unavailable':
        _save_cache(ticker, result)
    return result


def _fetch_from_yfinance(ticker: str) -> dict:
    """
    Fetches all financial data for one ticker. Never raises — returns empty dict on error.
    """
    import copy
    out = copy.deepcopy(EMPTY_RESULT)
    out['ticker'] = ticker

    try:
        stock = yf.Ticker(ticker)
        info  = stock.info or {}

        # ── Price and basic info ──────────────────────────────────────────
        out['current_price'] = (
            info.get('currentPrice') or info.get('regularMarketPrice')
        )
        try:
            out['current_price'] = float(out['current_price']) if out['current_price'] else None
        except (TypeError, ValueError):
            out['current_price'] = None

        out['market_cap']  = info.get('marketCap')
        out['avg_volume']  = info.get('averageVolume') or info.get('averageVolume10days')
        out['beta']        = info.get('beta')
        out['pe_ratio']    = info.get('trailingPE')
        out['profit_margin'] = info.get('profitMargins')
        if out['profit_margin']:
            out['profit_margin'] = float(out['profit_margin']) * 100  # convert to %
        out['debt_to_equity']      = info.get('debtToEquity') / 100 if info.get('debtToEquity') is not None else None
        out['operating_cash_flow'] = info.get('operatingCashflow')
        out['industry']            = info.get('industry')
        out['sector']              = info.get('sector')
        out['eps_ttm']             = info.get('trailingEps')

        # Earnings date (nearest upcoming)
        cal = stock.calendar
        if isinstance(cal, dict) and 'Earnings Date' in cal:
            ed = cal['Earnings Date']
            out['earnings_date'] = str(ed[0]) if isinstance(ed, list) else str(ed)

        # ── Income statement — revenue and net income ─────────────────────
        try:
            inc = stock.income_stmt
            out['revenue_ttm']       = _get_metric(inc, 'Total Revenue')
            out['net_income_ttm']    = _get_metric(inc, 'Net Income')
            # Previous year revenue (column 1 if available)
            if inc is not None and not inc.empty and len(inc.columns) > 1:
                prev_col = inc.columns[1]
                try:
                    rv = inc.loc['Total Revenue', prev_col] if 'Total Revenue' in inc.index else None
                    out['revenue_prev_year'] = float(rv) if rv is not None else None
                except Exception:
                    out['revenue_prev_year'] = None
        except Exception as e:
            log.warning(f'{ticker} income stmt: {e}')

        # ── Quarterly EPS ─────────────────────────────────────────────────
        try:
            qt = stock.quarterly_income_stmt
            if qt is not None and not qt.empty:
                eps_col = 'Basic EPS'
                if eps_col in qt.index:
                    eps_series = qt.loc[eps_col].dropna()
                    out['eps_quarterly'] = [
                        float(v) for v in eps_series.tolist()[:8]
                        if v is not None and str(v) != 'nan'
                    ]
        except Exception as e:
            log.warning(f'{ticker} quarterly EPS: {e}')

        out['data_source'] = 'yfinance'
        log.info(f'{ticker}: financials fetched OK (price={out["current_price"]})')

    except Exception as e:
        log.warning(f'{ticker}: yfinance fetch failed — {e}')
        out['data_source'] = 'unavailable'

    return out


# ── Alpha Vantage enrichment ───────────────────────────────────────────────

def enrich_with_alpha_vantage(ticker: str, av_data: dict, existing: dict) -> dict:
    """
    Merges Alpha Vantage data into an existing financial dict.
    AV data is used to fill gaps — yfinance values are NOT overwritten.
    Also performs cross-validation on structurally-identical fields.
    """
    if not av_data:
        return existing

    # Fill only missing values
    for field in ['market_cap', 'debt_to_equity', 'profit_margin', 'eps_ttm']:
        if existing.get(field) is None and av_data.get(field) is not None:
            existing[field] = av_data[field]
            log.info(f'{ticker}: filled {field} from Alpha Vantage')

    existing['cross_validated'] = cross_validate(ticker, existing, av_data)
    existing['data_source']     = 'yfinance+alphavantage'
    return existing


def cross_validate(ticker: str, yf_data: dict, av_data: dict) -> bool:
    """
    Validates market_cap (5% tolerance) and debt_to_equity (15% tolerance).
    Never compares revenue or net_income (TTM vs annual differences expected).
    Returns True if validation passes or fields are unavailable.
    """
    checks = [
        ('market_cap',    0.05),
        ('debt_to_equity', 0.15),
    ]
    for field, tol in checks:
        yf_val = yf_data.get(field)
        av_val = av_data.get(field)
        if yf_val is None or av_val is None:
            continue  # unavailable fields don't fail validation
        try:
            if abs(float(yf_val) - float(av_val)) / (abs(float(av_val)) + 1e-9) > tol:
                log.warning(
                    f'{ticker} cross-validation divergence: {field} '
                    f'yf={yf_val:.2f} av={av_val:.2f} (>{tol*100:.0f}% diff)'
                )
                return False
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    return True
