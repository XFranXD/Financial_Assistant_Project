"""
eq_analyzer/event_risk.py
Classifies each candidate ticker as NORMAL or HIGH RISK based on proximity
to earnings announcements and hardcoded macro events.
Non-fatal — returns NORMAL on any error or missing data.
"""

import json
import logging
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_MACRO_EVENTS_PATH = Path(__file__).parent.parent / 'data' / 'macro_events.json'


def _load_macro_events() -> dict:
    """Load the hardcoded macro event list from data/macro_events.json."""
    try:
        with open(_MACRO_EVENTS_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f'[ER] Failed to load macro_events.json: {e}')
        return {}


def _check_macro_events(today: datetime) -> tuple[bool, str]:
    """
    Check if today's date falls within 1 calendar day before any listed macro event.
    Returns (is_high_risk, description).
    """
    macro = _load_macro_events()
    today_date = today.date() if hasattr(today, 'date') else today

    all_dates = []
    for d_str in macro.get('fed_meetings', []):
        try:
            all_dates.append(('Fed meeting', datetime.strptime(d_str, '%Y-%m-%d').date()))
        except ValueError:
            continue
    for d_str in macro.get('cpi_releases', []):
        try:
            all_dates.append(('CPI release', datetime.strptime(d_str, '%Y-%m-%d').date()))
        except ValueError:
            continue

    for desc, event_date in all_dates:
        days_until = (event_date - today_date).days
        if 0 <= days_until <= 1:
            return True, f'{desc} in {days_until} day(s)'

    return False, ''


def get_event_risk(ticker: str, finnhub_token: str) -> dict:
    """
    Classifies a ticker as NORMAL or HIGH RISK based on:
    1. Proximity to earnings (Finnhub calendar, 1-5 days inclusive)
    2. Proximity to macro events (Fed meetings, CPI releases, 0-1 days)

    Returns:
        {
            'event_risk':        'NORMAL' | 'HIGH RISK',
            'event_risk_reason': str,
            'days_to_earnings':  int | None,
        }
    """
    default = {
        'event_risk': 'NORMAL',
        'event_risk_reason': '',
        'days_to_earnings': None,
    }

    try:
        today = datetime.now(timezone.utc)
        today_date = today.date()

        # ── Earnings check (primary) ──────────────────────────────────────
        earnings_risk = False
        earnings_reason = ''
        days_to_earnings = None

        if finnhub_token:
            try:
                from_date = today_date.strftime('%Y-%m-%d')
                to_date = (today_date + timedelta(days=7)).strftime('%Y-%m-%d')
                url = (
                    f'https://finnhub.io/api/v1/calendar/earnings'
                    f'?from={from_date}&to={to_date}'
                    f'&symbol={ticker}&token={finnhub_token}'
                )
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                calendar = data.get('earningsCalendar', [])
                for entry in calendar:
                    date_str = entry.get('date', '')
                    if not date_str:
                        continue
                    try:
                        earn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        diff = (earn_date - today_date).days
                        if 1 <= diff <= 5:
                            earnings_risk = True
                            days_to_earnings = diff
                            earnings_reason = f'Earnings in {diff} day(s)'
                            break  # take the nearest
                    except ValueError:
                        continue
            except Exception as e:
                logger.info(f'[ER] {ticker}: Finnhub earnings check failed — {e}')

        # ── Macro check (secondary / additive) ───────────────────────────
        macro_risk, macro_desc = _check_macro_events(today)

        # ── Combine results ──────────────────────────────────────────────
        if earnings_risk and macro_risk:
            return {
                'event_risk': 'HIGH RISK',
                'event_risk_reason': f'{earnings_reason} / {macro_desc}',
                'days_to_earnings': days_to_earnings,
            }
        elif earnings_risk:
            return {
                'event_risk': 'HIGH RISK',
                'event_risk_reason': earnings_reason,
                'days_to_earnings': days_to_earnings,
            }
        elif macro_risk:
            return {
                'event_risk': 'HIGH RISK',
                'event_risk_reason': macro_desc,
                'days_to_earnings': None,
            }
        else:
            return default

    except Exception as e:
        logger.warning(f'[ER] {ticker}: event risk check failed — {e}')
        return default
