"""
contracts/portfolio_schema.py
Single source of truth for all Sub5 (Portfolio & Correlation Layer) output keys
and constants. Mirrors the pattern of contracts/price_structure_schema.py.

Import from here in main.py, report_builder.py, and dashboard_builder.py.
Never hardcode these strings anywhere.
"""

# ── Per-candidate fields (mutated into each candidate dict by main.py) ────────

PL_CLUSTER_ID         = 'pl_cluster_id'          # int | None
PL_CORRELATION_FLAGS  = 'pl_correlation_flags'    # list[str] — tickers correlated above threshold
PL_SELECTED           = 'pl_selected'             # bool — True if in final portfolio subset
PL_EXCLUSION_REASON   = 'pl_exclusion_reason'     # 'CORRELATED'|'SECTOR_CAP'|'RANK_CUT'|'UNAVAILABLE'|None
PL_POSITION_WEIGHT    = 'pl_position_weight'      # float | None — allocation % (0–100), None if not selected

# ── Run-level portfolio summary dict ──────────────────────────────────────────

PL_RECOMMENDED_SUBSET    = 'pl_recommended_subset'      # list[str] — tickers ordered by weight descending
PL_EXCLUDED_CANDIDATES   = 'pl_excluded_candidates'     # list[dict] — [{ticker, exclusion_reason}, ...]
PL_SECTOR_EXPOSURE       = 'pl_sector_exposure'         # dict[str, float] — {sector_name: pct_of_portfolio}
PL_AVG_CORRELATION       = 'pl_avg_correlation'         # float | None
PL_DIVERSIFICATION_SCORE = 'pl_diversification_score'  # float | None — 1 - avg_correlation
PL_AVAILABLE             = 'pl_available'               # bool — False if < 2 candidates or any fatal error

# ── Config constants ───────────────────────────────────────────────────────────
# Defined here for visibility. Do NOT redefine in submodules — import from here.

MAX_POSITIONS         = 5      # hard cap on selected subset size
CORRELATION_THRESHOLD = 0.7    # Pearson threshold — at or above = correlated
MAX_SECTOR_PCT        = 40.0   # max portfolio weight any single sector may hold (%)
LOOKBACK_DAYS         = 120    # calendar-day window for price history fetch (~6 months)
