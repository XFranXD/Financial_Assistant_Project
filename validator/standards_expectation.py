"""
validator/standards_expectation.py
Bucket C — Market Expectation checks.

These check whether outputs are consistent with typical financial behavior
for this type of stock/market context. ALL checks return CONSISTENT or
QUESTIONABLE only — never INCONSISTENT. Finance is not binary.

Key notes on data sources:
- beta and avg_volume live in c['financials'], not directly on c
- return_3m is pulled from c['mtf']['r3m'] because the validator runs before
  _enrich_for_dashboard() which copies it to c['return_3m']
- composite_confidence < 35 is a C_EXPECTATION (soft) not B_CONTRADICTION,
  because in test/force-ticker mode the filter is intentionally bypassed —
  it would always fire INCONSISTENT on valid test runs
"""

from utils.logger import get_logger
from validator.validator_schema import (
    CONSISTENT, QUESTIONABLE,
    BUCKET_EXPECTATION,
)

log = get_logger('validator.expectation')


def _make_flag(check_id: str, subsystem: str, field: str,
               observed, context: dict, expected_range: str,
               verdict: str, note: str) -> dict:
    return {
        'check_id':       check_id,
        'bucket':         BUCKET_EXPECTATION,
        'subsystem':      subsystem,
        'field':          field,
        'observed':       observed,
        'context':        context,
        'expected_range': expected_range,
        'verdict':        verdict,
        'note':           note,
    }


# ── C1 — Volume / Liquidity expectation ──────────────────────────────────────

def check_volume_liquidity(c: dict) -> list[dict]:
    """
    High volume should imply low liquidity risk, and vice versa.
    avg_volume lives in c['financials'], not directly on c.
    """
    results = []
    try:
        fin        = c.get('financials') or {}
        avg_volume = fin.get('avg_volume')
        rsk        = c.get('risk_components') or {}
        liquidity  = rsk.get('liquidity')

        if avg_volume is None or liquidity is None:
            return results

        avg_volume_f = float(avg_volume)
        liquidity_f  = float(liquidity)

        # High volume → low liquidity risk expected
        if avg_volume_f > 3_000_000 and liquidity_f > 30:
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_VOLUME_LIQUIDITY_HIGH',
                subsystem      = 'sub1',
                field          = 'risk_components.liquidity',
                observed       = liquidity_f,
                context        = {'avg_volume': avg_volume_f},
                expected_range = '0–15 for avg_volume > 3M/day',
                verdict        = QUESTIONABLE,
                note           = (
                    f'Avg volume {avg_volume_f:,.0f} typically implies near-zero liquidity risk. '
                    f'Observed {liquidity_f:.1f} — expected range 0–15 for this volume tier.'
                ),
            ))
        elif avg_volume_f > 3_000_000:
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_VOLUME_LIQUIDITY_HIGH',
                subsystem      = 'sub1',
                field          = 'risk_components.liquidity',
                observed       = liquidity_f,
                context        = {'avg_volume': avg_volume_f},
                expected_range = '0–15 for avg_volume > 3M/day',
                verdict        = CONSISTENT,
                note           = (
                    f'Avg volume {avg_volume_f:,.0f} — liquidity risk {liquidity_f:.1f} '
                    f'consistent with high-volume stock.'
                ),
            ))

        # Thin volume → elevated liquidity risk expected
        if avg_volume_f < 600_000 and liquidity_f < 10:
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_VOLUME_LIQUIDITY_LOW',
                subsystem      = 'sub1',
                field          = 'risk_components.liquidity',
                observed       = liquidity_f,
                context        = {'avg_volume': avg_volume_f},
                expected_range = '50–100 for avg_volume < 600K/day',
                verdict        = QUESTIONABLE,
                note           = (
                    f'Thin volume ({avg_volume_f:,.0f}/day) typically implies elevated liquidity risk. '
                    f'Observed {liquidity_f:.1f} — expected range 50–100 for this volume tier.'
                ),
            ))
        elif avg_volume_f < 600_000:
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_VOLUME_LIQUIDITY_LOW',
                subsystem      = 'sub1',
                field          = 'risk_components.liquidity',
                observed       = liquidity_f,
                context        = {'avg_volume': avg_volume_f},
                expected_range = '50–100 for avg_volume < 600K/day',
                verdict        = CONSISTENT,
                note           = (
                    f'Avg volume {avg_volume_f:,.0f} — liquidity risk {liquidity_f:.1f} '
                    f'consistent with thin-volume stock.'
                ),
            ))

    except Exception as e:
        log.warning(f'[FSV][C] volume_liquidity: {e}')
    return results


