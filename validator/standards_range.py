"""
validator/standards_range.py
Bucket A — Range & Structural Validity checks.

These are binary checks for impossible values (score of 110, stop above entry, etc.).
All checks return CONSISTENT or INCONSISTENT only — never QUESTIONABLE.
These are the only checks in the FSV that can fire INCONSISTENT.

Each check function returns a dict or None (skipped).
"""

from utils.logger import get_logger
from validator.validator_schema import (
    CONSISTENT, INCONSISTENT,
    BUCKET_RANGE,
)

log = get_logger('validator.range')


def _make_flag(check_id: str, subsystem: str, field: str,
               observed, context: dict, expected_range: str,
               verdict: str, note: str) -> dict:
    return {
        'check_id':       check_id,
        'bucket':         BUCKET_RANGE,
        'subsystem':      subsystem,
        'field':          field,
        'observed':       observed,
        'context':        context,
        'expected_range': expected_range,
        'verdict':        verdict,
        'note':           note,
    }


def _check_score_range(c: dict, field: str, subsystem: str,
                       lo: float = 0.0, hi: float = 100.0) -> dict | None:
    """Generic 0–100 score range check. Returns None if field absent."""
    try:
        val = c.get(field)
        if val is None:
            return None
        val_f = float(val)
        if lo <= val_f <= hi:
            return _make_flag(
                check_id       = f'A_RANGE_{field.upper()}',
                subsystem      = subsystem,
                field          = field,
                observed       = val_f,
                context        = {},
                expected_range = f'{lo}–{hi}',
                verdict        = CONSISTENT,
                note           = f'{field} {val_f} is within valid range {lo}–{hi}',
            )
        else:
            return _make_flag(
                check_id       = f'A_RANGE_{field.upper()}',
                subsystem      = subsystem,
                field          = field,
                observed       = val_f,
                context        = {},
                expected_range = f'{lo}–{hi}',
                verdict        = INCONSISTENT,
                note           = f'{field} {val_f} is outside valid range {lo}–{hi} — impossible value',
            )
    except Exception as e:
        log.warning(f'[FSV][A] _check_score_range {field}: {e}')
        return None


# ── Sub1 checks ───────────────────────────────────────────────────────────────

def check_composite_confidence(c: dict) -> dict | None:
    try:
        return _check_score_range(c, 'composite_confidence', 'sub1')
    except Exception as e:
        log.warning(f'[FSV][A] composite_confidence: {e}')
        return None


def check_risk_score(c: dict) -> dict | None:
    try:
        return _check_score_range(c, 'risk_score', 'sub1')
    except Exception as e:
        log.warning(f'[FSV][A] risk_score: {e}')
        return None


def check_opportunity_score(c: dict) -> dict | None:
    try:
        return _check_score_range(c, 'opportunity_score', 'sub1')
    except Exception as e:
        log.warning(f'[FSV][A] opportunity_score: {e}')
        return None


def check_agreement_score(c: dict) -> dict | None:
    """agreement_score is 0–1 (not 0–100)."""
    try:
        val = c.get('agreement_score')
        if val is None:
            return None
        val_f = float(val)
        if 0.0 <= val_f <= 1.0:
            return _make_flag(
                check_id       = 'A_RANGE_AGREEMENT_SCORE',
                subsystem      = 'sub1',
                field          = 'agreement_score',
                observed       = val_f,
                context        = {},
                expected_range = '0–1',
                verdict        = CONSISTENT,
                note           = f'agreement_score {val_f} is within valid range 0–1',
            )
        else:
            return _make_flag(
                check_id       = 'A_RANGE_AGREEMENT_SCORE',
                subsystem      = 'sub1',
                field          = 'agreement_score',
                observed       = val_f,
                context        = {},
                expected_range = '0–1',
                verdict        = INCONSISTENT,
                note           = f'agreement_score {val_f} is outside valid range 0–1 — impossible value',
            )
    except Exception as e:
        log.warning(f'[FSV][A] agreement_score: {e}')
        return None


