TASK
────
Wire the Expectations vs Reality analyzer (Phase 2B, Phase B) into the
FINANCIAL_ASSISTANT_CORE pipeline. Phase A must be verified complete before
running this prompt. This phase modifies three existing files only:
main.py, reports/report_builder.py, reports/dashboard_builder.py.

═══════════════════════════════════════════════════════════════════════════
ABSOLUTE DO-NOT-MODIFY LIST — these files must not be opened or changed:
  analyzers/expectations.py          (completed in Phase A — read-only now)
  contracts/eq_schema.py             (completed in Phase A — read-only now)
  analyzers/opportunity_model.py
  eq_analyzer/event_risk.py
  eq_analyzer/insider_activity.py
  Any file not explicitly listed in DELIVERABLES below.
═══════════════════════════════════════════════════════════════════════════

───────────────────────────────────────────────────────────────────────────
DUPLICATION GUARD — run this before making any changes
───────────────────────────────────────────────────────────────────────────
Before inserting anything into main.py, run:

  grep -c "Step 27i" main.py

If the result is greater than 0, Step 27i already exists.
DO NOT insert again. Proceed directly to DELIVERABLE 2.

───────────────────────────────────────────────────────────────────────────
DELIVERABLE 1 — main.py  (TWO INSERTIONS — production path + debug path)
───────────────────────────────────────────────────────────────────────────
Insert Step 27i in BOTH the production path and the debug path.
Each insertion is identical in structure but differs in the candidate
list variable name (production uses `final_companies`,
debug uses `all_candidates`).

── PRODUCTION PATH ──

PRIMARY LOCATOR — find this exact line:
    # ── End Step 27h ─────────────────────────────────────────────────────────

FALLBACK LOCATOR (use only if primary is not found exactly):
    Search for the string "Step 27h" in main.py. Locate the comment line
    that ends the Step 27h block (it will be a comment starting with
    "# ── End Step 27h"). Insert immediately after that line.
    If no such line exists at all, STOP and report the missing anchor
    rather than guessing placement.

Insert the following block IMMEDIATELY AFTER the located line,
with one blank line separator:

    # ── Step 27i: Expectations vs Reality enrichment ─────────────────────────
    # Computes per-ticker expectations signal from Finnhub EPS history and
    # Sub1 fundamentals. Non-fatal — defaults to UNAVAILABLE on any error.
    try:
        from analyzers.expectations import get_expectations_signal
        from contracts.eq_schema import EXPECTATIONS_SIGNAL, EARNINGS_BEAT_RATE, PEG_RATIO
        exp_enriched = 0
        for candidate in final_companies:
            t = candidate.get('ticker', '')
            try:
                exp_result = get_expectations_signal(
                    ticker        = t,
                    finnhub_token = finnhub_token,
                    pe_ratio      = candidate.get('pe_ratio'),
                    eps_quarterly = candidate.get('eps_quarterly', []),
                )
                candidate[EXPECTATIONS_SIGNAL] = exp_result.get('expectations_signal', 'UNAVAILABLE')
                candidate[EARNINGS_BEAT_RATE]  = exp_result.get('earnings_beat_rate')
                candidate[PEG_RATIO]           = exp_result.get('peg_ratio')
                exp_enriched += 1
            except Exception as _exp_ticker_err:
                candidate[EXPECTATIONS_SIGNAL] = 'UNAVAILABLE'
                candidate[EARNINGS_BEAT_RATE]  = None
                candidate[PEG_RATIO]           = None
                log.info(f'[EXP] {t}: error — {_exp_ticker_err}')
        log.info(f'[EXP] Expectations enrichment complete. {exp_enriched}/{len(final_companies)} processed')
    except Exception as exp_err:
        log.warning(f'[EXP] Expectations enrichment failed (non-fatal): {exp_err}')
        for candidate in final_companies:
            candidate[EXPECTATIONS_SIGNAL] = 'UNAVAILABLE'
            candidate[EARNINGS_BEAT_RATE]  = None
            candidate[PEG_RATIO]           = None
    # ── End Step 27i ─────────────────────────────────────────────────────────

── DEBUG PATH ──

PRIMARY LOCATOR — find this exact line:
    # ── End Step 27h (Debug) ─────────────────────────────────────────────

FALLBACK LOCATOR (use only if primary is not found exactly):
    Search for the string "Step 27h (Debug)" in main.py. Locate the comment
    line that ends that block. Insert immediately after that line.
    If no such line exists at all, STOP and report the missing anchor.

