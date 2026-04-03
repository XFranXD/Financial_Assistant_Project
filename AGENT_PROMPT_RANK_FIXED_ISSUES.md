# MRE AGENT PROMPT — RANK CARD FIX v2
**Target files: `reports/dashboard_builder.py`, `docs/assets/style.css`**

---

## OBJECTIVE

Fix five specific issues introduced in the v5 rank card redesign:
1. SVG border animation stretches with the expanded panel instead of staying on the header row only
2. Dimming bug when switching between open cards leaves everything dimmed with no glow
3. Column header rows must be removed from both pages
4. Sector text needs dynamic per-sector color (font color only, no background)
5. Sector font size too small — increase it

---

## CONTEXT — READ BEFORE TOUCHING ANYTHING

`dashboard_builder.py` contains module-level Python string constants that hold JavaScript. These are NOT f-strings. Do not convert them to f-strings. `{}` inside these constants are literal JavaScript, never Python interpolation.

Do not rename any JSON fields. Do not modify sorting, filtering, loop order, or any function not explicitly listed below. Do not touch `closeExpRow()`, `closeExpRowInstant()`, `rafCollapseRow()`, `animateGenie()`, `animateSlide()`, `mkC()`, `countUp()`, `_RCT_JS`, `_COPY_PROMPT_JS`, `_ARCHIVE_FETCH_JS`. Do not touch `data-ref`, `data-cid`, canvas `id="ec..."`, or `.exp-row` expand panel blocks.

---

## FIX 1 — SVG border must animate on header only, not the full expanded card

**Root cause:** The `.rank-card-border-svg` is `position:absolute; inset:0; height:100%` inside `.rank-card`, which includes the `.exp-row` panel. When the panel expands, the SVG stretches to match the full card height. The SVG must be repositioned to live inside `.rank-card-main` instead of `.rank-card`.

**Scope note:** This fix applies to `_RANK_FETCH_JS` only. The home preview cards in `_INDEX_FETCH_JS` do not contain an SVG border element — do not add one.

### 1A. CSS change in `docs/assets/style.css`

Locate:
```css
.rank-card-main {
  display: flex; flex-wrap: wrap; align-items: center;
  gap: 8px; padding: 14px 16px; position: relative;
}
```

Replace with:
```css
.rank-card-main {
  display: flex; flex-wrap: wrap; align-items: center;
  gap: 8px; padding: 14px 16px; position: relative;
  overflow: hidden;
}
```

Also update the stroke-width. Locate:
```css
.rank-card-border-path {
  fill: none; stroke-width: 2.5; stroke: url(#rankBorderGrad);
  stroke-dasharray: 900; stroke-dashoffset: 900;
}
```

Replace with:
```css
.rank-card-border-path {
  fill: none; stroke-width: 1.2; stroke: url(#rankBorderGrad);
  stroke-dasharray: 900; stroke-dashoffset: 900;
}
```

Do not add `border-radius` to `.rank-card-border-svg` — the `<rect rx="13">` already handles the shape.

### 1B. JS change inside `_RANK_FETCH_JS` in `dashboard_builder.py`

Move the SVG element from being a sibling of `.rank-card-main` to being a child inside it.

Locate this exact block inside `_RANK_FETCH_JS`:
```python
    "      html += '<div class=\"rank-card\" data-ref=\"' + phUid + '\" data-eid=\"e' + i + '\" data-cid=\"ec' + i + '\" onclick=\"expT(this)\">'\\n"
    "           + '<svg class=\"rank-card-border-svg\" viewBox=\"0 0 100 100\" preserveAspectRatio=\"none\">'\\n"
    "           + '<rect class=\"rank-card-border-path\" x=\"1\" y=\"1\" width=\"98\" height=\"98\" rx=\"13\" ry=\"13\"/>'\\n"
    "           + '</svg>'\\n"
    "           + '<div class=\"rank-card-main\">'\\n"
```

Replace with:
```python
    "      html += '<div class=\"rank-card\" data-ref=\"' + phUid + '\" data-eid=\"e' + i + '\" data-cid=\"ec' + i + '\" onclick=\"expT(this)\">'\\n"
    "           + '<div class=\"rank-card-main\">'\\n"
    "           + '<svg class=\"rank-card-border-svg\" viewBox=\"0 0 100 100\" preserveAspectRatio=\"none\">'\\n"
    "           + '<rect class=\"rank-card-border-path\" x=\"1\" y=\"1\" width=\"98\" height=\"98\" rx=\"13\" ry=\"13\"/>'\\n"
    "           + '</svg>'\\n"
```

The `.rank-card-main` closing tag and everything after it (the `.exp-row` block) stays completely untouched.

---

## FIX 2 — Dimming bug when switching cards

