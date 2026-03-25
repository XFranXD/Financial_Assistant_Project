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
Prunes weekly_archive.json of stale entries after cleanup.
"""

import os
import json
from datetime import datetime
import pytz

REPORTS_DIR      = os.path.join('reports', 'output')
SERVED_REPORTS_DIR = os.path.join('docs', 'reports')
DATA_DIR         = os.path.join('docs', 'assets', 'data')
KEEP_DAYS        = 30
DELETE_DAYS      = 90


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

    # Also prune docs/reports/ on the same policy
    served_removed = 0
    if os.path.exists(SERVED_REPORTS_DIR):
        for fname in os.listdir(SERVED_REPORTS_DIR):
            if not fname.endswith('.html'):
                continue
            fpath = os.path.join(SERVED_REPORTS_DIR, fname)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath), tz=pytz.utc)
                age   = (now - mtime).days
                if age > DELETE_DAYS:
                    os.remove(fpath)
                    served_removed += 1
                    print(f'Deleted served report ({age}d old): {fname}')
                elif age > KEEP_DAYS:
                    print(f'Aged served report ({age}d): {fname}')
            except Exception as e:
                print(f'Error processing served report {fname}: {e}')

    _rebuild_index()
    _prune_weekly_archive()
    print(f'Cleanup complete. Removed {removed} output + {served_removed} served file(s).')


def _rebuild_index():
    """Rebuild reports.json from files actually present on disk.
    Reads existing JSON for metadata, removes entries whose HTML files
    no longer exist. Never invents new entries — only prunes stale ones."""
    index_path = os.path.join(DATA_DIR, 'reports.json')
    if not os.path.exists(index_path):
        print('reports.json not found — skipping index rebuild.')
        return
    try:
        with open(index_path) as f:
            index = json.load(f)

        existing_files = set(os.listdir(REPORTS_DIR)) if os.path.exists(REPORTS_DIR) else set()

        original_count = len(index.get('reports', []))
        clean_reports  = []

        for entry in index.get('reports', []):
            # Each entry in reports.json does not store the filename directly.
            # We match by date + time + slot to infer the filename pattern.
            # Conservative approach: keep the entry unless we can confirm
            # its corresponding full HTML file is gone.
            date   = entry.get('date', '').replace('-', '')
            # slot stored as "09:30" but filenames use "0930"
            slot_s = entry.get('slot', '').replace(':', '')
            # Look for any intraday_full file matching both date and slot
            matched = any(
                f.startswith('intraday_full') and date in f and slot_s in f
                for f in existing_files
            )
            if matched or not date:
                clean_reports.append(entry)

        index['reports'] = clean_reports
        pruned = original_count - len(clean_reports)

        with open(index_path, 'w') as f:
            json.dump(index, f, indent=2)

        print(f'reports.json rebuilt: {len(clean_reports)} entries kept, {pruned} pruned.')
    except Exception as e:
        print(f'Index rebuild failed: {e}')


def _prune_weekly_archive():
    """Remove stale prompt entries from weekly_archive.json.
    An entry is stale if its run timestamp date has no corresponding
    HTML file in reports/output/. Conservative: only prunes runs older
    than DELETE_DAYS with no matching file."""
    archive_path = os.path.join(DATA_DIR, 'weekly_archive.json')
    if not os.path.exists(archive_path):
        return
    try:
        with open(archive_path) as f:
            archive = json.load(f)

        existing_files = set(os.listdir(REPORTS_DIR)) if os.path.exists(REPORTS_DIR) else set()
        now = datetime.now(pytz.utc)
        pruned_runs = 0

        for week_key, week_data in list(archive.get('weeks', {}).items()):
            clean_runs = []
            for run in week_data.get('runs', []):
                ts = run.get('timestamp', '')
                if not ts:
                    clean_runs.append(run)
                    continue
                try:
                    run_date = datetime.strptime(ts[:10], '%Y-%m-%d').replace(tzinfo=pytz.utc)
                    age_days = (now - run_date).days
                except Exception:
                    clean_runs.append(run)
                    continue

                if age_days <= DELETE_DAYS:
                    clean_runs.append(run)
                else:
                    date_fragment = ts[:10].replace('-', '')
                    has_file = any(date_fragment in f for f in existing_files)
                    if has_file:
                        clean_runs.append(run)
                    else:
                        pruned_runs += 1

            week_data['runs'] = clean_runs

        # Remove empty weeks
        archive['weeks'] = {k: v for k, v in archive['weeks'].items() if v.get('runs')}

        with open(archive_path, 'w') as f:
            json.dump(archive, f, indent=2)

        print(f'weekly_archive.json pruned: {pruned_runs} stale run(s) removed.')
    except Exception as e:
        print(f'weekly_archive prune failed: {e}')


def _dry_run():
    """Show what cleanup would delete without actually deleting anything."""
    now          = datetime.now(pytz.utc)
    would_delete = []
    would_age    = []

    if not os.path.exists(REPORTS_DIR):
        print(f'Reports dir not found: {REPORTS_DIR}')
        return

    for fname in os.listdir(REPORTS_DIR):
        if not fname.endswith('.html'):
            continue
        fpath = os.path.join(REPORTS_DIR, fname)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath), tz=pytz.utc)
            age   = (now - mtime).days
            if age > DELETE_DAYS:
                would_delete.append((fname, age))
            elif age > KEEP_DAYS:
                would_age.append((fname, age))
        except Exception as e:
            print(f'Error reading {fname}: {e}')

    if would_delete:
        print(f'\nWould DELETE ({len(would_delete)} files):')
        for fname, age in sorted(would_delete, key=lambda x: x[1], reverse=True):
            print(f'  {fname}  ({age}d old)')
    else:
        print('\nNo files would be deleted.')

    if would_age:
        print(f'\nWould LOG as aged ({len(would_age)} files):')
        for fname, age in sorted(would_age, key=lambda x: x[1], reverse=True):
            print(f'  {fname}  ({age}d old)')
    else:
        print('No files in aged range.')

    print(f'\nDry run complete. Run with --force to execute deletions.')


if __name__ == '__main__':
    import sys
    if '--force' in sys.argv:
        print('Running cleanup (--force flag detected)...')
        run_cleanup()
    else:
        print('Manual cleanup mode.')
        print(f'This will delete HTML report files older than {DELETE_DAYS} days.')
        print('Run with --force to execute, or press Enter to do a dry run (no deletions).')
        choice = input('> ').strip().lower()
        if choice == '':
            # Dry run — show what would be deleted without deleting
            _dry_run()
        else:
            print('Aborted.')
