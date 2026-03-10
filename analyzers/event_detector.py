"""
analyzers/event_detector.py — Detects event types from news articles and
applies exponential recency decay before passing to news_impact_scorer.
"""

import json
from datetime import datetime, timezone

import pytz

from config import EVENT_TO_SECTOR_FILE, EVENT_KEYWORDS_FILE
from analyzers.event_decay import decay_event_cluster, apply_event_decay
from utils.logger import get_logger

log = get_logger('event_detector')


def _load_json(path: str) -> dict:
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log.error(f'Cannot load {path}: {e}')
        return {}


def _days_since(pub_dt) -> int:
    """Compute integer days between article publish time and now UTC."""
    if pub_dt is None:
        return 0
    try:
        now = datetime.now(pytz.utc)
        pub = pub_dt if pub_dt.tzinfo else pub_dt.replace(tzinfo=timezone.utc)
        return max(0, (now - pub).days)
    except Exception:
        return 0


def detect_events(articles: list[dict]) -> dict[str, list[dict]]:
    """
    Scans each article for event type matches. Groups matching events by type.
    Applies recency decay based on article publish timestamp.

    Returns:
        {event_type: [{'score': float, 'adjusted_score': float, 'days_old': int, ...}]}
    """
    keywords    = _load_json(EVENT_KEYWORDS_FILE)
    e2s         = _load_json(EVENT_TO_SECTOR_FILE)
    event_map: dict[str, list[dict]] = {}

    for article in articles:
        text      = article.get('text', '').lower()
        title     = article.get('title', '')
        pub_dt    = article.get('published')
        days_old  = _days_since(pub_dt)

        # Compute raw keyword score for this article
        raw_score = 0.0
        for tier_data in keywords.values():
            weight = tier_data.get('weight', 1)
            for term in tier_data.get('terms', []):
                if term.lower() in text:
                    raw_score += weight

        if raw_score == 0:
            continue

        # Check which event types match
        for event_type in e2s:
            event_phrase = event_type.replace('_', ' ')
            if event_phrase in text:
                if event_type not in event_map:
                    event_map[event_type] = []
                event_map[event_type].append({
                    'title':    title,
                    'score':    raw_score,
                    'days_old': days_old,
                    'pub_dt':   str(pub_dt),
                })

    # Apply recency decay to each event cluster
    for event_type, events in event_map.items():
        event_map[event_type] = decay_event_cluster(events)
        log.info(
            f'Event "{event_type}": {len(events)} occurrences, '
            f'max adjusted score = {max(e["adjusted_score"] for e in events):.2f}'
        )

    return event_map


def summarise_sector_events(event_map: dict, event_to_sector: dict) -> dict:
    """
    Aggregates adjusted event scores per sector.
    Returns {sector: {'total_adjusted': float, 'events': list, 'direction': str}}
    Used as input to news_impact_scorer.
    """
    sector_summary: dict[str, dict] = {}

    for event_type, events in event_map.items():
        sector_cfg = event_to_sector.get(event_type, {}).get('sectors', {})
        total_adj  = sum(e.get('adjusted_score', 0) for e in events)

        for sector, cfg in sector_cfg.items():
            confidence = cfg.get('confidence', 0.5)
            direction  = cfg.get('direction', 'positive')
            contrib    = total_adj * confidence

            if sector not in sector_summary:
                sector_summary[sector] = {
                    'total_adjusted': 0.0,
                    'direction':      direction,
                    'events':         [],
                }
            sector_summary[sector]['total_adjusted'] += contrib
            sector_summary[sector]['events'].append({
                'event_type': event_type,
                'contribution': round(contrib, 2),
                'direction':    direction,
            })

    return sector_summary
