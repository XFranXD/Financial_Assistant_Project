# AGENT INTEGRATION PROMPT

## CONTEXT

You are working on a zero-cost automated stock research engine built in Python 3.11 on Linux Ubuntu. The project lives at `/home/alejandro/Project_Financial_Assistant/`. No paid APIs, no ML, no trading logic.

The system has been expanded with a second analytical engine called the Earnings Quality Analyzer (System 2). Its files have already been manually copied into `/home/alejandro/Project_Financial_Assistant/eq_analyzer/`. Your job is to fuse System 2 into System 1 so they operate as a single engine under one `main.py` orchestrator.

---

## CURRENT STATE AFTER MANUAL COPY

```
/home/alejandro/Project_Financial_Assistant/
  main.py                          ← System 1 orchestrator
  config.py                        ← System 1 config
  analyzers/                       ← System 1 analyzers
  collectors/                      ← System 1 collectors
  filters/                         ← System 1 filters
  reports/
    report_builder.py              ← System 1 report builder
    email_builder.py               ← System 1 email builder
    dashboard_builder.py           ← System 1 dashboard builder
    email_sender.py
    summary_builder.py
    sentence_templates.py
    commodity_signal.py
    templates/
  utils/
  eq_analyzer/                     ← System 2 files just copied
    main.py                        ← needs refactoring into run_eq_analyzer()
    data_validator.py
    edgar_fetcher.py
    eq_handoff.py
    eq_scorer.py
    report_builder.py              ← needs rename to eq_report_builder.py
    notifier.py                    ← needs deletion
    __init__.py
    module_accruals.py
    module_cash_conversion.py
    module_dividend_stability.py
    module_earnings_consistency.py
    module_earnings_timing.py
    module_fcf_sustainability.py
    module_long_term_trends.py
    module_revenue_quality.py
    config.json                    ← System 2 config, keep here
    edgar_concept_fallbacks.json
    ticker_cik_cache.json
  contracts/                       ← does not exist yet, you create it
  sector_detector/                 ← does not exist yet, you create it
```

---

## TASK OVERVIEW

Execute these phases in strict order. Complete each phase fully before moving to the next. After each phase print a clear completion message.

---

## PHASE 1 — FOLDER SETUP

Create these two folders:

```bash
mkdir -p /home/alejandro/Project_Financial_Assistant/contracts
mkdir -p /home/alejandro/Project_Financial_Assistant/sector_detector
```

Create a placeholder file in `sector_detector/`:

File: `/home/alejandro/Project_Financial_Assistant/sector_detector/__init__.py`

Content:
```python
# sector_detector/ — reserved for System 3 (Sector Rotation Detector)
# Do not add any code here until System 3 design begins.
```

Print: `PHASE 1 COMPLETE — folders created`

---

## PHASE 2 — CREATE CONTRACTS LAYER

Create `/home/alejandro/Project_Financial_Assistant/contracts/__init__.py` as an empty file.

Create `/home/alejandro/Project_Financial_Assistant/contracts/eq_schema.py` with this exact content:

