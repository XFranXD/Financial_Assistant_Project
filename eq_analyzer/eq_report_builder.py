"""
report_builder.py
Report formatting for System 2 EQ results — v3.0 output structure.

Generates two output formats per ticker:
    build_text_block()  → compact plain-text for email
    build_html_block()  → rich HTML for GitHub Pages dashboard

Text output order:
    score → label modifier → key strengths → reliability → key warnings → verdict

HTML output order:
    score → reliability → key warnings →
    module breakdown (7 rows + tooltip on hover) → notes → verdict

Module tooltip behavior: each module row has a title= attribute.
CSS handles hover display — no JavaScript required.

Module display order in HTML breakdown is fixed (same order as COMPOSITE_MODULES).
N/A modules render in muted grey (#666666).
Skipped modules render in muted grey with "INSUFFICIENT DATA" label.

Color map:
    STRONG     #00ff88
    ACCEPTABLE #88ddff
    WEAK       #ffaa00
    POOR       #ff4444

Trend arrows:
    up   → ↑ (green)
    down → ↓ (red)
    flat → → (grey)

Debug logging: [REPORT] prefix
"""

import logging

logger = logging.getLogger(__name__)

# ---------- Static lookup tables ----------

MODULE_ORDER = [
    "cash_conversion", "accruals", "revenue_quality", "long_term_trends",
    "fcf_sustainability", "earnings_consistency", "dividend_stability"
]

MODULE_DISPLAY_NAMES = {
    "cash_conversion":      "Cash Conversion          23%",
    "accruals":             "Accruals Quality          19%",
    "revenue_quality":      "Revenue Quality           16%",
    "long_term_trends":     "Long-Term Trends          16%",
    "fcf_sustainability":   "FCF Sustainability        11%",
    "earnings_consistency": "Earnings Consistency      10%",
    "dividend_stability":   "Dividend Stability         5%"
}

BAND_COLORS = {
    "STRONG":     "#00ff88",
    "ACCEPTABLE": "#88ddff",
    "WEAK":       "#ffaa00",
    "POOR":       "#ff4444"
}

BAND_MEANINGS = {
    "STRONG":     "Earnings are well-backed by real cash generation across all signals.",
    "ACCEPTABLE": "Earnings are mostly cash-backed. Minor areas to monitor.",
    "WEAK":       "Notable gaps between reported earnings and cash metrics. Caution warranted.",
    "POOR":       "Significant accounting-to-cash divergence. Verify independently."
}

TREND_ARROWS = {"up": "↑", "down": "↓", "flat": "→"}
TREND_COLORS = {"up": "#00ff88", "down": "#ff4444", "flat": "#888888"}

TIER_HEADERS = {
    "PASS":  "✓ PASS",
    "WATCH": "⚡ WATCH  (human review recommended)",
    "FAIL":  "✗ FAIL",
}

# WARNING_WEIGHTS imported from eq_scorer to keep weights in one place
from eq_analyzer.eq_scorer import WARNING_WEIGHTS


