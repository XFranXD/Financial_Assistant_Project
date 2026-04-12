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
"""

from datetime import datetime

import pytz

from utils.logger import get_logger
from validator.validator_schema import (
    CONSISTENT, QUESTIONABLE, INCONSISTENT,
    CLEAN, REVIEW, CRITICAL,
    VALIDATOR_VERSION,
)

log = get_logger('validator')


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
            'ticker_verdict':     str (CLEAN | REVIEW | CRITICAL),
            'validator_version':  str,
        }
    """
    ticker = c.get('ticker', 'UNKNOWN')

    # ── Timestamp ────────────────────────────────────────────────────────────
    try:
        run_timestamp = datetime.now(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        run_timestamp = 'UNKNOWN'

    # ── Run all checks ────────────────────────────────────────────────────────
    all_checks: list[dict] = []

    try:
        from validator.standards_range import run_range_checks
        range_results = run_range_checks(c)
        all_checks.extend(range_results)
    except Exception as e:
        log.error(f'[FSV] {ticker}: Bucket A (range) crashed entirely: {e}')

    try:
        from validator.standards_contradiction import run_contradiction_checks
        contradiction_results = run_contradiction_checks(c)
        all_checks.extend(contradiction_results)
    except Exception as e:
        log.error(f'[FSV] {ticker}: Bucket B (contradiction) crashed entirely: {e}')

    try:
        from validator.standards_expectation import run_expectation_checks
        expectation_results = run_expectation_checks(c)
        all_checks.extend(expectation_results)
    except Exception as e:
        log.error(f'[FSV] {ticker}: Bucket C (expectation) crashed entirely: {e}')

    # ── Count verdicts ────────────────────────────────────────────────────────
    inconsistent_count = 0
    questionable_count = 0
    consistent_count   = 0

    try:
        for check in all_checks:
            v = check.get('verdict', '')
            if v == INCONSISTENT:
                inconsistent_count += 1
            elif v == QUESTIONABLE:
                questionable_count += 1
            elif v == CONSISTENT:
                consistent_count += 1
    except Exception as e:
        log.error(f'[FSV] {ticker}: verdict counting failed: {e}')

    # ── Compute ticker-level verdict ──────────────────────────────────────────
    try:
        if inconsistent_count > 0:
            ticker_verdict = CRITICAL
        elif questionable_count > 0:
            ticker_verdict = REVIEW
        else:
            ticker_verdict = CLEAN
    except Exception:
        ticker_verdict = REVIEW  # safe fallback

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
    }

    return report