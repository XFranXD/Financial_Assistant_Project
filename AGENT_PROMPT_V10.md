# AGENT_PROMPT_V10.md
# Delta document against confirmed working V9 codebase.
# This is NOT a rewrite. Apply only what is specified here.
# AGENT_PROGRESS.md must be updated BEFORE and AFTER every file touched.
# Format: "NOW WORKING ON filename" before. "COMPLETED filename" after.

---

## §ORDER — Implementation sequence

Execute in this exact order. Do not reorder.

1. reports/sentence_templates.py         — add new COMPANY_INTRO variants and TODAY_STORY_SENTENCE improvement
2. reports/report_builder.py             — update _build_story_sentences() and _enrich_company_for_template()
3. reports/templates/intraday_email.html — add industry subgroup to card header
4. reports/templates/intraday_full.html  — add industry subgroup to card header

Steps 3 and 4 are independent of each other.
Steps 3 and 4 depend on step 2 completing first (new template variable must exist before templates use it).

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
reports/commodity_signal.py
reports/summary_builder.py
reports/email_builder.py
reports/email_sender.py
reports/dashboard_builder.py
reports/templates/closing_email.html
reports/templates/closing_full.html
utils/state_manager.py
utils/logger.py
utils/retry.py
docs/index.html
docs/rank.html
docs/guide.html
docs/assets/style.css
docs/assets/app.js
scripts/cleanup_reports.py
.github/workflows/market_scan.yml
.github/workflows/cleanup.yml
config.py
main.py
validate_tickers.py
data/event_keywords.json
data/event_to_sector.json
data/sector_momentum_history.json
data/plain_english_terms.json
data/sector_etfs.json
data/sector_breadth_stocks.json
data/sector_tickers.json
data/sector_tickers_validated.json

---

## §CONTEXT — What is wrong and why

### Problem 1 — Industry subgroup not visible to user
Root cause: the candidate dict stores `financials['industry']` (confirmed key from
financial_parser.py) but the templates only display `sector_plain`. After V9's
industry deduplication, each card represents a distinct industry subgroup, but the
user sees only "Energy" for every card. The diversity the dedup creates is invisible.

Fix: add a new display field `industry_label` to the enriched candidate dict in
report_builder.py. Populate it from `candidate['financials']['industry']` with a
safe .get() fallback. Pass it to both intraday templates and render it in the card
header next to sector_plain.

### Problem 2 — Commodity signal shows data but no interpretation
Root cause: commodity_signal.py returns raw trend labels and a summary string that
lists the numbers but does not connect them to the candidates. On a day when gas
producers are surfaced but natural gas is down, the researcher sees the tension in
the data but the system does not name it.

Fix: in report_builder.py, after the commodity signal is fetched, add a second
interpretation sentence when there is a mismatch between candidate industry and
commodity trend. Specifically: if gas producer candidates are present and gas_trend
is 'negative', append a plain English interpretation sentence. If oil producer
candidates are present and crude_trend is 'negative', append a similar sentence.
This logic lives entirely in report_builder.py and does not touch commodity_signal.py.

### Problem 3 — TODAY_STORY_SENTENCE is generic placeholder language
Root cause: the template `"{SECTOR_PLAIN} stocks are {DIRECTION_PLAIN} today
following news about {EVENT_PLAIN}."` always resolves EVENT_PLAIN to
'recent market developments' or 'detected market news' because the event_type
lookup in _build_story_sentences() defaults to '_unknown' when no specific event
is matched. The result reads as boilerplate.

Fix: replace the EVENT_PLAIN fallback in _build_story_sentences() with a more
informative sentence that references the news signal count and sector score
rather than a vague event label. The sentence template in sentence_templates.py
needs a second variant for the case where no specific event type is known.

### Problem 4 — COMPANY_INTRO sentence is identical for every company
Root cause: render_company_intro() in sentence_templates.py uses a single fixed
template that only varies by sector and direction. Every company card produces the
same sentence. It reads as repetitive and gives no per-company information.

Fix: replace render_company_intro() with a function that selects one of several
template variants based on per-company data already available in the candidate dict
at enrichment time: confidence score tier, whether momentum is strong, whether
volume is elevated, and whether the stock is a sector leader by rank. This produces
meaningfully different sentences per company without free-text generation.

---

## §FIX 1 — New sentence templates in sentence_templates.py

File: reports/sentence_templates.py

### 1a — Replace COMPANY_INTRO with multiple variants

Find this exact block:
```python
COMPANY_INTRO = (
    "{COMPANY} appeared today because the {SECTOR} sector is seeing "
    "{DIRECTION} movement following news about {EVENT_PLAIN}."
)
```

