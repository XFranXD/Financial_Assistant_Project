"""
scripts/cleanup_reports.py
Weekly cleanup of old report output files + targeted force-delete mode.

Scheduled mode (--force):
  Runs via GitHub Actions every Sunday at 23:00 UTC.
  Policy:
    - Files newer than 30 days:  keep
    - Files 30-90 days old:      keep but log as aged
    - Files older than 90 days:  delete permanently
  Never deletes the reports/output/ directory itself.
  Rebuilds docs/assets/data/reports.json after cleanup.
  Prunes weekly_archive.json of stale entries after cleanup.

Force-delete mode (--delete TARGET):
  Deletes a specific run or range of runs by date/slot.
  TARGET formats (prefix match against date field in reports.json):
    2026                → all reports from year 2026
    2026-03             → all reports from March 2026
    2026-03-31          → all reports from that day (all slots)
    2026-03-31 2        → exactly that slot (slot 1=9:45, 2=11:45,
                          3=13:45, 4=16:00)
  After file deletion:
    - Matching entries removed from reports.json
    - Matching runs removed from weekly_archive.json
    - rank.json updated: ticker falls back to previous best score
      from weekly_archive.json, or removed entirely if no prior entry
"""

import os
import sys
import json
from datetime import datetime
import pytz

REPORTS_DIR        = os.path.join('reports', 'output')
SERVED_REPORTS_DIR = os.path.join('docs', 'reports')
DATA_DIR           = os.path.join('docs', 'assets', 'data')
KEEP_DAYS          = 30
DELETE_DAYS        = 90
CACHE_DIR          = os.path.join('data', 'fundamentals_cache')

# Slot number → slot string mapping (as stored in reports.json)
SLOT_MAP = {
    '1': '9:45-11:15',
    '2': '11:45-13:15',
    '3': '13:45-15:15',
    '4': '16:00-17:20',
}


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULED CLEANUP (--force)
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# TARGETED FORCE-DELETE (--delete TARGET)
# ══════════════════════════════════════════════════════════════════════════════

def _parse_target(raw: str):
    """
    Parse and normalize the TARGET input string.
    Returns (date_prefix, slot_str_or_None).
    Raises ValueError on invalid format.

    Valid inputs:
      '2026'              → ('2026', None)
      '2026-03'           → ('2026-03', None)
      '2026-03-31'        → ('2026-03-31', None)
      '2026-03-31 2'      → ('2026-03-31', '11:45-13:15')
      '2026 -03-31 2'     → normalized → ('2026-03-31', '11:45-13:15')
    """
    # Normalize: collapse whitespace, remove spaces around dashes
    normalized = ' '.join(raw.strip().split())
    normalized = normalized.replace(' -', '-').replace('- ', '-')

    parts = normalized.split(' ')
    date_part = parts[0]
    slot_part = parts[1] if len(parts) > 1 else None

    # Validate date prefix
    segments = date_part.split('-')
    if len(segments) == 1:
        if not segments[0].isdigit() or len(segments[0]) != 4:
            raise ValueError(f'Invalid year: {segments[0]}')
    elif len(segments) == 2:
        if not segments[0].isdigit() or len(segments[0]) != 4:
            raise ValueError(f'Invalid year: {segments[0]}')
        if not segments[1].isdigit() or len(segments[1]) != 2:
            raise ValueError(f'Invalid month: {segments[1]}')
    elif len(segments) == 3:
        if not segments[0].isdigit() or len(segments[0]) != 4:
            raise ValueError(f'Invalid year: {segments[0]}')
        if not segments[1].isdigit() or len(segments[1]) != 2:
            raise ValueError(f'Invalid month: {segments[1]}')
        if not segments[2].isdigit() or len(segments[2]) != 2:
            raise ValueError(f'Invalid day: {segments[2]}')
    else:
        raise ValueError(f'Invalid date prefix: {date_part}')

    # Validate and resolve slot
    slot_str = None
    if slot_part is not None:
        if len(segments) != 3:
            raise ValueError('Slot number requires a full date (YYYY-MM-DD).')
        if slot_part not in SLOT_MAP:
            raise ValueError(
                f'Invalid slot: {slot_part}. '
                f'Valid slots: 1=9:45-11:15, 2=11:45-13:15, '
                f'3=13:45-15:15, 4=16:00-17:20'
            )
        slot_str = SLOT_MAP[slot_part]

    return date_part, slot_str


