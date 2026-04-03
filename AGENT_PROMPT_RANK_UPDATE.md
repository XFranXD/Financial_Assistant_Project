# MRE AGENT PROMPT — RANK CARD REDESIGN v5
**Target files: `reports/dashboard_builder.py`, `docs/assets/style.css`**

---

## OBJECTIVE

Replace the existing grid table layout in the rank board with a ranked card stack design.
Apply the new pill-based color system to both the main rank page and the home page rank
preview section. Preserve all existing animations, expand/collapse behavior, Chart.js
sparklines, and countUp animation.

---

## CONTEXT — READ BEFORE TOUCHING ANYTHING

`dashboard_builder.py` contains module-level Python string constants that hold JavaScript.
These are NOT f-strings. The constants are:
- `_RANK_FETCH_JS` — builds the main rank board (rank.html)
- `_INDEX_FETCH_JS` — builds the home page rank preview (index.html)

Inside these JS string constants, `{}` are literal JavaScript — never Python interpolation.
Do not convert them to f-strings. Do not add Python backslash escapes inside `{}` expressions.

The outer HTML page structure uses Python f-strings. Keep them as-is.

Do not rename or transform any JSON field names. Only read and display them as they already exist.

Do not modify sorting, filtering, or loop order — only change HTML structure output.

Do not modify any Python functions unrelated to rank rendering. Only edit the JS string
constants `_RANK_FETCH_JS` and `_INDEX_FETCH_JS`, and the CSS file.

`--rim` and `--apple` are existing CSS variables — safe to use.

Do not modify `data-ref` or how `phUid` is assigned — the expand logic in `expT` depends
on `btn.dataset.ref` mapping to a script block ID.

Do not modify `data-cid` or canvas `id="ec..."` identifiers — Chart.js `mkC()` depends on
exact ID alignment.

Existing constants and helpers you must NOT modify:
- `_EM = '\u2014'`
- `_esc()`, `_safe_json()`, `_safe_js_json()`, `_fmt_pct()`, `_fmt_score()`, `_fmt_price()`
- `_conf_cls()`, `_eq_cls()`, `_rot_cls()`, `_align_cls()`
- All functions in `analyzers/`, `filters/`, `eq_analyzer/`, `sector_detector/`
- `reports/report_builder.py`, `email_builder.py`, `summary_builder.py`

---

## PART 1 — CSS CHANGES (`docs/assets/style.css`)

### 1A.
Do NOT delete any existing `.rank-row`, `.rank-head`, `.td-n`, `.td-t`, `.td-s`, `.td-p`,
`.td-c`, `.td-r`, `.rth` rules. Leave them in place as unused dead CSS.

### 1B. Add these new rules in the `/* ── RANK PAGE ── */` section after the existing `.rank-wrap` rule:

```css
.rank-card {
  background: linear-gradient(135deg, #130f22 0%, #1a1035 30%, #1f1040 55%, #180d30 75%, #0f0820 100%);
  border: 1px solid var(--rim);
  border-radius: 14px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.3s var(--apple), opacity 0.3s var(--apple);
  position: relative;
  margin-bottom: 10px;
}
.rank-card:last-child { margin-bottom: 0; }
.rank-card::before {
  content: ''; position: absolute; inset: 0; border-radius: 14px;
  background:
    radial-gradient(ellipse at 0% 0%, rgba(155,89,255,0.18) 0%, transparent 55%),
    radial-gradient(ellipse at 100% 100%, rgba(255,110,180,0.10) 0%, transparent 50%),
    radial-gradient(ellipse at 100% 0%, rgba(0,229,255,0.06) 0%, transparent 45%);
  pointer-events: none;
}
.rank-card.dimmed { opacity: 0.4; }
.rank-card.selected { border-color: transparent; }
.rank-card-border-svg {
  position: absolute; inset: 0; width: 100%; height: 100%;
  pointer-events: none; overflow: visible;
}
.rank-card-border-path {
  fill: none; stroke-width: 2.5; stroke: url(#rankBorderGrad);
  stroke-dasharray: 900; stroke-dashoffset: 900;
}
.rank-card.selected .rank-card-border-path {
  animation: rankBorderFill 0.65s cubic-bezier(0.4,0,0.2,1) forwards;
}
.rank-card.closing .rank-card-border-path {
  animation: rankBorderUnfill 0.45s cubic-bezier(0.4,0,0.2,1) forwards;
}
@keyframes rankBorderFill   { from { stroke-dashoffset: 900; } to { stroke-dashoffset: 0; } }
@keyframes rankBorderUnfill { from { stroke-dashoffset: 0;   } to { stroke-dashoffset: 900; } }
.rank-card-main {
  display: flex; flex-wrap: wrap; align-items: center;
  gap: 8px; padding: 14px 16px; position: relative;
}
.rck-n { font-size: 11px; color: var(--pu-lt); font-family: var(--ff-head); font-weight: 700; min-width: 28px; }
.rck-t { font-family: var(--ff-head); font-size: 14px; font-weight: 700; color: var(--snow); letter-spacing: 0.06em; min-width: 52px; }
.rck-s { font-size: 9px; color: var(--mist); flex: 1; min-width: 80px; }
.rck-pills { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.rpill {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 8px; letter-spacing: 0.1em; text-transform: uppercase;
  padding: 3px 8px; border-radius: 6px; border: 1px solid transparent;
  font-family: var(--ff-mono); font-weight: 600; white-space: nowrap;
}
.rpill-lbl { opacity: 0.7; font-size: 7px; }
.rpill-price  { color:#ffd700; background:linear-gradient(90deg,rgba(60,40,0,.8),rgba(180,130,0,.35)); border-image:linear-gradient(90deg,rgba(60,40,0,.9),rgba(255,215,0,.75)) 1; }
.rpill-cup    { color:#39e8a0; background:linear-gradient(90deg,rgba(10,50,30,.8),rgba(57,232,160,.25)); border-image:linear-gradient(90deg,rgba(10,50,30,.9),rgba(57,232,160,.75)) 1; }
.rpill-cnt    { color:#ff9a3c; background:linear-gradient(90deg,rgba(60,30,0,.8),rgba(255,154,60,.25)); border-image:linear-gradient(90deg,rgba(60,30,0,.9),rgba(255,154,60,.75)) 1; }
.rpill-cdn    { color:#ff4d6d; background:linear-gradient(90deg,rgba(60,10,20,.8),rgba(255,77,109,.25)); border-image:linear-gradient(90deg,rgba(60,10,20,.9),rgba(255,77,109,.75)) 1; }
.rpill-rlo    { color:#7dd8ff; background:linear-gradient(90deg,rgba(5,15,50,.8),rgba(0,180,255,.25)); border-image:linear-gradient(90deg,rgba(5,15,50,.9),rgba(100,200,255,.75)) 1; }
.rpill-rmd    { color:#e07a20; background:linear-gradient(90deg,rgba(50,35,0,.8),rgba(220,160,0,.25)); border-image:linear-gradient(90deg,rgba(50,35,0,.9),rgba(220,160,0,.75)) 1; }
.rpill-rhi    { color:#c084ff; background:linear-gradient(90deg,rgba(60,5,15,.8),rgba(180,50,80,.25)); border-image:linear-gradient(90deg,rgba(60,5,15,.9),rgba(200,60,90,.75)) 1; }
.rpill-eq-sup { color:#2dddb8; background:linear-gradient(90deg,rgba(5,50,40,.8),rgba(45,221,184,.25)); border-image:linear-gradient(90deg,rgba(5,50,40,.9),rgba(45,221,184,.75)) 1; }
.rpill-eq-neu { color:#e8e0ff; background:linear-gradient(90deg,rgba(40,40,50,.8),rgba(180,180,200,.25)); border-image:linear-gradient(90deg,rgba(40,40,50,.9),rgba(200,200,220,.75)) 1; }
.rpill-eq-wk  { color:#e07a20; background:linear-gradient(90deg,rgba(50,25,0,.8),rgba(200,110,0,.25)); border-image:linear-gradient(90deg,rgba(50,25,0,.9),rgba(200,110,0,.75)) 1; }
.rpill-eq-rsk { color:#c084ff; background:linear-gradient(90deg,rgba(60,5,15,.8),rgba(180,50,80,.25)); border-image:linear-gradient(90deg,rgba(60,5,15,.9),rgba(200,60,90,.75)) 1; }
.rpill-eq-una { color:#1a0a00; background:linear-gradient(90deg,rgba(80,35,0,.8),rgba(180,80,0,.35)); border-image:linear-gradient(90deg,rgba(80,35,0,.9),rgba(180,80,0,.75)) 1; }
.rpill-rt-sup { color:#2dddb8; background:linear-gradient(90deg,rgba(5,50,40,.8),rgba(45,221,184,.25)); border-image:linear-gradient(90deg,rgba(5,50,40,.9),rgba(45,221,184,.75)) 1; }
.rpill-rt-wt  { color:#e8e0ff; background:linear-gradient(90deg,rgba(40,40,50,.8),rgba(180,180,200,.25)); border-image:linear-gradient(90deg,rgba(40,40,50,.9),rgba(200,200,220,.75)) 1; }
.rpill-rt-wk  { color:#e07a20; background:linear-gradient(90deg,rgba(50,25,0,.8),rgba(200,110,0,.25)); border-image:linear-gradient(90deg,rgba(50,25,0,.9),rgba(200,110,0,.75)) 1; }
.rpill-rt-unk { color:#1a0a00; background:linear-gradient(90deg,rgba(80,35,0,.8),rgba(180,80,0,.35)); border-image:linear-gradient(90deg,rgba(80,35,0,.9),rgba(180,80,0,.75)) 1; }
```

