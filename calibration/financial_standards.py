"""
calibration/financial_standards.py
Financial Standards Engine — single source of truth for all TRADE DECISION thresholds.

Read by live_engine.py to make trade opening decisions.
NOT read by the calibration analyzer for its own behavior — see calibration_config.py.

Standards are NOT auto-updated. All changes require human approval and must be logged
in calibration/standards_history.log BEFORE this file is modified.

STANDARDS_VERSION must be incremented every time any threshold value changes.
"""

STANDARDS_VERSION = "v1.2"

# Which entry_quality labels are accepted for trade opening.
# v1.1: All four labels accepted — no entry quality is rejected.
# Evidence for tightening this must come from Phase 4B analyzer output.
ALLOWED_ENTRY_QUALITIES = {"GOOD", "MODERATE", "WEAK", "EXTENDED"}

# Minimum risk_reward_ratio for trade opening.
# v1.1: REMOVED — no evidence base exists for this threshold yet.
# Retained as a variable so live_engine.py import does not break,
# but set to 0.0 so it never filters anything.
MIN_RR_FOR_ENTRY = 0.0

# Maximum move_extension_pct accepted for trade opening.
# v1.1: None (no cap — derive from evidence).
# Set to a float to activate. Gate checks this in live_engine.py.
MAX_MOVE_EXTENSION_PCT = None
