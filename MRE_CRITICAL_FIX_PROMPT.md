# MRE — CRITICAL FIX PROMPT
# Two files to fix. Read everything before touching anything.
# Do not touch any file not listed below.

---

## WHAT IS BROKEN AND WHY

Every run crashes with this error:

    Dashboard build skipped: f-string expression part cannot include a backslash

This means `dashboard_builder.py` has never successfully produced new output
since the frontend redesign was deployed. The live dashboard still shows the
old pre-redesign HTML because the new render functions have never executed.

The cause is 7 specific lines in `dashboard_builder.py` where `"\u2014"` (the
em dash character) appears inside the `{}` expression part of an f-string.
Python 3.11 does not allow backslash escapes inside f-string expressions at
runtime. This crashes the entire `build_dashboard()` call.

The second issue is `docs/guide.html` — it was replaced with a thin 3-section
stub instead of keeping the real operational content with all 12 sections.

**IMPORTANT — py_compile warning:** The `py_compile` verification step below
will print `OK` even BEFORE the fix is applied, because `py_compile` on
Python 3.12 does not catch this class of error. Only the regex scan and the
presence of `_EM` in the file are reliable proof the fix was applied correctly.
Do not use `py_compile` output as confirmation — use the regex scan.

---

## FIX 1 — dashboard_builder.py: 7 f-string backslash bugs

File: `reports/dashboard_builder.py`

### Step 1 — Add a module-level constant near the top of the file

Find the block of module-level constants (where `_FONTS_LINK`, `_CHARTJS`,
`_safe_json` etc. are defined). Add this line with them:

```python
_EM = '\u2014'  # em dash — safe to use inside f-string expressions
```

This constant holds the em dash character directly, with no backslash escape,
so it can safely be referenced inside `{}` expression parts of f-strings.

### Step 2 — Fix all 7 lines

Make ONLY these 7 line replacements. Change nothing else.

**Line 911** — replace:
```python
                f'<div><span class="ntag {_eq_cls(eq_v)}">{_esc(eq_v) or "\u2014"}</span></div>'
```
with:
```python
                f'<div><span class="ntag {_eq_cls(eq_v)}">{_esc(eq_v) or _EM}</span></div>'
```

**Line 912** — replace:
```python
                f'<div><span class="ntag {_rot_cls(rot_s)}">{_esc(rot_s) or "\u2014"}</span></div>'
```
with:
```python
                f'<div><span class="ntag {_rot_cls(rot_s)}">{_esc(rot_s) or _EM}</span></div>'
```

**Line 979** — replace:
```python
                f'<div><div class="rcc-k">Sys 1 &middot; Tickers</div><div class="rcc-v">{tickers or "\u2014"}'
```
with:
```python
                f'<div><div class="rcc-k">Sys 1 &middot; Tickers</div><div class="rcc-v">{tickers or _EM}'
```

**Line 1147** — replace:
```python
                f'<div class="est"><div class="est-k">Verdict</div><div class="est-v {_conf_cls(conf)}">{_esc(verdict or "\u2014")}</div></div>'
```
with:
```python
                f'<div class="est"><div class="est-k">Verdict</div><div class="est-v {_conf_cls(conf)}">{_esc(verdict) or _EM}</div></div>'
```

**Line 1160** — replace:
```python
                f'<div><span class="ntag {_eq_cls(eq_v)}" style="font-size:8px">{_esc(eq_v) or "\u2014"}</span></div>'
```
with:
```python
                f'<div><span class="ntag {_eq_cls(eq_v)}" style="font-size:8px">{_esc(eq_v) or _EM}</span></div>'
```

**Line 1161** — replace:
```python
                f'<div><span class="ntag {_rot_cls(rot_s)}" style="font-size:8px">{_esc(rot_s) or "\u2014"}</span></div>'
```
with:
```python
                f'<div><span class="ntag {_rot_cls(rot_s)}" style="font-size:8px">{_esc(rot_s) or _EM}</span></div>'
```

**Line 1255** — replace:
```python
                    f'<div><div class="rcc-k">Sys 1</div><div class="rcc-v">{tickers or "\u2014"}'
```
with:
```python
                    f'<div><div class="rcc-k">Sys 1</div><div class="rcc-v">{tickers or _EM}'
```