def _ordinal(n: int) -> str:
    """Returns correct ordinal suffix: 1st, 2nd, 3rd, 4th, 11th, 12th, 13th, 21st..."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

MODULE_TOOLTIPS = {
    "cash_conversion": (
        "What it measures: Whether net income is converting to real operating cash flow. "
        "Why it matters: A company can report growing profits while actual cash generation shrinks — "
        "a classic early warning sign. High score = cash and profit moving together."
    ),
    "accruals": (
        "What it measures: The portion of reported earnings made up of non-cash accounting entries (accruals). "
        "Why it matters: High accruals relative to total assets is one of the strongest known predictors "
        "of future earnings deterioration (Sloan 1996). Low score = large gap between reported profit and cash reality."
    ),
    "revenue_quality": (
        "What it measures: Whether revenue growth is backed by actual cash collections or inflated by "
        "extending credit to customers. Tracks accounts receivable growth vs revenue growth, "
        "and days-sales-outstanding trend. High score = revenue is being collected, not just booked."
    ),
    "long_term_trends": (
        "What it measures: Whether the business is genuinely improving, stable, or deteriorating across "
        "four dimensions over the full available history: revenue trend, margin trend, debt trend, FCF trend. "
        "Why it matters: A business can look healthy today while quietly deteriorating over 2-3 years. "
        "High score = business trajectory is positive across all measured dimensions."
    ),
    "earnings_consistency": (
        "What it measures: Stability and predictability of net income across 8 quarters. "
        "Detects both high volatility and steady decline. "
        "Why it matters: Erratic or declining earnings are harder to model and carry higher fundamental risk. "
        "High score = smooth, stable earnings trajectory."
    ),
    "fcf_sustainability": (
        "What it measures: Whether the business generates more free cash than it consumes to sustain itself. "
        "FCF = Operating Cash Flow minus Capital Expenditures. "
        "Why it matters: A company spending more to operate than it generates cannot fund itself indefinitely. "
        "High score = self-funding business with healthy FCF margin."
    ),
    "dividend_stability": (
        "What it measures: Whether the company's dividend policy is financially sustainable. "
        "Tracks dividend growth consistency, payout ratio, and whether any cuts occurred in the last 3 years. "
        "Why it matters: Dividend cuts are one of the strongest real-world signals of financial stress — "
        "management resists them until there is no other option. N/A = company does not pay dividends."
    )
}


def build_text_block(eq_result: dict, module_results: list) -> str:
    """
    Compact plain-text EQ block for email — v3.0 output structure.
    Order: score → label modifier → key strengths → reliability → key warnings → verdict
    """
    logger.debug(f"[REPORT] Building text block for {eq_result['ticker']}")

    # 6.1 Tier-aware header
    pass_tier = eq_result.get("pass_tier", "PASS" if eq_result["passed"] else "FAIL")
    status = TIER_HEADERS.get(pass_tier, "✓ PASS")

    lines = []
    lines.append("━" * 52)
    lines.append(f"EARNINGS QUALITY CHECK  {status}")
    lines.append(f"SEC EDGAR · {eq_result['filing_date']} · {eq_result['filing_age_days']} days old")
    lines.append("━" * 52)

    # 1. EQ Score — combined modifier on one line
    if eq_result["total_modifier"] > 0:
        lines.append(
            f"EQ Score: {eq_result['eq_score_raw']} → {eq_result['eq_score_final']} "
            f"({eq_result['modifier_detail']}) / 100  →  {eq_result['band_label']}"
        )
    else:
        lines.append(f"EQ Score: {eq_result['eq_score_final']} / 100  →  {eq_result['band_label']}")

    band = eq_result["band_label"]
    lines.append(f"  {band}: {BAND_MEANINGS.get(band, '')}")

    # 6.2 Label modifier (ADJUSTED / CAUTION)
    if eq_result.get("eq_modifier") == "ADJUSTED":
        lines.append(f"  → Label adjusted to {eq_result.get('eq_label','')} due to active risk signals")
    elif eq_result.get("eq_modifier") == "CAUTION":
        lines.append(f"  → CAUTION: one moderate risk signal detected")

    # 6.2 Final classification
    lines.append(f"Final Classification:  {eq_result.get('final_classification', 'REVIEW')}")

    # 6.2 Constraint summary (only when constraints fired and delta >= 3)
    constraint_log = eq_result.get("constraint_log", [])
    if constraint_log:
        dominant = next((c for c in constraint_log if c.get("dominant")), None)
        if dominant and abs(dominant.get("delta", 0)) >= 3:
            name_readable = dominant["name"].replace("_", " ").title()
            lines.append(
                f"  Score constrained by: {name_readable} "
                f"(Δ{dominant['delta']:.1f} pts) — {dominant['reason']}"
            )
        fired_names = list({c["name"] for c in constraint_log
                            if abs(c.get("delta", 0)) >= 3})
        if len(fired_names) > 1 and dominant:
            others = [n for n in fired_names if n != dominant["name"]]
            if others:
                lines.append(
                    f"  Additional constraints: "
                    f"{', '.join(n.replace('_', ' ').title() for n in others)}"
                )

    # 6.2 Fatal flaw
    if eq_result.get("fatal_flaw_reason"):
        lines.append(f"⛔ FATAL FLAW: {eq_result['fatal_flaw_reason']}")

    # Section 7: Batch percentile (appended if present)
    pct = eq_result.get("eq_percentile")
    if pct is not None:
        lines.append(
            f"Batch Percentile:      {_ordinal(pct)}  "
            f"(scores higher than {pct}% of this batch)"
        )

    lines.append("")

    # 6.3 / 11.1 Reliability line — with N/A count (Issue 9)
    working         = len(eq_result.get("module_scores", {}))
    pct_rel         = round(eq_result.get("data_reliability", 0) * 100)
    results_by_name = {r["module_name"]: r for r in module_results}

    all_modules = [
        "cash_conversion", "accruals", "revenue_quality", "long_term_trends",
        "fcf_sustainability", "earnings_consistency", "dividend_stability"
    ]

    missing  = []
    na_count = 0
    for m in all_modules:
        if m not in eq_result.get("module_scores", {}):
            result = results_by_name.get(m)
            if result and result.get("not_applicable"):
                na_count += 1
            else:
                missing.append(m.replace("_", " "))

    executed_note = f"{working}/7"
    if na_count > 0:
        executed_note += f"  ({na_count} N/A)"
    if missing:
        executed_note += f"  missing: {', '.join(missing)}"

    confidence    = eq_result.get("data_confidence", "")
    critical_warn = " ⚠ CRITICAL METRIC MISSING" if eq_result.get("critical_metrics_missing") else ""
    lines.append(
        f"Data reliability: {pct_rel}%  →  {confidence}  "
        f"(modules executed: {executed_note}){critical_warn}"
    )

    # Score confidence (only when not HIGH)
    score_conf = eq_result.get("score_confidence", "")
    if score_conf and score_conf != "HIGH":
        lines.append(f"  Score confidence: {score_conf}  (module scores show internal variance)")

    lines.append("")

    # 11.2 Key Strengths block before Key Warnings
    top_strengths = eq_result.get("top_strengths", [])
    if top_strengths:
        lines.append("Key Strengths:")
        for strength in top_strengths:
            lines.append(f"  ✓ {strength}")
        lines.append("")

    # 11.2 Key Warnings — always use structured warnings list, sorted by weight
    warnings = eq_result.get("warnings", [])
    if warnings:
        lines.append("Key Warnings:")
        sorted_warnings = sorted(
            warnings,
            key=lambda w: WARNING_WEIGHTS.get(w["type"], 2),
            reverse=True
        )
        for w in sorted_warnings:
            severity_label = "[HIGH]  " if w["severity"] == "major" else "[MEDIUM]"
            lines.append(f"  {severity_label} {w['message']}")
        lines.append("")

    # Verdict
    lines.append(f"Verdict: {eq_result['verdict_sentence']}")
    lines.append("━" * 52)

    return "\n".join(lines)


def build_html_block(eq_result: dict, module_results: list) -> str:
    """
    Rich HTML EQ block for GitHub Pages dashboard.
    Each module row has a title= tooltip. N/A rows render muted.
    """
    logger.debug(f"[REPORT] Building rich HTML block for {eq_result['ticker']}")

    results_by_name = {r["module_name"]: r for r in module_results}

    # 6.1 Tier-aware header
    pass_tier    = eq_result.get("pass_tier", "PASS" if eq_result["passed"] else "FAIL")
    status_color = {"PASS": "#00ff88", "WATCH": "#ffaa00", "FAIL": "#ff4444"}.get(pass_tier, "#00ff88")
    status_text  = TIER_HEADERS.get(pass_tier, "✓ PASS")

    band_color   = BAND_COLORS.get(eq_result["band_label"], "#ffffff")
    band_meaning = BAND_MEANINGS.get(eq_result["band_label"], "")

    # Score display
    if eq_result["total_modifier"] > 0:
        score_display = (
            f'{eq_result["eq_score_raw"]} → '
            f'<strong>{eq_result["eq_score_final"]}</strong> '
            f'({eq_result["modifier_detail"]})'
        )
    else:
        score_display = f'<strong>{eq_result["eq_score_final"]}</strong>'

    # 6.3 Data reliability display
    pct = round(eq_result["data_reliability"] * 100)
    working = len(eq_result["module_scores"])
    rel_color = "#00ff88" if pct >= 90 else ("#ffaa00" if pct >= 70 else "#ff4444")
    critical_html = (
        ' <span style="color:#ff4444">⚠ CRITICAL METRIC MISSING</span>'
        if eq_result.get("critical_metrics_missing") else ""
    )
    confidence = eq_result.get("data_confidence", "")

    # Identify missing modules
    all_modules = [
        "cash_conversion", "accruals", "revenue_quality", "long_term_trends",
        "fcf_sustainability", "earnings_consistency", "dividend_stability"
    ]
    missing = []
    for m in all_modules:
        result = results_by_name.get(m)
        if m not in eq_result.get("module_scores", {}):
            if not (result and result.get("not_applicable")):
                missing.append(m.replace("_", " "))
    missing_html = f" · missing: {', '.join(missing)}" if missing else ""

    reliability_html = (
        f'<div class="eq-reliability" style="color:{rel_color}">'
        f'Data reliability: {pct}% &nbsp;·&nbsp; {confidence} &nbsp;·&nbsp; Modules: {working}/7{missing_html}{critical_html}'
        f'</div>'
    )

    # 11.2 Key Strengths HTML
    top_strengths = eq_result.get("top_strengths", [])
    strengths_html = ""
    if top_strengths:
        strength_items = "".join(f"<li>✓ {s}</li>" for s in top_strengths)
        strengths_html = f"""
    <div class="eq-top-strengths">
        <span class="eq-strengths-label">Key Strengths:</span>
        <ul class="eq-strengths-list">{strength_items}</ul>
    </div>"""

    # 11.2 Key Warnings HTML (sorted by weight)
    warnings  = eq_result.get("warnings", [])
    top_risks = eq_result.get("top_risks", [])
    risks_html = ""
    if warnings:
        sorted_warnings = sorted(
            warnings,
            key=lambda w: WARNING_WEIGHTS.get(w["type"], 2),
            reverse=True
        )
        risk_items = ""
        for w in sorted_warnings:
            sev_label = "[HIGH]" if w["severity"] == "major" else "[MEDIUM]"
            sev_color = "#ff4444" if w["severity"] == "major" else "#ffaa00"
            risk_items += f'<li><span style="color:{sev_color}">{sev_label}</span> {w["message"]}</li>'
        risks_html = f"""
    <div class="eq-top-risks">
        <span class="eq-risks-label">Key Warnings:</span>
        <ul class="eq-risks-list">{risk_items}</ul>
    </div>"""
    elif top_risks:
        risk_items = "".join(f"<li>{r}</li>" for r in top_risks)
        risks_html = f"""
    <div class="eq-top-risks">
        <span class="eq-risks-label">Key Warnings:</span>
        <ul class="eq-risks-list">{risk_items}</ul>
    </div>"""

    # Module rows with arrows, tooltips, and N/A / UNKNOWN states
    module_rows_html = ""
    for module_name in MODULE_ORDER:
        display = MODULE_DISPLAY_NAMES[module_name]
        result  = results_by_name.get(module_name)

        if result and result.get("not_applicable"):
            module_rows_html += f"""
        <div class="eq-module-row eq-module-na">
            <span class="eq-module-score" style="color:#666666">N/A</span>
            <span class="eq-module-arrow" style="color:#666666">–</span>
            <span class="eq-module-name" style="color:#666666">{display}</span>
            <span class="eq-module-desc" style="color:#666666">Not applicable — does not pay dividends</span>
        </div>"""
        elif result and result.get("unknown"):
            module_rows_html += f"""
        <div class="eq-module-row eq-module-unknown">
            <span class="eq-module-score" style="color:#ffaa00">?</span>
            <span class="eq-module-arrow" style="color:#ffaa00">–</span>
            <span class="eq-module-name" style="color:#ffaa00">{display}</span>
            <span class="eq-module-desc" style="color:#ffaa00">{result.get("plain_english", "Data unavailable")}</span>
        </div>"""
        elif module_name in eq_result["module_scores"]:
            s           = eq_result["module_scores"][module_name]
            flag        = result.get("flag") if result else None
            plain       = result.get("plain_english", "") if result else ""
            trend       = result.get("trend", "flat") if result else "flat"
            score_color = BAND_COLORS.get(result.get("label", ""), "#ffffff") if result else "#ffffff"
            arrow       = TREND_ARROWS[trend]
            arrow_color = TREND_COLORS[trend]
            flag_html   = (
                f'<span class="eq-flag-inline"> ⛔ {flag}</span>' if flag else ""
            )
            base_tooltip = MODULE_TOOLTIPS.get(module_name, "")
            full_tooltip = f"{base_tooltip} | This candidate: {plain}"
            safe_tooltip = full_tooltip.replace('"', "&quot;").replace("'", "&#39;")
            module_rows_html += f"""
        <div class="eq-module-row" title="{safe_tooltip}">
            <span class="eq-module-score" style="color:{score_color}">{s:.0f}</span>
            <span class="eq-module-arrow" style="color:{arrow_color}">{arrow}</span>
            <span class="eq-module-name">{display}{flag_html}</span>
            <span class="eq-module-desc">{plain}</span>
        </div>"""
        elif module_name in eq_result.get("skipped_modules", []):
            module_rows_html += f"""
        <div class="eq-module-row">
            <span class="eq-module-score" style="color:#666666">N/A</span>
            <span class="eq-module-arrow" style="color:#666666">–</span>
            <span class="eq-module-name" style="color:#666666">{display}</span>
            <span class="eq-module-desc" style="color:#666666">MODULE SKIPPED — insufficient data</span>
        </div>"""

    # Staleness
    staleness_html = ""
    tier = eq_result["staleness_tier"]
    if tier == "WARNING":
        staleness_html = (
            f'<div class="eq-staleness-warning">'
            f'⚠ STALE DATA: Filing is {eq_result["filing_age_days"]} days old.</div>'
        )
    elif tier == "PENALTY":
        staleness_html = (
            f'<div class="eq-staleness-penalty">'
            f'⛔ DATA STALE: Filing is {eq_result["filing_age_days"]} days old. '
            f'Score reduced by {eq_result["staleness_penalty"]} pts.</div>'
        )

    reduced_html = ""
    if eq_result.get("reduced_window_warning"):
        reduced_html = (
            '<div class="eq-reduced-warning">'
            '⚠ REDUCED WINDOW: Fewer than 8 quarters available.</div>'
        )

    failed_reason_html = ""
    if not eq_result["passed"] and eq_result.get("failed_reason"):
        failed_reason_html = (
            f'<div class="eq-fail-reason">⛔ {eq_result["failed_reason"]}</div>'
        )

    fatal_flaw_html = ""
    if eq_result.get("fatal_flaw_reason"):
        fatal_flaw_html = (
            f'<div class="eq-fatal-flaw" style="color:#ff4444">⛔ FATAL FLAW: {eq_result["fatal_flaw_reason"]}</div>'
        )

    html = f"""
