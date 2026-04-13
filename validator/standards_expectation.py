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

Patch v1.1 changes:
  - compute_market_verdict imported from validator_schema (no local duplicate).
  - All calibration thresholds extracted to named constants at top of file.
  - return_vs_trend threshold tightened from -15% to -25% to avoid flagging
    valid early-reversal / trend-change setups.
  - Stop loss proximity uses beta-tiered ranges with None fallback and 40%
    hard upper cap.
  - GOOD entry + distance_to_support_pct > 12% → QUESTIONABLE (C9 new check).
  - High composite_confidence + high risk_score → QUESTIONABLE (C10 new check).
  - Insider distributing note softened to reflect diversification context.
  - log.warning used consistently on expectation (QUESTIONABLE) paths.
"""

from utils.logger import get_logger
from validator.validator_schema import (
    CONSISTENT, QUESTIONABLE,
    BUCKET_EXPECTATION,
    compute_market_verdict,
)

log = get_logger('validator.expectation')

# ── Calibration constants ─────────────────────────────────────────────────────
# All thresholds live here. Adjust without hunting through logic.

# C1 — Volume / Liquidity
VOL_HIGH_AVG_THRESHOLD    = 3_000_000   # avg_volume above this = high-volume stock
VOL_LOW_AVG_THRESHOLD     = 600_000     # avg_volume below this = thin-volume stock
VOL_HIGH_LIQUIDITY_MAX    = 15          # expected liquidity risk ceiling for high-volume
VOL_LOW_LIQUIDITY_MIN     = 50          # expected liquidity risk floor for thin-volume

# C2 — Beta / Volatility
BETA_HIGH_THRESHOLD       = 2.0         # beta above this = high-beta
BETA_LOW_THRESHOLD        = 0.7         # beta below this = low-beta
BETA_HIGH_VOL_MIN         = 40          # volatility component floor for high-beta
BETA_LOW_VOL_MAX          = 60          # volatility component ceiling for low-beta

# C3 — Return vs Trend
RETURN_DECLINE_THRESHOLD  = -25.0       # 3m return below this with UP trend = atypical
RETURN_GAIN_THRESHOLD     = 15.0        # 3m return above this with DOWN trend = atypical

# C4 — Stop Loss Proximity
STOP_DEFAULT_MIN_PCT      = 2.0         # minimum stop distance (default band)
STOP_DEFAULT_MAX_PCT      = 25.0        # maximum stop distance (default band)
STOP_HIGH_BETA_THRESHOLD  = 1.8         # beta above this uses high-beta stop band
STOP_HIGH_BETA_MAX_PCT    = 35.0        # maximum stop distance for high-beta stocks
STOP_LOW_BETA_THRESHOLD   = 0.8         # beta below this uses low-beta stop band
STOP_LOW_BETA_MAX_PCT     = 20.0        # maximum stop distance for low-beta stocks
STOP_HARD_CAP_PCT         = 40.0        # absolute maximum stop distance regardless of beta

# C6 — Bear regime
BEAR_REGIME_FLAG          = 'BEAR'

# C7 — Distance vs key level
DIST_NEAR_SUPPORT_MAX     = 2.0         # within this % = near support
DIST_FAR_SUPPORT_MIN      = 10.0        # beyond this % = far from support label

# C9 — Good entry vs support distance
GOOD_ENTRY_SUPPORT_MAX    = 12.0        # GOOD entry with dist > this = atypical

# C10 — High confidence + high risk
HIGH_CONF_THRESHOLD       = 75.0        # composite_confidence >= this
HIGH_RISK_THRESHOLD       = 70.0        # risk_score >= this


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
        if avg_volume_f > VOL_HIGH_AVG_THRESHOLD and liquidity_f > VOL_HIGH_LIQUIDITY_MAX:
            log.warning(
                f'[FSV][C] QUESTIONABLE: avg_volume {avg_volume_f:,.0f} but '
                f'liquidity risk {liquidity_f:.1f} > {VOL_HIGH_LIQUIDITY_MAX}'
            )
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_VOLUME_LIQUIDITY_HIGH',
                subsystem      = 'sub1',
                field          = 'risk_components.liquidity',
                observed       = liquidity_f,
                context        = {'avg_volume': avg_volume_f},
                expected_range = f'0–{VOL_HIGH_LIQUIDITY_MAX} for avg_volume > {VOL_HIGH_AVG_THRESHOLD/1e6:.0f}M/day',
                verdict        = QUESTIONABLE,
                note           = (
                    f'Avg volume {avg_volume_f:,.0f} typically implies near-zero liquidity risk. '
                    f'Observed {liquidity_f:.1f} — expected range 0–{VOL_HIGH_LIQUIDITY_MAX} for this volume tier.'
                ),
            ))
        elif avg_volume_f > VOL_HIGH_AVG_THRESHOLD:
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_VOLUME_LIQUIDITY_HIGH',
                subsystem      = 'sub1',
                field          = 'risk_components.liquidity',
                observed       = liquidity_f,
                context        = {'avg_volume': avg_volume_f},
                expected_range = f'0–{VOL_HIGH_LIQUIDITY_MAX} for avg_volume > {VOL_HIGH_AVG_THRESHOLD/1e6:.0f}M/day',
                verdict        = CONSISTENT,
                note           = (
                    f'Avg volume {avg_volume_f:,.0f} — liquidity risk {liquidity_f:.1f} '
                    f'consistent with high-volume stock.'
                ),
            ))

        # Thin volume → elevated liquidity risk expected
        if avg_volume_f < VOL_LOW_AVG_THRESHOLD and liquidity_f < VOL_LOW_LIQUIDITY_MIN:
            log.warning(
                f'[FSV][C] QUESTIONABLE: avg_volume {avg_volume_f:,.0f} but '
                f'liquidity risk {liquidity_f:.1f} < {VOL_LOW_LIQUIDITY_MIN}'
            )
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_VOLUME_LIQUIDITY_LOW',
                subsystem      = 'sub1',
                field          = 'risk_components.liquidity',
                observed       = liquidity_f,
                context        = {'avg_volume': avg_volume_f},
                expected_range = f'{VOL_LOW_LIQUIDITY_MIN}–100 for avg_volume < {VOL_LOW_AVG_THRESHOLD/1e3:.0f}K/day',
                verdict        = QUESTIONABLE,
                note           = (
                    f'Thin volume ({avg_volume_f:,.0f}/day) typically implies elevated liquidity risk. '
                    f'Observed {liquidity_f:.1f} — expected range {VOL_LOW_LIQUIDITY_MIN}–100 for this volume tier.'
                ),
            ))
        elif avg_volume_f < VOL_LOW_AVG_THRESHOLD:
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_VOLUME_LIQUIDITY_LOW',
                subsystem      = 'sub1',
                field          = 'risk_components.liquidity',
                observed       = liquidity_f,
                context        = {'avg_volume': avg_volume_f},
                expected_range = f'{VOL_LOW_LIQUIDITY_MIN}–100 for avg_volume < {VOL_LOW_AVG_THRESHOLD/1e3:.0f}K/day',
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
    Note: beta is market-relative, not absolute — this check catches extreme
    mismatches only. Borderline cases are expected and not flagged.
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

        # High beta (> threshold) → volatility component >= BETA_HIGH_VOL_MIN
        if beta_f > BETA_HIGH_THRESHOLD:
            if vol_f < BETA_HIGH_VOL_MIN:
                log.warning(
                    f'[FSV][C] QUESTIONABLE: beta {beta_f:.2f} but '
                    f'volatility component {vol_f:.1f} < {BETA_HIGH_VOL_MIN}'
                )
                results.append(_make_flag(
                    check_id       = 'C_EXPECTATION_BETA_VOLATILITY_HIGH',
                    subsystem      = 'sub1',
                    field          = 'risk_components.volatility',
                    observed       = vol_f,
                    context        = {'beta': beta_f},
                    expected_range = f'>= {BETA_HIGH_VOL_MIN} for beta > {BETA_HIGH_THRESHOLD}',
                    verdict        = QUESTIONABLE,
                    note           = (
                        f'Beta {beta_f:.2f} typically produces volatility component >= {BETA_HIGH_VOL_MIN}. '
                        f'Observed {vol_f:.1f} — statistically low for this beta. '
                        f'Note: beta is market-relative and may not directly predict short-term volatility.'
                    ),
                ))
            else:
                results.append(_make_flag(
                    check_id       = 'C_EXPECTATION_BETA_VOLATILITY_HIGH',
                    subsystem      = 'sub1',
                    field          = 'risk_components.volatility',
                    observed       = vol_f,
                    context        = {'beta': beta_f},
                    expected_range = f'>= {BETA_HIGH_VOL_MIN} for beta > {BETA_HIGH_THRESHOLD}',
                    verdict        = CONSISTENT,
                    note           = (
                        f'Beta {beta_f:.2f} — volatility component {vol_f:.1f} '
                        f'consistent with high-beta stock.'
                    ),
                ))

        # Low beta (< threshold) → volatility component <= BETA_LOW_VOL_MAX
        elif beta_f < BETA_LOW_THRESHOLD:
            if vol_f > BETA_LOW_VOL_MAX:
                log.warning(
                    f'[FSV][C] QUESTIONABLE: beta {beta_f:.2f} but '
                    f'volatility component {vol_f:.1f} > {BETA_LOW_VOL_MAX}'
                )
                results.append(_make_flag(
                    check_id       = 'C_EXPECTATION_BETA_VOLATILITY_LOW',
                    subsystem      = 'sub1',
                    field          = 'risk_components.volatility',
                    observed       = vol_f,
                    context        = {'beta': beta_f},
                    expected_range = f'<= {BETA_LOW_VOL_MAX} for beta < {BETA_LOW_THRESHOLD}',
                    verdict        = QUESTIONABLE,
                    note           = (
                        f'Beta {beta_f:.2f} typically produces volatility component <= {BETA_LOW_VOL_MAX}. '
                        f'Observed {vol_f:.1f} — statistically high for this beta. '
                        f'Note: beta is market-relative and may not directly predict short-term volatility.'
                    ),
                ))
            else:
                results.append(_make_flag(
                    check_id       = 'C_EXPECTATION_BETA_VOLATILITY_LOW',
                    subsystem      = 'sub1',
                    field          = 'risk_components.volatility',
                    observed       = vol_f,
                    context        = {'beta': beta_f},
                    expected_range = f'<= {BETA_LOW_VOL_MAX} for beta < {BETA_LOW_THRESHOLD}',
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

    Threshold is -25% (not -15%) to avoid flagging valid early-reversal setups
    where a stock has declined but is beginning to form higher lows (UP trend).
    A -25% sustained decline with UP trend is a stronger anomaly signal.
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

        # Large sustained decline + UP trend
        if r3m_f < RETURN_DECLINE_THRESHOLD and trend == 'UP':
            log.warning(
                f'[FSV][C] QUESTIONABLE: return_3m {r3m_f:.1f}% with UP trend'
            )
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_RETURN_VS_TREND_DOWN',
                subsystem      = 'sub4',
                field          = 'trend_structure',
                observed       = trend,
                context        = {'return_3m': r3m_f},
                expected_range = f'trend_structure != UP when return_3m < {RETURN_DECLINE_THRESHOLD}%',
                verdict        = QUESTIONABLE,
                note           = (
                    f'3-month return {r3m_f:.1f}% with UP trend structure is atypical. '
                    f'A sustained decline of this magnitude rarely coincides with uptrend structure. '
                    f'Early reversals are possible — warrants manual review.'
                ),
            ))
        elif r3m_f < RETURN_DECLINE_THRESHOLD:
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_RETURN_VS_TREND_DOWN',
                subsystem      = 'sub4',
                field          = 'trend_structure',
                observed       = trend,
                context        = {'return_3m': r3m_f},
                expected_range = f'trend_structure != UP when return_3m < {RETURN_DECLINE_THRESHOLD}%',
                verdict        = CONSISTENT,
                note           = (
                    f'3-month return {r3m_f:.1f}% — trend structure {trend} '
                    f'consistent with declining price history.'
                ),
            ))

        # Large gain + DOWN trend
        if r3m_f > RETURN_GAIN_THRESHOLD and trend == 'DOWN':
            log.warning(
                f'[FSV][C] QUESTIONABLE: return_3m {r3m_f:.1f}% with DOWN trend'
            )
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_RETURN_VS_TREND_UP',
                subsystem      = 'sub4',
                field          = 'trend_structure',
                observed       = trend,
                context        = {'return_3m': r3m_f},
                expected_range = f'trend_structure != DOWN when return_3m > {RETURN_GAIN_THRESHOLD}%',
                verdict        = QUESTIONABLE,
                note           = (
                    f'3-month return {r3m_f:.1f}% with DOWN trend structure is atypical. '
                    f'Strong recent gain rarely coincides with downtrend structure.'
                ),
            ))
        elif r3m_f > RETURN_GAIN_THRESHOLD:
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_RETURN_VS_TREND_UP',
                subsystem      = 'sub4',
                field          = 'trend_structure',
                observed       = trend,
                context        = {'return_3m': r3m_f},
                expected_range = f'trend_structure != DOWN when return_3m > {RETURN_GAIN_THRESHOLD}%',
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
    Stop loss proximity check with beta-tiered acceptable ranges.

    Tiers:
      beta > STOP_HIGH_BETA_THRESHOLD (1.8): allow 2% – 35%
      beta < STOP_LOW_BETA_THRESHOLD  (0.8): allow 2% – 20%
      beta None or in between:               allow 2% – 25% (default)

    Hard cap: 40% maximum regardless of beta. A stop wider than 40% is
    outside any normal equity trading range.

    If beta is None or unparseable, falls back to default range.
    Only runs if entry_price and stop_loss are present.
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

        # Determine acceptable max based on beta
        beta_f    = None
        beta_note = ''
        try:
            fin    = c.get('financials') or {}
            raw_b  = fin.get('beta')
            if raw_b is not None:
                beta_f = float(raw_b)
        except (TypeError, ValueError):
            beta_f = None

        if beta_f is not None and beta_f > STOP_HIGH_BETA_THRESHOLD:
            stop_max = STOP_HIGH_BETA_MAX_PCT
            beta_note = f' (high-beta {beta_f:.2f} — wider range applied)'
        elif beta_f is not None and beta_f < STOP_LOW_BETA_THRESHOLD:
            stop_max = STOP_LOW_BETA_MAX_PCT
            beta_note = f' (low-beta {beta_f:.2f} — tighter range applied)'
        else:
            stop_max = STOP_DEFAULT_MAX_PCT
            beta_note = ' (default range — beta not available or mid-range)' if beta_f is None else ''

        # Hard cap overrides beta tier
        effective_max = min(stop_max, STOP_HARD_CAP_PCT)

        band_str = f'{STOP_DEFAULT_MIN_PCT}–{effective_max}%{beta_note}'

        if stop_pct < STOP_DEFAULT_MIN_PCT:
            log.warning(f'[FSV][C] QUESTIONABLE: stop_pct {stop_pct:.1f}% < {STOP_DEFAULT_MIN_PCT}%')
            return _make_flag(
                check_id       = 'C_EXPECTATION_STOP_LOSS_PROXIMITY',
                subsystem      = 'sub4',
                field          = 'stop_loss',
                observed       = stop_pct,
                context        = {'entry_price': entry_f, 'stop_loss': stop_f, 'beta': beta_f},
                expected_range = band_str,
                verdict        = QUESTIONABLE,
                note           = (
                    f'Stop {stop_pct:.1f}% below entry is tighter than typical for equity stops. '
                    f'Risk of noise-triggered exit is high.'
                ),
            )
        elif stop_pct > effective_max:
            log.warning(f'[FSV][C] QUESTIONABLE: stop_pct {stop_pct:.1f}% > {effective_max}%')
            return _make_flag(
                check_id       = 'C_EXPECTATION_STOP_LOSS_PROXIMITY',
                subsystem      = 'sub4',
                field          = 'stop_loss',
                observed       = stop_pct,
                context        = {'entry_price': entry_f, 'stop_loss': stop_f, 'beta': beta_f},
                expected_range = band_str,
                verdict        = QUESTIONABLE,
                note           = (
                    f'Stop {stop_pct:.1f}% below entry is wider than typical{beta_note}. '
                    f'Position sizing implications should be reviewed.'
                ),
            )
        else:
            return _make_flag(
                check_id       = 'C_EXPECTATION_STOP_LOSS_PROXIMITY',
                subsystem      = 'sub4',
                field          = 'stop_loss',
                observed       = stop_pct,
                context        = {'entry_price': entry_f, 'stop_loss': stop_f, 'beta': beta_f},
                expected_range = band_str,
                verdict        = CONSISTENT,
                note           = f'Stop {stop_pct:.1f}% below entry — within acceptable band{beta_note}.',
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
        eq_label  = (c.get('eq_label') or '').upper()
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
            log.warning(
                f'[FSV][C] QUESTIONABLE: SUPPORTIVE EQ with {n} major warning(s)'
            )
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
        market_verdict = compute_market_verdict(c)
        if not market_regime or market_regime == 'NEUTRAL':
            return None
        if market_regime == BEAR_REGIME_FLAG and market_verdict == 'RESEARCH NOW':
            log.warning(
                f'[FSV][C] QUESTIONABLE: RESEARCH NOW in BEAR regime'
            )
            return _make_flag(
                check_id       = 'C_EXPECTATION_BEAR_REGIME_RESEARCH_NOW',
                subsystem      = 'cross',
                field          = 'market_regime',
                observed       = market_regime,
                context        = {
                    'market_verdict':        market_verdict,
                    'composite_confidence':  c.get('composite_confidence'),
                    'risk_score':            c.get('risk_score'),
                },
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
        if dist_f < DIST_NEAR_SUPPORT_MAX and key_level not in ('NEAR_SUPPORT', 'BREAKOUT'):
            log.warning(
                f'[FSV][C] QUESTIONABLE: distance_to_support {dist_f:.1f}% '
                f'but key_level_position is {key_level}'
            )
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_DIST_VS_KEY_LEVEL_NEAR',
                subsystem      = 'sub4',
                field          = 'key_level_position',
                observed       = key_level,
                context        = {'distance_to_support_pct': dist_f},
                expected_range = f'NEAR_SUPPORT or BREAKOUT when distance_to_support_pct < {DIST_NEAR_SUPPORT_MAX}%',
                verdict        = QUESTIONABLE,
                note           = (
                    f'Distance to support {dist_f:.1f}% but key_level_position is {key_level}. '
                    f'Expected NEAR_SUPPORT or BREAKOUT at this proximity.'
                ),
            ))
        elif dist_f < DIST_NEAR_SUPPORT_MAX:
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_DIST_VS_KEY_LEVEL_NEAR',
                subsystem      = 'sub4',
                field          = 'key_level_position',
                observed       = key_level,
                context        = {'distance_to_support_pct': dist_f},
                expected_range = f'NEAR_SUPPORT or BREAKOUT when distance_to_support_pct < {DIST_NEAR_SUPPORT_MAX}%',
                verdict        = CONSISTENT,
                note           = f'Distance {dist_f:.1f}% and key_level_position {key_level} — consistent',
            ))

        # Far from support but labeled NEAR_SUPPORT
        if dist_f > DIST_FAR_SUPPORT_MIN and key_level == 'NEAR_SUPPORT':
            log.warning(
                f'[FSV][C] QUESTIONABLE: key_level NEAR_SUPPORT but '
                f'distance_to_support {dist_f:.1f}% > {DIST_FAR_SUPPORT_MIN}%'
            )
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_DIST_VS_KEY_LEVEL_FAR',
                subsystem      = 'sub4',
                field          = 'key_level_position',
                observed       = key_level,
                context        = {'distance_to_support_pct': dist_f},
                expected_range = f'key_level_position != NEAR_SUPPORT when distance_to_support_pct > {DIST_FAR_SUPPORT_MIN}%',
                verdict        = QUESTIONABLE,
                note           = (
                    f'key_level_position is NEAR_SUPPORT but distance to support is {dist_f:.1f}%. '
                    f'Atypical — NEAR_SUPPORT expected within ~3%.'
                ),
            ))
        elif dist_f > DIST_FAR_SUPPORT_MIN:
            results.append(_make_flag(
                check_id       = 'C_EXPECTATION_DIST_VS_KEY_LEVEL_FAR',
                subsystem      = 'sub4',
                field          = 'key_level_position',
                observed       = key_level,
                context        = {'distance_to_support_pct': dist_f},
                expected_range = f'key_level_position != NEAR_SUPPORT when distance_to_support_pct > {DIST_FAR_SUPPORT_MIN}%',
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
    Note: insider selling is not inherently bearish — diversification and
    compensation plans are common non-bearish reasons. This is a soft signal
    warranting awareness, not a red flag.
    """
    try:
        insider_signal = (c.get('insider_signal') or '').upper()
        if insider_signal != 'DISTRIBUTING':
            return None
        eq             = c.get('entry_quality')
        market_verdict = compute_market_verdict(c)

        if eq == 'GOOD' and market_verdict == 'RESEARCH NOW':
            log.warning(
                f'[FSV][C] QUESTIONABLE: insider DISTRIBUTING with '
                f'RESEARCH NOW + GOOD entry'
            )
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
                    f'Atypical combination — warrants manual review before acting. '
                    f'Note: insider selling may reflect diversification or compensation, '
                    f'not necessarily a negative outlook.'
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
    """
    try:
        conf = c.get('composite_confidence')
        if conf is None:
            return None
        conf_f = float(conf)
        if conf_f < 35:
            log.warning(
                f'[FSV][C] QUESTIONABLE: composite_confidence {conf_f:.1f} < 35'
            )
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


# ── C10 — Good entry far from support ────────────────────────────────────────

def check_good_entry_far_from_support(c: dict) -> dict | None:
    """
    GOOD entry quality with distance_to_support_pct > GOOD_ENTRY_SUPPORT_MAX (12%)
    is atypical. A GOOD entry should be near a structural anchor (support).
    Entry far from support increases downside risk if the move fails.

    Only fires when entry_quality is GOOD and ps_available is True.
    """
    try:
        if not c.get('ps_available'):
            return None
        eq   = c.get('entry_quality')
        dist = c.get('distance_to_support_pct')
        if eq != 'GOOD' or dist is None:
            return None
        dist_f = float(dist)
        if dist_f > GOOD_ENTRY_SUPPORT_MAX:
            log.warning(
                f'[FSV][C] QUESTIONABLE: GOOD entry but distance_to_support '
                f'{dist_f:.1f}% > {GOOD_ENTRY_SUPPORT_MAX}%'
            )
            return _make_flag(
                check_id       = 'C_EXPECTATION_GOOD_ENTRY_FAR_FROM_SUPPORT',
                subsystem      = 'sub4',
                field          = 'distance_to_support_pct',
                observed       = dist_f,
                context        = {'entry_quality': eq},
                expected_range = f'distance_to_support_pct <= {GOOD_ENTRY_SUPPORT_MAX}% for GOOD entry',
                verdict        = QUESTIONABLE,
                note           = (
                    f'GOOD entry quality but distance to nearest support is {dist_f:.1f}% '
                    f'(> {GOOD_ENTRY_SUPPORT_MAX}%). A structurally anchored entry typically '
                    f'sits closer to support. Increased downside risk if move fails.'
                ),
            )
        return _make_flag(
            check_id       = 'C_EXPECTATION_GOOD_ENTRY_FAR_FROM_SUPPORT',
            subsystem      = 'sub4',
            field          = 'distance_to_support_pct',
            observed       = dist_f,
            context        = {'entry_quality': eq},
            expected_range = f'distance_to_support_pct <= {GOOD_ENTRY_SUPPORT_MAX}% for GOOD entry',
            verdict        = CONSISTENT,
            note           = (
                f'GOOD entry with distance_to_support_pct {dist_f:.1f}% '
                f'within expected range — structurally anchored.'
            ),
        )
    except Exception as e:
        log.warning(f'[FSV][C] good_entry_far_from_support: {e}')
        return None


# ── C11 — High confidence + high risk anomaly ─────────────────────────────────

def check_high_confidence_high_risk(c: dict) -> dict | None:
    """
    composite_confidence >= HIGH_CONF_THRESHOLD (75) with
    risk_score >= HIGH_RISK_THRESHOLD (70) is atypical.

    These two values are designed to move inversely in a well-functioning
    scoring system. A stock with very high confidence and very high risk
    simultaneously suggests the scoring components may be pulling in
    contradictory directions — warrants manual review.

    Thresholds set deliberately high (75/70) to avoid firing on normal
    volatile growth stocks where moderate divergence is expected.
    """
    try:
        conf = c.get('composite_confidence')
        risk = c.get('risk_score')
        if conf is None or risk is None:
            return None
        conf_f = float(conf)
        risk_f = float(risk)

        if conf_f >= HIGH_CONF_THRESHOLD and risk_f >= HIGH_RISK_THRESHOLD:
            log.warning(
                f'[FSV][C] QUESTIONABLE: composite_confidence {conf_f:.1f} '
                f'with risk_score {risk_f:.1f}'
            )
            return _make_flag(
                check_id       = 'C_EXPECTATION_HIGH_CONF_HIGH_RISK',
                subsystem      = 'sub1',
                field          = 'composite_confidence',
                observed       = conf_f,
                context        = {'risk_score': risk_f},
                expected_range = (
                    f'composite_confidence and risk_score should not both exceed '
                    f'{HIGH_CONF_THRESHOLD}/{HIGH_RISK_THRESHOLD} simultaneously'
                ),
                verdict        = QUESTIONABLE,
                note           = (
                    f'composite_confidence {conf_f:.1f} and risk_score {risk_f:.1f} '
                    f'are both elevated. These metrics are expected to move inversely — '
                    f'simultaneous high values suggest scoring drift or data anomaly. '
                    f'Manual review recommended.'
                ),
            )
        return None  # No flag when not both elevated — saves noise
    except Exception as e:
        log.warning(f'[FSV][C] high_confidence_high_risk: {e}')
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
        check_good_entry_far_from_support,
        check_high_confidence_high_risk,
    ]

    for fn in single_checks:
        try:
            result = fn(c)
            if result is not None:
                results.append(result)
        except Exception as e:
            log.warning(f'[FSV][C] check {fn.__name__} crashed: {e}')

    # Multi-result checks
    for multi_fn in [
        check_volume_liquidity,
        check_beta_volatility,
        check_return_vs_trend,
        check_distance_vs_key_level,
    ]:
        try:
            results.extend(multi_fn(c))
        except Exception as e:
            log.warning(f'[FSV][C] check {multi_fn.__name__} crashed: {e}')

    return results