# MRE FRONTEND UPDATE — AGENT PROMPT v6.2
**Target agent:** Claude Sonnet 4.6 inside Antigravity IDE  
**If quota runs out mid-run:** Stop cleanly at end of current task. A continuation prompt will be provided to resume.

---

## YOUR IDENTITY AND OBJECTIVE

You are implementing a complete frontend visual redesign of the MRE (Market Research Engine) GitHub Pages dashboard. The engine is a live, operational Python 3.11 stock research system. You are updating its frontend only — the backend logic, scoring systems, and report pipeline are untouched except for three precise additions described below.

You have access to the full repository. Work methodically through each task in order. After completing each numbered task, write a short comment at the bottom of the last file you edited so a continuation agent knows exactly where you stopped.

---

## THE REFERENCE TEMPLATE

The file `mre_updated.html` in the repository root (or provided separately) is a 1720-line single-file HTML mockup. Study it fully before writing a single line of code.

**Critical rule:** You are NOT converting the engine to a single-page app. The template is a SPA with JavaScript tab switching — the engine uses separate HTML files per page with real `<a href>` navigation. You extract the design language from the template and apply it to each separate file individually.

**Polish rule:** Implement all animations, transitions, and visual effects exactly as they appear in the template — same polish, no downgrades. If a cleaner or more optimized implementation produces the same or better visual result, use it. Never simplify or remove a visual effect.

---

## WHAT YOU MUST NEVER TOUCH

Read this before touching any file. Violations break the live engine.

- `main.py` — only two additions allowed, described precisely in Tasks 10 and 12
- Everything in `analyzers/`, `filters/`, `eq_analyzer/`, `sector_detector/`, `contracts/`, `utils/` — zero changes
- `reports/report_builder.py` — zero changes
- `reports/email_builder.py` — zero changes
- `reports/summary_builder.py` — zero changes
- `docs/assets/data/reports.json` — never change structure, only add fields if needed
- `docs/assets/data/rank.json` — never change structure, only add fields
- `docs/assets/data/weekly_archive.json` — never change structure, only add fields
- Never use `print()` — always use the logger (`from utils.logger import get_logger`)
- Never use `datetime.now()` — always `datetime.now(pytz.utc)`
- Never raise exceptions from render functions — all wrapped in try/except returning safe defaults

---

## THE DESIGN SYSTEM

Extract these exactly from `mre_updated.html` and apply consistently across all dashboard pages.

**CSS variables** — copy verbatim from template `:root` block:
`--void`, `--l1`, `--l2`, `--l3`, `--l4`, `--pu`, `--pu-lt`, `--pu-dk`, `--pu-bg`, `--pu-glow`, `--mg`, `--mg-bg`, `--sun`, `--cyan`, `--up`, `--up-bg`, `--dn`, `--dn-bg`, `--nt`, `--snow`, `--slate`, `--mist`, `--ghost`, `--rim`, `--rim2`, `--rim3`, `--ff-head`, `--ff-mono`, `--apple`, `--soft-out`, `--ease`, `--spring`, `--genie`

**Fonts:** Orbitron (headings) + Share Tech Mono (monospace body) from Google Fonts CDN:
```
https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Share+Tech+Mono&display=swap
```

**Score color mapping — use everywhere a score or signal needs color:**
- Confidence ≥ 75 → `var(--up)` — Low Risk
- Confidence 50–74 → `var(--nt)` — Moderate Risk
- Confidence 35–49 → `var(--dn)` — Weak
- Confidence < 35 → `var(--ghost)` — Excluded
- Market verdict RESEARCH NOW → `var(--up)`
- Market verdict WATCH → `var(--nt)`
- Market verdict SKIP → `var(--dn)`
- EQ Supportive → `var(--up)`, Neutral → `var(--nt)`, Weak/Risky → `var(--dn)`, Unavailable → `var(--mist)`
- Rotation SUPPORT → `var(--up)`, WAIT → `var(--nt)`, WEAKEN → `var(--dn)`, UNKNOWN → `var(--mist)`
- Breadth strong → `var(--up)`, weak → `var(--dn)`, neutral → `var(--nt)`

---

## HTML ESCAPING — MANDATORY RULE

Any **string value** derived from data (tickers, sector names, headline titles, source names, verdict strings, conclusion text) inserted into HTML must be escaped. Add this import at the top of `dashboard_builder.py` if not present:

```python
import html
```

**Use the `_esc()` helper defined below — never call `html.escape()` inline directly.** This ensures the escaping contract is applied consistently and can be updated in one place.

Define at module level in `dashboard_builder.py`:
```python
def _esc(val) -> str:
    """
    Escape a data-derived string value for HTML insertion.
    Returns '—' for None/empty. Apply exactly once per value at render time.
    Never apply to pre-formatted numeric strings (_fmt_pct, _fmt_score, etc.).
    Never apply to values already passed through _esc() — no double-escaping.
    """
    if not val:
        return '—'
    return html.escape(str(val))
```

**Do NOT apply `_esc()` to numeric values.** Numbers formatted via `_fmt_pct()` or `_fmt_score()` are already safe — escaping them is unnecessary overhead. The rule applies to strings from external data sources only.

**Double-escape rule:** Never escape the same string twice. The `body` field from article objects is raw text from `_norm_article()` — it is not pre-escaped. Apply `_esc()` exactly once at render time. If upstream pipeline ever changes to store pre-escaped text, this rule must be revisited before touching escape calls.

---

## F-STRING ESCAPING RULES — READ BEFORE WRITING ANY PYTHON

`dashboard_builder.py` generates all HTML via Python f-strings. This is the highest-risk area for silent bugs.

