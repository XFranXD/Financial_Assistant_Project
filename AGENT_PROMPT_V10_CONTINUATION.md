# AGENT_PROMPT_V10_CONTINUATION.md
# Continuation of V10 — picks up where the previous agent session ended.
# sentence_templates.py is COMPLETE and CORRECT — do not touch it.
# Apply only the four remaining items listed below.
# AGENT_PROGRESS.md must be updated BEFORE and AFTER every file touched.
# Format: "NOW WORKING ON filename" before. "COMPLETED filename" after.

---

## §WHAT WAS ALREADY DONE — DO NOT REDO

sentence_templates.py is fully implemented and verified. It contains:
- COMPANY_INTRO_SECTOR_LEADER
- COMPANY_INTRO_MOMENTUM
- COMPANY_INTRO_FUNDAMENTALS
- COMPANY_INTRO_STANDARD
- TODAY_STORY_SENTENCE_SIGNALS

Do not modify sentence_templates.py under any circumstances.

The imports in report_builder.py already include all new template names.
Do not add or remove any imports from report_builder.py.

---

## §ORDER — Remaining implementation sequence

Execute in this exact order.

1. reports/report_builder.py   — §FIX 2b: replace _build_story_sentences() body
2. reports/report_builder.py   — §FIX 2c: replace intro logic in _enrich_company_for_template()
3. reports/report_builder.py   — §FIX 2d: add industry_label to enriched candidate return dict
4. reports/report_builder.py   — §FIX 2e: add commodity interpretation sentence
5. reports/templates/intraday_email.html  — §FIX 3: add industry_label to card headers
6. reports/templates/intraday_full.html   — §FIX 4: add industry_label to card headers

All four report_builder.py changes (steps 1-4) must be completed before
touching either template file.

---

## §DONOT — Files that must not be touched

reports/sentence_templates.py   ← ALREADY COMPLETE
reports/commodity_signal.py
reports/summary_builder.py
reports/email_builder.py
reports/email_sender.py
reports/dashboard_builder.py
reports/templates/closing_email.html
reports/templates/closing_full.html
analyzers/ (all files)
filters/candidate_filter.py
collectors/ (all files)
utils/ (all files)
main.py
config.py
validate_tickers.py
docs/ (all files)
data/ (all files)
scripts/ (all files)
.github/ (all files)

---

## §FIX 2b — Replace _build_story_sentences() in report_builder.py

The current function body still uses the old V8 logic with EVENT_PLAIN lookup.
Replace the ENTIRE function body with the following.
The function signature does not change.

Find this exact function (starts with):
```python
def _build_story_sentences(all_articles: list, sector_scores: dict, confirmed_sectors: list) -> list[str]:
    """
    Generates 2-3 plain English sentences describing today's market story.
    Uses TODAY_STORY_SENTENCE template. No free text.
    """
```

Replace the entire function with:
```python
def _build_story_sentences(all_articles: list, sector_scores: dict, confirmed_sectors: list) -> list[str]:
    """
    Generates plain English sentences describing today's market story.
    Uses signal count and sector score when no specific event type is matched.
    """
    sentences = []
    seen_sectors = set()

    for sector in confirmed_sectors[:3]:
        if sector in seen_sectors:
            continue
        seen_sectors.add(sector)
        score_data      = sector_scores.get(sector, {})
        score_val       = score_data.get('score', 0)
        direction       = 'positive' if score_val >= 0 else 'negative'
        direction_plain = DIRECTION_PLAIN.get(direction, 'moving')
        sector_plain    = render_sector_plain(sector)

        # Count articles that mention this sector
        sector_keyword = sector.replace('_', ' ')
        signal_count = sum(
            1 for a in all_articles
            if sector_keyword in (a.get('title', '') + ' ' + a.get('summary', '')).lower()
            or sector in (a.get('title', '') + ' ' + a.get('summary', '')).lower()
        )

        # Use signal-count variant when we have meaningful data, fallback otherwise
        if signal_count >= 2 and score_val > 0:
            sentences.append(TODAY_STORY_SENTENCE_SIGNALS.format(
                SECTOR_PLAIN    = sector_plain,
                DIRECTION_PLAIN = direction_plain,
                SIGNAL_COUNT    = signal_count,
                SECTOR_SCORE    = score_val,
            ))
        else:
            sentences.append(TODAY_STORY_SENTENCE.format(
                SECTOR_PLAIN    = sector_plain,
                DIRECTION_PLAIN = direction_plain,
                EVENT_PLAIN     = 'positive sector news signals',
            ))

    if not sentences:
        sentences.append(
            'Market conditions were monitored across all sectors today. '
            'See company details below for specific research opportunities.'
        )
    return sentences
```

