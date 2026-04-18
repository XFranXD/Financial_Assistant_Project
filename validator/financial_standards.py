"""
validator/financial_standards.py
Financial Standards Validator (FSV) — orchestrator.

Called from main.py (both scheduled run path and force-ticker/debug path).
Runs all three check buckets against a fully assembled candidate dict.
Returns a structured validator report. Never raises.

The validator:
  - Does NOT change any score
  - Does NOT change any verdict
  - Does NOT block the pipeline
  - Produces a structured flag report per ticker
  - Attaches the report to c['_validator'] in-place

Usage:
    from validator.financial_standards import validate_candidate
    val_result = validate_candidate(c)
    c['_validator'] = val_result

Patch v1.1 changes:
  - Pre-computes _computed_rr once before buckets run; stored on c as a
    temporary key so Bucket A and Bucket B share a single recomputed value.
  - Deterministic data integrity check using field tiers (HARD/PS/EQ) —
    replaces the old count-based approach. Any tier failure → CRITICAL.
  - Tracks which buckets executed. If Bucket B did not run → force CRITICAL.
  - Malformed dict guard in verdict counting loop.
  - UNKNOWN fallback when total checks < MIN_CHECK_THRESHOLD.
  - partial_execution flag added to report when any bucket crashed.
  - log.error only on CRITICAL escalations from integrity/bucket failures.
"""

from datetime import datetime

import pytz

from utils.logger import get_logger
from validator.validator_schema import (
    CONSISTENT, QUESTIONABLE, INCONSISTENT,
    CLEAN, REVIEW, CRITICAL, UNKNOWN,
    BUCKET_RANGE,
    VALIDATOR_VERSION,
    FLOAT_TOLERANCE,
    MIN_CHECK_THRESHOLD,
    HARD_FIELDS, PS_FIELDS, EQ_FIELDS,
    compute_market_verdict,
)

log = get_logger('validator')

# ── Internal sentinel — not exported ─────────────────────────────────────────
_COMPUTED_RR_KEY = '_computed_rr'


def _precompute_rr(c: dict) -> None:
    """
    Compute risk/reward ratio from first principles using entry_price,
    stop_loss, and price_target. Result is stored on c under _COMPUTED_RR_KEY
    as a float, or None if computation is not possible.

    Clamped to a maximum of 50 to prevent bad data from propagating extreme
    values into downstream checks.

    Division-by-zero (entry == stop) → None.
    Any parse failure → None.

    This runs once before any bucket so both Bucket A (validation) and
    Bucket B (logic checks) share the same computed value.
    """
    try:
        entry  = c.get('entry_price')
        stop   = c.get('stop_loss')
        target = c.get('price_target')
        if entry is None or stop is None or target is None:
            c[_COMPUTED_RR_KEY] = None
            return
        entry_f  = float(entry)
        stop_f   = float(stop)
        target_f = float(target)
        denominator = entry_f - stop_f
        if abs(denominator) < 1e-9:
            # entry == stop → undefined R/R
            c[_COMPUTED_RR_KEY] = None
            return
        rr = (target_f - entry_f) / denominator
        # Clamp extreme values caused by bad data
        rr = min(rr, 50.0)
        c[_COMPUTED_RR_KEY] = rr
    except Exception as e:
        log.warning(f'[FSV] _precompute_rr failed: {e}')
        c[_COMPUTED_RR_KEY] = None


