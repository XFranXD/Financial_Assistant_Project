"""
analyzers/opportunity_model.py — §20.2 Three-bucket atomic opportunity model.
Buckets: Fundamentals (opp_financial_health) 40% |
         Momentum    (opp_price_trend)       40% |
         Confirmation(opp_market_confirmation) 20%

Returns three named atomic bucket scores. No aggregate opportunity_score.
No composite_confidence. No ma_sc (removed — was a duplicate of ram_score).
Bucket 2 Momentum weights after ma_sc removal:
  ram_sc 25% → 25% | mtf_sc 25% → 40% | p20_sc 20% → 20% | rs_sc 15% → 15%
"""

from utils.logger import get_logger

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
    Computes three atomic opportunity bucket scores.

    Returns:
        {
            'opp_financial_health':     float (0-100),  — Bucket 1
            'opp_price_trend':          float (0-100),  — Bucket 2
            'opp_market_confirmation':  float (0-100),  — Bucket 3
        }
    No aggregate opportunity_score is returned. Consume individual buckets downstream.
    """

    # ── BUCKET 1: Financial Health (40% weight, named opp_financial_health) ─
    # Revenue growth YoY (32.5% of bucket)
    rev_ttm  = fin.get('revenue_ttm')
    rev_prev = fin.get('revenue_prev_year')
    if rev_ttm and rev_prev and float(rev_prev) > 0:
        rev_growth = ((float(rev_ttm) - float(rev_prev)) / float(rev_prev)) * 100
        rev_score  = min(100, max(0, rev_growth * 2.5))
    else:
        rev_score = 50.0

    # Profit margin (22.5% of bucket)
    margin    = _safe(fin.get('profit_margin'), 50.0 / 5.0)
    margin_sc = min(100, max(0, margin * 5.0))

    # EPS growth YoY (22.5% of bucket) — TTM vs prior 4 quarters
    eps_list = fin.get('eps_quarterly', [])
    if len(eps_list) >= 5:
        recent = sum(eps_list[:4])
        older  = sum(eps_list[1:5])
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
        rev_score * 0.325 +
        margin_sc * 0.225 +
        eps_sc    * 0.225 +
        pe_sc     * 0.225
    )
    opp_financial_health = round(min(100, b1), 1)

    # ── BUCKET 2: Price Trend (40% weight, named opp_price_trend) ──────────
    # ma_sc REMOVED — was derived from ram_score (duplicate signal).
    # Its 15% weight redistributed to mtf_sc (now 40% of bucket).
    #
    # ram_sc:  25% — risk-adjusted momentum
    # mtf_sc:  40% — multi-timeframe momentum (absorbs former ma_sc weight)
    # p20_sc:  20% — price momentum 20d
    # rs_sc:   15% — relative strength vs sector median

    ram_sc = _safe(ram_score, 0.5) * 100
    mtf_sc = _safe(mtf_score, 0.5) * 100

    ret_20d = None
    p20_sc  = min(100, max(0, 50 + _safe(ret_20d, 0) * 5))

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
        mtf_sc * 0.40 +
        p20_sc * 0.20 +
        rs_sc  * 0.15
    )
    opp_price_trend = round(min(100, b2), 1)

    # ── BUCKET 3: Market Confirmation (20% weight, named opp_market_confirmation)
    # Volume confirmation (40% of bucket)
    vol_sc = _safe(volume_score, 0.5) * 100

    # Relative strength vs ETF (35%)
    etf_ret = _safe(etf_return, 0)
    etf_sc  = min(100, max(0, 50 + etf_ret * 3))

    # Sector MA breadth (25%)
    bma_sc = _safe(breadth_ma_score, 0.5) * 100

    b3 = (
        vol_sc * 0.40 +
        etf_sc * 0.35 +
        bma_sc * 0.25
    )
    opp_market_confirmation = round(min(100, b3), 1)

    log.info(
        f'Opp buckets: financial_health={opp_financial_health} '
        f'price_trend={opp_price_trend} '
        f'market_confirmation={opp_market_confirmation}'
    )

    return {
        'opp_financial_health':    opp_financial_health,
        'opp_price_trend':         opp_price_trend,
        'opp_market_confirmation': opp_market_confirmation,
    }
