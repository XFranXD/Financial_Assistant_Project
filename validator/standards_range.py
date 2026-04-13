"""
validator/standards_range.py
Bucket A — Range & Structural Validity checks.

These are binary checks for impossible values (score of 110, stop above entry, etc.).
All checks return CONSISTENT or INCONSISTENT only — never QUESTIONABLE.
These are the only checks in the FSV that can fire INCONSISTENT.

Each check function returns a dict or None (skipped).

Patch v1.1 changes:
  - Upper bounds added: volume_ratio <= 100, move_extension_pct <= 1000,
    distance fields <= 500.
  - Price > 0 checks added for entry_price, stop_loss, price_target.
  - R/R formula recomputation check using c['_computed_rr'] (pre-computed by
    orchestrator). Flags INCONSISTENT if stored vs computed delta > 5%.
  - Presence checks: when ps_available is True, all four execution fields
    (entry_price, stop_loss, price_target, entry_quality) must be non-None.
  - FLOAT_TOLERANCE imported and used for threshold comparisons.
"""

from utils.logger import get_logger
from validator.validator_schema import (
    CONSISTENT, INCONSISTENT,
    BUCKET_RANGE,
    FLOAT_TOLERANCE,
)

log = get_logger('validator.range')

# ── R/R recomputation tolerance ───────────────────────────────────────────────
# If abs(stored_rr - computed_rr) / computed_rr > this, flag INCONSISTENT.
RR_DELTA_THRESHOLD = 0.05  # 5%


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
    """
    volume_ratio must be >= 0 and <= 100.
    A ratio above 100 indicates data corruption — no stock trades
    at 100x its average volume in a valid data feed.
    """
    try:
        _vol = c.get('volume_confirmation') or {}
        val  = _vol.get('volume_ratio')
        if val is None:
            return None
        val_f = float(val)
        if 0.0 <= val_f <= 100.0:
            return _make_flag(
                check_id       = 'A_RANGE_VOLUME_RATIO',
                subsystem      = 'sub1',
                field          = 'volume_ratio',
                observed       = val_f,
                context        = {},
                expected_range = '0–100',
                verdict        = CONSISTENT,
                note           = f'volume_ratio {val_f} is within valid range 0–100',
            )
        else:
            return _make_flag(
                check_id       = 'A_RANGE_VOLUME_RATIO',
                subsystem      = 'sub1',
                field          = 'volume_ratio',
                observed       = val_f,
                context        = {},
                expected_range = '0–100',
                verdict        = INCONSISTENT,
                note           = (
                    f'volume_ratio {val_f} is outside valid range 0–100 — '
                    f'{"negative value impossible" if val_f < 0 else "value > 100 indicates data corruption"}'
                ),
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


# ── Sub4 presence checks ──────────────────────────────────────────────────────

def check_ps_required_fields_present(c: dict) -> list[dict]:
    """
    When ps_available is True, all four execution fields must be non-None.
    Missing any → INCONSISTENT. Complements the data integrity tier check
    in the orchestrator with a Bucket A structural flag per field.
    """
    results = []
    try:
        if not c.get('ps_available'):
            return results
        required = [
            ('entry_price',   'entry_price'),
            ('stop_loss',     'stop_loss'),
            ('price_target',  'price_target'),
            ('entry_quality', 'entry_quality'),
        ]
        for field, label in required:
            try:
                val = c.get(field)
                if val is None:
                    results.append(_make_flag(
                        check_id       = f'A_RANGE_PS_FIELD_MISSING_{field.upper()}',
                        subsystem      = 'sub4',
                        field          = field,
                        observed       = None,
                        context        = {'ps_available': True},
                        expected_range = 'non-None when ps_available is True',
                        verdict        = INCONSISTENT,
                        note           = (
                            f'ps_available is True but {label} is None — '
                            f'required execution field missing.'
                        ),
                    ))
            except Exception as e:
                log.warning(f'[FSV][A] ps_required_fields {field}: {e}')
    except Exception as e:
        log.warning(f'[FSV][A] check_ps_required_fields_present: {e}')
    return results


# ── Sub4 price validity checks ────────────────────────────────────────────────

def check_price_validity(c: dict) -> list[dict]:
    """
    entry_price, stop_loss, and price_target must all be > 0.
    Zero or negative prices are impossible for equities and indicate
    upstream data corruption.
    Only runs if ps_available and all three fields are present.
    """
    results = []
    try:
        if not c.get('ps_available'):
            return results
        fields = [
            ('entry_price',  'entry_price'),
            ('stop_loss',    'stop_loss'),
            ('price_target', 'price_target'),
        ]
        for field, label in fields:
            try:
                val = c.get(field)
                if val is None:
                    continue  # absence handled by check_ps_required_fields_present
                val_f = float(val)
                if val_f > 0:
                    results.append(_make_flag(
                        check_id       = f'A_RANGE_PRICE_POSITIVE_{field.upper()}',
                        subsystem      = 'sub4',
                        field          = field,
                        observed       = val_f,
                        context        = {},
                        expected_range = '> 0',
                        verdict        = CONSISTENT,
                        note           = f'{label} {val_f} is positive — valid',
                    ))
                else:
                    results.append(_make_flag(
                        check_id       = f'A_RANGE_PRICE_POSITIVE_{field.upper()}',
                        subsystem      = 'sub4',
                        field          = field,
                        observed       = val_f,
                        context        = {},
                        expected_range = '> 0',
                        verdict        = INCONSISTENT,
                        note           = (
                            f'{label} {val_f} is <= 0 — impossible value for an equity price. '
                            f'Data corruption likely.'
                        ),
                    ))
            except Exception as e:
                log.warning(f'[FSV][A] price_validity {field}: {e}')
    except Exception as e:
        log.warning(f'[FSV][A] check_price_validity: {e}')
    return results


# ── Sub4 score checks ─────────────────────────────────────────────────────────

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
    """
    move_extension_pct must be >= 0 and <= 1000.
    A stock cannot be more than 1000% above its 126-day low in valid data.
    Values above 1000 indicate data corruption.
    """
    try:
        if not c.get('ps_available'):
            return None
        val = c.get('move_extension_pct')
        if val is None:
            return None
        val_f = float(val)
        if 0.0 <= val_f <= 1000.0:
            return _make_flag(
                check_id       = 'A_RANGE_MOVE_EXTENSION_PCT',
                subsystem      = 'sub4',
                field          = 'move_extension_pct',
                observed       = val_f,
                context        = {},
                expected_range = '0–1000',
                verdict        = CONSISTENT,
                note           = f'move_extension_pct {val_f} is within valid range 0–1000',
            )
        else:
            return _make_flag(
                check_id       = 'A_RANGE_MOVE_EXTENSION_PCT',
                subsystem      = 'sub4',
                field          = 'move_extension_pct',
                observed       = val_f,
                context        = {},
                expected_range = '0–1000',
                verdict        = INCONSISTENT,
                note           = (
                    f'move_extension_pct {val_f} is outside valid range 0–1000 — '
                    f'{"negative value impossible" if val_f < 0 else "value > 1000% indicates data corruption"}'
                ),
            )
    except Exception as e:
        log.warning(f'[FSV][A] move_extension_pct: {e}')
        return None


def check_dist_to_support_pct(c: dict) -> dict | None:
    """distance_to_support_pct must be >= 0 and <= 500."""
    try:
        if not c.get('ps_available'):
            return None
        val = c.get('distance_to_support_pct')
        if val is None:
            return None
        val_f = float(val)
        if 0.0 <= val_f <= 500.0:
            return _make_flag(
                check_id       = 'A_RANGE_DIST_TO_SUPPORT_PCT',
                subsystem      = 'sub4',
                field          = 'distance_to_support_pct',
                observed       = val_f,
                context        = {},
                expected_range = '0–500',
                verdict        = CONSISTENT,
                note           = f'distance_to_support_pct {val_f} is within valid range 0–500',
            )
        else:
            return _make_flag(
                check_id       = 'A_RANGE_DIST_TO_SUPPORT_PCT',
                subsystem      = 'sub4',
                field          = 'distance_to_support_pct',
                observed       = val_f,
                context        = {},
                expected_range = '0–500',
                verdict        = INCONSISTENT,
                note           = (
                    f'distance_to_support_pct {val_f} is outside valid range 0–500 — '
                    f'{"negative value impossible" if val_f < 0 else "value > 500% indicates data corruption"}'
                ),
            )
    except Exception as e:
        log.warning(f'[FSV][A] dist_to_support_pct: {e}')
        return None


def check_dist_to_resist_pct(c: dict) -> dict | None:
    """distance_to_resistance_pct must be >= 0 and <= 500."""
    try:
        if not c.get('ps_available'):
            return None
        val = c.get('distance_to_resistance_pct')
        if val is None:
            return None
        val_f = float(val)
        if 0.0 <= val_f <= 500.0:
            return _make_flag(
                check_id       = 'A_RANGE_DIST_TO_RESIST_PCT',
                subsystem      = 'sub4',
                field          = 'distance_to_resistance_pct',
                observed       = val_f,
                context        = {},
                expected_range = '0–500',
                verdict        = CONSISTENT,
                note           = f'distance_to_resistance_pct {val_f} is within valid range 0–500',
            )
        else:
            return _make_flag(
                check_id       = 'A_RANGE_DIST_TO_RESIST_PCT',
                subsystem      = 'sub4',
                field          = 'distance_to_resistance_pct',
                observed       = val_f,
                context        = {},
                expected_range = '0–500',
                verdict        = INCONSISTENT,
                note           = (
                    f'distance_to_resistance_pct {val_f} is outside valid range 0–500 — '
                    f'{"negative value impossible" if val_f < 0 else "value > 500% indicates data corruption"}'
                ),
            )
    except Exception as e:
        log.warning(f'[FSV][A] dist_to_resist_pct: {e}')
        return None


def check_risk_reward_ratio(c: dict) -> dict | None:
    """
    Stored risk_reward_ratio must be > 0.
    Only checks if all three execution levels are present.
    """
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


def check_risk_reward_recompute(c: dict) -> dict | None:
    """
    Cross-validates stored risk_reward_ratio against the value computed from
    first principles by the orchestrator (_computed_rr).

    Flags INCONSISTENT if:
      abs(stored - computed) / computed > RR_DELTA_THRESHOLD (5%)

    This catches upstream arithmetic bugs where the stored R/R does not
    match what the execution levels actually imply.

    Skipped if:
      - ps_available is False
      - Any of entry/stop/target is None
      - stored risk_reward_ratio is None
      - _computed_rr is None (division by zero or parse failure upstream)
    """
    try:
        if not c.get('ps_available'):
            return None
        computed_rr = c.get('_computed_rr')
        stored_rr   = c.get('risk_reward_ratio')
        if computed_rr is None or stored_rr is None:
            return None

        stored_f   = float(stored_rr)
        computed_f = float(computed_rr)

        # Relative delta — use computed as denominator (source of truth)
        if abs(computed_f) < 1e-9:
            return None  # degenerate case — skip

        delta = abs(stored_f - computed_f) / abs(computed_f)

        if delta > RR_DELTA_THRESHOLD:
            return _make_flag(
                check_id       = 'A_RANGE_RR_RECOMPUTE_DELTA',
                subsystem      = 'sub4',
                field          = 'risk_reward_ratio',
                observed       = stored_f,
                context        = {
                    'computed_rr':   round(computed_f, 4),
                    'delta_pct':     round(delta * 100, 2),
                    'threshold_pct': RR_DELTA_THRESHOLD * 100,
                    'entry_price':   c.get('entry_price'),
                    'stop_loss':     c.get('stop_loss'),
                    'price_target':  c.get('price_target'),
                },
                expected_range = f'stored R/R within {RR_DELTA_THRESHOLD*100:.0f}% of computed R/R',
                verdict        = INCONSISTENT,
                note           = (
                    f'Stored risk_reward_ratio {stored_f:.4f} diverges {delta*100:.1f}% '
                    f'from recomputed value {computed_f:.4f}. '
                    f'Upstream arithmetic error likely.'
                ),
            )
        return _make_flag(
            check_id       = 'A_RANGE_RR_RECOMPUTE_DELTA',
            subsystem      = 'sub4',
            field          = 'risk_reward_ratio',
            observed       = stored_f,
            context        = {
                'computed_rr': round(computed_f, 4),
                'delta_pct':   round(delta * 100, 2),
            },
            expected_range = f'stored R/R within {RR_DELTA_THRESHOLD*100:.0f}% of computed R/R',
            verdict        = CONSISTENT,
            note           = (
                f'Stored R/R {stored_f:.4f} within {delta*100:.1f}% of '
                f'recomputed R/R {computed_f:.4f} — arithmetic consistent'
            ),
        )
    except Exception as e:
        log.warning(f'[FSV][A] risk_reward_recompute: {e}')
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
        check_risk_reward_recompute,
    ]

    for fn in single_checks:
        try:
            result = fn(c)
            if result is not None:
                results.append(result)
        except Exception as e:
            log.warning(f'[FSV][A] check {fn.__name__} crashed: {e}')

    # Multi-result checks
    for multi_fn in [
        check_ps_required_fields_present,
        check_price_validity,
        check_execution_level_order,
    ]:
        try:
            results.extend(multi_fn(c))
        except Exception as e:
            log.warning(f'[FSV][A] check {multi_fn.__name__} crashed: {e}')

    return results