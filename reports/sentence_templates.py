"""
reports/sentence_templates.py — §23 File 1
All plain English sentence templates and lookup dictionaries.
Every sentence in a report comes from this file — no free-text generation.

DISCLAIMER: This system does NOT perform trading, does NOT give investment advice,
and does NOT make price predictions. It is a research data aggregation and scoring
tool only.
"""

# ── Sentence templates (uppercase placeholders replaced at render time) ─────

COMPANY_INTRO = (
    "{COMPANY} appeared today because the {SECTOR} sector is seeing "
    "{DIRECTION} movement following news about {EVENT_PLAIN}."
)

TREND_SENTENCE = (
    "The stock has been {TREND_LABEL} for the past {TREND_DAYS} days "
    "and is currently {MOMENTUM_LABEL}."
)

FINANCIAL_HEALTH = (
    "Financial health: keeps {MARGIN_PCT} cents from every dollar it earns "
    "(profit margin), and carries {DEBT_LABEL} debt compared to what it owns."
)

FINANCIAL_HEALTH_NO_MARGIN = (
    "Financial health: profit margin data not available. "
    "Carries {DEBT_LABEL} debt compared to what it owns."
)

MODERATE_RISK_REASON = (
    "Why moderate risk: {RISK_REASON_1}. {RISK_REASON_2}"
)

MODERATE_RISK_REASON_SINGLE = (
    "Why moderate risk: {RISK_REASON_1}."
)

UNUSUAL_VOLUME_NOTE = (
    "Notable: {UNUSUAL_LABEL} today — this means something significant "
    "may be drawing attention to this stock."
)

DRAWDOWN_NOTE = (
    "The stock is currently {DRAWDOWN_PCT}% below its highest price "
    "in the past 90 days."
)

EARNINGS_WARNING = (
    "■■ Earnings announcement in {DAYS} days — companies often move "
    "sharply around earnings. Factor this into your research."
)

EARNINGS_WARNING_IMMINENT = (
    "■■ Earnings announcement TOMORROW — companies often move "
    "sharply around earnings. Factor this into your research."
)

DIVERGENCE_WARNING = (
    "■■ Signal conflict: strong financial health but the price has been "
    "declining recently. Investigate why before researching further."
)

VOLUME_LINE = (
    "Trading activity: {VOLUME_LABEL}."
)

CONFIDENCE_LINE = (
    "Confidence: {CONFIDENCE_LABEL} ({CONFIDENCE_SCORE}/100)"
)

PRICE_LINE_UP = (
    "Price: ${PRICE} ▲ +{CHANGE_PCT}% today"
)

PRICE_LINE_DOWN = (
    "Price: ${PRICE} ▼ {CHANGE_PCT}% today"
)

PRICE_LINE_FLAT = (
    "Price: ${PRICE}  (flat today)"
)

PRICE_UNAVAILABLE = (
    "Price: not available"
)

SECTOR_ROTATION_NOTE = (
    "The {SECTOR} sector is {ROTATION_LABEL} — {ROTATION_DETAIL}."
)

MARKET_PULSE_LINE = (
    "{INDEX_NAME}:  {VALUE:,.0f}  {ARROW} {CHANGE_SIGN}{CHANGE_PCT}%  {LABEL}"
)

TODAY_STORY_SENTENCE = (
    "{SECTOR_PLAIN} stocks are {DIRECTION_PLAIN} today following news about {EVENT_PLAIN}."
)

CLOSING_WATCH_EARNINGS = (
    "■ {COMPANY} ({TICKER}) — earnings announcement in {DAYS} days."
)

CLOSING_WATCH_ROTATION = (
    "■ {SECTOR_PLAIN} sector is {ROTATION_LABEL} — worth monitoring."
)

CLOSING_FULL_RANKED_ROW = (
    "{RANK}. {COMPANY} ({TICKER}) — {SECTOR_PLAIN} — "
    "${PRICE} {ARROW}{CHANGE_PCT}% — Confidence: {CONF_LABEL} ({CONF_SCORE}/100) — "
    "Risk: {RISK_LABEL}"
)

DATA_UNAVAILABLE = "not available"


