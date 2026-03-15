# STOCK RESEARCH SYSTEM — AGENT PROMPT V8
# Delta Improvement Document
#
# WHAT THIS FILE IS:
# A precise set of changes to apply to the existing running system.
# It is NOT a full rewrite. It is NOT a new system from scratch.
# Every instruction here targets a specific existing file.
# Do NOT touch any file not listed in this document.
# Do NOT rewrite files from memory — always read the existing file first,
# then apply only the changes described here.
#
# HOW TO USE THIS FILE:
# Read it fully before touching any code.
# Implement changes in the order listed in §ORDER below.
# Update AGENT_PROGRESS.md before and after every file you touch.
#
# SYSTEM STATE AS OF V8:
# All 27 sections of the original roadmap are complete and running.
# The system produces real email reports and publishes to GitHub Pages.
# The analytical engine (all analyzers, scoring, pipeline) works correctly.
# Do NOT touch the analytical engine. Only output and UI layers change.

---

## §ORDER — IMPLEMENTATION ORDER

Complete in this exact order. Do not skip ahead.

1.  §FIX-2  — Fix trend display with actual timeframe data
              Files: reports/sentence_templates.py, reports/report_builder.py

2.  §FIX-3  — Improve financial health line and confidence breakdown
              Files: reports/sentence_templates.py, reports/report_builder.py

3.  §FIX-4  — Add SUMMARY block to every company entry
              Files: reports/sentence_templates.py, reports/report_builder.py

4.  §NEW-1  — Redesign intraday_email.html template
              File: reports/templates/intraday_email.html

5.  §NEW-2  — Redesign intraday_full.html template
              File: reports/templates/intraday_full.html

6.  §NEW-3  — Update closing_email.html color palette
              File: reports/templates/closing_email.html

7.  §NEW-4  — Update closing_full.html color palette + add Metric Guide
              File: reports/templates/closing_full.html

8.  §NEW-5  — Build HTML dashboard (new files only)
              New files: docs/index.html, docs/rank.html, docs/guide.html,
              docs/assets/style.css, docs/assets/app.js,
              reports/dashboard_builder.py
              One-line addition to: main.py (step 28 only)

9.  §NEW-6  — Add cleanup workflow
              New files: .github/workflows/cleanup.yml, scripts/cleanup_reports.py

---

## §DONOT — DO NOT TOUCH THESE

These files are working correctly. Read them for context only. Never modify them.

  main.py                              (except one-line addition in §NEW-5)
  all files in analyzers/              (all 20 analyzer modules complete)
  all files in collectors/             (news, market, financial parsers complete)
  all files in utils/                  (logger, state_manager, retry complete)
  filters/candidate_filter.py
  all files in data/                   (JSON data files complete)
  config.py
  validate_tickers.py
  requirements.txt
  .github/workflows/market_scan.yml   (existing schedule workflow — do not touch)
  reports/email_sender.py
  reports/summary_builder.py          (handles 16:10 closing report only — do not touch)
  state/daily_state.json

---

## §CONTEXT — WHAT IS ACTUALLY WRONG WITH CURRENT OUTPUT

Read the two actual output samples before writing any code.
These are the exact problems to fix. Nothing else.

--- SAMPLE (current working output) ---
"Trend: very stable upward trend"
"Financial health: keeps 25 cents from every dollar it earns (profit margin),
and carries very little debt compared to what it owns."
"Confidence: MODERATE (61/100)"
--- END SAMPLE ---

PROBLEM 1 — "very stable upward trend" repeated identically for every stock.
ROOT CAUSE: report_builder.py uses ram.get('label') which is a qualitative
string from risk_adjusted_momentum.py. The multi-timeframe percentage data
(r1m, r3m, r6m from mtf dict) is computed but never shown in the output.
FIX: See §FIX-2.

PROBLEM 2 — Financial health identical across different companies.
ROOT CAUSE: render_financial_health() only shows margin and D/E. Two companies
with 25% margin produce the same sentence. ROIC and FCF are computed in the
pipeline but never surface in the output.
FIX: See §FIX-3.

PROBLEM 3 — Confidence score "MODERATE (61/100)" with no breakdown.
ROOT CAUSE: CONFIDENCE_LINE template shows only label and score. The component
breakdown (risk_score, opportunity_score, signal_agreement) is computed and
stored in the candidate dict but never displayed.
FIX: See §FIX-3.

PROBLEM 4 — No summary at end of each company entry.
ROOT CAUSE: Not implemented.
FIX: See §FIX-4.

---

## §FIX-2 — TREND DISPLAY WITH ACTUAL DATA

### Files to modify:
  reports/sentence_templates.py
  reports/report_builder.py

### Change 1 of 2 — sentence_templates.py

Add these three new template strings immediately after the existing
TREND_SENTENCE constant:

  TREND_LINE_FULL = (
      "{RAM_LABEL} — "
      "1M: {R1M} · 3M: {R3M} · 6M: {R6M}"
  )

  TREND_LINE_PARTIAL = (
      "{RAM_LABEL} — "
      "3M: {R3M}"
  )

  TREND_VS_MA = (
      "vs 20D: {VS_20D} · vs 50D: {VS_50D} · vs 200D: {VS_200D}"
  )

### Change 2 of 2 — report_builder.py

At the top of the file, add TREND_LINE_FULL and TREND_LINE_PARTIAL to the
existing import from reports.sentence_templates.

In _enrich_company_for_template(), find this block:

  trend_label    = ram.get('label', 'trending')
  momentum_label = c.get('mtf', {}).get('label', 'no clear direction')

Replace with:

  ram_label = ram.get('label', 'no trend data')
  mtf       = c.get('mtf', {})
  r1m       = mtf.get('r1m')
  r3m       = mtf.get('r3m')
  r6m       = mtf.get('r6m')

  def _fmt_ret(v):
      if v is None: return 'n/a'
      if v > 0:   return f'▲{v:.1f}%'
      if v < 0:   return f'▼{abs(v):.1f}%'
      return '–0.0%'   # flat — neither up nor down arrow

  if r1m is not None and r3m is not None and r6m is not None:
      trend_label = TREND_LINE_FULL.format(
          RAM_LABEL = ram_label,
          R1M       = _fmt_ret(r1m),
          R3M       = _fmt_ret(r3m),
          R6M       = _fmt_ret(r6m),
      )
  elif r3m is not None:
      trend_label = TREND_LINE_PARTIAL.format(
          RAM_LABEL = ram_label,
          R3M       = _fmt_ret(r3m),
      )
  else:
      trend_label = ram_label

  momentum_label = mtf.get('label', 'no clear direction')