```python
"""
contracts/eq_schema.py
Shared data contract between System 1 and eq_analyzer (System 2).
All key names used to exchange data between systems are defined here.
When a key name changes in System 2, update it here only — nowhere else.
System 3 will add sector_schema.py to this folder when ready.

RENDERING RULE: System 2 returns RAW DATA ONLY.
System 1 owns all rendering — HTML, email, and dashboard display.
eq_analyzer never produces HTML for System 1 consumption.
Display keys below are built exclusively by System 1's report_builder.py.
"""

# ── Core EQ result keys (raw data from System 2) ──────────────────────────
EQ_SCORE_FINAL          = "eq_score_final"
EQ_LABEL                = "eq_label"
EQ_MODIFIER             = "eq_modifier"
PASS_TIER               = "pass_tier"
FINAL_CLASSIFICATION    = "final_classification"
WARNING_SCORE           = "warning_score"
WARNINGS                = "warnings"
TOP_RISKS               = "top_risks"
TOP_STRENGTHS           = "top_strengths"
DATA_CONFIDENCE         = "data_confidence"
SCORE_CONFIDENCE        = "score_confidence"
ECONOMIC_INTEGRITY      = "economic_integrity_score"
FATAL_FLAW_REASON       = "fatal_flaw_reason"
EQ_PERCENTILE           = "eq_percentile"
COMBINED_PRIORITY_SCORE = "combined_priority_score"
BATCH_REGIME            = "batch_regime"
BATCH_MEDIAN            = "batch_median"

# ── Display keys built by System 1's report_builder.py ────────────────────
# These are never set by eq_analyzer. They are computed from the raw keys above.
EQ_SCORE_DISPLAY         = "eq_score_display"
EQ_LABEL_DISPLAY         = "eq_label_display"
EQ_VERDICT_DISPLAY       = "eq_verdict_display"
EQ_TOP_RISKS_DISPLAY     = "eq_top_risks_display"
EQ_TOP_STRENGTHS_DISPLAY = "eq_top_strengths_display"
EQ_WARNINGS_DISPLAY      = "eq_warnings_display"
EQ_AVAILABLE             = "eq_available"
```

Print: `PHASE 2 COMPLETE — contracts layer created`

---

## PHASE 3 — CLEAN UP eq_analyzer

### 3A — Delete notifier.py

Delete this file entirely:
```
/home/alejandro/Project_Financial_Assistant/eq_analyzer/notifier.py
```

System 1 owns all email sending. `notifier.py` must not exist in the integrated engine.

### 3B — Rename report_builder.py

Rename:
```
/home/alejandro/Project_Financial_Assistant/eq_analyzer/report_builder.py
→
/home/alejandro/Project_Financial_Assistant/eq_analyzer/eq_report_builder.py
```

### 3C — Update all internal imports across eq_analyzer

Every `.py` file inside `eq_analyzer/` currently uses flat imports that worked when files lived inside `src/`. Now that they live inside `eq_analyzer/`, all internal imports must use the `eq_analyzer.` prefix.

Go through every `.py` file inside `eq_analyzer/` and apply these exact replacements:

| Old import | New import |
|---|---|
| `from edgar_fetcher import` | `from eq_analyzer.edgar_fetcher import` |
| `from data_validator import` | `from eq_analyzer.data_validator import` |
| `from eq_scorer import` | `from eq_analyzer.eq_scorer import` |
| `from report_builder import` | `from eq_analyzer.eq_report_builder import` |
| `from eq_handoff import` | `from eq_analyzer.eq_handoff import` |
| `from notifier import` | DELETE this line entirely |
| `import module_cash_conversion` | `from eq_analyzer import module_cash_conversion` |
| `import module_accruals` | `from eq_analyzer import module_accruals` |
| `import module_revenue_quality` | `from eq_analyzer import module_revenue_quality` |
| `import module_long_term_trends` | `from eq_analyzer import module_long_term_trends` |
| `import module_fcf_sustainability` | `from eq_analyzer import module_fcf_sustainability` |
| `import module_earnings_consistency` | `from eq_analyzer import module_earnings_consistency` |
| `import module_earnings_timing` | `from eq_analyzer import module_earnings_timing` |
| `import module_dividend_stability` | `from eq_analyzer import module_dividend_stability` |
| `from src.` | `from eq_analyzer.` — only apply to actual import statements, not comments or strings |

Also update the `MODULE_RUNNERS` dict in `eq_analyzer/main.py` to reference the correctly imported module names after the above changes are applied.

### 3D — Fix config and fallback paths in eq_analyzer/main.py

Update `load_config()` to point to:
```python
Path(__file__).parent / "config.json"
```

