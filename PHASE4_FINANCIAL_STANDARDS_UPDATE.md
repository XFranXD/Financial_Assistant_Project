# MRE Phase 4 — Implementation Spec & Session Handoff Document
## Version 1.2 — Post zip diagnostic, post ChatGPT v1.0 critique, post Claude v1.1 review

---

## HOW TO USE THIS DOCUMENT

This document is the single source of truth for Phase 4 implementation.
If a session limit is reached, give this file to a new Claude instance and say:
"Phase 4 implementation is in progress. The last completed section was [SECTION NAME].
Please verify that section is done by checking the files listed, then continue from the next section."

The new Claude must verify the prior section before continuing — not assume it is done.

---

## SECTION COMPLETION CHECKLIST

- [ ] SECTION 1 — Demolition (validator retirement)
- [ ] SECTION 2 — Schema additions (Sub6 new fields + Sheets duplicate guard)
- [ ] SECTION 3 — Standards engine (calibration/financial_standards.py + calibration/calibration_config.py)
- [ ] SECTION 4 — Gate integration (live_engine.py reads from standards engine)
- [ ] SECTION 5 — Calibration analyzer (calibration/calibration_analyzer.py)
- [ ] SECTION 6 — Audit log (calibration/log_decision.py + standards_history.log)

---

## PART 1 — CONTEXT

### What MRE is
Automated stock research pipeline. Python 3.11, GitHub Actions, GitHub Pages, Google Sheets.
Zero paid APIs, zero ML, zero trading logic. Paper trades only.
Runs 4x/weekday ET: ~9:45, 11:45, 13:45, 16:00.

### Key architecture rules (locked, never violate)
- eq_schema.py = single source of truth for shared keys
- dashboard_builder.py = single source of truth for all dashboard HTML
- main.py = 32-step pipeline orchestrator
- price_structure_schema.py = Sub4 contract
- paper_trading_schema.py = Sub6 contract
- Git: git add -A with stash/pop wrapping pulls
- No ML, no paid APIs, no auto-updates to financial standards

### What Phase 4 is
Financial Standards Calibration Engine. Problem: zero trades since system creation.
Cause: the trade opening gate in live_engine.py requires entry_quality == 'GOOD' only,
and no candidate has met that threshold. Phase 4 loosens this gate to also allow MODERATE,
collects trade evidence under broad-but-safe initial standards, then uses a human-in-the-loop
analysis module to derive evidence-based standards from real trade outcomes.

### Approved design summary
- financial_standards.py = new centralized standards config, read by pipeline decision gates
- calibration_config.py = analyzer behavior constants (separate from trading gates)
- Trade opening gate loosened: GOOD or MODERATE entry_quality accepted (was GOOD only)
- Analysis module reads closed trade history, produces recommendation reports
- No standard changes without explicit human approval
- FSV (validator/) retired entirely — it was human-review only, never consulted by pipeline
- Three new fields added to Sub6 schema: sector, move_extension_pct, standards_version
- Google Sheets: one spreadsheet, multiple tabs (auto-created on first access)
- Local standards_history.log = primary audit record. Sheets = convenience copy.

### Critical facts confirmed from zip diagnostic
1. FSV is confirmed 100% non-blocking. Entire validator/ folder is safe to retire.
2. The trade opening gate in live_engine.py lines 196–201 requires entry_quality == 'GOOD'.
   This is the primary reason zero trades occurred. Phase 4 loosens this to also allow MODERATE.
3. COMPOSITE_CONFIDENCE_MIN = 35 in config.py is already broad. Do not touch it.
4. market_verdict thresholds (70/55 in main.py) are scoring display logic. Do not touch them.
5. candidate_filter.py gates are company quality filters. Not Phase 4 targets. Do not touch.
6. PS_MOVE_EXTENSION_PCT = 'move_extension_pct'. It is set on candidate dicts via
   candidate[PS_MOVE_EXTENSION_PCT] in main.py Sub4 blocks. Safe to read as 'move_extension_pct'.
7. 'sector' is set directly on candidate dicts in main.py (lines 518, 1263). Safe to read.
8. PT_COMPOSITE_SCORE = "composite_score". trade_builder writes:
     base[PT_COMPOSITE_SCORE] = candidate.get('composite_confidence')
   read_all_trades() returns dicts keyed by SHEET_COLUMNS values, so the key in
   trade records from Sheets is "composite_score" — not "composite_confidence".
   The analyzer reads from Sheets records and must use "composite_score". This is correct.
