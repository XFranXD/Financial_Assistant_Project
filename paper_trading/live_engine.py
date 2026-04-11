import yfinance as yf
import pytz
from datetime import datetime, timedelta
from contracts.paper_trading_schema import (
    PT_TRADE_ID, PT_TICKER, PT_STATUS, PT_STATUS_OPEN,
    PT_STATUS_CLOSED, PT_STATUS_DROPPED,
    PT_ENTRY_PRICE, PT_STOP_LOSS, PT_PRICE_TARGET,
    PT_ENTRY_DATE, PT_EXIT_DATE, PT_EXIT_RUN,
    PT_EXIT_PRICE, PT_EXIT_REASON, PT_LIVE_PNL_PCT,
    PT_DAYS_HELD, PT_CLOSED_AT_TIMESTAMP, PT_LAST_UPDATED_RUN,
    PT_EXIT_TARGET, PT_EXIT_STOP, PT_EXIT_TIMEOUT, PT_EXIT_DROPPED,
    TIMEOUT_TRADING_DAYS, FAILED_FETCH_LIMIT, COOLDOWN_TRADING_DAYS,
)
from paper_trading.state_manager import load_open_trades, commit_updates
from paper_trading.trade_builder import build_trade
from paper_trading.execution_rules import infer_exit
from utils.logger import get_logger

log = get_logger(__name__)

def _is_trading_day(dt: datetime) -> bool:
    return dt.weekday() < 5

def _trading_days_between(date_a: str, date_b: str) -> int:
    if not date_a or not date_b or date_a == date_b:
        return 0
    try:
        dt_a = datetime.fromisoformat(date_a)
        dt_b = datetime.fromisoformat(date_b)
        days = 0
        current = min(dt_a, dt_b) + timedelta(days=1)
        end = max(dt_a, dt_b)
        while current <= end:
            if _is_trading_day(current):
                days += 1
            current += timedelta(days=1)
        return days
    except Exception:
        return 0

def _fetch_ohlc(ticker: str, date_str: str) -> dict | None:
    try:
        hist = yf.Ticker(ticker).history(period='5d', auto_adjust=False)
        if hist.empty:
            return None
            
        last_match = None
        for timestamp, row in hist.iterrows():
            if timestamp.date().isoformat() == date_str:
                last_match = {
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close'])
                }
        return last_match
    except Exception as e:
        log.warning(f"Failed to fetch OHLC for {ticker}: {e}")
        return None

def _validate_trade_numerics(trade: dict) -> bool:
    for field in (PT_ENTRY_PRICE, PT_STOP_LOSS, PT_PRICE_TARGET):
        val = trade.get(field)
        if val is None:
            return False
        try:
            float(val)
        except (TypeError, ValueError):
            return False

    entry_price  = float(trade[PT_ENTRY_PRICE])
    stop_loss    = float(trade[PT_STOP_LOSS])
    price_target = float(trade[PT_PRICE_TARGET])

    # All three must be strictly positive.
    if entry_price <= 0 or stop_loss <= 0 or price_target <= 0:
        log.warning(
            f"[{trade.get(PT_TICKER, 'unknown')}] Invalid trade levels: "
            f"entry={entry_price}, stop={stop_loss}, target={price_target} — "
            f"all must be > 0"
        )
        return False

    # Stop must be below entry, target must be above entry.
    # An inverted stop (stop >= entry) would trigger immediately on any candle.
    # An inverted target (target <= entry) would also trigger immediately.
    if stop_loss >= entry_price:
        log.warning(
            f"[{trade.get(PT_TICKER, 'unknown')}] stop_loss ({stop_loss}) >= "
            f"entry_price ({entry_price}) — invalid long trade setup"
        )
        return False
    if price_target <= entry_price:
        log.warning(
            f"[{trade.get(PT_TICKER, 'unknown')}] price_target ({price_target}) <= "
            f"entry_price ({entry_price}) — invalid long trade setup"
        )
        return False

    return True

