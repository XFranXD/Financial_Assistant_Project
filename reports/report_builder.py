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
from contracts.price_structure_schema import (
    PS_AVAILABLE,
    PS_ENTRY_QUALITY, PS_TREND_STRUCTURE, PS_TREND_STRENGTH,
    PS_KEY_LEVEL_POSITION, PS_VOLATILITY_STATE, PS_STRUCTURE_STATE,
    PS_PRICE_ACTION_SCORE, PS_MOVE_EXTENSION_PCT,
    PS_DISTANCE_TO_SUPPORT_PCT, PS_DISTANCE_TO_RESIST_PCT,
    PS_DATA_CONFIDENCE, PS_REASONING,
    PS_ENTRY_QUALITY_DISPLAY, PS_TREND_DISPLAY,
    PS_KEY_LEVEL_DISPLAY, PS_SCORE_DISPLAY, PS_REASONING_DISPLAY,
    PS_VERDICT_DISPLAY, PS_COMPRESSION_LOCATION,
)

log = get_logger('report_builder')

TEMPLATES_DIR  = os.path.join(os.path.dirname(__file__), 'templates')
OUTPUT_DIR     = os.path.join(os.path.dirname(__file__), 'output')
EMAIL_MAX      = 7
TIMEZONE       = 'America/New_York'

DISCLAIMER = (
    'DISCLAIMER: This system does NOT perform trading, does NOT give investment advice, '
    'and does NOT make price predictions. It is a research data aggregation and scoring tool only.'
)

SIGNAL_STRONG   = 70
SIGNAL_MODERATE = 50


def _get_jinja_env() -> Environment:
    return Environment(
        loader       = FileSystemLoader(TEMPLATES_DIR),
        autoescape   = select_autoescape(['html']),
        trim_blocks  = True,
        lstrip_blocks= True,
    )


def _build_market_pulse(indices: dict) -> list[str]:
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
    if conf_score >= SIGNAL_STRONG:
        return 'STRONG'
    elif conf_score >= SIGNAL_MODERATE:
        return 'MODERATE'
    return 'WEAK'


