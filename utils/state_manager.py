"""
utils/state_manager.py — Atomic state read/write. Never corrupts daily_state.json.
Atomic write: write to .tmp file then shutil.move to final path.
"""

import json
import os
import shutil
from datetime import datetime

import pytz

from utils.logger import get_logger

log = get_logger('state_manager')

STATE_FILE = 'state/daily_state.json'
STATE_TMP  = 'state/daily_state.json.tmp'

DEFAULT_STATE: dict = {
    'date':                     '',
    'reported_companies':       [],
    'alpha_vantage_calls_today': 0,
    'runs': {
        '10:30': {'companies': [], 'status': 'pending'},
        '12:30': {'companies': [], 'status': 'pending'},
        '14:30': {'companies': [], 'status': 'pending'},
        '16:10': {'companies': [], 'status': 'pending'},
    },
    'failed_tickers':           [],
    'api_failures':             {},
    'sector_scores_today':      {},
    'breadth_score_today':      None,
    'sector_breadth_ma_today':  {},
    'unusual_volume_flags':     [],
    'event_scores_today':       {},
    'indices_today':            {},
}


def load_state() -> dict:
    """
    Loads state from STATE_FILE. Returns DEFAULT_STATE copy if file is
    missing or corrupted. Resets to fresh state if date differs from today UTC.
    """
    today = datetime.now(pytz.utc).strftime('%Y-%m-%d')

    if not os.path.exists(STATE_FILE):
        log.warning('State file missing — starting fresh state')
        state = _fresh_state(today)
        save_state(state)
        return state

    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f'State file corrupt ({e}) — starting fresh state')
        state = _fresh_state(today)
        save_state(state)
        return state

    # If it's a new day, reset to fresh state (preserves no cross-day contamination)
    if state.get('date') != today:
        log.info(f'New trading day ({today}) — resetting state')
        state = _fresh_state(today)
        save_state(state)

    return state


def save_state(state: dict) -> None:
    """
    ATOMIC write: serialises to .tmp then renames.
    A crash mid-write will never leave a partial/corrupt state file.
    """
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    try:
        with open(STATE_TMP, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
        shutil.move(STATE_TMP, STATE_FILE)
        log.debug('State saved atomically')
    except OSError as e:
        log.error(f'CRITICAL: could not save state ({e})')


def _fresh_state(today: str) -> dict:
    """Returns a deep-copy of DEFAULT_STATE with today's date populated."""
    import copy
    state = copy.deepcopy(DEFAULT_STATE)
    state['date'] = today
    return state


def mark_slot_complete(state: dict, slot: str) -> dict:
    """Mark a run slot as completed."""
    if slot in state.get('runs', {}):
        state['runs'][slot]['status'] = 'complete'
        log.info(f'Slot {slot} marked complete')
    return state


def add_reported_companies(state: dict, tickers: list[str]) -> dict:
    """Add tickers to the reported_companies dedup list."""
    existing = set(state.get('reported_companies', []))
    new_ones  = [t for t in tickers if t not in existing]
    state['reported_companies'] = list(existing | set(tickers))
    if new_ones:
        log.info(f'Added to reported: {new_ones}')
    return state


def increment_av_calls(state: dict, n: int = 1) -> dict:
    """Increment Alpha Vantage call counter and save immediately."""
    state['alpha_vantage_calls_today'] = state.get('alpha_vantage_calls_today', 0) + n
    log.info(f"AV calls today: {state['alpha_vantage_calls_today']}")
    return state
