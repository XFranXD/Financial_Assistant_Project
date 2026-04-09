"""
contracts/eq_schema.py
Shared data contract between System 1 and eq_analyzer (System 2).
All key names used to exchange data between systems are defined here.
When a key name changes in System 2, update it here only — nowhere else.
System 3 will add sector_schema.py to this folder when ready.

RENDERING RULE: System 2 returns RAW DATA ONLY.
System 1 owns all rendering — HTML, email, and dashboard display.
eq_analyzer never produces HTML for System 1 consumption.
Display keys below are built exclusively by System 1's report_builder.py.
"""

# ── Core EQ result keys (raw data from System 2) ──────────────────────────
EQ_SCORE_FINAL          = "eq_score_final"
EQ_LABEL                = "eq_label"
EQ_MODIFIER             = "eq_modifier"
PASS_TIER               = "pass_tier"
FINAL_CLASSIFICATION    = "final_classification"
WARNING_SCORE           = "warning_score"
WARNINGS                = "warnings"
TOP_RISKS               = "top_risks"
TOP_STRENGTHS           = "top_strengths"
DATA_CONFIDENCE         = "data_confidence"
SCORE_CONFIDENCE        = "score_confidence"
ECONOMIC_INTEGRITY      = "economic_integrity_score"
FATAL_FLAW_REASON       = "fatal_flaw_reason"
EQ_PERCENTILE           = "eq_percentile"
COMBINED_PRIORITY_SCORE = "combined_priority_score"
BATCH_REGIME            = "batch_regime"
BATCH_MEDIAN            = "batch_median"

# ── Event Risk (1A) ─────────────────────────────────────────────────────────
EVENT_RISK        = 'event_risk'          # 'NORMAL' | 'HIGH RISK'
EVENT_RISK_REASON = 'event_risk_reason'   # display string
DAYS_TO_EARNINGS  = 'days_to_earnings'    # int | None

# ── Insider Activity (1B) ────────────────────────────────────────────────────
INSIDER_SIGNAL = 'insider_signal'   # 'ACCUMULATING' | 'DISTRIBUTING' | 'NEUTRAL' | 'UNAVAILABLE'
INSIDER_NOTE   = 'insider_note'     # display string

# ── Display keys built by System 1's report_builder.py ────────────────────
# These are never set by eq_analyzer. They are computed from the raw keys above.
EQ_SCORE_DISPLAY         = "eq_score_display"
EQ_LABEL_DISPLAY         = "eq_label_display"
EQ_VERDICT_DISPLAY       = "eq_verdict_display"
EQ_TOP_RISKS_DISPLAY     = "eq_top_risks_display"
EQ_TOP_STRENGTHS_DISPLAY = "eq_top_strengths_display"
EQ_WARNINGS_DISPLAY      = "eq_warnings_display"
EQ_AVAILABLE             = "eq_available"

# ── Market Regime (2A) — run-level context, not per-ticker ───────────────────
MARKET_REGIME       = 'market_regime'    # 'BULL' | 'NEUTRAL' | 'BEAR'
MARKET_BREADTH_PCT  = 'breadth_pct'      # float | None — % stocks above 200d SMA
REGIME_SCORE        = 'regime_score'     # int — raw score -3 to +3 (debug only)
REGIME_SPY_ABOVE    = 'spy_above_200d'   # bool | None — SPY above its 200d SMA
REGIME_VIX          = 'regime_vix'       # float | None — VIX value at run time