Update `load_fallbacks()` to point to:
```python
Path(__file__).parent / "edgar_concept_fallbacks.json"
```

Check `edgar_fetcher.py` for any path that previously pointed to `src/` or repo root for `ticker_cik_cache.json`. Update it to:
```python
Path(__file__).parent / "ticker_cik_cache.json"
```

Print: `PHASE 3 COMPLETE — eq_analyzer cleaned and imports updated`

---

## PHASE 4 — REFACTOR eq_analyzer/main.py INTO SUBMAIN

Refactor `eq_analyzer/main.py` into a `run_eq_analyzer()` function that:

- Accepts a list of ticker strings as its only argument
- Runs the full pipeline (fetch → validate → modules → score → handoff)
- Returns a normalized list of result dicts — one per ticker
- Does NOT send email
- Does NOT write any files except `ticker_cik_cache.json` (cache save only, not a report)
- Does NOT call `sys.exit()`
- Does NOT produce any HTML output — System 2 returns raw data only, System 1 owns all rendering

Keep all existing pipeline logic intact. Only remove the email delivery and HTML output layer.

The refactored `eq_analyzer/main.py` must follow this structure:

```python
"""
eq_analyzer/main.py — System 2 Submain
Called by System 1's main.py via run_eq_analyzer(tickers).
Returns normalized list of per-ticker result dicts. Never sends email,
never writes report files, never produces HTML.

RENDERING RULE: System 2 returns RAW DATA ONLY.
System 1 owns all rendering. No html_block is produced for System 1 consumption.
The text_block is retained only for standalone testing via __main__.

Pipeline per ticker:
    1. EDGAR fetch
    2. Data validation
    3. Module execution (M1-M7 composite)
    4. Earnings timing (post-score modifier)
    5. Composite scoring
    6. Batch percentile ranking (mutates results in-place, also returns list)
    7. Handoff dict construction via eq_handoff.py

Returns:
    List of normalized dicts. Each dict contains fields defined in
    contracts/eq_schema.py plus: ticker, passed, skipped, error, eq_result.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent  # eq_analyzer/ directory


def load_config() -> dict:
    path = ROOT_DIR / "config.json"
    logger.info(f"[EQ_ANALYZER] Loading config: {path}")
    with open(path) as f:
        import json
        return json.load(f)


def load_fallbacks() -> dict:
    path = ROOT_DIR / "edgar_concept_fallbacks.json"
    logger.info(f"[EQ_ANALYZER] Loading EDGAR fallbacks: {path}")
    with open(path) as f:
        import json
        return json.load(f)


def process_ticker(ticker, fetcher, config) -> dict:
    # keep exactly as-is from original — no changes to pipeline logic
    ...


def compute_batch_percentile_ranks(results: list) -> list:
    # NOTE: mutates results in-place AND returns the list
    # Always use as: results = compute_batch_percentile_ranks(results)
    ...


def normalize_result(r: dict) -> dict:
    """
    Enforces output shape at the submain boundary.
    Guarantees System 1 never receives missing keys from System 2.
    Called on every result before returning from run_eq_analyzer.

    combined_priority_score is a handoff-level field computed by eq_handoff.py
    and attached directly to the top-level result dict — not nested inside
    eq_result. Always read it from eq (top-level), never from eq_result.

    eq_result uses `or {}` not `default={}` to handle explicit None values.
    """
    return {
        "ticker":                  r.get("ticker", ""),
        "eq_result":               r.get("eq_result") or {},
        "passed":                  r.get("passed", False),
        "skipped":                 r.get("skipped", False),
        "error":                   r.get("error", None),
        "combined_priority_score": r.get("combined_priority_score", 0),
        "text_block":              r.get("text_block", ""),
    }


def run_eq_analyzer(tickers: list) -> list:
    """
    Entry point called by System 1's main.py.
    Accepts list of ticker strings.
    Returns normalized list of result dicts — one per ticker.
    Never raises — all exceptions caught per ticker and returned as error result.
    """
    logger.info(f"[EQ_ANALYZER] Starting run for {len(tickers)} tickers: {tickers}")

    try:
        config    = load_config()
        fallbacks = load_fallbacks()
    except Exception as e:
        logger.critical(f"[EQ_ANALYZER] Fatal: failed to load config or fallbacks: {e}")
        return [normalize_result({"ticker": t, "passed": False,
                                  "error": "config load failed"}) for t in tickers]

    from eq_analyzer.edgar_fetcher import EdgarFetcher
    fetcher = EdgarFetcher(config, fallbacks)
    results = []

    for ticker in tickers:
        try:
            result = process_ticker(ticker, fetcher, config)
            results.append(result)
        except Exception as e:
            logger.error(f"[EQ_ANALYZER] Unhandled exception for {ticker}: {e}")
            results.append({
                "ticker": ticker, "passed": False,
                "eq_score_final": 0, "error": str(e)
            })

    fetcher.save_cik_cache()

    # Mutates in-place and returns list — always assign back
    results = compute_batch_percentile_ranks(results)

    # Rebuild text_block after percentiles assigned (for standalone testing only)
    from eq_analyzer.eq_report_builder import build_text_block
    for r in results:
        if (
            "eq_result" in r
            and r.get("eq_result")
            and not r.get("skipped")
            and not r.get("error")
            and "module_results" in r
        ):
            r["text_block"] = build_text_block(r["eq_result"], r["module_results"])

    # Enforce output shape at boundary before returning to System 1
    results = [normalize_result(r) for r in results]

    logger.info(
        f"[EQ_ANALYZER] Run complete. "
        f"{sum(1 for r in results if r.get('passed'))} passed / {len(results)} total"
    )
    return results


# Standalone testing only — not used by System 1
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", type=str)
    args = parser.parse_args()
    tickers = [t.strip().upper() for t in args.tickers.split(",")
               if t.strip()] if args.tickers else []
    results = run_eq_analyzer(tickers)
    for r in results:
        print(r.get("text_block") or r.get("ticker"))
```