Replace with:
```python
# Multiple intro variants — selected by report_builder based on per-company signals
COMPANY_INTRO_SECTOR_LEADER = (
    "{COMPANY} appeared today as a top-ranked {SECTOR} stock — "
    "strong sector momentum and its own price trend triggered the opportunity model."
)

COMPANY_INTRO_MOMENTUM = (
    "{COMPANY} appeared today because its upward price trend aligned with "
    "{SECTOR} sector strength detected in today's news signals."
)

COMPANY_INTRO_FUNDAMENTALS = (
    "{COMPANY} appeared today because solid fundamental signals combined with "
    "{SECTOR} sector momentum pushed it above the opportunity threshold."
)

COMPANY_INTRO_STANDARD = (
    "{COMPANY} appeared today because the {SECTOR} sector is seeing "
    "{DIRECTION} movement and this stock passed all screening gates."
)
```

### 1b — Add improved TODAY_STORY_SENTENCE variant

Find this exact block:
```python
TODAY_STORY_SENTENCE = (
    "{SECTOR_PLAIN} stocks are {DIRECTION_PLAIN} today following news about {EVENT_PLAIN}."
)
```

Replace with:
```python
TODAY_STORY_SENTENCE = (
    "{SECTOR_PLAIN} stocks are {DIRECTION_PLAIN} today following news about {EVENT_PLAIN}."
)

TODAY_STORY_SENTENCE_SIGNALS = (
    "{SECTOR_PLAIN} stocks are {DIRECTION_PLAIN} today — "
    "the sector scanner detected {SIGNAL_COUNT} news signals with a momentum score of {SECTOR_SCORE:.1f}."
)
```

---

## §FIX 2 — Update report_builder.py

File: reports/report_builder.py

### 2a — Update sentence_templates imports

Find the existing import block from sentence_templates. It currently imports
`TODAY_STORY_SENTENCE` and `render_company_intro` among others.

Add these to the import list from sentence_templates:
```python
    TODAY_STORY_SENTENCE_SIGNALS,
    COMPANY_INTRO_SECTOR_LEADER,
    COMPANY_INTRO_MOMENTUM,
    COMPANY_INTRO_FUNDAMENTALS,
    COMPANY_INTRO_STANDARD,
```

Remove `render_company_intro` from the import list — it will be replaced inline.

### 2b — Replace _build_story_sentences() entirely

Find the entire _build_story_sentences() function. It currently starts with:
```python
def _build_story_sentences(all_articles: list, sector_scores: dict, confirmed_sectors: list) -> list[str]:
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
        score_data    = sector_scores.get(sector, {})
        score_val     = score_data.get('score', 0)
        direction     = 'positive' if score_val >= 0 else 'negative'
        direction_plain = DIRECTION_PLAIN.get(direction, 'moving')
        sector_plain  = render_sector_plain(sector)

        # Count how many articles mention this sector
        sector_keyword = sector.replace('_', ' ')
        signal_count = sum(
            1 for a in all_articles
            if sector_keyword in (a.get('title', '') + ' ' + a.get('summary', '')).lower()
            or sector in (a.get('title', '') + ' ' + a.get('summary', '')).lower()
        )

        # Use signal-count variant when we have meaningful data, fallback otherwise
        if signal_count >= 2 and score_val > 0:
            sentences.append(TODAY_STORY_SENTENCE_SIGNALS.format(
                SECTOR_PLAIN  = sector_plain,
                DIRECTION_PLAIN = direction_plain,
                SIGNAL_COUNT  = signal_count,
                SECTOR_SCORE  = score_val,
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

### 2c — Replace intro sentence logic in _enrich_company_for_template()

Find this block inside _enrich_company_for_template():
```python
    # Company intro
    company_name = c.get('company_name', c.get('ticker', ''))
    intro = render_company_intro(company_name, sector, direction, event_type)
```

Replace with:
```python
    # Company intro — variant selected by per-company signals
    company_name = c.get('company_name', c.get('ticker', ''))
    sector_plain_str = render_sector_plain(sector)
    final_rank   = c.get('final_rank', 99)
    conf_score_v = c.get('composite_confidence', 0)
    opp_score_v  = c.get('opportunity_score', 0)
    vol_ratio_v  = c.get('volume_confirmation', {}).get('volume_ratio', 1.0) or 1.0

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

### 2d — Add industry_label to enriched candidate dict

Find the return dict at the bottom of _enrich_company_for_template(). It starts with:
```python
    return {
        **c,
        'display_name':      company_name,
        'sector_plain':      render_sector_plain(sector),
```