# ── C2 — Beta / Volatility expectation ───────────────────────────────────────

def check_beta_volatility(c: dict) -> list[dict]:
    """
    beta lives in c['financials'], not directly on c.
    High beta should map to high volatility component, low beta to low.
    """
    results = []
    try:
        fin  = c.get('financials') or {}
        beta = fin.get('beta')
        rsk  = c.get('risk_components') or {}
        vol  = rsk.get('volatility')

        if beta is None or vol is None:
            return results

        beta_f = float(beta)
        vol_f  = float(vol)

        # High beta (>2.0) → volatility component 60–95
        if beta_f > 2.0:
            if vol_f < 40:
                results.append(_make_flag(
                    check_id       = 'C_EXPECTATION_BETA_VOLATILITY_HIGH',
                    subsystem      = 'sub1',
                    field          = 'risk_components.volatility',
                    observed       = vol_f,
                    context        = {'beta': beta_f},
                    expected_range = '60–95 for beta > 2.0',
                    verdict        = QUESTIONABLE,
                    note           = (
                        f'Beta {beta_f:.2f} typically produces volatility component 60–95. '
                        f'Observed {vol_f:.1f} — statistically low for this beta.'
                    ),
                ))
            else:
                results.append(_make_flag(
                    check_id       = 'C_EXPECTATION_BETA_VOLATILITY_HIGH',
                    subsystem      = 'sub1',
                    field          = 'risk_components.volatility',
                    observed       = vol_f,
                    context        = {'beta': beta_f},
                    expected_range = '60–95 for beta > 2.0',
                    verdict        = CONSISTENT,
                    note           = (
                        f'Beta {beta_f:.2f} — volatility component {vol_f:.1f} '
                        f'consistent with high-beta stock.'
                    ),
                ))

        # Low beta (<0.7) → volatility component 5–30
        elif beta_f < 0.7:
            if vol_f > 60:
                results.append(_make_flag(
                    check_id       = 'C_EXPECTATION_BETA_VOLATILITY_LOW',
                    subsystem      = 'sub1',
                    field          = 'risk_components.volatility',
                    observed       = vol_f,
                    context        = {'beta': beta_f},
                    expected_range = '5–30 for beta < 0.7',
                    verdict        = QUESTIONABLE,
                    note           = (
                        f'Beta {beta_f:.2f} typically produces volatility component 5–30. '
                        f'Observed {vol_f:.1f} — statistically high for this beta.'
                    ),
                ))
            else:
                results.append(_make_flag(
                    check_id       = 'C_EXPECTATION_BETA_VOLATILITY_LOW',
                    subsystem      = 'sub1',
                    field          = 'risk_components.volatility',
                    observed       = vol_f,
                    context        = {'beta': beta_f},
                    expected_range = '5–30 for beta < 0.7',
                    verdict        = CONSISTENT,
                    note           = (
                        f'Beta {beta_f:.2f} — volatility component {vol_f:.1f} '
                        f'consistent with low-beta stock.'
                    ),
                ))

    except Exception as e:
        log.warning(f'[FSV][C] beta_volatility: {e}')
    return results


# ── C3 — Price history vs trend structure ────────────────────────────────────

