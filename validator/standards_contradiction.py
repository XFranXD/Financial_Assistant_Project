"""
validator/standards_contradiction.py
Bucket B — Cross-field Contradiction checks.

These check logical consistency between fields — within a subsystem or across
subsystems. All checks return CONSISTENT or INCONSISTENT only — never QUESTIONABLE.
A contradiction either exists or it doesn't.

market_verdict is recomputed using the shared compute_market_verdict() utility
from validator_schema. This is the single source of truth — no local copy.

Patch v1.1 changes:
  - compute_market_verdict imported from validator_schema (no local duplicate).
  - R/R logic checks use c['_computed_rr'] (pre-computed by orchestrator) as
    effective R/R when available, falling back to stored value. This ensures
    logic checks operate on the correct arithmetic result, not a potentially
    corrupt stored value.
  - R/R gate threshold changed from < 2.0 to < (2.0 - FLOAT_TOLERANCE) to
    avoid false flags from floating point precision.
  - log.error used on INCONSISTENT verdict paths (not on exceptions).
"""

from utils.logger import get_logger
from validator.validator_schema import (
    CONSISTENT, INCONSISTENT,
    BUCKET_CONTRADICTION,
    FLOAT_TOLERANCE,
    compute_market_verdict,
)

log = get_logger('validator.contradiction')

# R/R minimum threshold with float tolerance applied
RR_MIN_THRESHOLD = 2.0 - FLOAT_TOLERANCE  # 1.995


def _make_flag(check_id: str, subsystem: str, field: str,
               observed, context: dict, expected_range: str,
               verdict: str, note: str) -> dict:
    return {
        'check_id':       check_id,
        'bucket':         BUCKET_CONTRADICTION,
        'subsystem':      subsystem,
        'field':          field,
        'observed':       observed,
        'context':        context,
        'expected_range': expected_range,
        'verdict':        verdict,
        'note':           note,
    }


def _get_effective_rr(c: dict) -> float | None:
    """
    Returns the effective R/R to use for logic checks.
    Prefers _computed_rr (from first principles) over the stored value.
    Falls back to stored risk_reward_ratio if _computed_rr is None.
    Returns None if neither is available.
    """
    computed = c.get('_computed_rr')
    if computed is not None:
        try:
            return float(computed)
        except (TypeError, ValueError):
            pass
    stored = c.get('risk_reward_ratio')
    if stored is not None:
        try:
            return float(stored)
        except (TypeError, ValueError):
            pass
    return None


# ── Sub4 internal contradictions ──────────────────────────────────────────────

def check_good_entry_with_high_extension(c: dict) -> dict | None:
    """
    entry_quality GOOD + move_extension_pct > 50 is INCONSISTENT.
    The entry_classifier has a hard rule: > 50% extension auto-sets EXTENDED.
    GOOD with extension > 50 means the rule was not applied.
    """
    try:
        if not c.get('ps_available'):
            return None
        eq  = c.get('entry_quality')
        ext = c.get('move_extension_pct')
        if eq is None or ext is None:
            return None
        ext_f = float(ext)
        if eq == 'GOOD' and ext_f > 50:
            log.error(
                f'[FSV][B] INCONSISTENT: entry_quality GOOD with '
                f'move_extension_pct {ext_f:.1f}% > 50 — rule not applied'
            )
            return _make_flag(
                check_id       = 'B_CONTRADICTION_GOOD_ENTRY_HIGH_EXTENSION',
                subsystem      = 'sub4',
                field          = 'entry_quality',
                observed       = eq,
                context        = {'move_extension_pct': ext_f},
                expected_range = 'entry_quality != GOOD when move_extension_pct > 50',
                verdict        = INCONSISTENT,
                note           = (
                    f'entry_quality is GOOD but move_extension_pct is {ext_f:.1f}% '
                    f'(> 50). Hard rule: extension > 50 auto-sets EXTENDED. '
                    f'Rule was not applied.'
                ),
            )
        return _make_flag(
            check_id       = 'B_CONTRADICTION_GOOD_ENTRY_HIGH_EXTENSION',
            subsystem      = 'sub4',
            field          = 'entry_quality',
            observed       = eq,
            context        = {'move_extension_pct': ext_f},
            expected_range = 'entry_quality != GOOD when move_extension_pct > 50',
            verdict        = CONSISTENT,
            note           = f'entry_quality {eq} and move_extension_pct {ext_f:.1f}% are consistent',
        )
    except Exception as e:
        log.warning(f'[FSV][B] good_entry_high_extension: {e}')
        return None


