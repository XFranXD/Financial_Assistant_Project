# AGENT_PROMPT_V9.md
# Delta document against confirmed working V8 codebase.
# This is NOT a rewrite. Apply only what is specified here.
# AGENT_PROGRESS.md must be updated BEFORE and AFTER every file touched.
# Format: "NOW WORKING ON filename" before. "COMPLETED filename" after.

---

## §ORDER — Implementation sequence

Execute in this exact order. Do not reorder.

1. reports/commodity_signal.py              — NEW FILE — commodity momentum utility
2. reports/report_builder.py                — inject commodity_signal call + pass to template context
3. reports/templates/intraday_email.html    — inject commodity block after story_sentences loop
4. reports/templates/intraday_full.html     — inject commodity block after story_sentences loop
5. reports/summary_builder.py               — inject commodity signal into _build_what_moved_today()
6. utils/state_manager.py                   — add today_scores key to DEFAULT_STATE
7. main.py                                  — add industry deduplication after rank_candidates()
8. main.py                                  — add score stability filter after deduplication
9. main.py                                  — add today_scores state save at Step 32

Steps 3 and 4 are independent of each other.
Step 5 is independent of steps 3 and 4.
Step 7 must complete before step 8.
Step 9 depends on step 8 being in place.

---

## §DONOT — Files that must not be touched

candidate_filter.py
analyzers/sector_momentum.py
analyzers/opportunity_model.py
analyzers/risk_model.py
analyzers/zscore_ranker.py
analyzers/signal_agreement.py
analyzers/market_regime.py
analyzers/market_breadth.py
analyzers/news_impact_scorer.py
analyzers/event_detector.py
analyzers/sector_mapper.py
analyzers/sector_validator.py
analyzers/volume_confirmation.py
analyzers/risk_adjusted_momentum.py
analyzers/multi_timeframe_momentum.py
analyzers/sector_breadth_ma.py
analyzers/event_decay.py
analyzers/sector_rotation_speed.py
analyzers/trend_stability.py
analyzers/drawdown_risk.py
analyzers/unusual_volume.py
reports/summary_builder.py — EXCEPTION: only _build_what_moved_today() may be modified (see §FIX 5)
reports/email_builder.py
reports/email_sender.py
reports/sentence_templates.py
reports/dashboard_builder.py
reports/templates/closing_email.html
reports/templates/closing_full.html
docs/index.html
docs/rank.html
docs/guide.html
docs/assets/style.css
docs/assets/app.js
scripts/cleanup_reports.py
.github/workflows/market_scan.yml
.github/workflows/cleanup.yml
data/event_keywords.json
data/event_to_sector.json
data/sector_momentum_history.json
data/plain_english_terms.json
data/sector_etfs.json
data/sector_breadth_stocks.json
data/sector_tickers.json
data/sector_tickers_validated.json
config.py
validate_tickers.py

---

## §CONTEXT — What is wrong and why

### Problem 1 — Single-sector over-selection
Root cause: after rank_candidates() returns in main.py Step 27, the only diversity
constraint in effect is MAX_COMPANIES_PER_SECTOR = 3 (set in config.py, enforced
inside zscore_ranker.py). This cap operates at sector level, not industry level.
When one sector dominates all upstream gates (e.g. Energy), up to 3 * number_of_
subsectors candidates may pass. On a day with 4 confirmed energy sub-industries,
12 candidates all representing energy can appear in a single report.

Fix: after rank_candidates() returns final_companies, apply a second deduplication
pass at industry level. Keep the top 2 candidates per industry subgroup, sorted by
composite_confidence primary and r3m (3-month momentum, confirmed key in mtf dict)
secondary. This operates on the already-ranked output of zscore_ranker and does not
touch the ranking logic itself.

The industry value is available in every candidate dict as
candidate['financials']['industry'] — confirmed present from financial_parser.py
output. Access it with .get() via candidate.get('financials', {}).get('industry', 'Unknown').

### Problem 2 — No commodity context for Energy sector
Root cause: the system infers energy sector strength through news, ETF signal, and
price momentum. WTI crude (CL=F) and natural gas (NG=F) prices are not consulted.
On rotation-driven days, energy stocks may score well without genuine commodity
support. Researchers have no signal about commodity momentum in the report.

Fix: create reports/commodity_signal.py as a standalone utility. Fetch 5-day returns
for CL=F and NG=F via yfinance. Classify each as positive/neutral/negative.
Return a plain English summary string.

For intraday reports: pass commodity_summary as a new template variable in
report_builder.py. Inject it into the story block of intraday_email.html and
intraday_full.html after the existing story_sentences loop ends.