def _run_integrity_check(c: dict, ticker: str) -> list[dict]:
    """
    Deterministic data integrity pre-check using field tiers.

    Tier rules:
      HARD_FIELDS — always required. Parse failure → CRITICAL flag.
      PS_FIELDS   — required when ps_available is True.
      EQ_FIELDS   — required when eq_available is True.

    A field "fails" if:
      - Its value on c is None, OR
      - It cannot be cast to float (for numeric fields).

    Returns a list of INCONSISTENT flags for any failed fields.
    An empty list means integrity passed.
    """
    flags = []

    def _check_field(key: str, label: str, context: dict) -> dict | None:
        val = c.get(key)
        if val is None:
            return {
                'check_id':       f'INTEGRITY_{key.upper()}',
                'bucket':         'INTEGRITY',
                'subsystem':      'orchestrator',
                'field':          key,
                'observed':       None,
                'context':        context,
                'expected_range': 'non-None required field',
                'verdict':        INCONSISTENT,
                'note':           (
                    f'Required field {label} is None — '
                    f'data integrity failure. Ticker output cannot be trusted.'
                ),
            }
        # Attempt float cast for numeric fields (non-string expected fields).
        # entry_quality is a legitimate string label by contract (GOOD / WEAK /
        # EXTENDED / EARLY) — skip numeric validation for this field entirely.
        # All other PS_FIELDS (entry_price, stop_loss, price_target) are numeric
        # and must pass the float-cast check.
        if isinstance(val, str) and key != 'entry_quality':
            try:
                float(val)
            except (ValueError, TypeError):
                return {
                    'check_id':       f'INTEGRITY_{key.upper()}',
                    'bucket':         'INTEGRITY',
                    'subsystem':      'orchestrator',
                    'field':          key,
                    'observed':       val,
                    'context':        context,
                    'expected_range': 'parseable numeric value',
                    'verdict':        INCONSISTENT,
                    'note':           (
                        f'Required field {label} value "{val}" cannot be parsed as numeric — '
                        f'data integrity failure.'
                    ),
                }
        return None

    # HARD_FIELDS — always required
    for key, label in HARD_FIELDS:
        try:
            flag = _check_field(key, label, {})
            if flag is not None:
                log.error(f'[FSV] {ticker}: INTEGRITY failure — hard field {label} invalid')
                flags.append(flag)
        except Exception as e:
            log.warning(f'[FSV] {ticker}: integrity check crashed on {key}: {e}')

    # PS_FIELDS — required when ps_available
    if c.get('ps_available') is True:
        for key, label in PS_FIELDS:
            try:
                flag = _check_field(key, label, {'ps_available': True})
                if flag is not None:
                    log.error(f'[FSV] {ticker}: INTEGRITY failure — ps field {label} invalid')
                    flags.append(flag)
            except Exception as e:
                log.warning(f'[FSV] {ticker}: integrity check crashed on {key}: {e}')

    # EQ_FIELDS — required when eq_available
    if c.get('eq_available') is True:
        for key, label in EQ_FIELDS:
            try:
                flag = _check_field(key, label, {'eq_available': True})
                if flag is not None:
                    log.error(f'[FSV] {ticker}: INTEGRITY failure — eq field {label} invalid')
                    flags.append(flag)
            except Exception as e:
                log.warning(f'[FSV] {ticker}: integrity check crashed on {key}: {e}')

    return flags


