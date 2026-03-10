"""
analyzers/sector_mapper.py — Maps detected events to affected sectors
with direction (positive/negative) and confidence weighting.
"""

import json
from config import EVENT_TO_SECTOR_FILE
from utils.logger import get_logger

log = get_logger('sector_mapper')


def _load_e2s() -> dict:
    try:
        with open(EVENT_TO_SECTOR_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log.error(f'Cannot load event_to_sector.json: {e}')
        return {}


def map_events_to_sectors(detected_events: list[str]) -> dict[str, dict]:
    """
    Given a list of detected event type strings, returns a combined
    sector impact map: {sector: {'direction': str, 'confidence': float, 'events': list}}

    When multiple events affect the same sector, confidences are averaged
    and directions are resolved (positive wins over conflicting negative).
    """
    e2s     = _load_e2s()
    impacts: dict[str, dict] = {}

    for event_type in detected_events:
        sector_data = e2s.get(event_type, {}).get('sectors', {})
        for sector, cfg in sector_data.items():
            direction  = cfg.get('direction', 'positive')
            confidence = cfg.get('confidence', 0.5)

            if sector not in impacts:
                impacts[sector] = {
                    'direction':   direction,
                    'confidence':  confidence,
                    'events':      [event_type],
                    '_conf_sum':   confidence,
                    '_count':      1,
                }
            else:
                impacts[sector]['_conf_sum'] += confidence
                impacts[sector]['_count']    += 1
                impacts[sector]['events'].append(event_type)
                # Average confidence across all events
                impacts[sector]['confidence'] = round(
                    impacts[sector]['_conf_sum'] / impacts[sector]['_count'], 3
                )
                # Direction resolution: positive wins tie-breaks
                if direction == 'positive':
                    impacts[sector]['direction'] = 'positive'

    # Clean up internal tracking keys
    for sector in impacts:
        impacts[sector].pop('_conf_sum', None)
        impacts[sector].pop('_count',    None)

    log.info(f'Mapped {len(detected_events)} events → {len(impacts)} sectors')
    return impacts


def get_sector_direction(sector: str, event_type: str) -> str:
    """Convenience: returns direction for a specific event→sector pair."""
    e2s = _load_e2s()
    return e2s.get(event_type, {}).get('sectors', {}).get(sector, {}).get('direction', 'positive')