---

## §FIX 2c — Replace intro logic in _enrich_company_for_template()

Find this exact block inside _enrich_company_for_template():
```python
    # Company intro
    company_name = c.get('company_name', c.get('ticker', ''))
    intro = render_company_intro(company_name, sector, direction, event_type)
```

Replace with:
```python
    # Company intro — variant selected by per-company signals
    company_name     = c.get('company_name', c.get('ticker', ''))
    sector_plain_str = render_sector_plain(sector)
    final_rank       = c.get('final_rank', 99)
    conf_score_v     = c.get('composite_confidence', 0)
    opp_score_v      = c.get('opportunity_score', 0)

    if final_rank == 1:
        intro = COMPANY_INTRO_SECTOR_LEADER.format(
            COMPANY = company_name,
            SECTOR  = sector_plain_str,
        )
    elif opp_score_v >= 70 and conf_score_v >= 65:
        intro = COMPANY_INTRO_FUNDAMENTALS.format(
            COMPANY = company_name,
            SECTOR  = sector_plain_str,
        )
    elif c.get('ram', {}).get('raw_value', 0) and c.get('ram', {}).get('raw_value', 0) > 1:
        intro = COMPANY_INTRO_MOMENTUM.format(
            COMPANY = company_name,
            SECTOR  = sector_plain_str,
        )
    else:
        intro = COMPANY_INTRO_STANDARD.format(
            COMPANY   = company_name,
            SECTOR    = sector_plain_str,
            DIRECTION = DIRECTION_PLAIN.get(direction, 'moving'),
        )
```

---

## §FIX 2d — Add industry_label to enriched candidate return dict

Find the return dict at the bottom of _enrich_company_for_template().
It starts with:
```python
    return {
        **c,
        'display_name':      company_name,
        'sector_plain':      render_sector_plain(sector),
```

Add industry_label as the third key:
```python
    return {
        **c,
        'display_name':      company_name,
        'sector_plain':      render_sector_plain(sector),
        'industry_label':    c.get('financials', {}).get('industry', ''),
```

Do not change any other key in the return dict.

---

## §FIX 2e — Add commodity interpretation sentence

Find this exact block in build_intraday_report():
```python
    # ── Commodity signal (Energy context, narrative only) ─────────────────
    commodity_summary = ''
    if any(c.get('sector') == 'energy' for c in companies):
        commodity_summary = get_commodity_signal().get('summary', '')
```

Replace with:
```python
    # ── Commodity signal (Energy context, narrative only) ─────────────────
    commodity_summary = ''
    if any(c.get('sector') == 'energy' for c in companies):
        commodity_data    = get_commodity_signal()
        commodity_summary = commodity_data.get('summary', '')

        # Interpretation: flag mismatch between commodity trend and candidate industries
        if commodity_summary:
            industries_present = [
                c.get('financials', {}).get('industry', '').lower()
                for c in companies if c.get('sector') == 'energy'
            ]
            gas_producers_present = any(
                'gas' in ind for ind in industries_present
            )
            oil_producers_present = any(
                'oil' in ind or 'exploration' in ind or 'crude' in ind
                for ind in industries_present
            )

            interpretation = ''
            if gas_producers_present and commodity_data.get('gas_trend') == 'negative':
                interpretation = (
                    'Note: natural gas prices are declining — '
                    'gas producer strength may reflect sector rotation rather than commodity support.'
                )
            elif oil_producers_present and commodity_data.get('crude_trend') == 'negative':
                interpretation = (
                    'Note: WTI crude is declining — '
                    'oil producer strength may reflect sector rotation rather than commodity support.'
                )

            if interpretation:
                commodity_summary += ' ' + interpretation
```

