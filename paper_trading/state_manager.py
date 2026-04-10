import copy
from paper_trading.sheets_ledger import (
    ensure_headers, read_all_trades, write_rows, update_rows
)
from contracts.paper_trading_schema import (
    PT_TICKER, PT_STATUS, PT_STATUS_OPEN, PT_STATUS_CLOSED, PT_STATUS_DROPPED,
    PT_LAST_UPDATED_RUN, PT_DATA_VALID, PT_VERSION,
    PT_SCHEMA_VERSION, PT_SAFE_DEFAULTS, SHEET_COLUMNS,
    PT_FLOAT_FIELDS, PT_INT_FIELDS, PT_BOOL_FIELDS,
)
from utils.logger import get_logger

log = get_logger(__name__)

def _normalize_trade_types(trade: dict) -> dict:
    for field in PT_FLOAT_FIELDS:
        if field in trade:
            val = trade[field]
            if val == "" or val is None:
                trade[field] = None
            else:
                try:
                    trade[field] = float(val)
                except (ValueError, TypeError):
                    log.warning(f"Failed to float cast {field} value {val}")
                    trade[field] = None

    for field in PT_INT_FIELDS:
        if field in trade:
            val = trade[field]
            if val == "" or val is None:
                trade[field] = None
            else:
                try:
                    trade[field] = int(float(val))
                except (ValueError, TypeError):
                    log.warning(f"Failed to int cast {field} value {val}")
                    trade[field] = None

    for field in PT_BOOL_FIELDS:
        if field in trade:
            val = trade[field]
            if val == "" or val is None:
                trade[field] = None
            elif isinstance(val, bool):
                pass
            elif str(val).strip() == "True":
                trade[field] = True
            elif str(val).strip() == "False":
                trade[field] = False
            else:
                trade[field] = None

    return trade

def load_open_trades(current_run: str) -> list[dict]:
    if not ensure_headers():
        return []
        
    trades = read_all_trades()
    open_trades = []
    
    for trade in trades:
        normalized_trade = _normalize_trade_types(trade)
        if normalized_trade.get(PT_STATUS) == PT_STATUS_OPEN:
            if normalized_trade.get(PT_LAST_UPDATED_RUN) != current_run:
                open_trades.append(normalized_trade)
                
    return open_trades

def is_terminal(trade: dict) -> bool:
    return trade.get(PT_STATUS) in (PT_STATUS_CLOSED, PT_STATUS_DROPPED)

def commit_updates(updated_trades: list[dict], new_trades: list[dict], current_run: str) -> bool:
    """
    Safe batch write. Called once per run after all processing.
    Atomicity note: Operations are NOT atomic. If update_rows succeeds but write_rows 
    fails, the system will be in a partially updated state. Idempotency guard prevents 
    double-processing on next run. Do NOT attempt rollback.
    """
    valid_updated_trades = []
    for trade in updated_trades:
        if is_terminal(trade):
            log.warning(f"Attempted to update terminal trade {trade.get('trade_id', 'unknown')}. Skipping.")
            continue
        trade[PT_LAST_UPDATED_RUN] = current_run
        trade[PT_DATA_VALID] = True
        valid_updated_trades.append(trade)

    for trade in new_trades:
        trade[PT_LAST_UPDATED_RUN] = current_run
        trade[PT_DATA_VALID] = True
        trade[PT_VERSION] = PT_SCHEMA_VERSION

    success = True
    if valid_updated_trades:
        if not update_rows(valid_updated_trades):
            log.error("Failed to commit updates: update_rows failed")
            success = False

    if new_trades:
        if not write_rows(new_trades):
            log.error("Failed to commit updates: write_rows failed")
            success = False

    return success

def build_empty_trade(ticker: str) -> dict:
    base = copy.deepcopy(PT_SAFE_DEFAULTS)
    base[PT_TICKER] = ticker
    return base