### 1C. Keep these rules completely unchanged:
`.exp-row`, `.exp-row.open`, `@keyframes snap-expand`, `.exp-row.open .est`,
`@keyframes tile-spark`, `.exp-inner`, `.exp-stats`, `.est`, `.est-k`, `.est-v`, `.exp-chart`

### 1D. In the `@media` block add (do not remove anything):
```css
.rank-card-main { gap: 6px; padding: 12px; }
.rck-pills { gap: 5px; }
.rpill { font-size: 7px; padding: 2px 6px; }
```

---

## PART 2 — JS CHANGES INSIDE `_RANK_FETCH_JS`

This is a module-level Python string constant. Do not convert it to an f-string.
Preserve all Python string concatenation syntax.

### 2A. SVG gradient injection

Locate `var scripts = ''` inside `_RANK_FETCH_JS`. Immediately after it, add a guarded
SVG injection using `scripts +=`:

```javascript
if (!document.getElementById('rankBorderGrad')) {
  scripts += '<svg width="0" height="0" style="position:absolute"><defs>'
    + '<linearGradient id="rankBorderGrad" x1="0%" y1="0%" x2="100%" y2="100%">'
    + '<stop offset="0%" stop-color="#1A0A2E"/>'
    + '<stop offset="25%" stop-color="#3D0A4F"/>'
    + '<stop offset="50%" stop-color="#6B0F6B"/>'
    + '<stop offset="75%" stop-color="#8B2BE8"/>'
    + '<stop offset="100%" stop-color="#9b59ff"/>'
    + '</linearGradient></defs></svg>';
}
```

### 2B. Replace the visible row wrapper

Locate the block inside the stocks loop that starts with:
```
html += '<div class="rank-row"
```
This block ends at its closing `+ '</div>'`, immediately before the expand panel block
that starts with `'<div class=\"exp-row\"'`.

Replace ONLY that visible row wrapper block (from the `html += '<div class=\"rank-row\"'`
line through its closing `+ '</div>'`) with:

```javascript
var confVal    = typeof stock.composite_confidence === 'number' ? stock.composite_confidence : null;
var riskVal    = typeof stock.risk_score === 'number' ? stock.risk_score : null;
var confCls    = confVal !== null ? (confVal >= 70 ? 'rpill-cup' : confVal >= 50 ? 'rpill-cnt' : 'rpill-cdn') : 'rpill-cnt';
var riskCls    = riskVal !== null ? (riskVal <= 30 ? 'rpill-rlo' : riskVal <= 55 ? 'rpill-rmd' : 'rpill-rhi') : 'rpill-rmd';
var eqMap      = {'SUPPORTIVE':'rpill-eq-sup','NEUTRAL':'rpill-eq-neu','WEAK':'rpill-eq-wk','RISKY':'rpill-eq-rsk','UNAVAILABLE':'rpill-eq-una'};
var rotMap     = {'SUPPORT':'rpill-rt-sup','WAIT':'rpill-rt-wt','WEAKEN':'rpill-rt-wk','UNKNOWN':'rpill-rt-unk'};
var eqPillCls  = eqMap[eqV]  || 'rpill-eq-neu';
var rotPillCls = rotMap[rotS] || 'rpill-rt-wt';
var confDisp   = confVal !== null ? Math.round(confVal) : '\u2014';
var riskDisp   = riskVal !== null ? Math.round(riskVal) : '\u2014';
var priceDisp  = typeof stock.price === 'number' ? '$' + stock.price.toFixed(2) : '\u2014';

html += '<div class="rank-card" data-ref="' + phUid + '" data-eid="e' + i + '" data-cid="ec' + i + '" onclick="expT(this)">'
     + '<svg class="rank-card-border-svg" viewBox="0 0 100 100" preserveAspectRatio="none">'
     + '<rect class="rank-card-border-path" x="1" y="1" width="98" height="98" rx="13" ry="13"/>'
     + '</svg>'
     + '<div class="rank-card-main">'
     + '<div class="rck-n">#' + i + '</div>'
     + '<div class="rck-t">' + (stock.ticker || '\u2014') + '</div>'
     + '<div class="rck-s">' + sector + '</div>'
     + '<div class="rck-pills">'
     + '<span class="rpill rpill-price"><span class="rpill-lbl">Price</span>' + priceDisp + '</span>'
     + '<span class="rpill ' + confCls + '"><span class="rpill-lbl">Conf</span>' + confDisp + '/100</span>'
     + '<span class="rpill ' + riskCls + '"><span class="rpill-lbl">Risk</span>' + riskDisp + '</span>'
     + '<span class="rpill ' + eqPillCls + '"><span class="rpill-lbl">EQ</span>' + (eqV || '\u2014') + '</span>'
     + '<span class="rpill ' + rotPillCls + '"><span class="rpill-lbl">Rotation</span>' + (rotS || '\u2014') + '</span>'
     + '</div>'
     + '</div>';
```

The expand panel block (`html += '<div class=\"exp-row\"...'`) that immediately follows
stays completely untouched — do not rewrite, reconstruct, or move it. Copy it verbatim
from the existing file.

After the expand panel block ends, add one closing tag to close `.rank-card`:
```javascript
html += '</div>';
```

### 2C. Selector updates — targeted only

In DOM selector and classList operations only, update `.rank-row` references to `.rank-card`.
Only change these specific patterns where found:
- `querySelector('.rank-row')`
- `querySelectorAll('.rank-row')`
- `closest('.rank-row')`
- `matches('.rank-row')`
- `classList.contains('rank-row')`
- `classList.add('rank-row')`
- `classList.remove('rank-row')`

Do not do a blanket string replace across the entire constant.

### 2D. Update `expT` function

Locate by signature `function expT(btn){`. Make only these targeted insertions:

After `var row=document.getElementById(eid);if(!row)return;` insert:
```javascript
var card=btn.closest('.rank-card');
```

After `document.querySelectorAll('.exp-row').forEach(r=>{if(r!==row)closeExpRowInstant(r);});` insert:
```javascript
document.querySelectorAll('.rank-card').forEach(function(c){
  if(c!==card){c.classList.remove('selected');c.classList.add('dimmed');}
});
```

After `row.classList.add('open');` insert:
```javascript
if(card){card.classList.add('selected');}
```

Replace `else { closeExpRow(row); }` with:
```javascript
} else {
  if(card){
    card.classList.remove('selected');
    card.classList.add('closing');
    setTimeout(function(){card.classList.remove('closing');},450);
  }
  document.querySelectorAll('.rank-card').forEach(function(c){c.classList.remove('dimmed');});
  closeExpRow(row);
}
```

Do not touch `closeExpRow()`, `closeExpRowInstant()`, `rafCollapseRow()`,
`animateGenie()`, `animateSlide()`, `mkC()`, `countUp()`.

---

## PART 3 — JS CHANGES INSIDE `_INDEX_FETCH_JS`

### 3A. Update column header row