Rules:
1. All `{` and `}` in CSS or JS inside an f-string must be doubled: `{{` and `}}`
2. Single quotes inside f-strings are safe. Use them for HTML attributes: `class='foo'` not `class="foo"`
3. For onclick handlers: `onclick='myFunc("arg")'`
4. Python variable interpolation uses `{variable}` — all other `{` must be `{{}}`
5. For Python data injected into any `<script>` context: use the appropriate helper — see JSON injection rules below. **Never use `json.dumps()` directly in any `<script>` context.**
6. **Large JS blocks rule:** Do NOT embed multi-line JS functions containing many `{` `}` inside f-strings. Define large JS blocks as module-level Python string constants (triple-quoted, not f-strings), then inject only dynamic data values separately as small f-string snippets:

```python
# At module level — not an f-string, no escaping needed
_RANK_JS = """
function expT(btn) {
  var el = document.getElementById(btn.dataset.ref);
  if (!el) return;
  var data;
  try { data = JSON.parse(el.textContent); } catch(e) { data = []; }
  // ... rest of function
}
"""

# In render function — only inject dynamic data
data_block = f'<script type="application/json" id="ph-{i}">{_safe_json(ph_list)}</script>'
```

7. Any CSS keyframe or JS object literal that must go inside a render function f-string uses `{{` and `}}` — verify mentally before finalizing

---

## JSON INJECTION RULES — TWO STRICT PATTERNS, NO MIXING

These two patterns are mutually exclusive. Never swap helpers. Never use `json.dumps()` directly in any `<script>` context — always use one of the two helpers below.

| Context | Helper |
|---|---|
| `<script type="application/json">...</script>` | `_safe_json()` |
| `<script>const X = ...;</script>` (inline JS assignment) | `_safe_js_json()` |

**Pattern A — `<script type="application/json">` blocks (data containers read by JS via `JSON.parse`):**

Define at module level in `dashboard_builder.py`:
```python
def _safe_json(data) -> str:
    """
    Serialize data for <script type="application/json"> blocks.
    Escapes </script> to prevent premature tag closing.
    Escapes U+2028 and U+2029 (line/paragraph separators) which are valid JSON
    but can cause parsing issues in some browsers when embedded in HTML.
    Use ONLY for application/json script blocks.
    Never use for inline JS variable assignments — use _safe_js_json() instead.
    Never use json.dumps() directly in any <script> context.
    """
    return (
        json.dumps(data)
        .replace('</script>', '<\\/script>')
        .replace('\u2028', '\\u2028')
        .replace('\u2029', '\\u2029')
    )
```

Usage:
```python
f'<script type="application/json" id="{uid}">{_safe_json(prompt_text)}</script>'
f'<script type="application/json" id="ph-{i}">{_safe_json(ph_list)}</script>'
```

**Pattern B — Inline JS variable assignments inside `<script>` blocks:**

Define at module level in `dashboard_builder.py`:
```python
def _safe_js_json(data) -> str:
    """
    Serialize data for inline JS variable assignment inside <script> blocks.
    ensure_ascii=True eliminates \\u2028/\\u2029 line/paragraph separators that
    are valid JSON but break JS execution in <script> context.
    </script> escape prevents tag injection via data values.
    Use ONLY for: const X = {_safe_js_json(data)};
    Never use for <script type="application/json"> blocks — use _safe_json() instead.
    Never use json.dumps() directly in any <script> context.
    """
    return json.dumps(data, ensure_ascii=True).replace('</script>', '<\\/script>')
```

Usage:
```python
f'<script>const IDX_DATA = {_safe_js_json(idx_data_dict)};</script>'
```

**Absolute rule:** `_safe_json()` for Pattern A only. `_safe_js_json()` for Pattern B only. `json.dumps()` never appears directly in any `<script>` context anywhere in this codebase. This applies to all pages: index, rank, archive, and any future pages.

---

## SAFE NUMERIC FORMATTING — MANDATORY PATTERN

Fields like `signal_agreement`, `opportunity_score`, `risk_score`, `composite_confidence`, `return_1m`, `return_3m`, `return_6m`, index `value`, index `change_pct` can be `None`. Never call `round()`, `f'{val:.2f}'`, or any format operation without a None guard.

Define these as module-level helpers in `dashboard_builder.py`:

```python
def _fmt_pct(val) -> str:
    """Format a percentage value with arrow. Returns '—' for None/non-numeric."""
    if not isinstance(val, (int, float)):
        return '—'
    arrow = '▲' if val > 0 else '▼' if val < 0 else '—'
    return f'{arrow}{abs(val):.1f}%'

def _fmt_score(val, decimals=1) -> str:
    """Format a numeric score. Returns '—' for None/non-numeric."""
    if not isinstance(val, (int, float)):
        return '—'
    return f'{val:.{decimals}f}'

def _fmt_price(val) -> str:
    """Format a price value. Returns '—' for None/non-numeric."""
    if not isinstance(val, (int, float)):
        return '—'
    return f'${val:,.2f}'

def _fmt_index_val(val) -> str:
    """Format an index value (e.g. 44210). Returns '—' for None/non-numeric."""
    if not isinstance(val, (int, float)):
        return '—'
    return f'{val:,.0f}'

def _calc_return_from_history(data: list, trading_days: int) -> str:
    """
    Calculate approximate return over N trading days from a price history list.
    Returns formatted display string like '▲2.4%' or '—' if insufficient data.
    For display only — never use the return value for calculations.
    """
    if not data or len(data) <= trading_days:
        return '—'
    try:
        start = data[-trading_days - 1]
        end   = data[-1]
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            return '—'
        if start == 0:
            return '—'
        pct   = ((end - start) / start) * 100
        arrow = '▲' if pct > 0 else '▼' if pct < 0 else '—'
        return f'{arrow}{abs(pct):.1f}%'
    except Exception:
        return '—'

def _sanitize_price_history(raw: list) -> list:
    """
    Remove any non-numeric or NaN values from a price history list before storage.

    SYSTEM CONTRACT: rank.json MUST NEVER contain unsanitized price_history.
    All writes to price_history in rank.json must pass through _update_rank_board(),
    which calls this function. Never bypass _update_rank_board() to write price_history
    directly to rank.json — doing so breaks the Chart.js render pipeline.
    """
    import math
    if not raw or not isinstance(raw, list):
        return []
    return [p for p in raw if isinstance(p, (int, float)) and not math.isnan(p)]
```