---

## §FIX-3 — FINANCIAL HEALTH AND CONFIDENCE BREAKDOWN

### Files to modify:
  reports/sentence_templates.py
  reports/report_builder.py

### Change 1 of 2 — sentence_templates.py

Add these two new template strings after the existing FINANCIAL_HEALTH_NO_MARGIN:

  FINANCIAL_HEALTH_EXTENDED = (
      "keeps {MARGIN_PCT} cents per $1 earned · "
      "{DEBT_LABEL} debt · "
      "ROIC: {ROIC} · "
      "Operating cash flow: {FCF_LABEL}"
  )

  CONFIDENCE_BREAKDOWN = (
      "{CONFIDENCE_LABEL} ({CONFIDENCE_SCORE}/100) — "
      "Risk {RISK_INT} · Opp {OPP_INT} · Agree {AGR_INT}"
  )

Also add this helper function to sentence_templates.py after the existing
debt_label() function:

  def roic_label(v: float | None) -> str:
      """Plain English ROIC label."""
      if v is None: return 'n/a'
      if v > 15:  return f'{v:.0f}% (high)'
      if v > 8:   return f'{v:.0f}% (solid)'
      if v > 0:   return f'{v:.0f}% (low)'
      return f'{v:.0f}% (weak)'

  def fcf_direction_label(v: float | None) -> str:
      """Plain English FCF direction."""
      if v is None: return 'n/a'
      return 'positive' if v > 0 else 'negative'

### Change 2 of 2 — report_builder.py

Add FINANCIAL_HEALTH_EXTENDED, CONFIDENCE_BREAKDOWN to the imports from
reports.sentence_templates at the top of the file.
Also add roic_label and fcf_direction_label to those imports.

In _enrich_company_for_template(), after the existing fin_health line
(which currently calls render_financial_health()), add:

  # Extended financial health — use verified key names from financial_parser.py
  # financial_parser.py confirmed output keys: operating_cash_flow, profit_margin,
  # debt_to_equity, revenue_ttm, net_income_ttm, eps_ttm, beta, pe_ratio
  # NOTE: ROIC is NOT returned by financial_parser.py — it is not in the dict.
  # Compute a proxy from available data if possible, otherwise skip.
  ocf_val  = fin.get('operating_cash_flow')   # operating cash flow (confirmed key)
  rev_val  = fin.get('revenue_ttm')            # revenue TTM (confirmed key)

  # ROIC proxy: not directly available. Use opportunity_model output if present.
  roic_val = c.get('roic_proxy')   # set by opportunity_model if computed, else None

  # FCF proxy: operating_cash_flow is the closest available free-tier equivalent
  fcf_val  = ocf_val

  if margin_pct is not None and fcf_val is not None:
      fin_health = FINANCIAL_HEALTH_EXTENDED.format(
          MARGIN_PCT = f'{margin_pct:.0f}',
          DEBT_LABEL = debt_label(de_ratio),
          ROIC       = roic_label(roic_val),      # will show 'n/a' if None
          FCF_LABEL  = fcf_direction_label(fcf_val),
      )
  # If operating_cash_flow also unavailable, fin_health stays as set by
  # render_financial_health() above — do not override it.
  # This ensures the extended format only appears when real data is present.

For the confidence breakdown, find the existing conf_line assignment:

  conf_line = CONFIDENCE_LINE.format(
      CONFIDENCE_LABEL = conf_lbl,
      CONFIDENCE_SCORE = int(conf_score),
  )

Replace with:

  agr_raw  = c.get('signal_agreement', {}).get('agreement_score', 0)
  agr_int  = int(agr_raw * 100)   # scaled to 0-100 for display only
  # agr_raw stays in 0-1 range for threshold checks below in §FIX-4
  conf_line = CONFIDENCE_BREAKDOWN.format(
      CONFIDENCE_LABEL = conf_lbl,
      CONFIDENCE_SCORE = int(conf_score),
      RISK_INT         = int(risk_score),
      OPP_INT          = int(c.get('opportunity_score', 0)),
      AGR_INT          = agr_int,
  )

---

## §FIX-4 — SUMMARY BLOCK PER COMPANY ENTRY

### IMPORTANT DISTINCTION — READ BEFORE IMPLEMENTING:
reports/summary_builder.py handles the 16:10 end-of-day CLOSING REPORT summary
(market close summary, full ranked list, watch tomorrow). It is explicitly
protected in §DONOT and must not be touched.

This section adds a DIFFERENT thing: a short per-company summary block at the
bottom of each individual company card inside INTRADAY reports (10:30, 12:30,
14:30). These are completely separate concerns. There is no duplication.

### Files to modify:
  reports/sentence_templates.py
  reports/report_builder.py

### Change 1 of 2 — sentence_templates.py

Add these constants and helper functions at the end of the file:

  SUMMARY_SCORE_LINE = "Score {SCORE}/100 — {SCORE_MEANING}"

  _SCORE_MEANINGS = [
      (85, "strong alignment across signals — prioritise for deeper research"),
      (70, "most signals favorable — verify key factors before acting"),
      (60, "passes screening — needs additional research"),
      (0,  "weak signal — approach with significant caution"),
  ]

  def score_meaning(score: int) -> str:
      """Returns plain English meaning of a confidence score."""
      for threshold, meaning in _SCORE_MEANINGS:
          if score >= threshold:
              return meaning
      return "insufficient data"

  def summary_verdict(conf_score: float, risk_score: float, section: str) -> str:
      """Returns RESEARCH NOW, WATCH, or SKIP based on scores."""
      if conf_score >= 70 and risk_score <= 35:
          return 'RESEARCH NOW'
      if conf_score >= 55 or (section == 'LOW RISK' and conf_score >= 45):
          return 'WATCH'
      return 'SKIP'

### Change 2 of 2 — report_builder.py

Add score_meaning, summary_verdict, SUMMARY_SCORE_LINE to the imports from
reports.sentence_templates.