### Step 3 — Fix the SyntaxWarning in _EXP_T_JS

There is a secondary non-crash issue: the `_EXP_T_JS` triple-quoted string
constant (around line 422) contains a JS regex `[\d.]` which generates a
`SyntaxWarning: invalid escape sequence '\d'` on Python 3.12+ because `\d`
is not a recognized Python escape sequence in a regular string.

Find this line inside `_EXP_T_JS`:
```python
          var prefix=raw.match(/^[▲▼]/)?.[0]||'',suffix=raw.replace(/^[▲▼]?[\d.]+/,'');
```

Fix by changing the opening `"""` of `_EXP_T_JS` to `r"""` (raw string), which
suppresses all Python escape processing inside it and is safe because the
string contains no Python escape sequences that need to be interpreted:

Find the line that reads:
```python
_EXP_T_JS = """
```
Replace it with:
```python
_EXP_T_JS = r"""
```

This silences the warning without changing any content of the JS string.

### Step 4 — Verify the fix

Run the regex scan to confirm all 7 lines are fixed:

```bash
python3 -c "
import re
with open('reports/dashboard_builder.py') as f:
    lines = f.readlines()
found = False
for i, line in enumerate(lines, 1):
    if 'f\"' not in line and \"f'\" not in line:
        continue
    matches = re.findall(r'\{[^{}]*\\\\[u0-9][^{}]*\}', line)
    if matches:
        print(f'Line {i} still has backslash in expression: {matches}')
        found = True
if not found:
    print('OK — no backslash-in-expression issues found')
"
```

This must print `OK — no backslash-in-expression issues found`.

Also confirm `_EM` exists in the file:

```bash
grep -n "_EM" reports/dashboard_builder.py | head -5
```

Must show the constant definition and at least some of the 7 fixed lines.

---

## FIX 2 — Restore docs/guide.html with real content + new design

File: `docs/guide.html`