def _eq_verdict_from_tier(pass_tier: str, fatal: str) -> str:
    """
    Maps EQ pass tier to controlled vocabulary verdict.
    Fatal flaw always overrides pass tier → RISKY.

    Vocabulary:
      SUPPORTIVE  — PASS tier
      NEUTRAL     — WATCH tier
      WEAK        — FAIL tier
      RISKY       — fatal flaw present
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
                     rotation_signal: str = 'UNKNOWN',
                     ps_entry_quality: str = 'UNAVAILABLE') -> str:
    """
    Deterministic alignment state across System 1, 2, 3, and 4.

    Four-dimensional alignment logic:
      market    → +1 if RESEARCH NOW / -1 if SKIP / 0 otherwise
      earnings  → +1 if SUPPORTIVE / -1 if WEAK or RISKY / 0 otherwise
      rotation  → +1 if SUPPORT / -1 if WEAKEN / 0 if WAIT or UNKNOWN
      ps        → +1 if GOOD / -1 if WEAK or EXTENDED / 0 if EARLY or UNAVAILABLE

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

    ps = (ps_entry_quality or '').strip().upper()
    if ps == 'GOOD':
        alignment_score += 1
    elif ps in ('WEAK', 'EXTENDED'):
        alignment_score -= 1
    # EARLY and UNAVAILABLE are neutral (0)

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
                            rotation_available: bool = False,
                            ps_entry_quality: str = 'UNAVAILABLE') -> dict:
    """
    Deterministic combined reading of System 1, 2, 3, and 4.
    Returns a structured dict for template rendering.

    BUY NOW hard gate (System 4):
      entry_quality must be GOOD for BUY NOW to be issued.
      EXTENDED or WEAK entry_quality blocks BUY NOW regardless of S1/S2/S3.
      EARLY is unconfirmed — does not block but does not enable BUY NOW.
      UNAVAILABLE treated same as EARLY — reduce confidence, no BUY NOW.

    Output keys:
      market_line    — Market classification line
      earnings_line  — Earnings classification line
      rotation_line  — Rotation timing line
      ps_line        — Price structure entry quality line
      alignment      — ALIGNED / PARTIAL / CONFLICT
      conclusion     — Final declarative conclusion sentence
    """
    signal     = _signal_strength_label(conf_score)
    eq_verdict = _eq_verdict_from_tier(pass_tier, fatal) if eq_available else 'UNAVAILABLE'
    rs         = rotation_signal.upper() if rotation_signal else 'UNKNOWN'
    mv         = market_verdict.upper() if market_verdict else ''
    ps_eq      = (ps_entry_quality or '').strip().upper()
    alignment  = _alignment_state(market_verdict, eq_verdict, eq_available, rs, ps_eq)

    mv_display    = market_verdict.upper() if market_verdict else signal
    market_line   = f'Market:          {mv_display} ({int(conf_score)}/100)'
    earnings_line = f'Earnings:        {eq_verdict}'
    rotation_line = f'Rotation:        {rs}'
    ps_line       = f'Price Structure: {ps_eq}'

    # ── No EQ data branch ─────────────────────────────────────────────────
    if not eq_available and not rotation_available:
        conclusion = 'Conclusion: No fundamental or timing validation available — not actionable.'

    elif not eq_available and rs == 'SUPPORT':
        if mv == 'RESEARCH NOW':
            if ps_eq == 'GOOD':
                conclusion = 'Conclusion: Sector timing supports acting and entry quality confirmed. No fundamental validation available.'
            elif ps_eq in ('EXTENDED', 'WEAK'):
                conclusion = 'Conclusion: Sector timing is favorable but entry quality blocks action — not actionable.'
            else:
                conclusion = 'Conclusion: Sector timing supports acting. No fundamental validation available.'
        elif mv == 'SKIP':
            conclusion = 'Conclusion: Sector timing is favorable but market signal is weak — insufficient basis to act.'
        else:
            conclusion = 'Conclusion: Sector timing is favorable but fundamental data is unavailable — not actionable.'

    elif not eq_available and rs == 'WAIT':
        conclusion = 'Conclusion: No fundamental validation and sector timing is not favorable — not actionable.'

    elif not eq_available and rs == 'WEAKEN':
        if mv == 'WATCH':
            conclusion = 'Conclusion: Weak signal and unfavorable sector timing — not actionable.'
        else:
            conclusion = 'Conclusion: Sector timing weakens this setup. No fundamental validation available — not actionable.'

    elif not eq_available:
        conclusion = 'Conclusion: No fundamental validation available — not actionable.'

    # ── EQ data present branch ─────────────────────────────────────────────
    elif fatal:
        conclusion = 'Conclusion: Fatal flaw in earnings structure. Avoid.'

    elif alignment == 'ALIGNED':
        if mv == 'RESEARCH NOW':
            # ── S4 BUY NOW hard gate ──────────────────────────────────────
            if ps_eq == 'GOOD':
                conclusion = 'Conclusion: Signal supported by fundamentals, sector timing, and entry quality confirmed. Highest priority candidate.'
            elif ps_eq in ('EXTENDED', 'WEAK'):
                conclusion = 'Conclusion: Signal aligned but entry quality is not GOOD — price structure blocks BUY NOW. Monitor for reset to support.'
            elif ps_eq == 'EARLY':
                conclusion = 'Conclusion: Signal aligned but entry pattern not yet confirmed — wait for price structure to confirm before acting.'
            else:
                # UNAVAILABLE — do not block but note reduced confidence
                conclusion = 'Conclusion: Signal supported by fundamentals and sector timing. Price structure data unavailable — verify entry manually.'
        else:
            conclusion = 'Conclusion: High-quality setup — fundamentals and sector timing aligned, but market signal unconfirmed — monitor for confirmation.'

    elif alignment == 'PARTIAL':
        tier = pass_tier.upper() if pass_tier else ''
        if rs == 'WEAKEN':
            conclusion = 'Conclusion: Signal present but sector flow is unfavorable — timing risk elevated — not actionable.'
        elif rs == 'WAIT':
            conclusion = 'Conclusion: Signal not fully confirmed and sector timing is not favorable — not actionable.'
        elif rs == 'SUPPORT' and signal == 'STRONG':
            if ps_eq == 'GOOD':
                conclusion = 'Conclusion: Strong signal with sector support and entry quality confirmed. Fundamentals require monitoring.'
            elif ps_eq in ('EXTENDED', 'WEAK'):
                conclusion = 'Conclusion: Strong signal with sector support but entry quality blocks action — not actionable.'
            else:
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
        'ps_line':        ps_line,
        'alignment':      alignment,
        'conclusion':     conclusion,
    }


