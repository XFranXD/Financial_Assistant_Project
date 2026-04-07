"""
contracts/price_structure_schema.py
Single source of truth for all Subsystem 4 (Price Structure Analyzer) output keys,
display key constants, and safe defaults.

Copied from price_structure/contracts/price_structure_schema.py and extended
with display key constants for System 1 rendering (report_builder.py /
dashboard_builder.py). The price_structure/ folder itself is locked.

Display key constants follow the same pattern as eq_schema.py and sector_schema.py.
"""

# ── Raw output keys (match price_structure analyze() return dict exactly) ───

PS_TREND_STRUCTURE          = 'trend_structure'           # UP / DOWN / SIDEWAYS
PS_TREND_STRENGTH           = 'trend_strength'            # 0-100
PS_KEY_LEVEL_POSITION       = 'key_level_position'        # NEAR_SUPPORT / MID_RANGE / NEAR_RESISTANCE / BREAKOUT
PS_ENTRY_QUALITY            = 'entry_quality'             # GOOD / EXTENDED / EARLY / WEAK
PS_VOLATILITY_STATE         = 'volatility_state'          # COMPRESSING / EXPANDING / NORMAL
PS_COMPRESSION_LOCATION     = 'compression_location'      # BULLISH / NEUTRAL
PS_CONSOLIDATION_CONFIRMED  = 'consolidation_confirmed'   # bool
PS_SUPPORT_REACTION         = 'support_reaction'          # bool
PS_BASE_DURATION_DAYS       = 'base_duration_days'        # int
PS_VOLUME_CONTRACTION       = 'volume_contraction'        # bool
PS_PRICE_ACTION_SCORE       = 'price_action_score'        # 0-100, display only
PS_MOVE_EXTENSION_PCT       = 'move_extension_pct'        # float, % above 126-day low
PS_DISTANCE_TO_SUPPORT_PCT  = 'distance_to_support_pct'   # float
PS_DISTANCE_TO_RESIST_PCT   = 'distance_to_resistance_pct'
PS_STRUCTURE_STATE          = 'structure_state'           # TRENDING / CONSOLIDATING / VOLATILE
PS_RECENT_CROSSOVER         = 'recent_crossover'          # bool
PS_DATA_CONFIDENCE          = 'ps_data_confidence'        # HIGH / LOW / UNAVAILABLE
PS_REASONING                = 'ps_reasoning'              # one-sentence human-readable summary

# ── Availability flag (set by main.py enrichment, not by analyze()) ─────────

PS_AVAILABLE                = 'ps_available'              # bool

# ── Display keys (set by report_builder._build_ps_display(), never by Sub4) ─

PS_ENTRY_QUALITY_DISPLAY    = 'ps_entry_quality_display'  # GOOD / EXTENDED / EARLY / WEAK / UNAVAILABLE
PS_TREND_DISPLAY            = 'ps_trend_display'          # UP / DOWN / SIDEWAYS / UNAVAILABLE
PS_KEY_LEVEL_DISPLAY        = 'ps_key_level_display'      # formatted for template
PS_SCORE_DISPLAY            = 'ps_score_display'          # '72/100' or 'UNAVAILABLE'
PS_REASONING_DISPLAY        = 'ps_reasoning_display'      # safe-escaped reasoning string
PS_VERDICT_DISPLAY          = 'ps_verdict_display'        # dashboard pill value

# ── Execution Layer (1C) ─────────────────────────────────────────────────────
PS_ENTRY_PRICE       = 'entry_price'        # float | None — computed entry price
PS_STOP_LOSS         = 'stop_loss'          # float | None — stop loss level
PS_PRICE_TARGET      = 'price_target'       # float | None — nearest resistance as target
PS_RISK_REWARD_RATIO = 'risk_reward_ratio'  # float | None — (target-entry)/(entry-stop)
PS_RR_OVERRIDE       = 'rr_override'        # bool — True if entry_quality overridden to WEAK

# ── Full key list (matches price_structure/contracts/price_structure_schema.py) ─

PRICE_STRUCTURE_KEYS = {
    'ticker':                       str,
    'trend_structure':              str,
    'trend_strength':               int,
    'key_level_position':           str,
    'entry_quality':                str,
    'volatility_state':             str,
    'compression_location':         str,
    'consolidation_confirmed':      bool,
    'support_reaction':             bool,
    'base_duration_days':           int,
    'volume_contraction':           bool,
    'price_action_score':           int,
    'move_extension_pct':           float,
    'distance_to_support_pct':      float,
    'distance_to_resistance_pct':   float,
    'structure_state':              str,
    'recent_crossover':             bool,
    'ps_data_confidence':           str,
    'ps_reasoning':                 str,
    'entry_price':                  float,
    'stop_loss':                    float,
    'price_target':                 float,
    'risk_reward_ratio':            float,
    'rr_override':                  bool,
}

PRICE_STRUCTURE_DEFAULTS = {
    'ticker':                       '',
    'trend_structure':              'SIDEWAYS',
    'trend_strength':               0,
    'key_level_position':           'MID_RANGE',
    'entry_quality':                'WEAK',
    'volatility_state':             'NORMAL',
    'compression_location':         'NEUTRAL',
    'consolidation_confirmed':      False,
    'support_reaction':             False,
    'base_duration_days':           0,
    'volume_contraction':           False,
    'price_action_score':           0,
    'move_extension_pct':           0.0,
    'distance_to_support_pct':      0.0,
    'distance_to_resistance_pct':   0.0,
    'structure_state':              'VOLATILE',
    'recent_crossover':             False,
    'ps_data_confidence':           'UNAVAILABLE',
    'ps_reasoning':                 'Insufficient data to assess price structure.',
    'entry_price':                  None,
    'stop_loss':                    None,
    'price_target':                 None,
    'risk_reward_ratio':            None,
    'rr_override':                  False,
}