# ── Event plain English lookup ───────────────────────────────────────────────

EVENT_PLAIN = {
    'interest_rate_increase':     'central bank raising interest rates',
    'interest_rate_decrease':     'central bank cutting interest rates',
    'inflation_increase':         'rising inflation data',
    'geopolitical_conflict':      'geopolitical tensions and conflict news',
    'geopolitical_resolution':    'easing of international tensions',
    'oil_supply_disruption':      'disruptions to global oil supply',
    'oil_supply_increase':        'increased oil supply announcements',
    'recession_signal':           'economic slowdown signals',
    'strong_jobs_report':         'strong employment data',
    'weak_jobs_report':           'weak employment data',
    'ai_investment_surge':        'increased AI and technology investment',
    'semiconductor_shortage':     'semiconductor supply constraints',
    'supply_chain_disruption':    'global supply chain disruptions',
    'bank_failure_credit_crisis': 'banking sector stress',
    'strong_earnings_season':     'strong corporate earnings results',
    'weak_earnings_season':       'disappointing corporate earnings',
    'tariff_increase':            'new or increased trade tariffs',
    'tariff_reduction':           'reduction of trade tariffs',
    'currency_usd_strengthening': 'strengthening US dollar',
    # fallback — used when event type not in list
    '_unknown':                   'detected market news',
}


# ── Risk reason lookup ───────────────────────────────────────────────────────

RISK_REASONS = {
    'de_too_high':        'carries more debt than most companies in its sector',
    'high_beta':          'its price tends to move more sharply than the overall market',
    'low_volume':         'fewer shares are traded daily — can be harder to buy or sell quickly',
    'earnings_proximity': 'has an earnings announcement coming soon — added short-term uncertainty',
    'drawdown_high':      'has declined significantly from its recent highest price',
    'margin_weakness':    'keeps a smaller portion of revenue as profit than peers',
    'eps_instability':    'its quarterly earnings have been inconsistent recently',
}


# ── Sector plain English names ───────────────────────────────────────────────

SECTOR_PLAIN = {
    'technology':              'Technology',
    'healthcare':              'Healthcare',
    'financials':              'Financial Services',
    'consumer_discretionary':  'Consumer',
    'consumer_staples':        'Consumer Staples',
    'industrials':             'Industrial',
    'materials':               'Materials',
    'energy':                  'Energy',
    'utilities':               'Utilities',
    'real_estate':             'Real Estate',
    'communication_services':  'Communications',
    'semiconductors':          'Semiconductors',
    'defense':                 'Defense',
}


# ── Direction plain English ───────────────────────────────────────────────────

DIRECTION_PLAIN = {
    'positive': 'moving higher',
    'negative': 'moving lower',
    'neutral':  'trading sideways',
}

DIRECTION_ARROW = {
    'Rising':      '▲',
    'Falling':     '▼',
    'Flat':        '–',
    'unavailable': '–',
}


# ── Confidence label lookup ───────────────────────────────────────────────────

def confidence_label(score: float | int) -> str:
    """Returns plain English confidence label from composite confidence score."""
    if score >= 75:
        return 'STRONG'
    elif score >= 50:
        return 'MODERATE'
    elif score >= 35:
        return 'WEAK'
    return 'LOW'


# ── Debt label from debt-to-equity ───────────────────────────────────────────

def debt_label(de_ratio: float | None) -> str:
    """Plain English debt description from D/E ratio."""
    if de_ratio is None:
        return 'an unknown amount of'
    if de_ratio < 0.3:
        return 'very little'
    if de_ratio < 0.8:
        return 'a modest amount of'
    if de_ratio < 1.5:
        return 'a moderate amount of'
    if de_ratio < 2.5:
        return 'a significant amount of'
    return 'a high level of'


# ── Risk section assignment ───────────────────────────────────────────────────

def risk_section(risk_score: float) -> str:
    """Returns 'LOW RISK' or 'MODERATE RISK' based on score."""
    return 'LOW RISK' if risk_score <= 40 else 'MODERATE RISK'


# ── Render helpers ────────────────────────────────────────────────────────────

