"""
analyzers/news_impact_scorer.py — Second gate after keyword scoring.
Events/sectors below 0.6 impact threshold are dropped.

Formula: impact = (source_count*0.4) + (keyword_weight*0.3) + (spy_move*0.3)
"""

import yfinance as yf
from utils.logger import get_logger
from utils.retry import retry_on_failure

log = get_logger('news_impact_scorer')

IMPACT_THRESHOLD = 0.6


@retry_on_failure(max_attempts=2, delay=2.0)
def _get_spy_move() -> float:
    """Returns SPY day % change. Returns 0.0 on failure."""
    try:
        d = yf.Ticker('SPY').history(period='2d')
        if d is None or len(d) < 2:
            return 0.0
        prev = float(d['Close'].iloc[-2])
        curr = float(d['Close'].iloc[-1])
        return abs(((curr - prev) / prev) * 100) if prev != 0 else 0.0
    except Exception as e:
        log.warning(f'SPY move fetch error: {e}')
        return 0.0


def score_sector_impact(
    sector: str,
    source_count: int,
    keyword_weight: float,
    spy_move_pct: float | None = None,
) -> dict:
    """
    Computes impact score for a sector signal.

    Args:
        sector:         sector name string
        source_count:   number of distinct news sources mentioning this sector
        keyword_weight: total accumulated keyword score (normalised 0-1 input expected)
        spy_move_pct:   SPY % move today (fetched once and reused)

    Returns:
        {'impact': float, 'passes_gate': bool, 'reason': str}
    """
    # Normalise inputs to 0-1 range
    norm_sources  = min(1.0, source_count / 3.0)   # 3 sources = max
    norm_keywords = min(1.0, keyword_weight / 20.0) # 20 pts = max keyword weight
    spy_contrib   = min(1.0, (spy_move_pct or 0.0) / 2.0)  # 2% move = normalised 1.0

    impact = (norm_sources * 0.4) + (norm_keywords * 0.3) + (spy_contrib * 0.3)
    impact = round(impact, 3)

    passes = impact >= IMPACT_THRESHOLD
    reason = (
        f'sources={source_count} kw={keyword_weight:.1f} spy={spy_move_pct or 0:.2f}% '
        f'→ impact={impact:.3f} {"✓ passes" if passes else "✗ below threshold"}'
    )
    log.info(f'Impact [{sector}]: {reason}')

    return {
        'impact':       impact,
        'passes_gate':  passes,
        'reason':       reason,
    }


def filter_sectors_by_impact(candidate_sectors: dict) -> dict:
    """
    Filters confirmed sectors by news impact gate.
    candidate_sectors: {sector: {'score': float, 'count': int, 'events': list}}
    Returns only sectors that pass the 0.6 threshold.
    """
    spy_move = _get_spy_move()
    if spy_move is None:
        spy_move = 0.0
    log.info(f'SPY day move: {spy_move:.2f}%')

    filtered = {}
    for sector, data in candidate_sectors.items():
        result = score_sector_impact(
            sector        = sector,
            source_count  = data.get('count', 1),
            keyword_weight= data.get('score', 0.0),
            spy_move_pct  = spy_move,
        )
        if result['passes_gate']:
            filtered[sector] = {**data, 'impact_score': result['impact']}
        else:
            log.info(f'Sector dropped by impact gate: {sector} ({result["reason"]})')

    log.info(f'Impact gate: {len(candidate_sectors)} → {len(filtered)} sectors passed')
    return filtered