9. PT_LIVE_PNL_PCT = "live_pnl_pct". Confirmed present on closed trade records.
   The analyzer correctly uses t.get('live_pnl_pct').
10. PT_SCHEMA_VERSION is written to each trade row as the 'version' column value.
    It is never validated on read — no code checks row['version'] != PT_SCHEMA_VERSION.
    Incrementing PT_SCHEMA_VERSION to 3 is safe and does NOT break existing rows.
11. PT_TRADE_ID = "trade_id". It is SHEET_COLUMNS[0] — column 1 (1-based) in Sheets.
    col_values(1) correctly reads trade_id. This assumption must be preserved.
12. 'alignment' is ONLY set by _enrich_for_dashboard() in main.py.
    In the live pipeline path, _enrich_for_dashboard() is called at Step 27m,
    AFTER run_paper_trading() at Step 27k. This means alignment is NOT set on
    candidates when the trade gate runs. The gate must NOT check alignment.
    See Section 4 for the correct gate design.

### Scoring vocabulary (locked)
- Market verdict: RESEARCH NOW / WATCH / SKIP
- EQ verdict: SUPPORTIVE / NEUTRAL / WEAK / RISKY / UNAVAILABLE
- Entry quality: GOOD / MODERATE / WEAK / EXTENDED
- Rotation signal: SUPPORT / WAIT / WEAKEN / UNKNOWN
- Alignment: ALIGNED / PARTIAL / CONFLICT

---

## PART 2 — CRITIQUE LOG (v1.0 → v1.1 → v1.2)

This section records every critique decision so the implementation agent
understands why the spec is written the way it is.

### ChatGPT v1.0 critique — decisions

**C1: composite_score vs composite_confidence in analyzer**
ChatGPT said: change composite_score → composite_confidence in analyzer BUCKETS.
Decision: REJECT ChatGPT. The analyzer reads Sheets records (keyed by composite_score).
composite_confidence is the candidate dict key, not the Sheets key. composite_score is correct.

**C2: Duplicate guard performance — col_values(1) instead of read_all_trades()**
Decision: ACCEPT. v1.1 implemented correctly. Assumption noted: trade_id must stay column 1.

**C3: Google Sheets as primary audit source — local log only on Sheets success**
ChatGPT said: write local log only if Sheets succeeds (Sheets = authority).
Decision: REJECT ChatGPT. Local .log file committed to repo is more durable than Sheets.
Free-tier Sheets has real failure modes (credential expiry, quota, API outage).
Audit logs exist precisely for when systems fail. Correct behavior: always write local
log, attempt Sheets, warn on failure. v1.2 restores this behavior.

**C4: Auto-create Sheets tabs**
Decision: ACCEPT. v1.1 implemented correctly via _get_or_create_tab(). Kept in v1.2.

**C5: Separate calibration_config.py from financial_standards.py**
Decision: ACCEPT. v1.1 implemented correctly. Kept in v1.2.

### ChatGPT v1.0 critique — issues that v1.1 left unresolved

**U1: Safe parse on risk_reward_ratio**
v1.1 still writes: _rr_ok = (_rr is not None and float(_rr) >= MIN_RR_FOR_ENTRY)
If _rr is "" or "N/A" this raises ValueError and can crash the loop.
v1.2 fix: wrap in try/except.

**U2: MAX_MOVE_EXTENSION_PCT is dead config**
v1.1 defines it but the gate never checks it. v1.2 adds the gate check with None as no-op.
This means the constant is active from day one and will work when set to a real value later.

### New issues found from zip (not in any prior critique)

**N1: alignment gate would silently block all trades in live path**
In main.py live path: run_paper_trading() runs at Step 27k (line ~1645).
_enrich_for_dashboard() runs at Step 27m (line ~1709), which is AFTER.
alignment is only set inside _enrich_for_dashboard(). Therefore alignment = ''
on every candidate when the gate runs. '' is not in ALLOWED_ALIGNMENTS,
so every candidate fails the gate silently. Zero trades would still occur.
v1.2 fix: remove alignment from the gate entirely. It is a display enrichment
field, not a scoring field. Alignment is derived from scores that are already
gated individually (verdict, entry_quality, composite_confidence). Gating on
alignment at the trade entry layer is redundant and cannot work given the execution order.

---

## PART 3 — IMPLEMENTATION SECTIONS

---

## SECTION 1 — DEMOLITION

Goal: Retire the entire FSV system.