---

## CHART.JS INTEGRATION

Chart.js is used in two places only: the index pill expand panel (index page) and the rank row expand panels (rank page). No other pages use Chart.js.

**CDN link — include on index and rank pages only, with `defer`:**
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js" defer></script>
```

The `defer` attribute ensures Chart.js is parsed before inline scripts execute on page load, eliminating load timing races. However, expand rows can be triggered by user interaction before Chart.js is ready on very slow connections. Therefore, add a `typeof Chart === 'undefined'` guard inside `mkC()` only (see below). Do not add this guard to `expT()` — the expand row must always open regardless of chart availability.

**Canvas ID pattern — enforce strictly:**
- Index expand panel: `id='idx-chart'` (single canvas, reused per pill — matches template)
- Rank expand rows: `id='ec{i}'` where `i` is the 1-based row index

**Chart memory leak prevention — mandatory:**

All Chart.js instances must be tracked and destroyed before reinitializing on the same canvas. Define at module level in the JS constants:

```javascript
window._mreCharts = window._mreCharts || {};

function mkC(cid, data) {
  if (typeof Chart === 'undefined') return;
  var canvas = document.getElementById(cid);
  if (!canvas) return;
  if (window._mreCharts[cid]) {
    window._mreCharts[cid].destroy();
    delete window._mreCharts[cid];
  }
  var up  = data[data.length - 1] >= data[0];
  var col = up ? '#39e8a0' : '#ff4d6d';
  window._mreCharts[cid] = new Chart(canvas, {
    // ... chart config
  });
}
```

**Index charts:** Build `IDX_DATA` dict in Python, inject using `_safe_js_json()` (Pattern B):
```python
idx_data_dict = _build_idx_data(index_history, indices)
idx_script    = f'<script>const IDX_DATA = {_safe_js_json(idx_data_dict)};</script>'
```

Build the dict using this helper:
```python
def _build_idx_data(index_history: dict, indices: dict) -> dict:
    configs = {
        'dow': ('Dow Jones', '#9b59ff', 'dow'),
        'sp':  ('S&P 500',   '#ff6eb4', 'sp500'),
        'nq':  ('Nasdaq',    '#00e5ff', 'nasdaq'),
    }
    result = {}
    for key, (name, color, hist_key) in configs.items():
        data = _sanitize_price_history(index_history.get(hist_key) or [])
        result[key] = {
            'name':   name,
            'color':  color,
            'data':   data,
            'stat1m': _calc_return_from_history(data, 21),
            'stat3m': '—',
            'stat6m': '—',
        }
    return result
```

`stat3m` and `stat6m` display `'—'` — the 30-day history window does not cover 90 or 180 days. Do not invent values you cannot compute from available data.

Copy `buildIdxChart()`, `animateGenie()`, `animateSlide()`, `toggleIdx()` from template as module-level string constants (not inside f-strings). Integrate the `window._mreCharts` destroy pattern into `buildIdxChart()`.

**Rank charts:** Per-stock price history in `<script type="application/json">` block (Pattern A). `expT()` reads via `data-ref`. Color in JS using hex literals (JS cannot read CSS custom properties):
```javascript
var up  = data[data.length - 1] >= data[0];
var col = up ? '#39e8a0' : '#ff4d6d';
```

**JS guard inside `expT()` — mandatory structure:**
```javascript
function expT(btn) {
  var el = document.getElementById(btn.dataset.ref);
  if (!el) return;
  var data;
  try { data = JSON.parse(el.textContent); } catch(e) { data = []; }
  var cid = btn.dataset.cid;
  var eid = btn.dataset.eid;
  // expand row open logic always runs — stats are useful even without chart
  // ... expand open logic here ...
  // chart init is gated — only attempt if data is valid
  if (data && data.length >= 2) {
    mkC(cid, data);  // mkC() itself guards typeof Chart === 'undefined'
  }
  // if data.length < 2, Python already rendered the "unavailable" message — nothing to do
}
```

The expand row always opens. Python is the single source of truth for whether a canvas element exists in the DOM (`has_chart = len(ph_list) > 1` controls this). JS only gates chart initialization — it never controls DOM structure.

Copy `mkC()`, `countUp()`, `rafCollapseRow()`, `closeExpRow()`, `closeExpRowInstant()` from template as module-level string constants. Integrate the `window._mreCharts` destroy pattern into `mkC()` as shown above.

**Empty data safety:** If sanitized `price_history` has fewer than 2 points, Python renders the expand panel without a canvas. Show:
```html
<div style='color:var(--mist);font-size:11px;padding:8px 0;'>Price history unavailable</div>
```

---

## TASK 1 — Replace `docs/assets/style.css`

Replace the entire file. Include:
- All CSS variables from template `:root` block (copy verbatim)
- All shared component classes: `.scanlines`, nav styles (`.brand`, `.brand-pulse`, `.nav-tabs`, `.tab`, `.tab.on`, `.tab::after`), `.page` base, `.sl`, `.status-strip`, `.idx-pill`, `.idx-expand` base, `.rank-preview` and children, `.rcard` and children, `.btn`, `.npc`, `.npc-stripe`, `.npc-title`, `.npc-meta`, `.ntag` variants, `.week-block`, `.week-head`, `.guide-card`, `.guide-term`, `.guide-desc`, `.thresh`, `.sys-pill` variants, `.pg-eyebrow`, `.pg-title`, `.pg-sub`, `.pex-item`, `.pex-k`, `.pex-v`, footer styles, scrollbar styles, responsive breakpoints
- All keyframe animations: `gradient-drift`, `radar-ring-slow`, `page-in`, `stagger-up`, `prv-snap`, `pex-spark`
- All easing curves as CSS custom properties

Page-specific styles (rank table column grid, exp-row, Chart.js canvas wrappers, idx-expand JS-driven clip-path states) go in each page's own `<style>` block.

---

## TASK 2 — Rewrite `_nav_html(active)` in `reports/dashboard_builder.py`

Returns an HTML string. Called by every render function with the active page name.

New nav must match template exactly:
- Sticky, `z-index: 200`, blurred backdrop (`backdrop-filter: blur(24px)`)
- Top gradient border line (purple → magenta → amber → transparent)
- Brand left: `.brand-pulse` dot with `radar-ring-slow` animation + "MRE // System" in Orbitron
- Right: tab buttons for Home, Rank, News, Archive, Guide
- Active tab: `on` class triggers `color: var(--pu-lt)` and bottom underline via `::after` in shared CSS
- Tab links: `index.html`, `rank.html`, `news.html`, `archive.html`, `guide.html`
- Active tab determined by Python `active` parameter — not JavaScript

**Nav CSS lives entirely in `style.css`.** Python emits only HTML structure with class names.

**Consistency rule:** `guide.html` (static file) and all Python-generated pages must use identical nav HTML structure — same class names, same element hierarchy. The static `guide.html` nav is a manual copy of the `_nav_html('guide')` output. If `_nav_html()` ever changes, `guide.html` must be updated to match. `.tab.on` behavior defined once in shared CSS, works everywhere.

---

## TASK 3 — Rewrite `_render_index_html()` in `reports/dashboard_builder.py`

Define all large JS functions as module-level string constants before this function. Build the page in this order.

**Page head:** CSS link, Chart.js CDN with `defer`, Google Fonts link, page-specific `<style>` block.

**Page structure:**
```
body → div.scanlines → nav (_nav_html('home')) → div.pages → div#p-home.page.on
  pg-eyebrow, pg-title "Market Overview", pg-sub (last scan time + candidate count)
  idx-section: 3 pills + expand panel
  div#home-below:
    status-strip
    rank-preview (top 5)
    Recent Reports (rcard cards, max 14)
    Signal Headlines (npc widget, max 5)
