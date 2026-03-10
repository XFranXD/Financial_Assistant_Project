"""
validate_tickers.py — ONE-TIME SETUP SCRIPT.
Run before first deploy: python validate_tickers.py

Checks every ticker in data/sector_tickers.json against yfinance.
Writes data/sector_tickers_validated.json with only valid tickers.

Filters applied:
  - Quote type must be EQUITY
  - Exchange must be in: NMS, NYQ, NGM, NCM, ASE
  - Market cap >= $500 million
  - Average volume >= 500,000 shares/day
  - Current price >= $5.00
  - Sector must match SECTOR_EQUIVALENCE mapping
"""

import json
import sys
import time
from datetime import datetime

import pytz
import yfinance as yf

# ── Config inline (avoid circular import from config.py at setup time) ─────
MIN_MARKET_CAP_M = 500
MIN_AVG_VOLUME   = 500_000
MIN_PRICE        = 5.00
VALID_EXCHANGES  = {'NMS', 'NYQ', 'NGM', 'NCM', 'ASE'}

SECTOR_EQUIVALENCE = {
    'Technology':             'technology',
    'Healthcare':             'healthcare',
    'Financial Services':     'financials',
    'Consumer Cyclical':      'consumer_discretionary',
    'Consumer Defensive':     'consumer_staples',
    'Industrials':            'industrials',
    'Basic Materials':        'materials',
    'Energy':                 'energy',
    'Utilities':              'utilities',
    'Real Estate':            'real_estate',
    'Communication Services': 'communication_services',
    'Semiconductors':         'semiconductors',
    'Defense':                'defense',
}

# Industry keywords for subset sectors
SUBSET_KEYWORDS = {
    'semiconductors': ['semiconductor', 'chip', 'wafer', 'fab', 'integrated circuit'],
    'defense':        ['defense', 'aerospace', 'military', 'government', 'armament'],
}

SECTOR_TICKERS_FILE    = 'data/sector_tickers.json'
VALIDATED_OUTPUT_FILE  = 'data/sector_tickers_validated.json'
REQUEST_DELAY_S        = 0.35   # yfinance rate limit courtesy delay

# ── Logging to stdout only (setup script) ─────────────────────────────────

def _log(msg: str):
    ts = datetime.now(pytz.utc).strftime('%H:%M:%SZ')
    print(f'[{ts}] {msg}', flush=True)


def validate_ticker(ticker: str, expected_sector: str) -> dict | None:
    """
    Validates one ticker. Returns enriched dict if passes all filters, else None.
    """
    try:
        info = yf.Ticker(ticker).info
        if not info or not isinstance(info, dict):
            _log(f'  SKIP {ticker}: no info returned')
            return None

        quote_type = info.get('quoteType', '')
        if quote_type != 'EQUITY':
            _log(f'  SKIP {ticker}: quoteType={quote_type}')
            return None

        exchange = info.get('exchange', '')
        if exchange not in VALID_EXCHANGES:
            _log(f'  SKIP {ticker}: exchange={exchange}')
            return None

        # Market cap check
        market_cap = info.get('marketCap') or 0
        if market_cap < MIN_MARKET_CAP_M * 1_000_000:
            _log(f'  SKIP {ticker}: marketCap=${market_cap/1e6:.0f}M < ${MIN_MARKET_CAP_M}M')
            return None

        # Volume check
        avg_volume = info.get('averageVolume') or info.get('averageVolume10days') or 0
        if avg_volume < MIN_AVG_VOLUME:
            _log(f'  SKIP {ticker}: avgVol={avg_volume:,} < {MIN_AVG_VOLUME:,}')
            return None

        # Price check
        price = info.get('currentPrice') or info.get('regularMarketPrice') or 0
        if price < MIN_PRICE:
            _log(f'  SKIP {ticker}: price=${price:.2f} < ${MIN_PRICE}')
            return None

        # Sector match
        yf_sector   = info.get('sector', '')
        yf_industry = info.get('industry', '').lower()
        mapped      = SECTOR_EQUIVALENCE.get(yf_sector, None)

        # For subset sectors (semiconductors, defense), check industry keywords
        if expected_sector in SUBSET_KEYWORDS:
            keywords = SUBSET_KEYWORDS[expected_sector]
            if not any(kw in yf_industry for kw in keywords):
                _log(f'  SKIP {ticker}: industry "{yf_industry}" not {expected_sector}')
                return None
        elif mapped != expected_sector:
            _log(f'  SKIP {ticker}: sector mismatch — yf={yf_sector}, expected={expected_sector}')
            return None

        # Determine cap tier
        cap_b = market_cap / 1_000_000_000
        cap_tier = 'large' if cap_b >= 10 else 'mid'

        _log(f'  OK   {ticker}: ${price:.2f} | vol={avg_volume:,} | cap={cap_tier} (${cap_b:.1f}B)')
        return {
            'ticker':        ticker,
            'sector':        expected_sector,
            'market_cap_b':  round(cap_b, 2),
            'cap_tier':      cap_tier,
            'avg_volume':    int(avg_volume),
            'price':         round(float(price), 2),
            'exchange':      exchange,
            'yf_sector':     yf_sector,
            'industry':      yf_industry,
        }

    except Exception as e:
        _log(f'  ERROR {ticker}: {e}')
        return None


def main():
    _log('=== validate_tickers.py — starting ===')

    try:
        with open(SECTOR_TICKERS_FILE, encoding='utf-8') as f:
            sector_tickers: dict = json.load(f)
    except FileNotFoundError:
        _log(f'CRITICAL: {SECTOR_TICKERS_FILE} not found. Exiting.')
        sys.exit(1)

    # Remove meta key if present
    sector_tickers.pop('_comment', None)

    validated: dict[str, list[dict]] = {}
    total_checked = 0
    total_passed  = 0

    for sector, tickers in sector_tickers.items():
        _log(f'\n-- Sector: {sector} ({len(tickers)} tickers) --')
        validated[sector] = []
        for ticker in tickers:
            total_checked += 1
            result = validate_ticker(ticker, sector)
            if result:
                validated[sector].append(result)
                total_passed += 1
            time.sleep(REQUEST_DELAY_S)

    output = {
        'validated_date': datetime.now(pytz.utc).strftime('%Y-%m-%d'),
        'total_sectors':  len(validated),
        'total_tickers':  total_passed,
        'sectors':        validated,
    }

    with open(VALIDATED_OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)

    _log(f'\n=== Done: {total_passed}/{total_checked} tickers passed validation ===')
    _log(f'Written to: {VALIDATED_OUTPUT_FILE}')

    # Summary per sector
    for sector, tickers in validated.items():
        _log(f'  {sector}: {len(tickers)} validated tickers')


if __name__ == '__main__':
    main()
