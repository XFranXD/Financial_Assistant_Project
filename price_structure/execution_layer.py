"""
price_structure/execution_layer.py
Computes concrete trade execution levels from Sub4 structural data.
Pure arithmetic — no API calls, no yfinance, no ML.

Inputs:  current_price, nearest_support, nearest_resistance, entry_quality
Outputs: entry_price, stop_loss, price_target, risk_reward_ratio,
         entry_quality (may be overridden to WEAK), rr_override (bool)

If R/R < MIN_RR_THRESHOLD, entry_quality is overridden to WEAK.
The override mutates entry_quality on the returned dict before it is
stamped onto the candidate. Original Sub4 entry_result is also mutated
in-place by price_structure_analyzer.py before the final return.
"""

MIN_RR_THRESHOLD = 2.0
STOP_BUFFER_PCT  = 0.005   # 0.5% buffer below support for stop loss


def compute_execution_levels(
    current_price:      float,
    nearest_support:    float | None,
    nearest_resistance: float | None,
    entry_quality:      str,
) -> dict:
    """
    Compute trade execution levels from Sub4 structural data.

    Returns:
        {
            'entry_price':       float | None,
            'stop_loss':         float | None,
            'price_target':      float | None,
            'risk_reward_ratio': float | None,
            'entry_quality':     str,   # may be overridden to WEAK
            'rr_override':       bool,  # True if entry_quality was overridden
        }

    All outputs default to None on any exception. Does not raise.
    """
    _safe = {
        'entry_price':       None,
        'stop_loss':         None,
        'price_target':      None,
        'risk_reward_ratio': None,
        'entry_quality':     entry_quality,
        'rr_override':       False,
    }

    try:
        # ── entry_price = current price (no manufactured price) ───────────
        if not isinstance(current_price, (int, float)) or current_price <= 0:
            return _safe
        entry_price = float(current_price)

        # ── stop_loss = nearest_support * (1 - STOP_BUFFER_PCT) ──────────
        stop_loss = None
        if nearest_support is not None and isinstance(nearest_support, (int, float)) and nearest_support > 0:
            stop_loss = float(nearest_support) * (1.0 - STOP_BUFFER_PCT)

        # ── price_target = nearest_resistance ────────────────────────────
        price_target = None
        if nearest_resistance is not None and isinstance(nearest_resistance, (int, float)) and nearest_resistance > 0:
            price_target = float(nearest_resistance)

        # ── risk_reward_ratio ─────────────────────────────────────────────
        risk_reward_ratio = None
        if entry_price is not None and stop_loss is not None and price_target is not None:
            if entry_price > stop_loss:   # valid setup: stop is below entry
                reward = price_target - entry_price
                risk   = entry_price   - stop_loss
                if risk > 0:
                    risk_reward_ratio = round(reward / risk, 2)

        # ── R/R override: downgrade entry_quality to WEAK if below threshold
        rr_override    = False
        final_eq       = entry_quality
        if risk_reward_ratio is not None and risk_reward_ratio < MIN_RR_THRESHOLD:
            final_eq    = 'WEAK'
            rr_override = True

        return {
            'entry_price':       entry_price,
            'stop_loss':         stop_loss,
            'price_target':      price_target,
            'risk_reward_ratio': risk_reward_ratio,
            'entry_quality':     final_eq,
            'rr_override':       rr_override,
        }

    except Exception:
        return _safe
        