Verify validator/ exists with:
  validator/__init__.py
  validator/validator_schema.py
  validator/financial_standards.py
  validator/standards_range.py
  validator/standards_contradiction.py
  validator/standards_expectation.py

### 1A — Remove FSV call block from main.py (debug path)

Search for:
  # ── FSV: Financial Standards Validator (debug path, non-fatal) ──

Delete from that comment through the closing comment:
  # ── End FSV (debug) ──

### 1B — Remove FSV call block from main.py (live path)

Search for (around Step 27l):
  # ── Step 27l: Financial Standards Validator (non-fatal diagnostic) ────────

Delete that entire block through:
  # ── End Step 27l ──────────────────────────────────────────────────────────

### 1C — Remove _validator rendering from dashboard_builder.py

Search dashboard_builder.py for references to:
  _validator, validator_version, ticker_verdict, buckets_executed,
  inconsistent_count, partial_execution

Remove FSV rendering blocks referencing these keys. Leave any non-FSV uses
of CLEAN/REVIEW/CRITICAL alone if they exist in other contexts.

### 1D — Delete validator/ folder

  rm -rf validator/

Run from project root after 1A–1C are verified.

### 1E — Verify

  grep -rn "from validator\|import validator\|_validator\|validate_candidate" . --include="*.py"

Expected: zero results.

---

## SECTION 2 — SCHEMA ADDITIONS

Goal: Add three missing fields to Sub6 trade records, add duplicate guard.

### 2A — Add three fields to contracts/paper_trading_schema.py

Step 1: Add after PT_IS_TEST = "is_test":
  PT_SECTOR              = "sector"
  PT_MOVE_EXTENSION_PCT  = "move_extension_pct"
  PT_STANDARDS_VERSION   = "standards_version"

Step 2: Add to SHEET_COLUMNS tail (after PT_IS_TEST):
  PT_SECTOR, PT_MOVE_EXTENSION_PCT, PT_STANDARDS_VERSION

Step 3: Add to PT_SAFE_DEFAULTS:
  PT_SECTOR:             "",
  PT_MOVE_EXTENSION_PCT: None,
  PT_STANDARDS_VERSION:  "",

Step 4: Add PT_MOVE_EXTENSION_PCT to PT_FLOAT_FIELDS list.

Step 5: Increment PT_SCHEMA_VERSION from 2 to 3.
  Confirmed safe: PT_VERSION field is written to each row as a value but is
  never validated on read. No code compares row['version'] to PT_SCHEMA_VERSION.
  Existing rows will simply show "2" in the version column — that is correct and expected.

### 2B — Update paper_trading/trade_builder.py

Step 1: Add to imports:
  from contracts.paper_trading_schema import (
      ...existing...,
      PT_SECTOR, PT_MOVE_EXTENSION_PCT, PT_STANDARDS_VERSION,
  )

Step 2: Add after base[PT_IS_TEST] = is_test inside build_trade():
  base[PT_SECTOR]             = candidate.get('sector', '')
  base[PT_MOVE_EXTENSION_PCT] = candidate.get('move_extension_pct')
  base[PT_STANDARDS_VERSION]  = _get_standards_version()

Step 3: Add module-level helper:
  def _get_standards_version() -> str:
      try:
          from calibration.financial_standards import STANDARDS_VERSION
          return STANDARDS_VERSION
      except Exception:
          return "UNKNOWN"

### 2C — Add duplicate guard to paper_trading/sheets_ledger.py

Add at the start of write_rows(), after "if sheet is None or not rows: return False":

  # Duplicate guard: read only trade_id column (col 1) for performance.
  # trade_id is SHEET_COLUMNS[0] — if schema changes move it, update col index here.
  # Guards against GitHub Actions retry double-fire.
  try:
      existing_ids = set(sheet.col_values(1)[1:])  # skip header row
      rows = [r for r in rows if str(r.get('trade_id', '')) not in existing_ids]
      if not rows:
          log.info('write_rows: all rows already exist (duplicate guard) — skipping write')
          return True
  except Exception as e:
      log.warning(f'write_rows: duplicate guard failed, proceeding without it: {e}')

Note: rows use string key 'trade_id' (PT_TRADE_ID = "trade_id"), which matches
how trade dicts are built in trade_builder.py. col_values(1) returns strings from
Sheets, and str(r.get('trade_id', '')) ensures consistent type comparison.

### 2D — Sheets tab setup

Tabs are auto-created on first access by Section 5 and Section 6.
No manual UI action needed.