def check_volume_ratio(c: dict) -> dict | None:
    try:
        _vol = c.get('volume_confirmation') or {}
        val  = _vol.get('volume_ratio')
        if val is None:
            return None
        val_f = float(val)
        if val_f >= 0:
            return _make_flag(
                check_id       = 'A_RANGE_VOLUME_RATIO',
                subsystem      = 'sub1',
                field          = 'volume_ratio',
                observed       = val_f,
                context        = {},
                expected_range = '>= 0',
                verdict        = CONSISTENT,
                note           = f'volume_ratio {val_f} is non-negative — valid',
            )
        else:
            return _make_flag(
                check_id       = 'A_RANGE_VOLUME_RATIO',
                subsystem      = 'sub1',
                field          = 'volume_ratio',
                observed       = val_f,
                context        = {},
                expected_range = '>= 0',
                verdict        = INCONSISTENT,
                note           = f'volume_ratio {val_f} is negative — impossible value',
            )
    except Exception as e:
        log.warning(f'[FSV][A] volume_ratio: {e}')
        return None


# ── Sub2 checks ───────────────────────────────────────────────────────────────

def check_eq_score_final(c: dict) -> dict | None:
    try:
        if not c.get('eq_available'):
            return None
        val = c.get('eq_score_final')
        if val is None:
            return _make_flag(
                check_id       = 'A_RANGE_EQ_SCORE_FINAL',
                subsystem      = 'sub2',
                field          = 'eq_score_final',
                observed       = None,
                context        = {'eq_available': True},
                expected_range = '0–100',
                verdict        = INCONSISTENT,
                note           = 'eq_available is True but eq_score_final is None — missing expected field',
            )
        return _check_score_range(c, 'eq_score_final', 'sub2')
    except Exception as e:
        log.warning(f'[FSV][A] eq_score_final: {e}')
        return None


# ── Sub3 checks ───────────────────────────────────────────────────────────────

def check_rotation_score(c: dict) -> dict | None:
    try:
        if not c.get('rotation_available'):
            return None
        val = c.get('rotation_score')
        if val is None:
            return _make_flag(
                check_id       = 'A_RANGE_ROTATION_SCORE',
                subsystem      = 'sub3',
                field          = 'rotation_score',
                observed       = None,
                context        = {'rotation_available': True},
                expected_range = '0–100',
                verdict        = INCONSISTENT,
                note           = 'rotation_available is True but rotation_score is None — missing expected field',
            )
        return _check_score_range(c, 'rotation_score', 'sub3')
    except Exception as e:
        log.warning(f'[FSV][A] rotation_score: {e}')
        return None


# ── Sub4 checks ───────────────────────────────────────────────────────────────

def check_trend_strength(c: dict) -> dict | None:
    try:
        if not c.get('ps_available'):
            return None
        return _check_score_range(c, 'trend_strength', 'sub4')
    except Exception as e:
        log.warning(f'[FSV][A] trend_strength: {e}')
        return None


def check_price_action_score(c: dict) -> dict | None:
    try:
        if not c.get('ps_available'):
            return None
        return _check_score_range(c, 'price_action_score', 'sub4')
    except Exception as e:
        log.warning(f'[FSV][A] price_action_score: {e}')
        return None


def check_move_extension_pct(c: dict) -> dict | None:
    try:
        if not c.get('ps_available'):
            return None
        val = c.get('move_extension_pct')
        if val is None:
            return None
        val_f = float(val)
        if val_f >= 0:
            return _make_flag(
                check_id       = 'A_RANGE_MOVE_EXTENSION_PCT',
                subsystem      = 'sub4',
                field          = 'move_extension_pct',
                observed       = val_f,
                context        = {},
                expected_range = '>= 0',
                verdict        = CONSISTENT,
                note           = f'move_extension_pct {val_f} is non-negative — valid',
            )
        else:
            return _make_flag(
                check_id       = 'A_RANGE_MOVE_EXTENSION_PCT',
                subsystem      = 'sub4',
                field          = 'move_extension_pct',
                observed       = val_f,
                context        = {},
                expected_range = '>= 0',
                verdict        = INCONSISTENT,
                note           = f'move_extension_pct {val_f} is negative — impossible value (% above 126-day low cannot be negative)',
            )
    except Exception as e:
        log.warning(f'[FSV][A] move_extension_pct: {e}')
        return None


