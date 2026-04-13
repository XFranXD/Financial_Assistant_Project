"""
validator/validator_schema.py
Constants for the Financial Standards Validator (FSV).
No business logic here — only verdict labels, bucket names, severity tags,
shared thresholds, and the shared market_verdict recompute utility.
"""

# ── Per-check verdict scale ───────────────────────────────────────────────────
CONSISTENT   = "CONSISTENT"    # value within expected range for this stock/market context
QUESTIONABLE = "QUESTIONABLE"  # outside typical range but not impossible — warrants review
INCONSISTENT = "INCONSISTENT"  # contradicts another field or violates a structural invariant

# ── Ticker-level verdict ──────────────────────────────────────────────────────
CLEAN    = "CLEAN"    # zero INCONSISTENT and zero QUESTIONABLE
REVIEW   = "REVIEW"   # one or more QUESTIONABLE, no INCONSISTENT
CRITICAL = "CRITICAL" # any INCONSISTENT present, or data integrity failure, or Bucket B did not run
UNKNOWN  = "UNKNOWN"  # fewer than MIN_CHECK_THRESHOLD checks ran — output cannot be trusted

# ── Check bucket identifiers ──────────────────────────────────────────────────
BUCKET_RANGE         = "A_RANGE"
BUCKET_CONTRADICTION = "B_CONTRADICTION"
BUCKET_EXPECTATION   = "C_EXPECTATION"

# ── Severity labels (for logging readability) ─────────────────────────────────
SEV_HARD = "hard"   # range violations and contradictions — INCONSISTENT only
SEV_SOFT = "soft"   # expectation checks — QUESTIONABLE only

# ── Float tolerance ───────────────────────────────────────────────────────────
# Used wherever a computed financial value is compared to a threshold to avoid
# false flags from floating point arithmetic.
FLOAT_TOLERANCE = 0.005

# ── Minimum check threshold ───────────────────────────────────────────────────
# If fewer than this many checks ran across all buckets, the ticker verdict is
# forced to UNKNOWN — too little coverage to trust any conclusion.
MIN_CHECK_THRESHOLD = 5

# ── Data integrity field tiers ────────────────────────────────────────────────
# HARD_FIELDS: always required — failure → CRITICAL regardless of subsystem flags.
# PS_FIELDS:   required when ps_available is True.
# EQ_FIELDS:   required when eq_available is True.
# Each entry is (candidate_dict_key, human_readable_label).
HARD_FIELDS = [
    ('composite_confidence', 'composite_confidence'),
    ('risk_score',           'risk_score'),
]

PS_FIELDS = [
    ('entry_price',   'entry_price'),
    ('stop_loss',     'stop_loss'),
    ('price_target',  'price_target'),
    ('entry_quality', 'entry_quality'),
]

EQ_FIELDS = [
    ('eq_score_final', 'eq_score_final'),
]

# ── Validator version ─────────────────────────────────────────────────────────
VALIDATOR_VERSION = "1.1"


# ── Shared market verdict recompute ──────────────────────────────────────────
def compute_market_verdict(c: dict) -> str:
    """
    Inline recompute of market_verdict. Single source of truth for the validator.
    Mirrors _enrich_for_dashboard() logic exactly:
      conf >= 70 AND risk <= 35 → RESEARCH NOW
      conf >= 55                → WATCH
      else                      → SKIP

    Used by both standards_contradiction and standards_expectation to avoid
    duplication and drift risk if thresholds change.

    Args:
        c: candidate dict

    Returns:
        'RESEARCH NOW' | 'WATCH' | 'SKIP'
    """
    conf = c.get('composite_confidence') or 0
    risk = c.get('risk_score') or 100
    if conf >= 70 and risk <= 35:
        return 'RESEARCH NOW'
    elif conf >= 55:
        return 'WATCH'
    return 'SKIP'