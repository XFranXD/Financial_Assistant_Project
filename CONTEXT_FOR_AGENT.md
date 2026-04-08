# MRE System 5 — Phase 1 Agent Prompt
### 1A · 1B · 1C Implementation
---
## CONTEXT AND CONSTRAINTS
You are implementing Phase 1 of the MRE (Market Research Engine) — three additive layers to an existing, fully operational Python pipeline. The system runs on GitHub Actions free tier, serves GitHub Pages, uses only free APIs, and has zero ML, zero trading logic, and zero paid dependencies.
**Before writing a single line of code, read the following files in full:**
- `eq_analyzer/main.py`
- `main.py`
- `contracts/eq_schema.py`
- `contracts/price_structure_schema.py`
- `reports/report_builder.py`
- `reports/dashboard_builder.py`
- `analyzers/risk_model.py`
- `eq_analyzer/edgar_fetcher.py`
- `eq_analyzer/module_earnings_timing.py`
- `price_structure/level_detector.py`
- `price_structure/entry_classifier.py`
- `price_structure/price_structure_analyzer.py`
- `docs/assets/style.css`
**Required Imports** (add to each new module where needed):
- `requests`
- `time`
- `datetime` (use `datetime.timezone.utc` for comparisons)
- `json`
- `xml.etree.ElementTree as ET`
- `logging`
- `pathlib`
Do not modify any file not listed in the explicit "Files to modify" section for each layer. Do not rename, restructure, or refactor anything outside of what is specified. All three layers are additive — they stamp new keys onto existing candidate dicts and add new display paths without altering existing ones.
**Locked constraints carry through every file you touch:**
- `eq_schema.py` is single source of truth for all shared EQ and event-risk keys
- `price_structure_schema.py` (under `contracts/`) is single source of truth for all Sub4 display keys
- `dashboard_builder.py` is single source of truth for all dashboard HTML — never edit `docs/*.html` directly
- All new pipeline steps are non-fatal — wrap in try/except, log failures, continue
- No new paid APIs, no ML, no trading logic
---
## LAYER 1A — EVENT RISK LAYER
### What you are building
A new standalone module that classifies each candidate ticker as `NORMAL` or `HIGH RISK` based on proximity to earnings announcements and hardcoded macro events. This supersedes the existing `earnings_warning` bool for display purposes but does **not** remove `risk_model.py`'s score penalty — that stays untouched.
### New files to create
**`eq_analyzer/event_risk.py`**
Standalone module. No class required. Expose a single public function:
```python
def get_event_risk(ticker: str, finnhub_token: str) -> dict:
```
Return dict contract:
```python
{
    'event_risk':        'NORMAL' | 'HIGH RISK',   # primary gate field
    'event_risk_reason': str,                       # one-line human display string
    'days_to_earnings':  int | None,                # None if no upcoming date found
}
```
- Hit Finnhub earnings calendar endpoint: `https://finnhub.io/api/v1/calendar/earnings?from={today}&to={today+7d}&symbol={ticker}&token={finnhub_token}`
- **Expected response format:** `{"earningsCalendar": [{"date": "YYYY-MM-DD", ...}]}`
- If any earnings date is within 1–5 calendar days (inclusive): `event_risk = 'HIGH RISK'`, `event_risk_reason = 'Earnings in {N} day(s)'`, `days_to_earnings = N`
- If a macro event (from `macro_events.json`) also triggers `HIGH RISK` for this sector:
  - Keep `'Earnings in {N} day(s)'` as the primary reason.
  - Append the macro event description: `event_risk_reason = 'Earnings in {N} day(s) / {macro_desc}'`.
