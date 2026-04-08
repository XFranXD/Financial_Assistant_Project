"""
eq_analyzer/insider_activity.py
Fetches SEC Form 4 insider transaction data via EDGAR RSS for a given ticker.
Reuses EdgarFetcher CIK resolution. Returns a directional signal only.
Non-fatal — returns UNAVAILABLE on any error or missing data.

Signal logic:
  ACCUMULATING — net insider buying > net selling * 1.5 over last 90 days
  DISTRIBUTING — net insider selling > net buying * 1.5 over last 90 days
  NEUTRAL      — no clear direction or insufficient data
  UNAVAILABLE  — CIK not resolved, fetch failed, or parse error
"""

import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests

log = logging.getLogger(__name__)

_EDGAR_SLEEP = 0.25   # seconds between EDGAR HTTP requests (same as edgar_fetcher.py)
_LOOKBACK_DAYS = 90


def get_insider_signal(ticker: str, fetcher) -> dict:
    """
    Fetches SEC Form 4 insider transaction data via EDGAR Atom RSS for the
    last 90 days. Reuses the passed-in EdgarFetcher instance for CIK resolution.

    Args:
        ticker:  uppercase stock symbol
        fetcher: instantiated EdgarFetcher object from the EQ pipeline

    Returns:
        {
            'insider_signal': 'ACCUMULATING' | 'DISTRIBUTING' | 'NEUTRAL' | 'UNAVAILABLE',
            'insider_note':   str,
        }
    """
    _unavail = {'insider_signal': 'UNAVAILABLE', 'insider_note': ''}

    try:
        # ── CIK resolution via existing fetcher ──────────────────────────
        cik = fetcher._resolve_cik(ticker)
        if not cik:
            log.info(f'[INS] {ticker}: CIK not resolved — UNAVAILABLE')
            return _unavail

        # ── Session for all EDGAR requests ────────────────────────────────
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'MRE-InsiderTracker contact@example.com',
            'Accept-Encoding': 'gzip, deflate',
        })

        cutoff = datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS)

        # ── Fetch Atom feed for Form 4s ───────────────────────────────────
        feed_url = (
            f'https://www.sec.gov/cgi-bin/browse-edgar'
            f'?action=getcompany&CIK={cik}&type=4&dateb=&owner=include'
            f'&count=40&output=atom'
        )
        time.sleep(_EDGAR_SLEEP)
        try:
            feed_resp = session.get(feed_url, timeout=15)
        except Exception as e:
            log.info(f'[INS] {ticker}: feed fetch error — {e}')
            return _unavail

        if not feed_resp.ok:
            log.info(f'[INS] {ticker}: feed HTTP {feed_resp.status_code}')
            return _unavail

        # ── Parse Atom feed ───────────────────────────────────────────────
        try:
            feed_root = ET.fromstring(feed_resp.content)
        except ET.ParseError as e:
            log.info(f'[INS] {ticker}: Atom parse error — {e}')
            return _unavail

        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = feed_root.findall('atom:entry', ns)

        total_bought = 0.0
        total_sold   = 0.0
        filings_parsed = 0

        for entry in entries:
            # ── Date filter: ignore filings older than 90 days ─────────────
            updated_el = entry.find('atom:updated', ns)
            if updated_el is None:
                updated_el = entry.find('atom:published', ns)
            if updated_el is not None and updated_el.text:
                try:
                    # Atom timestamps: 2024-11-04T00:00:00-04:00 or Z
                    ts_text = updated_el.text.strip()
                    # Normalize timezone offset
                    if ts_text.endswith('Z'):
                        ts_text = ts_text[:-1] + '+00:00'
                    filing_dt = datetime.fromisoformat(ts_text)
                    if filing_dt.tzinfo is None:
                        filing_dt = filing_dt.replace(tzinfo=timezone.utc)
                    if filing_dt < cutoff:
                        continue
                except Exception:
                    # If we can't parse the date, skip rather than include stale data
                    continue

            # ── Find filing index link ────────────────────────────────────
            index_url = None
            for link_el in entry.findall('atom:link', ns):
                href = link_el.get('href', '')
                if href and ('/Archives/' in href or 'action=getcompany' not in href):
                    index_url = href
                    break

            if not index_url:
                continue

            # ── Fetch filing index page ───────────────────────────────────
            time.sleep(_EDGAR_SLEEP)
            try:
                idx_resp = session.get(index_url, timeout=15)
            except Exception as e:
                log.debug(f'[INS] {ticker}: index fetch error — {e}')
                continue

            if not idx_resp.ok:
                continue

            # ── Discover Form 4 XML URL ───────────────────────────────────
            xml_url = None
            # Parse index HTML looking for .xml links
            idx_text = idx_resp.text
            import re
            # Find all hrefs ending in .xml
            xml_hrefs = re.findall(r'href=["\']([^"\']+\.xml)["\']', idx_text, re.IGNORECASE)
            for href in xml_hrefs:
                fname = href.split('/')[-1].lower()
                if 'form4' in fname or '4' in fname:
                    # Prefer filenames containing "form4"
                    xml_url = href if href.startswith('http') else f'https://www.sec.gov{href}'
                    break
            if not xml_url and xml_hrefs:
                # Fallback: first .xml link
                href = xml_hrefs[0]
                xml_url = href if href.startswith('http') else f'https://www.sec.gov{href}'

            if not xml_url:
                continue

            # ── Fetch and parse Form 4 XML ────────────────────────────────
            time.sleep(_EDGAR_SLEEP)
            try:
                xml_resp = session.get(xml_url, timeout=15)
            except Exception as e:
                log.debug(f'[INS] {ticker}: xml fetch error — {e}')
                continue

            if not xml_resp.ok:
                continue

            try:
                xml_root = ET.fromstring(xml_resp.content)
            except ET.ParseError:
                continue

            # ── Extract transactions ──────────────────────────────────────
            for txn in xml_root.findall('.//nonDerivativeTransaction'):
                try:
                    shares_el = txn.find('./transactionAmounts/transactionShares/value')
                    price_el  = txn.find('./transactionAmounts/transactionPricePerShare/value')
                    code_el   = txn.find('./transactionAmounts/transactionAcquiredDisposedCode/value')

                    if shares_el is None or code_el is None:
                        continue

                    shares = float(shares_el.text.strip()) if shares_el.text else 0.0
                    price  = float(price_el.text.strip())  if (price_el is not None and price_el.text) else 0.0
                    code   = code_el.text.strip().upper()  if code_el.text else ''

                    value = shares * price

                    if code == 'A':
                        total_bought += value
                    elif code == 'D':
                        total_sold += value
                except (ValueError, AttributeError):
                    continue

            filings_parsed += 1

        log.info(f'[INS] {ticker}: parsed {filings_parsed} filings — bought=${total_bought:,.0f} sold=${total_sold:,.0f}')

        # ── Signal classification ─────────────────────────────────────────
        if total_bought == 0.0 and total_sold == 0.0:
            return {'insider_signal': 'NEUTRAL', 'insider_note': 'No significant insider activity'}

        if total_bought > total_sold * 1.5:
            return {
                'insider_signal': 'ACCUMULATING',
                'insider_note':   'Net insider buying over 90 days',
            }
        elif total_sold > total_bought * 1.5:
            return {
                'insider_signal': 'DISTRIBUTING',
                'insider_note':   'Net insider selling over 90 days',
            }
        else:
            return {
                'insider_signal': 'NEUTRAL',
                'insider_note':   'No significant insider activity',
            }

    except Exception as e:
        log.warning(f'[INS] {ticker}: unexpected error — {e}')
        return _unavail