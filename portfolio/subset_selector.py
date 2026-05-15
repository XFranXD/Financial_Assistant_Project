"""
portfolio/subset_selector.py
Layer 2: Cluster pruning + MAX_POSITIONS cap.
"""

import logging
from contracts.portfolio_schema import MAX_POSITIONS
from price_structure.execution_layer import MIN_RR_THRESHOLD

log = logging.getLogger(__name__)

# Tier definitions (lower = higher priority):
#   Tier 0 — GOOD entry + R:R >= threshold  → fully tradeable
#   Tier 1 — GOOD entry + R:R <  threshold  → structurally valid, not executable
#   Tier 2 — non-GOOD entry + R:R >= threshold → high payoff, structurally weaker
#   Tier 3 — non-GOOD entry + R:R <  threshold → weakest

def _tier(entry_quality: str, rr) -> int:
    if rr is None:
        return 3
    good    = entry_quality == 'GOOD'
    high_rr = float(rr) >= MIN_RR_THRESHOLD
    if good and high_rr:
        return 0
    if good and not high_rr:
        return 1
    if not good and high_rr:
        return 2
    return 3


def select(
    candidates:        list[dict],
    clusters:          list[list[str]],
    ticker_to_cluster: dict[str, int],
    unavailable:       list[str],
    max_positions:     int = MAX_POSITIONS,
) -> tuple[list[str], dict[str, str]]:
    """
    Input:
        candidates:        list[dict] with 'ticker', 'opp_price_trend',
                           'entry_quality', and 'risk_reward_ratio' keys
        clusters:          list[list[str]] from correlation_engine (sorted)
        ticker_to_cluster: dict[str, int]
        unavailable:       list[str] — tickers excluded due to data issues
        max_positions:     int — hard cap

    Output:
        selected_tickers  — list[str] ordered by tier then opp_price_trend
        exclusion_reasons — dict[str, str] for all excluded tickers
    """
    conf_map: dict[str, float] = {
        c.get('ticker', ''): float(c.get('opp_price_trend', 0))
        for c in candidates if c.get('ticker')
    }

    tier_map: dict[str, int] = {
        c.get('ticker', ''): _tier(
            c.get('entry_quality', ''),
            c.get('risk_reward_ratio'),
        )
        for c in candidates if c.get('ticker')
    }

    def sort_key(t: str) -> tuple:
        return (tier_map.get(t, 3), -conf_map.get(t, 0), t)

    exclusion_reasons: dict[str, str] = {}
    selected: list[str] = []

    for t in unavailable:
        exclusion_reasons[t] = 'UNAVAILABLE'

    for cluster in clusters:
        eligible = [t for t in cluster if t not in exclusion_reasons]
        if not eligible:
            continue
        if len(eligible) <= 2:
            selected.extend(eligible)
        else:
            ranked = sorted(eligible, key=sort_key)
            selected.extend(ranked[:2])
            for t in ranked[2:]:
                exclusion_reasons[t] = 'CORRELATED'
                log.info(f'[PL] {t} excluded — CORRELATED (cluster {ticker_to_cluster.get(t)})')

    if len(selected) > max_positions:
        ranked_selected = sorted(selected, key=sort_key)
        for t in ranked_selected[max_positions:]:
            exclusion_reasons[t] = 'RANK_CUT'
            log.info(f'[PL] {t} excluded — RANK_CUT (cap={max_positions})')
        selected = ranked_selected[:max_positions]

    selected = sorted(selected, key=sort_key)

    log.info(f'[PL] Subset selected: {selected} | Excluded: {list(exclusion_reasons.keys())}')
    return selected, exclusion_reasons
    