# SYSTEM 3 → SYSTEM 1 INTEGRATION
# AI AGENT MASTER PROMPT v1.2

## MISSION

Wire System 3 (Sector Rotation Detector) into System 1 (Financial Assistant). System 3 source files have already been copied into `sector_detector/` inside the System 1 project. Everything lives inside `/home/alejandro/Project_Financial_Assistant/`.

This is a targeted integration. Do not rebuild anything. Do not modify any scoring logic. Do not touch any System 2 files. Apply only the changes described below to exactly the files listed.

**Goal: inject rotation_signal and rotation context into every candidate card and combined reading across all report types.**

---

## ARCHITECTURE RULES

- System 3 returns raw data only. System 1 owns all rendering.
- System 3 call is non-fatal. System 1 always continues if System 3 fails.
- `composite_confidence` is System 1's primary ranking signal. System 3 never modifies it.
- Rotation is a timing modifier only — it never reorders candidates.
- `contracts/sector_schema.py` is the single source of truth for all System 3 key names.
- System 1 sector names already match System 3 sector names exactly. No mapping needed.
- System 3 source files live at `sector_detector/` inside the System 1 project. No external path dependency.

---

## PROJECT STRUCTURE AFTER INTEGRATION
```
/home/alejandro/Project_Financial_Assistant/
  sector_detector/
    __init__.py              ← System 3 entry point (modify this)
    main.py                  ← System 3 main (already copied)
    data_fetcher.py          ← System 3 module (already copied)
    momentum_scorer.py       ← System 3 module (already copied)
    relative_strength_scorer.py ← System 3 module (already copied)
    volume_scorer.py         ← System 3 module (already copied)
    rotation_engine.py       ← System 3 module (already copied)
    output_formatter.py      ← System 3 module (already copied)
  contracts/
    eq_schema.py             ← System 2 contract (do not touch)
    sector_schema.py         ← System 3 contract (create this)
  main.py                    ← System 1 orchestrator (add Step 27e)
  reports/
    report_builder.py        ← modify
    templates/
      intraday_email.html    ← modify
      intraday_full.html     ← modify
      closing_email.html     ← modify
      closing_full.html      ← modify

STEP 1 — CREATE contracts/sector_schema.py
Create this file exactly:
python"""
contracts/sector_schema.py
Shared data contract between System 1 and sector_detector (System 3).
All key names used to exchange data between systems are defined here.
When a key name changes in System 3, update it here only — nowhere else.

RENDERING RULE: System 3 returns RAW DATA ONLY.
System 1 owns all rendering — HTML, email, and dashboard display.
sector_detector never produces HTML for System 1 consumption.
Display keys below are built exclusively by System 1's report_builder.py.

KEY NAMING RULE: raw data keys match System 3 output field names exactly.
No translation layer between System 3 output and System 1 storage.
"""

# ── Core rotation result keys (raw data from System 3) ────────────────────
# These match System 3 output_formatter.py field names exactly.
ROTATION_SCORE          = "rotation_score"
ROTATION_STATUS         = "rotation_status"
ROTATION_SIGNAL         = "rotation_signal"
SECTOR_ETF              = "sector_etf"
MOMENTUM_SCORE          = "momentum_score"
RELATIVE_STRENGTH_SCORE = "relative_strength_score"
VOLUME_SCORE            = "volume_score"
ROTATION_CONFIDENCE     = "data_confidence"
TIMEFRAMES_USED         = "timeframes_used"
ROTATION_REASONING      = "reasoning"

# ── Availability flag ──────────────────────────────────────────────────────
ROTATION_AVAILABLE      = "rotation_available"

# ── Display keys built by System 1's report_builder.py ────────────────────
# These are never set by sector_detector. Computed from raw keys above.
ROTATION_SCORE_DISPLAY  = "rotation_score_display"
ROTATION_SIGNAL_DISPLAY = "rotation_signal_display"
ROTATION_ETF_DISPLAY    = "rotation_etf_display"

STEP 2 — REWRITE sector_detector/init.py
System 3 source files are already inside sector_detector/. The __init__.py imports directly from them — no path injection needed.
Replace the current placeholder content with:
python"""
sector_detector/__init__.py
Entry point for System 3 (Sector Rotation Detector).
All System 3 source files live inside this package.
System 1 calls run_rotation_analyzer(candidates) from here.
"""

from sector_detector.main import get_rotation_result


def run_rotation_analyzer(candidates: list[dict]) -> list[dict]:
    """
    Accepts a list of candidate dicts with 'ticker' and 'sector' keys.
    Returns a list of rotation result dicts, one per candidate.
    Non-fatal — returns empty list on any failure.
    """
    try:
        results = []
        for c in candidates:
            ticker = c.get('ticker', '')
            sector = c.get('sector', '')
            if not ticker or not sector:
                continue
            try:
                result = get_rotation_result(ticker, sector)
                result['ticker'] = ticker
                results.append(result)
            except Exception as e:
                results.append({
                    'ticker':          ticker,
                    'rotation_status': 'SKIP',
                    'rotation_signal': 'UNKNOWN',
                    'rotation_score':  None,
                    'error':           str(e)
                })
        return results
    except Exception:
        return []

STEP 3 — UPDATE sector_detector/main.py IMPORTS
System 3's main.py was built as a standalone script. Its internal imports use bare module names like from data_fetcher import .... These must be updated to package-relative imports so they work inside System 1.
Open sector_detector/main.py and update all internal imports from:
pythonfrom data_fetcher import ...
from rotation_engine import ...
from output_formatter import ...
To:
pythonfrom sector_detector.data_fetcher import ...
from sector_detector.rotation_engine import ...
from sector_detector.output_formatter import ...
Apply the same pattern to all other files inside sector_detector/ that import from sibling modules. Check each file:

rotation_engine.py — likely imports from multiple scorers
output_formatter.py — likely imports from rotation_engine
All scorer files — check for any cross-imports

For each bare import like from momentum_scorer import ... change it to from sector_detector.momentum_scorer import ....

STEP 4 — ADD Step 27e to main.py
Add the following import at the top of main.py alongside the existing System 2 import:
pythonfrom sector_detector import run_rotation_analyzer
Also add this import alongside the existing contract imports:
pythonfrom contracts.sector_schema import (
    ROTATION_AVAILABLE, ROTATION_SCORE, ROTATION_STATUS,
    ROTATION_SIGNAL, SECTOR_ETF, ROTATION_CONFIDENCE,
    ROTATION_REASONING, TIMEFRAMES_USED
)
Then add Step 27e immediately after the # ── End Step 27d ───── line:
python    # ── Step 27e: Sector Rotation enrichment ─────────────────────────────
    # Run System 3 (Sector Rotation Detector) against all final candidates.
    # System 3 returns raw data only. System 1 owns all rendering.
    # rotation_signal is a timing modifier only — does NOT reorder candidates.
    try:
        rotation_candidates = [
            {'ticker': c.get('ticker', ''), 'sector': c.get('sector', '')}
            for c in final_companies
            if c.get('ticker') and c.get('sector')
        ]
        if rotation_candidates:
            log.info(f'[ROT] Running rotation analysis on {len(rotation_candidates)} candidates')
            rotation_results = run_rotation_analyzer(rotation_candidates)

            if not rotation_results:
                log.warning('[ROT] No results returned from System 3')
            else:
                rotation_map = {
                    r.get('ticker'): r
                    for r in rotation_results
                    if isinstance(r.get('ticker'), str) and r.get('ticker')
                }

                for candidate in final_companies:
                    t   = candidate.get('ticker', '')
                    rot = rotation_map.get(t, {})

                    if (rot
                            and rot.get('rotation_status') not in ('SKIP', None)
                            and not rot.get('error')):
                        candidate[ROTATION_AVAILABLE]  = True
                        candidate[ROTATION_SCORE]      = rot.get(ROTATION_SCORE)
                        candidate[ROTATION_STATUS]     = rot.get(ROTATION_STATUS, '')
                        candidate[ROTATION_SIGNAL]     = rot.get(ROTATION_SIGNAL, 'UNKNOWN')
                        candidate[SECTOR_ETF]          = rot.get(SECTOR_ETF, '')
                        candidate[ROTATION_CONFIDENCE] = rot.get(ROTATION_CONFIDENCE, '')
                        candidate[ROTATION_REASONING]  = rot.get(ROTATION_REASONING, '')
                        candidate[TIMEFRAMES_USED]     = rot.get(TIMEFRAMES_USED, [])
                    else:
                        candidate[ROTATION_AVAILABLE]  = False
                        candidate[ROTATION_SIGNAL]     = 'UNKNOWN'
                        log.info(f'[ROT] {t}: no rotation data — skipped or error')

                log.info(
                    f'[ROT] Enrichment complete. '
                    f'{sum(1 for c in final_companies if c.get(ROTATION_AVAILABLE))} enriched / '
                    f'{len(final_companies)} total'
                )
        else:
            log.info('[ROT] No candidates for rotation analysis')

    except Exception as rot_err:
        log.warning(f'[ROT] Rotation analysis failed (non-fatal): {rot_err}')
        for candidate in final_companies:
            candidate[ROTATION_AVAILABLE] = False
            candidate[ROTATION_SIGNAL]    = 'UNKNOWN'
    # ── End Step 27e ─────────────────────────────────────────────────────

STEP 5 — MODIFY reports/report_builder.py
Add these imports at the top alongside existing contract imports:
pythonfrom contracts.sector_schema import (
    ROTATION_AVAILABLE, ROTATION_SCORE, ROTATION_STATUS,
    ROTATION_SIGNAL, SECTOR_ETF, ROTATION_CONFIDENCE,
    ROTATION_REASONING, ROTATION_SCORE_DISPLAY,
    ROTATION_SIGNAL_DISPLAY, ROTATION_ETF_DISPLAY
)
A. Add _build_rotation_display() after _build_eq_display():
pythondef _build_rotation_display(c: dict) -> dict:
    """
    Builds display-ready rotation fields from raw System 3 data on the
    candidate dict. System 1 owns all rendering.
    Returns safe fallback display values when rotation data is unavailable.

    rotation_signal controlled vocabulary:
      SUPPORT  — sector flow supports acting now
      WAIT     — neutral timing environment
      WEAKEN   — sector flow weakens the setup
      UNKNOWN  — insufficient data or SKIP
    """
    rotation_available = bool(c.get(ROTATION_AVAILABLE))

    if not rotation_available:
        return {
            ROTATION_SCORE_DISPLAY:  'UNAVAILABLE',
            ROTATION_SIGNAL_DISPLAY: 'UNKNOWN',
            ROTATION_ETF_DISPLAY:    '',
            'rotation_available':    False,
            'rotation_conf_note':    '',
        }

    score  = c.get(ROTATION_SCORE)
    signal = c.get(ROTATION_SIGNAL, 'UNKNOWN')
    etf    = c.get(SECTOR_ETF, '')
    conf   = c.get(ROTATION_CONFIDENCE, '')

    score_display = f'{score:.1f}/100' if score is not None else 'N/A'
    conf_note     = f' ({conf.lower()} confidence)' if conf and conf != 'HIGH' else ''

    return {
        ROTATION_SCORE_DISPLAY:  score_display,
        ROTATION_SIGNAL_DISPLAY: signal,
        ROTATION_ETF_DISPLAY:    etf,
        'rotation_available':    True,
        'rotation_conf_note':    conf_note,
    }
B. Replace _alignment_state() with three-dimensional version:
pythondef _alignment_state(market_verdict: str, eq_verdict: str,
                     eq_available: bool,
                     rotation_signal: str = 'UNKNOWN') -> str:
    """
    Deterministic alignment state across System 1, System 2, and System 3.

    Three-dimensional alignment logic:
      market    → +1 if RESEARCH NOW / -1 if SKIP / 0 otherwise
      earnings  → +1 if SUPPORTIVE / -1 if WEAK or RISKY / 0 otherwise
      rotation  → +1 if SUPPORT / -1 if WEAKEN / 0 if WAIT or UNKNOWN

    Final label:
      >= 2  → ALIGNED
      0–1   → PARTIAL
      < 0   → CONFLICT
    """
    alignment_score = 0

    mv = market_verdict.upper() if market_verdict else ''
    if mv == 'RESEARCH NOW':
        alignment_score += 1
    elif mv == 'SKIP':
        alignment_score -= 1

    if eq_available and eq_verdict not in ('UNAVAILABLE', ''):
        ev = eq_verdict.upper()
        if ev == 'SUPPORTIVE':
            alignment_score += 1
        elif ev in ('WEAK', 'RISKY'):
            alignment_score -= 1

    rs = rotation_signal.upper() if rotation_signal else 'UNKNOWN'
    if rs == 'SUPPORT':
        alignment_score += 1
    elif rs == 'WEAKEN':
        alignment_score -= 1

    if alignment_score >= 2:
        return 'ALIGNED'
    elif alignment_score >= 0:
        return 'PARTIAL'
    else:
        return 'CONFLICT'
C. Replace _build_combined_reading() with rotation-aware version:
pythondef _build_combined_reading(conf_score: float, pass_tier: str,
                            eq_available: bool, fatal: str,
                            market_verdict: str = '',
                            rotation_signal: str = 'UNKNOWN',
                            rotation_available: bool = False) -> dict:
    """
    Deterministic combined reading of System 1, System 2, and System 3.
    Returns a structured dict for template rendering.
    Controls AI interpretation — no inference required.

    Output keys:
      market_line    — Market classification line
      earnings_line  — Earnings classification line
      rotation_line  — Rotation timing line
      alignment      — ALIGNED / PARTIAL / CONFLICT
      conclusion     — Final declarative conclusion sentence
    """
    signal     = _signal_strength_label(conf_score)
    eq_verdict = _eq_verdict_from_tier(pass_tier, fatal) if eq_available else 'UNAVAILABLE'
    rs         = rotation_signal.upper() if rotation_signal else 'UNKNOWN'
    alignment  = _alignment_state(market_verdict, eq_verdict, eq_available, rs)

    mv_display    = market_verdict.upper() if market_verdict else signal
    market_line   = f'Market:    {mv_display} ({int(conf_score)}/100)'
    earnings_line = f'Earnings:  {eq_verdict}'
    rotation_line = f'Rotation:  {rs}'

    if not eq_available and not rotation_available:
        conclusion = 'Conclusion: No fundamental or timing validation available.'
    elif not eq_available and rs == 'SUPPORT':
        conclusion = 'Conclusion: Sector timing supports acting. No fundamental validation available.'
    elif not eq_available and rs == 'WEAKEN':
        conclusion = 'Conclusion: Sector timing weakens this setup. No fundamental validation available.'
    elif not eq_available:
        conclusion = 'Conclusion: No fundamental validation available.'
    elif fatal:
        conclusion = 'Conclusion: Fatal flaw in earnings structure. Avoid.'
    elif alignment == 'ALIGNED':
        conclusion = 'Conclusion: Signal supported by fundamentals and sector timing. Highest priority candidate.'
    elif alignment == 'PARTIAL':
        tier = pass_tier.upper() if pass_tier else ''
        if rs == 'WEAKEN':
            conclusion = 'Conclusion: Signal present but sector flow is unfavorable — timing risk elevated.'
        elif rs == 'SUPPORT' and signal == 'STRONG':
            conclusion = 'Conclusion: Strong signal with sector support. Fundamentals require monitoring.'
        elif tier == 'PASS':
            conclusion = 'Conclusion: Fundamentals solid. Signal not fully confirmed. Requires further confirmation.'
        else:
            conclusion = 'Conclusion: Signal not fully confirmed. Requires caution.'
    else:  # CONFLICT
        if signal == 'STRONG':
            conclusion = 'Conclusion: Signal not supported by fundamentals. High risk of false signal.'
        else:
            conclusion = 'Conclusion: No alignment between signal and fundamentals. Avoid.'

    return {
        'market_line':    market_line,
        'earnings_line':  earnings_line,
        'rotation_line':  rotation_line,
        'alignment':      alignment,
        'conclusion':     conclusion,
    }
D. Update both _build_combined_reading() calls inside _build_eq_display():
Find both calls to _build_combined_reading() inside _build_eq_display() and replace each with:
pythonrotation_signal    = c.get(ROTATION_SIGNAL, 'UNKNOWN')
rotation_available = bool(c.get(ROTATION_AVAILABLE))
combined_reading   = _build_combined_reading(
    conf_score, pass_tier, eq_available, fatal, market_verdict,
    rotation_signal, rotation_available
)
E. Add rotation display fields to both return dicts in _build_eq_display():
In both the if not eq_available return dict and the main return dict add:
python**_build_rotation_display(c),

STEP 6 — UPDATE ALL FOUR TEMPLATES
Apply identical changes to all four templates:

reports/templates/intraday_email.html
reports/templates/intraday_full.html
reports/templates/closing_email.html
reports/templates/closing_full.html

A. Add rotation section immediately before <!-- ── COMBINED READING -->:
html<!-- ── SECTOR ROTATION ANALYSIS ──────────────────────────── -->
<div class="analysis-section sec-rotation">
  <div class="section-label-inner">── SECTOR ROTATION ANALYSIS ───────</div>
  {% if c.rotation_available %}
  <div class="line">
    Sector ETF:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    <span class="val">{{ c.rotation_etf_display }}</span>
  </div>
  <div class="line">
    Rotation score:&nbsp;
    <span class="val">{{ c.rotation_score_display }}</span>
    {{ c.rotation_conf_note }}
  </div>
  <div class="line">
    Timing signal:&nbsp;&nbsp;
    <span class="
    {%- if c.rotation_signal_display == 'SUPPORT' %} eq-v-supportive
    {%- elif c.rotation_signal_display == 'WEAKEN' %} eq-v-risky
    {%- elif c.rotation_signal_display == 'WAIT' %} eq-v-weak
    {%- else %} eq-v-unavailable{%- endif %}">
      {{ c.rotation_signal_display }}
    </span>
  </div>
  {% else %}
  <div class="line" style="color:#8888aa">Rotation: UNAVAILABLE</div>
  {% endif %}
</div>
B. Add rotation line to combined reading block after earnings_line and before Alignment::
html<div class="combined-text">{{ c.eq_combined_reading.rotation_line }}</div>

STEP 7 — VERIFY contracts/init.py
Open contracts/__init__.py. If it is empty or does not exist, no change needed. Python will find sector_schema directly as a module in the contracts package.

EXECUTION
After all changes run:
bashcd /home/alejandro/Project_Financial_Assistant
FORCE_TICKERS=XOM,COP python3 main.py
Report the full terminal output. The integration is complete when:

No import errors
[ROT] Running rotation analysis... appears in logs
rotation_signal appears in generated HTML
Combined reading shows Rotation line in all report types
No crashes


DO NOT

Modify any System 2 files
Modify any scoring or ranking logic
Change composite_confidence calculation
Change candidate order
Add rotation to dashboard_builder
Modify any System 3 source files except to fix import paths in Step 3