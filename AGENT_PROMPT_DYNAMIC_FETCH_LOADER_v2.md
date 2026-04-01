# AGENT PROMPT v2 — Dynamic Client-Side Fetch + MRE Loader Animation
## File: `reports/dashboard_builder.py`
## Scope: One file only. No other files need to change.

---

## OBJECTIVE

Two goals implemented together in `dashboard_builder.py`:

1. **Loader animation** — Every page shows a pixel-style bar loader on load. On fetch pages it stays until data renders. On baked pages it dismisses on `DOMContentLoaded`.

2. **Dynamic fetch** — `index.html`, `rank.html`, and `archive.html` currently bake their data into HTML at build time. Convert these three pages to fetch their data at runtime via `fetch()` so that cleanup-script deletions are reflected immediately without a rebuild.

---

## CONSTRAINT

All `fetch()` calls must use **relative paths** only (e.g. `assets/data/reports.json`). GitHub Pages serves these files statically — no backend, no API key, no cost.

---

## PART 1 — THREE NEW MODULE-LEVEL CONSTANTS

Add these three constants near the top of `dashboard_builder.py`, directly after the existing `_CHARTJS` line (currently around line 26). They must be module-level, not inside any function.

```python
_LOADER_CSS = (
    '<style>'
    '#mre-loader{'
        'position:fixed;inset:0;z-index:9999;'
        'background:#0a0a12;'
        'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px;'
        'transition:opacity 0.4s ease;'
    '}'
    '#mre-loader.done{opacity:0;pointer-events:none;}'
    '.mre-bar-shell{'
        'position:relative;width:280px;height:40px;'
        'border:2px solid #c850c0;border-radius:6px;padding:5px;'
        'box-shadow:0 0 8px #c850c080,0 0 20px #c850c040,inset 0 0 6px #c850c020;'
        'overflow:hidden;'
    '}'
    '.mre-bar-shell::after{'
        'content:\'\';position:absolute;inset:0;'
        'background:repeating-linear-gradient('
            '90deg,'
            'transparent,'
            'transparent calc(100% / 10 - 3px),'
            '#0a0a12 calc(100% / 10 - 3px),'
            '#0a0a12 calc(100% / 10)'
        ');'
        'pointer-events:none;z-index:2;'
    '}'
    '.mre-bar-fill{'
        'height:100%;width:0%;border-radius:2px;'
        'background:linear-gradient(90deg,#5c6fff,#9b59ff,#c850c0);'
        'box-shadow:0 0 12px #9b59ff80;'
        'position:relative;z-index:1;'
        'transition:width 0.05s linear;'
    '}'
    '#mre-loader-text{'
        'font-family:\'Orbitron\',sans-serif;font-size:13px;'
        'letter-spacing:0.25em;color:#9b59ff;'
        'text-shadow:0 0 10px #9b59ff80;'
        'min-width:130px;text-align:center;'
    '}'
    '</style>'
)

_LOADER_HTML = (
    '<div id="mre-loader">'
    '<div class="mre-bar-shell"><div class="mre-bar-fill" id="mre-bar-fill"></div></div>'
    '<div id="mre-loader-text">LOADING</div>'
    '</div>'
)

# NOTE: This is a plain string, NOT an f-string. No Python variables are
# interpolated here. Do not convert it to an f-string — JS braces must not
# be doubled.
_LOADER_JS = (
    '<script>'
    '(function(){'
    'var _li=0,_ls=["LOADING","LOADING.","LOADING..","LOADING..."];'
    'var _lt=document.getElementById("mre-loader-text");'
    'var _lp=setInterval(function(){_li=(_li+1)%4;if(_lt)_lt.textContent=_ls[_li];},420);'
    'var _bf=document.getElementById("mre-bar-fill");'
    'var _bt=null;'
    'function _bStep(ts){'
    'if(!_bt)_bt=ts;'
    'var prog=Math.min((ts-_bt)/1800,1);'
    'var ease=1-Math.pow(1-prog,3);'
    'if(_bf)_bf.style.width=(ease*100)+"%";'
    'if(prog<1)requestAnimationFrame(_bStep);'
    '}'
    'requestAnimationFrame(_bStep);'
    'window.dismissLoader=function(){'
    'clearInterval(_lp);'
    'if(_bf)_bf.style.width="100%";'
    'setTimeout(function(){'
    'var el=document.getElementById("mre-loader");'
    'if(el){el.classList.add("done");setTimeout(function(){if(el.parentNode)el.parentNode.removeChild(el);},450);}'
    '},120);'
    '};'
    '})();'
    '</script>'
)
```

---

## PART 2 — INJECT LOADER INTO EVERY PAGE RENDER FUNCTION

There are five render functions plus `_err_page` that each contain a `return (...)` block building an HTML string. Apply the **same three-step injection** to all six:

**Step A** — Inside `<head>`: add `f'{_LOADER_CSS}'` on the line immediately after `'<link rel="stylesheet" href="assets/style.css">'`. If the page has an additional inline `<style>` block after the stylesheet link (e.g. `page_css` in index, or the `.exp-chart canvas` style in rank), place `_LOADER_CSS` before those extra styles.

**Step B** — Inside `<body>`: add `f'{_LOADER_HTML}'` and `f'{_LOADER_JS}'` as the **first two items** after `'</head><body>'`, before `'<div class="scanlines"></div>'`.

**Step C** — Dismiss call: varies by page type — see sections below.

### Exact injection diff for each function

#### `_err_page` (line ~548)

Before:
```python
'<!DOCTYPE html><html lang="en"><head>'
'<meta charset="UTF-8">'
f'{_FONTS_LINK}'
'<link rel="stylesheet" href="assets/style.css">'
'</head><body>'
'<div class="scanlines"></div>'
...
'<footer><span>MRE</span> &middot; Not investment advice</footer>'
'</body></html>'
```

After:
```python
'<!DOCTYPE html><html lang="en"><head>'
'<meta charset="UTF-8">'
f'{_FONTS_LINK}'
'<link rel="stylesheet" href="assets/style.css">'
f'{_LOADER_CSS}'
'</head><body>'
f'{_LOADER_HTML}'
f'{_LOADER_JS}'
'<div class="scanlines"></div>'
...
'<footer><span>MRE</span> &middot; Not investment advice</footer>'
'<script>document.addEventListener("DOMContentLoaded",function(){if(window.dismissLoader)window.dismissLoader();});</script>'
'</body></html>'
```

---

#### `_render_news_html` (line ~1344)

Before:
```python
'<link rel="stylesheet" href="assets/style.css">'
'</head><body>'
'<div class="scanlines"></div>'
...
'</body></html>'
```

After:
```python
'<link rel="stylesheet" href="assets/style.css">'
f'{_LOADER_CSS}'
'</head><body>'
f'{_LOADER_HTML}'
f'{_LOADER_JS}'
'<div class="scanlines"></div>'
...
'<footer>...</footer>'
'<script>document.addEventListener("DOMContentLoaded",function(){if(window.dismissLoader)window.dismissLoader();});</script>'
'</body></html>'
```

Note: `_render_news_html` currently has no `<script>` block in its return string. Add the dismiss script as a new `<script>` tag just before `</body></html>`.

---

#### `_render_index_html` (line ~1051)

Before:
```python
'<link rel="stylesheet" href="assets/style.css">'
f'{page_css}'
'</head><body>'
'<div class="scanlines"></div>'
```

After:
```python
'<link rel="stylesheet" href="assets/style.css">'
f'{_LOADER_CSS}'
f'{page_css}'
'</head><body>'
f'{_LOADER_HTML}'
f'{_LOADER_JS}'
'<div class="scanlines"></div>'
```

Dismiss: called inside the `reports.json` fetch — see Part 3.

---

#### `_render_rank_html` (line ~1170)

Before:
```python
'<link rel="stylesheet" href="assets/style.css">'
'<style>.exp-chart canvas{width:100%!important;height:100%!important;}</style>'
'</head><body>'
'<div class="scanlines"></div>'
```

After:
```python
'<link rel="stylesheet" href="assets/style.css">'
f'{_LOADER_CSS}'
'<style>.exp-chart canvas{width:100%!important;height:100%!important;}</style>'
'</head><body>'
f'{_LOADER_HTML}'
f'{_LOADER_JS}'
'<div class="scanlines"></div>'
```

Dismiss: called inside the `rank.json` fetch — see Part 3.

---

#### `_render_archive_html` (line ~1272)

Before:
```python
'<link rel="stylesheet" href="assets/style.css">'
'</head><body>'
'<div class="scanlines"></div>'
```

After:
```python
'<link rel="stylesheet" href="assets/style.css">'
f'{_LOADER_CSS}'
'</head><body>'
f'{_LOADER_HTML}'
f'{_LOADER_JS}'
'<div class="scanlines"></div>'
```

Dismiss: called inside the `weekly_archive.json` fetch — see Part 3.

---

## PART 3 — DYNAMIC FETCH FOR THREE PAGES

### Architecture rule

The Python render functions **keep generating the full HTML shell** (nav, titles, baked sections, footer, all existing JS constants). They **stop generating** the data-dependent sections listed below and replace them with empty mount `<div>`s. A `<script>` block appended before `</body></html>` does the `fetch()` and renders into those mount divs.

**Important:** All fetch JS in this part must be stored as **plain Python strings** (not f-strings) since no Python variables are interpolated into them. This avoids having to escape every JS brace as `{{` / `}}`.

---

