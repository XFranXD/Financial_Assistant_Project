TASK
────
Implement the Expectations vs Reality analyzer (Phase 2B, Phase A) for the
FINANCIAL_ASSISTANT_CORE stock research engine. This phase creates one new
file and appends to one schema contract. Zero integration work happens in
this phase — main.py, report_builder.py, and dashboard_builder.py are NOT
touched here.

═══════════════════════════════════════════════════════════════════════════
ABSOLUTE DO-NOT-MODIFY LIST — these files must not be opened or changed:
  main.py
  reports/report_builder.py
  reports/dashboard_builder.py
  analyzers/opportunity_model.py
  eq_analyzer/event_risk.py
  eq_analyzer/insider_activity.py
  Any file not explicitly listed in DELIVERABLES below.
═══════════════════════════════════════════════════════════════════════════

───────────────────────────────────────────────────────────────────────────
BACKGROUND
───────────────────────────────────────────────────────────────────────────
The engine is a fully automated Python 3.11 stock research pipeline running
on GitHub Actions. Sub1 fetches fundamentals per ticker via yfinance and
stores them in a candidate dict. Phase 1 (1A/1B/1C) enriched each candidate
with event risk, insider activity, and price structure fields. Phase 2B adds
a per-ticker "Expectations vs Reality" signal using Finnhub historical EPS
data and already-available Sub1 fields.

───────────────────────────────────────────────────────────────────────────
DELIVERABLE 1 — analyzers/expectations.py  (CREATE NEW FILE)
───────────────────────────────────────────────────────────────────────────
Create this file from scratch. Do not place it in eq_analyzer/ — it belongs
in analyzers/.

MODULE DOCSTRING must read exactly:
"""
analyzers/expectations.py
Computes the Expectations vs Reality signal for a single ticker.
Uses Finnhub historical EPS data and Sub1-provided fundamentals.
Non-fatal — returns UNAVAILABLE on any error or missing data.
"""

IMPORTS (only these, in this order):
  import requests
  import logging
  from utils.logger import get_logger

  log = get_logger('expectations')

──── FUNCTION: get_expectations_signal ────

Signature:
  def get_expectations_signal(
      ticker:        str,
      finnhub_token: str,
      pe_ratio:      float | None,
      eps_quarterly: list,
  ) -> dict:

Docstring:
  """
  Computes expectations signal from two components:
    Component 1 — Earnings surprise streak (Finnhub /stock/earnings)
    Component 2 — Bounded PEG ratio (pe_ratio / eps_growth_rate)

  Args:
      ticker:        stock ticker symbol
      finnhub_token: Finnhub API token string (may be empty string)
      pe_ratio:      trailing P/E from Sub1 financial_parser (may be None)
      eps_quarterly: list of up to 8 quarterly EPS floats, most recent first,
                     from Sub1 financial_parser (may be empty list)

  Returns:
      {
          'expectations_signal': 'BEATING' | 'INLINE' | 'MISSING' | 'UNAVAILABLE',
          'earnings_beat_rate':  float | None,   e.g. 0.75 = beat 3 of 4
          'peg_ratio':           float | None,
      }
  On any exception: returns UNAVAILABLE dict. Never raises.
  """

DEFAULT RETURN VALUE — define this at the top of the function body,
before the outer try block:
  _default = {
      'expectations_signal': 'UNAVAILABLE',
      'earnings_beat_rate':  None,
      'peg_ratio':           None,
  }

──── COMPONENT 1: Earnings surprise streak ────

Fetch the last 4 quarters of EPS actual vs estimate from Finnhub using
this exact URL pattern:
  https://finnhub.io/api/v1/stock/earnings?symbol={ticker}&token={finnhub_token}

HTTP behavior:
- Use requests.get(url, timeout=10)
- If finnhub_token is empty string or None:
    beat_score = 0
    beat_rate  = None
    log at INFO: f'[EXP] {ticker}: no Finnhub token — skipping beat streak'
    Skip the HTTP request entirely.
- If resp.ok is False:
    beat_score = 0
    beat_rate  = None
    log at INFO: f'[EXP] {ticker}: Finnhub returned HTTP {resp.status_code}'
- If the request raises any exception (catch separately inside Component 1):
    beat_score = 0
    beat_rate  = None
    log at INFO: f'[EXP] {ticker}: Finnhub request failed — {e}'

Parsing the response:
- The endpoint returns a JSON list directly (not wrapped in a key).
  Each element is a dict with keys 'actual' and 'estimate'
  (both numeric or null).
- Take only the first 4 elements of the list (most recent 4 quarters).
- For each element: collect it as a "valid quarter" only if both 'actual'
  and 'estimate' are not None. Count how many valid quarters beat:
  a quarter is a beat if actual > estimate.
- MINIMUM SAMPLE RULE: If the count of valid quarters is less than 2,
  set beat_rate = None and beat_score = 0 and do not proceed further
  with Component 1 scoring.
- Otherwise:
    beat_count = number of valid quarters where actual > estimate
    beat_rate  = beat_count / len(valid_quarters)

