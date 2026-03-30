# MRE — FIX PROMPT: CHART RACE CONDITION + GUIDE CONTENT
# Two targeted fixes. Read everything before touching anything.
# Do not touch any file not listed below.

---

## FIX 1 — dashboard_builder.py: rapid-click chart race condition

File: `reports/dashboard_builder.py`

### What is broken and why

When the user clicks an index pill while a slide animation is completing, the
following race occurs:

1. Slide animation finishes → `isAnimating = false` → a naked `setTimeout(onDone, 320)` is queued
2. User clicks another pill during that 320ms window
3. `isAnimating` is false so `toggleIdx` proceeds → starts a new slide/genie
4. The original 320ms timer fires → `buildIdxChart` runs for the OLD index
5. The new animation also calls `buildIdxChart` → two chart builds fire in sequence

The fix is a `pendingChartTimer` variable that tracks the 320ms delay and
cancels it when a new click arrives. This is the exact pattern used in the
reference template (`mre_updated.html`).

### Step 1 — Fix `_SLIDE_JS`

Find this exact line inside `_SLIDE_JS` (near the end of the function):

```python
      if(onDone) setTimeout(()=>onDone(),320);
```

Replace it with:

```python
      if(onDone) pendingChartTimer=setTimeout(()=>{pendingChartTimer=null;onDone();},320);
```

This stores the timer handle so it can be cancelled.

### Step 2 — Fix `_TOGGLE_IDX_JS`

Find this exact line inside `_TOGGLE_IDX_JS`:

```python
let currentIdx=null, isAnimating=false;
```

Replace it with:

```python
let currentIdx=null, isAnimating=false, pendingChartTimer=null;
```

Then find these two lines that appear at the top of the `toggleIdx` function
body (right after `if(isAnimating)return;`):

```python
  if(window._mreCharts&&window._mreCharts['idx-chart']){
    window._mreCharts['idx-chart'].destroy();delete window._mreCharts['idx-chart'];
  }
```

Replace them with:

```python
  if(pendingChartTimer){clearTimeout(pendingChartTimer);pendingChartTimer=null;}
  if(window._mreCharts&&window._mreCharts['idx-chart']){
    window._mreCharts['idx-chart'].destroy();delete window._mreCharts['idx-chart'];
  }
```

### Step 3 — Verify

After making changes, confirm both strings are present in the file:

```bash
grep -n "pendingChartTimer" reports/dashboard_builder.py
```

Must show at least 4 lines: the declaration, the clear in toggleIdx, the
assignment in animateSlide's completion, and the null-reset inside the timer.

---

## FIX 2 — docs/guide.html: replace content with full operational guide

File: `docs/guide.html`

The current guide has 4 abbreviated sections. Replace it with the full
8-section operational guide below. The HTML structure (nav, page wrapper,
CSS classes, footer) is preserved exactly — only the page content changes.