Locate this block inside `_INDEX_FETCH_JS` (the `rp-cols` header):
```javascript
+ '<div class="rp-cols">'
+ '<span class="rp-col-h">#</span><span class="rp-col-h">Ticker</span>'
+ '<span class="rp-col-h">Sector</span><span class="rp-col-h">Conf</span>'
+ '<span class="rp-col-h">Risk</span><span class="rp-col-h">EQ</span>'
+ '<span class="rp-col-h">Rotation</span>'
+ '</div>'
```

Replace with:
```javascript
+ '<div class="rp-cols">'
+ '<span class="rp-col-h">#</span><span class="rp-col-h">Ticker</span>'
+ '<span class="rp-col-h">Sector</span><span class="rp-col-h">Price</span>'
+ '<span class="rp-col-h">Conf</span>'
+ '</div>'
```

### 3B. Replace the home preview row

The replacement target starts exactly at:
```
rows += '<div class="rp-row" onclick="rpT(\'rp' + i + '\')">'
```
and ends at (but does not include):
```
'<div class="rp-exp" id="rp' + i + '">'
```

Replace everything between those two boundaries with:

```javascript
var rpConfVal = typeof s.composite_confidence === 'number' ? s.composite_confidence : null;
var rpConf    = rpConfVal !== null ? Math.round(rpConfVal) : '\u2014';
var rpConfCls = rpConfVal !== null ? (rpConfVal >= 70 ? 'rpill-cup' : rpConfVal >= 50 ? 'rpill-cnt' : 'rpill-cdn') : 'rpill-cnt';
var rpPrice   = typeof s.price === 'number' ? '$' + s.price.toFixed(2) : '\u2014';
var sector    = (s.sector || '').replace(/_/g,' ').replace(/\b\w/g, function(c){ return c.toUpperCase(); });

rows += '<div class="rank-card" onclick="rpT(\'rp' + i + '\')">'
      + '<div class="rank-card-main">'
      + '<div class="rck-n">#' + i + '</div>'
      + '<div class="rck-t">' + (s.ticker || '\u2014') + '</div>'
      + '<div class="rck-s">' + sector + '</div>'
      + '<div class="rck-pills">'
      + '<span class="rpill rpill-price"><span class="rpill-lbl">Price</span>' + rpPrice + '</span>'
      + '<span class="rpill ' + rpConfCls + '"><span class="rpill-lbl">Conf</span>' + rpConf + '/100</span>'
      + '</div>'
      + '</div>';
```

Everything from `'<div class=\"rp-exp\"'` onward stays verbatim unchanged.

After the `.rp-exp` closing block add:
```javascript
rows += '</div>';
```

Preserve the existing top-5 limit already in the original block.

---

## DO NOT TOUCH
- `closeExpRow()`, `closeExpRowInstant()`, `rafCollapseRow()`, `animateGenie()`,
  `animateSlide()`, `mkC()`, `countUp()`
- Any `data-raw` attributes on `.est-v` elements
- `data-ref`, `data-cid`, canvas `id="ec..."` — required for expand and Chart.js
- `_ARCHIVE_FETCH_JS`, `_COPY_PROMPT_JS`, `_RCT_JS` constants
- `docs/assets/app.js`
- All files outside `reports/dashboard_builder.py` and `docs/assets/style.css`

---

## VERIFICATION CHECKLIST

Before finishing, confirm every item:

1. No f-string was created from a JS string constant
2. No backslash escape inside a `{}` in an f-string
3. Expand panel block copied verbatim — not reconstructed or rewritten
4. `expT()` still calls `closeExpRowInstant` and `closeExpRow`
5. `countUp` still reads `ev.dataset.raw`
6. Both `_RANK_FETCH_JS` and `_INDEX_FETCH_JS` updated
7. SVG gradient uses `scripts +=` with `getElementById` guard before the loop
8. No invented CSS variables used (`--rim` and `--apple` already exist)
9. No JSON field names renamed
10. Only DOM selector/classList `.rank-row` references updated — no blanket replace
11. `data-ref`, `data-cid`, canvas IDs untouched
12. Loop order, sorting, filtering untouched
13. Home preview `.rp-exp` block untouched — only row header replaced
14. Closing `</div>` added after expand panel in both `_RANK_FETCH_JS` and `_INDEX_FETCH_JS`
    to correctly close `.rank-card`