def check_return_vs_trend(c: dict) -> list[dict]:
    """
    return_3m comes from c['mtf']['r3m'] (not c['return_3m'] — that field is
    set by _enrich_for_dashboard which runs after the validator).
    Large negative return with UP trend, or large positive return with DOWN trend,
    is atypical.
    """
    results = []
    try:
        if not c.get('ps_available'):
            return results

        mtf       = c.get('mtf') or {}
        return_3m = mtf.get('r3m')
        trend     = c.get('trend_structure')

        if return_3m is None or trend is None:
            return results

        r3m_f = float(return_3m)

        # Large decline + UP trend
        if r3m_f < -15.0 and trend == 'UP':
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_RETURN_VS_TREND_DOWN',
                subsystem      = 'sub4',
                field          = 'trend_structure',
                observed       = trend,
                context        = {'return_3m': r3m_f},
                expected_range = 'trend_structure != UP when return_3m < -15%',
                verdict        = QUESTIONABLE,
                note           = (
                    f'3-month return {r3m_f:.1f}% with UP trend structure is atypical. '
                    f'Extended price decline rarely coincides with uptrend structure.'
                ),
            ))
        elif r3m_f < -15.0:
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_RETURN_VS_TREND_DOWN',
                subsystem      = 'sub4',
                field          = 'trend_structure',
                observed       = trend,
                context        = {'return_3m': r3m_f},
                expected_range = 'trend_structure != UP when return_3m < -15%',
                verdict        = CONSISTENT,
                note           = (
                    f'3-month return {r3m_f:.1f}% — trend structure {trend} '
                    f'consistent with declining price history.'
                ),
            ))

        # Large gain + DOWN trend
        if r3m_f > 15.0 and trend == 'DOWN':
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_RETURN_VS_TREND_UP',
                subsystem      = 'sub4',
                field          = 'trend_structure',
                observed       = trend,
                context        = {'return_3m': r3m_f},
                expected_range = 'trend_structure != DOWN when return_3m > 15%',
                verdict        = QUESTIONABLE,
                note           = (
                    f'3-month return {r3m_f:.1f}% with DOWN trend structure is atypical. '
                    f'Strong recent gain rarely coincides with downtrend structure.'
                ),
            ))
        elif r3m_f > 15.0:
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_RETURN_VS_TREND_UP',
                subsystem      = 'sub4',
                field          = 'trend_structure',
                observed       = trend,
                context        = {'return_3m': r3m_f},
                expected_range = 'trend_structure != DOWN when return_3m > 15%',
                verdict        = CONSISTENT,
                note           = (
                    f'3-month return {r3m_f:.1f}% — trend structure {trend} '
                    f'consistent with positive price history.'
                ),
            ))

    except Exception as e:
        log.warning(f'[FSV][C] return_vs_trend: {e}')
    return results


# ── C4 — Stop loss proximity ──────────────────────────────────────────────────

def check_stop_loss_proximity(c: dict) -> dict | None:
    """
    Stop loss that is too tight (<2%) or too wide (>25%) is unusual.
    Only runs if all three execution levels are present.
    """
    try:
        if not c.get('ps_available'):
            return None
        entry = c.get('entry_price')
        stop  = c.get('stop_loss')
        if entry is None or stop is None:
            return None

        entry_f = float(entry)
        stop_f  = float(stop)
        if entry_f <= 0:
            return None

        stop_pct = (entry_f - stop_f) / entry_f * 100

        if stop_pct < 2.0:
            return _make_flag(
                check_id       = 'C_EXPECTATION_STOP_LOSS_PROXIMITY',
                subsystem      = 'sub4',
                field          = 'stop_loss',
                observed       = stop_pct,
                context        = {'entry_price': entry_f, 'stop_loss': stop_f},
                expected_range = '2–25% below entry price',
                verdict        = QUESTIONABLE,
                note           = (
                    f'Stop {stop_pct:.1f}% below entry is tighter than typical for equity stops. '
                    f'Risk of noise-triggered exit is high.'
                ),
            )
        elif stop_pct > 25.0:
            return _make_flag(
                check_id       = 'C_EXPECTATION_STOP_LOSS_PROXIMITY',
                subsystem      = 'sub4',
                field          = 'stop_loss',
                observed       = stop_pct,
                context        = {'entry_price': entry_f, 'stop_loss': stop_f},
                expected_range = '2–25% below entry price',
                verdict        = QUESTIONABLE,
                note           = (
                    f'Stop {stop_pct:.1f}% below entry is wider than typical. '
                    f'Position sizing implications should be reviewed.'
                ),
            )
        else:
            return _make_flag(
                check_id       = 'C_EXPECTATION_STOP_LOSS_PROXIMITY',
                subsystem      = 'sub4',
                field          = 'stop_loss',
                observed       = stop_pct,
                context        = {'entry_price': entry_f, 'stop_loss': stop_f},
                expected_range = '2–25% below entry price',
                verdict        = CONSISTENT,
                note           = (
                    f'Stop {stop_pct:.1f}% below entry — within typical 2–25% band.'
                ),
            )
    except Exception as e:
        log.warning(f'[FSV][C] stop_loss_proximity: {e}')
        return None