**Root cause:** `closeExpRowInstant` closes the expand panel of the previously selected card but does not remove the `selected` class from that card. When a new card is clicked, the dimming loop skips the new card but leaves the old card's `selected` class intact. The fix is to strip ALL cards of `selected`, `dimmed`, and `closing` at the very top of `expT`, before anything else runs — then re-apply `dimmed` conditionally only when opening.

The `expT` function lives in the constant `_EXP_T_JS` (a raw triple-quoted string, defined around line 839).

**Target only the setup block at the top of `expT` — do not touch anything inside `if(!was){` or the `else` branch.**

Locate this exact setup block inside `expT` (from the function signature through the end of the dimming forEach):
```javascript
function expT(btn){
  var el=document.getElementById(btn.dataset.ref);
  if(!el)return;
  var data;
  try{data=JSON.parse(el.textContent);}catch(e){data=[];}
  var cid=btn.dataset.cid,eid=btn.dataset.eid;
  var row=document.getElementById(eid);if(!row)return;
  var card=btn.closest('.rank-card');
  var was=row.classList.contains('open');
  document.querySelectorAll('.exp-row').forEach(r=>{if(r!==row)closeExpRowInstant(r);});
  document.querySelectorAll('.rank-card').forEach(function(c){
    if(c!==card){c.classList.remove('selected');c.classList.add('dimmed');}
  });
```

Replace with:
```javascript
function expT(btn){
  var el=document.getElementById(btn.dataset.ref);
  if(!el)return;
  var data;
  try{data=JSON.parse(el.textContent);}catch(e){data=[];}
  var cid=btn.dataset.cid,eid=btn.dataset.eid;
  var row=document.getElementById(eid);if(!row)return;
  var card=btn.closest('.rank-card');
  var was=row.classList.contains('open');
  document.querySelectorAll('.rank-card').forEach(function(c){
    c.classList.remove('selected','dimmed','closing');
  });
  document.querySelectorAll('.exp-row').forEach(r=>{if(r!==row)closeExpRowInstant(r);});
  if(!was){
    document.querySelectorAll('.rank-card').forEach(function(c){
      if(c!==card){c.classList.add('dimmed');}
    });
```

Everything from `row.style.display=''` onward through the end of the function is untouched.

---

## FIX 3 — Remove column header rows

### 3A. Static rank page header — Python f-string in `dashboard_builder.py`

Locate this exact block in the Python f-string (around line 1481):
```python
            '<div class="rank-head">'
            '<span class="rth">#</span><span class="rth">Ticker</span><span class="rth">Sector</span>'
            '<span class="rth">Price</span><span class="rth">Conf</span><span class="rth">Risk</span>'
            '<span class="rth">EQ</span><span class="rth">Rotation</span>'
            '</div>'
```

Delete these five lines entirely. The `<div class="rank-wrap">` before it and `<div id="rank-board-mount"></div>` after it stay untouched.

### 3B. Home preview header — inside `_INDEX_FETCH_JS`

Locate this block inside `_INDEX_FETCH_JS`:
```python
    "      + '<div class=\"rp-cols\">'\\n"
    "      + '<span class=\"rp-col-h\">#</span><span class=\"rp-col-h\">Ticker</span>'\\n"
    "      + '<span class=\"rp-col-h\">Sector</span><span class=\"rp-col-h\">Price</span>'\\n"
    "      + '<span class=\"rp-col-h\">Conf</span>'\\n"
    "      + '</div>'\\n"
```

Delete these five lines entirely. The `rank-preview-head` div before it and the `+ rows` line after it stay untouched.

---

## FIX 4 & 5 — Sector dynamic color and increased font size

### 4A. CSS change in `docs/assets/style.css`

Locate:
```css
.rck-s { font-size: 9px; color: var(--mist); flex: 1; min-width: 80px; }
```

Replace with:
```css
.rck-s { font-size: 11px; flex: 1; min-width: 80px; }
```

Color is now set inline per-card via JS — remove the `color` declaration from the CSS rule.

### 4B. JS change — sector color map in `_RANK_FETCH_JS`

Locate this line inside the `arr.forEach` loop in `_RANK_FETCH_JS`:
```python
    "      var sector   = (stock.sector || '').replace(/_/g,' ').replace(/\\b\\w/g, function(c){ return c.toUpperCase(); });\\n"
```

Replace with:
```python
    "      var sector   = (stock.sector || '').replace(/_/g,' ').replace(/\\b\\w/g, function(c){ return c.toUpperCase(); });\\n"
    "      var _sMap={'Energy':'#f4a44a','Technology':'#7dd8ff','Healthcare':'#7be8b0','Financials':'#c9b8ff',\\n"
    "        'Consumer Discretionary':'#ff9ec4','Consumer Staples':'#b8e8c8','Industrials':'#ffd27a',\\n"
    "        'Materials':'#a8e6cf','Real Estate':'#ffb8a0','Utilities':'#9ecfff',\\n"
    "        'Communication Services':'#d4b8ff'};\\n"
    "      var _sKey=_sMap[sector]?sector:Object.keys(_sMap).find(function(k){return sector.toLowerCase().indexOf(k.toLowerCase())!==-1;})||'';\\n"
    "      var sectorColor=_sMap[_sKey]||'#a89bc2';\\n"
```

