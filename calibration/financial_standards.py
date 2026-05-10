"""
calibration/financial_standards.py
Financial Standards Engine — single source of truth for all TRADE DECISION thresholds.

Read by live_engine.py to make trade opening decisions.
NOT read by the calibration analyzer for its own behavior — see calibration_config.py.

Standards are NOT auto-updated. All changes require human approval and must be logged
in calibration/standards_history.log BEFORE this file is modified.

STANDARDS_VERSION must be incremented every time any threshold value changes.
"""

STANDARDS_VERSION = "v1.0"

# Which entry_quality labels are accepted for trade opening.
# Phase 4A: GOOD and MODERATE. WEAK and EXTENDED always rejected.
ALLOWED_ENTRY_QUALITIES = {"GOOD", "MODERATE"}

# Minimum composite_confidence for trade opening.
# Must always be >= COMPOSITE_CONFIDENCE_MIN in config.py (= 35).
# Phase 4A: 45
CONFIDENCE_FLOOR = 45

# Minimum risk_reward_ratio for trade opening.
# Phase 4A: 1.5
MIN_RR_FOR_ENTRY = 1.5

# Maximum move_extension_pct accepted for trade opening.
# Phase 4A: None (no cap — derive from evidence).
# Set to a float to activate. Gate checks this in live_engine.py.
MAX_MOVE_EXTENSION_PCT = None
