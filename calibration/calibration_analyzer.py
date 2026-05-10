"""
calibration/calibration_analyzer.py
Phase 4 Calibration Analyzer — standalone script.

Reads closed trade history from Google Sheets.
Runs bucket analysis per metric.
Flags underperforming buckets only when significance criteria are fully met.
Generates human-readable recommendation report.
Writes summary to calibration_reports Sheets tab (auto-created if missing).
Never modifies financial_standards.py. Never raises.

Run: python3 -m calibration.calibration_analyzer

Field name note: analyzer uses "composite_score" (Sheets column name).
Not "composite_confidence" (candidate dict name at scoring time).
"""

import os
from datetime import datetime, date
from collections import defaultdict
import pytz

from calibration.financial_standards import STANDARDS_VERSION
from calibration.calibration_config import (
    BUCKET_MIN_SAMPLE,
    SIGNIFICANCE_EXPECTANCY_DELTA,
    SIGNIFICANCE_WINRATE_DELTA,
    CYCLE_MIN_NEW_TRADES,
    CYCLE_MIN_OBSERVATION_DAYS,
    EXPLORATORY_ANALYSIS_MIN,
    RECOMMENDATION_MIN,
    PREFERRED_CALIBRATION_MIN,
    CHOKE_DROP_THRESHOLD,
    SHEET_TAB_STANDARDS_HISTORY,
    SHEET_TAB_CALIBRATION_REPORTS,
    STANDARDS_HISTORY_HEADERS,
    CALIBRATION_REPORTS_HEADERS,
)
from utils.logger import get_logger
log = get_logger('calibration_analyzer')


# ── Sheets tab access (with auto-create) ─────────────────────────────────────

def _get_or_create_tab(spreadsheet, tab_name, headers):
    """Get worksheet by name, auto-creating with headers if missing. Returns ws or None."""
    try:
        return spreadsheet.worksheet(tab_name)
    except Exception:
        pass
    try:
        ws = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=len(headers) + 2)
        ws.append_row(headers, value_input_option='RAW')
        log.info(f'[ANALYZER] Auto-created tab: {tab_name}')
        return ws
    except Exception as e:
        log.error(f'[ANALYZER] Failed to create tab {tab_name}: {e}')
        return None


def _get_spreadsheet():
    try:
        from paper_trading.sheets_ledger import _get_sheet
        sheet = _get_sheet()
        if sheet is None:
            return None
        return sheet.spreadsheet
    except Exception as e:
        log.error(f'[ANALYZER] Cannot access spreadsheet: {e}')
        return None


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_closed_trades():
    try:
        from paper_trading.sheets_ledger import read_all_trades
        all_trades = read_all_trades()
        closed = [t for t in all_trades if t.get('status') == 'CLOSED']
        log.info(f'[ANALYZER] {len(closed)} closed trades loaded.')
        return closed
    except Exception as e:
        log.error(f'[ANALYZER] Failed to load trades: {e}')
        return []


def _load_cycle_history(spreadsheet):
    try:
        ws = _get_or_create_tab(spreadsheet, SHEET_TAB_CALIBRATION_REPORTS, CALIBRATION_REPORTS_HEADERS)
        if ws is None:
            return []
        return ws.get_all_records()
    except Exception as e:
        log.warning(f'[ANALYZER] Could not load cycle history: {e}')
        return []


# ── Cycle validity ────────────────────────────────────────────────────────────

def _check_cycle_validity(closed_trades, cycle_history):
    if not cycle_history:
        return {
            'valid': True,
            'reason': 'No prior cycles — first cycle always valid.',
            'new_trades_since_last': len(closed_trades),
            'days_since_last': None,
        }

    last = max(cycle_history, key=lambda r: r.get('report_timestamp', ''))
    last_date_str = str(last.get('report_timestamp', ''))[:10]

    try:
        days_since = (
            datetime.now(pytz.timezone('America/New_York')).date()
            - date.fromisoformat(last_date_str)
        ).days
    except Exception:
        days_since = None

    new_count = len([t for t in closed_trades if t.get('exit_date', '') > last_date_str])
    reasons = []
    valid = True

    if new_count < CYCLE_MIN_NEW_TRADES:
        valid = False
        reasons.append(f'Only {new_count} new closed trades (min {CYCLE_MIN_NEW_TRADES}).')
    if days_since is not None and days_since < CYCLE_MIN_OBSERVATION_DAYS:
        valid = False
        reasons.append(f'Only {days_since} days since last cycle (min {CYCLE_MIN_OBSERVATION_DAYS}).')

    return {
        'valid': valid,
        'reason': ' | '.join(reasons) if reasons else 'Cycle conditions met.',
        'new_trades_since_last': new_count,
        'days_since_last': days_since,
    }


# ── Statistics ────────────────────────────────────────────────────────────────

def _sf(val, default=None):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _expectancy(trades):
    pnls = [_sf(t.get('live_pnl_pct')) for t in trades]
    pnls = [p for p in pnls if p is not None]
    if not pnls:
        return None
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    wr = len(wins) / len(pnls)
    lr = len(losses) / len(pnls)
    return round(
        (wr * (sum(wins) / len(wins) if wins else 0))
        - (lr * (abs(sum(losses) / len(losses)) if losses else 0)),
        4
    )


