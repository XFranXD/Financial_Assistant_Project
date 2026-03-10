"""
analyzers/event_decay.py — §14 NEW
Exponential recency decay for news events. Older events carry less weight.

Formula: adjusted_score = original_score * exp(-days_since_event / 10)
"""

import math
from utils.logger import get_logger

log = get_logger('event_decay')
DECAY_FACTOR = 10   # controls fade speed — do not change


def apply_event_decay(original_score: float, days_since_event: int) -> float:
    if days_since_event < 0:
        log.warning(f'Negative days_since_event={days_since_event} — treating as 0')
        days_since_event = 0
    adjusted = original_score * math.exp(-days_since_event / DECAY_FACTOR)
    log.info(f'Event decay: {original_score:.2f} -> {adjusted:.2f} ({days_since_event}d old)')
    return round(adjusted, 3)


def decay_event_cluster(events: list[dict]) -> list[dict]:
    """
    Each dict must have: 'score' (float) and 'days_old' (int).
    Returns updated list with 'adjusted_score' added to each event.
    """
    for event in events:
        event['adjusted_score'] = apply_event_decay(
            event.get('score', 0),
            event.get('days_old', 0)
        )
    return events