Insert the following block IMMEDIATELY AFTER the located line,
with one blank line separator:

    # ── Step 27i: Expectations vs Reality enrichment (Debug) ──────────────
    try:
        from analyzers.expectations import get_expectations_signal
        from contracts.eq_schema import EXPECTATIONS_SIGNAL, EARNINGS_BEAT_RATE, PEG_RATIO
        exp_enriched = 0
        for candidate in all_candidates:
            t = candidate.get('ticker', '')
            try:
                exp_result = get_expectations_signal(
                    ticker        = t,
                    finnhub_token = finnhub_token,
                    pe_ratio      = candidate.get('pe_ratio'),
                    eps_quarterly = candidate.get('eps_quarterly', []),
                )
                candidate[EXPECTATIONS_SIGNAL] = exp_result.get('expectations_signal', 'UNAVAILABLE')
                candidate[EARNINGS_BEAT_RATE]  = exp_result.get('earnings_beat_rate')
                candidate[PEG_RATIO]           = exp_result.get('peg_ratio')
                exp_enriched += 1
            except Exception as _exp_ticker_err:
                candidate[EXPECTATIONS_SIGNAL] = 'UNAVAILABLE'
                candidate[EARNINGS_BEAT_RATE]  = None
                candidate[PEG_RATIO]           = None
                log.info(f'[EXP] {t}: error — {_exp_ticker_err}')
        log.info(f'[EXP] Expectations enrichment complete. {exp_enriched}/{len(all_candidates)} processed')
    except Exception as exp_err:
        log.warning(f'[EXP] Expectations enrichment failed (non-fatal): {exp_err}')
        for candidate in all_candidates:
            candidate[EXPECTATIONS_SIGNAL] = 'UNAVAILABLE'
            candidate[EARNINGS_BEAT_RATE]  = None
            candidate[PEG_RATIO]           = None
    # ── End Step 27i (Debug) ─────────────────────────────────────────────

CRITICAL: `finnhub_token` is already defined in Step 27g in both paths.
Do NOT redefine it. Do NOT add a new os.environ.get call for it.

───────────────────────────────────────────────────────────────────────────
DELIVERABLE 2 — reports/report_builder.py  (TWO CHANGES)
───────────────────────────────────────────────────────────────────────────

CHANGE 2A — extend the existing schema import block:

Locate this exact line near the top of the file (it is the last line
of the eq_schema import block):
        INSIDER_SIGNAL, INSIDER_NOTE,
    )

Replace it with:
        INSIDER_SIGNAL, INSIDER_NOTE,
        EXPECTATIONS_SIGNAL, EARNINGS_BEAT_RATE, PEG_RATIO,
    )

Do not rewrite the entire import block. Only the last line before the
closing parenthesis changes.

CHANGE 2B — per-candidate AI prompt block:

Locate this exact block (it is unique in the file):
        f"Insider Activity (1B):\n"
        f"  Signal: {c.get('insider_signal', 'UNAVAILABLE')}\n"
        f"  Note:   {c.get('insider_note', '') or 'None'}\n"
        f"\n"
        f"Combined Reading:\n"

Insert the Expectations section between the blank line after 1B and
the "Combined Reading:" line. The result must read exactly:

        f"Insider Activity (1B):\n"
        f"  Signal: {c.get('insider_signal', 'UNAVAILABLE')}\n"
        f"  Note:   {c.get('insider_note', '') or 'None'}\n"
        f"\n"
        f"Expectations vs Reality (2B):\n"
        f"  Signal:     {c.get('expectations_signal', 'UNAVAILABLE')}\n"
        f"  Beat rate:  {_exp_beat_display}\n"
        f"  PEG ratio:  {_exp_peg_display}\n"
        f"\n"
        f"Combined Reading:\n"

The two display variables must be assigned as plain variables BEFORE
the f-string block that builds candidate_block. Locate the existing
line that assigns `rr_display` (it already follows this pattern) and
add the following four lines immediately after it:

        _exp_beat_raw     = c.get('earnings_beat_rate')
        _exp_beat_display = f'{round(_exp_beat_raw * 100)}%' if _exp_beat_raw is not None else 'N/A'
        _exp_peg_raw      = c.get('peg_ratio')
        _exp_peg_display  = str(_exp_peg_raw) if _exp_peg_raw is not None else 'N/A'

───────────────────────────────────────────────────────────────────────────
DELIVERABLE 3 — reports/dashboard_builder.py  (THREE CHANGES)
───────────────────────────────────────────────────────────────────────────

CHANGE 3A — per-company dict:

Locate this exact block (it is unique in the file):
                'insider_signal':      c.get('insider_signal',    'UNAVAILABLE'),
                'insider_note':        c.get('insider_note',      ''),

Add the following three lines immediately after `insider_note`:
                'expectations_signal': c.get('expectations_signal', 'UNAVAILABLE'),
                'earnings_beat_rate':  c.get('earnings_beat_rate'),
                'peg_ratio':           c.get('peg_ratio'),

CHANGE 3B — expanded row JS string:

Locate this exact string (it is unique in the file):
    "           + '<div class=\"est\"><div class=\"est-k\">Insider</div><div class=\"est-v\">' + (stock.insider_signal || 'N/A') + '</div></div>'\n"
    "           + '</div>'\n"