<div class="eq-block">
    <div class="eq-header">
        <span class="eq-title">EARNINGS QUALITY CHECK</span>
        <span class="eq-status" style="color:{status_color}">{status_text}</span>
    </div>
    <div class="eq-filing-note">
        SEC EDGAR · {eq_result['filing_date']} · {eq_result['filing_age_days']} days old
    </div>
    <div class="eq-score-line">
        EQ Score: {score_display} / 100 &nbsp;→&nbsp;
        <span style="color:{band_color}">{eq_result['band_label']}</span>
    </div>
    <div class="eq-score-meaning" style="color:{band_color}">{band_meaning}</div>
    {reliability_html}
    {strengths_html}
    {risks_html}
    <div class="eq-modules">
        <div class="eq-modules-label">Module Breakdown <span class="eq-tooltip-hint">(hover rows for detail)</span>:</div>
        {module_rows_html}
    </div>
    {staleness_html}
    {reduced_html}
    {failed_reason_html}
    {fatal_flaw_html}
    <div class="eq-verdict">{eq_result['verdict_sentence']}</div>
</div>"""

    logger.debug(f"[REPORT] Rich HTML block built for {eq_result['ticker']}")
    return html


def build_skip_block_text(ticker: str, filing_age_days: int,
                           staleness_tier: str,
                           skip_reason: str = "") -> str:
    """Compact plain-text block when all modules are skipped."""
    if skip_reason:
        reason_line = skip_reason
    else:
        reason_line = f"Most recent SEC filing is {filing_age_days} days old."

    return "\n".join([
        "━" * 52,
        "EARNINGS QUALITY CHECK  ⚠ SKIPPED",
        reason_line,
        "Earnings quality cannot be assessed. Treat this candidate with additional caution.",
        "━" * 52
    ])


def build_skip_block_html(ticker: str, filing_age_days: int, staleness_tier: str) -> str:
    """HTML block when all modules are skipped."""
    return f"""
<div class="eq-block eq-skipped">
    <div class="eq-header">
        <span class="eq-title">EARNINGS QUALITY CHECK</span>
        <span class="eq-status" style="color:#ffaa00">⚠ SKIPPED</span>
    </div>
    <div class="eq-filing-note">
        Most recent filing is {filing_age_days} days old. Data is unusable.
    </div>
    <div class="eq-verdict" style="color:#ffaa00">
        Earnings quality cannot be assessed. Treat this candidate with additional caution.
    </div>
</div>"""
