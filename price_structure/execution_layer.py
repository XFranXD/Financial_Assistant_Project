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

                # ── Geometric invalidity guard ────────────────────────────
                # reward <= 0 means price_target is at or below entry —
                # the trade structure is inverted or flat and cannot exist.
                # risk <= 0 is already blocked by entry_price > stop_loss
                # above, but guarded here explicitly for safety.
                # Nullify all levels so no downstream layer receives a
                # geometrically impossible trade structure. This is distinct
                # from sub-threshold R:R (0 < R:R < MIN_RR_THRESHOLD) which
                # is a quality failure, not a structural one — those keep
                # their levels and receive entry_quality = WEAK below.
                if reward <= 0 or risk <= 0:
                    return {
                        'entry_price':       None,
                        'stop_loss':         None,
                        'price_target':      None,
                        'risk_reward_ratio': None,
                        'entry_quality':     'WEAK',
                        'rr_override':       True,
                    }

                # Round to 4dp — 2dp causes relative errors exceeding 5% on
                # sub-0.05 R:R values (e.g. 0.0188 -> 0.02 = 6.3% error),
                # which triggers false A_RANGE_RR_RECOMPUTE_DELTA FSV flags.
                # 4dp is sufficient for all realistic R:R values.
                risk_reward_ratio = round(reward / risk, 4)

        # ── R/R threshold flag: report separately, do NOT mutate entry_quality ──
        # entry_quality reflects price structure (entry_classifier.py decision).
        # R:R reflects execution geometry. These are independent judgments.
        # rr_below_threshold signals that geometry is unfavorable for execution
        # without destroying the structural quality reading.
        # rr_override kept for backward compatibility (FSV notice layer reads it).
        rr_below_threshold = (
            risk_reward_ratio is not None
            and risk_reward_ratio < MIN_RR_THRESHOLD
        )
        rr_override = rr_below_threshold  # alias — same signal, legacy name

        return {
            'entry_price':        entry_price,
            'stop_loss':          stop_loss,
            'price_target':       price_target,
            'risk_reward_ratio':  risk_reward_ratio,
            'entry_quality':      entry_quality,       # unchanged — structural reading preserved
            'rr_override':        rr_override,         # True when R:R < 2.0 (legacy compat)
            'rr_below_threshold': rr_below_threshold,  # explicit flag for downstream layers
        }

    except Exception:
        return _safe