For closing reports: the closing templates use a what_moved list built by
_build_what_moved_today() in summary_builder.py. Inject the commodity signal
as a sentence appended to that list inside _build_what_moved_today(). Do not
modify closing_email.html or closing_full.html.

The commodity_signal fetch must be called once per run and the result reused.
It must not affect any score.

### Problem 3 — No same-day score stability check
Root cause: each slot run is fully independent. A candidate with a declining
composite_confidence score from slot to slot is shown in every slot regardless.
State is already persisted between runs but per-ticker confidence scores are not
stored.

Fix: at the end of Step 32 in main.py, save the current slot's per-ticker
confidence scores to state['today_scores'] as a dict mapping ticker -> float.
This overwrites the previous slot's scores — that is intentional. Only the most
recent prior slot score is needed for comparison.

At the start of candidate output (after deduplication, before report build),
load today_prior_scores from state.get('today_scores', {}). For each candidate:
- If ticker not in today_prior_scores: first appearance, always allow.
- If current composite_confidence >= prior score: stable or improving, allow.
- If current composite_confidence < prior score: suppressed, log at INFO level.

State resets automatically at the start of each new trading day via the existing
load_state() logic in state_manager.py — no additional reset logic is needed.

---

## §FIX 1 — New commodity signal utility

File: reports/commodity_signal.py (CREATE this file — it does not exist)

```python
"""
reports/commodity_signal.py
Fetches 5-day momentum for WTI crude (CL=F) and natural gas (NG=F) via yfinance.
Returns a plain English summary string for report injection.
Does not modify any score. Fails silently — returns empty string on any error.
"""

import yfinance as yf
from utils.logger import get_logger

log = get_logger('commodity_signal')


def get_commodity_signal() -> dict:
    """
    Returns:
        crude_trend: 'positive' | 'neutral' | 'negative'
        gas_trend:   'positive' | 'neutral' | 'negative'
        crude_pct:   float  (5-day return %)
        gas_pct:     float
        summary:     str    (plain English, empty string on failure)
    """
    default = {
        'crude_trend': 'neutral',
        'gas_trend':   'neutral',
        'crude_pct':   0.0,
        'gas_pct':     0.0,
        'summary':     '',
    }

    try:
        crude_hist = yf.Ticker('CL=F').history(period='7d')
        gas_hist   = yf.Ticker('NG=F').history(period='7d')

        if crude_hist.empty or len(crude_hist) < 2:
            log.warning('commodity_signal: CL=F history empty or insufficient')
            return default

        if gas_hist.empty or len(gas_hist) < 2:
            log.warning('commodity_signal: NG=F history empty or insufficient')
            return default

        crude_pct = round(
            (crude_hist['Close'].iloc[-1] - crude_hist['Close'].iloc[0])
            / crude_hist['Close'].iloc[0] * 100,
            1,
        )
        gas_pct = round(
            (gas_hist['Close'].iloc[-1] - gas_hist['Close'].iloc[0])
            / gas_hist['Close'].iloc[0] * 100,
            1,
        )

        def classify(pct: float) -> str:
            if pct >= 1.5:
                return 'positive'
            if pct <= -1.5:
                return 'negative'
            return 'neutral'

        crude_trend = classify(crude_pct)
        gas_trend   = classify(gas_pct)

        parts = []
        if crude_trend == 'positive':
            parts.append(f'WTI crude up {crude_pct}% over 5 days')
        elif crude_trend == 'negative':
            parts.append(f'WTI crude down {abs(crude_pct)}% over 5 days')
        else:
            parts.append(f'WTI crude flat ({crude_pct:+.1f}%)')

        if gas_trend == 'positive':
            parts.append(f'natural gas up {gas_pct}% over 5 days')
        elif gas_trend == 'negative':
            parts.append(f'natural gas down {abs(gas_pct)}% over 5 days')
        else:
            parts.append(f'natural gas flat ({gas_pct:+.1f}%)')

        summary = 'Commodity momentum: ' + ' · '.join(parts) + '.'
        log.debug(f'commodity_signal: {summary}')

        return {
            'crude_trend': crude_trend,
            'gas_trend':   gas_trend,
            'crude_pct':   crude_pct,
            'gas_pct':     gas_pct,
            'summary':     summary,
        }

    except Exception as e:
        log.error(f'commodity_signal: failed — {e}')
        return default
```

---

## §FIX 2 — Inject commodity signal in report_builder.py

File: reports/report_builder.py

### 2a — Add import at top of file

Find this existing import block (it is already present):
```python
from utils.logger import get_logger
```