### PAGE 1: `index.html` — changes to `_render_index_html`

#### Python changes

1. **Remove** the entire `top_stocks` / `rp_rows` / `rank_preview` generation block (the loop over `top_stocks` that builds `rp_rows` and the `rank_preview` wrapper).

2. **Remove** the entire `cards_html` generation block (the loop over `reports` that builds `script_block`, `copy_btn`, `cards_html`).

3. In the return string, replace:
   ```python
   f'{rank_preview}'
   ```
   with:
   ```python
   '<div id="rank-preview-mount"></div>'
   ```

4. In the return string, replace:
   ```python
   f'{cards_html}'
   ```
   with:
   ```python
   '<div id="report-cards-mount"></div>'
   ```

5. Keep all other variables: `strip`, `npc_html`, `page_css`, `pills`, `idx_script`, `pg_sub`, `js_block`. These are all baked and unchanged.

6. Add a new variable `_INDEX_FETCH_JS` (plain string, defined inside the function before the return, or as a module-level constant — agent's choice) containing the JS below.

7. Append to `js_block` (after `f'<script>{_COPY_PROMPT_JS}</script>'`):
   ```python
   f'<script>{_INDEX_FETCH_JS}</script>'
   ```
   Wait — `_INDEX_FETCH_JS` is a plain string not an f-string, so use concatenation: `'<script>' + _INDEX_FETCH_JS + '</script>'` and append it to the return string just before `'</body></html>'`, after `f'{js_block}'`.

#### `_INDEX_FETCH_JS` content (plain string, no f-string)

```javascript
// ── Rank preview fetch ───────────────────────────────────────────────────
fetch('assets/data/rank.json')
  .then(function(r){ return r.ok ? r.json() : Promise.reject(r.status); })
  .then(function(rankData) {
    var stocks = rankData.stocks || {};
    var arr = Array.isArray(stocks) ? stocks : Object.values(stocks);
    arr = arr.filter(function(s){ return s && typeof s === 'object'; });
    arr.sort(function(a,b){
      var ca = typeof a.confidence === 'number' ? a.confidence : -1;
      var cb = typeof b.confidence === 'number' ? b.confidence : -1;
      return cb - ca;
    });
    var top5 = arr.slice(0, 5);
    var rows = '';
    top5.forEach(function(s, idx) {
      var i    = idx + 1;
      var conf = typeof s.confidence === 'number' ? s.confidence : null;
      var cCls = conf === null ? 'nt' : conf >= 70 ? 'up' : conf >= 50 ? 'nt' : 'dn';
      var eqV  = s.eq_verdict_display  || '';
      var eqCls  = eqV  === 'STRONG'  ? 'up' : eqV  === 'WEAK'    ? 'dn' : 'nt';
      var rotS = s.rotation_signal_display || '';
      var rotCls = rotS === 'LEADING' ? 'up' : rotS === 'LAGGING' ? 'dn' : 'nt';
      var verdict  = s.market_verdict_display || s.market_verdict || '\u2014';
      var confStr  = conf !== null ? Math.round(conf) : '\u2014';
      var riskStr  = typeof s.risk_score === 'number' ? Math.round(s.risk_score) : '\u2014';
      var ret1m = typeof s.return_1m === 'number' ? (s.return_1m >= 0 ? '\u25b2' : '\u25bc') + ' ' + Math.abs(s.return_1m).toFixed(1) + '%' : '\u2014';
      var ret3m = typeof s.return_3m === 'number' ? (s.return_3m >= 0 ? '\u25b2' : '\u25bc') + ' ' + Math.abs(s.return_3m).toFixed(1) + '%' : '\u2014';
      var ret6m = typeof s.return_6m === 'number' ? (s.return_6m >= 0 ? '\u25b2' : '\u25bc') + ' ' + Math.abs(s.return_6m).toFixed(1) + '%' : '\u2014';
      var sector = (s.sector || '').replace(/_/g,' ').replace(/\b\w/g, function(c){ return c.toUpperCase(); });
      rows += '<div class="rp-row" onclick="rpT(\'rp' + i + '\')">'
            + '<div class="rp-n">#' + i + '</div>'
            + '<div class="rp-tick">' + (s.ticker || '\u2014') + '</div>'
            + '<div class="rp-sect">' + sector + '</div>'
            + '<div class="rp-conf ' + cCls + '">' + confStr + '</div>'
            + '<div style="font-size:11px;color:var(--mist);">' + riskStr + '</div>'
            + '<div><span class="ntag ' + eqCls + '">' + (eqV || '\u2014') + '</span></div>'
            + '<div><span class="ntag ' + rotCls + '">' + (rotS || '\u2014') + '</span></div>'
            + '</div>'
            + '<div class="rp-exp" id="rp' + i + '"><div class="rp-exp-inner">'
            + '<div class="pex-item"><div class="pex-k">1M Return</div><div class="pex-v">' + ret1m + '</div></div>'
            + '<div class="pex-item"><div class="pex-k">3M Return</div><div class="pex-v">' + ret3m + '</div></div>'
            + '<div class="pex-item"><div class="pex-k">6M Return</div><div class="pex-v">' + ret6m + '</div></div>'
            + '<div class="pex-item"><div class="pex-k">Verdict</div><div class="pex-v ' + cCls + '">' + verdict + '</div></div>'
            + '</div></div>';
    });
    if (!rows) rows = '<div style="padding:14px 18px;color:var(--mist);font-size:11px;">No candidates this week.</div>';
    document.getElementById('rank-preview-mount').innerHTML =
        '<div class="rank-preview">'
      + '<div class="rank-preview-head">'
      + '<span class="rank-preview-title">Top 5 Candidates \u00b7 Week Rank</span>'
      + '<a href="rank.html" class="rp-link">Full \u2192</a>'
      + '</div>'
      + '<div class="rp-cols">'
      + '<span class="rp-col-h">#</span><span class="rp-col-h">Ticker</span>'
      + '<span class="rp-col-h">Sector</span><span class="rp-col-h">Conf</span>'
      + '<span class="rp-col-h">Risk</span><span class="rp-col-h">EQ</span>'
      + '<span class="rp-col-h">Rotation</span>'
      + '</div>'
      + rows
      + '</div>';
  })
  .catch(function() {
    document.getElementById('rank-preview-mount').innerHTML =
      '<div style="color:var(--dn);font-family:var(--ff-mono);font-size:11px;padding:14px;">Error loading rank data.</div>';
  });

// ── Report cards fetch ───────────────────────────────────────────────────
// NOTE: dismissLoader() is called here (reports fetch), not in rank fetch,
// because this is the last fetch to resolve. Both .then and .catch call it.
fetch('assets/data/reports.json')
  .then(function(r){ return r.ok ? r.json() : Promise.reject(r.status); })
  .then(function(data) {
    var reports = Array.isArray(data.reports) ? data.reports.slice(0, 14) : [];
    var html = '';
    reports.forEach(function(r, idx) {
      var vc = r.verdicts || {};
      var rnC, wC, sC;
      if (Array.isArray(vc)) {
        rnC = vc.filter(function(v){ return v === 'RESEARCH NOW'; }).length;
        wC  = vc.filter(function(v){ return v === 'WATCH'; }).length;
        sC  = vc.filter(function(v){ return v === 'SKIP'; }).length;
      } else {
        rnC = (typeof vc['RESEARCH NOW'] === 'number') ? vc['RESEARCH NOW'] : 0;
        wC  = (typeof vc['WATCH']        === 'number') ? vc['WATCH']        : 0;
        sC  = (typeof vc['SKIP']         === 'number') ? vc['SKIP']         : 0;
      }
      var tickers  = Array.isArray(r.tickers) ? r.tickers.join(', ') : '\u2014';
      var topScore = typeof r.top_score === 'number' ? Math.round(r.top_score) : '\u2014';
      var b        = r.breadth || '';
      var bCls     = b === 'BULLISH' ? 'up' : b === 'BEARISH' ? 'dn' : 'nt';
      var bTitle   = b.charAt(0).toUpperCase() + b.slice(1).toLowerCase();
      var count    = r.count || 0;
      var regime   = (r.regime || '').replace(/\b\w/g, function(c){ return c.toUpperCase(); });
      var uid      = 'prompt_' + (idx + 1);
      var promptText  = r.prompt || '';
      var scriptBlock = '';
      var copyBtn     = '';
      if (promptText) {
        var safePrompt = JSON.stringify(promptText).replace(/<\/script>/gi, '<\\/script>');
        scriptBlock = '<script type="application/json" id="' + uid + '">' + safePrompt + '<\/script>';
        copyBtn = '<button class="btn mg copy-prompt-btn" data-ref="' + uid + '">\u29c9 Copy AI Prompt</button>';
      }
      var reportUrl = r.report_url || '';
      var fullBtn = reportUrl
        ? '<a href="' + reportUrl + '" class="btn" target="_blank" onclick="event.stopPropagation()">\u2197 Full Report</a>'
        : '';
      html += scriptBlock
           + '<div class="rcard" onclick="rcT(this)">'
           + '<div class="rcard-head"><div>'
           + '<div class="rcard-date">' + (r.date || '') + ' \u00b7 ' + (r.slot || '') + ' \u00b7 ' + count + ' stock' + (count !== 1 ? 's' : '') + '</div>'
           + '<div class="rcard-slot" style="font-size:11px;color:var(--mist);">' + (r.time || '') + ' ET \u00b7 ' + regime + '</div>'
           + '</div>'
           + '<span class="rcard-badge ' + bCls + '">' + bTitle + '</span>'
           + '</div>'
           + '<div class="rcard-body"><div class="rcard-inner">'
           + '<div class="rcard-cols">'
           + '<div><div class="rcc-k">Sys 1 \u00b7 Tickers</div><div class="rcc-v">' + tickers
           + '<br><span style="font-size:11px;color:var(--mist)">Top conf: ' + topScore + '/100</span></div></div>'
           + '<div><div class="rcc-k">Verdicts</div><div class="rcc-v">'
           + '<span style="color:var(--up)">RN:' + rnC + '</span> '
           + '<span style="color:var(--nt)">W:' + wC + '</span> '
           + '<span style="color:var(--dn)">S:' + sC + '</span></div></div>'
           + '<div><div class="rcc-k">Breadth</div><div class="rcc-v" style="color:var(--' + bCls + ')">' + bTitle + '</div></div>'
           + '</div>'
           + '<div class="rcard-btns">' + fullBtn + copyBtn + '</div>'
           + '</div></div></div>';
    });
    if (!html) html = '<div style="color:var(--mist);font-family:var(--ff-mono);font-size:11px;">No reports yet.</div>';
    document.getElementById('report-cards-mount').innerHTML = html;
    // ── Dismiss loader after final data is in the DOM ──
    if (window.dismissLoader) window.dismissLoader();
  })
  .catch(function() {
    document.getElementById('report-cards-mount').innerHTML =
      '<div style="color:var(--dn);font-family:var(--ff-mono);font-size:11px;padding:14px;">Error loading reports. Try refreshing.</div>';
    if (window.dismissLoader) window.dismissLoader();
  });
```

---

### PAGE 2: `rank.html` — changes to `_render_rank_html`

#### Python changes

1. **Remove** the entire `rows_html` / `ph_scripts` / `exp_row` generation loop.

2. In the return string, replace:
   ```python
   f'{rows_html}'
   ```
   with:
   ```python
   '<div id="rank-board-mount"></div>'
   ```

3. Remove `f'{ph_scripts}'` from the return string entirely.

4. The `week_display` variable is still used in `pg-sub` — keep it.

5. Add a plain string `_RANK_FETCH_JS` (defined before the return or at module level) and append `'<script>' + _RANK_FETCH_JS + '</script>'` to the return string just before `'</body></html>'`, after the existing `f'<script>{_DAYS_JS}{_EXP_T_JS}{_RAF_COLLAPSE_JS}{_COPY_PROMPT_JS}</script>'`.

#### `_RANK_FETCH_JS` content (plain string, no f-string)

```javascript
fetch('assets/data/rank.json')
  .then(function(r){ return r.ok ? r.json() : Promise.reject(r.status); })
  .then(function(rankData) {
    var stocks = rankData.stocks || {};
    var arr = Array.isArray(stocks) ? stocks : Object.values(stocks);
    arr = arr.filter(function(s){ return s && typeof s === 'object'; });
    arr.sort(function(a,b){
      var ca = typeof a.confidence === 'number' ? a.confidence : -1;
      var cb = typeof b.confidence === 'number' ? b.confidence : -1;
      return cb - ca;
    });
    var html    = '';
    var scripts = '';
    arr.forEach(function(stock, idx) {
      var i    = idx + 1;
      var conf = typeof stock.confidence === 'number' ? stock.confidence : null;
      var risk = typeof stock.risk_score  === 'number' ? stock.risk_score  : null;
      var cCls   = conf === null ? 'nt' : conf >= 70 ? 'up' : conf >= 50 ? 'nt' : 'dn';
      var eqV    = stock.eq_verdict_display  || '';
      var eqCls  = eqV  === 'STRONG'  ? 'up' : eqV  === 'WEAK'    ? 'dn' : 'nt';
      var rotS   = stock.rotation_signal_display || '';
      var rotCls = rotS === 'LEADING' ? 'up' : rotS === 'LAGGING' ? 'dn' : 'nt';
      var verdict  = stock.market_verdict_display || stock.market_verdict || '\u2014';
      var confStr  = conf !== null ? Math.round(conf) : '\u2014';
      var riskStr  = risk !== null ? Math.round(risk)  : '\u2014';
      var price    = typeof stock.price === 'number' ? '$' + stock.price.toFixed(2) : '\u2014';
      var alignVal = stock.alignment || '';
      var aCls     = alignVal === 'ALIGNED' ? 'up' : alignVal === 'MIXED' ? 'nt' : 'dn';
      var sector   = (stock.sector || '').replace(/_/g,' ').replace(/\b\w/g, function(c){ return c.toUpperCase(); });
      var ret1m = typeof stock.return_1m === 'number' ? (stock.return_1m >= 0 ? '\u25b2' : '\u25bc') + ' ' + Math.abs(stock.return_1m).toFixed(1) + '%' : '\u2014';
      var ret3m = typeof stock.return_3m === 'number' ? (stock.return_3m >= 0 ? '\u25b2' : '\u25bc') + ' ' + Math.abs(stock.return_3m).toFixed(1) + '%' : '\u2014';
      var ret6m = typeof stock.return_6m === 'number' ? (stock.return_6m >= 0 ? '\u25b2' : '\u25bc') + ' ' + Math.abs(stock.return_6m).toFixed(1) + '%' : '\u2014';
      var phUid  = 'ph-' + i;
      var rawPh  = Array.isArray(stock.price_history) ? stock.price_history : [];
      var phList = rawPh.filter(function(v){ return typeof v === 'number' && isFinite(v); });
      var hasCh  = phList.length > 1;
      var chartEl = hasCh
        ? '<canvas id="ec' + i + '" height="92"></canvas>'
        : '<div style="color:var(--mist);font-size:11px;padding:8px 0;">Price history unavailable</div>';
      scripts += '<script type="application/json" id="' + phUid + '">'
              + JSON.stringify(phList).replace(/<\/script>/gi,'<\\/script>')
              + '<\/script>';
      html += '<div class="rank-row" data-ref="' + phUid + '" data-eid="e' + i + '" data-cid="ec' + i + '" onclick="expT(this)">'
           + '<div class="td-n">#' + i + '</div>'
           + '<div class="td-t">' + (stock.ticker || '\u2014') + '</div>'
           + '<div class="td-s">' + sector + '</div>'
           + '<div class="td-p">' + price + '</div>'
           + '<div class="td-c ' + cCls + '">' + confStr + '</div>'
           + '<div class="td-r">' + riskStr + '</div>'
           + '<div><span class="ntag ' + eqCls + '" style="font-size:8px">' + (eqV || '\u2014') + '</span></div>'
           + '<div><span class="ntag ' + rotCls + '" style="font-size:8px">' + (rotS || '\u2014') + '</span></div>'
           + '</div>'
           + '<div class="exp-row" id="e' + i + '"><div class="exp-inner">'
           + '<div class="exp-stats">'
           + '<div class="est"><div class="est-k">1M</div><div class="est-v">' + ret1m + '</div></div>'
           + '<div class="est"><div class="est-k">3M</div><div class="est-v">' + ret3m + '</div></div>'
           + '<div class="est"><div class="est-k">6M</div><div class="est-v">' + ret6m + '</div></div>'
           + '<div class="est"><div class="est-k">Verdict</div><div class="est-v ' + cCls + '">' + verdict + '</div></div>'
           + '<div class="est"><div class="est-k">Align</div><div class="est-v ' + aCls + '">' + (alignVal || '\u2014') + '</div></div>'
           + '</div>'
           + '<div class="exp-chart">' + chartEl + '</div>'
           + '</div></div>';
    });
    if (!html) html = '<div style="color:var(--mist);font-family:var(--ff-mono);padding:28px;">No candidates this week.</div>';
    // Inject script blocks first (before HTML) so they exist when onclick handlers fire
    document.getElementById('rank-board-mount').innerHTML = scripts + html;
    if (window.dismissLoader) window.dismissLoader();
  })
  .catch(function() {
    document.getElementById('rank-board-mount').innerHTML =
      '<div style="color:var(--dn);font-family:var(--ff-mono);font-size:11px;padding:28px;">Error loading rank data. Try refreshing.</div>';
    if (window.dismissLoader) window.dismissLoader();
  });
```

---

### PAGE 3: `archive.html` — changes to `_render_archive_html`

#### Python changes

1. **Remove** the entire `blocks_html` generation loop (the outer `for wk in week_keys` loop and all inner `cards_html` construction).

2. In the return string, replace:
   ```python
   f'{blocks_html}'
   ```
   with:
   ```python
   '<div id="archive-mount"></div>'
   ```

3. Add plain string `_ARCHIVE_FETCH_JS` and append `'<script>' + _ARCHIVE_FETCH_JS + '</script>'` to the return string just before `'</body></html>'`, after the existing `f'<script>{_RCT_JS}{_COPY_PROMPT_JS}</script>'`.

#### `_ARCHIVE_FETCH_JS` content (plain string, no f-string)

```javascript
fetch('assets/data/weekly_archive.json')
  .then(function(r){ return r.ok ? r.json() : Promise.reject(r.status); })
  .then(function(archiveData) {
    var weeksRaw = archiveData.weeks || {};
    if (typeof weeksRaw !== 'object' || Array.isArray(weeksRaw)) weeksRaw = {};
    var weekKeys = Object.keys(weeksRaw).sort().reverse();
    var html = '';
    weekKeys.forEach(function(wk) {
      var weekInfo = weeksRaw[wk];
      var runs     = (weekInfo && Array.isArray(weekInfo.runs)) ? weekInfo.runs : [];
      var label    = wk.replace('W', ' \u2014 Week ');
      var cardsHtml = '';
      runs.forEach(function(run, runIdx) {
        var slot      = run.slot      || '';
        var ts        = run.timestamp || '';
        var breadth   = run.breadth   || '';
        var regime    = run.regime    || '';
        var count     = run.count     || 0;
        var runType   = run.run_type  || '';
        var bCls      = breadth === 'BULLISH' ? 'up' : breadth === 'BEARISH' ? 'dn' : 'nt';
        var bTitle    = breadth.charAt(0).toUpperCase() + breadth.slice(1).toLowerCase();
        var regTitle  = regime.charAt(0).toUpperCase()  + regime.slice(1).toLowerCase();
        var cands     = Array.isArray(run.candidates) ? run.candidates : [];
        var tickers   = cands.slice(0,5).map(function(c){ return c.ticker||''; }).filter(Boolean).join(', ') || '\u2014';
        var topConf   = cands.length
          ? Math.max.apply(null, cands.map(function(c){ return typeof c.confidence === 'number' ? c.confidence : 0; }))
          : 0;
        var topConfStr = topConf > 0 ? Math.round(topConf) : '\u2014';
        var vc  = run.verdict_counts || {};
        var rnC = typeof vc['RESEARCH NOW'] === 'number' ? vc['RESEARCH NOW'] : 0;
        var wC  = typeof vc['WATCH']        === 'number' ? vc['WATCH']        : 0;
        var sC  = typeof vc['SKIP']         === 'number' ? vc['SKIP']         : 0;
        var promptText  = run.prompt || '';
        var scriptBlock = '';
        var copyBtn     = '';
        if (promptText) {
          var uid = 'arc_' + wk + '_' + runIdx;
          scriptBlock = '<script type="application/json" id="' + uid + '">'
                      + JSON.stringify(promptText).replace(/<\/script>/gi,'<\\/script>')
                      + '<\/script>';
          copyBtn = '<button class="btn mg copy-prompt-btn" data-ref="' + uid + '">\u29c9 Copy AI Prompt</button>';
        }
        var reportUrl = run.report_url || '';
        var fullBtn = reportUrl
          ? '<a href="' + reportUrl + '" class="btn" target="_blank" onclick="event.stopPropagation()">\u2197 Full Report</a>'
          : '';
        var rtypeBadge = runType === 'MANUAL'
          ? '<span style="font-size:8px;color:var(--sun);margin-left:8px">MANUAL</span>'
          : '';
        cardsHtml += scriptBlock
          + '<div class="rcard" onclick="rcT(this)">'
          + '<div class="rcard-head"><div>'
          + '<div class="rcard-date">' + ts + ' \u00b7 ' + slot + ' \u00b7 ' + count + ' stock' + (count !== 1 ? 's' : '') + rtypeBadge + '</div>'
          + '<div class="rcard-slot">' + regTitle + '</div>'
          + '</div><span class="rcard-badge ' + bCls + '">' + bTitle + '</span></div>'
          + '<div class="rcard-body"><div class="rcard-inner">'
          + '<div class="rcard-cols">'
          + '<div><div class="rcc-k">Sys 1</div><div class="rcc-v">' + tickers
          + '<br><span style="color:var(--mist);font-size:10px">Top conf: ' + topConfStr + '/100</span></div></div>'
          + '<div><div class="rcc-k">Verdicts</div><div class="rcc-v">'
          + '<span style="color:var(--up)">RN:' + rnC + '</span> '
          + '<span style="color:var(--nt)">W:' + wC  + '</span> '
          + '<span style="color:var(--dn)">S:'  + sC  + '</span>'
          + '</div></div>'
          + '<div><div class="rcc-k">Breadth</div><div class="rcc-v" style="color:var(--' + bCls + ')">' + bTitle + '</div></div>'
          + '</div>'
          + '<div class="rcard-btns">' + fullBtn + copyBtn + '</div>'
          + '</div></div></div>';
      });
      html += '<div class="week-block">'
            + '<div class="week-head">' + label + ' <span class="week-count">' + runs.length + ' report' + (runs.length !== 1 ? 's' : '') + '</span></div>'
            + cardsHtml
            + '</div>';
    });
    if (!html) html = '<div style="color:var(--mist);font-family:var(--ff-mono);font-size:11px;padding:28px;">No archive data yet.</div>';
    document.getElementById('archive-mount').innerHTML = html;
    if (window.dismissLoader) window.dismissLoader();
  })
  .catch(function() {
    document.getElementById('archive-mount').innerHTML =
      '<div style="color:var(--dn);font-family:var(--ff-mono);font-size:11px;padding:28px;">Error loading archive. Try refreshing.</div>';
    if (window.dismissLoader) window.dismissLoader();
  });
```

---

## PART 4 — PYTHON CLEANUP CHECKLIST

After all changes, verify these conditions before finishing:

- [ ] `_LOADER_CSS`, `_LOADER_HTML`, `_LOADER_JS` defined at module level after `_CHARTJS` line
- [ ] All six return blocks (`_render_index_html`, `_render_rank_html`, `_render_archive_html`, `_render_news_html`, `_err_page`) inject `_LOADER_CSS` into `<head>` immediately after the stylesheet `<link>` and inject `_LOADER_HTML` + `_LOADER_JS` as the first two items after `</head><body>`
- [ ] `_render_index_html` no longer contains any loop over `top_stocks` or `reports` for HTML generation
- [ ] `_render_rank_html` no longer contains the `rows_html` / `ph_scripts` loop
- [ ] `_render_archive_html` no longer contains the `blocks_html` loop
- [ ] `_render_index_html` return string has `<div id="rank-preview-mount"></div>` and `<div id="report-cards-mount"></div>` in the correct positions (where `{rank_preview}` and `{cards_html}` were)
- [ ] `_render_rank_html` return string has `<div id="rank-board-mount"></div>` where `{rows_html}` was, and `{ph_scripts}` is gone
- [ ] `_render_archive_html` return string has `<div id="archive-mount"></div>` where `{blocks_html}` was
- [ ] `dismissLoader()` called in both `.then` and `.catch` of: `reports.json` fetch (index), `rank.json` fetch (rank), `weekly_archive.json` fetch (archive)
- [ ] `dismissLoader()` called on `DOMContentLoaded` for news and error pages (via inline `<script>` just before `</body></html>`)
- [ ] `_COPY_PROMPT_JS` remains in all page JS blocks — the copy button handler reads from DOM by ID and works with dynamically injected script blocks
- [ ] `_RCT_JS` remains in index and archive page JS — rcards use `onclick="rcT(this)"` attributes so they work on dynamically injected DOM nodes without re-binding
- [ ] `_EXP_T_JS` (`expT`) remains in rank page JS — same reason
- [ ] No Python f-string brace escaping issues: `_INDEX_FETCH_JS`, `_RANK_FETCH_JS`, `_ARCHIVE_FETCH_JS`, and `_LOADER_JS` are all plain strings with no Python variable interpolation
- [ ] `_sanitize_price_history` Python function is NOT called in `_render_rank_html` anymore — price history sanitization is now done in JS (`rawPh.filter(function(v){ return typeof v === 'number' && isFinite(v); })`)
- [ ] No changes to `_update_reports_index`, `_update_rank_board`, `_update_weekly_archive`, `build_dashboard`, or `main.py`

---

## PART 5 — CRITICAL NOTES

**1. Plain strings vs f-strings for JS blocks**
`_LOADER_JS`, `_INDEX_FETCH_JS`, `_RANK_FETCH_JS`, `_ARCHIVE_FETCH_JS` must all be plain Python strings — not f-strings. None of them interpolate Python variables. Storing them as plain strings means JS braces `{` and `}` do not need to be escaped as `{{` / `}}`. If the agent accidentally wraps any of these in `f'...'`, every JS brace will cause a `KeyError` at runtime or a Python syntax error.

**2. Script execution order is safe**
`_LOADER_JS` is placed immediately after `<body>` — before the `<div class="scanlines">` — so `window.dismissLoader` is defined before any other script runs. The fetch JS blocks are placed just before `</body></html>`, after all other JS. This means:
- Loader starts instantly on body parse ✓
- `document.getElementById('...-mount')` is called inside `.then()` callbacks which fire after the full DOM is parsed ✓
- No `DOMContentLoaded` wrapper is needed around fetch calls since they are non-blocking and resolve after DOM is ready ✓

**3. `_COPY_PROMPT_JS` works with dynamically injected prompt script blocks**
The handler reads `document.getElementById(uid)` at click time, not at page load. Since the `<script type="application/json">` blocks are injected into the mount div's innerHTML before `dismissLoader()` is called, they will be in the DOM by the time any user can click a button.

**4. `rcT` and `expT` use inline `onclick` attributes**
Both functions are called via `onclick="rcT(this)"` and `onclick="expT(this)"` attributes on dynamically generated HTML strings. This means no `addEventListener` re-binding is needed after mount — the attributes fire correctly on dynamically inserted nodes.

**5. Idempotency**
`dashboard_builder.py` regenerates each HTML file completely from scratch on every run. There is no risk of duplicate loader blocks accumulating across builds — each build writes a fresh file.

**6. Local testing**
`fetch()` requires HTTP, not `file://`. Test locally with `python -m http.server 8000` from the `docs/` directory, then open `http://localhost:8000/index.html`.