Add `industry_label` to this dict:
```python
    return {
        **c,
        'display_name':      company_name,
        'sector_plain':      render_sector_plain(sector),
        'industry_label':    c.get('financials', {}).get('industry', ''),
```

### 2e — Add commodity interpretation sentence

Find this existing block in build_intraday_report():
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
        commodity_data = get_commodity_signal()
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
                commodity_summary = commodity_summary + ' ' + interpretation
```

---

## §FIX 3 — Add industry subgroup to intraday_email.html card header

File: reports/templates/intraday_email.html

Find this exact line in the LOW RISK card section:
```html
      <div class="card-name">■■■ {{ c.display_name }} <span class="tk">({{ c.ticker }})</span> — {{ c.sector_plain }} ■■■</div>
```

Replace with:
```html
      <div class="card-name">■■■ {{ c.display_name }} <span class="tk">({{ c.ticker }})</span> — {{ c.sector_plain }}{% if c.industry_label %} ({{ c.industry_label }}){% endif %} ■■■</div>
```

Find this exact line in the MODERATE RISK card section:
```html
      <div class="card-name">■■ {{ c.display_name }} <span class="tk">({{ c.ticker }})</span> — {{ c.sector_plain }} ■■</div>
```

Replace with:
```html
      <div class="card-name">■■ {{ c.display_name }} <span class="tk">({{ c.ticker }})</span> — {{ c.sector_plain }}{% if c.industry_label %} ({{ c.industry_label }}){% endif %} ■■</div>
```

---

## §FIX 4 — Add industry subgroup to intraday_full.html card header

File: reports/templates/intraday_full.html

Find this exact line in the LOW RISK card section:
```html
        <div class="card-title">{{ c.display_name }} <span class="tk">({{ c.ticker }})</span><span class="sec">— {{ c.sector_plain }}</span></div>
```

Replace with:
```html
        <div class="card-title">{{ c.display_name }} <span class="tk">({{ c.ticker }})</span><span class="sec">— {{ c.sector_plain }}{% if c.industry_label %} ({{ c.industry_label }}){% endif %}</span></div>
```

Find the same pattern in the MODERATE RISK card section and apply the same replacement.

---

## §VERIFY — Confirming correct implementation

1. Run the system with energy sector candidates present. The card header should show:
   `CTRA (CTRA) — Energy (Oil & Gas Exploration & Production)`
   or similar industry string from yfinance. Verify it appears for all cards.

2. If industry_label is empty string for any candidate (yfinance returned no industry),
   the `{% if c.industry_label %}` conditional silently suppresses it. No crash,
   no blank parentheses rendered. Verify this is the behavior when industry is absent.

3. The Today's Story sentence should now read approximately:
   `Energy stocks are moving higher today — the sector scanner detected N news
   signals with a momentum score of X.`
   Verify the signal count and score values are non-zero and plausible.

4. The company intro sentence should differ between the #1 ranked company and
   lower-ranked companies. Verify CTRA (rank 1) gets the SECTOR_LEADER variant
   and EQT/KMI get different variants based on their scores.

5. On a day with gas producers present and negative natural gas trend, the commodity
   summary line should include the interpretation sentence after the raw numbers.
   Verify it appears only when the mismatch condition is true, not unconditionally.

6. The disclaimer must appear exactly once per report. Verify it has not been
   duplicated.

7. Confirm closing_email.html, closing_full.html, and main.py were not modified.

---

## §PALETTE

No CSS changes required. The industry label renders inline inside existing card
header elements and inherits their styles. No new classes needed.

---

## §DISCLAIMER

The disclaimer already exists in the system and renders correctly in all report
templates. It must not be added, duplicated, or moved anywhere in this
implementation.

---

## Footer

**Scope:** output layer only — sentence templates, report builder enrichment logic,
and two intraday HTML templates.
**Analytical engine:** untouched.
**Scoring formula:** untouched.
**main.py:** untouched.

**Files modified (4):**
- reports/sentence_templates.py (new COMPANY_INTRO variants, new TODAY_STORY variant)
- reports/report_builder.py (story sentences, intro logic, industry_label, commodity interpretation)
- reports/templates/intraday_email.html (industry label in card headers)
- reports/templates/intraday_full.html (industry label in card headers)

**Files explicitly protected:** all files listed in §DONOT.

**Changelog from V9:**
- NEW: industry subgroup label displayed in card headers for both intraday templates
- NEW: per-company intro sentence now varies by rank, opportunity score, and momentum — no longer identical for all companies
- NEW: Today's Story sentence now references actual signal count and sector score when available
- NEW: commodity signal appends plain English interpretation when candidate industry conflicts with commodity trend direction
- NO changes to analytical engine, scoring, ranking, state, or infrastructure
