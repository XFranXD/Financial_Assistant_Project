"""
reports/summary_builder.py — §23 File 4
build_closing_report() — called by main.py step 30 for the 16:10 closing slot.

Generates closing HTML files (email + full browser).
Structure: market summary → what moved today → full ranked list → watch tomorrow.

DISCLAIMER: This system does NOT perform trading, does NOT give investment advice,
and does NOT make price predictions. It is a research data aggregation and scoring
tool only.
"""

import os
from datetime import datetime

import pytz
from jinja2 import Environment, FileSystemLoader, select_autoescape

from utils.logger import get_logger
from reports.sentence_templates import (
    render_market_pulse_line,
    render_sector_plain,
    render_event_plain,
    render_price_line,
    confidence_label,
    CLOSING_WATCH_EARNINGS,
    CLOSING_WATCH_ROTATION,
    CLOSING_FULL_RANKED_ROW,
    DIRECTION_ARROW,
)
from reports.commodity_signal import get_commodity_signal

log = get_logger('summary_builder')

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')
OUTPUT_DIR    = os.path.join(os.path.dirname(__file__), 'output')
TIMEZONE      = 'America/New_York'

DISCLAIMER = (
    'DISCLAIMER: This system does NOT perform trading, does NOT give investment advice, '
    'and does NOT make price predictions. It is a research data aggregation and scoring tool only.'
)


def _get_jinja_env() -> Environment:
    return Environment(
        loader        = FileSystemLoader(TEMPLATES_DIR),
        autoescape    = select_autoescape(['html']),
        trim_blocks   = True,
        lstrip_blocks = True,
    )


def _build_market_close_summary(indices: dict) -> list[dict]:
    """
    Returns list of dicts for each index with display fields.
    One per index: Dow, S&P 500, Nasdaq.
    """
    label_map = {
        'dow':    'Dow Jones',
        'sp500':  'S&P 500',
        'nasdaq': 'Nasdaq',
    }
    result = []
    for key, display in label_map.items():
        data      = indices.get(key, {})
        value     = data.get('value')
        chg_pct   = data.get('change_pct')
        lbl       = data.get('label', 'unavailable')
        arrow     = DIRECTION_ARROW.get(lbl, '–')
        pulse_str = render_market_pulse_line(display, data)

        # One plain English sentence per index
        if lbl == 'Rising':
            sentence = f'The {display} closed higher, gaining {abs(chg_pct or 0):.1f}% on the day.'
        elif lbl == 'Falling':
            sentence = f'The {display} closed lower, declining {abs(chg_pct or 0):.1f}% on the day.'
        elif lbl == 'Flat':
            sentence = f'The {display} ended the day little changed.'
        else:
            sentence = f'The {display} closing value is not available for this run.'

        result.append({
            'name':      display,
            'pulse_str': pulse_str,
            'sentence':  sentence,
            'value':     value,
            'change_pct': chg_pct,
            'label':     lbl,
            'arrow':     arrow,
        })
    return result


