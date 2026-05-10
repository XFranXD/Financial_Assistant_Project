"""
calibration/log_decision.py
CLI helper — log a standards decision.

Local calibration/standards_history.log = primary (always written).
Google Sheets standards_history tab = backup (written after local succeeds).

Run: python3 -m calibration.log_decision
"""

import os
from datetime import datetime
import pytz

from calibration.calibration_config import (
    SHEET_TAB_STANDARDS_HISTORY,
    STANDARDS_HISTORY_HEADERS,
)

LOG_FILE = 'calibration/standards_history.log'


def _write_log(entry: str):
    os.makedirs('calibration', exist_ok=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(entry + '\n')


def _write_sheets(row: list) -> bool:
    try:
        from paper_trading.sheets_ledger import _get_sheet
        from calibration.calibration_analyzer import _get_or_create_tab
        sheet = _get_sheet()
        if sheet is None:
            return False
        ws = _get_or_create_tab(sheet.spreadsheet, SHEET_TAB_STANDARDS_HISTORY, STANDARDS_HISTORY_HEADERS)
        if ws is None:
            return False
        ws.append_row(row, value_input_option='RAW')
        return True
    except Exception as e:
        print(f'WARNING: Sheets write failed: {e}')
        return False


def main():
    print('MRE Standards Decision Logger')
    print('Local log = primary. Sheets = backup.')
    print('=' * 40)

    now_str = datetime.now(pytz.timezone('America/New_York')).strftime('%Y-%m-%dT%H:%M ET')
    cycle    = input('Cycle number: ').strip()
    metric   = input('Metric (or "none"): ').strip()
    old_val  = input('Old value: ').strip()
    new_val  = input('New value (or "REJECTED"): ').strip()
    rec      = input('Recommendation summary: ').strip()
    sim      = input('Simulation summary: ').strip()
    decision = input('Decision (APPROVED/REJECTED): ').strip().upper()
    reason   = input('Reasoning: ').strip()

    entry = (
        f'\n[{now_str}]\n'
        f'Cycle: {cycle} | Metric: {metric} | Decision: {decision}\n'
        f'Old: {old_val} | New: {new_val}\n'
        f'Rec: {rec}\nSim: {sim}\nReason: {reason}\n'
        f'{"-"*40}'
    )

    # Always write local log first — this is the durable record.
    _write_log(entry)
    print(f'Logged to {LOG_FILE}.')

    # Attempt Sheets write as backup. Failure does not invalidate the local log.
    sheets_ok = _write_sheets(
        [now_str, cycle, metric, old_val, new_val, rec, sim, decision, reason]
    )
    if sheets_ok:
        print('Also written to Sheets standards_history tab.')
    else:
        print('WARNING: Sheets write failed. Decision is still recorded in local log.')

    if decision == 'APPROVED' and metric.lower() != 'none':
        print('\nReminder: update financial_standards.py and increment STANDARDS_VERSION.')


if __name__ == '__main__':
    main()