def _win_rate(trades):
    pnls = [_sf(t.get('live_pnl_pct')) for t in trades]
    pnls = [p for p in pnls if p is not None]
    if not pnls:
        return None
    return round(len([p for p in pnls if p > 0]) / len(pnls) * 100, 1)


# ── Bucket analysis ───────────────────────────────────────────────────────────

# Field names are Sheets column names (trade record keys after read_all_trades()).
# "composite_score" is correct here — NOT "composite_confidence".
NUMERIC_BUCKETS = {
    'composite_score': [
        (0,   45,  '0-45'),
        (45,  55,  '45-55'),
        (55,  65,  '55-65'),
        (65,  75,  '65-75'),
        (75,  100, '75-100'),
    ],
    'risk_reward_ratio': [
        (0.0, 1.5, '0-1.5'),
        (1.5, 2.0, '1.5-2.0'),
        (2.0, 2.5, '2.0-2.5'),
        (2.5, 3.5, '2.5-3.5'),
        (3.5, 999, '3.5+'),
    ],
    'move_extension_pct': [
        (0,  15,  '0-15%'),
        (15, 30,  '15-30%'),
        (30, 50,  '30-50%'),
        (50, 999, '50%+'),
    ],
}
CATEGORICAL_METRICS = ['entry_quality', 'sector']


def _bucket_numeric(trades, field, buckets):
    return [
        {
            'label':      label,
            'count':      len(bt := [
                t for t in trades
                if _sf(t.get(field)) is not None
                and lo <= _sf(t.get(field)) < hi
            ]),
            'win_rate':   _win_rate(bt),
            'expectancy': _expectancy(bt),
        }
        for lo, hi, label in buckets
    ]


def _bucket_categorical(trades, field):
    groups = defaultdict(list)
    for t in trades:
        groups[t.get(field) or 'UNKNOWN'].append(t)
    return [
        {
            'label':      k,
            'count':      len(v),
            'win_rate':   _win_rate(v),
            'expectancy': _expectancy(v),
        }
        for k, v in sorted(groups.items())
    ]


def _flag(buckets, overall_exp, overall_wr, can_recommend):
    out = []
    for b in buckets:
        if b['count'] < BUCKET_MIN_SAMPLE:
            b['flag'] = 'INSUFFICIENT_SAMPLE'
            b['rec'] = None
        elif (
            (overall_exp is not None and b['expectancy'] is not None
             and (overall_exp - b['expectancy']) >= SIGNIFICANCE_EXPECTANCY_DELTA)
            or
            (overall_wr is not None and b['win_rate'] is not None
             and (overall_wr - b['win_rate']) >= SIGNIFICANCE_WINRATE_DELTA)
        ):
            b['flag'] = 'UNDERPERFORMING'
            b['rec'] = (
                f"Consider restricting. WR {b['win_rate']}% vs overall {overall_wr}%. "
                f"Exp {b['expectancy']} vs overall {overall_exp}."
                if can_recommend else
                "Noted — no recommendations until 50+ trades."
            )
        else:
            b['flag'] = 'OK'
            b['rec'] = None
        out.append(b)
    return out


# ── Choke detection ───────────────────────────────────────────────────────────

def _choke(closed_trades, cycle_history):
    if not cycle_history:
        return {'choke_warning': False, 'reason': 'No prior cycle.'}
    last = max(cycle_history, key=lambda r: r.get('report_timestamp', ''))
    last_date = str(last.get('report_timestamp', ''))[:10]
    last_n = _sf(last.get('total_closed_trades'), 0)
    this_trades = [t for t in closed_trades if t.get('exit_date', '') > last_date]
    this_n = float(len(this_trades))
    if last_n == 0:
        return {'choke_warning': False, 'reason': 'Last cycle had 0 trades.'}
    drop = (last_n - this_n) / last_n
    if drop > CHOKE_DROP_THRESHOLD:
        last_exp = _sf(last.get('overall_expectancy'))
        this_exp = _expectancy(this_trades)
        if not (last_exp is not None and this_exp is not None and this_exp > last_exp):
            return {
                'choke_warning': True,
                'reason': (
                    f'Trade count dropped {drop*100:.0f}% vs prior cycle '
                    f'({int(this_n)} vs {int(last_n)}) without expectancy improvement.'
                ),
            }
    return {'choke_warning': False, 'reason': 'Trade frequency acceptable.'}


# ── Report ────────────────────────────────────────────────────────────────────

def _tier(n):
    if n < EXPLORATORY_ANALYSIS_MIN:  return 'BELOW_MINIMUM'
    if n < RECOMMENDATION_MIN:        return 'EXPLORATORY'
    if n < PREFERRED_CALIBRATION_MIN: return 'RECOMMENDATION'
    return 'HIGH_CONFIDENCE'