# ── C5 — EQ label vs warnings coexistence ────────────────────────────────────

def check_supportive_eq_with_major_warnings(c: dict) -> dict | None:
    """
    SUPPORTIVE EQ with major-severity warnings coexisting is atypical.
    """
    try:
        if not c.get('eq_available'):
            return None
        eq_label = (c.get('eq_label') or '').upper()
        # eq_verdict_display is set by _enrich_for_dashboard (runs after validator)
        # So check pass_tier == PASS as proxy for SUPPORTIVE
        pass_tier = (c.get('pass_tier') or '').upper()
        is_supportive = (eq_label in ('SUPPORTIVE',) or pass_tier == 'PASS')
        if not is_supportive:
            return None

        warnings = c.get('warnings') or []
        major_warnings = [
            w for w in warnings
            if isinstance(w, dict) and (w.get('severity') or '').lower() == 'major'
        ]
        n = len(major_warnings)

        if n > 0:
            return _make_flag(
                check_id       = 'C_EXPECTATION_SUPPORTIVE_EQ_MAJOR_WARNINGS',
                subsystem      = 'sub2',
                field          = 'eq_label',
                observed       = eq_label or pass_tier,
                context        = {'major_warning_count': n},
                expected_range = 'No major warnings when EQ is SUPPORTIVE/PASS',
                verdict        = QUESTIONABLE,
                note           = (
                    f'SUPPORTIVE EQ label coexists with {n} major-severity warning(s). '
                    f'Atypical — major warnings typically preclude SUPPORTIVE classification.'
                ),
            )
        return _make_flag(
            check_id       = 'C_EXPECTATION_SUPPORTIVE_EQ_MAJOR_WARNINGS',
            subsystem      = 'sub2',
            field          = 'eq_label',
            observed       = eq_label or pass_tier,
            context        = {'major_warning_count': 0},
            expected_range = 'No major warnings when EQ is SUPPORTIVE/PASS',
            verdict        = CONSISTENT,
            note           = 'SUPPORTIVE EQ with zero major-severity warnings — consistent',
        )
    except Exception as e:
        log.warning(f'[FSV][C] supportive_eq_major_warnings: {e}')
        return None


# ── C6 — Market regime vs market verdict ─────────────────────────────────────

def check_bear_regime_research_now(c: dict) -> dict | None:
    """
    RESEARCH NOW in BEAR regime is statistically rare and warrants awareness.
    market_regime comes from run-level context, set on each candidate dict.
    """
    try:
        market_regime  = (c.get('market_regime') or '').upper()
        market_verdict = _compute_market_verdict_local(c)
        if not market_regime or market_regime == 'NEUTRAL':
            return None
        if market_regime == 'BEAR' and market_verdict == 'RESEARCH NOW':
            return _make_flag(
                check_id       = 'C_EXPECTATION_BEAR_REGIME_RESEARCH_NOW',
                subsystem      = 'cross',
                field          = 'market_regime',
                observed       = market_regime,
                context        = {'market_verdict': market_verdict, 'composite_confidence': c.get('composite_confidence'), 'risk_score': c.get('risk_score')},
                expected_range = 'RESEARCH NOW in BEAR regime is statistically rare',
                verdict        = QUESTIONABLE,
                note           = (
                    f'RESEARCH NOW in BEAR regime is statistically rare. '
                    f'Human should reduce confidence one step per BEAR regime protocol.'
                ),
            )
        return _make_flag(
            check_id       = 'C_EXPECTATION_BEAR_REGIME_RESEARCH_NOW',
            subsystem      = 'cross',
            field          = 'market_regime',
            observed       = market_regime,
            context        = {'market_verdict': market_verdict},
            expected_range = 'RESEARCH NOW in BEAR regime is statistically rare',
            verdict        = CONSISTENT,
            note           = f'market_regime {market_regime} with market_verdict {market_verdict} — no unusual combination',
        )
    except Exception as e:
        log.warning(f'[FSV][C] bear_regime_research_now: {e}')
        return None


