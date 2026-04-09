"""
portfolio/sector_constraint.py
Layer 4: 40% max per sector cap with iterative renormalization.
Includes fallback mathematical weight capping.
"""

import logging
from contracts.portfolio_schema import MAX_SECTOR_PCT

log = logging.getLogger(__name__)


def apply_sector_cap(
    weights:        dict[str, float],
    candidates:     list[dict],
    max_sector_pct: float = MAX_SECTOR_PCT,
) -> tuple[dict[str, float], list[str]]:
    """
    Input:
        weights:        dict[str, float] — from position_sizer, sum == 100.0
        candidates:     list[dict] with 'ticker', 'sector', 'composite_confidence'
        max_sector_pct: float — cap threshold

    Output:
        final_weights       — dict[str, float] renormalized after enforcement
        sector_cap_excluded — list[str] tickers removed by this layer
    """
    conf_map: dict[str, float] = {
        c.get('ticker', ''): float(c.get('composite_confidence', 0))
        for c in candidates if c.get('ticker')
    }
    sector_map: dict[str, str] = {
        c.get('ticker', ''): c.get('sector', 'Unknown')
        for c in candidates if c.get('ticker')
    }

    current = dict(weights)
    sector_cap_excluded: list[str] = []

    # Iterative removal of weakest tickers in violating sectors with >1 ticker
    for _ in range(len(current) + 1):
        if not current:
            break

        sector_exposure: dict[str, float] = {}
        for ticker, w in current.items():
            s = sector_map.get(ticker, 'Unknown')
            sector_exposure[s] = sector_exposure.get(s, 0.0) + w

        violating = next(
            (s for s, pct in sector_exposure.items() if pct > max_sector_pct),
            None,
        )
        if violating is None:
            break

        sector_tickers = [t for t in current if sector_map.get(t, 'Unknown') == violating]
        
        # Mathematical impossibility check: if a sector with 1 ticker exceeds the cap,
        # dropping it could wipe out the portfolio and doesn't make sense logically.
        # We handle this in the mathematical cap fallback below.
        if len(sector_tickers) <= 1:
            break

        weakest = min(sector_tickers, key=lambda t: conf_map.get(t, 0))
        log.info(
            f'[PL] {weakest} excluded — SECTOR_CAP '
            f'(sector={violating}, exposure={sector_exposure[violating]:.1f}%)'
        )
        del current[weakest]
        sector_cap_excluded.append(weakest)

        total = sum(current.values())
        if total > 0:
            current = {t: round((w / total) * 100, 2) for t, w in current.items()}
            diff = round(100.0 - sum(current.values()), 2)
            if diff != 0 and current:
                largest = max(current, key=lambda t: current[t])
                current[largest] = round(current[largest] + diff, 2)

    # Mathematical capping fallback for any sectors STILL violating 
    for _ in range(10):
        sector_exposure = {}
        for ticker, w in current.items():
            s = sector_map.get(ticker, 'Unknown')
            sector_exposure[s] = sector_exposure.get(s, 0.0) + w
            
        violating = next((s for s, pct in sector_exposure.items() if pct > max_sector_pct), None)
        if violating is None:
            break
            
        locked_tickers = set()
        for t, w in current.items():
            s = sector_map.get(t, 'Unknown')
            if sector_exposure.get(s, 0.0) > max_sector_pct:
                current[t] = max_sector_pct  # Assuming 1 ticker left per violating sector due to above loop
                locked_tickers.add(t)
                
        locked_weight = sum(current[t] for t in locked_tickers)
        remaining_weight = max(0.0, 100.0 - locked_weight)
        
        unlocked = [t for t in current if t not in locked_tickers]
        if not unlocked:
            break
            
        unlocked_total = sum(current[t] for t in unlocked)
        if unlocked_total > 0:
            for t in unlocked:
                current[t] = round((current[t] / unlocked_total) * remaining_weight, 2)
                
        diff = round(100.0 - sum(current.values()), 2)
        if diff != 0 and unlocked:
            largest = max(unlocked, key=lambda t: current[t])
            current[largest] = round(current[largest] + diff, 2)

    return current, sector_cap_excluded