---

## §FIX 3 — Add industry_label to intraday_email.html card headers

File: reports/templates/intraday_email.html

There are two card header lines to update — one in LOW RISK section, one in
MODERATE RISK section.

Find this exact line (LOW RISK section):
```html
      <div class="card-name">■■■ {{ c.display_name }} <span class="tk">({{ c.ticker }})</span> — {{ c.sector_plain }} ■■■</div>
```

Replace with:
```html
      <div class="card-name">■■■ {{ c.display_name }} <span class="tk">({{ c.ticker }})</span> — {{ c.sector_plain }}{% if c.industry_label %} ({{ c.industry_label }}){% endif %} ■■■</div>
```

Find this exact line (MODERATE RISK section):
```html
      <div class="card-name">■■ {{ c.display_name }} <span class="tk">({{ c.ticker }})</span> — {{ c.sector_plain }} ■■</div>
```

Replace with:
```html
      <div class="card-name">■■ {{ c.display_name }} <span class="tk">({{ c.ticker }})</span> — {{ c.sector_plain }}{% if c.industry_label %} ({{ c.industry_label }}){% endif %} ■■</div>
```

---

## §FIX 4 — Add industry_label to intraday_full.html card headers

File: reports/templates/intraday_full.html

There are two card header lines to update — one in LOW RISK section, one in
MODERATE RISK section. Both use the same pattern.

Find this exact line (appears twice, once per section):
```html
        <div class="card-title">{{ c.display_name }} <span class="tk">({{ c.ticker }})</span><span class="sec">— {{ c.sector_plain }}</span></div>
```

Replace both occurrences with:
```html
        <div class="card-title">{{ c.display_name }} <span class="tk">({{ c.ticker }})</span><span class="sec">— {{ c.sector_plain }}{% if c.industry_label %} ({{ c.industry_label }}){% endif %}</span></div>
```

---

## §VERIFY — Confirming correct implementation

1. Run the system with energy sector candidates present. The Today's Story
   section should read approximately:
   "Energy stocks are moving higher today — the sector scanner detected N news
   signals with a momentum score of X."
   Verify N and X are non-zero plausible values.

2. The #1 ranked company card intro should read:
   "[TICKER] appeared today as a top-ranked Energy stock — strong sector momentum
   and its own price trend triggered the opportunity model."
   Lower-ranked companies should have different intro sentences.

3. The card header should show:
   "CTRA (CTRA) — Energy (Oil & Gas Exploration & Production)"
   or similar yfinance industry string. Verify it appears for all cards.
   If industry_label is empty for any candidate, verify no blank parentheses
   appear — the {% if %} guard must suppress it silently.

4. On a day with gas producers present and negative natural gas trend, the
   commodity line should include the interpretation sentence after the raw numbers.
   Verify it does not appear when no mismatch exists.

5. Confirm sentence_templates.py was not modified.
   Confirm main.py was not modified.
   Confirm closing_email.html and closing_full.html were not modified.

6. The disclaimer must appear exactly once per report.

---

## §DISCLAIMER

The disclaimer already exists in the system and renders correctly in all report
templates. It must not be added, duplicated, or moved anywhere in this
implementation.

---

## Footer

**Scope:** completion of V10 remaining items only.
**sentence_templates.py:** already complete — do not touch.
**Analytical engine:** untouched.
**main.py:** untouched.

**Files to modify (3):**
- reports/report_builder.py (four changes: 2b, 2c, 2d, 2e)
- reports/templates/intraday_email.html (two card header lines)
- reports/templates/intraday_full.html (two card header lines)

**Changelog — what this continuation adds to V10:**
- _build_story_sentences() replaced with signal-count aware version
- Per-company intro sentence now varies by rank, opportunity score, and momentum
- industry_label added to enriched candidate dict and rendered in card headers
- Commodity signal now appends plain English interpretation on trend mismatch
