from contracts.paper_trading_schema import (
    PT_LIVE_PNL_PCT, PT_EXPECTED_RETURN_PCT,
    PT_ERROR_PCT, PT_DIRECTION_CORRECT,
    PT_STATUS, PT_STATUS_CLOSED, PT_IS_TEST,
)
from utils.logger import get_logger

log = get_logger(__name__)

def compute_comparison(trade: dict) -> dict:
    live_pnl_pct = trade.get(PT_LIVE_PNL_PCT)
    expected_return_pct = trade.get(PT_EXPECTED_RETURN_PCT)

    if live_pnl_pct is None or expected_return_pct is None:
        return {PT_ERROR_PCT: None, PT_DIRECTION_CORRECT: None}

    try:
        live_pnl_pct = float(live_pnl_pct)
        expected_return_pct = float(expected_return_pct)
    except (ValueError, TypeError):
        return {PT_ERROR_PCT: None, PT_DIRECTION_CORRECT: None}

    error_pct = round(live_pnl_pct - expected_return_pct, 4)

    def _sign(x):
        return 1 if x > 0 else (-1 if x < 0 else 0)

    direction_correct = _sign(live_pnl_pct) == _sign(expected_return_pct)

    return {PT_ERROR_PCT: error_pct, PT_DIRECTION_CORRECT: direction_correct}

def enrich_closed_trades(trades: list[dict]) -> list[dict]:
    for trade in trades:
        if trade.get(PT_IS_TEST):
            continue  # test trades are never counted in signal accuracy stats
        if trade.get(PT_STATUS) == PT_STATUS_CLOSED:
            if trade.get(PT_LIVE_PNL_PCT) is not None and trade.get(PT_EXPECTED_RETURN_PCT) is not None:
                comp_result = compute_comparison(trade)
                if comp_result.get(PT_ERROR_PCT) is not None:
                    trade[PT_ERROR_PCT] = comp_result[PT_ERROR_PCT]
                    trade[PT_DIRECTION_CORRECT] = comp_result[PT_DIRECTION_CORRECT]
    return trades