Add directly below it:
```python
from reports.commodity_signal import get_commodity_signal
```

### 2b — Fetch commodity signal once in build_intraday_report()

Inside build_intraday_report(), find this existing block:
```python
    # ── Story sentences ───────────────────────────────────────────────────
    confirmed_sectors = list({c['sector'] for c in companies})
    story_sentences   = _build_story_sentences(all_articles, sector_scores, confirmed_sectors)
```

Add the commodity fetch immediately after it:
```python
    # ── Commodity signal (Energy context, narrative only) ─────────────────
    commodity_summary = ''
    if any(c.get('sector') == 'Energy' for c in companies):
        commodity_summary = get_commodity_signal().get('summary', '')
```

### 2c — Add commodity_summary to both template context dicts

Find the email template context dict. It currently ends with:
```python
            total_companies  = n_found,
        )
```

The full render call for email_tpl starts with:
```python
        email_html = email_tpl.render(
            subject          = subject,
```

Add `commodity_summary` to this dict:
```python
        email_html = email_tpl.render(
            subject          = subject,
            slot             = slot,
            date_str         = date_str,
            time_str         = time_str,
            pulse_lines      = pulse_lines,
            story_sentences  = story_sentences,
            low_risk         = email_low,
            moderate_risk    = email_mod,
            overflow_notice  = overflow_notice,
            regime_label     = regime.get('label', 'Normal market'),
            breadth_label    = breadth.get('label', 'neutral'),
            disclaimer       = DISCLAIMER,
            total_companies  = n_found,
            commodity_summary = commodity_summary,
        )
```

Find the full browser template render call for full_tpl. It currently ends with:
```python
            rotation         = rotation,
        )
```

Add `commodity_summary` to this dict:
```python
        full_html = full_tpl.render(
            subject          = subject,
            slot             = slot,
            date_str         = date_str,
            time_str         = time_str,
            pulse_lines      = pulse_lines,
            story_sentences  = story_sentences,
            low_risk         = full_low,
            moderate_risk    = full_mod,
            regime_label     = regime.get('label', 'Normal market'),
            breadth_label    = breadth.get('label', 'neutral'),
            disclaimer       = DISCLAIMER,
            total_companies  = n_found,
            rotation         = rotation,
            commodity_summary = commodity_summary,
        )
```

---

## §FIX 3 — Inject commodity block in intraday_email.html

File: reports/templates/intraday_email.html

Find this exact block (lines 71-77 in current file):
```html
  <!-- Today's Story -->
  <div class="story">
    <p><em>Today's story</em></p>
    {% for s in story_sentences %}
    <p>{{ s }}</p>
    {% endfor %}
  </div>
```

Replace with:
```html
  <!-- Today's Story -->
  <div class="story">
    <p><em>Today's story</em></p>
    {% for s in story_sentences %}
    <p>{{ s }}</p>
    {% endfor %}
    {% if commodity_summary %}
    <p style="color:#8888aa;font-style:italic">{{ commodity_summary }}</p>
    {% endif %}
  </div>
```

---

## §FIX 4 — Inject commodity block in intraday_full.html

File: reports/templates/intraday_full.html

Find the story block. It contains:
```html
    {% for s in story_sentences %}
```

Locate the closing `{% endfor %}` of that loop. The full block looks like:
```html
    {% for s in story_sentences %}
    ...
    {% endfor %}
```

Add the commodity conditional immediately after the `{% endfor %}`:
```html
    {% for s in story_sentences %}
    <p>{{ s }}</p>
    {% endfor %}
    {% if commodity_summary %}
    <p style="color:#8888aa;font-style:italic">{{ commodity_summary }}</p>
    {% endif %}
```

Do not modify any other part of intraday_full.html.

---

## §FIX 5 — Inject commodity signal in summary_builder.py

File: reports/summary_builder.py

IMPORTANT: Only _build_what_moved_today() may be modified. No other function
in summary_builder.py may be touched.

### 5a — Add import at top of summary_builder.py

Find the existing import block at the top of the file. Add:
```python
from reports.commodity_signal import get_commodity_signal
```

### 5b — Modify _build_what_moved_today() to append commodity signal

Find _build_what_moved_today(). Its current signature is:
```python
def _build_what_moved_today(state: dict, sector_scores: dict) -> list[str]:
```

At the end of this function, before the `return sentences[:5]` line, add:

```python
    # Commodity signal — append if Energy was active today
    reported = state.get('reported_companies', [])
    energy_tickers = ['XOM', 'CVX', 'COP', 'DVN', 'EOG', 'EQT', 'CTRA',
                      'RRC', 'AR', 'CNX', 'KMI', 'SM', 'APA']
    energy_reported = any(t in reported for t in energy_tickers)
    if energy_reported:
        try:
            commodity_summary = get_commodity_signal().get('summary', '')
            if commodity_summary:
                sentences.append(commodity_summary)
        except Exception as _ce:
            log.warning(f'commodity_signal in closing report failed: {_ce}')
```

The return statement stays unchanged: `return sentences[:5]`

NOTE: The energy_tickers list above is a heuristic. A more robust approach is
to check state.get('sector_scores_today', {}) for any key containing 'Energy'
with a score above 0. If the agent prefers that approach, it is equally valid.
The critical requirement is that the commodity signal is only added when energy
was active — do not add it unconditionally.

---

## §FIX 6 — Add today_scores to DEFAULT_STATE in state_manager.py

File: utils/state_manager.py

Find DEFAULT_STATE dict. It currently ends with:
```python
    'indices_today':            {},
```

Add one key after it:
```python
    'indices_today':            {},
    'today_scores':             {},
```

No other change to state_manager.py.

---

## §FIX 7 — Industry deduplication in main.py (after Step 27)

File: main.py

Find this block in main.py (Step 27, confirmed existing code):
```python
    # ── Step 27: Z-score ranking ──────────────────────────────────────────
    from analyzers.zscore_ranker import rank_candidates
    for _c in all_candidates:
        log.info(f"DEBUG candidate: {_c.get('ticker')} risk={_c.get('risk_score')} opp={_c.get('opportunity_score')} cap={regime['risk_cap']}")
    final_companies = rank_candidates(all_candidates, regime['risk_cap'])
    log.info(f'Final company count: {len(final_companies)}')
```

Replace with:
```python
    # ── Step 27: Z-score ranking ──────────────────────────────────────────
    from analyzers.zscore_ranker import rank_candidates
    from collections import defaultdict
    for _c in all_candidates:
        log.info(f"DEBUG candidate: {_c.get('ticker')} risk={_c.get('risk_score')} opp={_c.get('opportunity_score')} cap={regime['risk_cap']}")
    ranked_companies = rank_candidates(all_candidates, regime['risk_cap'])
    log.info(f'Post-ranking count: {len(ranked_companies)}')

    # ── Step 27b: Within-industry deduplication ───────────────────────────
    # Keep top 2 per industry subgroup.
    # Sort by composite_confidence (primary) then r3m from mtf dict (secondary).
    # Industry key is in candidate['financials']['industry'] — access via .get().
    industry_groups: dict = defaultdict(list)
    for _c in ranked_companies:
        _industry = _c.get('financials', {}).get('industry', 'Unknown')
        industry_groups[_industry].append(_c)

    deduplicated: list = []
    for _industry, _group in industry_groups.items():
        _sorted = sorted(
            _group,
            key=lambda c: (
                c.get('composite_confidence', 0),
                c.get('mtf', {}).get('r3m', 0) or 0,
            ),
            reverse=True,
        )
        deduplicated.extend(_sorted[:2])
        _kept = [c.get('ticker') for c in _sorted[:2]]
        _dropped = [c.get('ticker') for c in _sorted[2:]]
        if _dropped:
            log.info(f'Industry dedup [{_industry}]: kept={_kept} dropped={_dropped}')

    # Re-sort by composite_confidence to restore overall ranking order
    deduplicated.sort(key=lambda c: c.get('composite_confidence', 0), reverse=True)

    final_companies = deduplicated
    log.info(f'Final company count after industry dedup: {len(final_companies)}')
```

---

## §FIX 8 — Score stability filter in main.py (after deduplication)

File: main.py

This block must be inserted immediately after §FIX 7 — after the line:
```python
    log.info(f'Final company count after industry dedup: {len(final_companies)}')
```

Add:
```python
    # ── Step 27c: Score stability filter ─────────────────────────────────
    # First appearance today: always allowed.
    # Subsequent appearance: current confidence must be >= prior slot confidence.
    # today_prior_scores is populated from state at load time (see §FIX 9).
    today_prior_scores = state.get('today_scores', {})
    stable_companies: list = []
    for _c in final_companies:
        _ticker       = _c.get('ticker', '')
        _current_conf = _c.get('composite_confidence', 0)
        _prior_conf   = today_prior_scores.get(_ticker)

        if _prior_conf is None:
            stable_companies.append(_c)
            log.debug(f'score_stability: {_ticker} first appearance — allowed (score {_current_conf})')
        elif _current_conf >= _prior_conf:
            stable_companies.append(_c)
            log.debug(f'score_stability: {_ticker} stable/improving ({_prior_conf} -> {_current_conf}) — allowed')
        else:
            log.info(f'score_stability: {_ticker} suppressed — score declined ({_prior_conf} -> {_current_conf})')

    final_companies = stable_companies
    log.info(f'Final company count after score stability filter: {len(final_companies)}')
```