The current guide is a 91-line stub with only 3 sections. Replace the entire
contents of `docs/guide.html` with the following complete 12-section version:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="MRE Research Guide — How to read scores and act on signals">
<title>MRE // Research Guide</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/style.css">
<style>
.guide-section { margin-bottom: 36px; }
.guide-head {
  font-family: var(--ff-head);
  font-size: 13px; font-weight: 700; color: var(--snow);
  letter-spacing: 0.08em; text-transform: uppercase;
  padding-bottom: 9px; border-bottom: 1px solid var(--rim2); margin-bottom: 16px;
  display: flex; align-items: center; gap: 10px;
}
.guide-head span { color: transparent; background: linear-gradient(90deg, var(--pu-lt), var(--mg)); -webkit-background-clip: text; background-clip: text; }
.guide-head::before { content: '▸'; color: var(--pu); font-size: 11px; }
.guide-text { font-size: 11px; color: var(--slate); line-height: 1.9; margin-bottom: 14px; letter-spacing: 0.03em; }
.guide-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px,1fr)); gap: 8px; margin-bottom: 14px; }
.guide-card {
  background: var(--l1); border: 1px solid var(--rim);
  padding: 13px 15px; position: relative; overflow: hidden;
  transition: border-color 0.28s var(--ease), transform 0.3s var(--apple), box-shadow 0.3s var(--apple);
}
.guide-card::after {
  content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, var(--pu), var(--mg));
  transform: scaleX(0); transform-origin: left;
  transition: transform 0.38s var(--apple);
}
.guide-card:hover { border-color: var(--rim2); transform: translateY(-2px); box-shadow: 0 6px 24px rgba(155,89,255,0.1); }
.guide-card:hover::after { transform: scaleX(1); }
.guide-term { font-family: var(--ff-head); font-size: 10px; font-weight: 700; color: var(--pu-lt); letter-spacing: 0.06em; margin-bottom: 5px; text-transform: uppercase; }
.guide-desc { font-size: 11px; color: var(--mist); line-height: 1.65; }
.signal-row {
  display: flex; gap: 14px; align-items: flex-start;
  padding: 8px 0; border-bottom: 1px solid var(--rim);
  font-size: 11px;
}
.signal-row:last-child { border-bottom: none; }
.signal-key { color: var(--up); font-family: var(--ff-head); font-size: 10px; font-weight: 700; min-width: 130px; letter-spacing: 0.04em; padding-top: 2px; }
.signal-key.dn { color: var(--dn); }
.signal-key.nt { color: var(--nt); }
.signal-desc { color: var(--slate); line-height: 1.7; }
.verdict-row { display: flex; gap: 12px; align-items: flex-start; padding: 8px 0; border-bottom: 1px solid var(--rim); font-size: 11px; }
.verdict-row:last-child { border-bottom: none; }
.verdict-badge { font-family: var(--ff-head); font-weight: 700; font-size: 9px; letter-spacing: 0.08em; min-width: 140px; padding-top: 2px; }
.vr-now  { color: var(--up); }
.vr-watch { color: var(--nt); }
.vr-skip  { color: var(--mist); }
.warn-box {
  background: rgba(155,89,255,0.05);
  border-left: 3px solid var(--pu);
  padding: 12px 16px; margin: 14px 0;
  font-size: 11px; color: var(--slate); line-height: 1.8;
}
.warn-box strong { display: block; margin-bottom: 6px; color: var(--pu-lt); font-family: var(--ff-head); font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; }
.thresh {
  display: flex; align-items: center; gap: 14px;
  padding: 10px 16px; background: var(--l1);
  border: 1px solid var(--rim); border-top: none;
  transition: background 0.22s var(--ease); font-size: 11px;
}
.thresh:first-child { border-top: 1px solid var(--rim); }
.thresh:hover { background: var(--l2); }
.thresh-bar { height: 2px; width: 44px; border-radius: 1px; flex-shrink: 0; }
.thresh-label { color: var(--snow); flex: 1; }
.thresh-range { color: var(--mist); font-family: var(--ff-mono); }
.sys-pill {
  display: inline-block; font-family: var(--ff-mono);
  font-size: 9px; letter-spacing: 0.12em; text-transform: uppercase;
  padding: 3px 10px; border: 1px solid;
  margin-right: 8px; margin-bottom: 10px;
  transition: transform 0.28s var(--apple), box-shadow 0.28s var(--apple);
}
.sys-pill:hover { transform: translateY(-2px); }
.sp1 { color: var(--cyan);  border-color: rgba(0,229,255,.3); }
.sp1:hover { box-shadow: 0 0 12px rgba(0,229,255,.2); }
.sp2 { color: var(--up);    border-color: rgba(57,232,160,.3); }
.sp2:hover { box-shadow: 0 0 12px rgba(57,232,160,.2); }
.sp3 { color: var(--nt);    border-color: rgba(255,154,60,.3); }
.sp3:hover { box-shadow: 0 0 12px rgba(255,154,60,.2); }
</style>
</head>
<body>
<div class="scanlines"></div>

<!-- NAV: MUST MATCH _nav_html('guide') OUTPUT EXACTLY. -->
<nav>
  <div class="brand">
    <div class="brand-pulse"></div>
    <span>MRE // System</span>
  </div>
  <div class="nav-tabs">
    <a href="index.html"   class="tab">Home</a>
    <a href="rank.html"    class="tab">Rank</a>
    <a href="news.html"    class="tab">News</a>
    <a href="archive.html" class="tab">Archive</a>
    <a href="guide.html"   class="tab on">Guide</a>
  </div>
</nav>