Print: `PHASE 4 COMPLETE — eq_analyzer submain refactored`

---

## PHASE 5 — WIRE System 1 main.py TO CALL eq_analyzer

Open `/home/alejandro/Project_Financial_Assistant/main.py`.

### 5A — Add imports at top of file

After the existing imports block add:

```python
from eq_analyzer.main import run_eq_analyzer
from contracts.eq_schema import (
    EQ_SCORE_FINAL, EQ_LABEL, PASS_TIER, FINAL_CLASSIFICATION,
    TOP_RISKS, TOP_STRENGTHS, WARNINGS, DATA_CONFIDENCE,
    COMBINED_PRIORITY_SCORE, EQ_PERCENTILE, BATCH_REGIME,
    EQ_AVAILABLE, FATAL_FLAW_REASON,
)
```

### 5B — Insert Step 27d after Step 27c and before Step 28

```python
    # ── Step 27d: Earnings Quality enrichment ────────────────────────────
    # Run System 2 (EQ Analyzer) against all final candidates.
    # System 2 returns raw data only. System 1 owns all rendering.
    # combined_priority_score is available as a secondary signal but does
    # NOT replace or reorder System 1's composite_confidence ranking.
    try:
        eq_tickers = [c['ticker'] for c in final_companies if c.get('ticker')]
        if eq_tickers:
            log.info(f'[EQ] Running earnings quality analysis on {len(eq_tickers)} tickers')
            eq_results = run_eq_analyzer(eq_tickers)
            eq_map = {
                r.get('ticker'): r
                for r in eq_results
                if isinstance(r.get('ticker'), str) and r.get('ticker')
            }

            for candidate in final_companies:
                t         = candidate.get('ticker', '')
                eq        = eq_map.get(t, {})
                eq_result = eq.get('eq_result', {})

                if (eq_result
                        and isinstance(eq_result, dict)
                        and not eq.get('error')
                        and not eq.get('skipped')):
                    candidate[EQ_AVAILABLE]             = True
                    candidate[EQ_SCORE_FINAL]           = eq_result.get(EQ_SCORE_FINAL, 0)
                    candidate[EQ_LABEL]                 = eq_result.get(EQ_LABEL, '')
                    candidate[PASS_TIER]                = eq_result.get(PASS_TIER, '')
                    candidate[FINAL_CLASSIFICATION]     = eq_result.get(FINAL_CLASSIFICATION, '')
                    candidate[TOP_RISKS]                = eq_result.get(TOP_RISKS, [])
                    candidate[TOP_STRENGTHS]            = eq_result.get(TOP_STRENGTHS, [])
                    candidate[WARNINGS]                 = eq_result.get(WARNINGS, [])
                    candidate[DATA_CONFIDENCE]          = eq_result.get(DATA_CONFIDENCE, 0)
                    candidate[COMBINED_PRIORITY_SCORE]  = eq.get(COMBINED_PRIORITY_SCORE, 0)
                    candidate[EQ_PERCENTILE]            = eq_result.get(EQ_PERCENTILE, 0)
                    candidate[BATCH_REGIME]             = eq_result.get(BATCH_REGIME, '')
                    candidate[FATAL_FLAW_REASON]        = eq_result.get(FATAL_FLAW_REASON, '')
                else:
                    candidate[EQ_AVAILABLE] = False
                    log.info(f'[EQ] {t}: no EQ data — skipped or error')

            log.info(
                f'[EQ] Enrichment complete. '
                f'{sum(1 for c in final_companies if c.get(EQ_AVAILABLE))} enriched / '
                f'{len(final_companies)} total'
            )
        else:
            log.info('[EQ] No candidates for EQ analysis')

    except Exception as eq_err:
        log.warning(f'[EQ] EQ analysis failed (non-fatal): {eq_err}')
        for candidate in final_companies:
            candidate[EQ_AVAILABLE] = False
    # ── End Step 27d ─────────────────────────────────────────────────────
```