def validate_candidate(c: dict) -> dict:
    """
    Runs all FSV checks against a fully assembled candidate dict.
    Returns a structured validator report. Never raises — all exceptions
    caught internally. Returns a minimal error report if everything fails.

    Args:
        c: candidate dict as assembled by main.py pipeline

    Returns:
        {
            'ticker':             str,
            'run_timestamp':      str (ISO),
            'checks':             list[dict],
            'inconsistent_count': int,
            'questionable_count': int,
            'consistent_count':   int,
            'ticker_verdict':     str (CLEAN | REVIEW | CRITICAL | UNKNOWN),
            'validator_version':  str,
            'partial_execution':  bool,
            'buckets_executed':   list[str],
        }
    """
    ticker = c.get('ticker', 'UNKNOWN')

    # ── Timestamp ────────────────────────────────────────────────────────────
    try:
        run_timestamp = datetime.now(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        run_timestamp = 'UNKNOWN'

    # ── Pre-computation: R/R from first principles ────────────────────────────
    # Stored on c as _computed_rr. Bucket A validates it. Bucket B uses it
    # for logic checks. Cleaned up at the end of this function.
    try:
        _precompute_rr(c)
    except Exception as e:
        log.warning(f'[FSV] {ticker}: _precompute_rr outer guard: {e}')
        c[_COMPUTED_RR_KEY] = None

    # ── Data integrity pre-check ─────────────────────────────────────────────
    integrity_flags: list[dict] = []
    try:
        integrity_flags = _run_integrity_check(c, ticker)
    except Exception as e:
        log.error(f'[FSV] {ticker}: integrity check crashed entirely: {e}')

    # ── Run all check buckets ────────────────────────────────────────────────
    all_checks: list[dict] = list(integrity_flags)  # integrity flags go first
    buckets_executed: list[str] = []
    bucket_b_ran = False

    try:
        from validator.standards_range import run_range_checks
        range_results = run_range_checks(c)
        all_checks.extend(range_results)
        buckets_executed.append('A_RANGE')
    except Exception as e:
        log.error(f'[FSV] {ticker}: Bucket A (range) crashed entirely: {e}')

    try:
        from validator.standards_contradiction import run_contradiction_checks
        contradiction_results = run_contradiction_checks(c)
        all_checks.extend(contradiction_results)
        buckets_executed.append('B_CONTRADICTION')
        bucket_b_ran = True
    except Exception as e:
        log.error(f'[FSV] {ticker}: Bucket B (contradiction) crashed entirely: {e}')

    try:
        from validator.standards_expectation import run_expectation_checks
        expectation_results = run_expectation_checks(c)
        all_checks.extend(expectation_results)
        buckets_executed.append('C_EXPECTATION')
    except Exception as e:
        log.error(f'[FSV] {ticker}: Bucket C (expectation) crashed entirely: {e}')

    # ── Clean up temporary computed key ──────────────────────────────────────
    c.pop(_COMPUTED_RR_KEY, None)

    # ── Partial execution flag ────────────────────────────────────────────────
    partial_execution = len(buckets_executed) < 3

    # ── Count verdicts ────────────────────────────────────────────────────────
    inconsistent_count = 0
    questionable_count = 0
    consistent_count   = 0

    try:
        for check in all_checks:
            if not isinstance(check, dict):
                log.warning(f'[FSV] {ticker}: malformed check entry (not a dict): {type(check)}')
                continue
            v = check.get('verdict', '')
            if v == INCONSISTENT:
                inconsistent_count += 1
            elif v == QUESTIONABLE:
                questionable_count += 1
            elif v == CONSISTENT:
                consistent_count += 1
            else:
                log.warning(f'[FSV] {ticker}: unrecognized verdict "{v}" in check {check.get("check_id", "?")}')
    except Exception as e:
        log.error(f'[FSV] {ticker}: verdict counting failed: {e}')

    # ── Compute ticker-level verdict ──────────────────────────────────────────
    try:
        total_checks = len(all_checks)

        # Priority 1: Bucket B did not run → cannot trust output
        if not bucket_b_ran:
            ticker_verdict = CRITICAL
            log.error(
                f'[FSV] {ticker}: Bucket B (contradiction) did not execute — '
                f'forcing CRITICAL. Hard invariant layer missing.'
            )

        # Priority 2: Any data integrity failure
        elif integrity_flags:
            ticker_verdict = CRITICAL
            log.error(
                f'[FSV] {ticker}: {len(integrity_flags)} data integrity failure(s) — '
                f'forcing CRITICAL.'
            )

        # Priority 3: Any INCONSISTENT check
        elif inconsistent_count > 0:
            ticker_verdict = CRITICAL

        # Priority 4: Too few checks ran to trust the verdict
        elif total_checks < MIN_CHECK_THRESHOLD:
            ticker_verdict = UNKNOWN
            log.warning(
                f'[FSV] {ticker}: only {total_checks} check(s) ran '
                f'(minimum {MIN_CHECK_THRESHOLD}) — verdict forced to UNKNOWN.'
            )

        # Priority 5: Soft anomalies
        elif questionable_count > 0:
            ticker_verdict = REVIEW

        # All clear
        else:
            ticker_verdict = CLEAN

    except Exception:
        ticker_verdict = UNKNOWN  # safe fallback — do not assume CLEAN on error

    # ── Assemble report ───────────────────────────────────────────────────────
    report = {
        'ticker':             ticker,
        'run_timestamp':      run_timestamp,
        'checks':             all_checks,
        'inconsistent_count': inconsistent_count,
        'questionable_count': questionable_count,
        'consistent_count':   consistent_count,
        'ticker_verdict':     ticker_verdict,
        'validator_version':  VALIDATOR_VERSION,
        'partial_execution':  partial_execution,
        'buckets_executed':   buckets_executed,
    }

    return report