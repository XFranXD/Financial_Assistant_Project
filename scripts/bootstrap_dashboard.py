"""
scripts/bootstrap_dashboard.py

Force-regenerates all dashboard pages from existing stored data.
Use this any time the pages need to be refreshed without running the full pipeline.

Usage:
    cd /home/alejandro/Project_Financial_Assistant
    python scripts/bootstrap_dashboard.py
"""

import os
import json
import sys

# Anchor all paths to project root regardless of where script is run from
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from reports.dashboard_builder import (
    _write_index_page,
    _write_rank_page,
    _write_archive_page,
)

DATA_DIR = os.path.join(BASE_DIR, 'docs', 'assets', 'data')


def main():
    print('Bootstrapping dashboard pages from stored data...')

    # Load breadth and regime from most recent reports.json entry if available
    # Fall back to empty dicts — pages will show N/A for live market data
    # This is correct: live data is only available during a real pipeline run
    breadth = {}
    regime  = {}
    indices = {}

    try:
        index_path = os.path.join(DATA_DIR, 'reports.json')
        with open(index_path) as f:
            index = json.load(f)
        reports = index.get('reports', [])
        recent  = reports[0] if reports else {}
        breadth = {'label': recent.get('breadth', '')}
        regime  = {'label': recent.get('regime',  '')}
        print(f"  Using breadth='{breadth['label']}' regime='{regime['label']}' from most recent report entry.")
    except Exception as e:
        print(f'  Could not read reports.json ({e}) — using empty defaults.')

    # Regenerate index page
    try:
        _write_index_page(indices, breadth, regime)
        print('  docs/index.html written.')
    except Exception as e:
        print(f'  index.html failed: {e}')

    # Regenerate rank page
    try:
        _write_rank_page()
        print('  docs/rank.html written.')
    except Exception as e:
        print(f'  rank.html failed: {e}')

    # Regenerate archive page
    archive_path = os.path.join(DATA_DIR, 'weekly_archive.json')
    if not os.path.exists(archive_path):
        print('  weekly_archive.json not found — archive page will render empty (expected on first run).')
    try:
        _write_archive_page()
        print('  docs/archive.html written.')
    except Exception as e:
        print(f'  archive.html failed: {e}')

    # Validate output files were actually written
    for page in ['docs/index.html', 'docs/rank.html', 'docs/archive.html']:
        if os.path.exists(page) and os.path.getsize(page) > 0:
            print(f'  [OK] {page} ({os.path.getsize(page)} bytes)')
        else:
            print(f'  [MISSING or EMPTY] {page} — check errors above')

    print('Bootstrap complete.')
    print('Next step: git add docs/ && git commit -m "Refresh dashboard pages" && git push')


if __name__ == '__main__':
    main()