footer
```

**Index pills:** Values from `indices` dict via `_fmt_index_val()`. Change color/arrow from `change_pct` field. Guard against missing dict:
```python
indices = indices or {}
```

**IDX_DATA injection (Pattern B — inline JS):**
```python
idx_data_dict = _build_idx_data(index_history, indices)
idx_script    = f'<script>const IDX_DATA = {_safe_js_json(idx_data_dict)};</script>'
```

**home-below displacement engine:** Copy the full `requestAnimationFrame`-based system from the template that smoothly pushes `#home-below` on genie open/close. Define as module-level string constant. Include a null guard at the top of the displacement function:
```javascript
var el = document.getElementById('home-below');
if (!el) return;
```
Non-negotiable polish.

**Rank preview:**
```python
stocks_raw = rank_data.get('stocks', {})
if isinstance(stocks_raw, dict):
    all_stocks = list(stocks_raw.values())
else:
    all_stocks = stocks_raw or []
# Filter out malformed entries before sort
all_stocks = [s for s in all_stocks if isinstance(s, dict)]
top_stocks = sorted(
    all_stocks,
    key=lambda x: x.get('confidence') if isinstance(x.get('confidence'), (int, float)) else -1,
    reverse=True
)[:5]
```
Columns: `#`, Ticker, Sector, Conf, Risk, EQ, Rotation. All string values through `_esc()`. Verdict display: `stock.get('market_verdict_display') or stock.get('market_verdict', '—')`.

**Report cards:** Read `reports.json`. Normalize:
```python
if not isinstance(reports_data, dict):
    reports = []
else:
    reports_raw = reports_data.get('reports')
    if not isinstance(reports_raw, list):
        reports = []
    else:
        reports = reports_raw
```
Each rcard: date, time, slot, count, breadth badge. Expanded: tickers (escaped via `_esc()`), top score via `_fmt_score()`, verdict counts (RN/W/S). "Full Report" → `report_url`, opens new tab. "⧉ AI Prompt" copy button — see spec below.

**Signal Headlines npc widget:**
```python
try:
    with open(news_path, encoding='utf-8') as f:
        news_data = json.load(f)
    sectors = news_data.get('sectors')
    if not isinstance(sectors, list):
        sectors = []
    all_articles = []
    for sec in sectors:
        for art in sec.get('articles', []):
            new_art = dict(art)               # copy — never mutate original
            new_art['sector'] = sec['sector']
            all_articles.append(new_art)
    all_articles.sort(
        key=lambda x: x.get('score') if isinstance(x.get('score'), (int, float)) else 0,
        reverse=True
    )
    top_headlines = all_articles[:5]
except Exception:
    top_headlines = []
```
Each `npc` card: stripe color by score (score > 5 → `var(--up)`, score > 2 → `var(--nt)`, else `var(--pu-lt)`), title truncated to 120 chars then escaped: `_esc(art.get('title', '')[:120])`, sector ntag (`_esc(art.get('sector', ''))` title-cased, replace `_` with space), source `_esc(art.get('source') or 'Unknown')` + ` · ` + published string. "All →" → `news.html`. If `top_headlines` empty: `<div style='color:var(--mist);font-family:var(--ff-mono);font-size:11px;'>No signal headlines this run.</div>`.

**Copy AI Prompt button spec:**

`report_index` must be the loop counter from `enumerate(reports, 1)` — use the integer directly. Do not derive it from any other source. This guarantees unique IDs within the page.

```python
uid          = f'prompt_{report_index}'
script_block = f'<script type="application/json" id="{uid}">{_safe_json(prompt_text)}</script>'
button_html  = f'<button class="btn mg copy-prompt-btn" data-ref="{uid}">&#x2389; AI Prompt</button>'
```
If `prompt_text` is empty or None: do not render script block or button.