def _match_report_entry(entry: dict, date_prefix: str, slot_str) -> bool:
    """Return True if a reports.json entry matches the target."""
    entry_date = entry.get('date', '')
    if not entry_date.startswith(date_prefix):
        return False
    if slot_str is not None:
        return entry.get('slot', '') == slot_str
    return True


def _match_archive_run(run: dict, date_prefix: str, slot_str) -> bool:
    """Return True if a weekly_archive.json run matches the target."""
    ts = run.get('timestamp', '')
    run_date = ts[:10] if ts else ''
    if not run_date.startswith(date_prefix):
        return False
    if slot_str is not None:
        return run.get('slot', '') == slot_str
    return True


def _delete_report_files(report_url: str) -> int:
    """
    Delete the HTML file referenced by report_url from both
    docs/reports/ and reports/output/. Returns count deleted.
    """
    if not report_url:
        return 0
    fname  = os.path.basename(report_url)
    count  = 0
    for directory in [SERVED_REPORTS_DIR, REPORTS_DIR]:
        fpath = os.path.join(directory, fname)
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
                print(f'  Deleted: {fpath}')
                count += 1
            except Exception as e:
                print(f'  Error deleting {fpath}: {e}')
    return count


def _update_rank_json(deleted_tickers: set, date_prefix: str, slot_str):
    """
    For each deleted ticker, find its previous best score in
    weekly_archive.json (excluding the deleted runs). If a prior
    entry exists, update rank.json with that score. If not, remove
    the ticker from rank.json entirely.
    """
    rank_path    = os.path.join(DATA_DIR, 'rank.json')
    archive_path = os.path.join(DATA_DIR, 'weekly_archive.json')

    if not os.path.exists(rank_path):
        print('  rank.json not found — skipping rank update.')
        return
    if not deleted_tickers:
        return

    try:
        with open(rank_path) as f:
            rank_data = json.load(f)
    except Exception as e:
        print(f'  Error reading rank.json: {e}')
        return

    # Build best prior scores from weekly_archive.json
    # excluding the runs being deleted right now
    prior_best = {}  # ticker → best candidate dict from archive
    if os.path.exists(archive_path):
        try:
            with open(archive_path) as f:
                archive = json.load(f)
            for week_data in archive.get('weeks', {}).values():
                for run in week_data.get('runs', []):
                    # Skip runs that are being deleted
                    if _match_archive_run(run, date_prefix, slot_str):
                        continue
                    for cand in run.get('candidates', []):
                        ticker = cand.get('ticker', '')
                        if ticker not in deleted_tickers:
                            continue
                        conf = cand.get('confidence', 0)
                        if conf > prior_best.get(ticker, {}).get('confidence', -1):
                            prior_best[ticker] = cand
        except Exception as e:
            print(f'  Error reading weekly_archive.json for rank fallback: {e}')

    stocks = rank_data.get('stocks', {})
    for ticker in deleted_tickers:
        if ticker not in stocks:
            continue
        if ticker in prior_best:
            prior = prior_best[ticker]
            # Update confidence and core display fields from prior best
            stocks[ticker]['confidence']     = prior.get('confidence', 0)
            stocks[ticker]['market_verdict'] = prior.get('market_verdict', '')
            stocks[ticker]['market_verdict_display'] = prior.get(
                'market_verdict', stocks[ticker].get('market_verdict_display', ''))
            print(f'  rank.json: {ticker} rolled back to conf={prior.get("confidence")}')
        else:
            del stocks[ticker]
            print(f'  rank.json: {ticker} removed (no prior entry found)')

    rank_data['stocks'] = stocks
    try:
        tmp = rank_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(rank_data, f, indent=2)
        os.replace(tmp, rank_path)
        print('  rank.json updated.')
    except Exception as e:
        print(f'  Error writing rank.json: {e}')