### 2E — Verify

  python3 -c "
  from contracts.paper_trading_schema import SHEET_COLUMNS, PT_SCHEMA_VERSION
  print('Schema version:', PT_SCHEMA_VERSION)
  for f in ['sector', 'move_extension_pct', 'standards_version']:
      print(f, 'in schema:', f in SHEET_COLUMNS)
  "
Expected: version 3, all three True.

---

## SECTION 3 — STANDARDS ENGINE

Goal: Build two files.
  calibration/financial_standards.py — trading gate thresholds (read by pipeline)
  calibration/calibration_config.py  — analyzer behavior constants (read by analyzer only)

### 3A — Create calibration/ directory

  mkdir -p calibration
  touch calibration/__init__.py

### 3B — Create calibration/financial_standards.py

"""
calibration/financial_standards.py
Financial Standards Engine — single source of truth for all TRADE DECISION thresholds.

Read by live_engine.py to make trade opening decisions.
NOT read by the calibration analyzer for its own behavior — see calibration_config.py.

Standards are NOT auto-updated. All changes require human approval and must be logged
in calibration/standards_history.log BEFORE this file is modified.

STANDARDS_VERSION must be incremented every time any threshold value changes.
"""

STANDARDS_VERSION = "v1.0"

# Which entry_quality labels are accepted for trade opening.
# Phase 4A: GOOD and MODERATE. WEAK and EXTENDED always rejected.
ALLOWED_ENTRY_QUALITIES = {"GOOD", "MODERATE"}

# Minimum composite_confidence for trade opening.
# Must always be >= COMPOSITE_CONFIDENCE_MIN in config.py (= 35).
# Phase 4A: 45
CONFIDENCE_FLOOR = 45

# Minimum risk_reward_ratio for trade opening.
# Phase 4A: 1.5
MIN_RR_FOR_ENTRY = 1.5

# Maximum move_extension_pct accepted for trade opening.
# Phase 4A: None (no cap — derive from evidence).
# Set to a float to activate. Gate checks this in live_engine.py.
MAX_MOVE_EXTENSION_PCT = None

### 3C — Create calibration/calibration_config.py

"""
calibration/calibration_config.py
Calibration analyzer behavior constants.

These govern how calibration_analyzer.py behaves.
They are NOT trading gate thresholds. See financial_standards.py for those.
Changing these is treated the same as changing a financial standard:
log the change in standards_history.log with reasoning before modifying.
"""

BUCKET_MIN_SAMPLE             = 10
SIGNIFICANCE_EXPECTANCY_DELTA = 0.10
SIGNIFICANCE_WINRATE_DELTA    = 10

CYCLE_MIN_NEW_TRADES          = 10
CYCLE_MIN_OBSERVATION_DAYS    = 7

EXPLORATORY_ANALYSIS_MIN      = 30
RECOMMENDATION_MIN            = 50
PREFERRED_CALIBRATION_MIN     = 75

CHOKE_DROP_THRESHOLD          = 0.50

CONVERGENCE_MAX_DELTA         = 0.05
CONVERGENCE_CONSECUTIVE_CYCLES = 3

SHEET_TAB_STANDARDS_HISTORY   = "standards_history"
SHEET_TAB_CALIBRATION_REPORTS = "calibration_reports"

STANDARDS_HISTORY_HEADERS = [
    "timestamp", "cycle_number", "metric", "old_value", "new_value",
    "recommendation", "simulation_summary", "decision", "reasoning"
]

CALIBRATION_REPORTS_HEADERS = [
    "report_timestamp", "cycle_number", "tier_active", "total_closed_trades",
    "overall_expectancy", "overall_win_rate", "choke_warning",
    "recommendations_count", "report_text"
]

### 3D — Verify

  python3 -c "
  from calibration.financial_standards import STANDARDS_VERSION, ALLOWED_ENTRY_QUALITIES, CONFIDENCE_FLOOR, MIN_RR_FOR_ENTRY, MAX_MOVE_EXTENSION_PCT
  from calibration.calibration_config import BUCKET_MIN_SAMPLE, RECOMMENDATION_MIN
  print(STANDARDS_VERSION, ALLOWED_ENTRY_QUALITIES, CONFIDENCE_FLOOR, MIN_RR_FOR_ENTRY, MAX_MOVE_EXTENSION_PCT)
  print(BUCKET_MIN_SAMPLE, RECOMMENDATION_MIN)
  "
