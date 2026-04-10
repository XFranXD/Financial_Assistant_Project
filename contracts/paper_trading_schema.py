PT_TRADE_ID          = "trade_id"
PT_TICKER            = "ticker"
PT_ENTRY_DATE        = "entry_date"
PT_ENTRY_RUN         = "entry_run"
PT_ENTRY_TIMESTAMP   = "entry_timestamp"

PT_ENTRY_PRICE       = "entry_price"
PT_STOP_LOSS         = "stop_loss"
PT_PRICE_TARGET      = "price_target"
PT_RISK_REWARD       = "risk_reward_ratio"
PT_POSITION_SIZE_PCT = "position_size_pct"

PT_MARKET_VERDICT       = "market_verdict"
PT_ENTRY_QUALITY        = "entry_quality"
PT_EQ_VERDICT           = "eq_verdict"
PT_ROTATION_SIGNAL      = "rotation_signal"
PT_ALIGNMENT            = "alignment"
PT_COMPOSITE_SCORE      = "composite_score"
PT_MARKET_REGIME        = "market_regime"
PT_INSIDER_SIGNAL       = "insider_signal"
PT_EVENT_RISK           = "event_risk"
PT_EXPECTATIONS_SIGNAL  = "expectations_signal"

PT_STATUS              = "status"
PT_EXIT_DATE           = "exit_date"
PT_EXIT_RUN            = "exit_run"
PT_EXIT_PRICE          = "exit_price"
PT_EXIT_REASON         = "exit_reason"
PT_LIVE_PNL_PCT        = "live_pnl_pct"
PT_DAYS_HELD           = "days_held"
PT_CLOSED_AT_TIMESTAMP = "closed_at_timestamp"

PT_EXPECTED_RETURN_PCT = "expected_return_pct"

PT_ERROR_PCT           = "error_pct"
PT_DIRECTION_CORRECT   = "direction_correct"

PT_BENCHMARK_RETURN    = "benchmark_return"
PT_ALPHA               = "alpha"

PT_LAST_UPDATED_RUN    = "last_updated_run"
PT_DATA_VALID          = "data_valid"
PT_VERSION             = "version"


PT_STATUS_OPEN    = "OPEN"
PT_STATUS_CLOSED  = "CLOSED"
PT_STATUS_DROPPED = "DROPPED"

PT_EXIT_TARGET  = "TARGET_HIT"
PT_EXIT_STOP    = "STOP_HIT"
PT_EXIT_TIMEOUT = "TIMEOUT"
PT_EXIT_DROPPED = "DROPPED"


SHEET_COLUMNS = [
    PT_TRADE_ID, PT_TICKER, PT_ENTRY_DATE, PT_ENTRY_RUN, PT_ENTRY_TIMESTAMP,
    PT_ENTRY_PRICE, PT_STOP_LOSS, PT_PRICE_TARGET, PT_RISK_REWARD, PT_POSITION_SIZE_PCT,
    PT_MARKET_VERDICT, PT_ENTRY_QUALITY, PT_EQ_VERDICT, PT_ROTATION_SIGNAL,
    PT_ALIGNMENT, PT_COMPOSITE_SCORE, PT_MARKET_REGIME, PT_INSIDER_SIGNAL,
    PT_EVENT_RISK, PT_EXPECTATIONS_SIGNAL,
    PT_STATUS, PT_EXIT_DATE, PT_EXIT_RUN, PT_EXIT_PRICE, PT_EXIT_REASON,
    PT_LIVE_PNL_PCT, PT_DAYS_HELD, PT_CLOSED_AT_TIMESTAMP,
    PT_EXPECTED_RETURN_PCT,
    PT_ERROR_PCT, PT_DIRECTION_CORRECT,
    PT_BENCHMARK_RETURN, PT_ALPHA,
    PT_LAST_UPDATED_RUN, PT_DATA_VALID, PT_VERSION
]


SHEET_NAME            = "trades"
PT_SCHEMA_VERSION     = 1         # int — increment when schema changes
COOLDOWN_TRADING_DAYS = 1         # int — min trading days after close before
                                  #        same ticker can re-enter.
                                  #        Cooldown starts the day AFTER exit_date.
                                  #        Exit on Monday → cooldown day = Tuesday
                                  #        → earliest re-entry = Wednesday.
TIMEOUT_TRADING_DAYS  = 20        # int — force-close after N trading days open
FAILED_FETCH_LIMIT    = 3         # int — consecutive yfinance failures within
                                  #        one run before DROPPED is triggered.
                                  #        This is a per-run in-memory counter —
                                  #        it resets every GitHub Actions run.
                                  #        Purpose: guard against a ticker that
                                  #        yfinance cannot price at all this run.
                                  #        It does NOT persist across runs.

ENTRY_PRICE_ASSUMPTION = "sub4_execution_price_at_signal_time"
# Live engine reads c['entry_price'] from Sub4's Execution Layer output
# at the moment the pipeline runs. Replay engine reads PT_ENTRY_PRICE
# from the same stored trade dict. Both use the identical value —
# no adjustment, no next-open assumption, no slippage.
# This constant exists to make the assumption explicit and auditable.


PT_SAFE_DEFAULTS = {
    PT_TRADE_ID: "",
    PT_TICKER: "",
    PT_ENTRY_DATE: "",
    PT_ENTRY_RUN: "",
    PT_ENTRY_TIMESTAMP: "",
    PT_ENTRY_PRICE: None,
    PT_STOP_LOSS: None,
    PT_PRICE_TARGET: None,
    PT_RISK_REWARD: None,
    PT_POSITION_SIZE_PCT: None,
    PT_MARKET_VERDICT: "",
    PT_ENTRY_QUALITY: "",
    PT_EQ_VERDICT: "",
    PT_ROTATION_SIGNAL: "",
    PT_ALIGNMENT: "",
    PT_COMPOSITE_SCORE: None,
    PT_MARKET_REGIME: "",
    PT_INSIDER_SIGNAL: "",
    PT_EVENT_RISK: "",
    PT_EXPECTATIONS_SIGNAL: "",
    PT_STATUS: PT_STATUS_OPEN,
    PT_EXIT_DATE: "",
    PT_EXIT_RUN: "",
    PT_EXIT_PRICE: None,
    PT_EXIT_REASON: "",
    PT_LIVE_PNL_PCT: None,
    PT_DAYS_HELD: None,
    PT_CLOSED_AT_TIMESTAMP: "",
    PT_EXPECTED_RETURN_PCT: None,
    PT_ERROR_PCT: None,
    PT_DIRECTION_CORRECT: None,
    PT_BENCHMARK_RETURN: None,
    PT_ALPHA: None,
    PT_LAST_UPDATED_RUN: "",
    PT_DATA_VALID: True,
    PT_VERSION: PT_SCHEMA_VERSION,
}


PT_FLOAT_FIELDS = [
    PT_ENTRY_PRICE, PT_STOP_LOSS, PT_PRICE_TARGET,
    PT_RISK_REWARD, PT_POSITION_SIZE_PCT,
    PT_LIVE_PNL_PCT, PT_COMPOSITE_SCORE,
    PT_EXPECTED_RETURN_PCT, PT_ERROR_PCT,
    PT_BENCHMARK_RETURN, PT_ALPHA,
    PT_EXIT_PRICE,
]


PT_INT_FIELDS = [
    PT_DAYS_HELD, PT_VERSION,
]


PT_BOOL_FIELDS = [
    PT_DIRECTION_CORRECT, PT_DATA_VALID,
]
