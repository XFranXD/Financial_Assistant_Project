"""
analyzers/zscore_ranker.py — Lexicographic ranking on atomic component scores.
No aggregate scores. Ranking is fully traceable to individual inputs.

Priority order (descending):
  1. opp_financial_health    — business quality, slowest-moving
  2. opp_price_trend         — trade timing signal
  3. opp_market_confirmation — volume/breadth confirmation
  4. -risk_component_volatility — lower volatility preferred
  5. -risk_component_drawdown   — lower drawdown preferred

Max 3 companies per sector. Max 25 total. Unusual volume flag adds priority boost
by temporarily inflating opp_price_trend for tie-breaking purposes only.
"""

from utils.logger import get_logger
from config import MAX_COMPANIES_PER_SECTOR, MAX_TOTAL_COMPANIES, UNUSUAL_VOLUME_RANKING_BOOST

log = get_logger('zscore_ranker')


def rank_candidates(candidates: list[dict], risk_cap: float) -> list[dict]:
    """
    Ranks candidates using lexicographic tuple on atomic component scores.

    Input: list of candidate dicts, each must have:
        'ticker', 'sector',
        'opp_financial_health', 'opp_price_trend', 'opp_market_confirmation',
        'risk_component_volatility', 'risk_component_drawdown',
        'unusual_volume' (dict with 'unusual_flag')

    Steps:
        1. Exclude candidates where risk_component_volatility > risk_cap
           OR risk_component_drawdown > risk_cap (either elevated = excluded)
        2. Sort by lexicographic tuple descending
        3. Apply max 3 per sector cap
        4. Return top MAX_TOTAL_COMPANIES

    Returns: sorted list of candidate dicts with 'ranking_index' and 'final_rank' added.
    """
    # Step 1: filter by risk cap — exclude if either primary risk component exceeds cap
    eligible = [
        c for c in candidates
        if (
            c.get('risk_component_volatility', 100) <= risk_cap and
            c.get('risk_component_drawdown',   100) <= risk_cap
        )
    ]
    excluded = len(candidates) - len(eligible)
    if excluded:
        log.info(f'Ranker: excluded {excluded} candidates above risk_cap={risk_cap}')

    if not eligible:
        log.info('Ranker: no eligible candidates after risk cap filter')
        return []

    # Step 2: build sort key and assign ranking_index for traceability
    for c in eligible:
        pt = c.get('opp_price_trend', 0)
        # Unusual volume boost: temporarily adds to price_trend for tie-breaking only
        if c.get('unusual_volume', {}).get('unusual_flag', False):
            pt = min(100, pt + UNUSUAL_VOLUME_RANKING_BOOST * 100)

        c['_rank_tuple'] = (
            c.get('opp_financial_health',    0),
            pt,
            c.get('opp_market_confirmation', 0),
            -c.get('risk_component_volatility', 50),
            -c.get('risk_component_drawdown',   50),
        )
        # Store a human-readable summary for log traceability
        c['ranking_index'] = round(
            c.get('opp_financial_health', 0) * 0.001 +
            pt * 0.001,
            6
        )

    # Step 3: sort descending by tuple
    ranked = sorted(eligible, key=lambda c: c['_rank_tuple'], reverse=True)

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

    # Clean up temp key and add final rank
    for i, c in enumerate(final):
        c.pop('_rank_tuple', None)
        c['final_rank'] = i + 1

    log.info(
        f'Ranking complete: {len(candidates)} → {len(eligible)} eligible → '
        f'{len(final)} final (max {MAX_TOTAL_COMPANIES}, cap {MAX_COMPANIES_PER_SECTOR}/sector)'
    )
    return final