### 5C — Constraints for this wiring

- EQ call is wrapped in try/except and is NON-FATAL. System 1 continues normally if EQ fails.
- `composite_confidence` remains System 1's primary ranking signal. Do not reorder candidates.
- Do NOT modify any existing steps 1 through 27c.
- Insert Step 27d only — nothing else in main.py changes.

Print: `PHASE 5 COMPLETE — System 1 main.py wired to call eq_analyzer`

---

## PHASE 6 — UPDATE report_builder.py TO RENDER EQ DATA

Open `/home/alejandro/Project_Financial_Assistant/reports/report_builder.py`.

### 6A — Add EQ import at top

After existing imports add:

```python
from contracts.eq_schema import (
    EQ_AVAILABLE, EQ_SCORE_FINAL, EQ_LABEL, PASS_TIER,
    TOP_RISKS, TOP_STRENGTHS, WARNINGS, FATAL_FLAW_REASON,
    EQ_PERCENTILE, BATCH_REGIME, EQ_SCORE_DISPLAY,
    EQ_LABEL_DISPLAY, EQ_VERDICT_DISPLAY, EQ_TOP_RISKS_DISPLAY,
    EQ_TOP_STRENGTHS_DISPLAY, EQ_WARNINGS_DISPLAY,
)
```

### 6B — Add _build_eq_display function

Add this function before `_enrich_company_for_template()`:

