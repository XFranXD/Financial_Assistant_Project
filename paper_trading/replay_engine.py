import yfinance as yf
import pytz
from datetime import datetime, timedelta, date as _date
from contracts.paper_trading_schema import (
    PT_TICKER, PT_ENTRY_PRICE, PT_STOP_LOSS, PT_PRICE_TARGET,
    PT_ENTRY_DATE, TIMEOUT_TRADING_DAYS, ENTRY_PRICE_ASSUMPTION,
)
from paper_trading.execution_rules import infer_exit
from utils.logger import get_logger

log = get_logger(__name__)

def _is_trading_day(dt) -> bool:
    return dt.weekday() < 5

def simulate_expected_return(trade: dict) -> float | None:
    ticker       = trade.get(PT_TICKER)
    entry_price  = trade.get(PT_ENTRY_PRICE)
    stop_loss    = trade.get(PT_STOP_LOSS)
    price_target = trade.get(PT_PRICE_TARGET)
    entry_date   = trade.get(PT_ENTRY_DATE)

    if not ticker or entry_price is None or stop_loss is None or price_target is None or not entry_date:
        log.warning(f"[PT][Replay] {ticker}: missing required numeric field or entry_date")
        return None

    try:
        entry_price = float(entry_price)
        stop_loss = float(stop_loss)
        price_target = float(price_target)
    except (ValueError, TypeError):
        log.warning(f"[PT][Replay] {ticker}: failed to parse numeric field to float")
        return None

    try:
        entry_dt  = _date.fromisoformat(entry_date)
        end_dt    = entry_dt + timedelta(days=120)
        end_str   = end_dt.isoformat()

        hist = yf.Ticker(ticker).history(
            start=entry_date,
            end=end_str,
            auto_adjust=False,
        )

        if hist.empty:
            log.warning(f"[PT][Replay] {ticker}: empty history result")
            return None

        trading_days_walked = 0
        last_close = None

        first_matched = False
        for timestamp, row in hist.iterrows():
            candle_date = timestamp.date()
            if not _is_trading_day(candle_date):
                continue
                
            if candle_date <= entry_dt:
                continue

            trading_days_walked += 1
            last_close = float(row['Close'])

            if trading_days_walked > TIMEOUT_TRADING_DAYS:
                break

            low = float(row['Low'])
            high = float(row['High'])
            
            exit_reason, exit_price = infer_exit(low, high, stop_loss, price_target)
            if exit_reason is not None and exit_price is not None:
                return round((exit_price - entry_price) / entry_price * 100, 4)

        if last_close is None:
            log.warning(f'[PT][Replay] {ticker}: no candles walked, returning None')
            return None
            
        return round((last_close - entry_price) / entry_price * 100, 4)

    except Exception as e:
        log.warning(f"[PT][Replay] {ticker}: exception during simulation - {e}")
        return None