<div class="pages">
<div id="p-guide" class="page on">
  <div class="pg-eyebrow">Documentation &middot; How to use this system</div>
  <div class="pg-title">Research <span class="hi">Guide</span></div>
  <div class="pg-sub">How to read reports, what each signal means, and what this system cannot tell you.</div>

  <!-- 1. How This System Works -->
  <div class="guide-section">
    <div class="guide-head"><span>1.</span> How This System Works</div>
    <div class="guide-text">This system runs four times per trading day (9:45, 11:45, 13:45, and 16:00 ET). Each run collects news from free RSS feeds, fetches market data from Yahoo Finance and similar free-tier sources, runs a multi-module analytical pipeline, and ranks companies against each other using a composite confidence score.</div>
    <div class="guide-text">No paid data sources are used. No predictions are made. No trades are taken. The output is a ranked list of screening opportunities for further human research.</div>
    <div style="margin-bottom:14px">
      <span class="sys-pill sp1">System 1 &middot; Research Engine</span>
      <span class="sys-pill sp2">System 2 &middot; Earnings Quality</span>
      <span class="sys-pill sp3">System 3 &middot; Sector Rotation</span>
    </div>
    <div class="guide-text">Three integrated systems feed every candidate. System 1 aggregates news, momentum, and fundamentals into a composite confidence score. System 2 reads SEC filings to assess earnings trustworthiness. System 3 detects active sector rotation. All three feed the final ranking.</div>
  </div>

  <!-- 2. Reading the Report -->
  <div class="guide-section">
    <div class="guide-head"><span>2.</span> Reading the Report</div>
    <div class="guide-grid">
      <div class="guide-card">
        <div class="guide-term">LOW RISK OPPORTUNITIES</div>
        <div class="guide-desc">Confidence &ge; 75. Strong multi-signal alignment. Start research here.</div>
      </div>
      <div class="guide-card">
        <div class="guide-term">MODERATE RISK OPPORTUNITIES</div>
        <div class="guide-desc">Confidence 50&ndash;74. Partial signals. One or more risk factors elevated. Check the reason line.</div>
      </div>
      <div class="guide-card">
        <div class="guide-term">&#9632;&#9632; Warning notices</div>
        <div class="guide-desc">Earnings approaching, price-fundamental divergence, or unusual volume. Read these carefully.</div>
      </div>
      <div class="guide-card">
        <div class="guide-term">&#9650; / &#9660; Arrows</div>
        <div class="guide-desc">&#9650; = positive (price up, signal bullish). &#9660; = negative (price down, signal bearish). &ndash; = flat/neutral.</div>
      </div>
    </div>

    <div class="guide-text" style="margin-top:8px;margin-bottom:8px;color:var(--snow);">Verdict Labels</div>
    <div class="verdict-row"><span class="verdict-badge vr-now">RESEARCH NOW</span><span class="signal-desc">Confidence &ge; 75. Strong multi-signal alignment. Prioritise for deeper research.</span></div>
    <div class="verdict-row"><span class="verdict-badge vr-watch">WATCH</span><span class="signal-desc">Confidence 50&ndash;74. Partial signals. Worth monitoring but verify before acting.</span></div>
    <div class="verdict-row"><span class="verdict-badge vr-skip">SKIP</span><span class="signal-desc">Confidence 35&ndash;49. Signals too weak or mixed. Not worth research time at this stage.</span></div>
  </div>

  <!-- 3. Confidence Score -->
  <div class="guide-section">
    <div class="guide-head"><span>3.</span> Confidence Score</div>
    <div class="guide-text">The confidence score is a composite 0&ndash;100 metric. It is NOT a probability of profit. It measures how many independent signals align and how strongly. Formula: Risk 35% + Opportunity 35% + Signal Agreement 20% + Sector Momentum 10%.</div>
    <div class="thresh" style="border-top:1px solid var(--rim)">
      <div class="thresh-bar" style="background:var(--up)"></div>
      <div class="thresh-label">Low Risk &middot; Research Now</div><div class="thresh-range">75 &ndash; 100</div>
    </div>
    <div class="thresh">
      <div class="thresh-bar" style="background:var(--nt)"></div>
      <div class="thresh-label">Moderate Risk &middot; Watch</div><div class="thresh-range">50 &ndash; 74</div>
    </div>
    <div class="thresh">
      <div class="thresh-bar" style="background:var(--dn)"></div>
      <div class="thresh-label">Weak &middot; Monitor only</div><div class="thresh-range">35 &ndash; 49</div>
    </div>
    <div class="thresh">
      <div class="thresh-bar" style="background:var(--ghost)"></div>
      <div class="thresh-label">Excluded &middot; Not shown</div><div class="thresh-range">&lt; 35</div>
    </div>
  </div>

  <!-- 4. Trend Signals -->
  <div class="guide-section">
    <div class="guide-head"><span>4.</span> Trend Signals (1M / 3M / 6M)</div>
    <div class="guide-text">Trend shows price return over 1 month, 3 months, and 6 months. All three positive = confirmed momentum across timeframes. Only one timeframe positive = early-stage or single-period event, not confirmed.</div>
    <div class="signal-row"><span class="signal-key">&#9650; all three</span><span class="signal-desc">Sustained uptrend. Strongest trend signal.</span></div>
    <div class="signal-row"><span class="signal-key">&#9650; 1M only</span><span class="signal-desc">Recent pop. Could be mean reversion or news reaction &mdash; verify.</span></div>
    <div class="signal-row"><span class="signal-key dn">&#9660; all three</span><span class="signal-desc">Sustained downtrend. Risk of continued decline even with good fundamentals.</span></div>
  </div>

  <!-- 5. Valuation Signals -->
  <div class="guide-section">
    <div class="guide-head"><span>5.</span> Valuation Signals</div>
    <div class="guide-grid">
      <div class="guide-card">
        <div class="guide-term">Profit Margin</div>
        <div class="guide-desc">Cents kept per $1 of revenue. Higher = more efficient. Compare within the same sector.</div>
      </div>
      <div class="guide-card">
        <div class="guide-term">ROIC</div>
        <div class="guide-desc">Return on Invested Capital. Above 15% = excellent. 8&ndash;15% = solid. Below 8% = weak business economics.</div>
      </div>
      <div class="guide-card">
        <div class="guide-term">Debt-to-Equity (D/E)</div>
        <div class="guide-desc">Ratio of debt to shareholder equity. Below 0.3 = very little debt. Above 1.5 = elevated. Above 2.5 = high.</div>
      </div>
      <div class="guide-card">
        <div class="guide-term">FCF (Operating Cash Flow)</div>
        <div class="guide-desc">Free Cash Flow proxy. Positive = business generates real cash. Negative = burning cash.</div>
      </div>
    </div>
  </div>

  <!-- 6. Signal Agreement -->
  <div class="guide-section">
    <div class="guide-head"><span>6.</span> Signal Agreement</div>
    <div class="guide-text">Signal Agreement measures how many independent analysis modules reach the same directional conclusion. The model is multiplicative: one contradictory signal significantly reduces the overall score. Inputs: momentum &times; sector &times; event &times; volume. All four must align for a high agreement score.</div>
  </div>

  <!-- 7. Volume Signals -->
  <div class="guide-section">
    <div class="guide-head"><span>7.</span> Volume Signals</div>
    <div class="signal-row"><span class="signal-key">Elevated bullish</span><span class="signal-desc">High volume on up days &mdash; institutional buying signal.</span></div>
    <div class="signal-row"><span class="signal-key">Elevated bearish</span><span class="signal-desc">High volume on down days &mdash; distribution or panic signal.</span></div>
    <div class="signal-row"><span class="signal-key nt">Unusually high</span><span class="signal-desc">Volume &ge; 2&times; average. Something is drawing attention. Investigate why.</span></div>
    <div class="signal-row"><span class="signal-key nt">Low activity</span><span class="signal-desc">Volume &lt; 0.8&times; average. Less conviction behind any price move.</span></div>
  </div>

  <!-- 8. Risk Score -->
  <div class="guide-section">
    <div class="guide-head"><span>8.</span> Risk Score</div>
    <div class="guide-text">Composite 0&ndash;100 risk measure. Lower is safer. Seven components feed the score:</div>
    <div class="guide-grid">
      <div class="guide-card"><div class="guide-term">Debt (D/E)</div><div class="guide-desc">High leverage amplifies losses in downturns.</div></div>
      <div class="guide-card"><div class="guide-term">Volatility (Beta)</div><div class="guide-desc">High beta = larger price swings in both directions.</div></div>
      <div class="guide-card"><div class="guide-term">Liquidity</div><div class="guide-desc">Low average daily volume = harder to exit large positions quickly.</div></div>
      <div class="guide-card"><div class="guide-term">EPS Stability</div><div class="guide-desc">Inconsistent earnings make valuation unreliable.</div></div>
      <div class="guide-card"><div class="guide-term">Drawdown</div><div class="guide-desc">Large distance from 90-day high signals price weakness.</div></div>
      <div class="guide-card"><div class="guide-term">Margin</div><div class="guide-desc">Thin margins provide less buffer against cost shocks.</div></div>
    </div>
  </div>

  <!-- 9. Drawdown -->
  <div class="guide-section">
    <div class="guide-head"><span>9.</span> Drawdown</div>
    <div class="guide-text">Drawdown measures how far the current price is below the 90-day high. A 20%+ drawdown is flagged as a warning even if other metrics look strong &mdash; it means the stock has already fallen significantly and the catalyst may have already passed, or downward pressure is ongoing.</div>
  </div>

  <!-- 10. EQ Verdict -->
  <div class="guide-section">
    <div class="guide-head"><span>10.</span> Earnings Quality (EQ) Verdict</div>
    <div class="guide-text">System 2 reads SEC EDGAR filings to assess how trustworthy a company&rsquo;s reported earnings are. The EQ verdict is a separate signal from the confidence score.</div>
    <div class="guide-grid">
      <div class="guide-card"><div class="guide-term" style="color:var(--up)">Supportive</div><div class="guide-desc">Earnings are reliable and cash-backed. EQ score &ge; 55.</div></div>
      <div class="guide-card"><div class="guide-term" style="color:var(--nt)">Neutral</div><div class="guide-desc">Earnings are acceptable but have concerns. EQ score 35&ndash;54.</div></div>
      <div class="guide-card"><div class="guide-term" style="color:var(--dn)">Weak</div><div class="guide-desc">Earnings are unreliable. EQ score &lt; 35.</div></div>
      <div class="guide-card"><div class="guide-term" style="color:var(--dn)">Risky</div><div class="guide-desc">Critical structural problem detected. Overrides all other tiers regardless of score.</div></div>
      <div class="guide-card"><div class="guide-term" style="color:var(--mist)">Unavailable</div><div class="guide-desc">No SEC data found for this ticker. Confidence is reduced when EQ is unavailable.</div></div>
    </div>
  </div>

  <!-- 11. Rotation Signal -->
  <div class="guide-section">
    <div class="guide-head"><span>11.</span> Rotation Signal</div>
    <div class="guide-text">System 3 detects whether money is actively rotating into or out of a sector. It is backward-looking: it confirms rotation already in progress, not a prediction of future rotation.</div>
    <div class="signal-row"><span class="signal-key">SUPPORT</span><span class="signal-desc">Sector flow supports acting now. Rotation is actively moving into this sector.</span></div>
    <div class="signal-row"><span class="signal-key nt">WAIT</span><span class="signal-desc">Neutral timing. Rotation is not yet favorable. Monitor before acting.</span></div>
    <div class="signal-row"><span class="signal-key dn">WEAKEN</span><span class="signal-desc">Sector flow is deteriorating. Money is rotating out. Proceed with caution.</span></div>
  </div>

  <!-- 12. What This System Cannot Do -->
  <div class="guide-section">
    <div class="guide-head"><span>12.</span> What This System Cannot Do</div>
    <div class="warn-box">
      <strong>Honest free-tier ceiling</strong>
      Free-tier APIs provide delayed, sampled, or limited-depth data. This system cannot access real-time tick data, institutional order flow, insider filings, earnings call transcripts, or premium fundamental databases. All values are best-effort approximations that may be stale by up to 15 minutes for price data and up to 1 day for filing data.
    </div>
    <div class="guide-text">Does not execute trades, recommend position sizes, set stop-losses, provide price targets, track open positions, or access any brokerage account. All outputs are research signals for human review only. Always verify findings through independent sources before making any financial decision. Past system signals are not indicative of future performance.</div>
  </div>

</div>
</div><!-- /.pages -->

<footer>
  <span>MRE // System</span> &middot; Free-tier data only &middot; Not investment advice &middot; Always verify before acting
</footer>

</body>
</html>
```

---

## VERIFICATION

After both fixes, confirm ALL of these:

- [ ] Regex scan prints `OK — no backslash-in-expression issues found`
- [ ] `grep -n "_EM" reports/dashboard_builder.py` shows the constant definition and multiple usages
- [ ] None of the 7 original lines contain `"\u2014"` inside `{}` any more
- [ ] `_EXP_T_JS = r"""` (raw string, not plain `"""`)
- [ ] `docs/guide.html` contains all 12 numbered sections (1 through 12)
- [ ] `docs/guide.html` uses the new design classes (`guide-section`, `guide-head`, `guide-card`, `thresh`, `sys-pill`, `scanlines`, `nav`, `brand-pulse`)
- [ ] `docs/guide.html` does NOT contain fake placeholder tickers
- [ ] No other files were touched