def run_force_delete(target: str):
    """
    Main entry point for targeted deletion.
    Parses target, matches entries, deletes files, updates all JSON files.
    """
    try:
        date_prefix, slot_str = _parse_target(target)
    except ValueError as e:
        print(f'ERROR: {e}')
        print(
            'Valid formats:\n'
            '  2026              → all reports from 2026\n'
            '  2026-03           → all reports from March 2026\n'
            '  2026-03-31        → all reports from that day\n'
            '  2026-03-31 2      → slot 2 on that day (11:45-13:15)\n'
            'Slot numbers: 1=9:45-11:15  2=11:45-13:15  '
            '3=13:45-15:15  4=16:00-17:20'
        )
        sys.exit(1)

    slot_desc = f' slot={slot_str}' if slot_str else ''
    print(f'Force-delete target: date_prefix={date_prefix}{slot_desc}')
    print('─' * 60)

    # ── Step 1: Load and match reports.json ──────────────────────
    reports_path = os.path.join(DATA_DIR, 'reports.json')
    if not os.path.exists(reports_path):
        print('reports.json not found — nothing to delete.')
        return

    try:
        with open(reports_path) as f:
            reports_data = json.load(f)
    except Exception as e:
        print(f'ERROR reading reports.json: {e}')
        sys.exit(1)

    all_entries     = reports_data.get('reports', [])
    matched_entries = [
        e for e in all_entries
        if _match_report_entry(e, date_prefix, slot_str)
    ]

    if not matched_entries:
        print('No matching reports found. Nothing deleted.')
        return

    print(f'Matched {len(matched_entries)} report(s):')
    for e in matched_entries:
        tickers = ', '.join(e.get('tickers', []))
        print(f'  {e.get("date")} · {e.get("slot")} · {tickers}')

    # ── Step 2: Delete HTML files ─────────────────────────────────
    print('\nDeleting HTML files...')
    files_deleted = 0
    for entry in matched_entries:
        files_deleted += _delete_report_files(entry.get('report_url', ''))

    # ── Step 3: Update reports.json ───────────────────────────────
    print('\nUpdating reports.json...')
    clean_reports = [
        e for e in all_entries
        if not _match_report_entry(e, date_prefix, slot_str)
    ]
    reports_data['reports'] = clean_reports
    try:
        tmp = reports_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(reports_data, f, indent=2)
        os.replace(tmp, reports_path)
        removed = len(all_entries) - len(clean_reports)
        print(f'  reports.json: {removed} entr(ies) removed, '
              f'{len(clean_reports)} remaining.')
    except Exception as e:
        print(f'  ERROR writing reports.json: {e}')

    # ── Step 4: Update weekly_archive.json ───────────────────────
    print('\nUpdating weekly_archive.json...')
    archive_path = os.path.join(DATA_DIR, 'weekly_archive.json')
    archive_pruned = 0
    if os.path.exists(archive_path):
        try:
            with open(archive_path) as f:
                archive = json.load(f)
            for week_data in archive.get('weeks', {}).values():
                original = len(week_data.get('runs', []))
                week_data['runs'] = [
                    r for r in week_data.get('runs', [])
                    if not _match_archive_run(r, date_prefix, slot_str)
                ]
                archive_pruned += original - len(week_data['runs'])
            # Remove empty weeks
            archive['weeks'] = {
                k: v for k, v in archive['weeks'].items()
                if v.get('runs')
            }
            tmp = archive_path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(archive, f, indent=2)
            os.replace(tmp, archive_path)
            print(f'  weekly_archive.json: {archive_pruned} run(s) removed.')
        except Exception as e:
            print(f'  ERROR updating weekly_archive.json: {e}')
    else:
        print('  weekly_archive.json not found — skipping.')

    # ── Step 5: Update rank.json ──────────────────────────────────
    print('\nUpdating rank.json...')
    deleted_tickers = set()
    for entry in matched_entries:
        for t in entry.get('tickers', []):
            deleted_tickers.add(t)
    _update_rank_json(deleted_tickers, date_prefix, slot_str)

    # ── Step 6: Clear fundamentals cache for affected tickers ──────
    print('\nClearing fundamentals cache...')
    cache_cleared = 0
    if os.path.exists(CACHE_DIR):
        for ticker in deleted_tickers:
            cache_file = os.path.join(CACHE_DIR, f'{ticker}.json')
            if os.path.exists(cache_file):
                try:
                    os.remove(cache_file)
                    cache_cleared += 1
                    print(f'  Cleared cache: {ticker}.json')
                except Exception as e:
                    print(f'  Error clearing cache for {ticker}: {e}')
    else:
        print(f'  Cache dir not found: {CACHE_DIR} — skipping.')

    print('\n' + '─' * 60)
    print(
        f'Done. {files_deleted} file(s) deleted, '
        f'{len(matched_entries)} report entr(ies) removed, '
        f'{cache_cleared} cache file(s) cleared.'
    )


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULED CLEANUP HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _rebuild_index():
    """Rebuild reports.json from files actually present on disk."""
    index_path = os.path.join(DATA_DIR, 'reports.json')
    if not os.path.exists(index_path):
        print('reports.json not found — skipping index rebuild.')
        return
    try:
        with open(index_path) as f:
            index = json.load(f)

        existing_files = (
            set(os.listdir(REPORTS_DIR))
            if os.path.exists(REPORTS_DIR) else set()
        )

        original_count = len(index.get('reports', []))
        clean_reports  = []

        for entry in index.get('reports', []):
            date   = entry.get('date', '').replace('-', '')
            slot_s = entry.get('slot', '').replace(':', '')
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

        print(f'reports.json rebuilt: {len(clean_reports)} entries kept, '
              f'{pruned} pruned.')
    except Exception as e:
        print(f'Index rebuild failed: {e}')


