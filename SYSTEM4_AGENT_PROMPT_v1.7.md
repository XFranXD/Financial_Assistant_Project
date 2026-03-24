# AGENT PROMPT — SYSTEM 4 COMPLETE OVERHAUL — v1.7
# Single master document. Execute top to bottom without skipping any block.
# Read the full prompt before starting any work.

---

## WHO YOU ARE AND WHAT YOU ARE DOING

You are implementing the System 4 complete overhaul for the Financial Assistant Project.
The project is a zero-cost automated stock research engine built in Python 3.11.
The repo lives at: /home/alejandro/Project_Financial_Assistant/

You are making targeted changes to existing files and creating new logic.
Do not push or pull. Do not create any branches. Implement only.

---

## WHAT THIS SYSTEM DOES (READ BEFORE TOUCHING ANYTHING)

System 1 screens stocks and produces confidence scores.
System 2 analyzes earnings quality (EQ Score, pass tier, warnings).
System 3 detects sector rotation timing.
System 4 is Systems 1+2+3 integrated — it is not a separate build.

The main entry point is main.py. It calls build_intraday_report() in reports/report_builder.py
which produces two HTML files per run: intraday_email and intraday_full.
It also calls build_dashboard() in reports/dashboard_builder.py which writes
docs/index.html, docs/rank.html, and docs/assets/data/*.json.

The dashboard is served via GitHub Pages from the docs/ directory.

---

## ARCHITECTURAL RULES — NEVER VIOLATE THESE

- System 1 owns all rendering. Systems 2 and 3 return raw data only.
- composite_confidence is the primary ranking signal. Never replace or reorder it.
- Per-company SUMMARY block in report_builder.py and summary_builder.py serve
  distinct purposes and must never be merged.
- Every submain call in main.py is wrapped in try/except. System 1 always continues
  if any downstream system fails.
- The AI prompt is generated exactly once per run. The same string goes to both
  the HTML report and weekly_archive.json. Never recompute it separately.
- Debug runs and workflow_dispatch runs must be excluded from weekly_archive.json
  and from the Archive section of the dashboard.

---

## CURRENT FILE STRUCTURE (RELEVANT FILES ONLY)

```
Project_Financial_Assistant/
  main.py                          — coordinator, calls all steps
  reports/
    report_builder.py              — builds email + full HTML per run
    dashboard_builder.py           — builds docs/ dashboard
    commodity_signal.py            — returns crude_pct, gas_pct as floats
    sentence_templates.py          — all display strings
    templates/
      intraday_email.html          — Jinja2 email template
      intraday_full.html           — Jinja2 full report template
    output/                        — generated HTML files land here
  docs/
    index.html                     — home page (written by dashboard_builder)
    rank.html                      — rank page (written by dashboard_builder)
    guide.html                     — static guide page (REWRITE THIS)
    assets/
      app.js                       — minimal JS for confidence bar animation
      style.css                    — shared styles
      data/
        reports.json               — run index (BUG: rebuild does not filter deleted)
        rank.json                  — weekly rank data
  scripts/
    cleanup_reports.py             — weekly cleanup, runs Sunday 23:00 UTC
  contracts/
    eq_schema.py                   — EQ data contract field names
    sector_schema.py               — rotation data contract field names
```

---

## BLOCK 1 — ADD _build_ai_prompt() TO report_builder.py

### What to do

Add a new function `_build_ai_prompt()` to reports/report_builder.py.
Update `build_intraday_report()` to call it once and store the result.

### Function signature

```python
def _build_ai_prompt(
    enriched: list,
    slot: str,
    date_str: str,
    indices: dict,
    breadth: dict,
    regime: dict,
    commodity_data: dict,
) -> str:
```

### Helpers and defensive guards — define at the top of _build_ai_prompt()

Define helpers and guards inside the function before any other logic.
Guards go first, helpers second.

```python
# Defensive guards — protect against None from failed API calls or broken pipeline
indices        = indices or {}
commodity_data = commodity_data or {}

def fmt_pct(x):
    """Safe percentage formatter. Returns 'N/A' if x is None."""
    return 'N/A' if x is None else f'{x:+.1f}%'

def fmt_price(x):
    """Safe price formatter. Returns 'N/A' if x is None."""
    return 'N/A' if x is None else f'${x:,.2f}'

def fmt_index(val, chg):
    """Safe index formatter. Returns 'N/A' if either value is None."""
    if val is None or chg is None:
        return 'N/A'
    return f'{val:,.0f} ({chg:+.1f}%)'
```

Apply fmt_pct() to: r1m, r3m, r6m, price_change_pct, crude_pct, gas_pct
Apply fmt_price() to: current_price
Apply fmt_index() to: Dow Jones, S&P 500, Nasdaq index lines

### Global variable extraction — define after guards and helpers

After the guards and helpers, extract all global variables before building any
part of the prompt string. Never reference dict keys directly in f-strings.

```python
# Index values
dow_val = indices.get('dow_val')
dow_chg = indices.get('dow_chg')
sp_val  = indices.get('sp_val')
sp_chg  = indices.get('sp_chg')
nas_val = indices.get('nas_val')
nas_chg = indices.get('nas_chg')

# Market condition labels — guard against None regime/breadth dicts
regime_label  = regime.get('label', 'N/A')  if regime  else 'N/A'
breadth_label = breadth.get('label', 'N/A') if breadth else 'N/A'
```

### Commodity block — build dynamically

Read commodity values:
```python
crude_pct = commodity_data.get('crude_pct')
gas_pct   = commodity_data.get('gas_pct')
```

Do NOT use a 0.0 default. If a value is missing it must be None so that
fmt_pct() renders it as "N/A" rather than a misleading 0.0%.

Build the commodity block conditionally:
```python
if crude_pct is not None or gas_pct is not None:
    commodity_block = (
        "Commodity context:\n"
        f"  WTI Crude:   {fmt_pct(crude_pct)} (5-day)\n"
        f"  Natural Gas: {fmt_pct(gas_pct)} (5-day)"
    )
else:
    commodity_block = "Commodity context: N/A"
```

Do NOT use commodity_data.get('summary') as the visibility gate — the summary
string is irrelevant now that we use numeric fields directly.
These are the exact field names returned by get_commodity_signal() in
reports/commodity_signal.py. Do not use any other field names for commodity data.

### Prompt structure (generate in this exact order)

```
IMPORTANT: You must prioritize timing quality over raw momentum.
A stock with strong returns but late-stage trend is a worse entry
than a weaker stock in an early-stage trend.

Do not use certainty words: never say "will", "guaranteed", or "certain".
Always prioritize downside risk before upside potential.
If signals conflict, highlight the conflict clearly before drawing any conclusion.
If a stock has gained more than 30% in the last 3 months, flag elevated
pullback risk unless strong justification is present.

=============================================================
SYSTEM CONTEXT — READ THIS BEFORE ANALYZING
=============================================================

This report was generated by an automated stock screening system.
The system has three scoring layers:

MARKET SIGNAL (System 1)
  Confidence score 0-100. Primary ranking signal.
  Market verdict vocabulary:
    RESEARCH NOW — strong setup, multiple signals aligned
    WATCH        — moderate setup, signal not fully confirmed
    SKIP         — weak or conflicting setup, do not act

EARNINGS QUALITY (System 2)
  EQ Score 0-100. Measures earnings reliability.
  Pass tier vocabulary:
    PASS (SUPPORTIVE) — earnings are reliable and cash-backed
    WATCH (NEUTRAL)   — earnings are acceptable but have concerns
    FAIL (WEAK)       — earnings are unreliable
    fatal flaw → RISKY — overrides all tiers, critical structural problem
    UNAVAILABLE       — no SEC data found for this ticker

SECTOR ROTATION (System 3)
  Rotation score 0-100. Measures sector timing.
  Signal vocabulary:
    SUPPORT  — sector flow supports acting now
    WAIT     — neutral timing, not yet favorable
    WEAKEN   — sector flow is deteriorating
    UNKNOWN  — insufficient data

COMBINED READING (three-layer synthesis)
  Alignment vocabulary:
    ALIGNED  — all three systems agree
    PARTIAL  — mixed signals, partial agreement
    CONFLICT — systems disagree

TIMING QUALITY DEFINITIONS (use these when classifying)
  EARLY TREND  — price up less than 15% in 3 months, momentum building
  MID TREND    — price up 15-30% in 3 months, trend established
  LATE TREND   — price up more than 30% in 3 months, elevated pullback risk

=============================================================
GLOBAL CONTEXT
=============================================================

Date: {date_str}
Slot: {slot}
Market condition: {regime_label}
Market breadth: {breadth_label}

Market indices:
  Dow Jones: {fmt_index(dow_val, dow_chg)}
  S&P 500:   {fmt_index(sp_val, sp_chg)}
  Nasdaq:    {fmt_index(nas_val, nas_chg)}

{commodity_block}

=============================================================
CANDIDATES
=============================================================

[repeated per company — see format below]

=============================================================
YOUR TASK
=============================================================

For EACH candidate above, provide this structure:

--- [TICKER] ---

1) QUICK DECISION
   Entry: BUY NOW / WAIT / AVOID
   Timing quality: EARLY / MID / LATE TREND
   Confidence in timing: LOW / MEDIUM / HIGH
   (2 sentences max explaining your decision)

2) WHY (PLAIN ENGLISH)
   Explain what is happening using simple logic:
   - Is the trend strong or extended?
   - Does the sector support the move or contradict it?
   - Are there contradictions between signals (e.g. stocks rising but commodity falling)?
   Avoid technical jargon. If you use a term, explain it in parentheses.

3) ENTRY LOGIC
   Ideal entry scenario: [when would this be a good entry]
   Bad entry scenario:   [what would make this a poor entry]
   What to wait for:     [1-2 specific conditions that need to improve]

4) EXIT LOGIC
   Take profit if: [specific condition]
   Cut loss if:    [specific condition]
   Explain each in plain English.

5) TOP RISKS RIGHT NOW
   List the 2-3 biggest risks specific to this candidate based on the data above.
   No generic risks. Be specific to the signals shown.

6) VERDICT
   Choose one: Worth researching further / Watch closely / Avoid for now
   Explain in 2-3 sentences why.

7) ENTRY URGENCY
   Choose one: Immediate / Near-term / Wait for confirmation
   (1 sentence explaining the specific condition that determines urgency.
   Example: "Immediate — sector support and trend intact, but extended 3M return
   means entry window is narrow." or "Wait for confirmation — signal needs
   market verdict to strengthen from WATCH to RESEARCH NOW before acting.")

---

After all individual candidates, provide:

CROSS-CANDIDATE SUMMARY
  Best entry opportunity:  [ticker and one-sentence reason]
  Worst timing right now:  [ticker and one-sentence reason]
  Overall market read:     [1-2 sentences on whether this is a good time to act]
```

### Per-company block format

For each candidate `c` in `enriched`, extract all fields with `.get()` before
building the block string. Never access dict keys directly in f-strings.

```python
ticker    = c.get('ticker',   'N/A')
sector    = c.get('sector',   'N/A')
industry  = c.get('industry', 'N/A')

current_price    = c.get('current_price')
price_change_pct = c.get('price_change_pct')

r1m = c.get('r1m')
r3m = c.get('r3m')
r6m = c.get('r6m')

conf_score      = c.get('composite_confidence', 0)
signal_strength = c.get('signal_strength', 'N/A')
market_verdict  = c.get('summary_verdict',  'N/A')

ram_label    = c.get('ram_label',    'N/A')
volume_label = c.get('volume_label', 'N/A')

eq_score_display = c.get('eq_score_display', 'UNAVAILABLE')
eq_pass_display  = c.get('eq_pass_display',  'UNAVAILABLE')

sector_etf              = c.get('sector_etf',              'N/A')
rotation_score_display  = c.get('rotation_score_display',  'N/A')
rotation_signal_display = c.get('rotation_signal_display', 'UNKNOWN')

alignment  = c.get('eq_alignment', 'N/A')
conclusion = c.get('eq_combined_reading', {}).get('conclusion', 'N/A')

# EQ strengths and warnings — use 'or []' to handle None field values
strengths  = c.get('eq_strengths',         []) or []
crit_warn  = c.get('eq_warnings_critical', []) or []
minor_warn = c.get('eq_warnings_minor',    []) or []

strengths_txt  = '\n'.join(f'+ {s}' for s in strengths[:3])  or 'N/A'
crit_warn_txt  = '\n'.join(f'! {w}' for w in crit_warn[:3])  or 'N/A'
minor_warn_txt = '\n'.join(f'w {w}' for w in minor_warn[:3]) or ''

# Combined reading lines — built from already-extracted variables
market_line   = f"Market: {market_verdict} ({conf_score}/100)"
earnings_line = f"Earnings: {eq_pass_display}"
rotation_line = f"Rotation: {rotation_signal_display}"
```

Then inject this block between CANDIDATES and YOUR TASK:

```
[TICKER] — [SECTOR] ([INDUSTRY])

Price:         {fmt_price(current_price)} ({fmt_pct(price_change_pct)} today)
Confidence:    {conf_score}/100 ({signal_strength})
Market verdict: {market_verdict}

Trend:
  1 month:  {fmt_pct(r1m)}
  3 months: {fmt_pct(r3m)}
  6 months: {fmt_pct(r6m)}
  Label:    {ram_label}

Volume: {volume_label}

Earnings Quality:
  Score:     {eq_score_display}
  Tier:      {eq_pass_display}
  Strengths: {strengths_txt}
  Warnings:  {crit_warn_txt}
             {minor_warn_txt}

Sector Rotation:
  ETF:    {sector_etf}
  Score:  {rotation_score_display}
  Signal: {rotation_signal_display}

Combined Reading:
  {market_line}
  {earnings_line}
  {rotation_line}
  Alignment:  {alignment}
  Conclusion: {conclusion}
```

### Changes to build_intraday_report()

1. The function already calls get_commodity_signal() inside a conditional block
   for energy sectors. Move this call outside the energy conditional so commodity
   data is always available for the prompt even when no energy companies are present.
   Keep the existing energy-specific interpretation logic unchanged.

2. After building `enriched`, call:
   ```python
   prompt_text = _build_ai_prompt(
       enriched, slot, date_str, indices, breadth, regime, commodity_data
   )
   ```

3. Add prompt_text to the return dict:
   ```python
   return {'email': email_path, 'full': full_path, 'prompt': prompt_text}
   ```

4. Pass prompt_text to the full HTML template with a 15,000 character cap:
   ```python
   full_html = full_tpl.render(
       ...existing args...,
       ai_prompt = prompt_text[:15000],
   )
   ```
   Do NOT pass it to the email template.

---

## BLOCK 2 — UPDATE intraday_full.html TEMPLATE

### What to add

Append a new section at the end of intraday_full.html, after the candidate cards
and before the disclaimer block.

The section must use a styled pre block. No JavaScript. Select-all is the copy
mechanism. The block must be visually distinct from the rest of the report.

### HTML to add (insert before the disclaimer div)

```html
<div class="section-divider" style="margin: 40px 0 20px; border-top: 1px solid #1e1e3a;"></div>

<div class="wrap">
  <div style="color:#8888aa;font-size:11px;text-transform:uppercase;
              letter-spacing:.08em;margin-bottom:8px;">
    AI RESEARCH PROMPT
  </div>
  <div style="color:#555577;font-size:11px;font-family:monospace;margin-bottom:12px;">
    Select all text in the box below and paste into any AI assistant
    (Claude, ChatGPT, Gemini) for entry and exit timing analysis.
  </div>
  <pre style="
    background:#050508;
    border:1px solid #2a2a4a;
    border-radius:6px;
    padding:20px;
    font-family:'Courier New',Courier,monospace;
    font-size:12px;
    line-height:1.6;
    color:#c8c8e0;
    overflow-x:auto;
    white-space:pre;
    word-wrap:normal;
    max-height:600px;
    overflow-y:auto;
  ">{{ ai_prompt | e }}</pre>
</div>
```

Note: `| e` is Jinja2's escape filter. The prompt is plain text so this is safe
and prevents any HTML in the prompt from being interpreted.

---

## BLOCK 3 — UPDATE intraday_email.html TEMPLATE

### What to add

Add one line at the bottom of the email, after all candidate cards and before
the disclaimer block. This replaces nothing — it is an addition only.

Find the disclaimer block in intraday_email.html. Just before it, add:

```html
<div style="font-family:monospace;font-size:12px;color:#555577;
            text-align:center;padding:16px 0 8px;border-top:1px solid #1e1e3a;
            margin-top:20px;">
  Full report + AI research prompt available at the dashboard
</div>
```

No link is included because the GitHub Pages URL is not available as a variable
in the email template context. The message is intentionally generic.

---

## BLOCK 4 — ADD weekly_archive.json SCHEMA AND WRITER

### New file: docs/assets/data/weekly_archive.json

This file does not exist yet. Create it with an empty structure on first write:
```json
{"weeks": {}}
```

### Changes to dashboard_builder.py

Add a new function `_update_weekly_archive()` and call it from `build_dashboard()`.

#### Function signature

```python
def _update_weekly_archive(
    companies: list,
    slot: str,
    breadth: dict,
    regime: dict,
    prompt_text: str = '',
    is_debug: bool = False,
) -> None:
```

#### Logic

If is_debug is True, return immediately without writing anything.

Week key format: 'YYYY-WNN' using now_et.strftime('%Y-W%W')
Run key format: now_et.strftime('%Y-%m-%dT%H:%M')

Archive path: docs/assets/data/weekly_archive.json

Load existing archive. If file does not exist, start with {"weeks": {}}.

Build run entry:
```python
run_id = f"{slot}_{now_et.strftime('%Y-%m-%dT%H:%M')}"

run_entry = {
    'id':           run_id,
    'timestamp':    now_et.strftime('%Y-%m-%dT%H:%M'),
    'slot':         slot,
    'breadth':      breadth.get('label', ''),
    'regime':       regime.get('label', ''),
    'count':        len(companies),
    'verdict_counts': {
        'RESEARCH NOW': sum(1 for c in companies if c.get('summary_verdict') == 'RESEARCH NOW'),
        'WATCH':        sum(1 for c in companies if c.get('summary_verdict') == 'WATCH'),
        'SKIP':         sum(1 for c in companies if c.get('summary_verdict') == 'SKIP'),
    },
    'candidates': [
        {
            'ticker':          c.get('ticker', ''),
            'sector':          c.get('sector', ''),
            'confidence':      round(c.get('composite_confidence', 0), 1),
            'market_verdict':  c.get('summary_verdict', ''),
            'eq_verdict':      c.get('eq_verdict_display', ''),
            'rotation_signal': c.get('rotation_signal_display', ''),
            'alignment':       c.get('eq_alignment', ''),
            'conclusion':      c.get('eq_combined_reading', {}).get('conclusion', ''),
        }
        for c in companies
    ],
    'prompt': prompt_text[:12000],
}
```

Duplicate run guard — check before inserting using composite run_id (slot + timestamp):
```python
if week_key not in archive['weeks']:
    archive['weeks'][week_key] = {'runs': []}

existing_runs = archive['weeks'][week_key]['runs']
if not any(r.get('id') == run_id for r in existing_runs):
    existing_runs.insert(0, run_entry)
```

Keep at most 10 runs per week (drop oldest if exceeded).
Keep at most 12 weeks total (drop oldest week keys if exceeded).

Write back to file with indent=2.

#### Update build_dashboard() signature and call

Change the signature to:
```python
def build_dashboard(
    companies: list,
    slot: str,
    indices: dict,
    breadth: dict,
    regime: dict,
    rotation: dict,
    prompt_text: str = '',
    is_debug: bool = False,
) -> None:
```

Add call inside the try block after _write_rank_page():
```python
_update_weekly_archive(companies, slot, breadth, regime, prompt_text, is_debug)
```

#### Update main.py call

Find the call to build_dashboard() in main.py (step 28b).
Update it to pass prompt_text and is_debug.

The prompt_text comes from the return value of build_intraday_report() — it is
stored as report_paths['prompt'] where report_paths is the return dict.

For is_debug: check if the run is a debug run. In main.py there is already a
mechanism to detect debug mode — look for a variable or flag that controls
whether the debug ticker list is used. Pass that flag as is_debug.
If no explicit debug flag exists, check for an environment variable
DEBUG_MODE or similar. If none found, default is_debug=False.

---

## BLOCK 5 — FIX cleanup_reports.py

### Fix 1: _rebuild_index() bug

The current _rebuild_index() reads reports.json and writes it back without
filtering deleted entries. This means broken links survive after cleanup.

Replace the entire _rebuild_index() function with:

```python
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
            # Build expected filename fragment from entry metadata.
            date    = entry.get('date', '').replace('-', '')
            slot_s  = entry.get('slot', '').replace(':', '').replace('-', '_')
            # Look for any intraday_full file matching both date and slot.
            # IMPLEMENTATION NOTE: verify that entry.get('slot','') matches the
            # substring format used in actual filenames before deploying — if slot
            # is stored as "09:30" but filenames use "0930", replace ':' first:
            #   slot_s = entry.get('slot','').replace(':', '')
            # Use whichever form matches your actual filename pattern.
            slot_s  = entry.get('slot', '').replace(':', '')
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
```

### Fix 2: Prune weekly_archive.json after HTML deletion

Add a new function after _rebuild_index():

```python
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
```

Call _prune_weekly_archive() inside run_cleanup(), after _rebuild_index().

---

## BLOCK 6 — DASHBOARD OVERHAUL

### Overview of changes

Navigation changes from HOME / RANK / GUIDE to HOME / RANK / ARCHIVE / GUIDE.

The dashboard is built entirely in Python inside dashboard_builder.py.
No separate HTML files are used for the new pages — they are written by
_write_archive_page() and the existing pattern is followed.

### 6a — Update _nav_html()

Replace the pages list inside _nav_html():

```python
pages = [
    ('index.html',   'HOME'),
    ('rank.html',    'RANK'),
    ('archive.html', 'ARCHIVE'),
    ('guide.html',   'GUIDE'),
]
```

### 6b — Update Home page (index.html)

The Home page currently shows recent report cards with only ticker and top score.
Update the report cards to also show alignment and combined reading conclusion
when available.

In _update_reports_index(), add these fields to each entry:
```python
entry['alignments']   = [
    c.get('eq_alignment', '') for c in companies[:5]
]
entry['conclusions']  = [
    c.get('eq_combined_reading', {}).get('conclusion', '')
    for c in companies[:5]
]
entry['verdicts']     = [
    c.get('summary_verdict', '') for c in companies[:5]
]
```

In _render_index_html(), update the report card expanded body to show:
- Tickers (existing)
- Top score (existing)
- Verdict counts: RESEARCH NOW / WATCH / SKIP
- Alignment of top candidate

### 6c — Update Rank page (rank.html)

In _update_rank_board(), add eq_verdict and rotation_signal to each stock entry:
```python
rank_data['stocks'][ticker] = {
    ...existing fields...,
    'eq_verdict':       c.get('eq_verdict_display', ''),
    'rotation_signal':  c.get('rotation_signal_display', ''),
    'alignment':        c.get('eq_alignment', ''),
}
```

In _render_rank_html(), add two columns to the table: EQ and Rotation.
Update the thead to:
```
Rank | Ticker | Name | Sector | Price | Confidence | Risk | EQ | Rotation
```
Add corresponding td cells for eq_verdict and rotation_signal in each row.

### 6d — Add Archive page (archive.html)

Add a new function _write_archive_page() to dashboard_builder.py.
Call it from build_dashboard() after _write_rank_page().

```python
def _write_archive_page() -> None:
    archive_path = os.path.join(DATA_DIR, 'weekly_archive.json')
    try:
        with open(archive_path) as f:
            archive = json.load(f)
        weeks = archive.get('weeks', {})
    except Exception:
        weeks = {}

    html = _render_archive_html(weeks)
    with open(os.path.join(DOCS_DIR, 'archive.html'), 'w', encoding='utf-8') as f:
        f.write(html)
```

#### _render_archive_html() structure

The archive page uses a collapsible accordion by week.
Each week expands to show runs by timestamp.
Each run expands to show candidates with verdicts and a View Prompt section.

Visual design rules:
- Match existing dark theme: background #0a0a0f, borders #1e1e3a
- Use same font stack as existing pages
- Week headers are clickable accordion toggles (use onclick class toggle, no JS file changes)
- Run entries are nested inside week, also expandable
- Prompt is shown in a pre block inside the run, same style as intraday_full.html prompt block
- If no weeks exist, show: "No archived reports yet."

Blank current week behavior:
- Detect current week key using Python's datetime before rendering
- If current week has no runs, show a summary panel pulled from the most recent week:
  - Verdict counts from most recent week (sum across all runs)
  - Top 3 candidates by confidence score across all runs in that week
  - Label it clearly: "No reports yet this week. Last week's summary:"

Excluded runs: is_debug runs are never written to archive (handled in Block 4).
No filtering needed in the render function — the data is already clean.

```python
def _render_archive_html(weeks: dict) -> str:
    import html as html_module
    now_et = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    current_week = now_et.strftime('%Y-W%W')

    # Sort weeks newest first
    sorted_weeks = sorted(weeks.keys(), reverse=True)

    content = ''

    if not sorted_weeks:
        content = '<div style="color:#8888aa;font-size:13px;font-family:monospace;">No archived reports yet.</div>'
    else:
        # Blank current week handling
        if current_week not in weeks and sorted_weeks:
            last_week_key  = sorted_weeks[0]
            last_week_runs = weeks[last_week_key].get('runs', [])

            # Aggregate verdict counts across all runs in last week
            vc = {'RESEARCH NOW': 0, 'WATCH': 0, 'SKIP': 0}
            all_candidates = []
            for run in last_week_runs:
                for k in vc:
                    vc[k] += run.get('verdict_counts', {}).get(k, 0)
                all_candidates.extend(run.get('candidates', []))

            top3 = sorted(all_candidates, key=lambda x: x.get('confidence', 0), reverse=True)[:3]

            summary_rows = ''.join(
                f'<div style="font-family:monospace;font-size:12px;padding:4px 0;">'
                f'<span style="color:#e8e8f0;font-weight:bold;">{c.get("ticker","")}</span> '
                f'<span style="color:#8888aa;">{c.get("sector","").replace("_"," ").title()}</span> '
                f'<span style="color:#ffcc00;">{c.get("confidence",0):.0f}/100</span> '
                f'<span style="color:#555577;">{c.get("market_verdict","")}</span>'
                f'</div>'
                for c in top3
            )

            content += (
                f'<div style="background:#0f0f1a;border:1px solid #2a2a4a;border-radius:6px;'
                f'padding:16px;margin-bottom:20px;">'
                f'<div style="color:#8888aa;font-size:11px;text-transform:uppercase;'
                f'letter-spacing:.08em;margin-bottom:10px;">No reports yet this week — Last week\'s summary</div>'
                f'<div style="font-family:monospace;font-size:12px;color:#8888aa;margin-bottom:8px;">'
                f'RESEARCH NOW: <span style="color:#00ff88;">{vc["RESEARCH NOW"]}</span> &nbsp; '
                f'WATCH: <span style="color:#ffcc00;">{vc["WATCH"]}</span> &nbsp; '
                f'SKIP: <span style="color:#ff3355;">{vc["SKIP"]}</span>'
                f'</div>'
                f'<div style="color:#8888aa;font-size:11px;margin-bottom:6px;">Top candidates:</div>'
                f'{summary_rows}'
                f'</div>'
            )

        # Render each week as accordion
        for week_key in sorted_weeks:
            week_data = weeks[week_key]
            runs      = week_data.get('runs', [])
            run_count = len(runs)
            week_display = week_key.replace('-W', ' · Week ')

            # Build run entries
            run_html = ''
            for run in runs:
                ts         = run.get('timestamp', '')
                slot       = run.get('slot', '')
                count      = run.get('count', 0)
                breadth    = run.get('breadth', '')
                vc         = run.get('verdict_counts', {})
                candidates = run.get('candidates', [])
                prompt     = run.get('prompt', '')

                # Candidate rows
                cand_rows = ''
                for c in candidates:
                    alignment = c.get('alignment', '')
                    al_color  = '#00ff88' if alignment == 'ALIGNED' else '#ffcc00' if alignment == 'PARTIAL' else '#ff3355' if alignment == 'CONFLICT' else '#8888aa'
                    mv        = c.get('market_verdict', '')
                    mv_color  = '#00ff88' if mv == 'RESEARCH NOW' else '#ffcc00' if mv == 'WATCH' else '#ff3355' if mv == 'SKIP' else '#8888aa'
                    conclusion_text = c.get('conclusion', '').replace('Conclusion: ', '')
                    cand_rows += (
                        f'<div style="padding:6px 0;border-bottom:1px solid #1e1e3a;font-size:12px;">'
                        f'<span style="color:#e8e8f0;font-weight:bold;font-family:monospace;">{c.get("ticker","")}</span> '
                        f'<span style="color:#8888aa;font-size:11px;">{c.get("sector","").replace("_"," ").title()}</span> '
                        f'<span style="color:#ffcc00;font-family:monospace;">{c.get("confidence",0):.0f}/100</span> '
                        f'<span style="color:{mv_color};font-size:11px;">{mv}</span> '
                        f'<span style="color:{al_color};font-size:11px;">{alignment}</span>'
                        f'<div style="color:#555577;font-size:11px;margin-top:2px;">{conclusion_text}</div>'
                        f'</div>'
                    )

                # Prompt block — use html.escape() for complete HTML safety
                prompt_block = ''
                if prompt:
                    prompt_block = (
                        f'<div style="margin-top:12px;">'
                        f'<div style="color:#8888aa;font-size:11px;text-transform:uppercase;'
                        f'letter-spacing:.08em;margin-bottom:6px;">AI Research Prompt</div>'
                        f'<div style="color:#555577;font-size:11px;font-family:monospace;margin-bottom:6px;">'
                        f'Select all and paste into any AI assistant</div>'
                        f'<pre style="background:#050508;border:1px solid #2a2a4a;border-radius:4px;'
                        f'padding:12px;font-family:monospace;font-size:11px;color:#c8c8e0;'
                        f'overflow-x:auto;white-space:pre;max-height:400px;overflow-y:auto;">'
                        f'{html_module.escape(prompt)}</pre>'
                        f'</div>'
                    )

                b_color = '#00ff88' if 'strong' in breadth.lower() else '#ff3355' if 'weak' in breadth.lower() else '#ffcc00'

                run_id = ts.replace(':', '').replace('-', '').replace('T', '')
                run_html += (
                    f'<div style="margin-bottom:6px;">'
                    f'<div onclick="var b=document.getElementById(\'r{run_id}\');'
                    f'b.style.display=(b.style.display===\'block\')?\'none\':\'block\';" '
                    f'style="background:#0a0a14;border:1px solid #1e1e3a;border-radius:4px;'
                    f'padding:10px 14px;cursor:pointer;display:flex;'
                    f'justify-content:space-between;align-items:center;">'
                    f'<div style="font-family:monospace;font-size:12px;">'
                    f'<span style="color:#e8e8f0;">{ts}</span> '
                    f'<span style="color:#8888aa;">· {slot} · {count} stock{"s" if count!=1 else ""}</span>'
                    f'</div>'
                    f'<div style="color:{b_color};font-size:11px;">'
                    f'RN:{vc.get("RESEARCH NOW",0)} W:{vc.get("WATCH",0)} S:{vc.get("SKIP",0)}'
                    f'</div>'
                    f'</div>'
                    f'<div id="r{run_id}" style="display:none;background:#080810;'
                    f'border:1px solid #1e1e3a;border-top:none;border-radius:0 0 4px 4px;'
                    f'padding:12px 14px;">'
                    f'{cand_rows}'
                    f'{prompt_block}'
                    f'</div>'
                    f'</div>'
                )

            week_id = week_key.replace('-', '').replace('W', 'W')
            content += (
                f'<div style="margin-bottom:12px;">'
                f'<div onclick="var b=document.getElementById(\'w{week_id}\');'
                f'b.style.display=(b.style.display===\'block\')?\'none\':\'block\';" '
                f'style="background:#0f0f1a;border:1px solid #1e1e3a;border-radius:6px;'
                f'padding:12px 16px;cursor:pointer;display:flex;'
                f'justify-content:space-between;align-items:center;">'
                f'<div style="font-family:monospace;font-size:13px;color:#e8e8f0;">{week_display}</div>'
                f'<div style="color:#8888aa;font-size:12px;">{run_count} run{"s" if run_count!=1 else ""}</div>'
                f'</div>'
                f'<div id="w{week_id}" style="display:none;padding:8px 0 0 0;">'
                f'{run_html}'
                f'</div>'
                f'</div>'
            )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Report Archive</title>
<link rel="stylesheet" href="assets/style.css">
<style>
  body{{background:#0a0a0f;color:#e8e8f0;margin:0;padding:0;font-family:'JetBrains Mono','Fira Code','Courier New',monospace;}}
  .wrap{{max-width:900px;margin:0 auto;padding:24px 16px;}}
</style>
</head>
<body>
{_nav_html('archive')}
<div class="wrap">
  <h1 style="color:#ffffff;font-size:20px;margin:20px 0 4px;">REPORT ARCHIVE</h1>
  <div style="color:#8888aa;font-size:12px;margin-bottom:20px;">
    Weekly accordion — click a week to expand runs, click a run to see candidates and AI prompt
  </div>
  {content}
</div>
<div style="text-align:center;padding:20px;color:#444466;font-size:11px;font-family:monospace;">
  Free-tier data only &nbsp;·&nbsp; Not investment advice
</div>
</body>
</html>"""
```

### 6e — Rewrite guide.html

Write a new static guide.html file at docs/guide.html.
This is a static file — it is not regenerated on every run.
Write it once as part of this implementation.

The guide has six sections as a single scrollable page:
1. What this system does
2. System 1 — Market Signal Analysis
3. System 2 — Earnings Quality Analysis
4. System 3 — Sector Rotation Analysis
5. Combined Reading
6. How to use the output

Match the dark theme and monospace font of the existing pages.
Use the same nav bar (ARCHIVE link included).
Keep language simple and plain English throughout.
Each section has a header and 2-4 short paragraphs.
No tables. No investment advice.

Content guidance per section:

Section 1: What this system does
  The system scans the stock market 4 times per market day.
  It finds stocks with aligned momentum, volume, and sector signals.
  It scores and ranks them automatically. No trading. No price predictions.
  The output is a research shortlist — not a buy list.

Section 2: System 1 — Market Signal Analysis
  Confidence score 0-100. Built from momentum, volume, risk, and signal agreement.
  Market verdict: RESEARCH NOW means multiple signals aligned strongly.
  WATCH means the setup exists but needs more confirmation.
  SKIP means weak or conflicting signals — do not act.
  Risk tier: LOW RISK or MODERATE RISK based on drawdown and volatility.

Section 3: System 2 — Earnings Quality Analysis
  EQ Score 0-100. Measures whether reported earnings are reliable.
  Built from 7 modules: cash conversion, accruals, revenue quality,
  FCF sustainability, earnings consistency, dividend stability, long-term trends.
  Pass tier: PASS means earnings are cash-backed and reliable.
  WATCH means acceptable but has concerns. FAIL means unreliable.
  A fatal flaw overrides everything and always produces RISKY.
  UNAVAILABLE means no SEC data was found.

Section 4: System 3 — Sector Rotation Analysis
  Measures whether money is flowing into or out of the stock's sector.
  Uses ETF momentum, relative strength, and volume across multiple timeframes.
  SUPPORT means the sector is being bought now — timing is favorable.
  WAIT means neutral — no strong flow in either direction.
  WEAKEN means money is leaving the sector — timing is unfavorable.

Section 5: Combined Reading
  The combined reading synthesizes all three systems into one conclusion.
  Market is the gatekeeper — if market says SKIP or WATCH, no other signal overrides it.
  Rotation is a modifier — SUPPORT strengthens a setup, WEAKEN weakens it.
  Earnings is validation — SUPPORTIVE confirms the setup, RISKY blocks it.
  ALIGNED means all three systems agree. PARTIAL means mixed. CONFLICT means disagreement.
  Every conclusion ends with a plain English action statement.

Section 6: How to use the output
  Read the combined reading conclusion first. It tells you the action status.
  "not actionable" means do not act — wait for conditions to improve.
  "monitor for confirmation" means track the stock for signal strengthening.
  "highest priority candidate" means full alignment — research immediately.
  Use the AI Research Prompt at the bottom of the full report for entry/exit timing.
  Paste the prompt into any AI assistant to get plain English timing guidance.
  Final decision — buy, wait, or skip — always remains with you.

---

## BLOCK 7 — VERIFICATION

After implementing all blocks, run the following to verify nothing is broken:

```bash
cd /home/alejandro/Project_Financial_Assistant
python -c "from reports.report_builder import build_intraday_report; print('report_builder OK')"
python -c "from reports.dashboard_builder import build_dashboard; print('dashboard_builder OK')"
python -c "from scripts.cleanup_reports import run_cleanup; print('cleanup_reports OK')"
python -m py_compile reports/report_builder.py && echo "report_builder syntax OK"
python -m py_compile reports/dashboard_builder.py && echo "dashboard_builder syntax OK"
python -m py_compile scripts/cleanup_reports.py && echo "cleanup_reports syntax OK"
```

If any import fails, fix it before finishing.
Do not run the full main.py — only syntax and import checks.

---

## EXECUTION ORDER

Execute blocks in this exact order:
1. Block 1 — _build_ai_prompt() + report_builder.py changes
2. Block 2 — intraday_full.html template update
3. Block 3 — intraday_email.html template update
4. Block 4 — weekly_archive.json schema + dashboard_builder.py changes
5. Block 5 — cleanup_reports.py fixes
6. Block 6 — dashboard overhaul (all sub-blocks in order: 6a, 6b, 6c, 6d, 6e)
7. Block 7 — verification

Do not skip any block. Do not reorder blocks.
Do not push, pull, or create branches.
Do not modify any file in eq_analyzer/ or sector_detector/.
Do not modify contracts/eq_schema.py or contracts/sector_schema.py.
Do not modify main.py except for the two targeted changes described in Block 4.