def run_analysis() -> str:
    L = []
    now_str = datetime.now(pytz.timezone('America/New_York')).strftime('%Y-%m-%d %H:%M ET')
    L.append('=' * 70)
    L.append('MRE CALIBRATION ANALYZER REPORT')
    L.append(f'Generated: {now_str}  |  Standards: {STANDARDS_VERSION}')
    L.append('=' * 70)

    spreadsheet   = _get_spreadsheet()
    closed_trades = _load_closed_trades()
    cycle_history = _load_cycle_history(spreadsheet) if spreadsheet else []
    n    = len(closed_trades)
    tier = _tier(n)
    can_recommend = tier in ('RECOMMENDATION', 'HIGH_CONFIDENCE')

    tier_msgs = {
        'BELOW_MINIMUM':   f'BELOW MINIMUM ({n}/{EXPLORATORY_ANALYSIS_MIN}). No analysis. Keep collecting.',
        'EXPLORATORY':     f'EXPLORATORY ({n} trades). Orientation only. No recommendations until {RECOMMENDATION_MIN}.',
        'RECOMMENDATION':  f'RECOMMENDATION TIER ({n} trades). Recommendations issued when criteria met.',
        'HIGH_CONFIDENCE': f'HIGH CONFIDENCE ({n} trades >= {PREFERRED_CALIBRATION_MIN}).',
    }
    L.append(f'\nTotal closed trades: {n}')
    L.append(f'Tier: {tier_msgs[tier]}')

    if tier == 'BELOW_MINIMUM':
        return '\n'.join(L)

    cv = _check_cycle_validity(closed_trades, cycle_history)
    L.append(f'\nCycle validity: {cv["reason"]}')
    if not cv['valid']:
        L.append('Informational run only — not a new calibration cycle.')

    oe = _expectancy(closed_trades)
    ow = _win_rate(closed_trades)
    L.append(f'\nOVERALL  win_rate={ow}%  expectancy={oe}')

    ch = _choke(closed_trades, cycle_history)
    L.append(
        f'\n{"CHOKE WARNING: " + ch["reason"] if ch["choke_warning"] else "Choke: " + ch["reason"]}'
    )

    recs = []
    L.append('\n' + '-' * 70)
    L.append('BUCKET ANALYSIS')
    L.append('-' * 70)

    for metric, bucket_defs in NUMERIC_BUCKETS.items():
        L.append(f'\n[ {metric.upper()} ]')
        flagged = _flag(_bucket_numeric(closed_trades, metric, bucket_defs), oe, ow, can_recommend)
        for b in flagged:
            tag = f'[{b["flag"]}]' if b['flag'] != 'OK' else ''
            L.append(
                f'  {b["label"]:12} n={b["count"]:3}  '
                f'WR={str(b["win_rate"])+"%":7}  exp={b["expectancy"]}  {tag}'
            )
            if b.get('rec') and can_recommend:
                L.append(f'    -> {b["rec"]}')
                recs.append({'metric': metric, 'bucket': b['label'], 'text': b['rec']})

    for metric in CATEGORICAL_METRICS:
        L.append(f'\n[ {metric.upper()} ]')
        flagged = _flag(_bucket_categorical(closed_trades, metric), oe, ow, can_recommend)
        for b in flagged:
            tag = f'[{b["flag"]}]' if b['flag'] != 'OK' else ''
            L.append(
                f'  {str(b["label"]):20} n={b["count"]:3}  '
                f'WR={str(b["win_rate"])+"%":7}  exp={b["expectancy"]}  {tag}'
            )
            if b.get('rec') and can_recommend:
                L.append(f'    -> {b["rec"]}')
                recs.append({'metric': metric, 'bucket': b['label'], 'text': b['rec']})

    L.append('\n' + '-' * 70)
    if not recs:
        L.append('NO RECOMMENDATIONS THIS CYCLE.')
    else:
        L.append(f'RECOMMENDATIONS ({len(recs)}) — all require human approval:')
        for i, r in enumerate(recs, 1):
            L.append(f'  [{i}] {r["metric"]} / {r["bucket"]}: {r["text"]}')

    L.append('\nNEXT STEPS:')
    L.append('  1. Review recommendations above.')
    L.append('  2. Approve or reject each individually.')
    L.append('  3. Run: python3 -m calibration.log_decision')
    L.append('  4. If approved: update financial_standards.py, increment STANDARDS_VERSION.')
    L.append('=' * 70)

    report_text = '\n'.join(L)

    if spreadsheet:
        _write_summary(spreadsheet, tier, n, oe, ow, ch['choke_warning'], len(recs), report_text, cycle_history)

    return report_text


def _write_summary(spreadsheet, tier, n, exp, wr, choke, rec_count, report_text, cycle_history):
    try:
        ws = _get_or_create_tab(spreadsheet, SHEET_TAB_CALIBRATION_REPORTS, CALIBRATION_REPORTS_HEADERS)
        if ws is None:
            return
        now_str = datetime.now(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        ws.append_row(
            [now_str, len(cycle_history) + 1, tier, n, exp, wr, str(choke), rec_count, report_text[:50000]],
            value_input_option='RAW',
        )
    except Exception as e:
        log.warning(f'[ANALYZER] Failed to write summary: {e}')


if __name__ == '__main__':
    print(run_analysis())