def _build_ps_display(c: dict) -> dict:
    """
    Builds display-ready S4 fields from raw price structure data on the candidate dict.
    System 1 owns all S4 rendering. Returns safe fallback display values when
    price structure data is unavailable.

    entry_quality controlled vocabulary:
      GOOD      — price near support or valid base with confirmed setup
      EXTENDED  — price far above support, elevated pullback risk
      EARLY     — pattern forming but not yet confirmed
      WEAK      — no valid setup, avoid entry
      UNAVAILABLE — ps_analyze() returned UNAVAILABLE confidence
    """
    ps_available = bool(c.get(PS_AVAILABLE))

    if not ps_available:
        return {
            PS_ENTRY_QUALITY_DISPLAY: 'UNAVAILABLE',
            PS_TREND_DISPLAY:         'UNAVAILABLE',
            PS_KEY_LEVEL_DISPLAY:     'UNAVAILABLE',
            PS_SCORE_DISPLAY:         'UNAVAILABLE',
            PS_REASONING_DISPLAY:     'Price structure data unavailable.',
            PS_VERDICT_DISPLAY:       'UNAVAILABLE',
            'ps_available':           False,
        }

    entry_quality = (c.get(PS_ENTRY_QUALITY)     or 'WEAK').strip().upper()
    trend         = (c.get(PS_TREND_STRUCTURE)    or 'SIDEWAYS').strip().upper()
    key_level     = (c.get(PS_KEY_LEVEL_POSITION) or 'MID_RANGE').strip().upper()
    score         = c.get(PS_PRICE_ACTION_SCORE,   0)
    reasoning     = c.get(PS_REASONING,            'No reasoning available.')

    score_display     = f'{int(score)}/100'
    key_level_display = key_level.replace('_', ' ').title()

    return {
        PS_ENTRY_QUALITY_DISPLAY: entry_quality,
        PS_TREND_DISPLAY:         trend,
        PS_KEY_LEVEL_DISPLAY:     key_level_display,
        PS_SCORE_DISPLAY:         score_display,
        PS_REASONING_DISPLAY:     (reasoning[:200] if reasoning else ''),
        PS_VERDICT_DISPLAY:       entry_quality,   # same vocabulary — pill uses this
        'ps_available':           True,
    }


