"""
validator/standards_contradiction.py
Bucket B — Cross-field Contradiction checks.

These check logical consistency between fields — within a subsystem or across
subsystems. All checks return CONSISTENT or INCONSISTENT only — never QUESTIONABLE.
A contradiction either exists or it doesn't.

market_verdict is computed inline here because the validator runs before
_enrich_for_dashboard() in both scheduled and debug paths.
"""

from utils.logger import get_logger
from validator.validator_schema import (
    CONSISTENT, INCONSISTENT,
    BUCKET_CONTRADICTION,
)

log = get_logger('validator.contradiction')


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


def _compute_market_verdict(c: dict) -> str:
    """
    Inline recompute of market_verdict.
    Mirrors _enrich_for_dashboard() logic exactly:
      conf >= 70 AND risk <= 35 → RESEARCH NOW
      conf >= 55                → WATCH
      else                      → SKIP
    """
    conf = c.get('composite_confidence') or 0
    risk = c.get('risk_score') or 100
    if conf >= 70 and risk <= 35:
        return 'RESEARCH NOW'
    elif conf >= 55:
        return 'WATCH'
    return 'SKIP'


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
        # Flaw is present — check label
        if label != 'RISKY':
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
        # eq_available is False
        if score is not None:
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
        eq_label       = (c.get('eq_label') or '').upper()
        eq_verdict_disp = (c.get('eq_verdict_display') or '').upper()
        market_verdict = _compute_market_verdict(c)

        # eq_label from Sub2 raw can be 'RISKY', but eq_verdict_display is
        # what _enrich_for_dashboard computes — check both paths
        is_risky = (eq_label == 'RISKY') or (eq_verdict_disp == 'RISKY')
        if not is_risky:
            return None

        if market_verdict == 'RESEARCH NOW':
            return _make_flag(
                check_id       = 'B_CONTRADICTION_RISKY_EQ_RESEARCH_NOW',
                subsystem      = 'cross',
                field          = 'eq_label',
                observed       = eq_label or eq_verdict_disp,
                context        = {'market_verdict': market_verdict, 'composite_confidence': c.get('composite_confidence'), 'risk_score': c.get('risk_score')},
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
        market_verdict = _compute_market_verdict(c)
        if event_risk != 'HIGH RISK':
            return None
        if market_verdict == 'RESEARCH NOW':
            return _make_flag(
                check_id       = 'B_CONTRADICTION_HIGH_RISK_EVENT_RESEARCH_NOW',
                subsystem      = 'cross',
                field          = 'event_risk',
                observed       = event_risk,
                context        = {'market_verdict': market_verdict, 'event_risk_reason': c.get('event_risk_reason')},
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
    ps_available True + entry_quality GOOD + rr_override False + risk_reward_ratio < 2.0
    is INCONSISTENT. R/R below 2.0 without override flag means the R/R gate
    was not enforced — it should have forced entry_quality to WEAK.
    """
    try:
        if not c.get('ps_available'):
            return None
        eq       = c.get('entry_quality')
        override = c.get('rr_override')
        rr       = c.get('risk_reward_ratio')
        if eq != 'GOOD' or override is True or rr is None:
            return None
        rr_f = float(rr)
        if rr_f < 2.0:
            return _make_flag(
                check_id       = 'B_CONTRADICTION_RR_GATE_NOT_ENFORCED',
                subsystem      = 'cross',
                field          = 'risk_reward_ratio',
                observed       = rr_f,
                context        = {'entry_quality': eq, 'rr_override': override},
                expected_range = 'risk_reward_ratio >= 2.0 when entry_quality is GOOD and rr_override is False',
                verdict        = INCONSISTENT,
                note           = (
                    f'risk_reward_ratio is {rr_f:.2f} (< 2.0) with entry_quality GOOD '
                    f'and rr_override False. R/R gate not enforced — entry_quality '
                    f'should have been overridden to WEAK.'
                ),
            )
        return _make_flag(
            check_id       = 'B_CONTRADICTION_RR_GATE_NOT_ENFORCED',
            subsystem      = 'cross',
            field          = 'risk_reward_ratio',
            observed       = rr_f,
            context        = {'entry_quality': eq, 'rr_override': override},
            expected_range = 'risk_reward_ratio >= 2.0 when entry_quality is GOOD and rr_override is False',
            verdict        = CONSISTENT,
            note           = f'risk_reward_ratio {rr_f:.2f} >= 2.0 with GOOD entry — R/R gate correctly passed',
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