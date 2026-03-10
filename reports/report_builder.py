"""
reports/report_builder.py — §23 File 2
build_intraday_report() — called by main.py step 28.

Returns a dict with key 'email' (path to email HTML) and 'full' (path to full HTML).
Uses Jinja2 templates from reports/templates/.
All text goes through sentence_templates.py — no free-text generation.

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
    render_company_intro,
    render_financial_health,
    render_moderate_risk_block,
    render_market_pulse_line,
    render_price_line,
    render_event_plain,
    render_sector_plain,
    confidence_label,
    risk_section,
    TODAY_STORY_SENTENCE,
    EARNINGS_WARNING,
    EARNINGS_WARNING_IMMINENT,
    DIVERGENCE_WARNING,
    UNUSUAL_VOLUME_NOTE,
    DRAWDOWN_NOTE,
    VOLUME_LINE,
    CONFIDENCE_LINE,
    DIRECTION_PLAIN,
)

log = get_logger('report_builder')

TEMPLATES_DIR  = os.path.join(os.path.dirname(__file__), 'templates')
OUTPUT_DIR     = os.path.join(os.path.dirname(__file__), 'output')
EMAIL_MAX      = 7   # max companies in email body
TIMEZONE       = 'America/New_York'

DISCLAIMER = (
    'DISCLAIMER: This system does NOT perform trading, does NOT give investment advice, '
    'and does NOT make price predictions. It is a research data aggregation and scoring tool only.'
)


def _get_jinja_env() -> Environment:
    return Environment(
        loader       = FileSystemLoader(TEMPLATES_DIR),
        autoescape   = select_autoescape(['html']),
        trim_blocks  = True,
        lstrip_blocks= True,
    )


def _build_market_pulse(indices: dict) -> list[str]:
    """Returns 3 formatted market pulse lines (Dow, S&P, Nasdaq)."""
    label_map = {
        'dow':    'Dow Jones ',
        'sp500':  'S&P 500   ',
        'nasdaq': 'Nasdaq    ',
    }
    lines = []
    for key, display in label_map.items():
        data = indices.get(key, {})
        lines.append(render_market_pulse_line(display, data))
    return lines


def _build_story_sentences(all_articles: list, sector_scores: dict, confirmed_sectors: list) -> list[str]:
    """
    Generates 2-3 plain English sentences describing today's market story.
    Uses TODAY_STORY_SENTENCE template. No free text.
    """
    sentences = []
    seen_sectors = set()

    for sector in confirmed_sectors[:3]:
        if sector in seen_sectors:
            continue
        seen_sectors.add(sector)
        score_data  = sector_scores.get(sector, {})
        direction   = 'positive' if score_data.get('score', 0) >= 0 else 'negative'
        # Derive event plain from sector name as best effort
        event_plain = render_event_plain('_unknown')
        # Try to find matching event from articles keywords
        for article in all_articles[:20]:
            text = (article.get('title', '') + ' ' + article.get('summary', '')).lower()
            if sector.replace('_', ' ') in text or sector in text:
                # Use a generic but accurate sentence
                event_plain = 'recent market developments'
                break

        sentences.append(TODAY_STORY_SENTENCE.format(
            SECTOR_PLAIN  = render_sector_plain(sector),
            DIRECTION_PLAIN = DIRECTION_PLAIN.get(direction, 'moving'),
            EVENT_PLAIN   = event_plain,
        ))

    if not sentences:
        sentences.append(
            'Market conditions were monitored across all sectors today. '
            'See company details below for specific research opportunities.'
        )
    return sentences


def _enrich_company_for_template(c: dict) -> dict:
    """
    Adds all display-ready fields to a candidate dict for use in Jinja2 templates.
    All labels and plain English strings computed here — templates do no logic.
    """
    fin        = c.get('financials', {})
    risk_score = c.get('risk_score', 50)
    conf_score = c.get('composite_confidence', 0)
    dd         = c.get('drawdown', {})
    ram        = c.get('ram', {})
    uv         = c.get('unusual_volume', {})
    ev         = c.get('volume_confirmation', {})
    sector     = c.get('sector', '')
    direction  = c.get('sector_data', {}).get('direction', 'positive')

    # Determine primary event type (use first key in sector events if available)
    event_type = c.get('sector_data', {}).get('primary_event', '_unknown')

    # Price line
    price     = c.get('current_price') or fin.get('current_price')
    change_pct = fin.get('price_change_pct')
    price_line = render_price_line(price, change_pct)

    # Company intro
    company_name = c.get('company_name', c.get('ticker', ''))
    intro = render_company_intro(company_name, sector, direction, event_type)

    # Trend sentence — use RAM and MTF labels
    trend_label = ram.get('label', 'trending')
    momentum_label = c.get('mtf', {}).get('label', 'no clear direction')

    # Financial health
    margin_pct  = fin.get('profit_margin')
    de_ratio    = fin.get('debt_to_equity')
    fin_health  = render_financial_health(margin_pct, de_ratio)

    # Risk section
    section     = risk_section(risk_score)
    conf_lbl    = confidence_label(conf_score)

    # Moderate risk explanation (only for MODERATE RISK companies)
    mod_risk_text = ''
    if section == 'MODERATE RISK':
        risk_comps = c.get('risk_components', {})
        dd_pct     = dd.get('drawdown_pct')
        mod_risk_text = render_moderate_risk_block(risk_comps, risk_score, dd_pct)

    # Volume line
    vol_label  = ev.get('label', 'normal trading activity')
    volume_line = VOLUME_LINE.format(VOLUME_LABEL=vol_label.capitalize())

    # Confidence line
    conf_line = CONFIDENCE_LINE.format(
        CONFIDENCE_LABEL=conf_lbl,
        CONFIDENCE_SCORE=int(conf_score),
    )

    # Optional notice lines (earnings, divergence, unusual volume, drawdown)
    notices = []
    if c.get('earnings_warning'):
        days = fin.get('earnings_days', 5)
        if days <= 1:
            notices.append(EARNINGS_WARNING_IMMINENT)
        else:
            notices.append(EARNINGS_WARNING.format(DAYS=int(days)))

    if c.get('divergence_warning'):
        notices.append(DIVERGENCE_WARNING)

    if uv.get('unusual_flag'):
        notices.append(UNUSUAL_VOLUME_NOTE.format(
            UNUSUAL_LABEL=uv.get('label', 'unusually high trading volume').capitalize(),
        ))

    dd_pct = dd.get('drawdown_pct')
    if dd_pct is not None and dd_pct > 20:
        notices.append(DRAWDOWN_NOTE.format(DRAWDOWN_PCT=f'{dd_pct:.0f}'))

    return {
        **c,
        'display_name':      company_name,
        'sector_plain':      render_sector_plain(sector),
        'intro_sentence':    intro,
        'trend_label':       trend_label,
        'momentum_label':    momentum_label,
        'financial_health':  fin_health,
        'volume_line':       volume_line,
        'confidence_line':   conf_line,
        'price_line':        price_line,
        'section':           section,
        'confidence_label':  conf_lbl,
        'conf_score_int':    int(conf_score),
        'moderate_risk_text': mod_risk_text,
        'notices':           notices,
        'risk_score_int':    int(risk_score),
    }


def build_intraday_report(
    companies:     list,
    slot:          str,
    indices:       dict,
    breadth:       dict,
    regime:        dict,
    all_articles:  list,
    sector_scores: dict,
    rotation:      dict,
) -> dict:
    """
    Builds intraday report HTML files (email + full browser).
    Returns dict: {'email': str path, 'full': str path}
    Called by main.py step 28.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    now_utc  = datetime.now(pytz.utc)
    now_et   = now_utc.astimezone(pytz.timezone('America/New_York'))
    date_str = now_et.strftime('%Y-%m-%d')
    time_str = now_et.strftime('%H:%M ET')
    ts_str   = now_utc.strftime('%Y%m%dT%H%M%SZ')

    # ── Market pulse block ────────────────────────────────────────────────
    pulse_lines = _build_market_pulse(indices)

    # ── Story sentences ───────────────────────────────────────────────────
    confirmed_sectors = list({c['sector'] for c in companies})
    story_sentences   = _build_story_sentences(all_articles, sector_scores, confirmed_sectors)

    # ── Enrich all companies with display fields ──────────────────────────
    enriched = [_enrich_company_for_template(c) for c in companies]

    # ── Split into email (top 7) and overflow ─────────────────────────────
    email_companies    = enriched[:EMAIL_MAX]
    overflow_companies = enriched[EMAIL_MAX:]

    # ── Partition into LOW RISK / MODERATE RISK buckets ──────────────────
    def partition(lst):
        low  = [c for c in lst if c['section'] == 'LOW RISK']
        mod  = [c for c in lst if c['section'] == 'MODERATE RISK']
        return low, mod

    email_low, email_mod = partition(email_companies)
    full_low, full_mod   = partition(enriched)

    # Subject line
    n_found = len(companies)
    subject = f'■ Stock Research — {slot} Update — {n_found} opportunit{"y" if n_found == 1 else "ies"} found'

    # Overflow notice
    overflow_count   = len(overflow_companies)
    overflow_notice  = f'+ {overflow_count} more companies found today. View full report: [LINK]' if overflow_count else ''

    env = _get_jinja_env()

    # ── Render email HTML ─────────────────────────────────────────────────
    try:
        email_tpl = env.get_template('intraday_email.html')
        email_html = email_tpl.render(
            subject          = subject,
            slot             = slot,
            date_str         = date_str,
            time_str         = time_str,
            pulse_lines      = pulse_lines,
            story_sentences  = story_sentences,
            low_risk         = email_low,
            moderate_risk    = email_mod,
            overflow_notice  = overflow_notice,
            regime_label     = regime.get('label', 'Normal market'),
            breadth_label    = breadth.get('label', 'neutral'),
            disclaimer       = DISCLAIMER,
            total_companies  = n_found,
        )
        email_path = os.path.join(OUTPUT_DIR, f'intraday_email_{slot.replace(":", "")}_{ts_str}.html')
        with open(email_path, 'w', encoding='utf-8') as f:
            f.write(email_html)
        log.info(f'Email report written: {email_path}')
    except Exception as e:
        log.error(f'Failed to render email template: {e}')
        email_path = _write_fallback_email(slot, ts_str, pulse_lines, story_sentences, enriched)

    # ── Render full browser HTML ──────────────────────────────────────────
    try:
        full_tpl  = env.get_template('intraday_full.html')
        full_html = full_tpl.render(
            subject          = subject,
            slot             = slot,
            date_str         = date_str,
            time_str         = time_str,
            pulse_lines      = pulse_lines,
            story_sentences  = story_sentences,
            low_risk         = full_low,
            moderate_risk    = full_mod,
            regime_label     = regime.get('label', 'Normal market'),
            breadth_label    = breadth.get('label', 'neutral'),
            disclaimer       = DISCLAIMER,
            total_companies  = n_found,
            rotation         = rotation,
        )
        full_path = os.path.join(OUTPUT_DIR, f'intraday_full_{slot.replace(":", "")}_{ts_str}.html')
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        log.info(f'Full report written: {full_path}')
    except Exception as e:
        log.error(f'Failed to render full template: {e}')
        full_path = email_path   # fallback: same file

    return {'email': email_path, 'full': full_path}


def _write_fallback_email(slot, ts_str, pulse_lines, story_sentences, companies) -> str:
    """
    Minimal plain-HTML fallback if Jinja2 template fails.
    Never raises — always returns a valid path.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f'fallback_{slot.replace(":", "")}_{ts_str}.html')
    try:
        lines = [
            '<html><body style="font-family:monospace">',
            f'<h2>Stock Research — {slot}</h2>',
            '<h3>Market Pulse</h3>',
        ]
        for pl in pulse_lines:
            lines.append(f'<p>{pl}</p>')
        for s in story_sentences:
            lines.append(f'<p>{s}</p>')
        lines.append('<h3>Opportunities</h3>')
        for c in companies:
            lines.append(f'<p><b>{c.get("display_name", c.get("ticker"))} ({c.get("ticker")})</b> '
                         f'— {c.get("sector_plain")} — {c.get("confidence_line")}</p>')
        lines.append(f'<p><em>{DISCLAIMER}</em></p>')
        lines.append('</body></html>')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    except Exception as e:
        log.error(f'Fallback email write failed: {e}')
    return path