def check_rr_override_not_applied(c: dict) -> dict | None:
    """
    rr_override True + entry_quality not WEAK is INCONSISTENT.
    Override exists to force WEAK when R/R < 2.0. If True but entry_quality
    is not WEAK, the override did not apply.
    """
    try:
        if not c.get('ps_available'):
            return None
        override = c.get('rr_override')
        eq       = c.get('entry_quality')
        if override is None or eq is None:
            return None
        if override is True and eq != 'WEAK':
            log.error(
                f'[FSV][B] INCONSISTENT: rr_override True but entry_quality '
                f'is {eq} (expected WEAK)'
            )
            return _make_flag(
                check_id       = 'B_CONTRADICTION_RR_OVERRIDE_NOT_APPLIED',
                subsystem      = 'sub4',
                field          = 'rr_override',
                observed       = override,
                context        = {'entry_quality': eq},
                expected_range = 'entry_quality == WEAK when rr_override is True',
                verdict        = INCONSISTENT,
                note           = (
                    f'rr_override is True but entry_quality is {eq} (expected WEAK). '
                    f'Override forces WEAK when R/R < 2.0 — override did not apply.'
                ),
            )
        return _make_flag(
            check_id       = 'B_CONTRADICTION_RR_OVERRIDE_NOT_APPLIED',
            subsystem      = 'sub4',
            field          = 'rr_override',
            observed       = override,
            context        = {'entry_quality': eq},
            expected_range = 'entry_quality == WEAK when rr_override is True',
            verdict        = CONSISTENT,
            note           = f'rr_override {override} and entry_quality {eq} are consistent',
        )
    except Exception as e:
        log.warning(f'[FSV][B] rr_override_not_applied: {e}')
        return None


# ── Sub2 internal contradictions ──────────────────────────────────────────────

def check_fatal_flaw_without_risky(c: dict) -> dict | None:
    """
    fatal_flaw_reason not None + eq_label not RISKY is INCONSISTENT.
    A fatal flaw must produce eq_label RISKY.
    """
    try:
        if not c.get('eq_available'):
            return None
        flaw  = c.get('fatal_flaw_reason')
        label = c.get('eq_label')
        if flaw is None or flaw == '':
            return None  # no flaw — skip
        if label != 'RISKY':
            log.error(
                f'[FSV][B] INCONSISTENT: fatal_flaw_reason set but eq_label '
                f'is {label} (expected RISKY)'
            )
            return _make_flag(
                check_id       = 'B_CONTRADICTION_FATAL_FLAW_WITHOUT_RISKY',
                subsystem      = 'sub2',
                field          = 'eq_label',
                observed       = label,
                context        = {'fatal_flaw_reason': flaw},
                expected_range = 'eq_label == RISKY when fatal_flaw_reason is set',
                verdict        = INCONSISTENT,
                note           = (
                    f'fatal_flaw_reason is set ("{flaw}") but eq_label is {label} '
                    f'(expected RISKY). Fatal flaw must produce RISKY classification.'
                ),
            )
        return _make_flag(
            check_id       = 'B_CONTRADICTION_FATAL_FLAW_WITHOUT_RISKY',
            subsystem      = 'sub2',
            field          = 'eq_label',
            observed       = label,
            context        = {'fatal_flaw_reason': flaw},
            expected_range = 'eq_label == RISKY when fatal_flaw_reason is set',
            verdict        = CONSISTENT,
            note           = f'fatal_flaw_reason set and eq_label is RISKY — consistent',
        )
    except Exception as e:
        log.warning(f'[FSV][B] fatal_flaw_without_risky: {e}')
        return None


def check_eq_score_when_unavailable(c: dict) -> dict | None:
    """
    eq_available False + eq_score_final not None is INCONSISTENT.
    Score should not be populated when EQ unavailable.
    """
    try:
        available = c.get('eq_available')
        score     = c.get('eq_score_final')
        if available is True or available is None:
            return None  # available or not set — skip
        if score is not None:
            log.error(
                f'[FSV][B] INCONSISTENT: eq_available False but '
                f'eq_score_final is {score}'
            )
            return _make_flag(
                check_id       = 'B_CONTRADICTION_EQ_SCORE_WHEN_UNAVAILABLE',
                subsystem      = 'sub2',
                field          = 'eq_score_final',
                observed       = score,
                context        = {'eq_available': False},
                expected_range = 'eq_score_final == None when eq_available is False',
                verdict        = INCONSISTENT,
                note           = (
                    f'eq_available is False but eq_score_final is {score}. '
                    f'Score must be None when EQ is unavailable.'
                ),
            )
        return _make_flag(
            check_id       = 'B_CONTRADICTION_EQ_SCORE_WHEN_UNAVAILABLE',
            subsystem      = 'sub2',
            field          = 'eq_score_final',
            observed       = score,
            context        = {'eq_available': False},
            expected_range = 'eq_score_final == None when eq_available is False',
            verdict        = CONSISTENT,
            note           = 'eq_available False and eq_score_final is None — consistent',
        )
    except Exception as e:
        log.warning(f'[FSV][B] eq_score_when_unavailable: {e}')
        return None