Define this copy handler as a module-level string constant. Emit once per page, wrapped in `DOMContentLoaded`:
```javascript
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.copy-prompt-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var el = document.getElementById(this.dataset.ref);
      if (!el) return;
      var text;
      try {
        text = JSON.parse(el.textContent);
      } catch(e) {
        // Parse failed — show error state, do not expose raw JSON
        var self2 = this;
        self2.textContent = 'Error';
        self2.style.transition = 'color 0.3s ease, border-color 0.3s ease';
        self2.style.color = 'var(--dn)';
        setTimeout(function() {
          self2.textContent = '\u2389 AI Prompt';
          self2.style.color = '';
        }, 1800);
        return;
      }
      var self = this;
      function onCopied() {
        var orig = self.textContent;
        self.textContent = 'Copied \u2713';
        self.style.transition = 'color 0.3s ease, border-color 0.3s ease';
        self.style.color = 'var(--up)';
        self.style.borderColor = 'rgba(57,232,160,.5)';
        setTimeout(function() {
          self.textContent = orig;
          self.style.color = '';
          self.style.borderColor = '';
        }, 1800);
      }
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(onCopied).catch(function() {
          var ta = document.createElement('textarea');
          ta.value = text; document.body.appendChild(ta);
          ta.select(); document.execCommand('copy');
          document.body.removeChild(ta); onCopied();
        });
      } else {
        var ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta);
        ta.select(); document.execCommand('copy');
        document.body.removeChild(ta); onCopied();
      }
    });
  });
});
```

**Data safety:** Every file read wrapped in try/except. Missing file or field returns safe fallback. Render function must never raise.

**Render function fallback:**
```python
except Exception as e:
    log.error(f'Index page render failed: {e}')
    return f'''<!DOCTYPE html><html lang="en"><head>
    <meta charset="UTF-8"><title>MRE // Error</title>
    <link rel="stylesheet" href="assets/style.css">
    </head><body><div class="scanlines"></div>
    {_nav_html('home')}
    <div style="padding:44px 28px;color:var(--dn);font-family:var(--ff-mono);">
    Dashboard render error. Check logs.</div></body></html>'''
```
Apply equivalent fallback to all render functions.

---

## TASK 4 — Rewrite `_render_rank_html()` in `reports/dashboard_builder.py`

**Page head:** CSS link, Chart.js CDN with `defer`, Google Fonts, page-specific `<style>`.

**Page structure:**
```
body → div.scanlines → nav (_nav_html('rank')) → div.pages → div#p-rank.page.on
  pg-eyebrow "Rank Board · Active", pg-title "Weekly Rankings", pg-sub
  rank-wrap: rank-head + rows
footer
```

**Rank table columns:** `#`, Ticker, Sector, Price, Conf, Risk, EQ, Rotation

**Stocks normalization and sort:**
```python
stocks_raw = rank_data.get('stocks', {})
if isinstance(stocks_raw, dict):
    stocks = list(stocks_raw.values())
else:
    stocks = stocks_raw or []
# Filter out malformed entries before sort
stocks = [s for s in stocks if isinstance(s, dict)]
stocks = sorted(
    stocks,
    key=lambda x: x.get('confidence') if isinstance(x.get('confidence'), (int, float)) else -1,
    reverse=True
)
```

**Per-row data:**
- `ticker` → Orbitron font, `_esc()`
- `sector` → `_esc(stock.get('sector', '').replace('_', ' ').title())`
- `price` → `_fmt_price(stock.get('price'))`
- `confidence` → `_fmt_score(val, 0)`, color by score mapping
- `risk_score` → `_fmt_score(val, 0)`, `var(--mist)`
- `eq_verdict_display` → ntag, `_esc()`
- `rotation_signal_display` → ntag, `_esc()`
- Market verdict display: `stock.get('market_verdict_display') or stock.get('market_verdict', '—')`

**Price history script tag per row (Pattern A):**
```python
raw_ph    = stock.get('price_history') or []
ph_list   = _sanitize_price_history(raw_ph)
has_chart = len(ph_list) > 1
ph_uid    = f'ph-{i}'
ph_block  = f'<script type="application/json" id="{ph_uid}">{_safe_json(ph_list)}</script>'
```

Row element includes: `data-ref="{ph_uid}"` and `data-eid="e{i}"` and `data-cid="ec{i}"`.

**Expand row per stock:**
Stats: 1M via `_fmt_pct(stock.get('return_1m'))`, 3M via `_fmt_pct(stock.get('return_3m'))`, 6M via `_fmt_pct(stock.get('return_6m'))`, Opportunity via `_fmt_score(stock.get('opportunity_score'), 0)` + `/100`, Signal Agreement via `_fmt_score(stock.get('signal_agreement'), 2)`, Verdict via `_esc(stock.get('market_verdict_display') or stock.get('market_verdict', '—'))`.

Canvas only if `has_chart` True: `<canvas id='ec{i}' height='92'></canvas>`. If False: price history unavailable message.

**JS functions as module-level constants:** `expT()` (see structure in Chart.js section), `mkC()` (with `window._mreCharts` destroy pattern), `countUp()`, `rafCollapseRow()`, `closeExpRow()`, `closeExpRowInstant()`. Copy from template and adapt per the `expT()` structure and `mkC()` pattern defined in the Chart.js integration section above.

**Empty state:** If no stocks: `<div style='color:var(--mist);font-family:var(--ff-mono);padding:28px;'>No candidates this week.</div>`

---

## TASK 5 — Rewrite `_render_archive_html()` in `reports/dashboard_builder.py`

**Page head:** CSS link, Google Fonts. NO Chart.js.

**Page structure:**
```
body → div.scanlines → nav (_nav_html('archive')) → div.pages → div#p-archive.page.on
  pg-eyebrow "History · Stored", pg-title "Report Archive"
  week-blocks (newest week first)
footer
```

**Week data:**
```python
weeks = archive_data.get('weeks', {})
sorted_weeks = sorted(weeks.keys(), reverse=True)
```

**Per-run prompt script block (Pattern A):**

`run_idx` must be the loop counter from `enumerate(run_entries, 1)` where `run_entries` is the list of runs for the current week. Combined with `week_key` this produces globally unique IDs across the page.