def _close_trade(trade: dict, exit_reason: str, exit_price: float, exit_run: str) -> dict:
    today_et = datetime.now(pytz.timezone('America/New_York'))
    today_et_str = today_et.strftime('%Y-%m-%d')
    entry_price = float(trade[PT_ENTRY_PRICE])

    trade[PT_STATUS] = PT_STATUS_CLOSED
    trade[PT_EXIT_DATE] = today_et_str
    trade[PT_EXIT_RUN] = exit_run
    trade[PT_EXIT_PRICE] = exit_price
    trade[PT_EXIT_REASON] = exit_reason
    trade[PT_LIVE_PNL_PCT] = round((exit_price - entry_price) / entry_price * 100, 4)
    trade[PT_DAYS_HELD] = _trading_days_between(trade[PT_ENTRY_DATE], today_et_str)
    trade[PT_CLOSED_AT_TIMESTAMP] = datetime.now(pytz.utc).isoformat()
    return trade

def _drop_trade(trade: dict, exit_run: str) -> dict:
    """
    Mark a trade as DROPPED without computing PnL.
    Used when entry_price or other numeric fields are invalid — computing
    (exit_price - entry_price) / entry_price would produce a meaningless 0%
    result or raise an exception. exit_price and live_pnl_pct are left None
    so downstream analysis can distinguish DROPPED from a genuine 0% outcome.
    """
    today_et = datetime.now(pytz.timezone('America/New_York'))
    today_et_str = today_et.strftime('%Y-%m-%d')

    trade[PT_STATUS] = PT_STATUS_DROPPED
    trade[PT_EXIT_DATE] = today_et_str
    trade[PT_EXIT_RUN] = exit_run
    trade[PT_EXIT_PRICE] = None
    trade[PT_EXIT_REASON] = PT_EXIT_DROPPED
    trade[PT_LIVE_PNL_PCT] = None
    trade[PT_DAYS_HELD] = _trading_days_between(trade[PT_ENTRY_DATE], today_et_str)
    trade[PT_CLOSED_AT_TIMESTAMP] = datetime.now(pytz.utc).isoformat()
    return trade

def process_open_trades(current_slot: str, open_trades: list[dict]) -> list[dict]:
    today_date = datetime.now(pytz.timezone('America/New_York')).strftime('%Y-%m-%d')
    for trade in open_trades:
        if not _validate_trade_numerics(trade):
            log.warning(f"[{trade.get(PT_TICKER, 'unknown')}] Invalid numerics in trade — dropping")
            _drop_trade(trade, current_slot)
            continue
            
        ticker = trade[PT_TICKER]
        ohlc = _fetch_ohlc(ticker, today_date)
        
        if ohlc is None:
            trade['_failed_fetch_count'] = trade.get('_failed_fetch_count', 0) + 1
            if trade['_failed_fetch_count'] >= FAILED_FETCH_LIMIT:
                log.warning(f"[PT] {trade.get(PT_TICKER, 'unknown')}: FAILED_FETCH_LIMIT reached — dropping")
                _drop_trade(trade, current_slot)
            continue
        
        days_held = _trading_days_between(trade[PT_ENTRY_DATE], today_date)

        # Check SL/TP first — even on the timeout day, an actual level hit takes
        # priority over timeout. This matches replay engine's per-candle walk order.
        reason, price = infer_exit(ohlc['low'], ohlc['high'], float(trade[PT_STOP_LOSS]), float(trade[PT_PRICE_TARGET]))
        if reason:
            _close_trade(trade, reason, price, current_slot)
            continue

        if days_held >= TIMEOUT_TRADING_DAYS:
            _close_trade(trade, PT_EXIT_TIMEOUT, ohlc['close'], current_slot)
            continue
            
    return open_trades