```python
def _build_eq_display(c: dict) -> dict:
    """
    Builds display-ready EQ fields from raw EQ data on the candidate dict.
    System 1 owns all EQ rendering. System 2 never produces HTML for System 1.
    Returns safe fallback display values when EQ data is unavailable.
    """
    if not c.get(EQ_AVAILABLE):
        return {
            EQ_SCORE_DISPLAY:         'N/A',
            EQ_LABEL_DISPLAY:         'No earnings data',
            EQ_VERDICT_DISPLAY:       'EQ analysis unavailable for this ticker',
            EQ_TOP_RISKS_DISPLAY:     [],
            EQ_TOP_STRENGTHS_DISPLAY: [],
            EQ_WARNINGS_DISPLAY:      [],
        }

    eq_score   = c.get(EQ_SCORE_FINAL, 0)
    eq_label   = c.get(EQ_LABEL, '')
    pass_tier  = c.get(PASS_TIER, '')
    risks      = c.get(TOP_RISKS, [])
    strengths  = c.get(TOP_STRENGTHS, [])
    warnings   = c.get(WARNINGS, [])
    fatal      = c.get(FATAL_FLAW_REASON, '')
    percentile = c.get(EQ_PERCENTILE, 0)
    batch      = c.get(BATCH_REGIME, '')

    score_display = f'{int(eq_score)}/100'
    label_display = eq_label if eq_label else 'Unknown'

    if fatal:
        verdict = f'FATAL FLAW: {fatal}'
    elif pass_tier == 'PASS':
        verdict = f'Earnings quality PASS — {percentile}th percentile in batch ({batch})'
    elif pass_tier == 'WATCH':
        verdict = 'Earnings quality WATCH — monitor closely'
    else:
        verdict = f'Earnings quality FAIL — {eq_label}'

    warning_strings = []
    for w in warnings[:3]:
        if isinstance(w, dict):
            warning_strings.append(w.get('message', str(w)))
        else:
            warning_strings.append(str(w))

    return {
        EQ_SCORE_DISPLAY:         score_display,
        EQ_LABEL_DISPLAY:         label_display,
        EQ_VERDICT_DISPLAY:       verdict,
        EQ_TOP_RISKS_DISPLAY:     risks[:3],
        EQ_TOP_STRENGTHS_DISPLAY: strengths[:3],
        EQ_WARNINGS_DISPLAY:      warning_strings,
    }
```

### 6C — Call _build_eq_display inside _enrich_company_for_template

At the end of `_enrich_company_for_template()`, just before the final `return` statement, add:

```python
    # ── EQ display enrichment ─────────────────────────────────────────────
    eq_display = _build_eq_display(c)
```

Then merge into the returned dict with `**c` first and `**eq_display` second so EQ display fields win on any collision:

```python
    return {
        **c,              # original candidate data first
        **eq_display,     # EQ display fields second — these win on collision
        'display_name':      company_name,
        # ... rest of existing return keys unchanged
    }
```

### 6D — Update dashboard_builder.py rank board

Open `/home/alejandro/Project_Financial_Assistant/reports/dashboard_builder.py`.

In `_update_rank_board()`, update the per-ticker entry to store EQ data:

```python
        rank_data['stocks'][ticker] = {
            'ticker':     ticker,
            'name':       c.get('company_name', ticker),
            'sector':     c.get('sector', ''),
            'price':      (c.get('current_price')
                           or c.get('financials', {}).get('current_price')),
            'confidence': round(new_conf, 1),
            'risk':       round(c.get('risk_score', 50), 1),
            'eq_score':   round(c.get('eq_score_final', 0), 1),
            'eq_label':   c.get('eq_label', ''),
            'eq_pass':    c.get('pass_tier', ''),
        }
```

Print: `PHASE 6 COMPLETE — report_builder.py and dashboard_builder.py updated`

---

## PHASE 7 — VERIFY IMPORTS AND SYNTAX

Run these checks in order. Fix any error before continuing to the next check.

### 7A — Syntax check all modified files