- If no earnings in range but macro event exists: `event_risk = 'HIGH RISK'`, `event_risk_reason = macro_desc`
- If neither exists: `event_risk = 'NORMAL'`, `event_risk_reason = ''`, `days_to_earnings = None`
- On any exception (network error, bad response, missing token): return `event_risk = 'NORMAL'`, log the error, do not raise.
**Macro event check logic:**
- Import the macro event list from `data/macro_events.json` (you will create this file)
- Check if today's date falls within 1 calendar day before any listed event
- If so: override `event_risk = 'HIGH RISK'`, append to `event_risk_reason`: `'Fed/CPI event in {N} day(s)'`
- Macro events are secondary — earnings check runs first, macro is additive
**`data/macro_events.json`**
Hardcoded quarterly macro event list. Format:
```json
{
  "_comment": "Manually updated quarterly. Add dates as YYYY-MM-DD strings.",
  "fed_meetings": [
    "2025-03-19",
    "2025-05-07",
    "2025-06-18",
    "2025-07-30",
    "2025-09-17",
    "2025-10-29",
    "2025-12-10"
  ],
  "cpi_releases": [
    "2025-03-12",
    "2025-04-10",
    "2025-05-13",
    "2025-06-11",
    "2025-07-11",
    "2025-08-12",
    "2025-09-10",
    "2025-10-15",
    "2025-11-12",
    "2025-12-10"
  ]
}
```
### Files to modify
**`contracts/eq_schema.py`**
Add three new constants at the bottom of the existing key block, grouped with a comment:
```python
# ── Event Risk (1A) ─────────────────────────────────────────────────────────
EVENT_RISK        = 'event_risk'          # 'NORMAL' | 'HIGH RISK'
EVENT_RISK_REASON = 'event_risk_reason'   # display string
DAYS_TO_EARNINGS  = 'days_to_earnings'    # int | None
```
**`main.py`**
Add Step 27g immediately after the closing line of Step 27f (`# ── End Step 27f ─────`). Pattern mirrors Step 27d/27e/27f — non-fatal, per-candidate loop.
```python
# ── Step 27g: Event Risk enrichment ──────────────────────────────────────
# Classifies each candidate as NORMAL or HIGH RISK based on earnings proximity
# and hardcoded macro events. Non-fatal — defaults to NORMAL on any error.
try:
    from eq_analyzer.event_risk import get_event_risk
    from contracts.eq_schema import EVENT_RISK, EVENT_RISK_REASON, DAYS_TO_EARNINGS
    finnhub_token = os.environ.get('FINNHUB_TOKEN', '')
    er_enriched = 0
    for candidate in final_companies:
        t = candidate.get('ticker', '')
        try:
            er_result = get_event_risk(t, finnhub_token)
            candidate[EVENT_RISK]        = er_result.get('event_risk',        'NORMAL')
            candidate[EVENT_RISK_REASON] = er_result.get('event_risk_reason', '')
            candidate[DAYS_TO_EARNINGS]  = er_result.get('days_to_earnings',  None)
            er_enriched += 1
        except Exception as _er_ticker_err:
            candidate[EVENT_RISK]        = 'NORMAL'
            candidate[EVENT_RISK_REASON] = ''
            candidate[DAYS_TO_EARNINGS]  = None
            log.info(f'[ER] {t}: error — {_er_ticker_err}')
    log.info(f'[ER] Event risk enrichment complete. {er_enriched}/{len(final_companies)} processed')
except Exception as er_err:
    log.warning(f'[ER] Event risk enrichment failed (non-fatal): {er_err}')
    for candidate in final_companies:
        candidate[EVENT_RISK]        = 'NORMAL'
        candidate[EVENT_RISK_REASON] = ''
        candidate[DAYS_TO_EARNINGS]  = None
# ── End Step 27g ─────────────────────────────────────────────────────────
```
**`reports/report_builder.py`**
Three changes:
**Change 1 — Remove the `earnings_warning` notices block.**
In `_enrich_company_for_template()`, find and remove this block (the earnings_warning notice is superseded by event_risk display):
```python
    if c.get('earnings_warning'):
        days = fin.get('earnings_days', 5)
        if days <= 1:
            notices.append(EARNINGS_WARNING_IMMINENT)
        else:
            notices.append(EARNINGS_WARNING.format(DAYS=int(days)))
```
Do not remove `earnings_warning` from `risk_model.py` or from the `main.py` candidate dict stamping — only this display block is removed.
**Change 2 — Add event_risk notice in its place.**
In `_enrich_company_for_template()`, in the `notices = []` block where the above was removed, add:
```python
    event_risk_val    = c.get('event_risk', 'NORMAL')
    event_risk_reason = c.get('event_risk_reason', '')
    if event_risk_val == 'HIGH RISK':
        reason_str = f' — {event_risk_reason}' if event_risk_reason else ''
        notices.append(f'⚠ EVENT RISK: HIGH RISK{reason_str}. Avoid new entries until event passes.')
```
**Change 3 — Add event_risk to the AI prompt.**
In `_build_ai_prompt()`, inside the per-company `candidate_block` f-string, add a new section after the `Combined Reading:` block:
```python
            f"\n"
            f"Event Risk (1A):\n"
            f"  Status: {c.get('event_risk', 'NORMAL')}\n"
            f"  Reason: {c.get('event_risk_reason', '') or 'None'}\n"
```
Update the BUY NOW hard gate section of the prompt text to add a 6th condition. Find the block that reads:
```
"BUY NOW HARD GATE — ALL FIVE MUST BE TRUE\n"
```
Change it to:
```
"BUY NOW HARD GATE — ALL SIX MUST BE TRUE\n"
```
And append after condition 5:
```python
        "  6. event_risk = NORMAL  <- HIGH RISK blocks BUY NOW regardless of entry quality\n"
        "\n"
        "  HIGH RISK -> BUY NOW blocked. Risk event imminent. Flag prominently.\n"
```
**Change 1 — Define the `_RANK_FETCH_JS` replacement.**
To avoid syntax errors during string concatenation, replace the entire `_RANK_FETCH_JS` constant definition with this block (add the `evRisk` and `insS` logic as shown):
```python
_RANK_FETCH_JS = (
    "fetch('assets/data/rank.json?v='+Date.now())\n"
    "  .then(function(r){ return r.ok ? r.json() : Promise.reject(r.status); })\n"
    "  .then(function(rankData) {\n"
    "    var stocks = rankData.stocks || {};\n"
    "    var arr = Array.isArray(stocks) ? stocks : Object.values(stocks);\n"
    "    arr = arr.filter(function(s){ return s && typeof s === 'object'; });\n"
    "    arr.sort(function(a,b){\n"
    "      var ca = typeof a.confidence === 'number' ? a.confidence : -1;\n"
    "      var cb = typeof b.confidence === 'number' ? b.confidence : -1;\n"
    "      return cb - ca;\n"
    "    });\n"
    "    var html    = '';\n"
    "    var scripts = '';\n"
    "    arr.forEach(function(stock, idx) {\n"
    "      var i    = idx + 1;\n"
    "      var conf = typeof stock.confidence === 'number' ? stock.confidence : null;\n"
    "      var risk = typeof stock.risk_score  === 'number' ? stock.risk_score  : null;\n"
    "      var cCls   = conf === null ? 'nt' : conf >= 70 ? 'up' : conf >= 50 ? 'nt' : 'dn';\n"
    "      var eqV    = stock.eq_verdict_display  || '';\n"
    "      var rotS   = stock.rotation_signal_display || '';\n"
    "      var psV    = stock.ps_verdict_display  || '';\n"
    "      var psCls  = psV  === 'GOOD'     ? 'up' : psV  === 'EXTENDED' ? 'dn' : psV === 'WEAK' ? 'dn' : psV === 'EARLY' ? 'nt' : 'pu';\n"
    "      var evRisk = stock.event_risk || 'NORMAL';\n"
    "      var evRiskCls = evRisk === 'HIGH RISK' ? 'rpill-ev-hr' : 'rpill-ev-ok';\n"
    "      var insS   = stock.insider_signal || 'UNAVAILABLE';\n"
    "      var insCls = insS === 'ACCUMULATING' ? 'rpill-ins-ac' : insS === 'DISTRIBUTING' ? 'rpill-ins-di' : 'rpill-ins-na';\n"
    "      var verdict  = stock.market_verdict_display || stock.market_verdict || '\\u2014';\n"
    "      var confStr  = conf !== null ? Math.round(conf) : '\\u2014';\n"
    "      var riskStr  = risk !== null ? Math.round(risk)  : '\\u2014';\n"
    "      var price    = typeof stock.price === 'number' ? '$' + stock.price.toFixed(2) : '\\u2014';\n"
    "      var phUid    = 'ph-' + i;\n"
    "      var rawPh    = Array.isArray(stock.price_history) ? stock.price_history : [];\n"
    "      var phList   = rawPh.filter(function(v){ return typeof v === 'number' && isFinite(v); });\n"
    "      var hasCh    = phList.length > 1;\n"
    "      var chartEl  = hasCh\n"
    "        ? '<canvas id=\"ec' + i + '\" height=\"92\"></canvas>'\n"
    "        : '<div style=\"color:var(--mist);font-size:11px;padding:8px 0;\">Price history unavailable</div>';\n"
    "      scripts += '<script type=\"application/json\" id=\"' + phUid + '\">'\n"
    "              + JSON.stringify(phList).replace(/<\\/script>/gi,'<\\\\/script>')\n"
    "              + '<\\/script>';\n"
    "      var confVal    = typeof stock.confidence === 'number' ? stock.confidence : null;\n"
    "      var riskVal    = typeof stock.risk_score === 'number' ? stock.risk_score : null;\n"
    "      var confCls    = confVal !== null ? (confVal >= 70 ? 'rpill-cup' : confVal >= 50 ? 'rpill-cnt' : 'rpill-cdn') : 'rpill-una';\n"
    "      var riskCls    = riskVal !== null ? (riskVal <= 30 ? 'rpill-rlo' : riskVal <= 55 ? 'rpill-rmd' : 'rpill-rhi') : 'rpill-una';\n"
    "      var eqMap      = {'SUPPORTIVE':'rpill-eq-sup','NEUTRAL':'rpill-eq-neu','WEAK':'rpill-eq-wk','RISKY':'rpill-eq-rsk','UNAVAILABLE':'rpill-eq-una'};\n"
    "      var rotMap     = {'SUPPORT':'rpill-rt-sup','WAIT':'rpill-rt-wt','WEAKEN':'rpill-rt-wk','UNKNOWN':'rpill-rt-unk'};\n"
    "      var eqPillCls  = eqMap[eqV]  || 'rpill-una';\n"
    "      var rotPillCls = rotMap[rotS] || 'rpill-una';\n"
    "      var psMap      = {'GOOD':'rpill-ps-gd','EXTENDED':'rpill-ps-ex','EARLY':'rpill-ps-ea','WEAK':'rpill-ps-wk','UNAVAILABLE':'rpill-eq-una'};\n"
    "      var psPillCls  = psMap[psV]  || 'rpill-una';\n"
    "      var priceDisp  = typeof stock.price === 'number' ? '$' + stock.price.toFixed(2) : '\\u2014';\n"
    "      var psEntryPx  = typeof stock.ps_entry_price === 'number' ? '$' + stock.ps_entry_price.toFixed(2) : '\\u2014';\n"
    "      var psStopLx   = typeof stock.ps_stop_loss   === 'number' ? '$' + stock.ps_stop_loss.toFixed(2)   : '\\u2014';\n"
    "      var psTgtPx    = typeof stock.ps_price_target === 'number' ? '$' + stock.ps_price_target.toFixed(2) : '\\u2014';\n"
    "      var psRR       = typeof stock.ps_risk_reward_ratio === 'number' ? stock.ps_risk_reward_ratio.toFixed(2) + 'x' : '\\u2014';\n"
    "      var psRROvr    = stock.ps_rr_override === true;\n"
    "      html += '<div class=\"rank-card\" data-ref=\"' + phUid + '\" data-eid=\"e' + i + '\" data-cid=\"ec' + i + '\">'\n"
    "           + '<div class=\"rank-card-main\" onclick=\"expT(this.closest(\\'.rank-card\\'))\">'  \n"
    "           + '<div class=\"rck-n\">#' + i + '</div>'\n"
    "           + '<div class=\"rck-t\">' + (stock.ticker || '\\u2014') + '</div>'\n"
    "           + '<div class=\"rck-pills\">'\n"
    "           + '<span class=\"rpill rpill-price\"><span class=\"rpill-lbl\">Price</span>' + priceDisp + '</span>'\n"
    "           + '<span class=\"rpill ' + confCls + '\"><span class=\"rpill-lbl\">Conf</span>' + confVal + '/100</span>'\n"
    "           + '<span class=\"rpill ' + eqPillCls + '\"><span class=\"rpill-lbl\">EQ</span>' + (eqV || '\\u2014') + '</span>'\n"
    "           + '<span class=\"rpill ' + psPillCls + '\"><span class=\"rpill-lbl\">Entry</span>' + (psV || '\\u2014') + '</span>'\n"
    "           + '<span class=\"rpill ' + evRiskCls + '\"><span class=\"rpill-lbl\">Event</span>' + evRisk + '</span>'\n"
    "           + '<span class=\"rpill ' + insCls + '\"><span class=\"rpill-lbl\">Insider</span>' + insS + '</span>'\n"
    "           + '</div>'\n"
    "           + '</div>'\n"
    "           + '<div class=\"exp-row\" id=\"e' + i + '\" onclick=\"event.stopPropagation()\"><div class=\"exp-inner\">'\n"
    "           + '<div class=\"exp-stats\">'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Verdict</div><div class=\"est-v ' + cCls + '\">' + verdict + '</div></div>'\n"
    "           + '<div class=\"est est-divider\"></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Entry $</div><div class=\"est-v\">' + psEntryPx + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Stop $</div><div class=\"est-v est-dn\">' + psStopLx + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Target $</div><div class=\"est-v est-up\">' + psTgtPx + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">R/R</div><div class=\"est-v' + (psRROvr ? ' est-dn' : '') + '\">' + psRR + (psRROvr ? ' ⚠' : '') + '</div></div>'\n"
    "           + '</div>'\n"
    "           + '<div class=\"exp-chart\">' + chartEl + '</div>'\n"
    "           + '</div></div>'\n"
    "           + '</div>';\n"
    "    });\n"
    "    document.getElementById('rank-board-mount').innerHTML = scripts + html;\n"
    "  })\n"
);\n"
```
**Change 3 — Stamp event_risk in `_update_rank_json()`.**
In the `rank_data['stocks'][ticker] = { ... }` dict inside `_update_rank_json()`, add:
```python
                'event_risk':       c.get('event_risk', 'NORMAL'),
                'event_risk_reason': c.get('event_risk_reason', ''),
```
**`docs/assets/style.css`**
Add two new pill classes at the bottom of the existing rpill block (after `.rpill-ps-wk`):
```css
.rpill-ev-ok {
  background: rgba(57, 232, 160, 0.12);
  color: var(--up);
  border-color: rgba(57, 232, 160, 0.35);
}
.rpill-ev-hr {
  background: rgba(255, 77, 109, 0.18);
  color: var(--dn);
  border-color: rgba(255, 77, 109, 0.45);
  font-weight: 700;
}
```
---
## LAYER 1B — INSIDER & INSTITUTIONAL ACTIVITY
### What you are building
A new module that fetches SEC Form 4 insider transaction filings via EDGAR RSS for the last 90 days per candidate ticker and produces a single directional signal. It reuses `EdgarFetcher`'s CIK resolution infrastructure directly. The output is a single `insider_signal` field — it is a confirmation layer only, not a voting member of the alignment score.
### New files to create
**`eq_analyzer/insider_activity.py`**
```python
"""
eq_analyzer/insider_activity.py
Fetches SEC Form 4 insider transaction data via EDGAR RSS for a given ticker.
Reuses EdgarFetcher CIK resolution. Returns a directional signal only.
Non-fatal — returns UNAVAILABLE on any error or missing data.
"""
```
Expose a single public function:
```python
def get_insider_signal(ticker: str, fetcher) -> dict:
```
Where `fetcher` is an instantiated `EdgarFetcher` object (passed in from `main.py` — do not instantiate a new one here, reuse the existing one from the EQ pipeline).
Return dict contract:
```python
{
    'insider_signal': 'ACCUMULATING' | 'DISTRIBUTING' | 'NEUTRAL' | 'UNAVAILABLE',
    'insider_note':   str,  # one-line human display string, empty if UNAVAILABLE
}
```
**CIK resolution:** Call `fetcher._resolve_cik(ticker)` directly. If it returns `None`, return `UNAVAILABLE`.
- Create a single `requests.Session()` at the start of `get_insider_signal` and reuse it for all HTTP calls.
- Fetch Atom feed for Form 4s: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=40&output=atom`
- Parse the Atom feed. **Strictly ignore filings older than 90 days** by comparing the `<updated>` or `<published>` timestamp with `datetime.now(timezone.utc)`.
- For each valid entry, fetch the filing index page.
- **XML Discovery Rule:** Select the first link where `href` ends with `.xml` AND the filename contains `form4` (case-insensitive). If no filename match, fallback to the first link ending in `.xml`.
- **SEC Form 4 XML Structure Reference:**
```xml
<ownershipDocument>
    <nonDerivativeTable>
        <nonDerivativeTransaction>
            <transactionAmounts>
                <transactionShares><value>1000</value></transactionShares>
                <transactionPricePerShare><value>150.00</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
        </nonDerivativeTransaction>
    </nonDerivativeTable>