Replace it with:
    "           + '<div class=\"est\"><div class=\"est-k\">Insider</div><div class=\"est-v\">' + (stock.insider_signal || 'N/A') + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Expect.</div><div class=\"est-v\">' + (stock.expectations_signal || 'N/A') + '</div></div>'\n"
    "           + '</div>'\n"

CHANGE 3C — JS color-mapping variable block:

Locate this exact line (it is unique in the file):
    "      var insMap     = {'ACCUMULATING':'rpill-ins-ac','DISTRIBUTING':'rpill-ins-di','NEUTRAL':'rpill-ins-nt','UNAVAILABLE':'rpill-ins-na'};\n"

Add the following line immediately after it:
    "      var expMap     = {'BEATING':'rpill-exp-bt','INLINE':'rpill-exp-in','MISSING':'rpill-exp-ms','UNAVAILABLE':'rpill-exp-na'};\n"

Note: The CSS classes rpill-exp-* do not need to be created in this phase.
The variable is added now so the data mapping is wired. Visual styling
is a future pass.

───────────────────────────────────────────────────────────────────────────
F-STRING SAFETY RULE
───────────────────────────────────────────────────────────────────────────
Python 3.11 prohibits backslash characters inside f-string expression braces.
Assign computed values to plain variables BEFORE any f-string block and
reference those variables inside the braces. The display variables
_exp_beat_display and _exp_peg_display are already assigned as plain
variables per CHANGE 2B — this rule is satisfied for those.

───────────────────────────────────────────────────────────────────────────
VALIDATION — run all steps before declaring done
───────────────────────────────────────────────────────────────────────────

Step 1 — Syntax check all three modified files:
  python3 -m py_compile main.py && echo "main OK"
  python3 -m py_compile reports/report_builder.py && echo "report_builder OK"
  python3 -m py_compile reports/dashboard_builder.py && echo "dashboard_builder OK"

Step 2 — Confirm both Step 27i blocks exist in main.py:
  grep -c "Step 27i" main.py
  Expected output: 4
  (Each insertion has an opening comment and a closing comment —
  2 lines per path × 2 paths = 4 total)

Step 3 — Confirm finnhub_token is not redefined in 27i:
  grep -n "finnhub_token" main.py | grep "environ"
  Expected: the only lines containing both "finnhub_token" and "environ"
  belong to Step 27g. No such line must appear inside a Step 27i block.

Step 4 — Confirm schema import in report_builder.py:
  python3 -c "
  from reports.report_builder import _build_ai_prompt
  print('import OK')
  "

Step 5 — Confirm 2B block appears in AI prompt output:
  python3 - <<'EOF'
  import sys
  sys.path.insert(0, '.')
  from reports.report_builder import _build_ai_prompt

  dummy_candidate = {
      'ticker': 'TEST', 'company': 'Test Co', 'sector': 'Technology',
      'current_price': 100.0, 'composite_confidence': 60.0,
      'opportunity_score': 55.0, 'risk_score': 30.0,
      'eq_label': 'SUPPORTIVE', 'eq_score_final': 70.0,
      'alignment': 'PARTIAL', 'summary_verdict': 'WATCH',
      'event_risk': 'NORMAL', 'event_risk_reason': '',
      'insider_signal': 'NEUTRAL', 'insider_note': '',
      'expectations_signal': 'BEATING',
      'earnings_beat_rate': 0.75,
      'peg_ratio': 1.2,
  }
  result = _build_ai_prompt(
      [dummy_candidate],
      market_regime_dict={'market_regime': 'BULL', 'breadth_pct': 62.0}
  )
  assert 'Expectations vs Reality (2B)' in result, 'Section header missing'
  assert 'BEATING' in result, 'Signal value missing'
  assert '75%' in result, 'Beat rate display missing'
  assert '1.2' in result, 'PEG ratio display missing'
  print('AI prompt injection verified.')
  EOF

Step 6 — Confirm dashboard per-company dict has all three new fields:
  grep -n "expectations_signal\|earnings_beat_rate\|peg_ratio" reports/dashboard_builder.py
  Expected: at least 4 lines — 3 from the per-company dict (CHANGE 3A)
  and 1 from the JS expanded row string (CHANGE 3B).

Step 7 — Confirm git diff shows exactly 3 files modified:
  git diff --name-only
  Expected:
    main.py
    reports/report_builder.py
    reports/dashboard_builder.py
  If analyzers/expectations.py or contracts/eq_schema.py appear: STOP.
  Those are Phase A files and must not be modified in Phase B.

───────────────────────────────────────────────────────────────────────────
DONE CRITERIA
───────────────────────────────────────────────────────────────────────────
Phase B is complete when:
  ✓ All 3 modified files pass py_compile
  ✓ Step 27i appears in both main.py paths (grep -c = 4)
  ✓ finnhub_token is not re-assigned inside any 27i block
  ✓ AI prompt output contains the Expectations vs Reality section
    with correct values for signal, beat rate, and PEG ratio
  ✓ dashboard_builder.py has all 3 new fields in the per-company dict
  ✓ git diff shows exactly 3 files changed