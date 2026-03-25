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
from contracts.sector_schema import (
    ROTATION_AVAILABLE, ROTATION_SCORE, ROTATION_STATUS,
    ROTATION_SIGNAL, SECTOR_ETF, ROTATION_CONFIDENCE,
    ROTATION_REASONING, ROTATION_SCORE_DISPLAY,
    ROTATION_SIGNAL_DISPLAY, ROTATION_ETF_DISPLAY
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

# ── Signal strength thresholds ─────────────────────────────────────────────
# Used by combined reading logic. Locked — do not change without updating
# the combined reading rules below.
SIGNAL_STRONG   = 70   # confidence >= 70
SIGNAL_MODERATE = 50   # confidence 50-69
# confidence < 50 = WEAK signal

# ── EQ verdict vocabu# No lary ──────────────────────────────────────────────────
# Controlled vocabulary only. Maps directly from pass_tier.
# Fatal flaw overrides pass_tier and always produces RISKY.
# No other logic overrides this mapping.
#   PASS        → SUPPORTIVE
#   WATCH       → NEUTRAL
#   FAIL        → WEAK
#   fatal flaw  → RISKY
#   no data     → UNAVAILABLE


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

        sector_keyword = sector.replace('_', ' ')
        signal_count = sum(
            1 for a in all_articles
            if sector_keyword in (a.get('title', '') + ' ' + a.get('summary', '')).lower()
            or sector in (a.get('title', '') + ' ' + a.get('summary', '')).lower()
        )

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


def _signal_strength_label(conf_score: float) -> str:
    """
    Returns signal strength label based on locked thresholds.
    STRONG >= 70 | MODERATE 50-69 | WEAK < 50
    """
    if conf_score >= SIGNAL_STRONG:
        return 'STRONG'
    elif conf_score >= SIGNAL_MODERATE:
        return 'MODERATE'
    return 'WEAK'


def _eq_verdict_from_tier(pass_tier: str, fatal: str) -> str:
    """
    Maps EQ pass tier to controlled vocabulary verdict.
    Fatal flaw always overrides pass tier → RISKY.
    Warnings do NOT affect verdict — they belong in details only.

    Vocabulary:
      SUPPORTIVE  — PASS tier
      NEUTRAL     — WATCH tier
      WEAK        — FAIL tier
      RISKY       — fatal flaw present (overrides tier)
      UNAVAILABLE — no EQ data
    """
    if fatal:
        return 'RISKY'
    tier = pass_tier.upper() if pass_tier else ''
    if tier == 'PASS':
        return 'SUPPORTIVE'
    elif tier == 'WATCH':
        return 'NEUTRAL'
    elif tier == 'FAIL':
        return 'WEAK'
    return 'UNAVAILABLE'


def _alignment_state(market_verdict: str, eq_verdict: str,
                     eq_available: bool,
                     rotation_signal: str = 'UNKNOWN') -> str:
    """
    Deterministic alignment state across System 1, System 2, and System 3.

    Three-dimensional alignment logic:
      market    → +1 if RESEARCH NOW / -1 if SKIP / 0 otherwise
      earnings  → +1 if SUPPORTIVE / -1 if WEAK or RISKY / 0 otherwise
      rotation  → +1 if SUPPORT / -1 if WEAKEN / 0 if WAIT or UNKNOWN

    Final label:
      >= 2  → ALIGNED
      0–1   → PARTIAL
      < 0   → CONFLICT
    """
    alignment_score = 0

    mv = market_verdict.upper() if market_verdict else ''
    if mv == 'RESEARCH NOW':
        alignment_score += 1
    elif mv == 'SKIP':
        alignment_score -= 1

    if eq_available and eq_verdict not in ('UNAVAILABLE', ''):
        ev = eq_verdict.upper()
        if ev == 'SUPPORTIVE':
            alignment_score += 1
        elif ev in ('WEAK', 'RISKY'):
            alignment_score -= 1

    rs = rotation_signal.upper() if rotation_signal else 'UNKNOWN'
    if rs == 'SUPPORT':
        alignment_score += 1
    elif rs == 'WEAKEN':
        alignment_score -= 1

    if alignment_score >= 2:
        return 'ALIGNED'
    elif alignment_score >= 0:
        return 'PARTIAL'
    else:
        return 'CONFLICT'


def _build_combined_reading(conf_score: float, pass_tier: str,
                            eq_available: bool, fatal: str,
                            market_verdict: str = '',
                            rotation_signal: str = 'UNKNOWN',
                            rotation_available: bool = False) -> dict:
    """
    Deterministic combined reading of System 1, System 2, and System 3.
    Returns a structured dict for template rendering.
    Controls AI interpretation — no inference required.

    Output keys:
      market_line    — Market classification line
      earnings_line  — Earnings classification line
      rotation_line  — Rotation timing line
      alignment      — ALIGNED / PARTIAL / CONFLICT
      conclusion     — Final declarative conclusion sentence

    Conclusion rules (market is gatekeeper, rotation is modifier only):
      RESEARCH NOW + SUPPORT  → proactive
      WATCH + SUPPORT         → favorable timing but needs confirmation
      SKIP + SUPPORT          → hard block — rotation cannot override SKIP
      WATCH + WEAKEN          → not actionable
      WAIT always appears in conclusion — never silent
      "requires caution" banned — replaced with explicit action status
      Every non-actionable conclusion ends with "— not actionable"
    """
    signal     = _signal_strength_label(conf_score)
    eq_verdict = _eq_verdict_from_tier(pass_tier, fatal) if eq_available else 'UNAVAILABLE'
    rs         = rotation_signal.upper() if rotation_signal else 'UNKNOWN'
    mv         = market_verdict.upper() if market_verdict else ''
    alignment  = _alignment_state(market_verdict, eq_verdict, eq_available, rs)

    mv_display    = market_verdict.upper() if market_verdict else signal
    market_line   = f'Market:    {mv_display} ({int(conf_score)}/100)'
    earnings_line = f'Earnings:  {eq_verdict}'
    rotation_line = f'Rotation:  {rs}'

    # ── No EQ data branch ─────────────────────────────────────────────────
    if not eq_available and not rotation_available:
        conclusion = 'Conclusion: No fundamental or timing validation available — not actionable.'

    elif not eq_available and rs == 'SUPPORT':
        if mv == 'RESEARCH NOW':
            conclusion = 'Conclusion: Sector timing supports acting. No fundamental validation available.'
        elif mv == 'SKIP':
            conclusion = 'Conclusion: Sector timing is favorable but market signal is weak — insufficient basis to act.'
        else:
            # WATCH or unset
            conclusion = 'Conclusion: Sector timing is favorable but fundamental data is unavailable — not actionable.'
            
    elif not eq_available and rs == 'WAIT':
        conclusion = 'Conclusion: No fundamental validation and sector timing is not favorable — not actionable.'

    elif not eq_available and rs == 'WEAKEN':
        if mv == 'WATCH':
            conclusion = 'Conclusion: Weak signal and unfavorable sector timing — not actionable.'
        else:
            conclusion = 'Conclusion: Sector timing weakens this setup. No fundamental validation available — not actionable.'

    elif not eq_available:
        # UNKNOWN rotation
        conclusion = 'Conclusion: No fundamental validation available — not actionable.'

    # ── EQ data present branch ─────────────────────────────────────────────
    elif fatal:
        conclusion = 'Conclusion: Fatal flaw in earnings structure. Avoid.'

    elif alignment == 'ALIGNED':
        if mv == 'RESEARCH NOW':
            conclusion = 'Conclusion: Signal supported by fundamentals and sector timing. Highest priority candidate.'
        else:
            conclusion = 'Conclusion: High-quality setup — fundamentals and sector timing aligned, but market signal unconfirmed — monitor for confirmation.'

    elif alignment == 'PARTIAL':
        tier = pass_tier.upper() if pass_tier else ''
        if rs == 'WEAKEN':
            conclusion = 'Conclusion: Signal present but sector flow is unfavorable — timing risk elevated — not actionable.'
        elif rs == 'WAIT':
            conclusion = 'Conclusion: Signal not fully confirmed and sector timing is not favorable — not actionable.'
        elif rs == 'SUPPORT' and signal == 'STRONG':
            conclusion = 'Conclusion: Strong signal with sector support. Fundamentals require monitoring.'
        elif rs == 'SUPPORT' and eq_available:
            conclusion = 'Conclusion: Sector timing is favorable but fundamentals fail to provide strong validation — not actionable.'
        elif rs == 'SUPPORT':
            conclusion = 'Conclusion: Sector timing is favorable but signal lacks fundamental validation — not actionable.'
        elif tier == 'PASS':
            conclusion = 'Conclusion: Fundamentals solid but signal lacks sufficient strength — not actionable.'
        else:
            conclusion = 'Conclusion: Signal not fully confirmed — not actionable.'

    else:  # CONFLICT
        if signal == 'STRONG':
            conclusion = 'Conclusion: Signal not supported by fundamentals. High risk of false signal — not actionable.'
        else:
            conclusion = 'Conclusion: No alignment between signal and fundamentals — not actionable.'

    return {
        'market_line':    market_line,
        'earnings_line':  earnings_line,
        'rotation_line':  rotation_line,
        'alignment':      alignment,
        'conclusion':     conclusion,
    }


def _build_eq_display(c: dict, market_verdict: str = '') -> dict:
    """
    Builds display-ready EQ fields from raw EQ data on the candidate dict.
    System 1 owns all EQ rendering. System 2 never produces HTML for System 1.
    Returns safe fallback display values when EQ data is unavailable.

    EQ verdict controlled vocabulary (maps from pass_tier only):
      SUPPORTIVE  — PASS
      NEUTRAL     — WATCH
      WEAK        — FAIL
      RISKY       — fatal flaw present (overrides tier)
      UNAVAILABLE — no EQ data
    """
    conf_score   = c.get('composite_confidence', 0)
    eq_available = bool(c.get(EQ_AVAILABLE))
    pass_tier    = c.get(PASS_TIER, '')
    fatal        = c.get(FATAL_FLAW_REASON, '')

    rotation_signal    = c.get(ROTATION_SIGNAL, 'UNKNOWN')
    rotation_available = bool(c.get(ROTATION_AVAILABLE))
    combined_reading   = _build_combined_reading(
        conf_score, pass_tier, eq_available, fatal, market_verdict,
        rotation_signal, rotation_available
    )
    signal_strength  = _signal_strength_label(conf_score)

    if not eq_available:
        return {
            **_build_rotation_display(c),
            EQ_SCORE_DISPLAY:         'UNAVAILABLE',
            EQ_LABEL_DISPLAY:         'UNAVAILABLE',
            EQ_VERDICT_DISPLAY:       'UNAVAILABLE',
            EQ_TOP_RISKS_DISPLAY:     [],
            EQ_TOP_STRENGTHS_DISPLAY: [],
            EQ_WARNINGS_DISPLAY:      [],
            'eq_pass_display':        'UNAVAILABLE',
            'eq_combined_reading':    combined_reading,
            'signal_strength':        signal_strength,
            'eq_alignment':           combined_reading.get('alignment', 'UNKNOWN'),
        }

    eq_score   = c.get(EQ_SCORE_FINAL, 0)
    eq_label   = c.get(EQ_LABEL, '')
    risks      = c.get(TOP_RISKS, [])
    strengths  = c.get(TOP_STRENGTHS, [])
    warnings   = c.get(WARNINGS, [])
    percentile = c.get(EQ_PERCENTILE, 0)

    score_display = f'{int(eq_score)}/100'
    label_display = eq_label if eq_label else 'Unknown'

    # Verdict maps directly from pass tier — warnings do not affect this
    eq_verdict = _eq_verdict_from_tier(pass_tier, fatal)

    # Pass tier display line
    eq_verdict_for_display = _eq_verdict_from_tier(pass_tier, fatal)
    pass_display = f'{pass_tier.upper()} ({eq_verdict_for_display})' + (f' — {percentile}th percentile' if percentile else '')

    warning_strings = []
    for w in warnings[:3]:
        if isinstance(w, dict):
            warning_strings.append(w.get('message', str(w)))
        else:
            warning_strings.append(str(w))

    return {
        **_build_rotation_display(c),
        EQ_SCORE_DISPLAY:         score_display,
        EQ_LABEL_DISPLAY:         label_display,
        EQ_VERDICT_DISPLAY:       eq_verdict,
        EQ_TOP_RISKS_DISPLAY:     risks[:3],
        EQ_TOP_STRENGTHS_DISPLAY: strengths[:3],
        EQ_WARNINGS_DISPLAY:      warning_strings,
        'eq_pass_display':        pass_display,
        'eq_combined_reading':    combined_reading,
        'signal_strength':        signal_strength,
        'eq_alignment':           combined_reading.get('alignment', 'UNKNOWN'),
    }


def _build_rotation_display(c: dict) -> dict:
    """
    Builds display-ready rotation fields from raw System 3 data on the
    candidate dict. System 1 owns all rendering.
    Returns safe fallback display values when rotation data is unavailable.

    rotation_signal controlled vocabulary:
      SUPPORT  — sector flow supports acting now
      WAIT     — neutral timing environment
      WEAKEN   — sector flow weakens the setup
      UNKNOWN  — insufficient data or SKIP
    """
    rotation_available = bool(c.get(ROTATION_AVAILABLE))

    if not rotation_available:
        return {
            ROTATION_SCORE_DISPLAY:  'UNAVAILABLE',
            ROTATION_SIGNAL_DISPLAY: 'UNKNOWN',
            ROTATION_ETF_DISPLAY:    '',
            'rotation_available':    False,
            'rotation_conf_note':    '',
        }

    score  = c.get(ROTATION_SCORE)
    signal = c.get(ROTATION_SIGNAL, 'UNKNOWN')
    etf    = c.get(SECTOR_ETF, '')
    conf   = c.get(ROTATION_CONFIDENCE, '')

    score_display = f'{score:.1f}/100' if score is not None else 'N/A'
    conf_note     = f' ({conf.lower()} confidence)' if conf and conf != 'HIGH' else ''

    return {
        ROTATION_SCORE_DISPLAY:  score_display,
        ROTATION_SIGNAL_DISPLAY: signal,
        ROTATION_ETF_DISPLAY:    etf,
        'rotation_available':    True,
        'rotation_conf_note':    conf_note,
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

    event_type = c.get('sector_data', {}).get('primary_event', '_unknown')

    # Price line
    price      = c.get('current_price') or fin.get('current_price')
    change_pct = fin.get('price_change_pct')
    price_line = render_price_line(price, change_pct)

    # Company intro
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

    # Trend line
    ram_label = ram.get('label', 'no trend data')
    mtf       = c.get('mtf', {})
    r1m       = mtf.get('r1m')
    r3m       = mtf.get('r3m')
    r6m       = mtf.get('r6m')

    def _fmt_ret(v):
        if v is None: return 'n/a'
        if v > 0:   return f'\u25b2{v:.1f}%'
        if v < 0:   return f'\u25bc{abs(v):.1f}%'
        return '\u20130.0%'

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

    # Financial health
    margin_pct = fin.get('profit_margin')
    de_ratio   = fin.get('debt_to_equity')
    fin_health = render_financial_health(margin_pct, de_ratio)

    ocf_val  = fin.get('operating_cash_flow')
    roic_val = c.get('roic_proxy')
    fcf_val  = ocf_val

    if margin_pct is not None and fcf_val is not None:
        fin_health = FINANCIAL_HEALTH_EXTENDED.format(
            MARGIN_PCT = f'{margin_pct:.0f}',
            DEBT_LABEL = debt_label(de_ratio),
            ROIC       = roic_label(roic_val),
            FCF_LABEL  = fcf_direction_label(fcf_val),
        )

    # Risk section
    section  = risk_section(risk_score)
    conf_lbl = confidence_label(conf_score)

    mod_risk_text = ''
    if section == 'MODERATE RISK':
        risk_comps    = c.get('risk_components', {})
        dd_pct        = dd.get('drawdown_pct')
        mod_risk_text = render_moderate_risk_block(risk_comps, risk_score, dd_pct)

    # Volume line
    vol_label   = ev.get('label', 'normal trading activity')
    volume_line = VOLUME_LINE.format(VOLUME_LABEL=vol_label.capitalize())

    # Confidence breakdown
    agr_raw  = c.get('signal_agreement', {}).get('agreement_score', 0)
    agr_int  = int(agr_raw * 100)
    conf_line = CONFIDENCE_BREAKDOWN.format(
        CONFIDENCE_LABEL = conf_lbl,
        CONFIDENCE_SCORE = int(conf_score),
        RISK_INT         = int(risk_score),
        OPP_INT          = int(c.get('opportunity_score', 0)),
        AGR_INT          = agr_int,
    )

    # Notices
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

    # Summary block (System 1 verdict — market signal only)
    summary_score_line = SUMMARY_SCORE_LINE.format(
        SCORE         = int(conf_score),
        SCORE_MEANING = score_meaning(int(conf_score)),
    )

    summary_positives = []
    ram_raw = ram.get('raw_value')
    if ram_raw is not None and ram_raw > 1:
        summary_positives.append(f'[+] {ram_label}')
    if c.get('opportunity_score', 0) > 60:
        summary_positives.append('[+] Strong fundamental and momentum signals')
    elif fin.get('profit_margin', 0) > 20:
        pm = fin.get('profit_margin', 0)
        if pm:
            summary_positives.append(f'[+] Solid profit margin ({pm:.0f}%)')
    if agr_raw > 0.25:
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
    market_verdict      = summary_verdict_val

    # EQ display enrichment — market_verdict passed explicitly so combined reading
    # has the correct verdict before the return dict is assembled
    eq_display = _build_eq_display(c, market_verdict)

    return {
        **c,
        **eq_display,
        'display_name':       company_name,
        'sector_plain':       render_sector_plain(sector),
        'industry_label':     c.get('financials', {}).get('industry', ''),
        'intro_sentence':     intro,
        'trend_label':        trend_label,
        'momentum_label':     momentum_label,
        'financial_health':   fin_health,
        'volume_line':        volume_line,
        'confidence_line':    conf_line,
        'price_line':         price_line,
        'section':            section,
        'confidence_label':   conf_lbl,
        'conf_score_int':     int(conf_score),
        'moderate_risk_text': mod_risk_text,
        'notices':            notices,
        'risk_score_int':     int(risk_score),
        'summary_score_line': summary_score_line,
        'summary_positives':  summary_positives[:2],
        'summary_risks':      summary_risks[:2],
        'summary_verdict':    summary_verdict_val,
        'market_verdict':     market_verdict,
    }


def _build_ai_prompt(
    enriched: list,
    slot: str,
    date_str: str,
    indices: dict,
    breadth: dict,
    regime: dict,
    commodity_data: dict,
) -> str:
    """
    Builds the structured AI research prompt string.
    Called once per run — same string goes to full HTML and weekly_archive.
    """
    # Defensive guards — protect against None from failed API calls
    indices        = indices or {}
    commodity_data = commodity_data or {}

    def fmt_pct(x):
        """Safe percentage formatter. Returns 'N/A' if x is None."""
        return 'N/A' if x is None else f'{x:+.1f}%'

    def fmt_price(x):
        """Safe price formatter. Returns 'N/A' if x is None."""
        return 'N/A' if x is None else f'${x:,.2f}'

    def fmt_index(val, chg):
        """Safe index formatter. Returns 'N/A' if either value is None."""
        if val is None or chg is None:
            return 'N/A'
        return f'{val:,.0f} ({chg:+.1f}%)'

    # Index values — get_index_snapshot() returns nested dicts keyed by 'dow', 'sp500', 'nasdaq'
    dow_val = indices.get('dow',    {}).get('value')
    dow_chg = indices.get('dow',    {}).get('change_pct')
    sp_val  = indices.get('sp500',  {}).get('value')
    sp_chg  = indices.get('sp500',  {}).get('change_pct')
    nas_val = indices.get('nasdaq', {}).get('value')
    nas_chg = indices.get('nasdaq', {}).get('change_pct')

    # Market condition labels — guard against None regime/breadth dicts
    regime_label  = regime.get('label', 'N/A')  if regime  else 'N/A'
    breadth_label = breadth.get('label', 'N/A') if breadth else 'N/A'

    # Commodity values — do NOT default to 0.0
    crude_pct = commodity_data.get('crude_pct')
    gas_pct   = commodity_data.get('gas_pct')

    if crude_pct is not None or gas_pct is not None:
        commodity_block = (
            "Commodity context:\n"
            f"  WTI Crude:   {fmt_pct(crude_pct)} (5-day)\n"
            f"  Natural Gas: {fmt_pct(gas_pct)} (5-day)"
        )
    else:
        commodity_block = "Commodity context: N/A"

    header = (
        "TIMING PRIORITY RULE (APPLIES TO ALL CANDIDATES):\n"
        "  3M return > 30% = automatically LATE TREND unless strong counter-evidence is present.\n"
        "  LATE TREND = elevated pullback risk and lower entry quality.\n"
        "  EARLY or MID TREND is always preferred over LATE TREND, even if momentum is weaker.\n"
        "  A stock with strong returns but a late-stage trend is a worse entry than\n"
        "  a weaker stock in an early-stage trend.\n"
        "\n"
        "DECISION HIERARCHY (use this when signals conflict):\n"
        "  1. Timing quality (trend stage) has the highest priority.\n"
        "  2. Market verdict (System 1) is the primary directional signal.\n"
        "  3. Sector rotation confirms or weakens the timing.\n"
        "  4. Earnings quality validates or blocks conviction.\n"
        "  If timing is LATE TREND, the entry is never BUY NOW unless explicitly justified\n"
        "  by strong counter-evidence across all other signals.\n"
        "\n"
        "UNAVAILABLE DATA RULE:\n"
        "  If earnings data is UNAVAILABLE, do not assume positive or negative.\n"
        "  Reduce confidence level. Do not issue strong conviction (e.g. BUY NOW)\n"
        "  unless all other signals are strong and timing is EARLY or MID TREND.\n"
        "\n"
        "Do not use certainty words: never say \"will\", \"guaranteed\", or \"certain\".\n"
        "Always prioritize downside risk before upside potential.\n"
        "If signals conflict, highlight the conflict clearly before drawing any conclusion.\n"
        "\n"
        "=============================================================\n"
        "SYSTEM CONTEXT — READ THIS BEFORE ANALYZING\n"
        "=============================================================\n"
        "\n"
        "This report was generated by an automated stock screening system.\n"
        "The system has three scoring layers:\n"
        "\n"
        "MARKET SIGNAL (System 1)\n"
        "  Confidence score 0-100. Primary ranking signal.\n"
        "  Market verdict vocabulary:\n"
        "    RESEARCH NOW — strong setup, multiple signals aligned\n"
        "    WATCH        — moderate setup, signal not fully confirmed\n"
        "    SKIP         — weak or conflicting setup, do not act\n"
        "\n"
        "EARNINGS QUALITY (System 2)\n"
        "  EQ Score 0-100. Measures earnings reliability.\n"
        "  Pass tier vocabulary:\n"
        "    PASS (SUPPORTIVE) — earnings are reliable and cash-backed\n"
        "    WATCH (NEUTRAL)   — earnings are acceptable but have concerns\n"
        "    FAIL (WEAK)       — earnings are unreliable\n"
        "    fatal flaw → RISKY — overrides all tiers, critical structural problem\n"
        "    UNAVAILABLE       — no SEC data found for this ticker\n"
        "\n"
        "SECTOR ROTATION (System 3)\n"
        "  Rotation score 0-100. Measures sector timing.\n"
        "  Signal vocabulary:\n"
        "    SUPPORT  — sector flow supports acting now\n"
        "    WAIT     — neutral timing, not yet favorable\n"
        "    WEAKEN   — sector flow is deteriorating\n"
        "    UNKNOWN  — insufficient data\n"
        "\n"
        "COMBINED READING (three-layer synthesis)\n"
        "  Alignment vocabulary:\n"
        "    ALIGNED  — all three systems agree\n"
        "    PARTIAL  — mixed signals, partial agreement\n"
        "    CONFLICT — systems disagree\n"
        "\n"
        "TIMING QUALITY DEFINITIONS (use these when classifying)\n"
        "  EARLY TREND  — price up less than 15% in 3 months, momentum building\n"
        "  MID TREND    — price up 15-30% in 3 months, trend established\n"
        "  LATE TREND   — price up more than 30% in 3 months, elevated pullback risk\n"
        "\n"
        "=============================================================\n"
        "GLOBAL CONTEXT\n"
        "=============================================================\n"
        "\n"
        f"Date: {date_str}\n"
        f"Slot: {slot}\n"
        f"Market condition: {regime_label}\n"
        f"Market breadth: {breadth_label}\n"
        "\n"
        "Market indices:\n"
        f"  Dow Jones: {fmt_index(dow_val, dow_chg)}\n"
        f"  S&P 500:   {fmt_index(sp_val, sp_chg)}\n"
        f"  Nasdaq:    {fmt_index(nas_val, nas_chg)}\n"
        "\n"
        f"{commodity_block}\n"
        "\n"
        "=============================================================\n"
        "CANDIDATES\n"
        "=============================================================\n"
    )

    candidates_block = ''
    for c in enriched:
        ticker    = c.get('ticker',   'N/A')
        sector    = c.get('sector',   'N/A')
        industry  = c.get('industry', 'N/A')

        current_price    = c.get('current_price')
        price_change_pct = c.get('price_change_pct')

        mtf = c.get('mtf', {})
        r1m = mtf.get('r1m') if mtf else c.get('r1m')
        r3m = mtf.get('r3m') if mtf else c.get('r3m')
        r6m = mtf.get('r6m') if mtf else c.get('r6m')

        conf_score      = c.get('composite_confidence', 0)
        signal_strength = c.get('signal_strength', 'N/A')
        market_verdict  = c.get('summary_verdict',  'N/A')

        ram_label    = c.get('ram', {}).get('label', 'N/A') if c.get('ram') else c.get('ram_label', 'N/A')
        volume_label = c.get('volume_confirmation', {}).get('label', 'N/A') if c.get('volume_confirmation') else 'N/A'

        eq_score_display = c.get('eq_score_display', 'UNAVAILABLE')
        eq_pass_display  = c.get('eq_pass_display',  'UNAVAILABLE')

        sector_etf              = c.get('sector_etf',              'N/A')
        rotation_score_display  = c.get('rotation_score_display',  'N/A')
        rotation_signal_display = c.get('rotation_signal_display', 'UNKNOWN')

        alignment  = c.get('eq_alignment', 'N/A')
        conclusion = c.get('eq_combined_reading', {}).get('conclusion', 'N/A') if c.get('eq_combined_reading') else 'N/A'

        # EQ strengths and warnings — use 'or []' to handle None field values
        strengths  = c.get('eq_strengths',         []) or []
        crit_warn  = c.get('eq_warnings_critical', []) or []
        minor_warn = c.get('eq_warnings_minor',    []) or []

        strengths_txt  = '\n'.join(f'+ {s}' for s in strengths[:3])  or 'N/A'
        crit_warn_txt  = '\n'.join(f'! {w}' for w in crit_warn[:3])  or 'N/A'
        minor_warn_txt = '\n'.join(f'w {w}' for w in minor_warn[:3]) or ''

        # Combined reading lines — built from already-extracted variables
        market_line   = f"Market: {market_verdict} ({conf_score}/100)"
        earnings_line = f"Earnings: {eq_pass_display}"
        rotation_line = f"Rotation: {rotation_signal_display}"

        candidate_block = (
            f"\n[{ticker}] — {sector} ({industry})\n"
            f"\n"
            f"Price:          {fmt_price(current_price)} ({fmt_pct(price_change_pct)} today)\n"
            f"Confidence:     {conf_score}/100 ({signal_strength})\n"
            f"Market verdict: {market_verdict}\n"
            f"\n"
            f"Trend:\n"
            f"  1 month:  {fmt_pct(r1m)}\n"
            f"  3 months: {fmt_pct(r3m)}\n"
            f"  6 months: {fmt_pct(r6m)}\n"
            f"  Label:    {ram_label}\n"
            f"\n"
            f"Volume: {volume_label}\n"
            f"\n"
            f"Earnings Quality:\n"
            f"  Score:     {eq_score_display}\n"
            f"  Tier:      {eq_pass_display}\n"
            f"  Strengths: {strengths_txt}\n"
            f"  Warnings:  {crit_warn_txt}\n"
            f"             {minor_warn_txt}\n"
            f"\n"
            f"Sector Rotation:\n"
            f"  ETF:    {sector_etf}\n"
            f"  Score:  {rotation_score_display}\n"
            f"  Signal: {rotation_signal_display}\n"
            f"\n"
            f"Combined Reading:\n"
            f"  {market_line}\n"
            f"  {earnings_line}\n"
            f"  {rotation_line}\n"
            f"  Alignment:  {alignment}\n"
            f"  {conclusion}\n"
        )
        candidates_block += candidate_block

    footer = (
        "\n"
        "=============================================================\n"
        "YOUR TASK\n"
        "=============================================================\n"
        "\n"
        "For EACH candidate above, provide this structure:\n"
        "\n"
        "--- [TICKER] ---\n"
        "\n"
        "1) QUICK DECISION\n"
        "   Entry: BUY NOW / WAIT / AVOID\n"
        "   Timing quality: EARLY / MID / LATE TREND\n"
        "   Confidence in timing: LOW / MEDIUM / HIGH\n"
        "   (2 sentences max explaining your decision)\n"
        "\n"
        "2) WHY (PLAIN ENGLISH)\n"
        "   Explain what is happening using simple logic:\n"
        "   - Is the trend strong or extended?\n"
        "   - Does the sector support the move or contradict it?\n"
        "   - Are there contradictions between signals (e.g. stocks rising but commodity falling)?\n"
        "   Avoid technical jargon. If you use a term, explain it in parentheses.\n"
        "\n"
        "3) ENTRY LOGIC\n"
        "   Ideal entry scenario: [when would this be a good entry]\n"
        "   Bad entry scenario:   [what would make this a poor entry]\n"
        "   What to wait for:     [1-2 specific conditions that need to improve]\n"
        "\n"
        "4) EXIT LOGIC\n"
        "   Take profit if: [specific condition]\n"
        "   Cut loss if:    [specific condition]\n"
        "   Explain each in plain English.\n"
        "\n"
        "5) TOP RISKS RIGHT NOW\n"
        "   List the 2-3 biggest risks specific to this candidate based on the data above.\n"
        "   No generic risks. Be specific to the signals shown.\n"
        "\n"
        "6) VERDICT\n"
        "   Choose one: Worth researching further / Watch closely / Avoid for now\n"
        "   Explain in 2-3 sentences why.\n"
        "\n"
        "7) ENTRY URGENCY\n"
        "   Choose one: Immediate / Near-term / Wait for confirmation\n"
        "   (1 sentence explaining the specific condition that determines urgency.\n"
        "   Example: \"Immediate — sector support and trend intact, but extended 3M return\n"
        "   means entry window is narrow.\" or \"Wait for confirmation — signal needs\n"
        "   market verdict to strengthen from WATCH to RESEARCH NOW before acting.\")\n"
        "\n"
        "---\n"
        "\n"
        "After all individual candidates, provide:\n"
        "\n"
        "CROSS-CANDIDATE SUMMARY\n"
        "  Best entry opportunity:  [ticker and one-sentence reason]\n"
        "  Worst timing right now:  [ticker and one-sentence reason]\n"
        "  Overall market read:     [1-2 sentences on whether this is a good time to act]\n"
    )

    return header + candidates_block + footer


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
    from config import GITHUB_PAGES_URL
    dashboard_url = GITHUB_PAGES_URL
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    now_utc  = datetime.now(pytz.utc)
    now_et   = now_utc.astimezone(pytz.timezone('America/New_York'))
    date_str = now_et.strftime('%Y-%m-%d')
    time_str = now_et.strftime('%H:%M ET')
    ts_str   = now_utc.strftime('%Y%m%dT%H%M%SZ')

    pulse_lines = _build_market_pulse(indices)

    confirmed_sectors = list({c['sector'] for c in companies})
    story_sentences   = _build_story_sentences(all_articles, sector_scores, confirmed_sectors)

    # Always fetch commodity data so _build_ai_prompt() can use it
    commodity_data    = get_commodity_signal()
    commodity_summary = ''
    if any(c.get('sector') == 'energy' for c in companies):
        commodity_summary = commodity_data.get('summary', '')

        if commodity_summary:
            industries_present = [
                c.get('financials', {}).get('industry', '').lower()
                for c in companies if c.get('sector') == 'energy'
            ]
            gas_producers_present = any('gas' in ind for ind in industries_present)
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

    enriched = [_enrich_company_for_template(c) for c in companies]

    prompt_text = _build_ai_prompt(
        enriched, slot, date_str, indices, breadth, regime, commodity_data
    )

    email_companies    = enriched[:EMAIL_MAX]
    overflow_companies = enriched[EMAIL_MAX:]

    def partition(lst):
        low = [c for c in lst if c['section'] == 'LOW RISK']
        mod = [c for c in lst if c['section'] == 'MODERATE RISK']
        return low, mod

    email_low, email_mod = partition(email_companies)
    full_low, full_mod   = partition(enriched)

    n_found         = len(companies)
    subject         = f'■ Stock Research — {slot} Update — {n_found} opportunit{"y" if n_found == 1 else "ies"} found'
    overflow_count  = len(overflow_companies)
    overflow_notice = f'+ {overflow_count} more companies found today. View full report: [LINK]' if overflow_count else ''

    env = _get_jinja_env()

    try:
        email_tpl  = env.get_template('intraday_email.html')
        email_html = email_tpl.render(
            subject           = subject,
            slot              = slot,
            date_str          = date_str,
            time_str          = time_str,
            pulse_lines       = pulse_lines,
            story_sentences   = story_sentences,
            low_risk          = email_low,
            moderate_risk     = email_mod,
            overflow_notice   = overflow_notice,
            regime_label      = regime.get('label', 'Normal market'),
            breadth_label     = breadth.get('label', 'neutral'),
            disclaimer        = DISCLAIMER,
            total_companies   = n_found,
            commodity_summary = commodity_summary,
            dashboard_url     = dashboard_url,
        )
        email_path = os.path.join(OUTPUT_DIR, f'intraday_email_{slot.replace(":", "").replace("-", "_")}_{ts_str}.html')
        with open(email_path, 'w', encoding='utf-8') as f:
            f.write(email_html)
        log.info(f'Email report written: {email_path}')
    except Exception as e:
        log.error(f'Failed to render email template: {e}')
        email_path = _write_fallback_email(slot, ts_str, pulse_lines, story_sentences, enriched)

    try:
        full_tpl  = env.get_template('intraday_full.html')
        full_html = full_tpl.render(
            subject           = subject,
            slot              = slot,
            date_str          = date_str,
            time_str          = time_str,
            pulse_lines       = pulse_lines,
            story_sentences   = story_sentences,
            low_risk          = full_low,
            moderate_risk     = full_mod,
            regime_label      = regime.get('label', 'Normal market'),
            breadth_label     = breadth.get('label', 'neutral'),
            disclaimer        = DISCLAIMER,
            total_companies   = n_found,
            rotation          = rotation,
            commodity_summary = commodity_summary,
            ai_prompt         = prompt_text[:15000],
        )
        full_path = os.path.join(OUTPUT_DIR, f'intraday_full_{slot.replace(":", "").replace("-", "_")}_{ts_str}.html')
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        log.info(f'Full report written: {full_path}')
    except Exception as e:
        log.error(f'Failed to render full template: {e}')
        full_path = email_path

    return {'email': email_path, 'full': full_path, 'prompt': prompt_text}


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
    