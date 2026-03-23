"""
contracts/sector_schema.py
Shared data contract between System 1 and sector_detector (System 3).
All key names used to exchange data between systems are defined here.
When a key name changes in System 3, update it here only — nowhere else.

RENDERING RULE: System 3 returns RAW DATA ONLY.
System 1 owns all rendering — HTML, email, and dashboard display.
sector_detector never produces HTML for System 1 consumption.
Display keys below are built exclusively by System 1's report_builder.py.

KEY NAMING RULE: raw data keys match System 3 output field names exactly.
No translation layer between System 3 output and System 1 storage.
"""

# ── Core rotation result keys (raw data from System 3) ────────────────────
# These match System 3 output_formatter.py field names exactly.
ROTATION_SCORE          = "rotation_score"
ROTATION_STATUS         = "rotation_status"
ROTATION_SIGNAL         = "rotation_signal"
SECTOR_ETF              = "sector_etf"
MOMENTUM_SCORE          = "momentum_score"
RELATIVE_STRENGTH_SCORE = "relative_strength_score"
VOLUME_SCORE            = "volume_score"
ROTATION_CONFIDENCE     = "data_confidence"
TIMEFRAMES_USED         = "timeframes_used"
ROTATION_REASONING      = "reasoning"

# ── Availability flag ──────────────────────────────────────────────────────
ROTATION_AVAILABLE      = "rotation_available"

# ── Display keys built by System 1's report_builder.py ────────────────────
# These are never set by sector_detector. Computed from raw keys above.
ROTATION_SCORE_DISPLAY  = "rotation_score_display"
ROTATION_SIGNAL_DISPLAY = "rotation_signal_display"
ROTATION_ETF_DISPLAY    = "rotation_etf_display"
