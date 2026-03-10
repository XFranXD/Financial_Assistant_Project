"""
analyzers/sector_rotation_speed.py — §15 NEW
Measures rate of change in sector momentum ranking. Accelerating sectors
may signal institutional money rotating in.

Formula: rotation_speed = past_rank - curr_rank
  Positive → sector moved up in ranking (gaining)
  Negative → sector moved down (losing)
"""

import json
from utils.logger import get_logger
from config import SECTOR_MOMENTUM_HISTORY_FILE

log = get_logger('sector_rotation_speed')


def compute_rotation_speed(current_scores: dict) -> dict:
    """
    current_scores: dict from sector_momentum.py — {sector: {'score': float, 'rank': int}}
    Compares to entry from 7 days ago in history file.
    Returns {sector: {'rotation_speed': float, 'label': str, 'accelerating': bool}}
    """
    try:
        with open(SECTOR_MOMENTUM_HISTORY_FILE) as f:
            history = json.load(f)
    except Exception as e:
        log.warning(f'Rotation speed: cannot load history ({e})')
        return {}

    entries = history.get('history', [])
    if len(entries) < 2:
        log.info('Rotation speed: not enough history yet — skipping')
        return {}

    target_entry  = entries[-min(7, len(entries))]
    past_rankings = target_entry.get('rankings', {})

    results = {}
    for sector, data in current_scores.items():
        curr_rank = data.get('rank', 99)
        past_rank = past_rankings.get(sector, 99)
        speed     = past_rank - curr_rank   # negative rank change = moved up = positive speed

        if speed > 3:      label = 'rapidly gaining strength'
        elif speed > 1:    label = 'gaining momentum'
        elif speed >= -1:  label = 'stable'
        elif speed >= -3:  label = 'losing momentum'
        else:              label = 'rapidly losing strength'

        results[sector] = {
            'rotation_speed': speed,
            'label':          label,
            'accelerating':   speed > 2,
        }
        log.info(f'Rotation {sector}: rank {past_rank} -> {curr_rank} speed={speed} ({label})')
    return results
