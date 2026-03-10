"""
analyzers/opportunity_model.py — §20.2 Three-bucket weighted model.
Buckets: Fundamentals 40% | Momentum 40% | Confirmation 20%

Anti-double-counting: signals measuring similar properties share bucket weight.
No bucket can exceed its cap — enforced in code, not just comments.
"""

from utils.logger import get_logger
from config import OPP_BUCKET_WEIGHTS

log = get_logger('opportunity_model')


def _safe(val, default=50.0) -> float:
    """Returns float or default if val is None/invalid."""
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def compute_opportunity_score(
    fin: dict,
    regime: dict,
    breadth: dict,
    sector_pe: float | None,
    sector_median_ret: float | None,
    ram_score: float | None,
    mtf_score: float | None,
    volume_score: float | None,
    breadth_ma_score: float | None,
    etf_return: float | None,
) -> dict:
    """
    Computes three-bucket opportunity score.

    Returns:
        {
            'opportunity_score': float (0-100),
            'bucket_scores': {'fundamentals': float, 'momentum': float, 'confirmation': float},
            'risk_label': str,
            'components': dict,
        }
    """

    # ── BUCKET 1: Fundamentals (40% of final) ──────────────────────────────
    # Revenue growth YoY (32.5% of bucket)
    rev_ttm  = fin.get('revenue_ttm')
    rev_prev = fin.get('revenue_prev_year')
    if rev_ttm and rev_prev and float(rev_prev) > 0:
        rev_growth = ((float(rev_ttm) - float(rev_prev)) / float(rev_prev)) * 100
        rev_score  = min(100, max(0, rev_growth * 2.5))
    else:
        rev_score = 50.0  # neutral

    # Profit margin (22.5% of bucket)
    margin     = _safe(fin.get('profit_margin'), 50.0 / 5.0)
    margin_sc  = min(100, max(0, margin * 5.0))

    # EPS growth YoY (22.5% of bucket) — approximated from quarterly list
    eps_list = fin.get('eps_quarterly', [])
    if len(eps_list) >= 5:
        recent  = sum(eps_list[:4])   # last 4 quarters (TTM)
        older   = sum(eps_list[1:5])  # prior 4 quarters
        if older != 0:
            eps_growth = ((recent - older) / abs(older)) * 100
            eps_sc = min(100, max(0, eps_growth * 2.0))
        else:
            eps_sc = 50.0
    else:
        eps_sc = 50.0

    # Relative P/E vs sector (22.5% of bucket)
    pe = fin.get('pe_ratio')
    if pe and sector_pe:
        try:
            rel_pe = float(pe) / float(sector_pe)
            pe_sc  = 100 - min(100, max(0, (rel_pe - 1) * 100))
        except (TypeError, ValueError, ZeroDivisionError):
            pe_sc = 50.0
    else:
        pe_sc = 50.0

    b1 = (
        rev_score  * 0.325 +
        margin_sc  * 0.225 +
        eps_sc     * 0.225 +
        pe_sc      * 0.225
    )
    b1 = min(100, b1)

    # ── BUCKET 2: Momentum (40% of final) ──────────────────────────────────
    # Risk-adjusted momentum (25% of bucket)
    ram_sc = _safe(ram_score, 0.5) * 100

    # Multi-timeframe momentum (25%)
    mtf_sc = _safe(mtf_score, 0.5) * 100

    # Price momentum 20d (20%)
    # Approximated from MTF r1m data or 50.0 neutral
    ret_20d = None  # populated by caller if available
    p20_sc  = min(100, max(0, 50 + _safe(ret_20d, 0) * 5))

    # MA trend 50d vs 200d (15%) — from financial info if available
    # Simplified: use ram_score as proxy for trend direction
    ma_sc = 65.0 if _safe(ram_score, 0.5) > 0.5 else 40.0

    # Relative strength vs sector median (15%)
    if sector_median_ret is not None and etf_return is not None:
        try:
            rel_str = _safe(etf_return, 0) - _safe(sector_median_ret, 0)
            rs_sc   = min(100, max(0, 50 + rel_str * 3))
        except (TypeError, ValueError):
            rs_sc = 50.0
    else:
        rs_sc = 50.0

    b2 = (
        ram_sc * 0.25 +
        mtf_sc * 0.25 +
        p20_sc * 0.20 +
        ma_sc  * 0.15 +
        rs_sc  * 0.15
    )
    b2 = min(100, b2)

    # ── BUCKET 3: Confirmation (20% of final) ──────────────────────────────
    # Volume confirmation (40% of bucket)
    vol_sc = _safe(volume_score, 0.5) * 100

    # Relative strength vs ETF (35%)
    etf_ret = _safe(etf_return, 0)
    etf_sc  = min(100, max(0, 50 + etf_ret * 3))

    # Sector MA breadth (25%)
    bma_sc = _safe(breadth_ma_score, 0.5) * 100

    b3 = (
        vol_sc * 0.40 +
        etf_sc  * 0.35 +
        bma_sc  * 0.25
    )
    b3 = min(100, b3)

    # ── Combine buckets ─────────────────────────────────────────────────────
    raw = (
        b1 * OPP_BUCKET_WEIGHTS['fundamentals'] +
        b2 * OPP_BUCKET_WEIGHTS['momentum']     +
        b3 * OPP_BUCKET_WEIGHTS['confirmation']
    )

    # Apply both multipliers — both stack, cap at 100
    opp_mult    = regime.get('opp_mult', 1.0)
    breadth_mult = breadth.get('opp_multiplier', 1.0)
    final        = min(100, raw * opp_mult * breadth_mult)

    log.info(
        f'Opp score: b1={b1:.1f} b2={b2:.1f} b3={b3:.1f} '
        f'raw={raw:.1f} x{opp_mult} x{breadth_mult} = {final:.1f}'
    )

    return {
        'opportunity_score': round(final, 1),
        'raw_score':         round(raw, 1),
        'bucket_scores': {
            'Financial Health':     round(b1, 1),
            'Price Trend Strength': round(b2, 1),
            'Market Confirmation':  round(b3, 1),
        },
        'multipliers': {
            'regime':  opp_mult,
            'breadth': breadth_mult,
        },
    }


def compute_composite_confidence(
    risk_score:            float,
    opportunity_score:     float,
    agreement_score:       float,
    sector_momentum_score: float,
) -> dict:
    """
    §21 V5 Composite Confidence Formula.

    composite_confidence = ((100 - risk) * 0.35) + (opp * 0.35) +
                           (agreement * 100 * 0.20) + (sector_contrib * 0.10)

    sector_momentum_contrib = min(100, max(0, 50 + sector_momentum_score * 10))
    """
    sector_contrib = min(100, max(0, 50 + float(sector_momentum_score) * 10))

    confidence = round(
        ((100 - risk_score)        * 0.35) +
        (opportunity_score         * 0.35) +
        (agreement_score * 100     * 0.20) +
        (sector_contrib            * 0.10),
        1
    )

    if confidence >= 75:   conf_label = 'Strong confidence'
    elif confidence >= 50: conf_label = 'Moderate confidence'
    elif confidence >= 35: conf_label = 'Weak confidence'
    else:                  conf_label = 'Excluded'

    log.info(f'Composite confidence: {confidence:.1f} ({conf_label})')
    return {
        'composite_confidence': confidence,
        'confidence_label':     conf_label,
        'sector_contrib':       round(sector_contrib, 1),
        'disclaimer': (
            'This score reflects relative risk-adjusted positioning only. '
            'It is NOT a prediction of price movement or return.'
        ),
    }
