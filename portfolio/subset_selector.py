"""
portfolio/subset_selector.py
Layer 2: Cluster pruning + MAX_POSITIONS cap.
"""

import logging
from contracts.portfolio_schema import MAX_POSITIONS

log = logging.getLogger(__name__)


def select(
    candidates:        list[dict],
    clusters:          list[list[str]],
    ticker_to_cluster: dict[str, int],
    unavailable:       list[str],
    max_positions:     int = MAX_POSITIONS,
) -> tuple[list[str], dict[str, str]]:
    """
    Input:
        candidates:        list[dict] with 'ticker' and 'composite_confidence' keys
        clusters:          list[list[str]] from correlation_engine (sorted)
        ticker_to_cluster: dict[str, int]
        unavailable:       list[str] — tickers excluded due to data issues
        max_positions:     int — hard cap

    Output:
        selected_tickers  — list[str] ordered by composite_confidence descending
        exclusion_reasons — dict[str, str] for all excluded tickers
    """
    conf_map: dict[str, float] = {
        c.get('ticker', ''): float(c.get('composite_confidence', 0))
        for c in candidates if c.get('ticker')
    }

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
            ranked = sorted(eligible, key=lambda t: conf_map.get(t, 0), reverse=True)
            selected.extend(ranked[:2])
            for t in ranked[2:]:
                exclusion_reasons[t] = 'CORRELATED'
                log.info(f'[PL] {t} excluded — CORRELATED (cluster {ticker_to_cluster.get(t)})')

    if len(selected) > max_positions:
        ranked_selected = sorted(selected, key=lambda t: conf_map.get(t, 0), reverse=True)
        for t in ranked_selected[max_positions:]:
            exclusion_reasons[t] = 'RANK_CUT'
            log.info(f'[PL] {t} excluded — RANK_CUT (cap={max_positions})')
        selected = ranked_selected[:max_positions]

    selected = sorted(selected, key=lambda t: conf_map.get(t, 0), reverse=True)

    log.info(f'[PL] Subset selected: {selected} | Excluded: {list(exclusion_reasons.keys())}')
    return selected, exclusion_reasons
