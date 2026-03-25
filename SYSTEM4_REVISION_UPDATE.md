# AGENT PROMPT — SYSTEM 4 REVISION — v1.2
# Targeted fixes only. Read the full prompt before starting any work.
# Execute blocks in order. Do not skip any block.

---

## WHO YOU ARE AND WHAT YOU ARE DOING

You are applying a targeted revision to the System 4 implementation of the
Financial Assistant Project.
The repo lives at: /home/alejandro/Project_Financial_Assistant/

Four changes only:
1. Force-regenerate all dashboard pages using existing stored data
2. Add real GitHub Pages URL to email template
3. Allow debug runs to write to the archive (tagged MANUAL RUN)
4. Add manual cleanup trigger alongside the existing automatic cleanup

Do not push or pull. Do not create branches. Implement only.
Do not modify any file not explicitly listed in this prompt.

---

## CURRENT FILE STRUCTURE (RELEVANT FILES ONLY)

```
Project_Financial_Assistant/
  config.py                             — GITHUB_PAGES_URL constant lives here
  main.py                               — coordinator
  reports/
    report_builder.py                   — builds email + full HTML
    dashboard_builder.py                — builds docs/ dashboard
    templates/
      intraday_email.html               — Jinja2 email template
  docs/
    index.html                          — home page
    rank.html                           — rank page
    archive.html                        — archive page
    guide.html                          — guide page (do not touch)
    assets/
      data/
        reports.json                    — run index
        rank.json                       — weekly rank data
        weekly_archive.json             — archive data
  scripts/
    cleanup_reports.py                  — weekly cleanup
```

---

## BLOCK 1 — FORCE-REGENERATE ALL DASHBOARD PAGES

### What to do

Write a standalone bootstrap script at:
  scripts/bootstrap_dashboard.py

This script regenerates docs/index.html, docs/rank.html, and docs/archive.html
using the data already stored in reports.json and rank.json.
It does not require a live pipeline run.
It can be re-run any time a manual page refresh is needed.

### Script content

```python
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
```

### After writing the script, run it immediately:

```bash
cd /home/alejandro/Project_Financial_Assistant
python scripts/bootstrap_dashboard.py
```

If all three pages report success, run:

```bash
git add docs/index.html docs/rank.html docs/archive.html scripts/bootstrap_dashboard.py
git commit -m "Refresh dashboard pages and add bootstrap script"
git push
```

If any page fails, fix the error before committing.

---

## BLOCK 2 — ADD REAL GITHUB PAGES URL TO EMAIL TEMPLATE

### Current state

config.py already has:
```python
GITHUB_PAGES_URL = os.environ.get('GITHUB_PAGES_URL', 'https://your-username.github.io/your-repo')
```

The real URL is: https://xfranxd.github.io/Financial_Assistant_Project

### Step 1 — Update config.py default

In config.py, change the default fallback value:

```python
GITHUB_PAGES_URL = os.environ.get('GITHUB_PAGES_URL', 'https://xfranxd.github.io/Financial_Assistant_Project')
```

### Step 2 — Pass URL into build_intraday_report()

In reports/report_builder.py, find build_intraday_report().
At the top of the function, import and read the URL:

```python
from config import GITHUB_PAGES_URL
dashboard_url = GITHUB_PAGES_URL
```

Pass dashboard_url to the email template render call:
```python
email_html = email_tpl.render(
    ...existing args...,
    dashboard_url = dashboard_url,
)
```

Do NOT pass it to the full HTML template — the full report is already the
destination, it does not need to link to itself.

### Step 3 — Update intraday_email.html template

Find the current generic dashboard line:
```html
<div style="font-family:monospace;font-size:12px;color:#555577;
            text-align:center;padding:16px 0 8px;border-top:1px solid #1e1e3a;
            margin-top:20px;">
  Full report + AI research prompt available at the dashboard
</div>
```