def _build_what_moved_today(state: dict, sector_scores: dict) -> list[str]:
    """
    Returns 3-5 plain English sentences summarising what moved the market.
    Reads event_scores_today from state and sector scores.
    """
    sentences = []

    event_scores = state.get('event_scores_today', {})
    # Top sectors by momentum score, descending
    top_sectors = sorted(
        sector_scores.items(),
        key=lambda x: x[1].get('score', 0),
        reverse=True,
    )[:4]

    for sector, sdata in top_sectors:
        score    = sdata.get('score', 0)
        if score < 0.1:
            continue
        direction_word = 'rising' if score >= 0 else 'declining'
        sector_plain   = render_sector_plain(sector)
        sentences.append(
            f'{sector_plain} stocks were among the {direction_word} groups today, '
            f'with sector momentum at {score:.1f} points.'
        )

    # Add a sentence about unusual volume flags if any
    uv_flags = state.get('unusual_volume_flags', [])
    if uv_flags:
        count = len(uv_flags)
        sentences.append(
            f'{count} stock{"s" if count != 1 else ""} showed unusually high trading volume today '
            f'— {", ".join(uv_flags[:3])}{"..." if count > 3 else ""}.'
        )

    if not sentences:
        sentences.append(
            'No dominant sector movements were detected in today\'s data. '
            'Markets appeared to trade without a clear directional theme.'
        )

    # Commodity signal — append if Energy was active today
    reported = state.get('reported_companies', [])
    energy_tickers = ['XOM', 'CVX', 'COP', 'DVN', 'EOG', 'EQT', 'CTRA',
                      'RRC', 'AR', 'CNX', 'KMI', 'SM', 'APA']
    energy_reported = any(t in reported for t in energy_tickers)
    if energy_reported:
        try:
            commodity_summary = get_commodity_signal().get('summary', '')
            if commodity_summary:
                sentences.append(commodity_summary)
        except Exception as _ce:
            log.warning(f'commodity_signal in closing report failed: {_ce}')

    return sentences[:5]


def _build_full_ranked_list(state: dict) -> list[str]:
    """
    Builds ranked list rows from all companies reported across all slots today.
    Returns list of formatted strings.
    Note: Only ticker + sector data is available in state. Full financials are not
    re-fetched at closing time — we show what was recorded during intraday runs.
    """
    rows = []
    seen = set()
    rank = 1

    for slot in ['10:30', '12:30', '14:30', '16:10']:
        slot_data = state.get('runs', {}).get(slot, {})
        companies = slot_data.get('companies', [])
        for company_info in companies:
            # companies list may be list of tickers (str) or dicts
            if isinstance(company_info, str):
                ticker = company_info
                if ticker in seen:
                    continue
                seen.add(ticker)
                rows.append(f'{rank}. {ticker} — confidence data not stored (intraday only)')
                rank += 1
            elif isinstance(company_info, dict):
                ticker = company_info.get('ticker', '')
                if ticker in seen:
                    continue
                seen.add(ticker)
                c_label = confidence_label(company_info.get('composite_confidence', 50))
                c_score = company_info.get('composite_confidence', 0)
                sector  = render_sector_plain(company_info.get('sector', ''))
                price   = company_info.get('current_price')
                chg     = company_info.get('price_change_pct')
                arrow   = '▲' if (chg or 0) >= 0 else '▼'
                price_str = f'${price:,.2f}' if price else 'n/a'
                chg_str   = f'{abs(chg or 0):.1f}%' if chg is not None else 'n/a'
                risk_lbl  = 'Low Risk' if company_info.get('risk_score', 50) <= 40 else 'Moderate Risk'
                rows.append(
                    f'{rank}. {company_info.get("company_name", ticker)} ({ticker}) — '
                    f'{sector} — {price_str} {arrow}{chg_str} — '
                    f'Confidence: {c_label} ({int(c_score)}/100) — {risk_lbl}'
                )
                rank += 1

    return rows if rows else ['No companies were reported today.']


def _build_watch_tomorrow(state: dict, rotation: dict) -> list[str]:
    """
    Generates watch-tomorrow items:
    - Earnings warnings for companies in today's list
    - Sectors with accelerating rotation
    """
    items = []

    # Sectors with accelerating rotation
    accelerating = [
        s for s, d in rotation.items()
        if d.get('accelerating', False)
    ]
    for sector in accelerating[:3]:
        rot_label = rotation[sector].get('label', 'gaining momentum')
        items.append(CLOSING_WATCH_ROTATION.format(
            SECTOR_PLAIN  = render_sector_plain(sector),
            ROTATION_LABEL = rot_label,
        ))

    if not items:
        items.append('■ No strong sector rotation signals detected for tomorrow.')
        items.append('■ Monitor upcoming economic calendar for scheduled data releases.')

    return items


