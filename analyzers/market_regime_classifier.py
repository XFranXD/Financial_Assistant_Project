"""
analyzers/market_regime_classifier.py
Classifies the current market regime as BULL, NEUTRAL, or BEAR from
three pre-fetched inputs: SPY vs 200d SMA, VIX level, market breadth %.

Scoring (each condition contributes independently):
  SPY above 200d SMA       → +1
  SPY below 200d SMA       → -1
  SPY unavailable          →  0
  VIX < 20                 → +1
  VIX > 30                 → -1
  VIX 20-30 or unavailable →  0
  breadth_pct > 60         → +1
  breadth_pct < 40         → -1
  breadth_pct 40-60 or N/A →  0

Classification:
  score +2 or +3  → BULL
  score  0 or +1  → NEUTRAL
  score -1 to -3  → BEAR

Non-fatal — returns NEUTRAL on any exception.
"""

from utils.logger import get_logger

log = get_logger('market_regime_classifier')

VIX_BULL_THRESHOLD   = 20.0
VIX_BEAR_THRESHOLD   = 30.0
BREADTH_BULL_PCT     = 60.0
BREADTH_BEAR_PCT     = 40.0


def get_market_regime_classification(
    spy_sma_result: dict,
    vix_value:      float | None,
    breadth_pct:    float | None,
) -> dict:
    """
    Classifies market regime from pre-fetched inputs.

    Args:
        spy_sma_result: dict from get_spy_vs_200d() — must have 'spy_above_200d' key
        vix_value:      float | None — current VIX level from existing get_regime()
        breadth_pct:    float | None — % of basket stocks above 200d SMA (0-100)

    Returns:
        {
            'market_regime': 'BULL' | 'NEUTRAL' | 'BEAR',
            'regime_score':  int,    # raw score -3 to +3
            'regime_inputs': {
                'spy_above_200d': bool | None,
                'vix':            float | None,
                'breadth_pct':    float | None,
            }
        }
    On any exception: returns NEUTRAL with score 0. Never raises.
    """
    _default = {
        'market_regime': 'NEUTRAL',
        'regime_score':  0,
        'regime_inputs': {
            'spy_above_200d': None,
            'vix':            vix_value,
            'breadth_pct':    breadth_pct,
        },
    }

    try:
        spy_above = (spy_sma_result or {}).get('spy_above_200d')
        score     = 0

        # ── SPY vs 200d SMA ───────────────────────────────────────────────
        if spy_above is True:
            score += 1
        elif spy_above is False:
            score -= 1
        # None → 0 (no contribution)

        # ── VIX ───────────────────────────────────────────────────────────
        if vix_value is not None:
            if vix_value < VIX_BULL_THRESHOLD:
                score += 1
            elif vix_value > VIX_BEAR_THRESHOLD:
                score -= 1
        # 20-30 or None → 0 (no contribution)

        # ── Market breadth ────────────────────────────────────────────────
        if breadth_pct is not None:
            if breadth_pct > BREADTH_BULL_PCT:
                score += 1
            elif breadth_pct < BREADTH_BEAR_PCT:
                score -= 1
        # 40-60 or None → 0 (no contribution)

        # ── Classification ────────────────────────────────────────────────
        if score >= 2:
            regime = 'BULL'
        elif score <= -1:
            regime = 'BEAR'
        else:
            regime = 'NEUTRAL'

        log.info(
            f'[MRC] regime={regime} score={score} '
            f'spy_above={spy_above} vix={vix_value} breadth_pct={breadth_pct}'
        )

        return {
            'market_regime': regime,
            'regime_score':  score,
            'regime_inputs': {
                'spy_above_200d': spy_above,
                'vix':            vix_value,
                'breadth_pct':    breadth_pct,
            },
        }

    except Exception as e:
        log.warning(f'[MRC] Classification failed (non-fatal): {e}')
        return _default