```python
prompt_text = run_entry.get('prompt', '')
if prompt_text:
    uid          = f'prompt_{week_key}_{run_idx}'
    script_block = f'<script type="application/json" id="{uid}">{_safe_json(prompt_text)}</script>'
    copy_btn     = f'<button class="btn mg copy-prompt-btn" data-ref="{uid}">&#x2389; AI Prompt</button>'
else:
    script_block = ''
    copy_btn     = ''
```

**Expanded rcard content:** Per-candidate from `run_entry.get('candidates', [])`: ticker (`_esc()`), confidence via `_fmt_score()`, eq_verdict (`_esc()`), rotation_signal (`_esc()`), conclusion (`_esc(str(val)[:200])`).

Include same copy button JS handler (module-level constant, emit once per page, wrapped in `DOMContentLoaded`).

**rcT() expand/collapse:** Copy from template as module-level constant.

---

## TASK 6 — Rewrite `docs/guide.html`

Static file — write directly, not via Python.

Structure:
- Full `<html>` with `<link>` to `assets/style.css` + Google Fonts
- `<div class="scanlines"></div>`
- Nav: identical HTML structure to `_nav_html('guide')` output — copy exact class names and element hierarchy. Guide tab rendered as `<button class='tab on' ...>`. Mark with comment:

```html
<!-- NAV: MUST MATCH _nav_html('guide') OUTPUT EXACTLY.
     If _nav_html() changes, update this file to match. -->
```

- Page content:
  1. System Architecture: three `sys-pill` badges (sp1/sp2/sp3) + description paragraph
  2. Confidence Score Bands: four `thresh` rows (75–100 green, 50–74 amber, 35–49 red, <35 ghost)
  3. Key Terms: `guide-card` grid — 8 template cards plus "Combined Priority Score", "Entry Urgency", "Signal Agreement"
  4. System Limitations: free tier, 15-min delay, no real-time, no backtesting, no trades, no positions
- Footer

---

## TASK 7 — Build `docs/news.html` via `_write_news_page()`

Add `_write_news_page(confirmed_sectors: dict)` to `dashboard_builder.py`. Called from `build_dashboard()` every run.

**Use the `confirmed_sectors` parameter directly — do not re-read `news.json` from disk.**

Guard against malformed input at function entry:
```python
if not isinstance(confirmed_sectors, dict):
    confirmed_sectors = {}
```

Design intent (document in code comments):
- `_write_news_json()` — **preserve-on-empty:** if `confirmed_sectors` is empty this run, the JSON file is left unchanged so the index page npc widget retains last-run headlines.
- `_write_news_page()` — **run-current:** always reflects this run's state. If nothing confirmed, renders placeholder.
- These two functions intentionally diverge on empty input. This may cause the index page and news page to temporarily display different data states after empty runs. This is by design.

Build sector list from parameter, sorted by score descending:
```python
if not confirmed_sectors:
    sectors   = []
    generated = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York')).strftime('%Y-%m-%d %H:%M ET')
else:
    now_et    = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    generated = now_et.strftime('%Y-%m-%d %H:%M ET')
    sectors   = sorted(
        [
            {
                'sector':   sector,
                'score':    data.get('score', 0),
                'articles': data.get('articles', []),
            }
            for sector, data in confirmed_sectors.items()
            if data.get('articles')
        ],
        key=lambda x: x['score'] if isinstance(x['score'], (int, float)) else 0,
        reverse=True,
    )
```

**Live page** (sectors not empty): grouped by sector. Each `news-sec-head`: colored stripe (score ≥ 5 → `var(--up)`, score ≥ 2 → `var(--nt)`, else `var(--pu-lt)`), sector name (`_esc(sector.replace('_', ' ').title())`), article count. Each `news-card-full`:
- Title: `_esc((article.get('title') or '')[:180])`
- Summary: `_esc((article.get('body') or '')[:200])` — applied once, raw text only
- Source + time: `_esc(article.get('source') or 'Unknown')` + ` · ` + `_esc(article.get('published') or '')`
- NO "Read more" link — articles have no `url` field. Do not invent URLs.

**Placeholder page** (sectors empty): full design applied, message "Signal Headlines — Coming Soon. Data will populate after the next market run."

Write page using atomic write pattern:
```python
tmp_path = news_html_path + '.tmp'
with open(tmp_path, 'w', encoding='utf-8') as f:
    f.write(html_content)
os.replace(tmp_path, news_html_path)
```

---

## TASK 8 — Update Jinja2 full report templates

Files: `reports/templates/intraday_full.html` and `reports/templates/closing_full.html`

Scope: color palette and fonts only. Zero layout changes. Zero JS additions.

1. Add Google Fonts `<link>` in `<head>`
2. Add CSS variables `:root` block at top of inline `<style>`
3. Replace font stack with `'Share Tech Mono', monospace`
4. Replace color values:
   - `#0a0a0f`, `#0f0f1a` → `var(--void)`, `var(--l1)`
   - `#141428`, `#1a1a35` → `var(--l2)`, `var(--l3)`
   - `#e8e8f0` → `var(--snow)`
   - `#8888aa` → `var(--slate)`
   - `#444466` → `var(--mist)`
   - `#00ff88` → `var(--up)`
   - `#ff3355` → `var(--dn)`
   - `#ffcc00` → `var(--nt)`
   - `#00aaff` → `var(--cyan)`
   - `#aa55ff` → `var(--pu)`
5. Do not change HTML structure, Jinja2 variables `{{ }}` / `{% %}`, or class names

---

## TASK 9 — Update Jinja2 email templates

Files: `reports/templates/intraday_email.html` and `reports/templates/closing_email.html`

Scope: color hex values only. No CSS variables. No fonts. No JS. No layout changes.

Replace hex values inline (email clients ignore CSS variables and external fonts):
- `#0a0a0f` / `#0f0f1a` → `#0a0610` / `#130f22`
- `#141428` → `#1a1430`
- `#e8e8f0` → `#f0eaff`
- `#8888aa` → `#8878b8`
- `#00ff88` → `#39e8a0`
- `#ff3355` → `#ff4d6d`
- `#ffcc00` → `#ff9a3c`
- `#00aaff` → `#00e5ff`
- `#aa55ff` → `#9b59ff`

