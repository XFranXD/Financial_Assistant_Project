"""
analyzers/zscore_ranker.py — Z-score normalisation across full candidate pool.
Max 3 companies per sector. Max 25 total. Unusual volume flag adds +0.3 boost.
Companies above regime risk_cap are excluded before ranking.
"""

import statistics
from utils.logger import get_logger
from config import MAX_COMPANIES_PER_SECTOR, MAX_TOTAL_COMPANIES, UNUSUAL_VOLUME_RANKING_BOOST

log = get_logger('zscore_ranker')


def _zscore(value: float, mean: float, std: float) -> float:
    """Safe z-score. Returns 0.0 if std is zero."""
    if std == 0:
        return 0.0
    return (value - mean) / std


def rank_candidates(candidates: list[dict], risk_cap: float) -> list[dict]:
    """
    Ranks candidates using z-score normalisation.

    Input: list of candidate dicts, each must have:
        'ticker', 'sector', 'opportunity_score', 'risk_score',
        'composite_confidence', 'unusual_volume' (dict with 'unusual_flag')

    Steps:
        1. Exclude candidates above risk_cap
        2. Compute ranking_index = z(opportunity) - z(risk) + unusual_boost
        3. Sort descending by ranking_index
        4. Apply max 3 per sector cap
        5. Return top MAX_TOTAL_COMPANIES

    Returns: sorted list of candidate dicts with 'ranking_index' and 'final_rank' added.
    """
    # Step 1: filter by risk cap
    eligible = [c for c in candidates if c.get('risk_score', 100) <= risk_cap]
    excluded = len(candidates) - len(eligible)
    if excluded:
        log.info(f'Z-score ranker: excluded {excluded} candidates above risk_cap={risk_cap}')

    if not eligible:
        log.info('Z-score ranker: no eligible candidates after risk cap filter')
        return []

    # Step 2: compute z-scores across eligible pool
    opp_vals  = [c.get('opportunity_score', 50) for c in eligible]
    risk_vals = [c.get('risk_score', 50) for c in eligible]

    opp_mean  = statistics.mean(opp_vals)
    opp_std   = statistics.pstdev(opp_vals) or 1.0
    risk_mean = statistics.mean(risk_vals)
    risk_std  = statistics.pstdev(risk_vals) or 1.0

    for c in eligible:
        z_opp   = _zscore(c.get('opportunity_score', 50), opp_mean, opp_std)
        z_risk  = _zscore(c.get('risk_score', 50), risk_mean, risk_std)
        unusual_boost = (
            UNUSUAL_VOLUME_RANKING_BOOST
            if c.get('unusual_volume', {}).get('unusual_flag', False)
            else 0.0
        )
        c['ranking_index'] = round(z_opp - z_risk + unusual_boost, 4)

    # Step 3: sort descending
    ranked = sorted(eligible, key=lambda c: c['ranking_index'], reverse=True)

    # Step 4: apply max-per-sector cap
    sector_counts: dict[str, int] = {}
    sector_capped: list[dict]     = []
    for c in ranked:
        sector = c.get('sector', 'unknown')
        count  = sector_counts.get(sector, 0)
        if count < MAX_COMPANIES_PER_SECTOR:
            sector_capped.append(c)
            sector_counts[sector] = count + 1
        else:
            log.info(f'Sector cap ({MAX_COMPANIES_PER_SECTOR}): skipped {c["ticker"]} ({sector})')

    # Step 5: top N total
    final = sector_capped[:MAX_TOTAL_COMPANIES]

    # Add final rank
    for i, c in enumerate(final):
        c['final_rank'] = i + 1

    log.info(
        f'Z-score ranking complete: {len(candidates)} → {len(eligible)} eligible → '
        f'{len(final)} final (max {MAX_TOTAL_COMPANIES}, cap {MAX_COMPANIES_PER_SECTOR}/sector)'
    )
    return final