def detect_new_entries(candidates: list[dict], updated_trades: list[dict], all_trades_raw: list[dict], current_slot: str, market_regime: str, debug_mode: bool = False) -> list[dict]:
    today_et_str = datetime.now(pytz.timezone('America/New_York')).strftime('%Y-%m-%d')
    new_entries = []

    # Build a set of tickers that closed THIS run so cooldown applies immediately,
    # even though those exits haven't been written to the sheet yet.
    tickers_closed_this_run = {
        t.get(PT_TICKER)
        for t in updated_trades
        if t.get(PT_STATUS) in (PT_STATUS_CLOSED, PT_STATUS_DROPPED)
    }

    for candidate in candidates:
        ticker = candidate.get('ticker')

        if debug_mode:
            # Debug mode: bypass all financial strategy gates (verdict, entry quality).
            # Only require that numeric levels are present — the trade must still be
            # structurally valid so the replay engine and Sheets integration can be
            # tested with realistic data. Cooldown and duplicate-open checks still apply
            # so the ledger stays clean across repeated test runs.
            has_levels = (
                candidate.get('entry_price') is not None
                and candidate.get('stop_loss') is not None
                and candidate.get('price_target') is not None
            )
            if not has_levels:
                log.info(f'[PT][DEBUG] {ticker}: skip — entry/stop/target levels missing (Sub4 unavailable)')
                continue
        else:
            if not (candidate.get('market_verdict') in ('RESEARCH NOW', 'WATCH')
                    and candidate.get('entry_quality') == 'GOOD'
                    and candidate.get('entry_price') is not None
                    and candidate.get('stop_loss') is not None
                    and candidate.get('price_target') is not None):
                continue

        # ── Shared checks (both normal and debug mode) ────────────────────
        # Block re-entry for tickers that exited in this same run.
        if ticker in tickers_closed_this_run:
            log.info(f"[PT] {ticker}: skip — closed this run, cooldown applies")
            continue

        is_open = any(t.get(PT_TICKER) == ticker and t.get(PT_STATUS) == PT_STATUS_OPEN for t in updated_trades)
        if is_open:
            log.info(f"[PT] {ticker}: skip — already has open trade")
            continue

        closed_trades = [t for t in all_trades_raw if t.get(PT_TICKER) == ticker and t.get(PT_STATUS) == PT_STATUS_CLOSED]
        # ISO date strings sort lexicographically == chronologically
        closed_trades.sort(key=lambda x: x.get(PT_EXIT_DATE, ''), reverse=True)

        if closed_trades:
            most_recent = closed_trades[0]
            exit_date = most_recent.get(PT_EXIT_DATE)
            if exit_date:
                days_since_close = _trading_days_between(exit_date, today_et_str)
                if days_since_close <= COOLDOWN_TRADING_DAYS:
                    log.info(f"[PT] {ticker}: skip — cooldown active ({days_since_close} days since close)")
                    continue

        new_trade = build_trade(candidate, current_slot, market_regime)
        new_entries.append(new_trade)
            
    return new_entries

def run_paper_trading(candidates: list[dict], current_slot: str, market_regime: str, debug_mode: bool = False) -> dict:
    try:
        from paper_trading.sheets_ledger import read_all_trades
        all_trades_raw = read_all_trades()
        open_trades = load_open_trades(current_slot)
        
        updated_trades = process_open_trades(current_slot, open_trades)
        
        new_trades = detect_new_entries(
            candidates, updated_trades, all_trades_raw,
            current_slot, market_regime,
            debug_mode=debug_mode,
        )
        
        commit_updates(updated_trades, new_trades, current_slot)
        
        open_count = sum(1 for t in updated_trades if t.get(PT_STATUS) == PT_STATUS_OPEN)
        closed_count = sum(1 for t in updated_trades if t.get(PT_STATUS) in (PT_STATUS_CLOSED, PT_STATUS_DROPPED))
        
        return {
            'pt_available': True,
            'open_count': open_count,
            'new_count': len(new_trades),
            'closed_count': closed_count,
            'trades': updated_trades + new_trades
        }
    except Exception as e:
        log.error(f"Failed to run paper trading: {e}")
        return {
            'pt_available': False,
            'open_count': 0,
            'new_count': 0,
            'closed_count': 0,
            'trades': []
        }