def _compute_market_verdict_local(c: dict) -> str:
    """Same logic as in standards_contradiction — avoid cross-module import."""
    conf = c.get('composite_confidence') or 0
    risk = c.get('risk_score') or 100
    if conf >= 70 and risk <= 35:
        return 'RESEARCH NOW'
    elif conf >= 55:
        return 'WATCH'
    return 'SKIP'


# ── C7 — Distance vs key level position ──────────────────────────────────────

def check_distance_vs_key_level(c: dict) -> list[dict]:
    """
    Distance to support and key_level_position should be directionally consistent.
    """
    results = []
    try:
        if not c.get('ps_available'):
            return results
        dist      = c.get('distance_to_support_pct')
        key_level = c.get('key_level_position')
        if dist is None or key_level is None:
            return results

        dist_f = float(dist)

        # Very close to support → should be NEAR_SUPPORT or BREAKOUT
        if dist_f < 2.0 and key_level not in ('NEAR_SUPPORT', 'BREAKOUT'):
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_DIST_VS_KEY_LEVEL_NEAR',
                subsystem      = 'sub4',
                field          = 'key_level_position',
                observed       = key_level,
                context        = {'distance_to_support_pct': dist_f},
                expected_range = 'NEAR_SUPPORT or BREAKOUT when distance_to_support_pct < 2%',
                verdict        = QUESTIONABLE,
                note           = (
                    f'Distance to support {dist_f:.1f}% but key_level_position is {key_level}. '
                    f'Expected NEAR_SUPPORT or BREAKOUT at this proximity.'
                ),
            ))
        elif dist_f < 2.0:
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_DIST_VS_KEY_LEVEL_NEAR',
                subsystem      = 'sub4',
                field          = 'key_level_position',
                observed       = key_level,
                context        = {'distance_to_support_pct': dist_f},
                expected_range = 'NEAR_SUPPORT or BREAKOUT when distance_to_support_pct < 2%',
                verdict        = CONSISTENT,
                note           = f'Distance {dist_f:.1f}% and key_level_position {key_level} — consistent',
            ))

        # Far from support (>10%) but labeled NEAR_SUPPORT
        if dist_f > 10.0 and key_level == 'NEAR_SUPPORT':
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_DIST_VS_KEY_LEVEL_FAR',
                subsystem      = 'sub4',
                field          = 'key_level_position',
                observed       = key_level,
                context        = {'distance_to_support_pct': dist_f},
                expected_range = 'key_level_position != NEAR_SUPPORT when distance_to_support_pct > 10%',
                verdict        = QUESTIONABLE,
                note           = (
                    f'key_level_position is NEAR_SUPPORT but distance to support is {dist_f:.1f}%. '
                    f'Atypical — NEAR_SUPPORT expected within 3%.'
                ),
            ))
        elif dist_f > 10.0:
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_DIST_VS_KEY_LEVEL_FAR',
                subsystem      = 'sub4',
                field          = 'key_level_position',
                observed       = key_level,
                context        = {'distance_to_support_pct': dist_f},
                expected_range = 'key_level_position != NEAR_SUPPORT when distance_to_support_pct > 10%',
                verdict        = CONSISTENT,
                note           = f'Distance {dist_f:.1f}% and key_level_position {key_level} — consistent',
            ))

    except Exception as e:
        log.warning(f'[FSV][C] distance_vs_key_level: {e}')
    return results


# ── C8 — Insider signal vs system call ───────────────────────────────────────