# ── Sub4 availability contradiction ──────────────────────────────────────────

def check_execution_fields_when_unavailable(c: dict) -> list[dict]:
    """
    ps_available False + any execution field not None is INCONSISTENT.
    Execution fields must not be populated when Sub4 is unavailable.
    """
    results = []
    try:
        if c.get('ps_available') is not False:
            return results
        for field in ('entry_price', 'stop_loss', 'price_target'):
            try:
                val = c.get(field)
                if val is not None:
                    log.error(
                        f'[FSV][B] INCONSISTENT: ps_available False but '
                        f'{field} is {val}'
                    )
                    results.append(_make_flag(
                        check_id       = f'B_CONTRADICTION_EXEC_FIELD_WHEN_UNAVAILABLE_{field.upper()}',
                        subsystem      = 'sub4',
                        field          = field,
                        observed       = val,
                        context        = {'ps_available': False},
                        expected_range = f'{field} == None when ps_available is False',
                        verdict        = INCONSISTENT,
                        note           = (
                            f'ps_available is False but {field} is {val}. '
                            f'Execution fields must be None when Sub4 is unavailable.'
                        ),
                    ))
            except Exception as e:
                log.warning(f'[FSV][B] exec_field_unavailable {field}: {e}')
    except Exception as e:
        log.warning(f'[FSV][B] execution_fields_when_unavailable: {e}')
    return results


# ── Sub3 internal contradictions ──────────────────────────────────────────────

def check_rotation_signal_status_mapping(c: dict) -> list[dict]:
    """
    SUPPORT signal must map to FAVORABLE status.
    WEAKEN signal must map to UNFAVORABLE status.
    """
    results = []
    try:
        if not c.get('rotation_available'):
            return results
        signal = (c.get('rotation_signal') or '').upper()
        status = (c.get('rotation_status') or '').upper()
        if not signal or not status:
            return results

        # SUPPORT → FAVORABLE
        if signal == 'SUPPORT':
            if status == 'FAVORABLE':
                results.append(_make_flag(
                    check_id       = 'B_CONTRADICTION_ROTATION_SUPPORT_STATUS',
                    subsystem      = 'sub3',
                    field          = 'rotation_status',
                    observed       = status,
                    context        = {'rotation_signal': signal},
                    expected_range = 'rotation_status == FAVORABLE when rotation_signal == SUPPORT',
                    verdict        = CONSISTENT,
                    note           = 'rotation_signal SUPPORT → rotation_status FAVORABLE — consistent',
                ))
            else:
                log.error(
                    f'[FSV][B] INCONSISTENT: rotation_signal SUPPORT but '
                    f'rotation_status is {status} (expected FAVORABLE)'
                )
                results.append(_make_flag(
                    check_id       = 'B_CONTRADICTION_ROTATION_SUPPORT_STATUS',
                    subsystem      = 'sub3',
                    field          = 'rotation_status',
                    observed       = status,
                    context        = {'rotation_signal': signal},
                    expected_range = 'rotation_status == FAVORABLE when rotation_signal == SUPPORT',
                    verdict        = INCONSISTENT,
                    note           = (
                        f'rotation_signal is SUPPORT but rotation_status is {status} '
                        f'(expected FAVORABLE). Signal-status mapping violated.'
                    ),
                ))

        # WEAKEN → UNFAVORABLE
        elif signal == 'WEAKEN':
            if status == 'UNFAVORABLE':
                results.append(_make_flag(
                    check_id       = 'B_CONTRADICTION_ROTATION_WEAKEN_STATUS',
                    subsystem      = 'sub3',
                    field          = 'rotation_status',
                    observed       = status,
                    context        = {'rotation_signal': signal},
                    expected_range = 'rotation_status == UNFAVORABLE when rotation_signal == WEAKEN',
                    verdict        = CONSISTENT,
                    note           = 'rotation_signal WEAKEN → rotation_status UNFAVORABLE — consistent',
                ))
            else:
                log.error(
                    f'[FSV][B] INCONSISTENT: rotation_signal WEAKEN but '
                    f'rotation_status is {status} (expected UNFAVORABLE)'
                )
                results.append(_make_flag(
                    check_id       = 'B_CONTRADICTION_ROTATION_WEAKEN_STATUS',
                    subsystem      = 'sub3',
                    field          = 'rotation_status',
                    observed       = status,
                    context        = {'rotation_signal': signal},
                    expected_range = 'rotation_status == UNFAVORABLE when rotation_signal == WEAKEN',
                    verdict        = INCONSISTENT,
                    note           = (
                        f'rotation_signal is WEAKEN but rotation_status is {status} '
                        f'(expected UNFAVORABLE). Signal-status mapping violated.'
                    ),
                ))

    except Exception as e:
        log.warning(f'[FSV][B] rotation_signal_status_mapping: {e}')
    return results