Do not add `<link>`, `<script>`, CSS variable references. Do not change HTML structure or Jinja2 variables.

---

## TASK 10 — Add index price history to `market_collector.py`

Add this function:

```python
def get_index_history() -> dict:
    """
    Fetches 30-day closing price history for major indices.
    Returns {'dow': [...], 'sp500': [...], 'nasdaq': [...]}.
    Returns empty lists on any failure — never raises.
    """
    import yfinance as yf
    symbols = {'dow': '^DJI', 'sp500': '^GSPC', 'nasdaq': '^IXIC'}
    result  = {'dow': [], 'sp500': [], 'nasdaq': []}
    for key, sym in symbols.items():
        try:
            ticker = yf.Ticker(sym)
            hist   = ticker.history(period='35d')
            closes = hist['Close'].dropna().tolist()
            result[key] = [round(p, 2) for p in closes[-30:]]
        except Exception as e:
            log.warning(f'Index history fetch failed for {sym}: {e}')
    return result
```

**In `dashboard_builder.py`:**
- New parameters are keyword-only (see Task 13 for full signature)
- At top of `build_dashboard()`: `index_history = index_history or {}`
- Write to `docs/assets/data/index_history.json` using atomic write (`os.replace()`) with `encoding='utf-8'`
- Pass in-memory dict to `_write_index_page()` — never re-read the file during the same run

**In `main.py` — first addition only:**
```python
from collectors.market_collector import get_index_history
index_history = get_index_history()
```
Pass `index_history=index_history` to `build_dashboard()`.

---

## TASK 11 — Add stock price history to `financial_parser.py`

Find the function that opens `yf.Ticker(ticker)`. After existing data fetch from the open object, add:

```python
price_history = []
try:
    if ticker_obj is not None:
        hist          = ticker_obj.history(period='35d')
        closes        = hist['Close'].dropna().tolist()
        price_history = [round(p, 2) for p in closes[-30:]]
except Exception as e:
    log.warning(f'Price history fetch failed for {ticker}: {e}')
```

Return `price_history` in the function's return dict under key `'price_history'`.

**In `dashboard_builder.py → _update_rank_board()`:**
```python
raw_ph = c.get('price_history') or stock_entry.get('price_history', [])
entry['price_history'] = _sanitize_price_history(raw_ph)
```
Sanitize at write time. Render functions read `stock.get('price_history') or []` without re-sanitizing — data in `rank.json` is guaranteed clean per the system contract in `_sanitize_price_history()` docstring.

---

## TASK 12 — News backend

**In `collectors/news_collector.py` — extend `SectorSignalAccumulator`:**

In `__init__()` add:
```python
self._sector_articles: dict[str, list] = {}
```

In `process()`, inside the sector loop after the existing event append:
```python
if sector not in self._sector_articles:
    self._sector_articles[sector] = []
existing_titles = [a['title'] for a in self._sector_articles[sector]]
if article.get('title') and article['title'] not in existing_titles:
    pub     = article.get('published')
    pub_str = 'unknown'
    if pub is not None:
        try:
            pub_et  = pub.astimezone(pytz.timezone('America/New_York'))
            pub_str = pub_et.strftime('%Y-%m-%d %H:%M ET')
        except Exception:
            pass
    self._sector_articles[sector].append({
        'title':     article.get('title') or '',
        'body':      (article.get('body') or '')[:300],
        'source':    article.get('source') or 'Unknown',
        'published': pub_str,
        'score':     round(weighted, 2),
    })
```

In `confirmed()`, add to each confirmed sector:
```python
result[sector]['articles'] = self._sector_articles.get(sector, [])
```

**In `dashboard_builder.py` — add `_write_news_json()`:**
```python
def _write_news_json(confirmed_sectors: dict) -> None:
    """
    Writes docs/assets/data/news.json from confirmed sector articles.

    Preserve-on-empty: if confirmed_sectors is empty this run, the file is left
    unchanged so the index page npc widget retains last-run headlines.
    Intentional divergence from _write_news_page() which always reflects current
    run state. This may cause index and news page to temporarily display different
    data states after empty runs. This is by design.
    """
    if not isinstance(confirmed_sectors, dict):
        return
    news_path = os.path.join(DATA_DIR, 'news.json')
    if not confirmed_sectors:
        return
    now_et  = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    payload = {
        'generated': now_et.strftime('%Y-%m-%d %H:%M ET'),
        'sectors':   [],
    }
    sectors_sorted = sorted(
        [(sector, data) for sector, data in confirmed_sectors.items() if data.get('articles')],
        key=lambda x: x[1].get('score', 0) if isinstance(x[1].get('score'), (int, float)) else 0,
        reverse=True,
    )
    for sector, data in sectors_sorted:
        payload['sectors'].append({
            'sector':   sector,
            'score':    data.get('score', 0),
            'articles': data.get('articles', []),
        })
    try:
        tmp_path = news_path + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, news_path)
        log.info(f'News JSON written: {len(payload["sectors"])} sectors')
    except Exception as e:
        log.error(f'News JSON write failed: {e}')
```

**In `main.py` — second and final addition:**
`candidate_sectors` is already returned from `collect_news()` at line 539. Pass:
```python
build_dashboard(..., confirmed_sectors=candidate_sectors)
```

---

## TASK 13 — Wire `build_dashboard()` and verify all connections

Updated signature — new parameters are keyword-only after `*`:

```python
def build_dashboard(
    companies: list,
    slot: str,
    indices: dict,
    breadth: dict,
    regime: dict,
    rotation: dict,
    prompt_text: str = '',
    full_url: str = '',
    is_debug: bool = False,
    *,
    index_history: dict = None,
    confirmed_sectors: dict = None,
) -> None:
```

At top of function body:
```python
index_history     = index_history     or {}
confirmed_sectors = confirmed_sectors or {} if isinstance(confirmed_sectors, dict) else {}
```

