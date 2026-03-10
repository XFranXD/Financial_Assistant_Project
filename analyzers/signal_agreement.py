"""
analyzers/signal_agreement.py — §18 NEW
Multiplicative confidence model: all signals must align for a high score.
A single weak signal pulls the overall score down significantly.

Formula: raw = momentum * sector_strength * event_score * volume_score
"""

from utils.logger import get_logger

log = get_logger('signal_agreement')


def compute_signal_agreement(
    momentum_score:  float,
    sector_strength: float,
    event_score:     float,
    volume_score:    float,
) -> dict:
    """
    All inputs must be in range 0.0-1.0.
    Missing inputs default to 0.5 (neutral) — never block the calculation.
    Returns agreement_score 0.0-1.0 and a plain English confidence label.

    NOTE: The multiplicative formula compresses scores significantly.
    With all inputs at 0.8: 0.8^4 = 0.41.
    Treat scores above 0.35 as strong agreement for this system.
    """
    m = max(0.0, min(1.0, momentum_score  or 0.5))
    s = max(0.0, min(1.0, sector_strength or 0.5))
    e = max(0.0, min(1.0, event_score     or 0.5))
    v = max(0.0, min(1.0, volume_score    or 0.5))

    score = m * s * e * v  # multiplicative combination — already 0-1

    if score > 0.35:   label = 'strong agreement across all signals'
    elif score > 0.20: label = 'moderate agreement — most signals aligned'
    elif score > 0.08: label = 'partial agreement — some signals conflicting'
    else:              label = 'weak agreement — signals not aligned'

    log.info(f'Signal agreement: m={m:.2f} s={s:.2f} e={e:.2f} v={v:.2f} -> {score:.3f}')
    return {
        'agreement_score': round(score, 3),
        'label':           label,
        'inputs':          {'momentum': m, 'sector': s, 'event': e, 'volume': v},
    }


def sector_rank_to_score(rank: int, total_sectors: int = 13) -> float:
    """Convert sector rank (1=best) to 0-1 score for signal_agreement input."""
    return max(0.0, (total_sectors - rank) / (total_sectors - 1))