def _build_eq_display(c: dict, market_verdict: str = '') -> dict:
    """
    Builds display-ready EQ fields from raw EQ data on the candidate dict.
    System 1 owns all EQ rendering. System 2 never produces HTML for System 1.
    Returns safe fallback display values when EQ data is unavailable.
    """
    conf_score   = c.get('composite_confidence', 0)
    eq_available = bool(c.get(EQ_AVAILABLE))
    pass_tier    = c.get(PASS_TIER, '')
    fatal        = c.get(FATAL_FLAW_REASON, '')

    rotation_signal    = c.get(ROTATION_SIGNAL, 'UNKNOWN')
    rotation_available = bool(c.get(ROTATION_AVAILABLE))

    # S4 entry_quality for BUY NOW gate
    ps_entry_quality = (
        c.get(PS_ENTRY_QUALITY, 'UNAVAILABLE')
        if c.get(PS_AVAILABLE)
        else 'UNAVAILABLE'
    )

    combined_reading = _build_combined_reading(
        conf_score, pass_tier, eq_available, fatal, market_verdict,
        rotation_signal, rotation_available,
        ps_entry_quality=ps_entry_quality,
    )
    signal_strength = _signal_strength_label(conf_score)

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

    eq_verdict = _eq_verdict_from_tier(pass_tier, fatal)
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
    Builds display-ready rotation fields from raw System 3 data on the candidate dict.
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

    price      = c.get('current_price') or fin.get('current_price')
    change_pct = fin.get('price_change_pct')
    price_line = render_price_line(price, change_pct)

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

    section  = risk_section(risk_score)
    conf_lbl = confidence_label(conf_score)

    mod_risk_text = ''
    if section == 'MODERATE RISK':
        risk_comps    = c.get('risk_components', {})
        dd_pct        = dd.get('drawdown_pct')
        mod_risk_text = render_moderate_risk_block(risk_comps, risk_score, dd_pct)

    vol_label   = ev.get('label', 'normal trading activity')
    volume_line = VOLUME_LINE.format(VOLUME_LABEL=vol_label.capitalize())

    agr_raw  = c.get('signal_agreement', {}).get('agreement_score', 0)
    agr_int  = int(agr_raw * 100)
    conf_line = CONFIDENCE_BREAKDOWN.format(
        CONFIDENCE_LABEL = conf_lbl,
        CONFIDENCE_SCORE = int(conf_score),
        RISK_INT         = int(risk_score),
        OPP_INT          = int(c.get('opportunity_score', 0)),
        AGR_INT          = agr_int,
    )

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

    # EQ display enrichment — market_verdict passed explicitly
    eq_display = _build_eq_display(c, market_verdict)

    # S4 display enrichment
    ps_display = _build_ps_display(c)

    return {
        **c,
        **eq_display,
        **ps_display,
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
    Builds the daily dynamic AI research prompt string (USER turn only).
    Version: 2.0 — paired with MRE_AI_SYSTEM_PROMPT.md (static system prompt).

    The system prompt (MRE_AI_SYSTEM_PROMPT.md) carries all rules, vocabulary,
    decision hierarchy, and output format. This function provides only:
    global market context + per-candidate data blocks.

    Called once per run — same string goes to full HTML and weekly_archive.

    Changes from v1.0:
      - BUG FIX: eq_strengths / eq_warnings_critical replaced with
        top_strengths / top_risks (the actual keys set by eq_schema.py).
        Strengths and risks now show real data instead of N/A on every run.
      - ADDED: timing_label pre-computed in Python via _timing_label(r3m).
        AI receives EARLY TREND / MID TREND / LATE TREND directly in the
        candidate header instead of deriving it from a raw number.
      - ADDED: ps_volatility_state and ps_compression_location in the S4 block.
        COMPRESSING volatility near support is a meaningful setup signal.
      - KEPT: volume_label — volume confirmation matters for entry quality.
      - KEPT: Combined Reading block — pre-computed synthesis anchors AI analysis.
    """
    indices        = indices or {}
    commodity_data = commodity_data or {}

    # ── Formatting helpers ────────────────────────────────────────────────

    def fmt_pct(x):
        return 'N/A' if x is None else f'{x:+.1f}%'

    def fmt_price(x):
        return 'N/A' if x is None else f'${x:,.2f}'

    def fmt_index(val, chg):
        if val is None or chg is None:
            return 'N/A'
        return f'{val:,.0f} ({chg:+.1f}%)'

    def _timing_label(r3m_val):
        """
        Pre-compute timing label so the AI receives a definitive label
        rather than deriving it from raw numbers (reduces hallucination risk).
        Matches definitions in MRE_AI_SYSTEM_PROMPT.md.
        """
        if r3m_val is None:
            return 'UNKNOWN'
        if r3m_val > 30:
            return 'LATE TREND'
        if r3m_val >= 15:
            return 'MID TREND'
        return 'EARLY TREND'

    # ── Global context ────────────────────────────────────────────────────

    dow_val = indices.get('dow',    {}).get('value')
    dow_chg = indices.get('dow',    {}).get('change_pct')
    sp_val  = indices.get('sp500',  {}).get('value')
    sp_chg  = indices.get('sp500',  {}).get('change_pct')
    nas_val = indices.get('nasdaq', {}).get('value')
    nas_chg = indices.get('nasdaq', {}).get('change_pct')

    regime_label  = regime.get('label',  'N/A') if regime  else 'N/A'
    breadth_label = breadth.get('label', 'N/A') if breadth else 'N/A'

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
        "=============================================================\n"
        "GLOBAL CONTEXT\n"
        "=============================================================\n"
        "\n"
        f"Date:             {date_str}\n"
        f"Slot:             {slot}\n"
        f"Market condition: {regime_label}\n"
        f"Market breadth:   {breadth_label}\n"
        "\n"
        "Market indices:\n"
        f"  Dow Jones: {fmt_index(dow_val, dow_chg)}\n"
        f"  S&P 500:   {fmt_index(sp_val,  sp_chg)}\n"
        f"  Nasdaq:    {fmt_index(nas_val,  nas_chg)}\n"
        "\n"
        f"{commodity_block}\n"
        "\n"
        "=============================================================\n"
        "CANDIDATES\n"
        "=============================================================\n"
    )

    # ── Candidate blocks ──────────────────────────────────────────────────

    candidates_block = ''

    for c in enriched:

        # ── Identity ──────────────────────────────────────────────────────
        ticker   = c.get('ticker',   'N/A')
        sector   = c.get('sector',   'N/A')
        industry = c.get('industry', c.get('financials', {}).get('industry', 'N/A'))

        # ── Price / momentum ──────────────────────────────────────────────
        current_price    = c.get('current_price')
        price_change_pct = c.get('price_change_pct') or c.get('financials', {}).get('price_change_pct')

        mtf = c.get('mtf', {})
        r1m = mtf.get('r1m') if mtf else c.get('r1m')
        r3m = mtf.get('r3m') if mtf else c.get('r3m')
        r6m = mtf.get('r6m') if mtf else c.get('r6m')

        timing = _timing_label(r3m)

        ram_label = (
            c.get('ram', {}).get('label', 'N/A')
            if c.get('ram')
            else c.get('ram_label', 'N/A')
        )

        # ── System 1 ──────────────────────────────────────────────────────
        conf_score      = c.get('composite_confidence', 0)
        signal_strength = c.get('signal_strength', 'N/A')
        market_verdict  = c.get('summary_verdict',  'N/A')

        # ── Volume ────────────────────────────────────────────────────────
        volume_label = (
            c.get('volume_confirmation', {}).get('label', 'N/A')
            if c.get('volume_confirmation')
            else 'N/A'
        )

        # ── System 2 — EQ ─────────────────────────────────────────────────
        # v2.0 BUG FIX: use top_strengths / top_risks (actual eq_schema.py keys).
        # v1.0 used eq_strengths / eq_warnings_critical — keys that were never set,
        # causing Strengths and Risks to always render as N/A.
        eq_score_display = c.get('eq_score_display', 'UNAVAILABLE')
        eq_pass_display  = c.get('eq_pass_display',  'UNAVAILABLE')

        top_strengths = c.get('top_strengths', []) or []
        top_risks_raw = c.get('top_risks',     []) or []

        strengths_txt = '\n'.join(f'+ {s}' for s in top_strengths[:2]) or 'N/A'
        risks_txt     = '\n'.join(f'! {r}' for r in top_risks_raw[:2]) or 'N/A'

        # ── System 3 — Rotation ───────────────────────────────────────────
        sector_etf              = c.get('sector_etf',              'N/A')
        rotation_score_display  = c.get('rotation_score_display',  'N/A')
        rotation_signal_display = c.get('rotation_signal_display', 'UNKNOWN')

        # ── System 4 — Price Structure ────────────────────────────────────
        ps_available_val   = bool(c.get(PS_AVAILABLE))
        ps_available_str   = 'YES' if ps_available_val else 'NO'

        ps_entry_quality   = (c.get(PS_ENTRY_QUALITY)          or 'UNAVAILABLE') if ps_available_val else 'UNAVAILABLE'
        ps_trend_structure = (c.get(PS_TREND_STRUCTURE)        or 'UNAVAILABLE') if ps_available_val else 'UNAVAILABLE'
        ps_trend_strength  = c.get(PS_TREND_STRENGTH, 0)       if ps_available_val else 'N/A'
        ps_key_level       = (c.get(PS_KEY_LEVEL_POSITION)     or 'UNAVAILABLE') if ps_available_val else 'UNAVAILABLE'
        ps_structure_state = (c.get(PS_STRUCTURE_STATE)        or 'UNAVAILABLE') if ps_available_val else 'UNAVAILABLE'
        ps_score           = c.get(PS_PRICE_ACTION_SCORE, 0)   if ps_available_val else 'N/A'
        ps_move_ext        = f"{c.get(PS_MOVE_EXTENSION_PCT,        0.0):.1f}" if ps_available_val else 'N/A'
        ps_dist_sup        = f"{c.get(PS_DISTANCE_TO_SUPPORT_PCT,   0.0):.1f}" if ps_available_val else 'N/A'
        ps_dist_res        = f"{c.get(PS_DISTANCE_TO_RESIST_PCT,    0.0):.1f}" if ps_available_val else 'N/A'
        ps_reasoning       = (c.get(PS_REASONING) or 'No reasoning available.')[:200] if ps_available_val else 'UNAVAILABLE'

        # v2.0 ADDED: volatility_state and compression_location.
        # COMPRESSING near support is a meaningful setup signal the AI should see.
        ps_volatility_state = (c.get(PS_VOLATILITY_STATE)     or 'NORMAL')  if ps_available_val else 'UNAVAILABLE'
        ps_compression_loc  = (c.get(PS_COMPRESSION_LOCATION) or 'NEUTRAL') if ps_available_val else 'UNAVAILABLE'

        # ── Combined reading (pre-computed synthesis) ─────────────────────
        alignment  = c.get('eq_alignment', 'N/A')
        conclusion = (
            c.get('eq_combined_reading', {}).get('conclusion', 'N/A')
            if c.get('eq_combined_reading')
            else 'N/A'
        )

        market_line   = f"Market:          {market_verdict} ({int(conf_score)}/100)"
        earnings_line = f"Earnings:        {eq_pass_display}"
        rotation_line = f"Rotation:        {rotation_signal_display}"
        ps_cr_line    = f"Price Structure: {ps_entry_quality}"

        candidate_block = (
            f"\n[{ticker}] — {sector} ({industry}) | Timing: {timing}\n"
            f"\n"
            f"Price:          {fmt_price(current_price)} ({fmt_pct(price_change_pct)} today)\n"
            f"Confidence:     {int(conf_score)}/100 ({signal_strength})\n"
            f"Market verdict: {market_verdict}\n"
            f"\n"
            f"Trend:\n"
            f"  1 month:  {fmt_pct(r1m)}\n"
            f"  3 months: {fmt_pct(r3m)}  ← timing basis\n"
            f"  6 months: {fmt_pct(r6m)}\n"
            f"  Label:    {ram_label}\n"
            f"\n"
            f"Volume: {volume_label}\n"
            f"\n"
            f"Earnings Quality (System 2):\n"
            f"  Score:     {eq_score_display}\n"
            f"  Tier:      {eq_pass_display}\n"
            f"  Strengths: {strengths_txt}\n"
            f"  Risks:     {risks_txt}\n"
            f"\n"
            f"Sector Rotation (System 3):\n"
            f"  ETF:    {sector_etf}\n"
            f"  Score:  {rotation_score_display}\n"
            f"  Signal: {rotation_signal_display}\n"
            f"\n"
            f"Price Structure (System 4):\n"
            f"  Available:        {ps_available_str}\n"
            f"  Entry quality:    {ps_entry_quality}\n"
            f"  Trend:            {ps_trend_structure} (strength: {ps_trend_strength}/100)\n"
            f"  Key level:        {ps_key_level}\n"
            f"  Structure:        {ps_structure_state}\n"
            f"  Volatility state: {ps_volatility_state} (compression: {ps_compression_loc})\n"
            f"  Price action:     {ps_score}/100\n"
            f"  Move extension:   {ps_move_ext}% above 126-day low\n"
            f"  Dist to support:  {ps_dist_sup}%\n"
            f"  Dist to resist:   {ps_dist_res}%\n"
            f"  Reasoning:        {ps_reasoning}\n"
            f"\n"
            f"Combined Reading:\n"
            f"  {market_line}\n"
            f"  {earnings_line}\n"
            f"  {rotation_line}\n"
            f"  {ps_cr_line}\n"
            f"  Alignment:  {alignment}\n"
            f"  {conclusion}\n"
        )
        candidates_block += candidate_block

    # ── Footer — single trigger line; all rules live in MRE_AI_SYSTEM_PROMPT.md ──

    footer = (
        "\n"
        "=============================================================\n"
        "ANALYZE THE CANDIDATES ABOVE\n"
        "=============================================================\n"
        "\n"
        "Apply tier classification first.\n"
        "Then produce the required output sections for each tier.\n"
        "Follow all rules and output format from your system prompt exactly.\n"
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

        docs_reports_dir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'reports')
        os.makedirs(docs_reports_dir, exist_ok=True)
        full_fname  = os.path.basename(full_path)
        served_path = os.path.join(docs_reports_dir, full_fname)
        with open(served_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        full_url = f'reports/{full_fname}'
        log.info(f'Full report served at docs/{full_url}')
    except Exception as e:
        log.error(f'Failed to render full template: {e}')
        full_path = email_path
        full_url  = ''

    return {'email': email_path, 'full': full_path, 'full_url': full_url, 'prompt': prompt_text}


def _write_fallback_email(slot, ts_str, pulse_lines, story_sentences, companies) -> str:
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
    