---

## §FIX 9 — Save today_scores at Step 32 in main.py

File: main.py

Find Step 32 (state save at end of run). It currently reads:
```python
    # ── Step 32: Update state ─────────────────────────────────────────────
    tickers_reported = [c['ticker'] for c in final_companies]
    state = add_reported_companies(state, tickers_reported)
    state['runs'][slot]['companies'] = tickers_reported
    state = mark_slot_complete(state, slot)
    save_state(state)
```

Replace with:
```python
    # ── Step 32: Update state ─────────────────────────────────────────────
    tickers_reported = [c['ticker'] for c in final_companies]
    state = add_reported_companies(state, tickers_reported)
    state['runs'][slot]['companies'] = tickers_reported

    # Save current slot's per-ticker confidence scores for next slot's
    # score stability filter. Overwrites previous slot — intentional.
    state['today_scores'] = {
        c.get('ticker', ''): c.get('composite_confidence', 0)
        for c in final_companies
        if c.get('ticker')
    }

    state = mark_slot_complete(state, slot)
    save_state(state)
```

---

## §VERIFY — Confirming correct implementation

1. Run the system on a day when Energy sector dominates. The output should show
   at most 2 candidates per industry subgroup. Check logs for lines containing
   'Industry dedup' to confirm the filter fired.

2. In the intraday email and full browser reports, the Today's Story section
   should contain a commodity momentum line when Energy candidates are present.
   Verify the line appears inside the story div, after the sector sentences,
   and not inside any company card.

3. In the closing report (16:10), the What Moved The Market Today section should
   contain the commodity signal sentence when energy tickers were reported today.
   Verify closing_email.html and closing_full.html templates were NOT modified.

4. On the second slot of the day (12:30), check logs for lines containing
   'score_stability'. Candidates with stable or improving scores should log
   'allowed'. Any candidate whose confidence dropped should log 'suppressed'.

5. Check state/daily_state.json after a run. It must contain a 'today_scores'
   key with ticker -> float entries for the current slot's companies.

6. The disclaimer must appear exactly once per report. Verify it has not been
   duplicated anywhere.

7. The SUMMARY block inside individual company cards must be unchanged.
   Commodity signal must not appear inside any company card — only in the
   story/what_moved section.

8. Confirm that closing_email.html and closing_full.html were not modified.
   The commodity injection for closing reports goes through summary_builder.py
   only.

---

## §PALETTE

No new CSS is required. The commodity signal line uses inline style:
`style="color:#8888aa;font-style:italic"` in the intraday templates.
This matches the existing story section color scheme and requires no changes
to docs/assets/style.css or any template stylesheet block.

---

## §DISCLAIMER

The disclaimer already exists in the system. It renders correctly in all
report templates and in the fallback email writer. It must not be added,
duplicated, or moved anywhere in this implementation. The agent must not
insert any new disclaimer text in any file.

---

## Footer

**Scope:** output layer improvements and candidate assembly logic only.
**Analytical engine:** untouched.
**Scoring formula:** untouched.
**zscore_ranker.py:** untouched — deduplication happens after its output.

**Files created (1):**
- reports/commodity_signal.py

**Files modified (6):**
- reports/report_builder.py (import + commodity fetch + 2 context dict additions)
- reports/templates/intraday_email.html (commodity block in story section)
- reports/templates/intraday_full.html (commodity block in story section)
- reports/summary_builder.py (_build_what_moved_today() only)
- utils/state_manager.py (DEFAULT_STATE addition only)
- main.py (Steps 27b, 27c, 32)

**Files explicitly protected:** all files listed in §DONOT.

**Changelog from V8:**
- NEW: within-industry deduplication — top 2 per industry by composite_confidence + r3m, applied after zscore_ranker output, before report build
- NEW: commodity momentum signal — WTI crude and natural gas 5-day return, injected into Today's Story (intraday) and What Moved Today (closing), narrative only, no score changes
- NEW: same-day score stability filter — suppresses candidates whose composite_confidence declined from prior slot, first appearance always allowed
- NEW: today_scores persisted in state between slots for stability comparison
- NO changes to any scoring module, ranking module, analytical engine, or infrastructure
