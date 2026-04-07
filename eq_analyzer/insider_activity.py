"""
eq_analyzer/insider_activity.py
Fetches SEC Form 4 insider transaction data via EDGAR RSS for a given ticker.
Reuses EdgarFetcher CIK resolution. Returns a directional signal only.
Non-fatal — returns UNAVAILABLE on any error or missing data.
"""

import logging
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Atom namespace for EDGAR RSS feeds
_ATOM_NS = '{http://www.w3.org/2005/Atom}'

# Rate limit between EDGAR HTTP requests (seconds)
_RATE_LIMIT = 0.25

# Only consider filings from the last 90 days
_LOOKBACK_DAYS = 90

# User-Agent for SEC requests (reuse same policy as edgar_fetcher.py)
_USER_AGENT = 'MRE-System research@mre-system.com'


def get_insider_signal(ticker: str, fetcher) -> dict:
    """
    Fetches SEC Form 4 insider transaction data via EDGAR RSS for the last 90 days.
    Reuses EdgarFetcher CIK resolution.

    Args:
        ticker:  Stock ticker symbol
        fetcher: Instantiated EdgarFetcher object (from eq_analyzer/main.py)

    Returns:
        {
            'insider_signal': 'ACCUMULATING' | 'DISTRIBUTING' | 'NEUTRAL' | 'UNAVAILABLE',
            'insider_note':   str,
        }
    """
    default = {
        'insider_signal': 'UNAVAILABLE',
        'insider_note': '',
    }

    try:
        # ── CIK resolution via existing fetcher ──────────────────────────
        cik = fetcher._resolve_cik(ticker)
        if not cik:
            logger.info(f'[INS] {ticker}: CIK resolution failed — UNAVAILABLE')
            return default

        session = requests.Session()
        session.headers.update({
            'User-Agent': _USER_AGENT,
            'Accept-Encoding': 'gzip, deflate',
        })

        # ── Fetch Atom feed for Form 4s ──────────────────────────────────
        atom_url = (
            f'https://www.sec.gov/cgi-bin/browse-edgar'
            f'?action=getcompany&CIK={cik}&type=4&dateb=&owner=include'
            f'&count=40&output=atom'
        )
        time.sleep(_RATE_LIMIT)
        resp = session.get(atom_url, timeout=15)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        entries = root.findall(f'{_ATOM_NS}entry')

        if not entries:
            logger.info(f'[INS] {ticker}: No Form 4 entries found')
            return {
                'insider_signal': 'NEUTRAL',
                'insider_note': 'No significant insider activity',
            }

        cutoff = datetime.now(timezone.utc).timestamp() - (_LOOKBACK_DAYS * 86400)
        total_bought = 0.0
        total_sold = 0.0
        filings_parsed = 0

        for entry in entries:
            # ── Check filing date is within 90 days ──────────────────────
            updated_el = entry.find(f'{_ATOM_NS}updated')
            if updated_el is None:
                updated_el = entry.find(f'{_ATOM_NS}published')
            if updated_el is None or not updated_el.text:
                continue

            try:
                # Parse ISO date, handle various formats
                date_str = updated_el.text.strip()
                if date_str.endswith('Z'):
                    date_str = date_str[:-1] + '+00:00'
                filing_dt = datetime.fromisoformat(date_str)
                if filing_dt.timestamp() < cutoff:
                    continue
            except (ValueError, AttributeError):
                continue

            # ── Find the filing index page link ──────────────────────────
            link_el = entry.find(f'{_ATOM_NS}link')
            if link_el is None:
                continue
            index_url = link_el.get('href', '')
            if not index_url:
                continue

            # ── Fetch the filing index page ──────────────────────────────
            try:
                time.sleep(_RATE_LIMIT)
                idx_resp = session.get(index_url, timeout=15)
                idx_resp.raise_for_status()
                idx_html = idx_resp.text
            except Exception:
                continue

            # ── Find the Form 4 XML link ─────────────────────────────────
            xml_url = _find_form4_xml_url(idx_html, index_url)
            if not xml_url:
                continue

            # ── Fetch and parse the Form 4 XML ───────────────────────────
            try:
                time.sleep(_RATE_LIMIT)
                xml_resp = session.get(xml_url, timeout=15)
                xml_resp.raise_for_status()
                bought, sold = _parse_form4_xml(xml_resp.content)
                total_bought += bought
                total_sold += sold
                filings_parsed += 1
            except Exception as e:
                logger.debug(f'[INS] {ticker}: Failed to parse Form 4 XML: {e}')
                continue

        logger.info(
            f'[INS] {ticker}: parsed {filings_parsed} filings, '
            f'bought=${total_bought:,.0f}, sold=${total_sold:,.0f}'
        )

        # ── Signal classification ────────────────────────────────────────
        if total_bought == 0 and total_sold == 0:
            return {
                'insider_signal': 'NEUTRAL',
                'insider_note': 'No significant insider activity',
            }

        if total_bought > total_sold * 1.5:
            return {
                'insider_signal': 'ACCUMULATING',
                'insider_note': 'Net insider buying over 90 days',
            }
        elif total_sold > total_bought * 1.5:
            return {
                'insider_signal': 'DISTRIBUTING',
                'insider_note': 'Net insider selling over 90 days',
            }
        else:
            return {
                'insider_signal': 'NEUTRAL',
                'insider_note': 'No significant insider activity',
            }

    except Exception as e:
        logger.warning(f'[INS] {ticker}: insider activity check failed — {e}')
        return default