Then locate the `.rck-s` output line in `_RANK_FETCH_JS`:
```python
    "           + '<div class=\"rck-s\">' + sector + '</div>'\\n"
```

Replace with:
```python
    "           + '<div class=\"rck-s\" style=\"color:' + sectorColor + '\">' + sector + '</div>'\\n"
```

### 4C. Same sector color logic in `_INDEX_FETCH_JS`

Locate this line inside the `top5.forEach` loop in `_INDEX_FETCH_JS`:
```python
    "      var sector    = (s.sector || '').replace(/_/g,' ').replace(/\\b\\w/g, function(c){ return c.toUpperCase(); });\\n"
```

Replace with:
```python
    "      var sector    = (s.sector || '').replace(/_/g,' ').replace(/\\b\\w/g, function(c){ return c.toUpperCase(); });\\n"
    "      var _sMap={'Energy':'#f4a44a','Technology':'#7dd8ff','Healthcare':'#7be8b0','Financials':'#c9b8ff',\\n"
    "        'Consumer Discretionary':'#ff9ec4','Consumer Staples':'#b8e8c8','Industrials':'#ffd27a',\\n"
    "        'Materials':'#a8e6cf','Real Estate':'#ffb8a0','Utilities':'#9ecfff',\\n"
    "        'Communication Services':'#d4b8ff'};\\n"
    "      var _sKey=_sMap[sector]?sector:Object.keys(_sMap).find(function(k){return sector.toLowerCase().indexOf(k.toLowerCase())!==-1;})||'';\\n"
    "      var sectorColor=_sMap[_sKey]||'#a89bc2';\\n"
```

Then locate the `.rck-s` output line in `_INDEX_FETCH_JS`:
```python
    "            + '<div class=\"rck-s\">' + sector + '</div>'\\n"
```

Replace with:
```python
    "            + '<div class=\"rck-s\" style=\"color:' + sectorColor + '\">' + sector + '</div>'\\n"
```

---

## DO NOT TOUCH
- `closeExpRow()`, `closeExpRowInstant()`, `rafCollapseRow()`, `animateGenie()`, `animateSlide()`, `mkC()`, `countUp()`
- Everything inside `if(!was){` and the `else` branch of `expT` — Fix 2 only modifies the setup block before `if(!was){`
- `.exp-row` expand panel block — do not rewrite, reconstruct, or move it
- `data-ref`, `data-cid`, canvas `id="ec..."` attributes
- `_ARCHIVE_FETCH_JS`, `_COPY_PROMPT_JS`, `_RCT_JS`
- `docs/assets/app.js`
- All other Python functions in `dashboard_builder.py`
- All files outside `reports/dashboard_builder.py` and `docs/assets/style.css`

---

## VERIFICATION CHECKLIST

Before finishing, confirm every item:

1. SVG is now a child of `.rank-card-main` in `_RANK_FETCH_JS`, not a sibling
2. `_INDEX_FETCH_JS` preview cards were not modified for SVG — they never had one
3. `.rank-card-main` has `overflow: hidden` added to its CSS rule
4. `.rank-card-border-path` `stroke-width` is `1.2`, not `2.5`
5. No `border-radius` was added to `.rank-card-border-svg` in CSS
6. `expT` setup block: ALL cards stripped of `selected`, `dimmed`, `closing` first
7. `expT` setup block: `closeExpRowInstant` runs second on all other rows
8. `expT` setup block: `dimmed` applied to non-selected cards only inside `if(!was){`
9. `var was` is read BEFORE any class manipulation
10. Everything after `if(!was){` in `expT` is untouched
11. `.rank-head` block (5 lines) deleted from Python f-string — `rank-wrap` and `rank-board-mount` divs intact
12. `rp-cols` block (5 lines) deleted from `_INDEX_FETCH_JS` — `rank-preview-head` and `+ rows` intact
13. `.rck-s` CSS rule has no `color` declaration — only `font-size: 11px`, `flex`, `min-width`
14. `_sMap` in both JS blocks has no duplicate keys — `Energy` appears exactly once
15. Sector lookup uses exact-match-first: `_sMap[sector] ? sector : Object.keys(_sMap).find(...)`
16. Both `.rck-s` output lines include `style="color:' + sectorColor + '"` inline
17. No f-string was created from a JS string constant
18. `countUp` still reads `ev.dataset.raw`
19. `mkC()` call untouched, `data-cid` untouched