```bash
cd /home/alejandro/Project_Financial_Assistant

python3 -m py_compile main.py && echo "main.py OK"
python3 -m py_compile eq_analyzer/main.py && echo "eq_analyzer/main.py OK"
python3 -m py_compile eq_analyzer/edgar_fetcher.py && echo "edgar_fetcher.py OK"
python3 -m py_compile eq_analyzer/eq_scorer.py && echo "eq_scorer.py OK"
python3 -m py_compile eq_analyzer/data_validator.py && echo "data_validator.py OK"
python3 -m py_compile eq_analyzer/eq_handoff.py && echo "eq_handoff.py OK"
python3 -m py_compile eq_analyzer/eq_report_builder.py && echo "eq_report_builder.py OK"
python3 -m py_compile reports/report_builder.py && echo "report_builder.py OK"
python3 -m py_compile contracts/eq_schema.py && echo "eq_schema.py OK"
```

### 7B — Import check for eq_analyzer submain

```bash
cd /home/alejandro/Project_Financial_Assistant && python3 -c "from eq_analyzer.main import run_eq_analyzer; print('run_eq_analyzer import OK')"
```

### 7C — Import check for contracts

```bash
cd /home/alejandro/Project_Financial_Assistant && python3 -c "from contracts.eq_schema import EQ_SCORE_FINAL, EQ_AVAILABLE; print('contracts import OK')"
```

### 7D — Dry run eq_analyzer standalone against one ticker

```bash
cd /home/alejandro/Project_Financial_Assistant && python3 -m eq_analyzer.main --tickers AAPL
```

This makes real EDGAR network calls — allow up to 30 seconds. An EDGAR error result is acceptable. Import or syntax errors are not acceptable and must be fixed before continuing.

Print: `PHASE 7 COMPLETE — all syntax and import checks passed`

---

## PHASE 8 — FINAL CHECKLIST

Confirm every item is true before printing completion:

- `eq_analyzer/notifier.py` does not exist
- `eq_analyzer/report_builder.py` does not exist — renamed to `eq_report_builder.py`
- `eq_analyzer/main.py` has `run_eq_analyzer()` and `normalize_result()` functions
- `eq_analyzer/main.py` has no `send_report()` call and no `sys.exit()` outside `__main__`
- `eq_analyzer/main.py` produces no html_block for System 1 consumption
- `results = compute_batch_percentile_ranks(results)` assigns back explicitly
- `normalize_result()` uses `r.get("eq_result") or {}` not `r.get("eq_result", {})`
- `contracts/eq_schema.py` exists with all key constants and rendering rule comment
- `sector_detector/__init__.py` exists
- `main.py` has Step 27d block with `isinstance(eq_result, dict)` guard
- `main.py` Step 27d EQ block is fully wrapped in try/except and is non-fatal
- `main.py` eq_map construction guards for non-empty string ticker
- `main.py` reads `COMBINED_PRIORITY_SCORE` from top-level `eq` dict not from `eq_result`
- `reports/report_builder.py` has `_build_eq_display()` function
- `reports/report_builder.py` calls `_build_eq_display()` inside `_enrich_company_for_template()`
- `reports/report_builder.py` return dict has `**c` first then `**eq_display` second
- `reports/dashboard_builder.py` stores `eq_score`, `eq_label`, `eq_pass` in rank entries
- All Phase 7 checks passed with no errors

Print: `INTEGRATION COMPLETE — System 2 fused into System 1`

---

## HARD CONSTRAINTS

- Do NOT modify any existing System 1 pipeline steps 1 through 27c
- Do NOT change `_determine_slot()` — leave it exactly as-is
- Do NOT merge `reports/report_builder.py` with `eq_analyzer/eq_report_builder.py`
- Do NOT add investment disclaimers to any output
- Do NOT reorder candidates based on EQ results
- Do NOT produce HTML inside eq_analyzer for System 1 consumption
- The EQ call in Step 27d must always be non-fatal
- All file paths use absolute paths based on `/home/alejandro/Project_Financial_Assistant/`
- Python version is 3.11, OS is Linux Ubuntu