def _find_form4_xml_url(index_html: str, index_url: str) -> str | None:
    """
    Find the Form 4 XML URL from the filing index page HTML.
    XML Discovery Rule: Select the first link where href ends with .xml
    AND the filename contains 'form4' (case-insensitive).
    Fallback: first link ending in .xml.
    """
    import re

    # Extract all .xml links
    xml_links = re.findall(r'href=["\']([^"\']*\.xml)["\']', index_html, re.IGNORECASE)
    if not xml_links:
        return None

    # Determine base URL for relative links
    base_url = index_url.rsplit('/', 1)[0] if '/' in index_url else index_url

    # Try to find form4 match first
    for link in xml_links:
        filename = link.rsplit('/', 1)[-1].lower()
        if 'form4' in filename:
            if link.startswith('http'):
                return link
            elif link.startswith('/'):
                return f'https://www.sec.gov{link}'
            else:
                return f'{base_url}/{link}'

    # Fallback: first .xml link
    link = xml_links[0]
    if link.startswith('http'):
        return link
    elif link.startswith('/'):
        return f'https://www.sec.gov{link}'
    else:
        return f'{base_url}/{link}'


def _parse_form4_xml(xml_content: bytes) -> tuple[float, float]:
    """
    Parse a Form 4 XML document and compute total bought vs sold dollar amounts.

    Exact Parsing Paths:
      Root: .//nonDerivativeTransaction
      Shares: ./transactionAmounts/transactionShares/value
      Price: ./transactionAmounts/transactionPricePerShare/value
      Code: ./transactionAmounts/transactionAcquiredDisposedCode/value
            'A' = Buy, 'D' = Sell

    Returns: (total_bought, total_sold) in dollar amounts
    """
    total_bought = 0.0
    total_sold = 0.0

    try:
        root = ET.fromstring(xml_content)
        transactions = root.findall('.//nonDerivativeTransaction')

        for txn in transactions:
            try:
                shares_el = txn.find('./transactionAmounts/transactionShares/value')
                price_el = txn.find('./transactionAmounts/transactionPricePerShare/value')
                code_el = txn.find('./transactionAmounts/transactionAcquiredDisposedCode/value')

                if shares_el is None or code_el is None:
                    continue

                shares = float(shares_el.text) if shares_el.text else 0.0
                price = float(price_el.text) if (price_el is not None and price_el.text) else 0.0
                code = (code_el.text or '').strip().upper()

                dollar_amount = shares * price

                if code == 'A':
                    total_bought += dollar_amount
                elif code == 'D':
                    total_sold += dollar_amount
            except (ValueError, TypeError, AttributeError):
                continue
    except ET.ParseError:
        pass

    return total_bought, total_sold
