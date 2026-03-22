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
from reports.commodity_signal import get_commodity_signal
from reports.sentence_templates import (
    render_financial_health,
    render_moderate_risk_block,
    render_market_pulse_line,
    render_price_line,
    render_event_plain,
    render_sector_plain,
    confidence_label,
    risk_section,
    debt_label,
    roic_label,
    fcf_direction_label,
    score_meaning,
    summary_verdict,
    TODAY_STORY_SENTENCE,
    TODAY_STORY_SENTENCE_SIGNALS,
    EARNINGS_WARNING,
    EARNINGS_WARNING_IMMINENT,
    DIVERGENCE_WARNING,
    UNUSUAL_VOLUME_NOTE,
    DRAWDOWN_NOTE,
    VOLUME_LINE,
    CONFIDENCE_LINE,
    DIRECTION_PLAIN,
    TREND_LINE_FULL,
    TREND_LINE_PARTIAL,
    FINANCIAL_HEALTH_EXTENDED,
    CONFIDENCE_BREAKDOWN,
    SUMMARY_SCORE_LINE,
    COMPANY_INTRO_SECTOR_LEADER,
    COMPANY_INTRO_MOMENTUM,
    COMPANY_INTRO_FUNDAMENTALS,
    COMPANY_INTRO_STANDARD,
)
from contracts.eq_schema import (
    EQ_AVAILABLE, EQ_SCORE_FINAL, EQ_LABEL, PASS_TIER,
    TOP_RISKS, TOP_STRENGTHS, WARNINGS, FATAL_FLAW_REASON,
    EQ_PERCENTILE, BATCH_REGIME, EQ_SCORE_DISPLAY,
    EQ_LABEL_DISPLAY, EQ_VERDICT_DISPLAY, EQ_TOP_RISKS_DISPLAY,
    EQ_TOP_STRENGTHS_DISPLAY, EQ_WARNINGS_DISPLAY,
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
    Generates plain English sentences describing today's market story.
    Uses signal count and sector score when no specific event type is matched.
    """
    sentences = []
    seen_sectors = set()

    for sector in confirmed_sectors[:3]:
        if sector in seen_sectors:
            continue
        seen_sectors.add(sector)
        score_data      = sector_scores.get(sector, {})
        score_val       = score_data.get('score', 0)
        direction       = 'positive' if score_val >= 0 else 'negative'
        direction_plain = DIRECTION_PLAIN.get(direction, 'moving')
        sector_plain    = render_sector_plain(sector)

        # Count articles that mention this sector
        sector_keyword = sector.replace('_', ' ')
        signal_count = sum(
            1 for a in all_articles
            if sector_keyword in (a.get('title', '') + ' ' + a.get('summary', '')).lower()
            or sector in (a.get('title', '') + ' ' + a.get('summary', '')).lower()
        )

        # Use signal-count variant when we have meaningful data, fallback otherwise
        if signal_count >= 2 and score_val > 0:
            sentences.append(TODAY_STORY_SENTENCE_SIGNALS.format(
                SECTOR_PLAIN    = sector_plain,
                DIRECTION_PLAIN = direction_plain,
                SIGNAL_COUNT    = signal_count,
                SECTOR_SCORE    = score_val,
            ))
        else:
            sentences.append(TODAY_STORY_SENTENCE.format(
                SECTOR_PLAIN    = sector_plain,
                DIRECTION_PLAIN = direction_plain,
                EVENT_PLAIN     = 'positive sector news signals',
            ))

    if not sentences:
        sentences.append(
            'Market conditions were monitored across all sectors today. '
            'See company details below for specific research opportunities.'
        )
    return sentences


def _build_eq_display(c: dict) -> dict:
    """
    Builds display-ready EQ fields from raw EQ data on the candidate dict.
    System 1 owns all EQ rendering. System 2 never produces HTML for System 1.
    Returns safe fallback display values when EQ data is unavailable.
    """
    if not c.get(EQ_AVAILABLE):
        return {
            EQ_SCORE_DISPLAY:         'N/A',
            EQ_LABEL_DISPLAY:         'No earnings data',
            EQ_VERDICT_DISPLAY:       'EQ analysis unavailable for this ticker',
            EQ_TOP_RISKS_DISPLAY:     [],
            EQ_TOP_STRENGTHS_DISPLAY: [],
            EQ_WARNINGS_DISPLAY:      [],
        }

    eq_score   = c.get(EQ_SCORE_FINAL, 0)
    eq_label   = c.get(EQ_LABEL, '')
    pass_tier  = c.get(PASS_TIER, '')
    risks      = c.get(TOP_RISKS, [])
    strengths  = c.get(TOP_STRENGTHS, [])
    warnings   = c.get(WARNINGS, [])
    fatal      = c.get(FATAL_FLAW_REASON, '')
    percentile = c.get(EQ_PERCENTILE, 0)
    batch      = c.get(BATCH_REGIME, '')

    score_display = f'{int(eq_score)}/100'
    label_display = eq_label if eq_label else 'Unknown'

    if fatal:
        verdict = f'FATAL FLAW: {fatal}'
    elif pass_tier == 'PASS':
        verdict = f'Earnings quality PASS — {percentile}th percentile in batch ({batch})'
    elif pass_tier == 'WATCH':
        verdict = 'Earnings quality WATCH — monitor closely'
    else:
        verdict = f'Earnings quality FAIL — {eq_label}'

    warning_strings = []
    for w in warnings[:3]:
        if isinstance(w, dict):
            warning_strings.append(w.get('message', str(w)))
        else:
            warning_strings.append(str(w))

    return {
        EQ_SCORE_DISPLAY:         score_display,
        EQ_LABEL_DISPLAY:         label_display,
        EQ_VERDICT_DISPLAY:       verdict,
        EQ_TOP_RISKS_DISPLAY:     risks[:3],
        EQ_TOP_STRENGTHS_DISPLAY: strengths[:3],
        EQ_WARNINGS_DISPLAY:      warning_strings,
    }


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

    # Company intro — variant selected by per-company signals
    company_name     = c.get('company_name', c.get('ticker', ''))
    sector_plain_str = render_sector_plain(sector)
    final_rank       = c.get('final_rank', 99)
    conf_score_v     = c.get('composite_confidence', 0)
    opp_score_v      = c.get('opportunity_score', 0)

    if final_rank == 1:
        intro = COMPANY_INTRO_SECTOR_LEADER.format(
            COMPANY = company_name,
            SECTOR  = sector_plain_str,
        )
    elif opp_score_v >= 70 and conf_score_v >= 65:
        intro = COMPANY_INTRO_FUNDAMENTALS.format(
            COMPANY = company_name,
            SECTOR  = sector_plain_str,
        )
    elif c.get('ram', {}).get('raw_value', 0) and c.get('ram', {}).get('raw_value', 0) > 1:
        intro = COMPANY_INTRO_MOMENTUM.format(
            COMPANY = company_name,
            SECTOR  = sector_plain_str,
        )
    else:
        intro = COMPANY_INTRO_STANDARD.format(
            COMPANY   = company_name,
            SECTOR    = sector_plain_str,
            DIRECTION = DIRECTION_PLAIN.get(direction, 'moving'),
        )

    # ── §FIX-2: Trend line with actual timeframe data ───────────────────────
    ram_label = ram.get('label', 'no trend data')
    mtf       = c.get('mtf', {})
    r1m       = mtf.get('r1m')
    r3m       = mtf.get('r3m')
    r6m       = mtf.get('r6m')

    def _fmt_ret(v):
        if v is None: return 'n/a'
        if v > 0:   return f'\u25b2{v:.1f}%'
        if v < 0:   return f'\u25bc{abs(v):.1f}%'
        return '\u20130.0%'   # flat — neither up nor down arrow

    if r1m is not None and r3m is not None and r6m is not None:
        trend_label = TREND_LINE_FULL.format(
            RAM_LABEL = ram_label,
            R1M       = _fmt_ret(r1m),
            R3M       = _fmt_ret(r3m),
            R6M       = _fmt_ret(r6m),
        )
    elif r3m is not None:
        trend_label = TREND_LINE_PARTIAL.format(
            RAM_LABEL = ram_label,
            R3M       = _fmt_ret(r3m),
        )
    else:
        trend_label = ram_label

    momentum_label = mtf.get('label', 'no clear direction')

    # ── §FIX-3: Extended financial health ───────────────────────────────────
    margin_pct  = fin.get('profit_margin')
    de_ratio    = fin.get('debt_to_equity')
    fin_health  = render_financial_health(margin_pct, de_ratio)

    # Extended financial health — use verified key names from financial_parser.py
    # financial_parser.py confirmed output keys: operating_cash_flow, profit_margin,
    # debt_to_equity, revenue_ttm, net_income_ttm, eps_ttm, beta, pe_ratio
    # NOTE: ROIC is NOT returned by financial_parser.py — it is not in the dict.
    # Compute a proxy from available data if possible, otherwise skip.
    ocf_val  = fin.get('operating_cash_flow')   # operating cash flow (confirmed key)

    # ROIC proxy: not directly available. Use opportunity_model output if present.
    roic_val = c.get('roic_proxy')   # set by opportunity_model if computed, else None

    # FCF proxy: operating_cash_flow is the closest available free-tier equivalent
    fcf_val  = ocf_val

    if margin_pct is not None and fcf_val is not None:
        fin_health = FINANCIAL_HEALTH_EXTENDED.format(
            MARGIN_PCT = f'{margin_pct:.0f}',
            DEBT_LABEL = debt_label(de_ratio),
            ROIC       = roic_label(roic_val),
            FCF_LABEL  = fcf_direction_label(fcf_val),
        )
    # If operating_cash_flow also unavailable, fin_health stays as set by
    # render_financial_health() above — do not override it.

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

    # ── §FIX-3: Confidence breakdown line ───────────────────────────────────
    agr_raw  = c.get('signal_agreement', {}).get('agreement_score', 0)
    agr_int  = int(agr_raw * 100)   # scaled to 0-100 for display only
    # agr_raw stays in 0-1 range for threshold checks below in §FIX-4
    conf_line = CONFIDENCE_BREAKDOWN.format(
        CONFIDENCE_LABEL = conf_lbl,
        CONFIDENCE_SCORE = int(conf_score),
        RISK_INT         = int(risk_score),
        OPP_INT          = int(c.get('opportunity_score', 0)),
        AGR_INT          = agr_int,
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

    # ── §FIX-4: Summary block ────────────────────────────────────────────
    summary_score_line = SUMMARY_SCORE_LINE.format(
        SCORE         = int(conf_score),
        SCORE_MEANING = score_meaning(int(conf_score)),
    )

    summary_positives = []
    # ram dict confirmed keys from risk_adjusted_momentum.py:
    # ram_score, raw_value, return_3m, volatility, label
    ram_raw = ram.get('raw_value')   # float or None — always use .get(), never bracket
    if ram_raw is not None and ram_raw > 1:
        summary_positives.append(f'[+] {ram_label}')
    if c.get('opportunity_score', 0) > 60:
        summary_positives.append('[+] Strong fundamental and momentum signals')
    elif fin.get('profit_margin', 0) > 20:
        # use .get() with default — profit_margin may be None
        pm = fin.get('profit_margin', 0)
        if pm:
            summary_positives.append(f'[+] Solid profit margin ({pm:.0f}%)')
    if agr_raw > 0.25:   # agr_raw is 0-1 scale — 0.25 means 25% agreement strength
        summary_positives.append('[+] Multiple independent signals aligned')

    summary_risks = []
    dd_pct_val = dd.get('drawdown_pct')
    if dd_pct_val and dd_pct_val > 20:
        summary_risks.append(f'[-] {dd_pct_val:.0f}% below 90-day high')
    if de_ratio and de_ratio > 1.5:
        summary_risks.append('[-] Elevated debt for this sector')
    if c.get('risk_score', 0) > 50:
        summary_risks.append('[-] Risk score above moderate threshold')
    vol_ratio = ev.get('volume_ratio')
    if vol_ratio is not None and vol_ratio < 0.8:
        summary_risks.append('[-] Lower trading activity than usual')

    summary_verdict_val = summary_verdict(conf_score, risk_score, section)

    # ── EQ display enrichment ─────────────────────────────────────────────
    eq_display = _build_eq_display(c)

    return {
        **c,              # original candidate data first
        **eq_display,     # EQ display fields second — these win on collision
        'display_name':      company_name,
        'sector_plain':      render_sector_plain(sector),
        'industry_label':    c.get('financials', {}).get('industry', ''),
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
        'summary_score_line': summary_score_line,
        'summary_positives':  summary_positives[:2],
        'summary_risks':      summary_risks[:2],
        'summary_verdict':    summary_verdict_val,
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

    # ── Commodity signal (Energy context, narrative only) ─────────────────
    commodity_summary = ''
    if any(c.get('sector') == 'energy' for c in companies):
        commodity_data    = get_commodity_signal()
        commodity_summary = commodity_data.get('summary', '')

        # Interpretation: flag mismatch between commodity trend and candidate industries
        if commodity_summary:
            industries_present = [
                c.get('financials', {}).get('industry', '').lower()
                for c in companies if c.get('sector') == 'energy'
            ]
            gas_producers_present = any(
                'gas' in ind for ind in industries_present
            )
            oil_producers_present = any(
                'oil' in ind or 'exploration' in ind or 'crude' in ind
                for ind in industries_present
            )

            interpretation = ''
            if gas_producers_present and commodity_data.get('gas_trend') == 'negative':
                interpretation = (
                    'Note: natural gas prices are declining — '
                    'gas producer strength may reflect sector rotation rather than commodity support.'
                )
            elif oil_producers_present and commodity_data.get('crude_trend') == 'negative':
                interpretation = (
                    'Note: WTI crude is declining — '
                    'oil producer strength may reflect sector rotation rather than commodity support.'
                )

            if interpretation:
                commodity_summary += ' ' + interpretation

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
            commodity_summary = commodity_summary,
        )
        email_path = os.path.join(OUTPUT_DIR, f'intraday_email_{slot.replace(":", "").replace("-", "_")}_{ts_str}.html')
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
            commodity_summary = commodity_summary,
        )
        full_path = os.path.join(OUTPUT_DIR, f'intraday_full_{slot.replace(":", "").replace("-", "_")}_{ts_str}.html')
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
    path = os.path.join(OUTPUT_DIR, f'fallback_{slot.replace(":", "").replace("-", "_")}_{ts_str}.html')
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