In _enrich_company_for_template(), at the end of the function body
(just before the return statement), add:

  # ── Summary block ────────────────────────────────────────────────────────
  summary_score_line = SUMMARY_SCORE_LINE.format(
      SCORE        = int(conf_score),
      SCORE_MEANING = score_meaning(int(conf_score)),
  )

  summary_positives = []
  # ram dict confirmed keys from risk_adjusted_momentum.py:
  # ram_score, raw_value, return_3m, volatility, label
  ram_raw = ram.get('raw_value')   # float or None — always use .get(), never bracket
  if ram_raw is not None and ram_raw > 1:
      summary_positives.append(f'[+] {ram_label}')
  if c.get('opportunity_score', 0) > 60:
      summary_positives.append('[+] Strong fundamental and momentum signals')
  elif fin.get('profit_margin', 0) > 20:
      # use .get() with default — profit_margin may be None
      pm = fin.get('profit_margin', 0)
      summary_positives.append(f'[+] Solid profit margin ({pm:.0f}%)')
  if agr_raw > 0.25:   # agr_raw is 0-1 scale — 0.25 means 25% agreement strength
      summary_positives.append('[+] Multiple independent signals aligned')

  summary_risks = []
  dd_pct_val = dd.get('drawdown_pct')
  if dd_pct_val and dd_pct_val > 20:
      summary_risks.append(f'[-] {dd_pct_val:.0f}% below 90-day high')
  if de_ratio and de_ratio > 1.5:
      summary_risks.append('[-] Elevated debt for this sector')
  if c.get('risk_score', 0) > 50:
      summary_risks.append('[-] Risk score above moderate threshold')
  vol_ratio = ev.get('volume_ratio')
  if vol_ratio is not None and vol_ratio < 0.8:
      summary_risks.append('[-] Lower trading activity than usual')

  summary_verdict_val = summary_verdict(conf_score, risk_score, section)

Add these keys to the return dict at the end of _enrich_company_for_template():

  'summary_score_line': summary_score_line,
  'summary_positives':  summary_positives[:2],
  'summary_risks':      summary_risks[:2],
  'summary_verdict':    summary_verdict_val,

NOTE: agr_raw must be computed before this block. It is already computed
in the confidence breakdown section added by §FIX-3 above. The implementation
order within _enrich_company_for_template() must be:
  1. existing code (unchanged)
  2. §FIX-2 trend changes
  3. §FIX-3 financial + confidence changes (sets agr_raw)
  4. §FIX-4 summary block (uses agr_raw)

---

## §NEW-1 — REDESIGN intraday_email.html

### File to modify: reports/templates/intraday_email.html

Read the existing file completely before replacing it.
Then replace the entire file with a new version using the specifications below.

### REQUIRED JINJA2 VARIABLES — ALL MUST REMAIN IN THE NEW TEMPLATE:
These variables are passed by report_builder.py and must not be removed or renamed.

  Template-level variables (passed to render()):
    subject           string — email subject line
    slot              string — e.g. "10:30"
    date_str          string — e.g. "2026-03-12"
    time_str          string — e.g. "11:30 ET"
    pulse_lines       list of strings — pre-formatted index lines
    story_sentences   list of strings — today's story paragraphs
    low_risk          list of company dicts (LOW RISK section)
    moderate_risk     list of company dicts (MODERATE RISK section)
    overflow_notice   string or empty string
    regime_label      string — e.g. "Elevated uncertainty"
    breadth_label     string — e.g. "weak breadth — most stocks declining"
    disclaimer        string — the full disclaimer text
    total_companies   int

  Per-company dict keys (accessed as c.key in template loops):
    c.display_name          string
    c.ticker                string
    c.sector_plain          string
    c.intro_sentence        string
    c.trend_label           string   (now includes timeframe data from §FIX-2)
    c.price_line            string
    c.financial_health      string   (now extended from §FIX-3 when data available)
    c.volume_line           string
    c.confidence_label      string   ('STRONG', 'MODERATE', 'WEAK')
    c.conf_score_int        int
    c.conf_line             string   (now breakdown format from §FIX-3)
    c.moderate_risk_text    string   (only present for MODERATE RISK cards)
    c.notices               list of strings (earnings/divergence/unusual volume)
    c.summary_score_line    string   (NEW — added by §FIX-4)
    c.summary_positives     list     (NEW — up to 2 items, added by §FIX-4)
    c.summary_risks         list     (NEW — up to 2 items, added by §FIX-4)
    c.summary_verdict       string   (NEW — 'RESEARCH NOW'/'WATCH'/'SKIP', §FIX-4)

The new version must:

1. Use the §PALETTE colors throughout (see palette table at end of this document).

