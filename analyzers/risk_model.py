"""
analyzers/risk_model.py — §20.1 Atomic risk components. No aggregate risk_score.

Returns 7 individual component scores (0-100, higher = more risk) plus metadata.
No collapsed score is returned. Downstream code consumes components directly.
Regime multiplier applied per-component so each value is fully adjusted.

Components: debt, volatility, liquidity, eps, margin, mcap, drawdown.
"""

import statistics
from utils.logger import get_logger

log = get_logger('risk_model')

# Days before earnings that triggers proximity penalty
EARNINGS_PROXIMITY_DAYS_WARN = 5
EARNINGS_PROXIMITY_PENALTY   = 10


def compute_risk_score(fin: dict, regime: dict, drawdown_score: float | None = None) -> dict:
    """
    Computes 7 atomic risk component scores (0-100, higher = more risk).
    Regime multiplier is applied per-component so each value is fully adjusted.

    Args:
        fin:            dict from financial_parser.get_financials()
        regime:         dict from market_regime.get_regime()
        drawdown_score: 0-1 from drawdown_risk.compute_drawdown_risk()

    Returns:
        {
            'risk_component_debt':       float,
            'risk_component_volatility': float,
            'risk_component_liquidity':  float,
            'risk_component_eps':        float,
            'risk_component_margin':     float,
            'risk_component_mcap':       float,
            'risk_component_drawdown':   float,
            'earnings_warning':          bool,
            'divergence_warning':        bool,
        }
    No aggregate risk_score is returned. Consume individual components downstream.
    """
    risk_mult = regime.get('risk_mult', 1.0)

    # ── 1. Debt risk ────────────────────────────────────────────────────────
    d_e = fin.get('debt_to_equity')
    if d_e is not None:
        try:
            debt_raw = min(100, max(0, float(d_e) * 25))
        except (TypeError, ValueError):
            debt_raw = 50.0
    else:
        debt_raw = 50.0
    debt = round(min(100, debt_raw * risk_mult), 1)

    # ── 2. Volatility — beta ────────────────────────────────────────────────
    beta = fin.get('beta')
    if beta is not None:
        try:
            vol_raw = min(100, max(0, (float(beta) - 0.5) * 50))
        except (TypeError, ValueError):
            vol_raw = 50.0
    else:
        vol_raw = 50.0
    volatility = round(min(100, vol_raw * risk_mult), 1)

    # ── 3. Liquidity risk — average volume ─────────────────────────────────
    vol_m     = (fin.get('avg_volume') or 0) / 1_000_000
    liq_raw   = max(0, 100 - (vol_m * 8))
    liquidity = round(min(100, liq_raw * risk_mult), 1)

    # ── 4. Earnings instability — quarterly EPS std/mean ───────────────────
    eps_list = fin.get('eps_quarterly', [])
    if eps_list and len(eps_list) >= 3:
        try:
            mean    = abs(sum(eps_list) / len(eps_list))
            std     = statistics.stdev(eps_list)
            eps_raw = min(100, (std / (mean + 1e-9)) * 50) if mean > 0 else 50.0
        except Exception:
            eps_raw = 50.0
    else:
        eps_raw = 50.0
    eps = round(min(100, eps_raw * risk_mult), 1)

    # ── 5. Margin weakness ──────────────────────────────────────────────────
    margin_val = fin.get('profit_margin')
    if margin_val is not None:
        try:
            margin_raw = max(0, 100 - float(margin_val) * 4)
        except (TypeError, ValueError):
            margin_raw = 50.0
    else:
        margin_raw = 50.0
    margin = round(min(100, margin_raw * risk_mult), 1)

    # ── 6. Market cap risk ──────────────────────────────────────────────────
    cap_b   = (fin.get('market_cap') or 0) / 1_000_000_000
    cap_raw = max(0, 100 - cap_b * 8)
    mcap    = round(min(100, cap_raw * risk_mult), 1)

    # ── 7. Drawdown risk ────────────────────────────────────────────────────
    dd_score = drawdown_score if drawdown_score is not None else 0.5
    dd_raw   = (1.0 - dd_score) * 100
    drawdown = round(min(100, dd_raw * risk_mult), 1)

    # ── Earnings proximity warning ──────────────────────────────────────────
    earnings_warning = False
    earnings_date    = fin.get('earnings_date')
    if earnings_date:
        try:
            from datetime import datetime
            import pytz
            ed   = datetime.fromisoformat(str(earnings_date).split(' ')[0])
            now  = datetime.now(pytz.utc).replace(tzinfo=None)
            days = (ed.date() - now.date()).days
            if 0 <= days <= EARNINGS_PROXIMITY_DAYS_WARN:
                earnings_warning = True
                log.info(f'Earnings proximity warning: {days} days away')
        except Exception:
            pass

    # ── Momentum divergence flag ────────────────────────────────────────────
    divergence_warning = False
    if debt < 30 and margin < 40:
        if fin.get('_price_trend_negative', False):
            divergence_warning = True

    log.info(
        f'Risk components: debt={debt} vol={volatility} liq={liquidity} '
        f'eps={eps} margin={margin} mcap={mcap} drawdown={drawdown} '
        f'regime_mult={risk_mult}'
    )

    return {
        'risk_component_debt':       debt,
        'risk_component_volatility': volatility,
        'risk_component_liquidity':  liquidity,
        'risk_component_eps':        eps,
        'risk_component_margin':     margin,
        'risk_component_mcap':       mcap,
        'risk_component_drawdown':   drawdown,
        'earnings_warning':          earnings_warning,
        'divergence_warning':        divergence_warning,
    }