def render_price_line(price: float | None, change_pct: float | None) -> str:
    """Renders a price line with direction arrow."""
    if price is None:
        return PRICE_UNAVAILABLE
    price_str = f'{price:,.2f}'
    if change_pct is None:
        return f'Price: ${price_str}'
    if change_pct > 0.05:
        return PRICE_LINE_UP.format(PRICE=price_str, CHANGE_PCT=f'{change_pct:.1f}')
    elif change_pct < -0.05:
        return PRICE_LINE_DOWN.format(PRICE=price_str, CHANGE_PCT=f'{abs(change_pct):.1f}')
    return PRICE_LINE_FLAT.format(PRICE=price_str)


def render_market_pulse_line(name: str, data: dict) -> str:
    """Renders one index line for the Market Pulse block."""
    value      = data.get('value')
    change_pct = data.get('change_pct')
    label      = data.get('label', 'unavailable')

    if value is None:
        return f'{name}:  unavailable'

    arrow      = DIRECTION_ARROW.get(label, '–')
    change_abs = abs(change_pct) if change_pct is not None else 0.0
    sign       = '+' if (change_pct or 0) >= 0 else ''

    return (
        f'{name}:  {value:>10,.0f}  {arrow} {sign}{change_abs:.1f}%  {label}'
    )


def render_event_plain(event_type: str) -> str:
    """Converts event type code to plain English. Falls back gracefully."""
    return EVENT_PLAIN.get(event_type, EVENT_PLAIN['_unknown'])


def render_sector_plain(sector: str) -> str:
    """Returns plain English sector name."""
    return SECTOR_PLAIN.get(sector, sector.replace('_', ' ').title())


def render_company_intro(company: str, sector: str, direction: str, event_type: str) -> str:
    return COMPANY_INTRO.format(
        COMPANY     = company,
        SECTOR      = render_sector_plain(sector),
        DIRECTION   = DIRECTION_PLAIN.get(direction, direction),
        EVENT_PLAIN = render_event_plain(event_type),
    )


def render_financial_health(margin_pct: float | None, de_ratio: float | None) -> str:
    d_label = debt_label(de_ratio)
    if margin_pct is not None:
        return FINANCIAL_HEALTH.format(
            MARGIN_PCT = f'{margin_pct:.0f}',
            DEBT_LABEL = d_label,
        )
    return FINANCIAL_HEALTH_NO_MARGIN.format(DEBT_LABEL=d_label)


def render_risk_reasons(risk_components: dict, risk_score: float, drawdown_pct: float | None) -> list[str]:
    """
    Derives top 1-2 risk reason strings from a risk_components dict.
    Returns list of plain English strings (max 2).
    """
    reasons = []

    # Check each risk factor and map to readable reason
    if risk_components.get('debt', 0) > 60:
        reasons.append(RISK_REASONS['de_too_high'])
    if risk_components.get('volatility', 0) > 60:
        reasons.append(RISK_REASONS['high_beta'])
    if risk_components.get('liquidity', 0) > 60:
        reasons.append(RISK_REASONS['low_volume'])
    if risk_components.get('eps', 0) > 60:
        reasons.append(RISK_REASONS['eps_instability'])
    if risk_components.get('margin', 0) > 60:
        reasons.append(RISK_REASONS['margin_weakness'])
    if drawdown_pct is not None and drawdown_pct > 20:
        reasons.append(RISK_REASONS['drawdown_high'])

    # If nothing triggered but score still moderate, use generic
    if not reasons and risk_score > 40:
        reasons.append('shows mixed signals across risk indicators')

    return reasons[:2]  # max 2 reasons


def render_moderate_risk_block(risk_components: dict, risk_score: float, drawdown_pct: float | None) -> str:
    """Returns formatted moderate risk explanation string."""
    reasons = render_risk_reasons(risk_components, risk_score, drawdown_pct)
    if len(reasons) >= 2:
        return MODERATE_RISK_REASON.format(
            RISK_REASON_1 = reasons[0].capitalize(),
            RISK_REASON_2 = reasons[1].capitalize() + '.',
        )
    elif reasons:
        return MODERATE_RISK_REASON_SINGLE.format(RISK_REASON_1=reasons[0].capitalize())
    return ''