</ownershipDocument>
```
- **Exact Parsing Paths:**
  - Root: `.//nonDerivativeTransaction`
  - Shares: `./transactionAmounts/transactionShares/value`
  - Price: `./transactionAmounts/transactionPricePerShare/value`
  - Code: `./transactionAmounts/transactionAcquiredDisposedCode/value` ('A' = Buy, 'D' = Sell)
- Compute: `total_bought = sum(shares * price for A transactions)`, `total_sold = sum(shares * price for D transactions)`
**Signal classification:**
- If `total_bought > total_sold * 1.5`: `ACCUMULATING`, note `'Net insider buying over 90 days'`
- If `total_sold > total_bought * 1.5`: `DISTRIBUTING`, note `'Net insider selling over 90 days'`
- If both are zero or data is sparse: `NEUTRAL`, note `'No significant insider activity'`
- On any exception or parse failure: `UNAVAILABLE`, log the error
**Rate limiting:** Add `time.sleep(0.25)` between any EDGAR HTTP requests (same policy as `edgar_fetcher.py`). This module is called sequentially per ticker, so no batching needed.
**Important:** Do not instantiate `EdgarFetcher` inside this module. It is passed in. Do not load config or fallbacks files — those belong to `edgar_fetcher.py` only. This module only uses `fetcher._resolve_cik()` and then makes its own direct HTTP requests via `requests.Session`.
### Files to modify
**`contracts/eq_schema.py`**
Add two new constants (continuing the 1A block):
```python
# ── Insider Activity (1B) ────────────────────────────────────────────────────
INSIDER_SIGNAL = 'insider_signal'   # 'ACCUMULATING' | 'DISTRIBUTING' | 'NEUTRAL' | 'UNAVAILABLE'
INSIDER_NOTE   = 'insider_note'     # display string
```
**`eq_analyzer/main.py`** [MANDATORY]
Before implementing Layer 1B, you must expose the `EdgarFetcher` instance created in `run_eq_analyzer`.
1. Modify `run_eq_analyzer(tickers: list)` to return a tuple: `(results, fetcher)`.
2. Ensure the `fetcher` instance (created on line ~265) is returned.
**`main.py`** [MANDATORY]
Update Step 27d to capture the fetcher:
```python
# Change from:
# eq_results = run_eq_analyzer(eq_tickers)
# To:
eq_results, eq_fetcher = run_eq_analyzer(eq_tickers)
```
Now Step 27h can reuse `eq_fetcher` without re-instantiating. Add Step 27h immediately after Step 27g's closing line.
```python
# ── Step 27h: Insider Activity enrichment ────────────────────────────────
# Fetches SEC Form 4 insider transaction data via EDGAR RSS.
# Reuses EdgarFetcher from Step 27d. Non-fatal — defaults to UNAVAILABLE.
try:
    from eq_analyzer.insider_activity import get_insider_signal
    from contracts.eq_schema import INSIDER_SIGNAL, INSIDER_NOTE
    ins_enriched = 0
    for candidate in final_companies:
        t = candidate.get('ticker', '')
        try:
            ins_result = get_insider_signal(t, eq_fetcher)  # eq_fetcher from Step 27d
            candidate[INSIDER_SIGNAL] = ins_result.get('insider_signal', 'UNAVAILABLE')
            candidate[INSIDER_NOTE]   = ins_result.get('insider_note',   '')
            ins_enriched += 1
        except Exception as _ins_ticker_err:
            candidate[INSIDER_SIGNAL] = 'UNAVAILABLE'
            candidate[INSIDER_NOTE]   = ''
            log.info(f'[INS] {t}: error — {_ins_ticker_err}')
    log.info(f'[INS] Insider enrichment complete. {ins_enriched}/{len(final_companies)} processed')
except Exception as ins_err:
    log.warning(f'[INS] Insider enrichment failed (non-fatal): {ins_err}')
    for candidate in final_companies:
        candidate[INSIDER_SIGNAL] = 'UNAVAILABLE'
        candidate[INSIDER_NOTE]   = ''
# ── End Step 27h ─────────────────────────────────────────────────────────
```
**Note on `eq_fetcher` scope:** In Step 27d, the `EdgarFetcher` instance is created. Ensure it is assigned to a variable named `eq_fetcher` at the outer `final_companies` scope so Step 27h can access it. If it is currently scoped differently, rename it at declaration. Do not create a second instance.
**`reports/report_builder.py`**
Two changes:
**Change 1 — Add insider_signal to `_enrich_company_for_template()` notices.**
After the event_risk notice block you added in 1A, add:
```python
    insider_signal = c.get('insider_signal', 'UNAVAILABLE')
    insider_note   = c.get('insider_note', '')
    if insider_signal == 'DISTRIBUTING':
        notices.append(f'⚠ INSIDER ACTIVITY: Net selling detected. {insider_note}')
    elif insider_signal == 'ACCUMULATING':
        notices.append(f'✓ INSIDER ACTIVITY: Net buying detected. {insider_note}')
```
**Change 2 — Add insider_signal to AI prompt per-company block.**
In `_build_ai_prompt()`, add a new section after the Event Risk block:
```python
            f"\n"
            f"Insider Activity (1B):\n"
            f"  Signal: {c.get('insider_signal', 'UNAVAILABLE')}\n"
            f"  Note:   {c.get('insider_note', '') or 'None'}\n"
```
Also add a rule to the CONFLICT AND RISK RULES section of the prompt:
```python
        "  DISTRIBUTING insider signal near resistance = elevated risk flag.\n"
        "  ACCUMULATING insider signal near support = confirmation note.\n"
        "  UNAVAILABLE = no data. Do not treat as negative signal.\n"
```
**Change 3 — Add `_update_rank_json` and `_update_weekly_archive` stamping.**
Ensure keys match exactly with the schema constants.
```python
# In _update_rank_json()
'event_risk':       c.get('event_risk', 'NORMAL'),
'event_risk_reason': c.get('event_risk_reason', ''),
'insider_signal':    c.get('insider_signal', 'UNAVAILABLE'),
'insider_note':      c.get('insider_note', ''),
```
**`docs/assets/style.css`**
Add three new pill classes after the event risk classes:
```css
.rpill-ins-ac {
  background: rgba(57, 232, 160, 0.12);
  color: var(--up);
  border-color: rgba(57, 232, 160, 0.35);
}
.rpill-ins-di {
  background: rgba(255, 77, 109, 0.18);
  color: var(--dn);
  border-color: rgba(255, 77, 109, 0.45);
}
.rpill-ins-na {
  background: rgba(168, 155, 194, 0.10);
  color: var(--mist);
  border-color: rgba(168, 155, 194, 0.25);
}
```
---
## LAYER 1C — EXECUTION LAYER
### What you are building
An arithmetic extension of Sub4 that translates the existing structural knowledge (current price, support distance, resistance distance) into four concrete trade definition numbers: entry price, stop loss, price target, and risk/reward ratio. Pure arithmetic — no new API, no new data source. If the R/R ratio is below 2.0, `entry_quality` is overridden to `WEAK`.
### Design decisions (locked)
- Minimum R/R threshold: **2.0**
- R/R override landing: **WEAK** (not EARLY — an insufficient R/R is an active failure condition, not a neutral pending state)
- The override mutates `entry_quality` on the `ps_result` dict before it is stamped onto the candidate. The original Sub4 output is modified in-place.
### New files to create
**`price_structure/execution_layer.py`**
```python
"""
price_structure/execution_layer.py
Computes concrete trade execution levels from Sub4 structural data.
Pure arithmetic — no API calls, no yfinance, no ML.
Inputs: current_price, nearest_support, nearest_resistance, entry_quality.
Outputs: entry_price, stop_loss, price_target, risk_reward_ratio.
If R/R < MIN_RR_THRESHOLD, entry_quality is overridden to WEAK.
"""
MIN_RR_THRESHOLD = 2.0
STOP_BUFFER_PCT  = 0.005   # 0.5% buffer below support for stop loss
def compute_execution_levels(
    current_price:      float,
    nearest_support:    float | None,
    nearest_resistance: float | None,
    entry_quality:      str,
) -> dict:
    """
    Returns:
        {
            'entry_price':       float | None,
            'stop_loss':         float | None,
            'price_target':      float | None,
            'risk_reward_ratio': float | None,
            'entry_quality':     str,   # may be overridden to WEAK
            'rr_override':       bool,  # True if entry_quality was overridden
        }
    """
```
**Computation logic:**
```
entry_price = current_price   (always — we don't manufacture a better price)
stop_loss   = nearest_support * (1 - STOP_BUFFER_PCT)
              → None if nearest_support is None or nearest_support <= 0
price_target = nearest_resistance
               → None if nearest_resistance is None or nearest_resistance <= 0
risk_reward_ratio:
  → None if any of entry_price, stop_loss, price_target is None
  → None if entry_price <= stop_loss (no valid setup)
  → (price_target - entry_price) / (entry_price - stop_loss)
  → round to 2 decimal places
entry_quality override:
  → If risk_reward_ratio is not None and risk_reward_ratio < MIN_RR_THRESHOLD:
        entry_quality = 'WEAK'
        rr_override   = True
  → Otherwise: entry_quality unchanged, rr_override = False
```
All outputs default to `None` on any exception. Do not raise — return safe defaults.
### Files to modify
**`price_structure/level_detector.py`**
The `detect_levels()` function computes `nearest_support` and `nearest_resistance` internally but does not return them. Add them to the return dict:
In the existing `return { ... }` statement, add:
```python
        "nearest_support":    float(nearest_support)    if nearest_support    is not None else None,
        "nearest_resistance": float(nearest_resistance) if nearest_resistance is not None else None,
```
These two fields are now part of the `detect_levels()` output. No other logic changes.
**`price_structure/price_structure_analyzer.py`**
After `entry_classifier.classify_entry()` is called and `entry_result` is populated, add the execution layer call:
```python
    from price_structure.execution_layer import compute_execution_levels
    current_price      = float(df["Close"].iloc[-1]) if len(df) > 0 else 0.0
    nearest_support    = level_result.get("nearest_support")
    nearest_resistance = level_result.get("nearest_resistance")
    entry_quality_raw  = entry_result.get("entry_quality", "WEAK")
    exec_result = compute_execution_levels(
        current_price      = current_price,
        nearest_support    = nearest_support,
        nearest_resistance = nearest_resistance,
        entry_quality      = entry_quality_raw,
    )
    # Apply R/R override back to entry_result before building final output
    entry_result["entry_quality"] = exec_result["entry_quality"]
```
Then include the execution fields in the final `analyze()` return dict:
```python
    return {
        ...existing fields...,
        "entry_price":       exec_result.get("entry_price"),
        "stop_loss":         exec_result.get("stop_loss"),
        "price_target":      exec_result.get("price_target"),
        "risk_reward_ratio": exec_result.get("risk_reward_ratio"),
        "rr_override":       exec_result.get("rr_override", False),
    }
```
**`contracts/price_structure_schema.py`**
Add four new raw output key constants and one flag, grouped with a comment:
```python
# ── Execution Layer (1C) ─────────────────────────────────────────────────────
PS_ENTRY_PRICE       = 'entry_price'        # float | None — computed entry price
PS_STOP_LOSS         = 'stop_loss'          # float | None — stop loss level
PS_PRICE_TARGET      = 'price_target'       # float | None — nearest resistance as target
PS_RISK_REWARD_RATIO = 'risk_reward_ratio'  # float | None — (target-entry)/(entry-stop)
PS_RR_OVERRIDE       = 'rr_override'        # bool — True if entry_quality overridden to WEAK
```
Add to `PRICE_STRUCTURE_KEYS`:
```python
    'entry_price':       float,
    'stop_loss':         float,
    'price_target':      float,
    'risk_reward_ratio': float,
    'rr_override':       bool,
```
Add to `PRICE_STRUCTURE_DEFAULTS`:
```python
    'entry_price':       None,
    'stop_loss':         None,
    'price_target':      None,
    'risk_reward_ratio': None,
    'rr_override':       False,
```
**`main.py`**
In Step 27f's candidate stamping blocks (both the debug path around line 526 and the main path around line 1055), add the four execution fields after the existing PS fields. Add to both the `if ps_result ...` block and the existing stamp list:
```python
                        candidate[PS_ENTRY_PRICE]       = ps_result.get(PS_ENTRY_PRICE,       PRICE_STRUCTURE_DEFAULTS['entry_price'])
                        candidate[PS_STOP_LOSS]         = ps_result.get(PS_STOP_LOSS,         PRICE_STRUCTURE_DEFAULTS['stop_loss'])
                        candidate[PS_PRICE_TARGET]      = ps_result.get(PS_PRICE_TARGET,      PRICE_STRUCTURE_DEFAULTS['price_target'])
                        candidate[PS_RISK_REWARD_RATIO] = ps_result.get(PS_RISK_REWARD_RATIO, PRICE_STRUCTURE_DEFAULTS['risk_reward_ratio'])
                        candidate[PS_RR_OVERRIDE]       = ps_result.get(PS_RR_OVERRIDE,       False)
```
Make sure `PS_ENTRY_PRICE`, `PS_STOP_LOSS`, `PS_PRICE_TARGET`, `PS_RISK_REWARD_RATIO`, `PS_RR_OVERRIDE` are imported from `contracts.price_structure_schema` alongside the existing PS constant imports.
**`reports/report_builder.py`**
Three changes:
**Change 1 — Add execution fields to `_build_ps_display()`.**
At the end of the function's populated-state return dict (where `ps_available` is `True`), add:
```python
        'ps_entry_price':       c.get(PS_ENTRY_PRICE),
        'ps_stop_loss':         c.get(PS_STOP_LOSS),
        'ps_price_target':      c.get(PS_PRICE_TARGET),
        'ps_risk_reward_ratio': c.get(PS_RISK_REWARD_RATIO),
        'ps_rr_override':       bool(c.get(PS_RR_OVERRIDE, False)),
```
In the unavailable fallback return dict, add:
```python
        'ps_entry_price':       None,
        'ps_stop_loss':         None,
        'ps_price_target':      None,
        'ps_risk_reward_ratio': None,
        'ps_rr_override':       False,
```
**Change 2 — Add execution fields to AI prompt per-company block.**
In `_build_ai_prompt()`, add inside the `Price Structure (System 4):` section, after the existing `Dist to resist` line:
```python
            f"  Entry price:      {fmt_price(c.get(PS_ENTRY_PRICE)) if c.get(PS_ENTRY_PRICE) else 'N/A'}\n"
            f"  Stop loss:        {fmt_price(c.get(PS_STOP_LOSS))   if c.get(PS_STOP_LOSS)   else 'N/A'}\n"
            f"  Price target:     {fmt_price(c.get(PS_PRICE_TARGET)) if c.get(PS_PRICE_TARGET) else 'N/A'}\n"
            f"  Risk/Reward:      {f\"{c.get(PS_RISK_REWARD_RATIO):.2f}x\" if c.get(PS_RISK_REWARD_RATIO) else 'N/A'}\n"
            f"  R/R override:     {'YES — entry_quality downgraded to WEAK' if c.get(PS_RR_OVERRIDE) else 'No'}\n"
```
Add a rule to the CONFLICT AND RISK RULES section of the prompt:
```python
        "  R/R < 2.0 overrides entry_quality to WEAK automatically (rr_override=YES).\n"
        "  Even with GOOD entry_quality, if R/R is 'N/A', treat as WEAK for BUY NOW.\n"
```
**Change 3 — Add R/R override to notices in `_enrich_company_for_template()`.**
After the insider_signal notice block, add:
```python
    if c.get('ps_rr_override') or c.get(PS_RR_OVERRIDE):
        rr_val = c.get(PS_RISK_REWARD_RATIO) or c.get('ps_risk_reward_ratio')
        rr_str = f' (computed R/R: {rr_val:.2f}x)' if rr_val else ''
        notices.append(f'↓ ENTRY QUALITY OVERRIDDEN: R/R below 2.0{rr_str}. Entry downgraded to WEAK.')
```
**`reports/dashboard_builder.py`**
Two changes:
**Change 1 — Add JS variables and display for execution fields in `_RANK_FETCH_JS`.**
In the PS variable declaration block (where `psKeyLvl`, `psPaScore`, etc. are declared), add:
```javascript
      var psEntryPx = typeof stock.ps_entry_price === 'number' ? '$' + stock.ps_entry_price.toFixed(2) : '\u2014';
      var psStopLx  = typeof stock.ps_stop_loss   === 'number' ? '$' + stock.ps_stop_loss.toFixed(2)   : '\u2014';
      var psTgtPx   = typeof stock.ps_price_target === 'number' ? '$' + stock.ps_price_target.toFixed(2) : '\u2014';
      var psRR      = typeof stock.ps_risk_reward_ratio === 'number' ? stock.ps_risk_reward_ratio.toFixed(2) + 'x' : '\u2014';
      var psRROvr   = stock.ps_rr_override === true;
```
In the expanded row PS block (the section gated by `psAvail ?`), append after the `Dist Res.` line:
```javascript
           + '<div class="est est-divider"></div>'
           + '<div class="est"><div class="est-k">Entry $</div><div class="est-v">' + psEntryPx + '</div></div>'
           + '<div class="est"><div class="est-k">Stop $</div><div class="est-v est-dn">' + psStopLx + '</div></div>'
           + '<div class="est"><div class="est-k">Target $</div><div class="est-v est-up">' + psTgtPx + '</div></div>'
           + '<div class="est"><div class="est-k">R/R</div><div class="est-v' + (psRROvr ? ' est-dn' : '') + '">' + psRR + (psRROvr ? ' ⚠' : '') + '</div></div>'
```
**Change 2 — Stamp execution fields in `_update_rank_json()`.**
In the `rank_data['stocks'][ticker]` dict, add:
```python
                'ps_entry_price':       c.get('entry_price'),
                'ps_stop_loss':         c.get('stop_loss'),
                'ps_price_target':      c.get('price_target'),
                'ps_risk_reward_ratio': c.get('risk_reward_ratio'),
                'ps_rr_override':       c.get('rr_override', False),
```
---
## SCHEMA SYNCHRONIZATION REFERENCE
| File | Constant Name | Key Name | Notes |
| :--- | :--- | :--- | :--- |
| `eq_schema.py` | `EVENT_RISK` | `'event_risk'` | 'NORMAL' \| 'HIGH RISK' |
| `eq_schema.py` | `INSIDER_SIGNAL` | `'insider_signal'` | 'ACCUMULATING' \| 'DISTRIBUTING' \| ... |
| `contracts/price_structure_schema.py` | `PS_ENTRY_PRICE` | `'ps_entry_price'` | float \| None |
| `contracts/price_structure_schema.py` | `PS_STOP_LOSS` | `'ps_stop_loss'` | float \| None |
| `contracts/price_structure_schema.py` | `PS_PRICE_TARGET` | `'ps_price_target'` | float \| None |
| `contracts/price_structure_schema.py` | `PS_RISK_REWARD_RATIO` | `'ps_risk_reward_ratio'` | float \| None |
> [!WARNING]
> Mismatching keyed strings between `main.py` stamping and `dashboard_builder.py` JS retrieval will cause "N/A" or "undefined" to display silently. Always use constant variables where possible.
---
## VERIFICATION CHECKLIST
After completing all three layers, verify the following before committing:
**Structural checks**
- [ ] `eq_analyzer/event_risk.py` exists and exports `get_event_risk(ticker, finnhub_token) -> dict`
- [ ] `eq_analyzer/insider_activity.py` exists and exports `get_insider_signal(ticker, fetcher) -> dict`
- [ ] `price_structure/execution_layer.py` exists and exports `compute_execution_levels(...) -> dict`
- [ ] `data/macro_events.json` exists with valid JSON
- [ ] `contracts/eq_schema.py` contains `EVENT_RISK`, `EVENT_RISK_REASON`, `DAYS_TO_EARNINGS`, `INSIDER_SIGNAL`, `INSIDER_NOTE`
- [ ] `contracts/price_structure_schema.py` contains `PS_ENTRY_PRICE`, `PS_STOP_LOSS`, `PS_PRICE_TARGET`, `PS_RISK_REWARD_RATIO`, `PS_RR_OVERRIDE` and their defaults
**Pipeline checks**
- [ ] `main.py` Step 27g runs after Step 27f end, stamps `event_risk` on all candidates
- [ ] `main.py` Step 27h runs after Step 27g, stamps `insider_signal` on all candidates, reuses `eq_fetcher`
- [ ] `main.py` Step 27f stamps the four execution fields from `ps_result`
- [ ] `price_structure/level_detector.py` returns `nearest_support` and `nearest_resistance`
- [ ] `price_structure/price_structure_analyzer.py` calls `compute_execution_levels()` and stamps the result
- [ ] Entry quality override (`WEAK` when R/R < 2.0) happens in `execution_layer.py` before the result is returned to `price_structure_analyzer.py`
**Display checks**
- [ ] `_enrich_company_for_template()` no longer appends the old `earnings_warning` notice
- [ ] `_enrich_company_for_template()` appends event_risk notice when `HIGH RISK`
- [ ] `_enrich_company_for_template()` appends insider notice for `ACCUMULATING` and `DISTRIBUTING`
- [ ] `_enrich_company_for_template()` appends R/R override notice when `ps_rr_override` is True
- [ ] `_build_ai_prompt()` BUY NOW gate now lists 6 conditions
- [ ] `_build_ai_prompt()` per-company block shows Event Risk, Insider Activity, and execution fields
- [ ] `_RANK_FETCH_JS` renders Event, Insider pills in the rank card pills row
- [ ] `_RANK_FETCH_JS` renders Entry/Stop/Target/R/R fields in the expanded PS block
- [ ] `_update_rank_json()` stamps all new fields into `rank.json`
- [ ] `docs/assets/style.css` contains the 5 new pill classes (`rpill-ev-ok`, `rpill-ev-hr`, `rpill-ins-ac`, `rpill-ins-di`, `rpill-ins-na`)
**Safety checks**
- [ ] `analyzers/risk_model.py` is **unchanged** — `earnings_warning` score penalty intact
- [ ] `main.py` candidate stamping of `earnings_warning` from `risk_result` is **unchanged**
- [ ] All three new steps in `main.py` are wrapped in outer try/except with non-fatal fallback defaults
- [ ] `insider_activity.py` does **not** instantiate `EdgarFetcher` internally
- [ ] `execution_layer.py` has **no** imports beyond stdlib
- [ ] No edits to `docs/*.html` directly
---
## QUICK SMOKE TEST
After implementing, run locally with `FORCE_TICKERS=AAPL` via workflow_dispatch equivalent:
```bash
FORCE_TICKERS=AAPL python main.py
```
Expected log output (in order, all non-fatal):
```
[PS]  Enrichment complete. 1 enriched / 1 total
[ER]  Event risk enrichment complete. 1/1 processed
[INS] Insider enrichment complete. 1/1 processed
```
Expected in `docs/assets/data/rank.json` for AAPL entry: presence of keys `event_risk`, `insider_signal`, `ps_entry_price`, `ps_stop_loss`, `ps_price_target`, `ps_risk_reward_ratio`.
Expected in rendered rank page: Event pill and Insider pill visible in card pills row. Execution fields visible in expanded PS section.
We are doing this another way because it seems that agents couldnt perform the task, so heres the prompt that I gave to the agent but everything went totally wrong for the front end so instead you claude will perform all the necessary updates of the phase 1 im going to give you the prompt when you are ready i will give you the zip file that cointains all the logic, frontend and backend of the system. so for now this is the AI agent prompt which now you will be the one that proceeds with all the changes. if you have any questions please ask, because this includes updates in the backend and front end, first you will take care of the backend side first so you will give me the files that need this update once we finish the back end side (you give the full files updated) we will go to the front end where I will perform the changes basically you will give me the code fragment to add or to change. basically for the front end you will give me the instructions to update it myself the front end so we can optimize tokens and messages for that part, but since I consider the back end be more important than the front end you can take care all of that. prompt: (ignore the first sentence is not for you just focus on the AI agent prompt). ready?
claude response: 
Good. Now let me read all the files I need to touch before writing a single line.---