def build_closing_report(
    state:         dict,
    indices:       dict,
    sector_scores: dict,
    rotation:      dict,
) -> None:
    """
    Builds closing HTML email + full browser report for the 16:10 slot.
    Writes files to reports/output/ and commits via main.py's git step.
    Returns None (main.py does not use return value).
    Called by main.py step 30.
    """
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        now_utc  = datetime.now(pytz.utc)
        now_et   = now_utc.astimezone(pytz.timezone(TIMEZONE))
        date_str = now_et.strftime('%Y-%m-%d')
        ts_str   = now_utc.strftime('%Y%m%dT%H%M%SZ')

        # ── Build content sections ────────────────────────────────────────
        market_summary  = _build_market_close_summary(indices)
        what_moved      = _build_what_moved_today(state, sector_scores)
        ranked_list     = _build_full_ranked_list(state)
        watch_tomorrow  = _build_watch_tomorrow(state, rotation)

        # Total companies reported today
        reported = state.get('reported_companies', [])
        n_total  = len(reported)
        subject  = f'■ Daily Summary — {date_str} — {n_total} total opportunit{"y" if n_total == 1 else "ies"}'

        env = _get_jinja_env()

        # ── Render closing email HTML ─────────────────────────────────────
        try:
            email_tpl  = env.get_template('closing_email.html')
            email_html = email_tpl.render(
                subject        = subject,
                date_str       = date_str,
                market_summary = market_summary,
                what_moved     = what_moved,
                ranked_list    = ranked_list,
                watch_tomorrow = watch_tomorrow,
                n_total        = n_total,
                disclaimer     = DISCLAIMER,
            )
            email_path = os.path.join(OUTPUT_DIR, f'closing_email_{ts_str}.html')
            with open(email_path, 'w', encoding='utf-8') as f:
                f.write(email_html)
            log.info(f'Closing email written: {email_path}')
        except Exception as e:
            log.error(f'Closing email template failed: {e}')
            _write_fallback_closing(ts_str, date_str, market_summary, what_moved, ranked_list, watch_tomorrow)

        # ── Render closing full browser HTML ──────────────────────────────
        try:
            full_tpl  = env.get_template('closing_full.html')
            full_html = full_tpl.render(
                subject        = subject,
                date_str       = date_str,
                market_summary = market_summary,
                what_moved     = what_moved,
                ranked_list    = ranked_list,
                watch_tomorrow = watch_tomorrow,
                n_total        = n_total,
                rotation       = rotation,
                sector_scores  = sector_scores,
                disclaimer     = DISCLAIMER,
            )
            full_path = os.path.join(OUTPUT_DIR, f'closing_full_{ts_str}.html')
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(full_html)
            log.info(f'Closing full report written: {full_path}')
        except Exception as e:
            log.error(f'Closing full template failed: {e}')

    except Exception as e:
        log.error(f'build_closing_report crashed (non-fatal): {e}')


def _write_fallback_closing(ts_str, date_str, market_summary, what_moved, ranked_list, watch_tomorrow):
    """Minimal plain-HTML fallback for closing report."""
    path = os.path.join(OUTPUT_DIR, f'closing_fallback_{ts_str}.html')
    try:
        lines = [f'<html><body style="font-family:monospace"><h2>Daily Summary — {date_str}</h2>']
        lines.append('<h3>Market Close</h3>')
        for m in market_summary:
            lines.append(f'<p>{m["pulse_str"]}</p><p>{m["sentence"]}</p>')
        lines.append('<h3>What Moved Today</h3>')
        for s in what_moved:
            lines.append(f'<p>{s}</p>')
        lines.append('<h3>Today\'s Full Ranked List</h3>')
        for row in ranked_list:
            lines.append(f'<p>{row}</p>')
        lines.append('<h3>Watch Tomorrow</h3>')
        for w in watch_tomorrow:
            lines.append(f'<p>{w}</p>')
        lines.append(f'<p><em>{DISCLAIMER}</em></p></body></html>')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        log.info(f'Closing fallback written: {path}')
    except Exception as e:
        log.error(f'Closing fallback write failed: {e}')