Expected: v1.0 {'GOOD','MODERATE'} 45 1.5 None  and  10 50

---

## SECTION 4 — GATE INTEGRATION

Goal: Modify live_engine.py so the trade opening gate reads from financial_standards.py.
This is the ONLY pipeline file that changes in Phase 4.

CRITICAL: The gate does NOT check alignment.
Reason: _enrich_for_dashboard() sets alignment AFTER run_paper_trading() runs in the
live pipeline path (Step 27m comes after Step 27k). alignment is '' on all candidates
at gate time. Checking alignment would silently block every trade.
Alignment is a display enrichment field derived from scores already checked individually
(verdict, entry_quality, composite_confidence). Removing it from the gate loses nothing.

### 4A — Add import to paper_trading/live_engine.py

After existing imports:
  from calibration.financial_standards import (
      ALLOWED_ENTRY_QUALITIES,
      CONFIDENCE_FLOOR,
      MIN_RR_FOR_ENTRY,
      MAX_MOVE_EXTENSION_PCT,
  )

### 4B — Replace the trade opening gate (lines 196–201)

Current code:
  if not (candidate.get('market_verdict') in ('RESEARCH NOW', 'WATCH')
          and candidate.get('entry_quality') == 'GOOD'
          and candidate.get('entry_price') is not None
          and candidate.get('stop_loss') is not None
          and candidate.get('price_target') is not None):
      continue

Replace with:
  # ── Trade opening gate — reads from calibration/financial_standards.py ──
  _eq      = candidate.get('entry_quality', '')
  _conf    = candidate.get('composite_confidence') or 0
  _rr_raw  = candidate.get('risk_reward_ratio')
  _verdict = candidate.get('market_verdict', '')
  _move_ext = candidate.get('move_extension_pct')
  _has_lvls = (
      candidate.get('entry_price') is not None
      and candidate.get('stop_loss') is not None
      and candidate.get('price_target') is not None
  )

  try:
      _rr_val = float(_rr_raw) if _rr_raw is not None else None
  except (TypeError, ValueError):
      _rr_val = None
  _rr_ok = (_rr_val is not None and _rr_val >= MIN_RR_FOR_ENTRY)

  _move_ok = True
  if MAX_MOVE_EXTENSION_PCT is not None:
      try:
          _move_ok = (_move_ext is not None and float(_move_ext) <= MAX_MOVE_EXTENSION_PCT)
      except (TypeError, ValueError):
          _move_ok = False

  if not (
      _verdict in ('RESEARCH NOW', 'WATCH')
      and _eq in ALLOWED_ENTRY_QUALITIES
      and _conf >= CONFIDENCE_FLOOR
      and _rr_ok
      and _move_ok
      and _has_lvls
  ):
      log.info(
          f'[PT] {candidate.get("ticker","?")}: gate fail -- '
          f'verdict={_verdict} eq={_eq} conf={_conf} rr={_rr_raw} '
          f'move_ext={_move_ext} levels={_has_lvls}'
      )
      continue

Notes on this gate:
- alignment is intentionally excluded (see CRITICAL note above)
- _rr_raw is logged (not _rr_val) so the raw value is visible in logs for debugging
- MAX_MOVE_EXTENSION_PCT = None is a no-op; setting it to a float activates the cap
- The gate fail log line is the primary Phase 4A diagnostic signal

### 4C — Verify

  python3 -c "from paper_trading.live_engine import run_paper_trading; print('ok')"
  grep -n "gate fail" paper_trading/live_engine.py

Expected: ok and one matching line.

---

## SECTION 5 — CALIBRATION ANALYZER

Goal: Build calibration/calibration_analyzer.py.
Standalone script, never imported by main.py.
Reads closed trades from Sheets, runs bucket analysis, generates report.
Auto-creates Sheets tabs if missing. Never modifies financial_standards.py.

Run: python3 -m calibration.calibration_analyzer

Field name notes:
  - Analyzer reads Sheets records. Keys come from SHEET_COLUMNS string values.
  - composite_score is correct (PT_COMPOSITE_SCORE = "composite_score")
    trade_builder writes: base[PT_COMPOSITE_SCORE] = candidate.get('composite_confidence')
    Do NOT use "composite_confidence" in the analyzer — it will always be None.
  - live_pnl_pct is correct (PT_LIVE_PNL_PCT = "live_pnl_pct")

### 5A — Create calibration/calibration_analyzer.py

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

### 5B — Verify

  python3 -c "from calibration.calibration_analyzer import run_analysis; print('import ok')"

