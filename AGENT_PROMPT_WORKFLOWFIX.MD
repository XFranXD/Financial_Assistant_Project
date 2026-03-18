# DELTA PROMPT — market_scan.yml push fix + keepalive workflow
# This is a delta, not a rewrite.
# AGENT_PROGRESS.md must be updated BEFORE and AFTER every file touched.
# Format: "NOW WORKING ON <filename>" before, "COMPLETED <filename>" after.

---

## §ORDER

1. Update AGENT_PROGRESS.md — mark start
2. Modify .github/workflows/market_scan.yml — add git pull --rebase before push
3. Create .github/workflows/keepalive.yml — new file, no existing file touched
4. Update AGENT_PROGRESS.md — mark complete

---

## §DONOT

Do not touch any of these files under any circumstances:

- main.py
- report_builder.py
- summary_builder.py
- financial_parser.py
- Any file inside analyzers/
- Any file inside templates/
- Any file inside docs/
- Any file inside data/
- Any file inside scripts/
- requirements.txt
- Any existing state/ files
- AGENT_PROGRESS.md (except the protocol updates required above)

---

## §CONTEXT

### Problem 1 — Push rejection on market_scan.yml

Root cause: the commit step has no git pull before git push. When the
remote has any commits the runner does not have locally (from a previous
run, a manual push, or a concurrent job), the push is rejected with
"fetch first". The fix is one line added immediately before git push.

### Problem 2 — GitHub Actions schedule suppression

Root cause: GitHub silently suppresses scheduled workflow triggers on
repositories with no recent activity. This is a known GitHub free tier
behavior. There is no API or setting to disable it. The only reliable
workaround is ensuring the repository receives a commit every day,
keeping it active in GitHub's scheduler. A dedicated lightweight
keepalive workflow provides this without touching any system files.

---

## §FIX 1 — Add git pull --rebase before push in market_scan.yml

File: .github/workflows/market_scan.yml

Find this exact block:

      - name: Commit outputs
        run: |
          git config user.name  'github-actions[bot]'
          git config user.email 'github-actions[bot]@users.noreply.github.com'
          git add --force reports/output/ docs/ state/ data/fundamentals_cache/ logs/ || true
          git diff --staged --quiet || \
            git commit -m "Auto: market scan $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          git push

Replace with:

      - name: Commit outputs
        run: |
          git config user.name  'github-actions[bot]'
          git config user.email 'github-actions[bot]@users.noreply.github.com'
          git add --force reports/output/ docs/ state/ data/fundamentals_cache/ logs/ || true
          git diff --staged --quiet || \
            git commit -m "Auto: market scan $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          git pull --rebase origin main
          git push

Why this is safe: git pull --rebase origin main runs after the commit
is already formed locally. It replays the local commit on top of any
remote changes before pushing. This resolves the "fetch first" rejection
without discarding any output files. The || true on git add ensures a
failed add never blocks the rebase. No analytical files are touched.

---

## §FIX 2 — Create keepalive.yml

File: .github/workflows/keepalive.yml
This file does not exist yet. Create it at that exact path.

Full file content:

name: Keep Alive

on:
  schedule:
    - cron: '0 6 * * 1-5'
  workflow_dispatch:

jobs:
  keepalive:
    runs-on: ubuntu-latest
    timeout-minutes: 5

    permissions:
      contents: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Write keepalive timestamp
        run: |
          echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > state/keepalive.txt

      - name: Commit keepalive
        run: |
          git config user.name  'github-actions[bot]'
          git config user.email 'github-actions[bot]@users.noreply.github.com'
          git add state/keepalive.txt
          git diff --staged --quiet || \
            git commit -m "Keep alive $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          git pull --rebase origin main
          git push

Why this is safe: runs at 06:00 UTC weekdays only, well outside all
four market scan windows. Writes only to state/keepalive.txt. That path
is not read by main.py, any analyzer, or any report builder. The file
content is a plain UTC timestamp string. The keepalive workflow has no
Python dependency, no secrets, and no pip install step. It cannot affect
any analytical output.

---

## §VERIFY

After implementation, confirm all of the following:

1. .github/workflows/market_scan.yml contains the line
   "git pull --rebase origin main" immediately before "git push"
   and nowhere else in the file.

2. .github/workflows/keepalive.yml exists at that exact path.

3. keepalive.yml cron is '0 6 * * 1-5' — 06:00 UTC weekdays only.
   Confirm this does not overlap with any market_scan.yml cron window.
   market_scan.yml windows are 14:30, 16:30, 18:30, 20:10 UTC.
   06:00 UTC has zero overlap. Confirmed safe.

4. state/keepalive.txt does not appear in any import, open(), or
   read operation inside main.py or any module. Verify by searching
   the codebase for "keepalive" — the string should appear nowhere
   except the two workflow files.

5. Trigger keepalive.yml manually once via workflow_dispatch to
   confirm it commits and pushes without error before relying on
   the schedule.

6. On the next scheduled market scan run, confirm the push step
   completes without "fetch first" rejection.

---

## §DISCLAIMER

The system disclaimer already exists and renders correctly in every
report. Do not add any disclaimer anywhere in any file touched by
this delta.

---

## FOOTER

Scope: infrastructure only. Zero analytical files touched.
Files modified: 1 (.github/workflows/market_scan.yml)
Files created: 1 (.github/workflows/keepalive.yml)
Files protected: all analytical modules, all templates, all data
files, all docs, main.py, report_builder.py, summary_builder.py,
financial_parser.py, requirements.txt.

Changelog from previous version:
- market_scan.yml: added git pull --rebase origin main before git push
- keepalive.yml: new file, runs 06:00 UTC weekdays, writes timestamp
  to state/keepalive.txt to prevent GitHub schedule suppression