# ── Cross-subsystem hard gate violations ─────────────────────────────────────

def check_risky_eq_with_research_now(c: dict) -> dict | None:
    """
    eq_label RISKY + market_verdict RESEARCH NOW is INCONSISTENT.
    RISKY EQ is a hard gate against RESEARCH NOW.
    """
    try:
        if not c.get('eq_available'):
            return None
        eq_label        = (c.get('eq_label') or '').upper()
        eq_verdict_disp = (c.get('eq_verdict_display') or '').upper()
        market_verdict  = compute_market_verdict(c)

        is_risky = (eq_label == 'RISKY') or (eq_verdict_disp == 'RISKY')
        if not is_risky:
            return None

        if market_verdict == 'RESEARCH NOW':
            log.error(
                f'[FSV][B] INCONSISTENT: eq_label RISKY but market_verdict '
                f'computed as RESEARCH NOW — hard gate not enforced'
            )
            return _make_flag(
                check_id       = 'B_CONTRADICTION_RISKY_EQ_RESEARCH_NOW',
                subsystem      = 'cross',
                field          = 'eq_label',
                observed       = eq_label or eq_verdict_disp,
                context        = {
                    'market_verdict':        market_verdict,
                    'composite_confidence':  c.get('composite_confidence'),
                    'risk_score':            c.get('risk_score'),
                },
                expected_range = 'market_verdict != RESEARCH NOW when eq_label is RISKY',
                verdict        = INCONSISTENT,
                note           = (
                    f'eq_label is RISKY but market_verdict computed as RESEARCH NOW. '
                    f'RISKY EQ is a hard gate — RESEARCH NOW should not be possible here.'
                ),
            )
        return _make_flag(
            check_id       = 'B_CONTRADICTION_RISKY_EQ_RESEARCH_NOW',
            subsystem      = 'cross',
            field          = 'eq_label',
            observed       = eq_label or eq_verdict_disp,
            context        = {'market_verdict': market_verdict},
            expected_range = 'market_verdict != RESEARCH NOW when eq_label is RISKY',
            verdict        = CONSISTENT,
            note           = f'RISKY EQ with market_verdict {market_verdict} — gate correctly blocking RESEARCH NOW',
        )
    except Exception as e:
        log.warning(f'[FSV][B] risky_eq_research_now: {e}')
        return None


def check_high_risk_event_with_research_now(c: dict) -> dict | None:
    """
    event_risk HIGH RISK + market_verdict RESEARCH NOW is INCONSISTENT.
    HIGH RISK event is a hard gate against RESEARCH NOW.
    """
    try:
        event_risk     = (c.get('event_risk') or '').upper()
        market_verdict = compute_market_verdict(c)
        if event_risk != 'HIGH RISK':
            return None
        if market_verdict == 'RESEARCH NOW':
            log.error(
                f'[FSV][B] INCONSISTENT: event_risk HIGH RISK but '
                f'market_verdict computed as RESEARCH NOW — hard gate not enforced'
            )
            return _make_flag(
                check_id       = 'B_CONTRADICTION_HIGH_RISK_EVENT_RESEARCH_NOW',
                subsystem      = 'cross',
                field          = 'event_risk',
                observed       = event_risk,
                context        = {
                    'market_verdict':    market_verdict,
                    'event_risk_reason': c.get('event_risk_reason'),
                },
                expected_range = 'market_verdict != RESEARCH NOW when event_risk is HIGH RISK',
                verdict        = INCONSISTENT,
                note           = (
                    f'event_risk is HIGH RISK but market_verdict computed as RESEARCH NOW. '
                    f'HIGH RISK event is a hard gate — RESEARCH NOW should not be possible here.'
                ),
            )
        return _make_flag(
            check_id       = 'B_CONTRADICTION_HIGH_RISK_EVENT_RESEARCH_NOW',
            subsystem      = 'cross',
            field          = 'event_risk',
            observed       = event_risk,
            context        = {'market_verdict': market_verdict},
            expected_range = 'market_verdict != RESEARCH NOW when event_risk is HIGH RISK',
            verdict        = CONSISTENT,
            note           = f'HIGH RISK event with market_verdict {market_verdict} — gate correctly blocking RESEARCH NOW',
        )
    except Exception as e:
        log.warning(f'[FSV][B] high_risk_event_research_now: {e}')
        return None