Replace it with a real clickable link:
```html
<div style="font-family:monospace;font-size:12px;color:#555577;
            text-align:center;padding:16px 0 8px;border-top:1px solid #1e1e3a;
            margin-top:20px;">
  Full report + AI research prompt:
  <a href="{{ dashboard_url }}" style="color:#00aaff;text-decoration:none;">
    {{ dashboard_url }}
  </a>
</div>
```

---

## BLOCK 3 — ALLOW DEBUG RUNS TO WRITE TO ARCHIVE (TAGGED MANUAL RUN)

### What to change

Debug runs (FORCE_TICKERS mode) currently pass is_debug=True to build_dashboard(),
which causes _update_weekly_archive() to return immediately without writing anything.

Remove that block entirely. Debug runs must write to the archive like normal runs,
but tagged so they are visually distinct on the archive page.

### Step 1 — Add run_type field to run_entry in _update_weekly_archive()

In reports/dashboard_builder.py, find _update_weekly_archive().

Remove the early return guard:
```python
if is_debug:
    return
```

Add run_type to run_entry:
```python
run_entry = {
    'id':        run_id,
    'run_type':  'MANUAL' if is_debug else 'SCHEDULED',
    'timestamp': now_et.strftime('%Y-%m-%dT%H:%M'),
    ...rest of existing fields unchanged...
}
```

Everything else in _update_weekly_archive() stays identical.

### Step 2 — Update _render_archive_html() to show MANUAL RUN badge

In _render_archive_html(), find the run header block inside the run loop.
This is the clickable div that shows timestamp + slot + count + verdict counts.

Add a run_type badge next to the timestamp. Find this line:
```python
ts         = run.get('timestamp', '')
slot       = run.get('slot', '')
```

Add after it:
```python
run_type   = run.get('run_type', 'SCHEDULED')
is_manual  = run_type == 'MANUAL'
type_badge = (
    '<span style="background:#1a0a2a;border:1px solid #6600aa;color:#aa44ff;'
    'font-size:10px;padding:1px 6px;border-radius:3px;margin-left:8px;'
    'text-transform:uppercase;letter-spacing:.05em;">MANUAL RUN</span>'
    if is_manual else ''
)
```

Then inject {type_badge} into the run header span, right after the timestamp:

Find the run header f-string line that contains:
```python
f'<span style="color:#e8e8f0;">{ts}</span> '
f'<span style="color:#8888aa;">· {slot} · {count} stock{"s" if count!=1 else ""}</span>'
```

Replace with:
```python
f'<span style="color:#e8e8f0;">{ts}</span>'
f'{type_badge} '
f'<span style="color:#8888aa;">· {slot} · {count} stock{"s" if count!=1 else ""}</span>'
```

### Step 3 — Remove is_debug guard from main.py debug pipeline call

In main.py, find the build_dashboard() call inside _run_force_ticker_pipeline()
(around line 418). It currently passes is_debug=True.

Change it to is_debug=True BUT this is now only used for the run_type tag,
not as a skip guard. No change needed in main.py — the is_debug=True value
is still correct, it now just controls the badge instead of skipping entirely.

No changes needed in main.py.

---

## BLOCK 4 — ADD MANUAL CLEANUP TRIGGER

### What to do

The existing cleanup runs automatically every Sunday at 23:00 UTC via GitHub Actions.
Add a manual trigger so cleanup can be run on demand for testing and verification.

Two changes: one to the script, one to the GitHub Actions workflow.

### Step 1 — Find the GitHub Actions workflow file

```bash
find /home/alejandro/Project_Financial_Assistant/.github -name "*.yml" | head -10
```

Do NOT just pick any workflow file. You must find the one file that contains
ALL THREE of the following strings:
- `cleanup_reports` or `run_cleanup`
- `0 23 * * 0`
- `schedule`

Run these two commands and compare their output. The correct file appears in BOTH:

```bash
grep -rl "cleanup_reports" /home/alejandro/Project_Financial_Assistant/.github/
grep -rl "0 23 \* \* 0" /home/alejandro/Project_Financial_Assistant/.github/
```

Only modify the file that appears in both results.
If no file appears in both, report the issue and stop — do not guess.
If more than one file appears in both, report the filenames and stop — do not modify either.

### Step 2 — Add workflow_dispatch trigger to the cleanup workflow

In the cleanup workflow YAML file, find the `on:` block.
It currently has only a `schedule:` trigger.

Add `workflow_dispatch:` as a second trigger:

```yaml
on:
  schedule:
    - cron: '0 23 * * 0'   # Every Sunday at 23:00 UTC — keep existing
  workflow_dispatch:         # Manual trigger — add this line
```

The `workflow_dispatch:` line with no parameters is sufficient.
It enables the "Run workflow" button in GitHub Actions UI with no extra inputs.

### Step 3 — Add a manual runner to cleanup_reports.py

At the bottom of scripts/cleanup_reports.py, the existing entry point is:
```python
if __name__ == '__main__':
    run_cleanup()
```

This already works for local manual runs:
```bash
cd /home/alejandro/Project_Financial_Assistant
python scripts/cleanup_reports.py
```

Add a confirmation prompt so accidental runs don't delete files without warning:

Replace the existing entry point block at the bottom of the file with the
following TWO blocks in this exact order. `_dry_run()` MUST come first.
Do not reverse the order. If `_dry_run()` is placed after `if __name__`,
it will crash with NameError when called.

```python
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
```

### Manual usage summary

Local dry run (no deletions, just shows what would be affected):
```bash
cd /home/alejandro/Project_Financial_Assistant
python scripts/cleanup_reports.py
```

Local forced run (actually deletes):
```bash
python scripts/cleanup_reports.py --force
```

GitHub Actions manual run:
- Go to Actions tab in the repo
- Select the cleanup workflow
- Click "Run workflow"
- This runs the full cleanup via the workflow_dispatch trigger

---

## BLOCK 5 — VERIFICATION

```bash
cd /home/alejandro/Project_Financial_Assistant

# Syntax checks
python -m py_compile scripts/bootstrap_dashboard.py && echo "bootstrap_dashboard syntax OK"
python -m py_compile scripts/cleanup_reports.py && echo "cleanup_reports syntax OK"
python -m py_compile reports/dashboard_builder.py && echo "dashboard_builder syntax OK"
python -m py_compile reports/report_builder.py && echo "report_builder syntax OK"

# Import checks
python -c "from scripts.cleanup_reports import run_cleanup, _dry_run; print('cleanup_reports imports OK')"
python -c "from reports.dashboard_builder import build_dashboard; print('dashboard_builder imports OK')"

# Run the bootstrap script
python scripts/bootstrap_dashboard.py
```

If all checks pass and bootstrap completes, commit and push:
```bash
git add docs/index.html docs/rank.html docs/archive.html
git add scripts/bootstrap_dashboard.py
git add scripts/cleanup_reports.py
git add reports/dashboard_builder.py
git add reports/report_builder.py
git add reports/templates/intraday_email.html
git add config.py
git commit -m "System 4 revision: page refresh, email URL, manual run archive, cleanup trigger"
git push
```

---

## EXECUTION ORDER

1. Block 1 — Write and run bootstrap_dashboard.py
2. Block 2 — Add GitHub Pages URL to email
3. Block 3 — Allow debug runs to write to archive with MANUAL RUN tag
4. Block 4 — Add manual cleanup trigger and dry run mode
5. Block 5 — Verification and push

Do not skip any block. Do not reorder blocks.
Do not modify any file not listed above.
Do not modify main.py.
Do not modify guide.html.
Do not modify any file in eq_analyzer/ or sector_detector/.
Do not modify contracts/eq_schema.py or contracts/sector_schema.py.