def check_dist_to_support_pct(c: dict) -> dict | None:
    try:
        if not c.get('ps_available'):
            return None
        val = c.get('distance_to_support_pct')
        if val is None:
            return None
        val_f = float(val)
        verdict = CONSISTENT if val_f >= 0 else INCONSISTENT
        note = (
            f'distance_to_support_pct {val_f} is non-negative — valid'
            if verdict == CONSISTENT else
            f'distance_to_support_pct {val_f} is negative — impossible value'
        )
        return _make_flag(
            check_id       = 'A_RANGE_DIST_TO_SUPPORT_PCT',
            subsystem      = 'sub4',
            field          = 'distance_to_support_pct',
            observed       = val_f,
            context        = {},
            expected_range = '>= 0',
            verdict        = verdict,
            note           = note,
        )
    except Exception as e:
        log.warning(f'[FSV][A] dist_to_support_pct: {e}')
        return None


def check_dist_to_resist_pct(c: dict) -> dict | None:
    try:
        if not c.get('ps_available'):
            return None
        val = c.get('distance_to_resistance_pct')
        if val is None:
            return None
        val_f = float(val)
        verdict = CONSISTENT if val_f >= 0 else INCONSISTENT
        note = (
            f'distance_to_resistance_pct {val_f} is non-negative — valid'
            if verdict == CONSISTENT else
            f'distance_to_resistance_pct {val_f} is negative — impossible value'
        )
        return _make_flag(
            check_id       = 'A_RANGE_DIST_TO_RESIST_PCT',
            subsystem      = 'sub4',
            field          = 'distance_to_resistance_pct',
            observed       = val_f,
            context        = {},
            expected_range = '>= 0',
            verdict        = verdict,
            note           = note,
        )
    except Exception as e:
        log.warning(f'[FSV][A] dist_to_resist_pct: {e}')
        return None


def check_risk_reward_ratio(c: dict) -> dict | None:
    """Only check if all three execution levels are present."""
    try:
        if not c.get('ps_available'):
            return None
        entry  = c.get('entry_price')
        stop   = c.get('stop_loss')
        target = c.get('price_target')
        if entry is None or stop is None or target is None:
            return None
        val = c.get('risk_reward_ratio')
        if val is None:
            return _make_flag(
                check_id       = 'A_RANGE_RISK_REWARD_RATIO',
                subsystem      = 'sub4',
                field          = 'risk_reward_ratio',
                observed       = None,
                context        = {'entry_price': entry, 'stop_loss': stop, 'price_target': target},
                expected_range = '> 0',
                verdict        = INCONSISTENT,
                note           = 'All three execution levels present but risk_reward_ratio is None — missing expected field',
            )
        val_f = float(val)
        if val_f > 0:
            return _make_flag(
                check_id       = 'A_RANGE_RISK_REWARD_RATIO',
                subsystem      = 'sub4',
                field          = 'risk_reward_ratio',
                observed       = val_f,
                context        = {},
                expected_range = '> 0',
                verdict        = CONSISTENT,
                note           = f'risk_reward_ratio {val_f} is positive — valid',
            )
        else:
            return _make_flag(
                check_id       = 'A_RANGE_RISK_REWARD_RATIO',
                subsystem      = 'sub4',
                field          = 'risk_reward_ratio',
                observed       = val_f,
                context        = {'entry_price': entry, 'stop_loss': stop, 'price_target': target},
                expected_range = '> 0',
                verdict        = INCONSISTENT,
                note           = f'risk_reward_ratio {val_f} is <= 0 — impossible value',
            )
    except Exception as e:
        log.warning(f'[FSV][A] risk_reward_ratio: {e}')
        return None


