"""
portfolio/portfolio_analyzer.py
Sub5 orchestrator. Single public function called by main.py.
Mirrors price_structure/price_structure_analyzer.py pattern.
"""

import logging
import numpy as np
from contracts.portfolio_schema import (
    PL_CLUSTER_ID, PL_CORRELATION_FLAGS, PL_SELECTED,
    PL_EXCLUSION_REASON, PL_POSITION_WEIGHT, PL_AVAILABLE,
    PL_RECOMMENDED_SUBSET, PL_EXCLUDED_CANDIDATES,
    PL_SECTOR_EXPOSURE, PL_AVG_CORRELATION, PL_DIVERSIFICATION_SCORE,
    MAX_POSITIONS, CORRELATION_THRESHOLD, MAX_SECTOR_PCT, LOOKBACK_DAYS,
)
from portfolio.correlation_engine import compute as ce_compute
from portfolio.subset_selector import select as ss_select
from portfolio.position_sizer import compute_weights
from portfolio.sector_constraint import apply_sector_cap

log = logging.getLogger(__name__)

_SAFE_SUMMARY = {
    PL_AVAILABLE:             False,
    PL_RECOMMENDED_SUBSET:    [],
    PL_EXCLUDED_CANDIDATES:   [],
    PL_SECTOR_EXPOSURE:       {},
    PL_AVG_CORRELATION:       None,
    PL_DIVERSIFICATION_SCORE: None,
}


def _write_safe_defaults(candidate: dict) -> None:
    """Write safe PL_* defaults to a candidate dict in-place."""
    candidate[PL_CLUSTER_ID]        = None
    candidate[PL_CORRELATION_FLAGS] = []
    candidate[PL_SELECTED]          = False
    candidate[PL_EXCLUSION_REASON]  = 'UNAVAILABLE'
    candidate[PL_POSITION_WEIGHT]   = None
    candidate[PL_AVAILABLE]         = False


def analyze(candidates: list[dict]) -> dict:
    """
    Input:
        candidates: list[dict] — full final_companies list after S1–S4 enrichment

    Output:
        portfolio_summary dict with all PL_* run-level keys

    Side effects:
        Mutates every candidate dict in-place adding:
        PL_CLUSTER_ID, PL_CORRELATION_FLAGS, PL_SELECTED,
        PL_EXCLUSION_REASON, PL_POSITION_WEIGHT, PL_AVAILABLE

    Non-fatal: any exception → PL_AVAILABLE=False everywhere, returns _SAFE_SUMMARY copy.
    """
    if len(candidates) < 2:
        log.info('[PL] analyze() called with fewer than 2 candidates — skipping')
        for c in candidates:
            _write_safe_defaults(c)
        return dict(_SAFE_SUMMARY)

    try:
        # Layer 1: Correlation
        corr_result = ce_compute(candidates, lookback=LOOKBACK_DAYS)

        corr_matrix       = corr_result['correlation_matrix']
        clusters          = corr_result['clusters']
        ticker_to_cluster = corr_result['ticker_to_cluster']
        correlation_flags = corr_result['correlation_flags']
        avg_correlation   = corr_result['avg_correlation']
        unavailable       = corr_result['unavailable']
        returns_data      = corr_result['returns_data']

        if len(returns_data) < 2:
            log.warning('[PL] Fewer than 2 tickers with usable returns — aborting')
            for c in candidates:
                _write_safe_defaults(c)
            return dict(_SAFE_SUMMARY)

        # Layer 2: Subset selection
        selected_tickers, exclusion_reasons = ss_select(
            candidates        = candidates,
            clusters          = clusters,
            ticker_to_cluster = ticker_to_cluster,
            unavailable       = unavailable,
            max_positions     = MAX_POSITIONS,
        )

        # Layer 3: Position sizing
        weights = compute_weights(
            selected_tickers = selected_tickers,
            candidates       = candidates,
            returns_data     = returns_data,
        )

        # Layer 4: Sector cap
        final_weights, sector_cap_excluded = apply_sector_cap(
            weights        = weights,
            candidates     = candidates,
            max_sector_pct = MAX_SECTOR_PCT,
        )
        for t in sector_cap_excluded:
            exclusion_reasons[t] = 'SECTOR_CAP'

        final_selected = list(final_weights.keys())

        # Sector exposure from final weights
        sector_map = {
            c.get('ticker', ''): c.get('sector', 'Unknown')
            for c in candidates if c.get('ticker')
        }
        sector_exposure: dict[str, float] = {}
        for ticker, w in final_weights.items():
            s = sector_map.get(ticker, 'Unknown')
            sector_exposure[s] = round(sector_exposure.get(s, 0.0) + w, 2)

        # Diversification score from selected subset pairwise correlations
        selected_corrs = []
        for i, ta in enumerate(final_selected):
            for tb in final_selected[i + 1:]:
                val = corr_matrix.get(ta, {}).get(tb)
                if val is not None:
                    selected_corrs.append(val)
        subset_avg_corr = round(float(np.mean(selected_corrs)), 4) if selected_corrs else avg_correlation
        diversification = round(1.0 - subset_avg_corr, 4) if subset_avg_corr is not None else None

        recommended_subset = sorted(final_selected, key=lambda t: final_weights.get(t, 0), reverse=True)

        excluded_candidates = [
            {'ticker': t, 'exclusion_reason': r}
            for t, r in exclusion_reasons.items()
        ]

        # Mutate candidates in-place
        for c in candidates:
            ticker = c.get('ticker', '')
            if not ticker:
                continue
            c[PL_CLUSTER_ID]        = ticker_to_cluster.get(ticker)
            c[PL_CORRELATION_FLAGS] = correlation_flags.get(ticker, [])
            c[PL_AVAILABLE]         = True
            if ticker in final_selected:
                c[PL_SELECTED]         = True
                c[PL_EXCLUSION_REASON] = None
                c[PL_POSITION_WEIGHT]  = final_weights.get(ticker)
            else:
                c[PL_SELECTED]         = False
                c[PL_EXCLUSION_REASON] = exclusion_reasons.get(ticker, 'RANK_CUT')
                c[PL_POSITION_WEIGHT]  = None

        summary = {
            PL_AVAILABLE:             True,
            PL_RECOMMENDED_SUBSET:    recommended_subset,
            PL_EXCLUDED_CANDIDATES:   excluded_candidates,
            PL_SECTOR_EXPOSURE:       sector_exposure,
            PL_AVG_CORRELATION:       subset_avg_corr,
            PL_DIVERSIFICATION_SCORE: diversification,
        }

        log.info(
            f'[PL] Analysis complete. Selected: {recommended_subset} | '
            f'Diversification: {diversification} | Sectors: {sector_exposure}'
        )
        return summary

    except Exception as e:
        log.error(f'[PL] portfolio_analyzer.analyze() failed: {e}', exc_info=True)
        for c in candidates:
            _write_safe_defaults(c)
        return dict(_SAFE_SUMMARY)