def check_rr_gate_not_enforced(c: dict) -> dict | None:
    """
    ps_available True + entry_quality GOOD + rr_override False +
    effective R/R < RR_MIN_THRESHOLD (1.995) is INCONSISTENT.

    Uses _computed_rr if available (source of truth), falling back to stored
    risk_reward_ratio. This ensures the gate check operates on correct
    arithmetic even if the stored value is corrupt.
    """
    try:
        if not c.get('ps_available'):
            return None
        eq       = c.get('entry_quality')
        override = c.get('rr_override')
        if eq != 'GOOD' or override is True:
            return None

        rr_f = _get_effective_rr(c)
        if rr_f is None:
            return None

        rr_source = 'computed' if c.get('_computed_rr') is not None else 'stored'

        if rr_f < RR_MIN_THRESHOLD:
            log.error(
                f'[FSV][B] INCONSISTENT: R/R {rr_f:.4f} ({rr_source}) < '
                f'{RR_MIN_THRESHOLD} with entry_quality GOOD — gate not enforced'
            )
            return _make_flag(
                check_id       = 'B_CONTRADICTION_RR_GATE_NOT_ENFORCED',
                subsystem      = 'cross',
                field          = 'risk_reward_ratio',
                observed       = rr_f,
                context        = {
                    'entry_quality': eq,
                    'rr_override':   override,
                    'rr_source':     rr_source,
                },
                expected_range = f'risk_reward_ratio >= {RR_MIN_THRESHOLD} when entry_quality is GOOD and rr_override is False',
                verdict        = INCONSISTENT,
                note           = (
                    f'Effective R/R ({rr_source}) is {rr_f:.4f} (< {RR_MIN_THRESHOLD}) '
                    f'with entry_quality GOOD and rr_override False. '
                    f'R/R gate not enforced — entry_quality should have been overridden to WEAK.'
                ),
            )
        return _make_flag(
            check_id       = 'B_CONTRADICTION_RR_GATE_NOT_ENFORCED',
            subsystem      = 'cross',
            field          = 'risk_reward_ratio',
            observed       = rr_f,
            context        = {
                'entry_quality': eq,
                'rr_override':   override,
                'rr_source':     rr_source,
            },
            expected_range = f'risk_reward_ratio >= {RR_MIN_THRESHOLD} when entry_quality is GOOD and rr_override is False',
            verdict        = CONSISTENT,
            note           = (
                f'Effective R/R ({rr_source}) {rr_f:.4f} >= {RR_MIN_THRESHOLD} '
                f'with GOOD entry — R/R gate correctly passed'
            ),
        )
    except Exception as e:
        log.warning(f'[FSV][B] rr_gate_not_enforced: {e}')
        return None


# ── Runner ────────────────────────────────────────────────────────────────────

def run_contradiction_checks(c: dict) -> list[dict]:
    """Run all Bucket B checks. Returns list of flag dicts (no Nones)."""
    results = []

    single_checks = [
        check_good_entry_with_high_extension,
        check_rr_override_not_applied,
        check_fatal_flaw_without_risky,
        check_eq_score_when_unavailable,
        check_risky_eq_with_research_now,
        check_high_risk_event_with_research_now,
        check_rr_gate_not_enforced,
    ]

    for fn in single_checks:
        try:
            result = fn(c)
            if result is not None:
                results.append(result)
        except Exception as e:
            log.warning(f'[FSV][B] check {fn.__name__} crashed: {e}')

    # Multi-result checks
    for multi_fn in [check_execution_fields_when_unavailable, check_rotation_signal_status_mapping]:
        try:
            results.extend(multi_fn(c))
        except Exception as e:
            log.warning(f'[FSV][B] check {multi_fn.__name__} crashed: {e}')

    return results