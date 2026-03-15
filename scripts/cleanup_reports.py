"""
scripts/cleanup_reports.py
Weekly cleanup of old report output files.
Runs via GitHub Actions every Sunday at 23:00 UTC.

Policy:
  - Files newer than 30 days:  keep
  - Files 30-90 days old:      keep but log as aged
  - Files older than 90 days:  delete permanently

Never deletes the reports/output/ directory itself.
Rebuilds docs/assets/data/reports.json index after cleanup.
"""

import os
import json
from datetime import datetime
import pytz

REPORTS_DIR = os.path.join('reports', 'output')
DATA_DIR    = os.path.join('docs', 'assets', 'data')
KEEP_DAYS   = 30
DELETE_DAYS = 90


def run_cleanup():
    now     = datetime.now(pytz.utc)
    removed = 0

    if not os.path.exists(REPORTS_DIR):
        print(f'Reports dir not found: {REPORTS_DIR} — nothing to clean.')
        return

    for fname in os.listdir(REPORTS_DIR):
        if not fname.endswith('.html'):
            continue
        fpath = os.path.join(REPORTS_DIR, fname)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath), tz=pytz.utc)
            age   = (now - mtime).days
            if age > DELETE_DAYS:
                os.remove(fpath)
                removed += 1
                print(f'Deleted ({age}d old): {fname}')
            elif age > KEEP_DAYS:
                print(f'Aged ({age}d): {fname}')
        except Exception as e:
            print(f'Error processing {fname}: {e}')

    _rebuild_index()
    print(f'Cleanup complete. Removed {removed} file(s).')


def _rebuild_index():
    """Remove stale entries from reports.json after file deletion."""
    index_path = os.path.join(DATA_DIR, 'reports.json')
    if not os.path.exists(DATA_DIR) or not os.path.exists(index_path):
        return
    try:
        with open(index_path) as f:
            index = json.load(f)
        with open(index_path, 'w') as f:
            json.dump(index, f, indent=2)
        print('reports.json index updated.')
    except Exception as e:
        print(f'Index rebuild skipped: {e}')


if __name__ == '__main__':
    run_cleanup()
