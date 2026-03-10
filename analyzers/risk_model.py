"""
analyzers/risk_model.py — §20.1 Updated risk scoring with drawdown component.
7 components totalling 100%. Final score multiplied by VIX regime risk_mult.

Component weights: debt(22%) vol(18%) liq(18%) eps(14%) margin(9%) mcap(9%) drawdown(10%)
"""

import statistics
from utils.logger import get_logger
from config import RISK_WEIGHTS

log = get_logger('risk_model')

# Days before earnings that triggers proximity penalty
EARNINGS_PROXIMITY_DAYS_WARN = 5
EARNINGS_PROXIMITY_PENALTY   = 10


def compute_risk_score(fin: dict, regime: dict, drawdown_score: float | None = None) -> dict:
    """
    Computes composite risk score 0-100 (lower is better/safer).

    Args:
        fin:            dict from financial_parser.get_financials()
        regime:         dict from market_regime.get_regime()
        drawdown_score: 0-1 from drawdown_risk.compute_drawdown_risk()

    Returns:
        {'risk_score': float, 'components': dict, 'risk_label': str,
         'earnings_warning': bool, 'divergence_warning': bool}
    """
    components = {}

    # ── 1. Debt risk (22%) ──────────────────────────────────────────────────
    d_e = fin.get('debt_to_equity')
    if d_e is not None:
        try:
            debt_raw = min(100, max(0, float(d_e) * 25))
        except (TypeError, ValueError):
            debt_raw = 50.0
    else:
        debt_raw = 50.0  # neutral when missing
    components['debt'] = round(debt_raw, 1)

    # ── 2. Volatility (18%) — beta ──────────────────────────────────────────
    beta = fin.get('beta')
    if beta is not None:
        try:
            vol_raw = min(100, max(0, (float(beta) - 0.5) * 50))
        except (TypeError, ValueError):
            vol_raw = 50.0
    else:
        vol_raw = 50.0
    components['volatility'] = round(vol_raw, 1)

    # ── 3. Liquidity risk (18%) — average volume ────────────────────────────
    vol_m = (fin.get('avg_volume') or 0) / 1_000_000  # millions
    liq_raw = max(0, 100 - (vol_m * 8))
    components['liquidity'] = round(min(100, liq_raw), 1)

    # ── 4. Earnings instability (14%) — quarterly EPS std/mean ─────────────
    eps_list = fin.get('eps_quarterly', [])
    if eps_list and len(eps_list) >= 3:
        try:
            mean = abs(sum(eps_list) / len(eps_list))
            std  = statistics.stdev(eps_list)
            eps_raw = min(100, (std / (mean + 1e-9)) * 50) if mean > 0 else 50.0
        except Exception:
            eps_raw = 50.0
    else:
        eps_raw = 50.0
    components['eps'] = round(eps_raw, 1)

    # ── 5. Margin weakness (9%) ─────────────────────────────────────────────
    margin = fin.get('profit_margin')
    if margin is not None:
        try:
            margin_raw = max(0, 100 - float(margin) * 4)
        except (TypeError, ValueError):
            margin_raw = 50.0
    else:
        margin_raw = 50.0
    components['margin'] = round(min(100, margin_raw), 1)

    # ── 6. Market cap risk (9%) ─────────────────────────────────────────────
    cap_b = (fin.get('market_cap') or 0) / 1_000_000_000
    cap_raw = max(0, 100 - cap_b * 8)
    components['mcap'] = round(min(100, cap_raw), 1)

    # ── 7. Drawdown risk (10%) ──────────────────────────────────────────────
    # Higher drawdown = higher risk, so use (1 - drawdown_score)
    dd_score = drawdown_score if drawdown_score is not None else 0.5
    components['drawdown'] = round((1.0 - dd_score) * 100, 1)

    # ── Weighted raw score ──────────────────────────────────────────────────
    weights = RISK_WEIGHTS
    raw = (
        components['debt']      * weights['debt']     +
        components['volatility'] * weights['volatility'] +
        components['liquidity'] * weights['liquidity']  +
        components['eps']       * weights['eps']       +
        components['margin']    * weights['margin']    +
        components['mcap']      * weights['mcap']      +
        components['drawdown']  * weights['drawdown']
    )

    # ── Earnings proximity penalty ──────────────────────────────────────────
    earnings_warning = False
    earnings_penalty = 0
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
                earnings_penalty = EARNINGS_PROXIMITY_PENALTY
                log.info(f'Earnings proximity penalty: {days} days away')
        except Exception:
            pass

    # ── Momentum divergence flag ────────────────────────────────────────────
    # Flag when financials look strong but price is declining
    divergence_warning = False
    if components['debt'] < 30 and components['margin'] < 40:
        # looks financially healthy
        momentum_ok = fin.get('_price_trend_negative', False)
        if momentum_ok:
            divergence_warning = True

    # ── Apply regime multiplier ─────────────────────────────────────────────
    risk_mult   = regime.get('risk_mult', 1.0)
    final_score = min(100, (raw + earnings_penalty) * risk_mult)

    # Label
    if final_score < 30:   risk_label = 'Low Risk'
    elif final_score < 55: risk_label = 'Moderate Risk'
    else:                  risk_label = 'High Risk'

    log.info(f'Risk score: raw={raw:.1f} penalty={earnings_penalty} mult={risk_mult} final={final_score:.1f}')

    return {
        'risk_score':          round(final_score, 1),
        'raw_score':           round(raw, 1),
        'components':          components,
        'risk_label':          risk_label,
        'earnings_warning':    earnings_warning,
        'divergence_warning':  divergence_warning,
        'regime_mult_applied': risk_mult,
    }