Good news — I've read all the critical files. Before I write a single line of code, let me flag one important discrepancy I found between the agent prompt and the actual codebase:

**Key finding in `_update_rank_json`:** The existing rank stamping uses raw key names like `c.get('key_level_position', '')` / `c.get('distance_to_support_pct')` etc. (not the schema constants), meaning 1C execution fields must follow the same pattern — `c.get('entry_price')`, `c.get('stop_loss')`, etc. I'll handle this correctly.

**Everything else looks clean.** The files match what the prompt expects. Here's my implementation plan before I start writing:

**Order of files I'll produce (backend only):**

1. `data/macro_events.json` — new file
2. `eq_analyzer/event_risk.py` — new file (1A)
3. `eq_analyzer/insider_activity.py` — new file (1B)
4. `price_structure/execution_layer.py` — new file (1C)
5. `contracts/eq_schema.py` — add 5 new constants
6. `contracts/price_structure_schema.py` — add 5 execution constants + keys + defaults
7. `price_structure/level_detector.py` — expose `nearest_support` / `nearest_resistance`
8. `price_structure/price_structure_analyzer.py` — call execution layer
9. `eq_analyzer/main.py` — expose `fetcher` in return tuple
10. `main.py` — update Step 27d capture, add Steps 27g + 27h, add 5 execution fields to both 27f stamp blocks
11. `reports/report_builder.py` — all 1A/1B/1C changes

