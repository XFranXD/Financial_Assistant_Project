"""
price_structure/execution_layer.py
Computes concrete trade execution levels from Sub4 structural data.
Pure arithmetic — no API calls, no yfinance, no ML.
Inputs: current_price, nearest_support, nearest_resistance, entry_quality.
Outputs: entry_price, stop_loss, price_target, risk_reward_ratio.
If R/R < MIN_RR_THRESHOLD, entry_quality is overridden to WEAK.
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
    Computes concrete trade execution levels from Sub4 structural data.

    Returns:
        {
            'entry_price':       float | None,
            'stop_loss':         float | None,
            'price_target':      float | None,
            'risk_reward_ratio': float | None,
            'entry_quality':     str,   # may be overridden to WEAK
            'rr_override':       bool,  # True if entry_quality was overridden
        }
    """
    defaults = {
        'entry_price':       None,
        'stop_loss':         None,
        'price_target':      None,
        'risk_reward_ratio': None,
        'entry_quality':     entry_quality,
        'rr_override':       False,
    }

    try:
        # entry_price = current_price (always — we don't manufacture a better price)
        entry_price = current_price if current_price and current_price > 0 else None

        # stop_loss = nearest_support * (1 - STOP_BUFFER_PCT)
        # → None if nearest_support is None or nearest_support <= 0
        if nearest_support is not None and nearest_support > 0:
            stop_loss = nearest_support * (1 - STOP_BUFFER_PCT)
        else:
            stop_loss = None

        # price_target = nearest_resistance
        # → None if nearest_resistance is None or nearest_resistance <= 0
        if nearest_resistance is not None and nearest_resistance > 0:
            price_target = nearest_resistance
        else:
            price_target = None

        # risk_reward_ratio:
        #   → None if any of entry_price, stop_loss, price_target is None
        #   → None if entry_price <= stop_loss (no valid setup)
        #   → (price_target - entry_price) / (entry_price - stop_loss)
        #   → round to 2 decimal places
        risk_reward_ratio = None
        if entry_price is not None and stop_loss is not None and price_target is not None:
            if entry_price > stop_loss:
                rr = (price_target - entry_price) / (entry_price - stop_loss)
                risk_reward_ratio = round(rr, 2)

        # entry_quality override:
        #   → If risk_reward_ratio is not None and risk_reward_ratio < MIN_RR_THRESHOLD:
        #         entry_quality = 'WEAK'
        #         rr_override   = True
        #   → Otherwise: entry_quality unchanged, rr_override = False
        rr_override = False
        if risk_reward_ratio is not None and risk_reward_ratio < MIN_RR_THRESHOLD:
            entry_quality = 'WEAK'
            rr_override = True

        return {
            'entry_price':       entry_price,
            'stop_loss':         stop_loss,
            'price_target':      price_target,
            'risk_reward_ratio': risk_reward_ratio,
            'entry_quality':     entry_quality,
            'rr_override':       rr_override,
        }

    except Exception:
        return defaults
