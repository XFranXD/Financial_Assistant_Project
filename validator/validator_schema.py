"""
validator/validator_schema.py
Constants for the Financial Standards Validator (FSV).
No business logic here — only verdict labels, bucket names, and severity tags.
"""

# ── Per-check verdict scale ───────────────────────────────────────────────────
CONSISTENT   = "CONSISTENT"    # value within expected range for this stock/market context
QUESTIONABLE = "QUESTIONABLE"  # outside typical range but not impossible — warrants review
INCONSISTENT = "INCONSISTENT"  # contradicts another field or violates a structural invariant

# ── Ticker-level verdict ──────────────────────────────────────────────────────
CLEAN    = "CLEAN"    # no INCONSISTENT, zero or one QUESTIONABLE
REVIEW   = "REVIEW"   # one or more QUESTIONABLE, no INCONSISTENT
CRITICAL = "CRITICAL" # any INCONSISTENT present

# ── Check bucket identifiers ──────────────────────────────────────────────────
BUCKET_RANGE         = "A_RANGE"
BUCKET_CONTRADICTION = "B_CONTRADICTION"
BUCKET_EXPECTATION   = "C_EXPECTATION"

# ── Severity labels (for logging readability) ─────────────────────────────────
SEV_HARD = "hard"   # range violations and contradictions — INCONSISTENT only
SEV_SOFT = "soft"   # expectation checks — QUESTIONABLE only

# ── Validator version ─────────────────────────────────────────────────────────
VALIDATOR_VERSION = "1.0"