One question before I start: **`_RANK_FETCH_JS`** is listed as a frontend change. Should I skip that entirely (you'll handle it as part of the frontend phase), or include it now since it's in `dashboard_builder.py` (Python file)? The prompt spec puts it in `dashboard_builder.py` which is backend. Your call. 
my response: 
That depends on you if you include that change would you use more tokens than you would if you do only the back end? in case it doesnt change then you can include it, but try to maximize the tokens for the backend only if you have quota or message limit tell me what needs to be included or missing if there is anything for backend part, also I want you to return what is left to do for the front end part once you finish the back end part because I need a roadmap to follow too. so in summary if there is something left for the back end include both back end and front end if you finish the back end then just return what is left for the front end part. once you have understood you can continue working.
claude: 
Got it. I'll include `dashboard_builder.py` since it's Python — that keeps the frontend work minimal. Let me start building.Good — I have a complete picture. Now I'll build everything systematically.**File 1 of 11 — `data/macro_events.json`****File 2 of 11 — `eq_analyzer/event_risk.py`****File 3 of 11 — `eq_analyzer/insider_activity.py`****File 4 of 11 — `price_structure/execution_layer.py`****File 5 of 11 — `contracts/eq_schema.py`****File 6 of 11 — `contracts/price_structure_schema.py`****File 7 of 11 — `price_structure/level_detector.py`** — expose `nearest_support` / `nearest_resistance`Also need to expose `nearest_support` / `nearest_resistance` in the empty-df fallback:**File 8 of 11 — `price_structure/price_structure_analyzer.py`**Now add the execution fields to the `analyze()` return dict:**File 9 of 11 — `eq_analyzer/main.py`** — expose fetcher in return tuple**Backend completed so far (8 of 11 files):**

| # | File | Status |
|---|------|--------|
| 1 | `data/macro_events.json` | ✅ Done |
| 2 | `eq_analyzer/event_risk.py` | ✅ Done |
| 3 | `eq_analyzer/insider_activity.py` | ✅ Done |
| 4 | `price_structure/execution_layer.py` | ✅ Done |
| 5 | `contracts/eq_schema.py` | ✅ Done |
| 6 | `contracts/price_structure_schema.py` | ✅ Done |
| 7 | `price_structure/level_detector.py` | ✅ Done |
| 8 | `price_structure/price_structure_analyzer.py` | ✅ Done |
| 9 | `eq_analyzer/main.py` | ⚠️ Partial — return tuple started, need to finish the final `return` line |
| 10 | `main.py` | ❌ Not started — Steps 27g, 27h, 27d capture, 27f execution fields |
| 11 | `reports/report_builder.py` | ❌ Not started — all 1A/1B/1C display changes |
| 12 | `reports/dashboard_builder.py` | ❌ Not started — `_RANK_FETCH_JS` + `_update_rank_board` |

**Frontend roadmap (for you to do manually in `docs/assets/style.css`):**

Add these 5 CSS classes after the existing `.rpill-ps-wk` block:
```css
.rpill-ev-ok { background: rgba(57,232,160,0.12); color: var(--up); border-color: rgba(57,232,160,0.35); }
.rpill-ev-hr { background: rgba(255,77,109,0.18); color: var(--dn); border-color: rgba(255,77,109,0.45); font-weight: 700; }
.rpill-ins-ac { background: rgba(57,232,160,0.12); color: var(--up); border-color: rgba(57,232,160,0.35); }
.rpill-ins-di { background: rgba(255,77,109,0.18); color: var(--dn); border-color: rgba(255,77,109,0.45); }
.rpill-ins-na { background: rgba(168,155,194,0.10); color: var(--mist); border-color: rgba(168,155,194,0.25); }
```

**Can you start a new message so I can finish files 9–12?** I have the full context of what needs to happen in each — it's about 3–4 more tool calls to complete the backend.

read this, i already started with another claude however my message and session limits was hit on that claude so we will continue here; we already made some progress on the backend so right now we will finish the entire thingswhat the back end part is left and the entire front end. you can check the file so you get the context you need to continue.

Now adding exec fields to both Step 27f stamp blocks, then Steps 27g and 27h.Now add Steps 27g and 27h after `# ── End Step 27f ─────`:`main.py` done. Now `report_builder.py` — all 1A/1B/1C changes.Now check the imports at the top of report_builder.py for PS_RR_OVERRIDE and PS_RISK_REWARD_RATIO:Now add exec fields to `_build_ps_display()`:Now add exec fields to the AI prompt's Price Structure section and BUY NOW gate:Now add Event Risk and Insider Activity blocks to the candidate_block, and update BUY NOW gate:Now update BUY NOW gate (ALL FIVE → ALL SIX) and add conditions 6 + conflict rules:---

**Completed in this message:**
- `eq_analyzer/main.py` — return tuple ✅
- `main.py` — PS exec imports, `eq_fetcher` capture, exec fields in both 27f blocks, Steps 27g + 27h ✅
- `reports/report_builder.py` — PS exec imports, `_build_ps_display` exec fields (both paths), notices block (earnings_warning removed, event_risk + insider + RR override added), AI prompt exec fields + Event Risk + Insider Activity sections, BUY NOW gate 5→6 ✅

**Still needs one more message:**
- `reports/report_builder.py` — CONFLICT AND RISK RULES additions (R/R and insider rules)
- `reports/dashboard_builder.py` — `_RANK_FETCH_JS` (evRisk + insS vars, 2 new pills in pill row, exec fields in PS expanded block) + `_update_rank_json` (6 new fields)

**CSS for you to add manually** (already covered last session — just confirm you have it):
```css
.rpill-ev-ok { background: rgba(57,232,160,0.12); color: var(--up); border-color: rgba(57,232,160,0.35); }
.rpill-ev-hr { background: rgba(255,77,109,0.18); color: var(--dn); border-color: rgba(255,77,109,0.45); font-weight: 700; }
.rpill-ins-ac { background: rgba(57,232,160,0.12); color: var(--up); border-color: rgba(57,232,160,0.35); }
.rpill-ins-di { background: rgba(255,77,109,0.18); color: var(--dn); border-color: rgba(255,77,109,0.45); }
.rpill-ins-na { background: rgba(168,155,194,0.10); color: var(--mist); border-color: rgba(168,155,194,0.25); }
```

Start a new message and I'll finish `report_builder.py` CONFLICT rules + all of `dashboard_builder.py` and produce the final downloadable files.