2. Render a confidence ASCII bar using this Jinja2 macro at the top of the template:

  {% macro conf_bar(score) %}
  {%- set filled = [score // 10, 10] | min | int -%}
  {%- set empty = 10 - filled -%}
  [{{ '█' * filled }}{{ '░' * empty }}] {{ score }}/100
  {%- endmacro %}

3. Show the SUMMARY block at the bottom of every company card.
   The SUMMARY block uses these new template variables added by §FIX-4:
     c.summary_score_line
     c.summary_positives   (list, up to 2 items)
     c.summary_risks       (list, up to 2 items)
     c.summary_verdict     ('RESEARCH NOW', 'WATCH', or 'SKIP')

4. Verdict label colors:
     RESEARCH NOW  → color: #00ff88
     WATCH         → color: #ffcc00
     SKIP          → color: #8888aa

5. Section headers:
     LOW RISK OPPORTUNITIES      → color: #00ff88
     MODERATE RISK OPPORTUNITIES → color: #ffcc00

6. Company card structure (both sections, in this order):
   - Company name + ticker + sector header
   - Intro sentence (why it appeared today)
   - Trend line (now includes timeframe data from §FIX-2)
   - Price line
   - Financial health (now extended from §FIX-3)
   - Trading activity (volume line)
   - Confidence: [ASCII bar] breakdown (from §FIX-3)
   - Any notices (earnings warnings, drawdown, unusual volume) — unchanged
   - Horizontal rule
   - SUMMARY block

7. Do NOT add a "How to Read This Report" block.

8. The disclaimer already exists in the template — do not add another one.
   Keep it exactly where it is now (at the bottom of the template).

9. Background: #0a0a0f
   Card background: #0f0f1a
   Border color: #1e1e3a

---

## §NEW-2 — REDESIGN intraday_full.html

### File to modify: reports/templates/intraday_full.html

Read the existing file completely before replacing it.
Then replace it with an updated version using the §PALETTE colors.

### REQUIRED JINJA2 VARIABLES — ALL MUST REMAIN IN THE NEW TEMPLATE:
Same as §NEW-1 plus one additional variable passed only to the full template:
  rotation    dict — sector rotation data (used by the existing rotation block)

All per-company dict keys from §NEW-1 apply here identically.

Changes vs current version:

1. Update all color values to §PALETTE. Map current colors as follows:
     #0d1117 → #0a0a0f  (bg)
     #161b22 → #0f0f1a  (card bg)
     #1c2128 → #141428  (inner bg)
     #3fb950 → #00ff88  (green)
     #f85149 → #ff3355  (red)
     #d29922 → #ffcc00  (yellow)
     #58a6ff → #00aaff  (blue)
     #30363d → #1e1e3a  (border)

2. Add SUMMARY block to each company card. Same structure as §NEW-1.

3. Add Metric Guide section before the disclaimer.
   This is the ONLY place where full definitions appear.
   Do NOT add the Metric Guide to the email template (§NEW-1).

   Metric Guide section markup (place immediately before the disclaimer div):

   <div class="metric-guide">
     <h3>METRIC GUIDE</h3>
     <div class="guide-grid">

       <div class="guide-item">
         <span class="guide-term">Confidence Score</span>
         <span class="guide-def">Composite screening score 0-100. Not a profit
           probability. 85+ = strong signal · 70-84 = solid · 60-69 = screening only</span>
       </div>

       <div class="guide-item">
         <span class="guide-term">ROIC</span>
         <span class="guide-def">Return on Invested Capital — profit generated per
           dollar invested in the business. Above 15% = excellent. Below 8% = weak.</span>
       </div>

       <div class="guide-item">
         <span class="guide-term">Trend (1M/3M/6M)</span>
         <span class="guide-def">Price return over 1, 3, and 6 months. Positive
           across all three = confirmed momentum. One timeframe only = early stage.</span>
       </div>

       <div class="guide-item">
         <span class="guide-term">Signal Agreement</span>
         <span class="guide-def">How many independent signals point the same
           direction. Multiplicative — one weak signal pulls the whole score down.</span>
       </div>

       <div class="guide-item">
         <span class="guide-term">Beta (Volatility)</span>
         <span class="guide-def">Market baseline = 1.0. Beta 1.8 = stock moves
           ~1.8x as much as the market. Higher beta = larger swings in both
           directions.</span>
       </div>

       <div class="guide-item">
         <span class="guide-term">Drawdown</span>
         <span class="guide-def">How far the stock has fallen from its 90-day
           highest price. Above 20% = meaningful risk even if fundamentals
           look clean.</span>
       </div>

       <div class="guide-item">
         <span class="guide-term">FCF</span>
         <span class="guide-def">Free Cash Flow — real cash the business generates
           after all expenses. Declining FCF is an early warning sign.</span>
       </div>

       <div class="guide-item">
         <span class="guide-term">Risk Score</span>
         <span class="guide-def">Composite risk measure 0-100. Higher = more risk.
           Factors: debt, volatility, liquidity, earnings stability,
           drawdown.</span>
       </div>

     </div>
   </div>

   CSS for metric guide (add to the style block):

   .metric-guide { margin-top: 28px; padding-top: 20px;
                   border-top: 1px solid #1e1e3a; }
   .metric-guide h3 { color: #8888aa; font-size: 11px; text-transform: uppercase;
                      letter-spacing: 0.12em; margin: 0 0 14px; }
   .guide-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                 gap: 12px; }
   .guide-item { background: #0f0f1a; border: 1px solid #1e1e3a; border-radius: 6px;
                 padding: 10px 12px; }
   .guide-term { display: block; color: #00aaff; font-size: 12px; font-weight: bold;
                 margin-bottom: 4px; }
   .guide-def  { display: block; color: #8888aa; font-size: 12px; line-height: 1.5; }

4. The existing rotation block is correct — keep it, update colors only.

5. Disclaimer is already present — do NOT add another.

---

## §TEMPLATE-CHECKLIST — ALL FOUR TEMPLATE FILES

Before starting §NEW-1 through §NEW-4, confirm all four template files exist
at these exact paths. Read each one before modifying it.

  reports/templates/intraday_email.html   — §NEW-1 (full redesign)
  reports/templates/intraday_full.html    — §NEW-2 (full redesign + Metric Guide)
  reports/templates/closing_email.html    — §NEW-3 (color palette only)
  reports/templates/closing_full.html     — §NEW-4 (color palette + Metric Guide)

After completing all four, verify none of the existing Jinja2 variables listed
in §NEW-1 are missing from any template. The variable list in §NEW-1 applies
to all four templates (minus the rotation variable which is full-report only).

---

## §NEW-3 — UPDATE closing_email.html

### File to modify: reports/templates/closing_email.html

Read the existing file. Apply §PALETTE color replacements only:
  #0d1117 → #0a0a0f
  #161b22 → #0f0f1a
  #1c2128 → #141428
  #3fb950 → #00ff88
  #f85149 → #ff3355
  #d29922 → #ffcc00
  #58a6ff → #00aaff
  #30363d → #1e1e3a

Do not change structure, variables, or logic. Colors only.
Disclaimer is already present — do NOT add another.

---

## §NEW-4 — UPDATE closing_full.html

### File to modify: reports/templates/closing_full.html

Read the existing file. Apply §PALETTE color replacements (same as §NEW-3).
Add the Metric Guide section from §NEW-2 before the disclaimer.
Disclaimer is already present — do NOT add another.

---

## §NEW-5 — HTML DASHBOARD (NEW FILES)

These are brand new files. No existing files are harmed by this section
except for a single try/except import line added to main.py at step 28.

### New file: reports/dashboard_builder.py

This module is called from main.py after build_intraday_report() completes.
It reads computed data and generates static dashboard pages.
It must NEVER crash the run — everything wrapped in try/except.

```python
"""
reports/dashboard_builder.py
Builds static HTML dashboard pages for GitHub Pages.
Called from main.py step 28 — after build_intraday_report() completes.
NEVER raises — all failures logged and skipped safely.

Does NOT replace any existing report output.
Reads computed data, writes to docs/ directory.
"""

import os
import json
from datetime import datetime
import pytz
from utils.logger import get_logger

log = get_logger('dashboard_builder')

DOCS_DIR  = 'docs'
DATA_DIR  = os.path.join(DOCS_DIR, 'assets', 'data')


def build_dashboard(companies: list, slot: str, indices: dict,
                    breadth: dict, regime: dict, rotation: dict) -> None:
    """
    Entry point called from main.py step 28.
    Updates: docs/index.html, docs/rank.html, docs/assets/data/*.json
    Does not touch: docs/guide.html (static, written once)

    IMPORTANT: The docs/ directory must exist in the repository for GitHub Pages
    to serve it. If docs/ does not exist on first run, this function creates it.
    After creation, commit docs/ to the repository manually once so GitHub Pages
    can be configured to serve from the docs/ folder on the main branch.
    """
    try:
        os.makedirs(DOCS_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)
        _update_reports_index(companies, slot, indices, breadth, regime)
        _update_rank_board(companies)
        _write_index_page(indices, breadth, regime)
        _write_rank_page()
        log.info('Dashboard updated successfully')
    except Exception as e:
        log.error(f'Dashboard build failed (non-fatal): {e}')


def _update_reports_index(companies, slot, indices, breadth, regime):
    index_path = os.path.join(DATA_DIR, 'reports.json')
    try:
        with open(index_path) as f:
            index = json.load(f)
    except Exception:
        index = {'reports': []}

    now_et = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    entry = {
        'date':      now_et.strftime('%Y-%m-%d'),
        'time':      now_et.strftime('%H:%M'),
        'slot':      slot,
        'breadth':   breadth.get('label', 'unknown'),
        'regime':    regime.get('label', 'unknown'),
        'count':     len(companies),
        'tickers':   [c.get('ticker', '') for c in companies[:5]],
        'top_score': max((c.get('composite_confidence', 0) for c in companies), default=0),
    }
    index['reports'].insert(0, entry)
    index['reports'] = index['reports'][:50]

    with open(index_path, 'w') as f:
        json.dump(index, f, indent=2)


def _update_rank_board(companies):
    rank_path = os.path.join(DATA_DIR, 'rank.json')
    now_et    = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    week_key  = now_et.strftime('%Y-W%W')

    try:
        with open(rank_path) as f:
            rank_data = json.load(f)
    except Exception:
        rank_data = {}

    if rank_data.get('week') != week_key:
        rank_data = {'week': week_key, 'stocks': {}}

    for c in companies:
        ticker   = c.get('ticker', '')
        if not ticker:
            continue
        existing = rank_data['stocks'].get(ticker, {})
        new_conf = c.get('composite_confidence', 0)
        if new_conf > existing.get('confidence', 0):
            rank_data['stocks'][ticker] = {
                'ticker':     ticker,
                'name':       c.get('company_name', ticker),
                'sector':     c.get('sector', ''),
                'price':      (c.get('current_price')
                               or c.get('financials', {}).get('current_price')),
                'confidence': round(new_conf, 1),
                'risk':       round(c.get('risk_score', 50), 1),
            }

    with open(rank_path, 'w') as f:
        json.dump(rank_data, f, indent=2)


def _write_index_page(indices, breadth, regime):
    index_path = os.path.join(DATA_DIR, 'reports.json')
    try:
        with open(index_path) as f:
            index = json.load(f)
        reports = index.get('reports', [])[:14]
    except Exception:
        reports = []

    rank_path = os.path.join(DATA_DIR, 'rank.json')
    try:
        with open(rank_path) as f:
            rank_data = json.load(f)
        top_stocks = sorted(
            rank_data.get('stocks', {}).values(),
            key=lambda x: x.get('confidence', 0),
            reverse=True
        )[:5]
    except Exception:
        top_stocks = []

    now_et = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    html = _render_index_html(reports, top_stocks, indices, breadth, regime, now_et)

    with open(os.path.join(DOCS_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)


def _write_rank_page():
    rank_path = os.path.join(DATA_DIR, 'rank.json')
    try:
        with open(rank_path) as f:
            rank_data = json.load(f)
        stocks = sorted(
            rank_data.get('stocks', {}).values(),
            key=lambda x: x.get('confidence', 0),
            reverse=True
        )
        week = rank_data.get('week', '')
    except Exception:
        stocks = []
        week   = ''

    html = _render_rank_html(stocks, week)
    with open(os.path.join(DOCS_DIR, 'rank.html'), 'w', encoding='utf-8') as f:
        f.write(html)


def _nav_html(active: str) -> str:
    pages  = [('index.html', 'HOME'), ('rank.html', 'RANK'), ('guide.html', 'GUIDE')]
    links  = []
    for href, label in pages:
        is_active = (label.lower() == active.lower())
        color     = '#ffffff' if is_active else '#8888aa'
        underline = 'text-decoration:underline;' if is_active else ''
        links.append(
            f'<a href="{href}" style="color:{color};{underline}'
            f'text-decoration-color:#00aaff;margin:0 12px;'
            f'font-family:monospace;font-size:13px;">{label}</a>'
        )
    return (
        '<div style="background:#0f0f1a;border-bottom:1px solid #1e1e3a;'
        'padding:12px 24px;display:flex;align-items:center;justify-content:space-between;">'
        '<span style="color:#ffffff;font-family:monospace;font-weight:bold;font-size:14px;">'
        'STOCK RESEARCH</span>'
        f'<div>{"".join(links)}</div>'
        '</div>'
    )


def _breadth_color(label: str) -> str:
    if 'weak' in label.lower():   return '#ff3355'
    if 'strong' in label.lower(): return '#00ff88'
    return '#ffcc00'


def _conf_color(score: float) -> str:
    if score >= 70: return '#00ff88'
    if score >= 60: return '#ffcc00'
    return '#ff3355'


def _render_index_html(reports, top_stocks, indices, breadth, regime, now_et) -> str:
    dow    = indices.get('dow', {})
    sp     = indices.get('sp500', {})
    nas    = indices.get('nasdaq', {})

    def idx_html(name, data):
        val   = data.get('value')
        chg   = data.get('change_pct', 0) or 0
        label = data.get('label', '')
        color = '#00ff88' if chg > 0 else '#ff3355' if chg < 0 else '#8888aa'
        arrow = '▲' if chg > 0 else '▼' if chg < 0 else '–'
        val_s = f'{val:,.0f}' if val else 'n/a'
        return (
            f'<div style="background:#0f0f1a;border:1px solid #1e1e3a;'
            f'border-radius:6px;padding:14px;text-align:center;">'
            f'<div style="color:#8888aa;font-size:11px;text-transform:uppercase;'
            f'letter-spacing:.08em;margin-bottom:6px;">{name}</div>'
            f'<div style="color:#e8e8f0;font-size:20px;font-weight:bold;'
            f'font-family:monospace;">{val_s}</div>'
            f'<div style="color:{color};font-size:13px;margin-top:4px;">'
            f'{arrow} {abs(chg):.1f}% {label}</div>'
            f'</div>'
        )

    pulse = (
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);'
        'gap:12px;margin-bottom:20px;">'
        + idx_html('Dow Jones', dow)
        + idx_html('S&P 500', sp)
        + idx_html('Nasdaq', nas)
        + '</div>'
    )

    b_color  = _breadth_color(breadth.get('label', ''))
    b_label  = breadth.get('label', 'unknown')
    r_label  = regime.get('label', 'unknown')

    status = (
        f'<div style="background:#0f0f1a;border:1px solid #1e1e3a;border-radius:6px;'
        f'padding:10px 16px;margin-bottom:20px;font-family:monospace;font-size:13px;">'
        f'<span style="color:#8888aa;">BREADTH: </span>'
        f'<span style="color:{b_color};">{b_label.upper()}</span>'
        f'&nbsp;&nbsp;&nbsp;'
        f'<span style="color:#8888aa;">MARKET: </span>'
        f'<span style="color:#e8e8f0;">{r_label}</span>'
        f'</div>'
    )

    rank_html = ''
    if top_stocks:
        rows = ''
        for i, s in enumerate(top_stocks, 1):
            conf  = s.get('confidence', 0)
            color = _conf_color(conf)
            rows += (
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:6px 0;border-bottom:1px solid #1e1e3a;font-size:13px;">'
                f'<span style="color:#8888aa;">#{i}</span>'
                f'<span style="color:#e8e8f0;font-weight:bold;">{s.get("ticker","")}</span>'
                f'<span style="color:#8888aa;">{s.get("sector","").replace("_"," ").title()}</span>'
                f'<span style="color:{color};">{conf:.0f}/100</span>'
                f'</div>'
            )
        rank_html = (
            f'<div style="background:#0f0f1a;border:1px solid #1e1e3a;border-radius:6px;'
            f'padding:14px 16px;margin-bottom:20px;">'
            f'<div style="color:#8888aa;font-size:11px;text-transform:uppercase;'
            f'letter-spacing:.08em;margin-bottom:10px;">THIS WEEK\'S BEST</div>'
            f'{rows}'
            f'<div style="margin-top:10px;font-size:12px;">'
            f'<a href="rank.html" style="color:#00aaff;">→ Full rank board</a></div>'
            f'</div>'
        )

    cards = ''
    for r in reports:
        date      = r.get('date', '')
        time_s    = r.get('time', '')
        slot      = r.get('slot', '')
        count     = r.get('count', 0)
        b         = r.get('breadth', '')
        tickers   = ', '.join(r.get('tickers', []))
        top_score = r.get('top_score', 0)
        b_col     = _breadth_color(b)

        cards += (
            f'<div class="report-card" style="background:#0f0f1a;border:1px solid #1e1e3a;'
            f'border-radius:6px;margin-bottom:8px;overflow:hidden;'
            f'transition:border-color .2s,box-shadow .2s,transform .2s;cursor:pointer;"'
            f'onclick="this.classList.toggle(\'expanded\')">'
            f'<div style="padding:12px 16px;display:flex;justify-content:space-between;'
            f'align-items:center;">'
            f'<div style="font-family:monospace;font-size:13px;">'
            f'<span style="color:#e8e8f0;">{date}</span>'
            f'<span style="color:#8888aa;"> · {time_s} · {slot} · {count} stock{"s" if count!=1 else ""}</span>'
            f'</div>'
            f'<div style="color:{b_col};font-size:11px;text-transform:uppercase;">{b}</div>'
            f'</div>'
            f'<div class="report-card-body" style="max-height:0;overflow:hidden;'
            f'transition:max-height .4s cubic-bezier(.4,0,.2,1),opacity .3s;opacity:0;">'
            f'<div style="padding:0 16px 14px;border-top:1px solid #1e1e3a;">'
            f'<div style="font-family:monospace;font-size:12px;color:#8888aa;margin-top:8px;">'
            f'Tickers: <span style="color:#e8e8f0;">{tickers}</span></div>'
            f'<div style="font-family:monospace;font-size:12px;color:#8888aa;margin-top:4px;">'
            f'Top score: <span style="color:#00ff88;">{top_score:.0f}/100</span></div>'
            f'</div></div>'
            f'</div>'
        )

    if not cards:
        cards = '<div style="color:#8888aa;font-size:13px;font-family:monospace;">No reports yet.</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Research Dashboard</title>
<link rel="stylesheet" href="assets/style.css">
<style>
  body{{background:#0a0a0f;color:#e8e8f0;margin:0;padding:0;font-family:'JetBrains Mono','Fira Code','Courier New',monospace;}}
  .wrap{{max-width:900px;margin:0 auto;padding:24px 16px;}}
  .report-card:hover{{border-color:#3a3a70!important;box-shadow:0 0 20px rgba(58,58,112,.3);transform:translateY(-1px);}}
  .report-card.expanded .report-card-body{{max-height:200px!important;opacity:1!important;}}
  .stagger-item{{opacity:0;transform:translateY(8px);animation:fadeUp .4s ease forwards;}}
  @keyframes fadeUp{{to{{opacity:1;transform:translateY(0);}}}}
  .stagger-item:nth-child(1){{animation-delay:.05s;}}
  .stagger-item:nth-child(2){{animation-delay:.10s;}}
  .stagger-item:nth-child(3){{animation-delay:.15s;}}
  .stagger-item:nth-child(4){{animation-delay:.20s;}}
  .stagger-item:nth-child(5){{animation-delay:.25s;}}
</style>
</head>
<body>
{_nav_html('home')}
<div class="wrap">
  <h1 style="color:#ffffff;font-size:22px;margin:20px 0 4px;">STOCK RESEARCH</h1>
  <div style="color:#8888aa;font-size:12px;margin-bottom:20px;">{now_et.strftime('%Y-%m-%d %H:%M ET')}</div>
  <div class="stagger-item">{pulse}</div>
  <div class="stagger-item">{status}</div>
  <div class="stagger-item">{rank_html}</div>
  <div class="stagger-item">
    <div style="color:#8888aa;font-size:11px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;">RECENT REPORTS</div>
    {cards}
  </div>
</div>
<div style="text-align:center;padding:20px;color:#444466;font-size:11px;font-family:monospace;">
  Free-tier data only &nbsp;·&nbsp; Not investment advice &nbsp;·&nbsp; Always verify before acting
</div>
</body>
</html>"""


def _render_rank_html(stocks, week) -> str:
    rows = ''
    for i, s in enumerate(stocks, 1):
        conf   = s.get('confidence', 0)
        risk   = s.get('risk', 50)
        color  = _conf_color(conf)
        price  = s.get('price')
        price_s = f'${price:,.2f}' if price else 'n/a'
        rows += (
            f'<tr style="border-bottom:1px solid #1e1e3a;transition:background .15s;"'
            f'onmouseover="this.style.background=\'#1f1f40\'"'
            f'onmouseout="this.style.background=\'transparent\'">'
            f'<td style="color:#8888aa;padding:8px 12px;font-size:13px;">#{i}</td>'
            f'<td style="color:#e8e8f0;font-weight:bold;padding:8px 12px;">{s.get("ticker","")}</td>'
            f'<td style="color:#e8e8f0;padding:8px 12px;">{s.get("name","")}</td>'
            f'<td style="color:#8888aa;padding:8px 12px;font-size:12px;">'
            f'{s.get("sector","").replace("_"," ").title()}</td>'
            f'<td style="padding:8px 12px;font-family:monospace;">{price_s}</td>'
            f'<td style="color:{color};font-weight:bold;padding:8px 12px;">{conf:.0f}</td>'
            f'<td style="color:#8888aa;padding:8px 12px;">{risk:.0f}</td>'
            f'</tr>'
        )

    if not rows:
        rows = ('<tr><td colspan="7" style="text-align:center;color:#8888aa;'
                'padding:20px;font-size:13px;">No stocks ranked this week yet.</td></tr>')

    week_display = week.replace('W', ' week ') if week else 'current week'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Weekly Rank Board</title>
<link rel="stylesheet" href="assets/style.css">
<style>
  body{{background:#0a0a0f;color:#e8e8f0;margin:0;padding:0;font-family:'JetBrains Mono','Fira Code','Courier New',monospace;}}
  .wrap{{max-width:900px;margin:0 auto;padding:24px 16px;}}
  table{{width:100%;border-collapse:collapse;}}
  th{{color:#8888aa;font-size:11px;text-transform:uppercase;letter-spacing:.08em;padding:8px 12px;text-align:left;border-bottom:2px solid #1e1e3a;}}
</style>
</head>
<body>
{_nav_html('rank')}
<div class="wrap">
  <h1 style="color:#ffffff;font-size:20px;margin:20px 0 4px;">WEEKLY RANK BOARD</h1>
  <div style="color:#8888aa;font-size:12px;margin-bottom:20px;">{week_display} — resets every Monday</div>
  <table>
    <thead>
      <tr>
        <th>Rank</th><th>Ticker</th><th>Name</th><th>Sector</th>
        <th>Price</th><th>Confidence</th><th>Risk</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<div style="text-align:center;padding:20px;color:#444466;font-size:11px;font-family:monospace;">
  Free-tier data only &nbsp;·&nbsp; Not investment advice
</div>
</body>
</html>"""
```

### New file: docs/guide.html

This is a static file. Write it once. It is NOT regenerated per run.
It contains the full Metric Guide. Use §PALETTE colors.
Include the nav bar (same as index.html and rank.html).

Sections to include:
  1. How This System Works
  2. Reading the Report (signal markers, status labels, verdict meanings)
  3. Confidence Score (breakdown, what it means, what it does NOT mean)
  4. Trend Signals (1M/3M/6M, moving averages, why these timeframes)
  5. Valuation Signals (margin, ROIC, D/E, FCF)
  6. Signal Agreement (multiplicative model explanation)
  7. Volume Signals (elevated bullish vs bearish)
  8. Risk Score (components, thresholds)
  9. Drawdown (why it matters, 20% threshold)
  10. What This System Cannot Do (free-tier honest ceiling)
  11. Footer: "Not investment advice."

### New file: docs/assets/style.css

Shared stylesheet. The CSS variable definitions go here.
Imported by index.html, rank.html, guide.html.
Report templates (intraday_email.html etc.) use inline styles for email
compatibility — they do NOT import this file.

```css
/* docs/assets/style.css */
:root {
  --bg-base:        #0a0a0f;
  --bg-primary:     #0f0f1a;
  --bg-secondary:   #141428;
  --bg-accent:      #1a1a35;
  --bg-hover:       #1f1f40;
  --border-default: #1e1e3a;
  --border-active:  #2a2a50;
  --border-glow:    #3a3a70;
  --text-primary:   #e8e8f0;
  --text-secondary: #8888aa;
  --text-muted:     #444466;
  --signal-green:   #00ff88;
  --signal-red:     #ff3355;
  --signal-yellow:  #ffcc00;
  --signal-blue:    #00aaff;
  --signal-purple:  #aa55ff;
  --font-mono:      'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
}
* { box-sizing: border-box; }
body {
  background: var(--bg-base);
  color: var(--text-primary);
  font-family: var(--font-mono);
  margin: 0; padding: 0;
}
a { color: var(--signal-blue); text-decoration: none; }
a:hover { text-decoration: underline; }
h1 { color: #ffffff; }
h2, h3 { color: var(--text-secondary); }
```

### New file: docs/assets/app.js

Shared JavaScript. Minimal. Only used for dashboard pages.
Report HTML templates (email/full) do NOT use this file.

```javascript
/* docs/assets/app.js */
/* Confidence bar animation on page load */
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.conf-bar-fill').forEach(function(bar) {
    var target = bar.getAttribute('data-width') || '0';
    setTimeout(function() { bar.style.width = target + '%'; }, 100);
  });
});
```

### main.py integration (ONE LINE ADDITION ONLY):

Read main.py carefully. Find step 28 in the pipeline which calls
build_intraday_report(). The call will look approximately like:

  report_paths = build_intraday_report(
      companies     = final_companies,
      slot          = slot,
      indices       = state['indices_today'],
      breadth       = breadth,
      regime        = regime,
      all_articles  = articles,
      sector_scores = scores,
      rotation      = rotation,
  )

The dashboard call goes IMMEDIATELY AFTER this block closes.
Not before it. Not inside it. Not after step 29 (email send).
Between step 28 (report build) and step 29 (email send):

  # ── Step 28b — Dashboard update (non-fatal) ──────────────────────────────
  try:
      from reports.dashboard_builder import build_dashboard
      build_dashboard(
          companies = final_companies,
          slot      = slot,
          indices   = state.get('indices_today', {}),
          breadth   = breadth,
          regime    = regime,
          rotation  = rotation,
      )
  except Exception as _dash_err:
      log.warning(f'Dashboard build skipped: {_dash_err}')
  # ── End step 28b ──────────────────────────────────────────────────────────

Do not change any other part of main.py.
Do not move any existing steps. Do not change step 29 or beyond.

---

## §NEW-6 — CLEANUP WORKFLOW

### New file: .github/workflows/cleanup.yml

```yaml
name: Cleanup Old Reports

on:
  schedule:
    - cron: '0 23 * * 0'   # Every Sunday at 23:00 UTC
  workflow_dispatch:

jobs:
  cleanup:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }

      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }

      - name: Run cleanup
        run: python scripts/cleanup_reports.py

      - name: Commit cleanup
        run: |
          git config user.name  'github-actions[bot]'
          git config user.email 'github-actions[bot]@users.noreply.github.com'
          git add reports/output/ docs/ || true
          git diff --staged --quiet || \
            git commit -m 'Auto: weekly cleanup $(date -u +%Y-%m-%dT%H:%M:%SZ)'
          git pull --rebase origin main
          git push
```

### New file: scripts/cleanup_reports.py

```python
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
"""

import os
import json
from datetime import datetime
import pytz

REPORTS_DIR = os.path.join('reports', 'output')
DATA_DIR    = os.path.join('docs', 'assets', 'data')
KEEP_DAYS   = 30
DELETE_DAYS = 90


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

    _rebuild_index()
    print(f'Cleanup complete. Removed {removed} file(s).')


def _rebuild_index():
    """Remove stale entries from reports.json after file deletion."""
    index_path = os.path.join(DATA_DIR, 'reports.json')
    if not os.path.exists(DATA_DIR) or not os.path.exists(index_path):
        return
    try:
        with open(index_path) as f:
            index = json.load(f)
        with open(index_path, 'w') as f:
            json.dump(index, f, indent=2)
        print('reports.json index updated.')
    except Exception as e:
        print(f'Index rebuild skipped: {e}')


if __name__ == '__main__':
    run_cleanup()
```

Also create the scripts/ directory when writing cleanup_reports.py.

---

## §PALETTE — SHARED COLOR REFERENCE

Both email templates and dashboard use only these colors.
Do not invent new colors. Use only values from this table.

  Purpose                        Value
  ─────────────────────────────  ─────────
  Page / email background        #0a0a0f
  Card / surface primary         #0f0f1a
  Card inner / surface 2         #141428
  Accent surface                 #1a1a35
  Hover background               #1f1f40
  Default border                 #1e1e3a
  Active border                  #2a2a50
  Glow border (hover effect)     #3a3a70
  Text primary                   #e8e8f0
  Text secondary                 #8888aa
  Text muted                     #444466
  White — titles ONLY            #ffffff
  Signal green (growth/good)     #00ff88
  Signal red (risk/bad)          #ff3355
  Signal yellow (caution/warn)   #ffcc00
  Signal blue (neutral/info)     #00aaff
  Signal purple (sector tags)    #aa55ff

White (#ffffff) is used ONLY for: h1 page titles, active nav items.
All other text uses #e8e8f0 or lower.

---

## §DISCLAIMER — EXISTING — DO NOT DUPLICATE

The disclaimer already exists and works correctly.
It is defined in report_builder.py as the DISCLAIMER constant.
It renders at the bottom of every email via the existing templates.

DO NOT add another disclaimer anywhere.
DO NOT add a SYSTEM NOTE block.
DO NOT add a "free-tier data only" block inside emails.

For the HTML dashboard footer only, use this shorter version:
"Free-tier data only · Not investment advice · Always verify before acting."

---

## §VERIFY — CONFIRM CHANGES WORKED

After all sections complete, verify these specific things:

1. Confirm trend line shows actual percentage numbers (▲X.X%) not just a label.

3. Confirm financial health line shows ROIC and FCF when that data is available.
   When ROIC/FCF are None, confirm it falls back to the original format gracefully.

4. Confirm SUMMARY block appears at the bottom of each company card.
   Confirm verdict is one of: RESEARCH NOW / WATCH / SKIP

5. Run main.py. Confirm docs/index.html is created or updated.
   Confirm docs/assets/data/reports.json and rank.json are created.

6. Confirm the disclaimer appears exactly ONCE per email.
   Search generated HTML for "DISCLAIMER" — must appear exactly once.

7. Confirm no new imports break the existing working imports in report_builder.py.
   All new imports come from sentence_templates.py which already exists.

---

## §PROGRESS — UPDATE PROTOCOL

The existing §00 protocol from the original roadmap is still in effect.
Before starting any file: write "NOW WORKING ON: [filename]" in AGENT_PROGRESS.md
After completing any file: write "COMPLETED: [filename] | NEXT: [next]"

Add a new session entry to the Session Log:
  Session 3: [date] — implementing AGENT_PROMPT_V8.md changes

---
END OF AGENT PROMPT V8
Scope: 3 precise bug fixes + 4 template redesigns + dashboard + cleanup
Touch: reports/sentence_templates.py, reports/report_builder.py,
       4 HTML templates, main.py (one line), 6 new files
Do not touch: all analyzers, all collectors, all utils, filters,
              data files, config, validate_tickers, requirements,
              market_scan.yml, email_sender, summary_builder
Key fixes across all revision rounds:
  Round 1: Explicit Jinja2 variable lists in §NEW-1 and §NEW-2
  Round 1: ROIC/FCF keys corrected to actual financial_parser.py output keys
  Round 1: §FIX-4 clarified to distinguish from summary_builder.py (no duplication)
  Round 1: ram.get('raw_value') annotated with confirmed key name
  Round 2: _fmt_ret() flat-value edge case fixed (v==0 → –0.0% not ▼0.0%)
  Round 2: agr_raw scale annotated to prevent 0-1 vs 0-100 confusion
  Round 2: docs/ directory GitHub Pages note added to dashboard_builder.py
  Round 3: fin['profit_margin'] bracket access replaced with safe .get()
  Round 3: §TEMPLATE-CHECKLIST consolidation block added before §NEW-3
  Round 3: main.py insertion point made explicit with step label and position rule