Replace the entire file contents with:

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
.signal-key { font-family: var(--ff-head); font-size: 10px; font-weight: 700; min-width: 140px; letter-spacing: 0.04em; padding-top: 2px; }
.signal-key.up { color: var(--up); }
.signal-key.dn { color: var(--dn); }
.signal-key.nt { color: var(--nt); }
.signal-key.pu { color: var(--pu-lt); }
.signal-desc { color: var(--slate); line-height: 1.7; font-size: 11px; }
.verdict-row { display: flex; gap: 12px; align-items: flex-start; padding: 8px 0; border-bottom: 1px solid var(--rim); }
.verdict-row:last-child { border-bottom: none; }
.verdict-badge { font-family: var(--ff-head); font-weight: 700; font-size: 9px; letter-spacing: 0.08em; min-width: 160px; padding-top: 3px; }
.vr-now   { color: var(--up); }
.vr-watch { color: var(--nt); }
.vr-skip  { color: var(--mist); }
.warn-box {
  background: rgba(155,89,255,0.05); border-left: 3px solid var(--pu);
  padding: 12px 16px; margin: 14px 0;
  font-size: 11px; color: var(--slate); line-height: 1.8;
}
.warn-box strong { display: block; margin-bottom: 6px; color: var(--pu-lt); font-family: var(--ff-head); font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; }
.thresh {
  display: flex; align-items: center; gap: 14px;
  padding: 10px 16px; background: var(--l1); border: 1px solid var(--rim); border-top: none;
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
.priority-table { width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 14px; }
.priority-table th { font-family: var(--ff-head); font-size: 9px; letter-spacing: 0.08em; color: var(--mist); text-transform: uppercase; text-align: left; padding: 6px 12px; border-bottom: 1px solid var(--rim2); }
.priority-table td { padding: 8px 12px; border-bottom: 1px solid var(--rim); color: var(--slate); vertical-align: top; }
.priority-table td:first-child { color: var(--pu-lt); font-family: var(--ff-head); font-size: 9px; letter-spacing: 0.06em; white-space: nowrap; }
.priority-table tr:last-child td { border-bottom: none; }
</style>
</head>
<body>
<div class="scanlines"></div>

<!-- NAV: MUST MATCH _nav_html('guide') OUTPUT EXACTLY -->
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
  <div class="pg-sub">How this system works, what every signal means, and how to use the AI prompt to make decisions.</div>

  <!-- 01. How the system works -->
  <div class="guide-section">
    <div class="guide-head"><span>01</span> How the System Works</div>
    <div class="guide-text">This is a zero-cost automated stock research engine. It runs four times per trading day &mdash; 9:45, 11:45, 13:45, and 16:00 ET &mdash; and can also be triggered manually for research on specific tickers. No paid APIs, no machine learning, no trading logic. It collects public data, scores it, and produces a ranked list of screening candidates for human decision-making.</div>
    <div style="margin-bottom:14px">
      <span class="sys-pill sp1">System 1 &middot; Market Signal</span>
      <span class="sys-pill sp2">System 2 &middot; Earnings Quality</span>
      <span class="sys-pill sp3">System 3 &middot; Sector Rotation</span>
    </div>
    <div class="guide-text">Three analytical layers run in sequence on every candidate. System 1 scores momentum, trend quality, volume, risk, and financial health. System 2 pulls SEC EDGAR filings to measure whether earnings are cash-backed across 7 modules. System 3 measures sector-level momentum to determine whether capital flow supports or opposes entering now.</div>
    <div class="guide-text">After all three score a candidate, a Combined Reading synthesises the signals into an alignment verdict and a conclusion. The final output is a full report with an AI Research Prompt &mdash; a pre-built block you paste into any AI assistant for entry and exit analysis. The system never tells you to buy or sell. It identifies candidates and organises data so you can make an informed decision.</div>
  </div>

  <!-- 02. System 1 -->
  <div class="guide-section">
    <div class="guide-head"><span>02</span> System 1 &mdash; Market Signal Analysis</div>
    <div class="guide-text">System 1 is the primary screening layer. It evaluates each candidate across momentum, trend stability, volume behaviour, financial health, and risk. The output is a confidence score (0&ndash;100) and a market verdict.</div>

    <div class="guide-text" style="color:var(--snow);margin-bottom:6px;">Verdict Labels</div>
    <div class="verdict-row"><span class="verdict-badge vr-now">RESEARCH NOW</span><span class="signal-desc">Confidence &ge; 70 and risk &le; 35. Strong multi-signal alignment. Highest priority.</span></div>
    <div class="verdict-row"><span class="verdict-badge vr-watch">WATCH</span><span class="signal-desc">Confidence &ge; 55, or low risk with confidence &ge; 45. Partial signals. Worth monitoring.</span></div>
    <div class="verdict-row" style="margin-bottom:16px"><span class="verdict-badge vr-skip">SKIP</span><span class="signal-desc">Signals too weak or conflicting. Not worth research time at this stage.</span></div>

    <div class="guide-text" style="color:var(--snow);margin-bottom:6px;">Confidence Score</div>
    <div class="guide-text">A composite 0&ndash;100 metric. Not a probability of profit. Three sub-components: Risk (lower is safer &mdash; composite of debt, volatility, liquidity, EPS stability, drawdown, margin), Opportunity (higher is better &mdash; trend strength and momentum vs. current market regime), and Signal Agreement (how many of the analysis modules agree on direction &mdash; multiplicative, so one contradiction significantly reduces the score).</div>
    <div class="thresh" style="border-top:1px solid var(--rim)">
      <div class="thresh-bar" style="background:var(--up)"></div>
      <div class="thresh-label">Strong alignment &middot; Highest priority</div><div class="thresh-range">85 &ndash; 100</div>
    </div>
    <div class="thresh">
      <div class="thresh-bar" style="background:var(--up)" style="opacity:0.7"></div>
      <div class="thresh-label">Most signals favorable &middot; Verify before acting</div><div class="thresh-range">70 &ndash; 84</div>
    </div>
    <div class="thresh">
      <div class="thresh-bar" style="background:var(--nt)"></div>
      <div class="thresh-label">Passes screening &middot; Needs additional research</div><div class="thresh-range">60 &ndash; 69</div>
    </div>
    <div class="thresh">
      <div class="thresh-bar" style="background:var(--dn)"></div>
      <div class="thresh-label">Weak signal &middot; Significant caution required</div><div class="thresh-range">Below 60</div>
    </div>

    <div class="guide-text" style="color:var(--snow);margin-top:18px;margin-bottom:6px;">Timing Quality (Trend Stage)</div>
    <div class="guide-text">Trend stage is classified from the 3-month return. This is critical &mdash; a stock in a late-stage trend is a worse entry than a weaker stock in an early-stage trend, even if all other signals look good.</div>
    <div class="signal-row"><span class="signal-key up">EARLY TREND</span><span class="signal-desc">3M return &lt; 15%. Momentum building. Best entry window.</span></div>
    <div class="signal-row"><span class="signal-key nt">MID TREND</span><span class="signal-desc">3M return 15&ndash;30%. Trend established. Acceptable entry.</span></div>
    <div class="signal-row" style="margin-bottom:16px"><span class="signal-key dn">LATE TREND</span><span class="signal-desc">3M return &gt; 30%. Elevated pullback risk. Requires strong justification from all other signals. Maximum allowed entry is WAIT &mdash; never BUY NOW.</span></div>

    <div class="guide-text" style="color:var(--snow);margin-bottom:6px;">Volume</div>
    <div class="signal-row"><span class="signal-key up">Elevated bullish</span><span class="signal-desc">High volume on up days &mdash; institutional buying signal.</span></div>
    <div class="signal-row"><span class="signal-key dn">Elevated bearish</span><span class="signal-desc">High volume on down days &mdash; distribution or panic signal.</span></div>
    <div class="signal-row"><span class="signal-key nt">Unusually high</span><span class="signal-desc">Volume &ge; 2&times; average. Something is drawing attention &mdash; investigate why.</span></div>
    <div class="signal-row" style="margin-bottom:16px"><span class="signal-key nt">Low activity</span><span class="signal-desc">Volume &lt; 0.8&times; average. Less conviction behind any price move.</span></div>

    <div class="guide-text" style="color:var(--snow);margin-bottom:6px;">Financial Health</div>
    <div class="guide-grid">
      <div class="guide-card"><div class="guide-term">Profit Margin</div><div class="guide-desc">Cents kept per $1 of revenue. Compare within sector only.</div></div>
      <div class="guide-card"><div class="guide-term">ROIC</div><div class="guide-desc">Return on Invested Capital. Above 15% = excellent. 8&ndash;15% = solid. Below 8% = weak economics.</div></div>
      <div class="guide-card"><div class="guide-term">Debt-to-Equity</div><div class="guide-desc">Below 0.3 = minimal debt. Above 1.5 = elevated. Above 2.5 = high leverage risk. Above 2.5 is filtered out.</div></div>
      <div class="guide-card"><div class="guide-term">Operating Cash Flow</div><div class="guide-desc">Positive = real cash generation. Negative OCF = always excluded regardless of other signals.</div></div>
      <div class="guide-card"><div class="guide-term">Drawdown</div><div class="guide-desc">Distance from 90-day high. Above 20% flagged as warning &mdash; price already fell significantly.</div></div>
    </div>
  </div>

  <!-- 03. System 2 -->
  <div class="guide-section">
    <div class="guide-head"><span>03</span> System 2 &mdash; Earnings Quality Analysis</div>
    <div class="guide-text">System 2 pulls raw financial data directly from SEC EDGAR filings and measures whether a company&rsquo;s earnings are reliable, cash-backed, and sustainable. It does not use estimated or screened data &mdash; only filed quarterly reports. A minimum of 6 quarters is required to run.</div>

    <div class="guide-text" style="color:var(--snow);margin-bottom:6px;">EQ Verdict</div>
    <div class="guide-grid">
      <div class="guide-card"><div class="guide-term" style="color:var(--up)">Supportive</div><div class="guide-desc">PASS &mdash; Earnings are reliable and cash-backed. Fundamentals support the market signal.</div></div>
      <div class="guide-card"><div class="guide-term" style="color:var(--nt)">Neutral</div><div class="guide-desc">WATCH &mdash; Earnings are acceptable but have concerns. Not a blocker, but worth monitoring.</div></div>
      <div class="guide-card"><div class="guide-term" style="color:var(--dn)">Weak</div><div class="guide-desc">FAIL &mdash; Earnings are unreliable. Reduces conviction significantly regardless of market signal.</div></div>
      <div class="guide-card"><div class="guide-term" style="color:var(--dn)">Risky</div><div class="guide-desc">FATAL FLAW &mdash; Critical structural problem. Overrides all other verdicts. Avoid.</div></div>
      <div class="guide-card"><div class="guide-term" style="color:var(--mist)">Unavailable</div><div class="guide-desc">No SEC data found. Cannot validate &mdash; do not assume positive or negative. Confidence is reduced.</div></div>
    </div>

    <div class="guide-text" style="color:var(--snow);margin-bottom:6px;">The 7 Modules</div>
    <div class="guide-grid">
      <div class="guide-card"><div class="guide-term">Accruals</div><div class="guide-desc">Gap between reported earnings and actual cash flow. Large positive accruals = earnings may not reflect real cash.</div></div>
      <div class="guide-card"><div class="guide-term">Cash Conversion</div><div class="guide-desc">How consistently earnings convert to operating cash. Low conversion = quality concern.</div></div>
      <div class="guide-card"><div class="guide-term">Revenue Quality</div><div class="guide-desc">Revenue growth consistency and relationship to receivables. Receivables growing faster than revenue = warning.</div></div>
      <div class="guide-card"><div class="guide-term">FCF Sustainability</div><div class="guide-desc">Free cash flow vs. capex and investment phase. Measures whether cash generation is sustainable.</div></div>
      <div class="guide-card"><div class="guide-term">Earnings Consistency</div><div class="guide-desc">EPS stability across quarters. High variance = unreliable earnings base for valuation.</div></div>
      <div class="guide-card"><div class="guide-term">Long-Term Trends</div><div class="guide-desc">Multi-year momentum in operating cash flow, margins, and capex. Detects structural improvement or deterioration.</div></div>
      <div class="guide-card"><div class="guide-term">Dividend Stability</div><div class="guide-desc">For dividend-paying stocks: consistency and coverage ratio. A dividend cut triggers the RISKY fatal flaw override.</div></div>
    </div>
    <div class="warn-box">
      <strong>Why UNAVAILABLE is common</strong>
      EDGAR requires matching ticker to CIK, then finding correct XBRL tags across multiple filing types. Some tickers have incomplete filings, non-standard tags, or insufficient quarterly history. When data is unavailable, System 2 is skipped entirely &mdash; it does not penalise the candidate, but it also cannot validate it.
    </div>
  </div>

  <!-- 04. System 3 -->
  <div class="guide-section">
    <div class="guide-head"><span>04</span> System 3 &mdash; Sector Rotation Analysis</div>
    <div class="guide-text">System 3 measures whether a candidate&rsquo;s sector is currently receiving capital inflows or outflows. A strong stock in a deteriorating sector faces a headwind. A strong stock in an accelerating sector has a tailwind. Timing matters as much as stock quality.</div>

    <div class="guide-text" style="color:var(--snow);margin-bottom:6px;">Timing Signal</div>
    <div class="signal-row"><span class="signal-key up">SUPPORT</span><span class="signal-desc">Sector flow supports acting now. Capital is rotating in. Timing is favorable.</span></div>
    <div class="signal-row"><span class="signal-key nt">WAIT</span><span class="signal-desc">Neutral timing. Not yet attracting strong inflows. A better entry may come.</span></div>
    <div class="signal-row" style="margin-bottom:16px"><span class="signal-key dn">WEAKEN</span><span class="signal-desc">Sector flow is deteriorating. Capital is rotating out. Timing risk is elevated.</span></div>

    <div class="guide-text">For commodity-sensitive sectors (energy, materials), the system also tracks 5-day commodity price moves. If the sector is rising while the underlying commodity is falling, this is a negative divergence &mdash; sector strength may not be sustainable.</div>
  </div>

  <!-- 05. Combined Reading -->
  <div class="guide-section">
    <div class="guide-head"><span>05</span> Combined Reading</div>
    <div class="guide-text">After all three systems score a candidate, the Combined Reading synthesises them into a single alignment verdict and a deterministic conclusion sentence.</div>

    <div class="signal-row"><span class="signal-key up">ALIGNED</span><span class="signal-desc">All three systems agree. Highest conviction setup.</span></div>
    <div class="signal-row"><span class="signal-key nt">PARTIAL</span><span class="signal-desc">Mixed signals &mdash; two systems agree, one does not. Proceed with caution.</span></div>
    <div class="signal-row" style="margin-bottom:16px"><span class="signal-key dn">CONFLICT</span><span class="signal-desc">Systems disagree. The conflict must be understood before any action.</span></div>

    <div class="guide-text" style="color:var(--snow);margin-bottom:6px;">Decision Priority Order</div>
    <div class="guide-text">When signals conflict, the system and the AI prompt follow this hierarchy:</div>
    <table class="priority-table">
      <thead><tr><th>Priority</th><th>Signal</th><th>Why it ranks here</th></tr></thead>
      <tbody>
        <tr><td>1 &mdash; Highest</td><td style="color:var(--snow)">Timing quality (trend stage)</td><td>A late-stage trend cannot result in BUY NOW regardless of other signals.</td></tr>
        <tr><td>2</td><td style="color:var(--snow)">Market verdict (System 1)</td><td>Primary directional signal from the full scoring pipeline.</td></tr>
        <tr><td>3</td><td style="color:var(--snow)">Sector rotation (System 3)</td><td>Confirms or weakens the timing of entry.</td></tr>
        <tr><td>4</td><td style="color:var(--snow)">Earnings quality (System 2)</td><td>Validates or blocks conviction. RISKY overrides everything above it.</td></tr>
      </tbody>
    </table>
  </div>

  <!-- 06. The AI Prompt -->
  <div class="guide-section">
    <div class="guide-head"><span>06</span> The AI Research Prompt</div>
    <div class="guide-text">Every run generates an AI Research Prompt &mdash; a structured block of text containing all automated research data for every candidate in that run. Copy it and paste it into any AI assistant (Claude, ChatGPT, Gemini) to get entry analysis, exit logic, risk assessment, and a final verdict. No additional instructions are needed &mdash; the prompt is self-contained.</div>
    <div class="guide-text">This is the last 5% of the process. The system handles data collection, scoring, and structuring. The AI assistant handles interpretation and plain-English reasoning. You make the final call.</div>

    <div class="guide-text" style="color:var(--snow);margin-bottom:6px;">How to Access It</div>
    <div class="guide-text">Open any run entry on the Archive page. Click the <span style="color:var(--mg)">&#x2389; Copy Prompt</span> button to copy the full prompt to clipboard. Or click the report link to open the full report page &mdash; it includes the same copy button at the bottom.</div>

    <div class="guide-text" style="color:var(--snow);margin-bottom:6px;">What the Prompt Contains</div>
    <div class="guide-grid">
      <div class="guide-card"><div class="guide-term">Rules block</div><div class="guide-desc">Timing rules, decision hierarchy, BUY NOW gate, conflict definitions &mdash; pre-loaded so the AI reasons consistently.</div></div>
      <div class="guide-card"><div class="guide-term">System vocabulary</div><div class="guide-desc">All signal labels and exact meanings so the AI interprets RESEARCH NOW, SUPPORT, ALIGNED, LATE TREND correctly.</div></div>
      <div class="guide-card"><div class="guide-term">Global context</div><div class="guide-desc">Date, slot, market regime, breadth, index values, and 5-day commodity moves.</div></div>
      <div class="guide-card"><div class="guide-term">Per-candidate data</div><div class="guide-desc">Price, confidence, trend (1M/3M/6M), volume, EQ score, rotation signal, combined reading, strengths, and warnings.</div></div>
    </div>

    <div class="guide-text" style="color:var(--snow);margin-bottom:6px;">Hard Rules Enforced in the Prompt</div>
    <div class="warn-box">
      <strong>BUY NOW gate</strong>
      BUY NOW is only allowed if ALL of the following are true: Timing = EARLY TREND or MID TREND &middot; Market verdict = RESEARCH NOW &middot; Rotation = SUPPORT &middot; No major signal conflicts.<br><br>
      LATE TREND override: even with RESEARCH NOW + SUPPORT + no conflicts, the maximum allowed entry is WAIT &mdash; never BUY NOW.<br><br>
      UNAVAILABLE earnings blocks BUY NOW unless all other signals are strong and timing is EARLY or MID TREND.
    </div>
  </div>

  <!-- 07. The Archive -->
  <div class="guide-section">
    <div class="guide-head"><span>07</span> The Archive</div>
    <div class="guide-text">The Archive page stores every run the system has produced, organised by week. Each week is a collapsible section. Each run shows the timestamp, slot, candidate count, verdict counts (RESEARCH NOW / WATCH / SKIP), and market regime. Expanding a run shows the candidate table with the AI prompt copy button and a link to the full report.</div>

    <div class="signal-row"><span class="signal-key pu">SCHEDULED</span><span class="signal-desc">Automatic run at one of the four daily slots.</span></div>
    <div class="signal-row" style="margin-bottom:16px"><span class="signal-key pu">MANUAL RUN</span><span class="signal-desc">User-triggered run on specific tickers. Useful for investigating stocks outside the normal pipeline.</span></div>

    <div class="guide-text">Retention: up to 10 runs per week, 12 weeks of history. Full report files are pruned after 90 days by the weekly cleanup script.</div>
  </div>

  <!-- 08. Limitations -->
  <div class="guide-section">
    <div class="guide-head"><span>08</span> What This System Cannot Do</div>
    <div class="warn-box">
      <strong>Free-tier data ceiling</strong>
      Free-tier APIs provide delayed, sampled, or limited-depth data. This system cannot access real-time tick data, institutional order flow, insider filings, earnings call transcripts, Level 2 order books, or premium fundamental databases. All values are best-effort approximations that may be stale by minutes to hours.
    </div>
    <div class="guide-grid">
      <div class="guide-card"><div class="guide-term">No predictions</div><div class="guide-desc">Cannot predict whether a stock will go up or down. Identifies candidates that pass thresholds. Past signals do not indicate future performance.</div></div>
      <div class="guide-card"><div class="guide-term">EDGAR coverage gaps</div><div class="guide-desc">System 2 requires 6+ quarters of filed XBRL data. Smaller companies, recent IPOs, or foreign-listed stocks often show UNAVAILABLE. Data issue, not a signal.</div></div>
      <div class="guide-card"><div class="guide-term">Rotation history depth</div><div class="guide-desc">System 3 accuracy improves with more historical runs. Early in the system&rsquo;s life, rotation speed calculations have limited data points.</div></div>
      <div class="guide-card"><div class="guide-term">No execution</div><div class="guide-desc">Does not execute trades, recommend position sizes, set stop-losses, provide price targets, track open positions, or access any brokerage account.</div></div>
    </div>
    <div class="guide-text">All outputs are research signals for human review only. Always verify findings through independent sources before making any financial decision.</div>
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

After both fixes:

- [ ] `grep -n "pendingChartTimer" reports/dashboard_builder.py` shows at least 4 lines
- [ ] The declaration line reads: `let currentIdx=null, isAnimating=false, pendingChartTimer=null;`
- [ ] The clear block in `toggleIdx` reads: `if(pendingChartTimer){clearTimeout(pendingChartTimer);pendingChartTimer=null;}`
- [ ] The timer assignment in `_SLIDE_JS` reads: `pendingChartTimer=setTimeout(()=>{pendingChartTimer=null;onDone();},320);`
- [ ] `docs/guide.html` contains all 8 numbered sections (01 through 08)
- [ ] `docs/guide.html` nav matches `_nav_html('guide')` structure exactly (Guide tab has `class="tab on"`)
- [ ] No other files were touched