Call order inside `build_dashboard()`:
1. `_write_news_json(confirmed_sectors)`
2. `_update_reports_index(...)`
3. `_update_rank_board(companies)`
4. `_write_index_page(indices, breadth, regime, index_history)`
5. `_write_rank_page()`
6. `_update_weekly_archive(...)`
7. `_write_archive_page()`
8. `_write_news_page(confirmed_sectors)`

Verify all call sites of `build_dashboard()` in the repo use keyword arguments. The `*` separator prevents positional misalignment. `scripts/bootstrap_dashboard.py` will not break because new parameters have defaults.

---

## TASK 14 — Final verification checklist

- [ ] `docs/assets/style.css` has full CSS variable set and all shared classes
- [ ] All 5 nav pages link correctly, no 404s
- [ ] Active tab underline correct on each page (Python-set, not JS)
- [ ] Same nav HTML structure in static `guide.html` as in `_nav_html()` output; sync comment present
- [ ] Index pills render with real values, genie expand animates, Chart.js sparklines render
- [ ] `home-below` displacement animation works on index page; null guard `if (!el) return` present
- [ ] `index_history.json` written every run using `os.replace()` atomic write with `encoding='utf-8'`
- [ ] Rank page shows real tickers sorted by confidence, expand rows open, charts render
- [ ] `rank.json` entries include sanitized `price_history` field (NaN-free, via `_sanitize_price_history()`)
- [ ] Price history in `<script type="application/json">` tags per rank row (Pattern A — `_safe_json()`)
- [ ] `expT()` has `if (!el) return` null guard, `try/catch` around `JSON.parse`, and chart init gated behind `data.length >= 2` — expand row always opens regardless of chart data
- [ ] `mkC()` has `typeof Chart === 'undefined'` guard and `window._mreCharts` destroy-before-reinit pattern
- [ ] Chart.js CDN script has `defer` attribute on index and rank pages only
- [ ] Archive week blocks render with working copy buttons
- [ ] Copy AI Prompt: script tags use `_safe_json()` (Pattern A), `try/catch` in JS handler shows "Error" state on parse failure (not raw JSON), `DOMContentLoaded` wrapper, green "Copied ✓" transition, reverts after 1.8s
- [ ] `report_index` IDs come from `enumerate(reports, 1)` loop counter — no other source
- [ ] `run_idx` IDs on archive page come from `enumerate(run_entries, 1)` loop counter combined with `week_key`
- [ ] IDX_DATA injected via `_safe_js_json()` (Pattern B — inline `<script>`)
- [ ] `_safe_json()` used for all Pattern A blocks; `_safe_js_json()` used for all Pattern B assignments; `json.dumps()` never used directly in any `<script>` context on any page
- [ ] `_safe_json()` includes `\u2028` and `\u2029` escape replacements in addition to `</script>` escape
- [ ] Guide page all sections present, correct active nav tab hardcoded, matches `_nav_html('guide')` structure exactly; sync comment present
- [ ] `news.html` renders without 404 (live or placeholder)
- [ ] `_write_news_page()` uses `confirmed_sectors` parameter directly — no file re-read; includes `isinstance` guard at entry
- [ ] `_write_news_json()` preserves file on empty run (no-op); `_write_news_page()` renders placeholder on empty run — intentional divergence documented in both functions with temporal mismatch note
- [ ] `news.json` write uses `os.replace()` atomic pattern with `encoding='utf-8'`
- [ ] Sectors sorted by score descending in both `_write_news_json()` and `_write_news_page()`; sort key has `isinstance` guard for None score
- [ ] `news.json` structure: `{generated, sectors:[{sector, score, articles:[{title,body,source,published,score}]}]}`
- [ ] `intraday_full.html` and `closing_full.html` use new palette and Share Tech Mono
- [ ] Email templates use new inline hex values only, no CSS variables
- [ ] `_esc()` helper defined at module level; used for all data-derived string insertions (strings only, not formatted numbers); applied exactly once per value
- [ ] All article field access uses `.get()` — no bare dict key access on article objects
- [ ] `market_verdict_display` used as primary, `market_verdict` as fallback, everywhere verdicts are rendered
- [ ] `reports` list normalized with `isinstance(reports_data, dict)` check then `isinstance(reports_raw, list)` check before iteration
- [ ] Stock list filtered with `isinstance(s, dict)` before sort, on both index and rank pages
- [ ] Sort keys use `isinstance(x.get('confidence'), (int, float))` guard, returning `-1` for None, on all pages
- [ ] `_sanitize_price_history()` includes `math.isnan()` check; docstring contains system contract — called only at write time in `_update_rank_board()`; render functions do not re-sanitize
- [ ] `_calc_return_from_history()` uses `len(data) <= trading_days` guard
- [ ] `confirmed_sectors` guarded with `isinstance(confirmed_sectors, dict)` at entry of both `_write_news_json()` and `_write_news_page()`
- [ ] `indices` guarded with `indices = indices or {}` at start of index render function
- [ ] `_fmt_pct()`, `_fmt_score()`, `_fmt_price()`, `_fmt_index_val()`, `_calc_return_from_history()`, `_sanitize_price_history()`, `_safe_json()`, `_safe_js_json()`, `_esc()` all defined at module level and used consistently
- [ ] No `print()` calls added
- [ ] No `datetime.now()` without `pytz.utc` added
- [ ] All render functions have try/except with defined fallback HTML
- [ ] All file writes use `encoding='utf-8'`
- [ ] `build_dashboard()` new parameters keyword-only after `*`
- [ ] `bootstrap_dashboard.py` still callable without errors

---

## IF QUOTA RUNS OUT

Stop at the end of the current task. Do not begin a new task you cannot finish cleanly. Write at the bottom of the last file you edited:

```python
# AGENT STOP — completed through Task N
# Last file modified: filename
# Next task: Task N+1 — brief description
# Notes: anything the next agent must know
```

The next agent receives a continuation prompt built from this summary.