Expected: import ok

---

## SECTION 6 — AUDIT LOG

Goal: Build calibration/log_decision.py and calibration/standards_history.log.

Audit log priority:
  Local calibration/standards_history.log = PRIMARY (always written, committed to repo)
  Google Sheets standards_history tab = SECONDARY (convenience copy, written after local)
  Rationale: audit logs exist for when systems fail. Sheets can fail (credential expiry,
  API quota, outage). Local file committed to git is the more durable record.

### 6A — Create calibration/log_decision.py

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

### 6B — Initialize standards_history.log

  mkdir -p calibration

  cat >> calibration/standards_history.log << 'EOF'

[Phase 4A -- v1.0 initial standards]
All values are broad Phase 4A starting points, not evidence-derived.
ALLOWED_ENTRY_QUALITIES: GOOD, MODERATE
CONFIDENCE_FLOOR: 45
MIN_RR_FOR_ENTRY: 1.5
MAX_MOVE_EXTENSION_PCT: None (no cap)
alignment: removed from gate (set after live_engine runs in pipeline)
Phase 4A data collection begins.
----------------------------------------
EOF

### 6C — Gitignore check

Confirm .gitignore does NOT exclude calibration/standards_history.log.
If *.log is globally excluded, add:
  !calibration/standards_history.log

---

## PART 4 — POST-IMPLEMENTATION VERIFICATION

Run after all 6 sections are complete:

  # 1. No FSV references remain
  grep -rn "from validator\|import validator\|_validator\|validate_candidate" . --include="*.py"
  # Expected: zero results

  # 2. Schema correct
  python3 -c "
  from contracts.paper_trading_schema import SHEET_COLUMNS, PT_SCHEMA_VERSION
  print('Version:', PT_SCHEMA_VERSION)
  for f in ['sector', 'move_extension_pct', 'standards_version']:
      print(f, ':', f in SHEET_COLUMNS)
  "
  # Expected: 3, all True

  # 3. Standards and config importable
  python3 -c "
  from calibration.financial_standards import STANDARDS_VERSION, ALLOWED_ENTRY_QUALITIES, CONFIDENCE_FLOOR, MIN_RR_FOR_ENTRY
  from calibration.calibration_config import BUCKET_MIN_SAMPLE, RECOMMENDATION_MIN
  print(STANDARDS_VERSION, ALLOWED_ENTRY_QUALITIES, CONFIDENCE_FLOOR, MIN_RR_FOR_ENTRY)
  print(BUCKET_MIN_SAMPLE, RECOMMENDATION_MIN)
  "
  # Expected: v1.0 {'GOOD','MODERATE'} 45 1.5  and  10 50

  # 4. Live engine clean
  python3 -c "from paper_trading.live_engine import run_paper_trading; print('ok')"
  grep -n "gate fail" paper_trading/live_engine.py
  # Expected: ok + one result

  # 5. Analyzer clean
  python3 -c "from calibration.calibration_analyzer import run_analysis; print('ok')"
  # Expected: ok

  # 6. Log decision importable
  python3 -c "import calibration.log_decision; print('ok')"
  # Expected: ok

---

## PART 5 — PHASE 4A OPERATING INSTRUCTIONS

Phase 4A begins automatically on the next GitHub Actions run after implementation.

Monitor:
- GitHub Actions logs: search for [PT] ticker: gate fail
  If all fail on conf < 45 → lower CONFIDENCE_FLOOR in financial_standards.py
  If all fail on rr → lower MIN_RR_FOR_ENTRY
  Always log the change with python3 -m calibration.log_decision first.
- Google Sheets trades tab: watch for OPEN rows appearing.
- Do not change any threshold without gate fail log evidence.

When to run the analyzer:
- 30+ CLOSED rows in trades tab → exploratory run (orientation only)
- 50+ CLOSED rows → first recommendation run
- Run: python3 -m calibration.calibration_analyzer

Standards version discipline — every change to financial_standards.py requires:
  1. python3 -m calibration.log_decision first (writes local log + Sheets)
  2. Local log write confirmed
  3. Update financial_standards.py
  4. Increment STANDARDS_VERSION

Convergence definition (for reference):
  Standards are considered converged when across three consecutive valid calibration cycles:
  - No recommended change exceeds CONVERGENCE_MAX_DELTA (0.05) in any metric
  - Overall expectancy stable or improving
  - No choke warning active
  Phase 4 is complete when converged AND at least 50 closed trades exist.