beat_score mapping (only reached if valid_quarters >= 2):
  beat_count 3 or 4  → beat_score = +1
  beat_count 2       → beat_score =  0
  beat_count 0 or 1  → beat_score = -1

──── COMPONENT 2: Bounded PEG ratio ────

Inputs: pe_ratio (from function arg), eps_quarterly (from function arg).

Step 1 — compute eps_growth_rate from eps_quarterly:
  The list contains up to 8 floats, most recent first.
  recent = sum of eps_quarterly[0:4]   (TTM — last 4 quarters)
  older  = sum of eps_quarterly[1:5]   (prior 4 quarters, offset by 1)
  If len(eps_quarterly) < 5:
      eps_growth_rate = None
  Else if older == 0:
      eps_growth_rate = None
  Otherwise:
      eps_growth_rate = ((recent - older) / abs(older)) * 100
      (result is a percentage, e.g. 15.0 means 15% YoY growth)

Step 2 — score the PEG with these exact rules applied in this exact order:

  Rule A — Missing data (not enough history or zero denominator):
      If eps_growth_rate is None:
          peg_score     = 0        ← neutral, not penalized
          peg_ratio_val = None

  Rule B — Negative or zero growth (bad fundamental signal):
      Else if eps_growth_rate <= 0:
          peg_score     = -1
          peg_ratio_val = None

  Rule C — PE unavailable (growth is positive but can't compute ratio):
      Else if pe_ratio is None:
          peg_score     = 0
          peg_ratio_val = None

  Rule D — Compute bounded PEG:
      Else:
          capped_growth = min(eps_growth_rate, 50.0)
          peg_ratio_val = round(pe_ratio / capped_growth, 2)
          if peg_ratio_val <= 1.5:  peg_score = +1
          if peg_ratio_val <= 3.0:  peg_score =  0   (covers 1.5 < PEG <= 3.0)
          if peg_ratio_val >  3.0:  peg_score = -1

The 50.0 cap prevents a hypergrowth stock with 200% EPS growth from
producing an artificially low PEG that scores +1 unfairly.

──── COMBINED SIGNAL ────

combined_score = beat_score + peg_score

Signal mapping — apply in this order:
  If combined_score == +2:          signal = 'BEATING'
  If combined_score == +1 or 0:     signal = 'INLINE'
  If combined_score == -1 or -2:    signal = 'MISSING'

UNAVAILABLE override — apply after the above mapping:
  If beat_rate is None AND peg_ratio_val is None:
      signal = 'UNAVAILABLE'
  This override fires when both components returned no usable numeric output.
  If either component produced a numeric value (beat_rate or peg_ratio_val),
  the signal stays BEATING/INLINE/MISSING regardless.

Return:
  {
      'expectations_signal': signal,
      'earnings_beat_rate':  round(beat_rate, 2) if beat_rate is not None else None,
      'peg_ratio':           peg_ratio_val,
  }

──── ERROR HANDLING ────

The entire function body after _default definition must be wrapped in a
single outer try/except block:
  except Exception as e:
      log.warning(f'[EXP] {ticker}: unexpected error — {e}')
      return _default

Component 1's HTTP request must have its own inner try/except inside
Component 1 (not the outer one) so a Finnhub failure does not abort
Component 2.

All log statements must include [EXP] and the ticker as shown above.

───────────────────────────────────────────────────────────────────────────
DELIVERABLE 2 — contracts/eq_schema.py  (APPEND ONLY)
───────────────────────────────────────────────────────────────────────────
DO NOT modify any existing line. Append these lines at the very end of the
file, after the last existing constant (REGIME_VIX):

# ── Expectations vs Reality (2B) — per-ticker ────────────────────────────
EXPECTATIONS_SIGNAL  = 'expectations_signal'  # 'BEATING' | 'INLINE' | 'MISSING' | 'UNAVAILABLE'
EARNINGS_BEAT_RATE   = 'earnings_beat_rate'    # float | None — e.g. 0.75 = beat 3 of 4
PEG_RATIO            = 'peg_ratio'             # float | None

Verify the last existing line before appending:
  REGIME_VIX = 'regime_vix'  # float | None — VIX value at run time
Append immediately after it with one blank line separator.

───────────────────────────────────────────────────────────────────────────
F-STRING SAFETY RULE
───────────────────────────────────────────────────────────────────────────
Python 3.11 prohibits backslash characters inside f-string expression braces.
Assign computed values to plain variables BEFORE any f-string and reference
those variables inside the braces.

BAD  (raises SyntaxError in Python 3.11):
  log.info(f"val={x if x is not None else 'N/A'}")
GOOD:
  _display = x if x is not None else 'N/A'
  log.info(f"val={_display}")

───────────────────────────────────────────────────────────────────────────
VALIDATION — run all steps before declaring done
───────────────────────────────────────────────────────────────────────────

Step 1 — Syntax check:
  python3 -m py_compile analyzers/expectations.py && echo OK
  python3 -m py_compile contracts/eq_schema.py && echo OK

Step 2 — Import check:
  python3 -c "from analyzers.expectations import get_expectations_signal; print('import OK')"
  python3 -c "from contracts.eq_schema import EXPECTATIONS_SIGNAL, EARNINGS_BEAT_RATE, PEG_RATIO; print('schema OK')"

Step 3 — Schema append check:
  Confirm the last 5 lines of contracts/eq_schema.py contain exactly:
    REGIME_VIX
    (blank line)
    # ── Expectations vs Reality (2B) — per-ticker
    EXPECTATIONS_SIGNAL
    EARNINGS_BEAT_RATE
    PEG_RATIO

Step 4 — Logic boundary tests (run this script verbatim):

  python3 - <<'EOF'
  import sys
  sys.path.insert(0, '.')
  from analyzers.expectations import get_expectations_signal

  # Test A: no token, no PE, no EPS → UNAVAILABLE
  r = get_expectations_signal('TEST', '', None, [])
  assert r['expectations_signal'] == 'UNAVAILABLE', f"A failed: {r}"

  # Test B: no token, good PEG (pe=10, eps_growth≈25%) → beat=0, peg=+1 → combined=+1 → INLINE
  r = get_expectations_signal('TEST', '', 10.0, [2.0, 1.5, 1.0, 0.8, 1.6, 1.2, 0.9, 0.7])
  assert r['expectations_signal'] == 'INLINE', f"B failed: {r}"
  assert r['peg_ratio'] is not None, f"B peg_ratio missing: {r}"

  # Test C: no token, negative EPS growth → peg=-1, beat=0 → combined=-1 → MISSING
  r = get_expectations_signal('TEST', '', 15.0, [1.0, 1.5, 1.2, 1.8, 1.1, 1.3, 1.4, 1.6])
  assert r['expectations_signal'] == 'MISSING', f"C failed: {r}"
  assert r['peg_ratio'] is None, f"C peg_ratio should be None: {r}"

  # Test D: no token, PE=None, positive eps_growth → Rule C fires (peg=0, peg_ratio_val=None)
  # beat_rate=None (no token), peg_ratio_val=None → UNAVAILABLE override fires
  r = get_expectations_signal('TEST', '', None, [2.0, 1.5, 1.0, 0.8, 1.6, 1.2, 0.9, 0.7])
  assert r['expectations_signal'] == 'UNAVAILABLE', f"D failed: {r}"

  # Test E: no token, high PEG (pe=100, eps_growth≈25%) → peg=-1, beat=0 → combined=-1 → MISSING
  r = get_expectations_signal('TEST', '', 100.0, [2.0, 1.5, 1.0, 0.8, 1.6, 1.2, 0.9, 0.7])
  assert r['expectations_signal'] == 'MISSING', f"E failed: {r}"

  # Test F: fewer than 5 eps_quarterly entries → eps_growth=None → Rule A (peg=0, peg_ratio_val=None)
  # beat_rate=None (no token) → UNAVAILABLE override fires
  r = get_expectations_signal('TEST', '', 10.0, [1.0, 1.2, 1.1])
  assert r['expectations_signal'] == 'UNAVAILABLE', f"F failed: {r}"

  # Test G: hypergrowth cap — pe=10, raw_growth≈500% capped at 50% → PEG=0.2 → peg=+1
  # beat=0 (no token), peg_ratio_val=0.2 (not None) → override does NOT fire → INLINE
  r = get_expectations_signal('TEST', '', 10.0, [6.0, 1.0, 0.5, 0.5, 1.0, 0.9, 0.8, 0.7])
  assert r['expectations_signal'] == 'INLINE', f"G failed: {r}"
  assert r['peg_ratio'] is not None and r['peg_ratio'] < 1.5, f"G peg should be capped low: {r}"

  # Test H: no token, eps_growth=None (< 5 quarters), pe=None → both None → UNAVAILABLE
  r = get_expectations_signal('TEST', '', None, [1.0, 1.2])
  assert r['expectations_signal'] == 'UNAVAILABLE', f"H failed: {r}"

  # Test I: no token, short eps list → eps_growth=None → Rule A → peg=0, peg_ratio_val=None
  # beat_rate=None → UNAVAILABLE override fires
  r = get_expectations_signal('TEST', '', 10.0, [1.5, 1.2])
  assert r['expectations_signal'] == 'UNAVAILABLE', f"I failed: {r}"

  print('All 9 boundary tests passed.')
  EOF

Step 5 — Confirm DO-NOT-MODIFY files unchanged:
  git diff --name-only
  Expected output: only these two files appear:
    analyzers/expectations.py
    contracts/eq_schema.py
  If main.py, report_builder.py, or dashboard_builder.py appear: STOP and revert.

───────────────────────────────────────────────────────────────────────────
DONE CRITERIA
───────────────────────────────────────────────────────────────────────────
Phase A is complete when:
  ✓ analyzers/expectations.py exists and passes all validation steps
  ✓ contracts/eq_schema.py has the 3 new constants appended at the end
  ✓ All 9 boundary tests pass without modification to the test script
  ✓ git diff shows exactly 2 files changed
  ✓ The pipeline has NOT been run — no report files have been modified