def check_insider_distributing_research_now(c: dict) -> dict | None:
    """
    Insiders distributing while system produces RESEARCH NOW + GOOD entry is atypical.
    """
    try:
        insider_signal = (c.get('insider_signal') or '').upper()
        if insider_signal != 'DISTRIBUTING':
            return None
        eq             = c.get('entry_quality')
        market_verdict = _compute_market_verdict_local(c)

        if eq == 'GOOD' and market_verdict == 'RESEARCH NOW':
            return _make_flag(
                check_id       = 'C_EXPECTATION_INSIDER_DISTRIBUTING_RESEARCH_NOW',
                subsystem      = 'cross',
                field          = 'insider_signal',
                observed       = insider_signal,
                context        = {'entry_quality': eq, 'market_verdict': market_verdict},
                expected_range = 'Insider DISTRIBUTING with RESEARCH NOW + GOOD entry is atypical',
                verdict        = QUESTIONABLE,
                note           = (
                    f'Insiders distributing while system produces RESEARCH NOW + GOOD entry. '
                    f'Atypical combination — warrants manual review before acting.'
                ),
            )
        return _make_flag(
            check_id       = 'C_EXPECTATION_INSIDER_DISTRIBUTING_RESEARCH_NOW',
            subsystem      = 'cross',
            field          = 'insider_signal',
            observed       = insider_signal,
            context        = {'entry_quality': eq, 'market_verdict': market_verdict},
            expected_range = 'Insider DISTRIBUTING with RESEARCH NOW + GOOD entry is atypical',
            verdict        = CONSISTENT,
            note           = (
                f'Insider DISTRIBUTING but market_verdict is {market_verdict} '
                f'and entry_quality is {eq} — combination does not trigger soft concern'
            ),
        )
    except Exception as e:
        log.warning(f'[FSV][C] insider_distributing_research_now: {e}')
        return None


# ── C9 — Low composite confidence (soft, not hard gate) ──────────────────────

def check_low_confidence(c: dict) -> dict | None:
    """
    composite_confidence < 35 is below the scheduled-run filter threshold.
    This is QUESTIONABLE not INCONSISTENT because in test/force-ticker mode
    the filter is intentionally bypassed — it's always valid in debug runs.
    The note flags it for awareness without breaking anything.
    """
    try:
        conf = c.get('composite_confidence')
        if conf is None:
            return None
        conf_f = float(conf)
        if conf_f < 35:
            return _make_flag(
                check_id       = 'C_EXPECTATION_LOW_CONFIDENCE',
                subsystem      = 'sub1',
                field          = 'composite_confidence',
                observed       = conf_f,
                context        = {},
                expected_range = '>= 35 for scheduled runs (filter threshold)',
                verdict        = QUESTIONABLE,
                note           = (
                    f'composite_confidence {conf_f:.1f} is below the scheduled-run filter '
                    f'threshold of 35. Acceptable in force-ticker/test mode — '
                    f'unexpected in a scheduled run.'
                ),
            )
        return None  # Above threshold — no flag needed (saves noise)
    except Exception as e:
        log.warning(f'[FSV][C] low_confidence: {e}')
        return None


# ── Runner ────────────────────────────────────────────────────────────────────

def run_expectation_checks(c: dict) -> list[dict]:
    """Run all Bucket C checks. Returns list of flag dicts (no Nones)."""
    results = []

    single_checks = [
        check_stop_loss_proximity,
        check_supportive_eq_with_major_warnings,
        check_bear_regime_research_now,
        check_insider_distributing_research_now,
        check_low_confidence,
    ]

    for fn in single_checks:
        try:
            result = fn(c)
            if result is not None:
                results.append(result)
        except Exception as e:
            log.warning(f'[FSV][C] check {fn.__name__} crashed: {e}')

    # Multi-result checks
    for multi_fn in [check_volume_liquidity, check_beta_volatility,
                     check_return_vs_trend, check_distance_vs_key_level]:
        try:
            results.extend(multi_fn(c))
        except Exception as e:
            log.warning(f'[FSV][C] check {multi_fn.__name__} crashed: {e}')

    return results