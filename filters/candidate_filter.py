"""
filters/candidate_filter.py — V5 thresholds for candidate company filtering.
Applied per ticker before any scoring. Uses data from financial_parser.get_financials().
"""

from utils.logger import get_logger
from config import MIN_MARKET_CAP_M, MIN_AVG_VOLUME, MIN_PRICE

log = get_logger('candidate_filter')


def passes_candidate_filter(
    ticker: str,
    fin: dict,
    sector: str,
    reported_companies: list[str],
) -> tuple[bool, str]:
    """
    Returns (True, '') if the candidate passes all filters,
    or (False, reason_string) if excluded.

    Filters (in order):
        1. Already reported today → skip (no data fetch needed)
        2. Market cap < $500M → exclude
        3. Average volume < 500,000 shares/day → exclude
        4. Current price < $5.00 → exclude
        5. Operating cash flow < 0 → exclude
        6. Debt-to-equity > 2.5 → exclude (EXCEPT financials sector)
    """
    # 1. Already reported
    if ticker in reported_companies:
        return False, 'already reported today'

    # 2. Market cap
    cap = fin.get('market_cap')
    if cap is not None and float(cap) < MIN_MARKET_CAP_M * 1_000_000:
        return False, f'market cap ${float(cap)/1e6:.0f}M below ${MIN_MARKET_CAP_M}M threshold'

    # 3. Average volume
    vol = fin.get('avg_volume')
    if vol is not None and float(vol) < MIN_AVG_VOLUME:
        return False, f'avg volume {int(float(vol)):,} below {MIN_AVG_VOLUME:,} threshold'

    # 4. Current price
    price = fin.get('current_price')
    if price is not None and float(price) < MIN_PRICE:
        return False, f'price ${float(price):.2f} below ${MIN_PRICE} minimum'

    # 5. Operating cash flow
    ocf = fin.get('operating_cash_flow')
    if ocf is not None and float(ocf) < 0:
        return False, f'negative operating cash flow ({float(ocf)/1e6:.0f}M)'

    # 6. Debt-to-equity — skip for financials sector
    if sector != 'financials':
        d_e = fin.get('debt_to_equity')
        if d_e is None:
            log.info(f'{ticker}: D/E missing — will be flagged in report but not excluded')
        elif float(d_e) > 2.5:
            return False, f'debt-to-equity {float(d_e):.2f} above 2.5 threshold'

    return True, ''


def apply_candidate_filter(
    tickers: list[str],
    financials: dict[str, dict],
    sector: str,
    reported_companies: list[str],
) -> list[str]:
    """
    Filters a list of tickers for a given sector.
    Returns list of tickers that passed all filters.

    financials: {ticker: fin_dict} — must be pre-fetched before calling this.
    """
    passed: list[str] = []
    for ticker in tickers:
        fin = financials.get(ticker, {})
        ok, reason = passes_candidate_filter(ticker, fin, sector, reported_companies)
        if ok:
            passed.append(ticker)
            log.info(f'{ticker} ({sector}): passed candidate filter')
        else:
            log.info(f'{ticker} ({sector}): filtered — {reason}')
    return passed