def check_execution_level_order(c: dict) -> list[dict]:
    """
    Structural invariant: stop_loss < entry_price < price_target.
    Returns up to three flags (one per pair), only if all three levels present.
    """
    results = []
    try:
        if not c.get('ps_available'):
            return results
        entry  = c.get('entry_price')
        stop   = c.get('stop_loss')
        target = c.get('price_target')
        if entry is None or stop is None or target is None:
            return results

        entry_f  = float(entry)
        stop_f   = float(stop)
        target_f = float(target)

        # Check 1: stop_loss < entry_price
        ctx_se = {'stop_loss': stop_f, 'entry_price': entry_f}
        if stop_f < entry_f:
            results.append(_make_flag(
                check_id       = 'A_RANGE_STOP_BELOW_ENTRY',
                subsystem      = 'sub4',
                field          = 'stop_loss',
                observed       = stop_f,
                context        = ctx_se,
                expected_range = 'stop_loss < entry_price',
                verdict        = CONSISTENT,
                note           = f'stop_loss {stop_f} < entry_price {entry_f} — structural order correct',
            ))
        else:
            results.append(_make_flag(
                check_id       = 'A_RANGE_STOP_BELOW_ENTRY',
                subsystem      = 'sub4',
                field          = 'stop_loss',
                observed       = stop_f,
                context        = ctx_se,
                expected_range = 'stop_loss < entry_price',
                verdict        = INCONSISTENT,
                note           = f'stop_loss {stop_f} >= entry_price {entry_f} — structural invariant violated',
            ))

        # Check 2: entry_price < price_target
        ctx_et = {'entry_price': entry_f, 'price_target': target_f}
        if entry_f < target_f:
            results.append(_make_flag(
                check_id       = 'A_RANGE_ENTRY_BELOW_TARGET',
                subsystem      = 'sub4',
                field          = 'entry_price',
                observed       = entry_f,
                context        = ctx_et,
                expected_range = 'entry_price < price_target',
                verdict        = CONSISTENT,
                note           = f'entry_price {entry_f} < price_target {target_f} — structural order correct',
            ))
        else:
            results.append(_make_flag(
                check_id       = 'A_RANGE_ENTRY_BELOW_TARGET',
                subsystem      = 'sub4',
                field          = 'entry_price',
                observed       = entry_f,
                context        = ctx_et,
                expected_range = 'entry_price < price_target',
                verdict        = INCONSISTENT,
                note           = f'entry_price {entry_f} >= price_target {target_f} — structural invariant violated',
            ))

        # Check 3: stop_loss < price_target
        ctx_st = {'stop_loss': stop_f, 'price_target': target_f}
        if stop_f < target_f:
            results.append(_make_flag(
                check_id       = 'A_RANGE_STOP_BELOW_TARGET',
                subsystem      = 'sub4',
                field          = 'stop_loss',
                observed       = stop_f,
                context        = ctx_st,
                expected_range = 'stop_loss < price_target',
                verdict        = CONSISTENT,
                note           = f'stop_loss {stop_f} < price_target {target_f} — structural order correct',
            ))
        else:
            results.append(_make_flag(
                check_id       = 'A_RANGE_STOP_BELOW_TARGET',
                subsystem      = 'sub4',
                field          = 'stop_loss',
                observed       = stop_f,
                context        = ctx_st,
                expected_range = 'stop_loss < price_target',
                verdict        = INCONSISTENT,
                note           = f'stop_loss {stop_f} >= price_target {target_f} — structural invariant violated',
            ))

    except Exception as e:
        log.warning(f'[FSV][A] execution_level_order: {e}')

    return results


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_range_checks(c: dict) -> list[dict]:
    """Run all Bucket A checks. Returns list of flag dicts (no Nones)."""
    results = []

    single_checks = [
        check_composite_confidence,
        check_risk_score,
        check_opportunity_score,
        check_agreement_score,
        check_volume_ratio,
        check_eq_score_final,
        check_rotation_score,
        check_trend_strength,
        check_price_action_score,
        check_move_extension_pct,
        check_dist_to_support_pct,
        check_dist_to_resist_pct,
        check_risk_reward_ratio,
    ]

    for fn in single_checks:
        try:
            result = fn(c)
            if result is not None:
                results.append(result)
        except Exception as e:
            log.warning(f'[FSV][A] check {fn.__name__} crashed: {e}')

    # Multi-result check
    try:
        results.extend(check_execution_level_order(c))
    except Exception as e:
        log.warning(f'[FSV][A] check execution_level_order crashed: {e}')

    return results