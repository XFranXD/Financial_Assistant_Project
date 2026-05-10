"""
calibration/calibration_config.py
Calibration analyzer behavior constants.

These govern how calibration_analyzer.py behaves.
They are NOT trading gate thresholds. See financial_standards.py for those.
Changing these is treated the same as changing a financial standard:
log the change in standards_history.log with reasoning before modifying.
"""

BUCKET_MIN_SAMPLE             = 10
SIGNIFICANCE_EXPECTANCY_DELTA = 0.10
SIGNIFICANCE_WINRATE_DELTA    = 10

CYCLE_MIN_NEW_TRADES          = 10
CYCLE_MIN_OBSERVATION_DAYS    = 7

EXPLORATORY_ANALYSIS_MIN      = 30
RECOMMENDATION_MIN            = 50
PREFERRED_CALIBRATION_MIN     = 75

CHOKE_DROP_THRESHOLD          = 0.50

CONVERGENCE_MAX_DELTA         = 0.05
CONVERGENCE_CONSECUTIVE_CYCLES = 3

SHEET_TAB_STANDARDS_HISTORY   = "standards_history"
SHEET_TAB_CALIBRATION_REPORTS = "calibration_reports"

STANDARDS_HISTORY_HEADERS = [
    "timestamp", "cycle_number", "metric", "old_value", "new_value",
    "recommendation", "simulation_summary", "decision", "reasoning"
]

CALIBRATION_REPORTS_HEADERS = [
    "report_timestamp", "cycle_number", "tier_active", "total_closed_trades",
    "overall_expectancy", "overall_win_rate", "choke_warning",
    "recommendations_count", "report_text"
]
