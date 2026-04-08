"""
eq_analyzer/event_risk.py
Classifies each candidate ticker as NORMAL or HIGH RISK based on proximity
to earnings announcements and hardcoded macro events.

Supersedes earnings_warning bool for display purposes only.
Does NOT remove risk_model.py's score penalty — that stays untouched.

Non-fatal — returns NORMAL on any error or missing data.
"""

import json
import logging
import requests
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_MACRO_EVENTS_PATH = Path(__file__).parent.parent / 'data' / 'macro_events.json'
_MACRO_EVENTS_CACHE: dict | None = None


def _load_macro_events() -> dict:
    global _MACRO_EVENTS_CACHE
    if _MACRO_EVENTS_CACHE is not None:
        return _MACRO_EVENTS_CACHE
    try:
        with open(_MACRO_EVENTS_PATH, encoding='utf-8') as f:
            _MACRO_EVENTS_CACHE = json.load(f)
    except Exception as e:
        log.warning(f'[ER] Failed to load macro_events.json: {e}')
        _MACRO_EVENTS_CACHE = {}
    return _MACRO_EVENTS_CACHE


def _check_macro_event(today: datetime.date) -> tuple[bool, str]:
    """
    Check if today falls within 1 calendar day before a macro event.
    Returns (triggered: bool, description: str).
    """
    events = _load_macro_events()
    fed_dates = events.get('fed_meetings', [])
    cpi_dates = events.get('cpi_releases', [])

    for date_str in fed_dates:
        try:
            event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            days_away = (event_date - today).days
            if 0 <= days_away <= 1:
                return True, f'Fed meeting in {days_away} day(s)'
        except ValueError:
            continue

    for date_str in cpi_dates:
        try:
            event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            days_away = (event_date - today).days
            if 0 <= days_away <= 1:
                return True, f'CPI release in {days_away} day(s)'
        except ValueError:
            continue

    return False, ''


def get_event_risk(ticker: str, finnhub_token: str) -> dict:
    """
    Classifies a ticker as NORMAL or HIGH RISK based on:
      1. Earnings proximity (1–5 calendar days, checked via Finnhub)
      2. Macro events (Fed meetings / CPI releases from macro_events.json)

    Returns:
        {
            'event_risk':        'NORMAL' | 'HIGH RISK',
            'event_risk_reason': str,
            'days_to_earnings':  int | None,
        }

    On any exception: returns NORMAL, logs error, does not raise.
    """
    _default = {
        'event_risk':        'NORMAL',
        'event_risk_reason': '',
        'days_to_earnings':  None,
    }

    try:
        today = datetime.now(timezone.utc).date()
        end   = today + timedelta(days=7)

        # ── Earnings check via Finnhub ────────────────────────────────────
        earnings_triggered = False
        earnings_reason    = ''
        days_to_earnings   = None

        if finnhub_token:
            try:
                url = (
                    f'https://finnhub.io/api/v1/calendar/earnings'
                    f'?from={today.isoformat()}'
                    f'&to={end.isoformat()}'
                    f'&symbol={ticker}'
                    f'&token={finnhub_token}'
                )
                resp = requests.get(url, timeout=10)
                if resp.ok:
                    data = resp.json()
                    calendar = data.get('earningsCalendar', [])
                    for entry in calendar:
                        date_str = entry.get('date', '')
                        if not date_str:
                            continue
                        try:
                            event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                            days_away  = (event_date - today).days
                            if 1 <= days_away <= 5:
                                if days_to_earnings is None or days_away < days_to_earnings:
                                    days_to_earnings   = days_away
                                    earnings_triggered = True
                                    earnings_reason    = f'Earnings in {days_away} day(s)'
                        except ValueError:
                            continue
                else:
                    log.info(f'[ER] {ticker}: Finnhub returned HTTP {resp.status_code}')
            except Exception as finnhub_err:
                log.info(f'[ER] {ticker}: Finnhub request failed — {finnhub_err}')
        else:
            log.info(f'[ER] {ticker}: no Finnhub token — skipping earnings check')

        # ── Macro event check ─────────────────────────────────────────────
        macro_triggered, macro_desc = _check_macro_event(today)

        # ── Combine results ───────────────────────────────────────────────
        if earnings_triggered and macro_triggered:
            return {
                'event_risk':        'HIGH RISK',
                'event_risk_reason': f'{earnings_reason} / {macro_desc}',
                'days_to_earnings':  days_to_earnings,
            }
        elif earnings_triggered:
            return {
                'event_risk':        'HIGH RISK',
                'event_risk_reason': earnings_reason,
                'days_to_earnings':  days_to_earnings,
            }
        elif macro_triggered:
            return {
                'event_risk':        'HIGH RISK',
                'event_risk_reason': macro_desc,
                'days_to_earnings':  None,
            }
        else:
            return {
                'event_risk':        'NORMAL',
                'event_risk_reason': '',
                'days_to_earnings':  None,
            }

    except Exception as e:
        log.warning(f'[ER] {ticker}: unexpected error in get_event_risk — {e}')
        return _default