from contracts.paper_trading_schema import PT_EXIT_STOP, PT_EXIT_TARGET

PESSIMISTIC_PRIORITY = "stop_first"
# When both stop_loss and price_target are hit on the same candle,
# stop is always assumed to have hit first (pessimistic inference).
# This prevents inflating the system's apparent win rate.

def infer_exit(
    low: float,
    high: float,
    stop_loss: float,
    price_target: float,
) -> tuple[str | None, float | None]:
    """
    Apply pessimistic OHLC inference to determine if a trade exits.

    Rules (in priority order):
    1. If low <= stop_loss AND high >= price_target on same candle:
       → return (PT_EXIT_STOP, stop_loss)   # pessimistic: stop assumed first
    2. If low <= stop_loss:
       → return (PT_EXIT_STOP, stop_loss)
    3. If high >= price_target:
       → return (PT_EXIT_TARGET, price_target)
    4. Neither hit:
       → return (None, None)

    Args:
        low:          candle low price
        high:         candle high price
        stop_loss:    trade stop loss level
        price_target: trade price target level

    Returns:
        (exit_reason, exit_price) or (None, None) if no exit triggered
    """
    if low <= stop_loss and high >= price_target:
        return (PT_EXIT_STOP, stop_loss)
    if low <= stop_loss:
        return (PT_EXIT_STOP, stop_loss)
    if high >= price_target:
        return (PT_EXIT_TARGET, price_target)
    return (None, None)