def _prune_weekly_archive():
    """Remove stale entries from weekly_archive.json."""
    archive_path = os.path.join(DATA_DIR, 'weekly_archive.json')
    if not os.path.exists(archive_path):
        return
    try:
        with open(archive_path) as f:
            archive = json.load(f)

        existing_files = (
            set(os.listdir(REPORTS_DIR))
            if os.path.exists(REPORTS_DIR) else set()
        )
        now        = datetime.now(pytz.utc)
        pruned_runs = 0

        for week_data in archive.get('weeks', {}).values():
            clean_runs = []
            for run in week_data.get('runs', []):
                ts = run.get('timestamp', '')
                if not ts:
                    clean_runs.append(run)
                    continue
                try:
                    run_date = datetime.strptime(
                        ts[:10], '%Y-%m-%d'
                    ).replace(tzinfo=pytz.utc)
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

        archive['weeks'] = {
            k: v for k, v in archive['weeks'].items()
            if v.get('runs')
        }

        with open(archive_path, 'w') as f:
            json.dump(archive, f, indent=2)

        print(f'weekly_archive.json pruned: {pruned_runs} stale run(s) removed.')
    except Exception as e:
        print(f'weekly_archive prune failed: {e}')


def _dry_run():
    """Show what scheduled cleanup would delete without deleting anything."""
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


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    if '--force' in sys.argv:
        print('Running scheduled cleanup (--force)...')
        run_cleanup()
    elif '--delete' in sys.argv:
        idx = sys.argv.index('--delete')
        # Accept target as remaining args joined (handles spaces naturally)
        remaining = sys.argv[idx + 1:]
        if not remaining:
            print('ERROR: --delete requires a TARGET argument.')
            print('Example: python scripts/cleanup_reports.py --delete "2026-03-31 2"')
            sys.exit(1)
        target = ' '.join(remaining)
        run_force_delete(target)
    else:
        print('Manual cleanup mode.')
        print(f'This will delete HTML report files older than {DELETE_DAYS} days.')
        print('Run with --force to execute, or press Enter to do a dry run.')
        choice = input('> ').strip().lower()
        if choice == '':
            _dry_run()
        else:
            print('Aborted.')
