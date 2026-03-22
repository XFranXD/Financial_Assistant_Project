"""
eq_scorer.py
Composite EQ Score calculator — v3.0 System 2 architecture.

Scoring pipeline:
    1. Weighted sum of 7 composite module scores (earnings_timing excluded)
    2. Runtime N/A and UNKNOWN weight redistribution
    3. Conflict detection (magnitude-first, opposite-sign only)
    4. Warning score penalty (pre-constraint, graduated, capped at 5pts)
    5. Unified constraint pipeline (critical floors → economic integrity → global consistency → extreme cases)
    6. Subtract staleness penalty
    7. Subtract earnings timing modifier (0 to -5 pts)
    8. Evaluate FAILED conditions (existing logic preserved)
    9. Weighted data reliability (with staleness adjustment)
    10. Top risks + top strengths extraction
    11. Warning infrastructure (structured list with tier/severity)
    12. Composite label (eq_label + eq_modifier)
    13. Pass tier (PASS / WATCH / FAIL with sector relaxation)
    14. Classification (HIGH_PRIORITY / PRIORITY / REVIEW / AVOID / SKIP)
    15. Fatal flaw override (context-gated)
    16. Confidence fields (data_confidence, score_confidence)
    17. Dynamic verdict sentence

Debug logging: [SCORER] prefix
"""

import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Module and metric constants
# ─────────────────────────────────────────────

COMPOSITE_MODULES = [
    "cash_conversion", "accruals", "revenue_quality", "long_term_trends",
    "fcf_sustainability", "earnings_consistency", "dividend_stability"
]

FLAG_PRIORITY = [
    "cash_conversion", "accruals", "revenue_quality", "long_term_trends",
    "fcf_sustainability", "earnings_consistency", "dividend_stability"
]

MODULE_RISK_LABELS = {
    "cash_conversion":      "Profit-to-cash conversion is below acceptable levels",
    "accruals":             "Non-cash accounting entries are elevated",
    "revenue_quality":      "Receivables growing faster than revenue",
    "long_term_trends":     "Business trajectory is deteriorating across multiple dimensions",
    "earnings_consistency": "Earnings are volatile or unpredictable",
    "fcf_sustainability":   "Free cash flow margin is under pressure",
    "dividend_stability":   "Dividend policy shows signs of financial stress"
}

CRITICAL_METRICS = ["net_income", "operating_cash_flow", "revenue"]

# ─────────────────────────────────────────────
# 4.1 Warning infrastructure
# ─────────────────────────────────────────────

WARNING_SEVERITY_MAP = {
    "LOW CASH CONVERSION":           "major",
    "HIGH ACCRUALS":                 "major",
    "AGGRESSIVE AR GROWTH":          "major",
    "EARNINGS_QUALITY_CONFLICT":     "major",
    "ACCRUALS_CASH_CONFLICT":        "major",
    "LOW FCF MARGIN":                "medium",
    "REVENUE QUALITY CONCERN":       "medium",
    "EARNINGS VOLATILE":             "medium",
    "LONG TERM DETERIORATION":       "medium",
    "DIVIDEND STRESS":               "medium",
    "CONSISTENCY_TREND_CONFLICT":    "medium",
}

WARNING_DESCRIPTIONS = {
    "LOW CASH CONVERSION":        "Cash conversion rate critically low",
    "HIGH ACCRUALS":              "Accruals risk elevated — earnings may be inflated",
    "AGGRESSIVE AR GROWTH":       "Accounts receivable growing faster than revenue",
    "EARNINGS_QUALITY_CONFLICT":  "Revenue growth diverging significantly from cash conversion",
    "ACCRUALS_CASH_CONFLICT":     "Accruals-based earnings diverging from cash earnings",
    "CONSISTENCY_TREND_CONFLICT": "Short-term earnings consistency contradicting long-term trend",
    "LOW FCF MARGIN":             "Free cash flow margin is under pressure",
    "REVENUE QUALITY CONCERN":    "Revenue quality signals are deteriorating",
    "EARNINGS VOLATILE":          "Earnings are volatile or unpredictable",
    "LONG TERM DETERIORATION":    "Business trajectory deteriorating across multiple dimensions",
    "DIVIDEND STRESS":            "Dividend policy showing signs of financial stress",
}

WARNING_TIER = {
    "LOW CASH CONVERSION":        "causal",
    "HIGH ACCRUALS":              "causal",
    "AGGRESSIVE AR GROWTH":       "causal",
    "LOW FCF MARGIN":             "causal",
    "REVENUE QUALITY CONCERN":    "causal",
    "EARNINGS VOLATILE":          "causal",
    "LONG TERM DETERIORATION":    "causal",
    "DIVIDEND STRESS":            "causal",
    "EARNINGS_QUALITY_CONFLICT":  "diagnostic",
    "ACCRUALS_CASH_CONFLICT":     "diagnostic",
    "CONSISTENCY_TREND_CONFLICT": "diagnostic",
}

FLAG_TO_MODULE = {
    "LOW CASH CONVERSION":     "cash_conversion",
    "HIGH ACCRUALS":           "accruals",
    "AGGRESSIVE AR GROWTH":    "revenue_quality",
    "LOW FCF MARGIN":          "fcf_sustainability",
    "EARNINGS VOLATILE":       "earnings_consistency",
    "LONG TERM DETERIORATION": "long_term_trends",
    "DIVIDEND STRESS":         "dividend_stability",
}


def _classify_warnings(warnings: list) -> tuple:
    major  = [w for w in warnings if w["severity"] == "major"]
    medium = [w for w in warnings if w["severity"] == "medium"]
    return major, medium


def _infer_severity_from_score(flag: str, module_score) -> str:
    if module_score is None:
        return "medium"
    if module_score < 40:
        return "major"
    elif module_score < 60:
        return "medium"
    else:
        return "low"


def _build_warnings(active_flags: list, module_scores: dict) -> list:
    warnings = []
    for flag in active_flags:
        linked_module = FLAG_TO_MODULE.get(flag)
        if linked_module and linked_module in module_scores:
            severity = _infer_severity_from_score(flag, module_scores[linked_module])
            static_severity = WARNING_SEVERITY_MAP.get(flag, "medium")
            if static_severity == "major" and severity == "low":
                severity = "medium"
        else:
            severity = WARNING_SEVERITY_MAP.get(flag, "medium")
        category = "business"
        tier     = WARNING_TIER.get(flag, "causal")
        message  = WARNING_DESCRIPTIONS.get(flag, flag)
        warnings.append({
            "type": flag, "severity": severity,
            "category": category, "tier": tier, "message": message
        })
        logger.debug(
            f"[SCORER] Warning: type={flag} severity={severity} tier={tier}"
        )
    return warnings


# ─────────────────────────────────────────────
# 4.2 Warning score with deduplication
# ─────────────────────────────────────────────

WARNING_WEIGHTS = {
    "LOW CASH CONVERSION":        4,
    "HIGH ACCRUALS":              4,
    "AGGRESSIVE AR GROWTH":       3,
    "EARNINGS_QUALITY_CONFLICT":  2,
    "ACCRUALS_CASH_CONFLICT":     2,
    "CONSISTENCY_TREND_CONFLICT": 1,
    "LOW FCF MARGIN":             1,
    "REVENUE QUALITY CONCERN":    1,
    "EARNINGS VOLATILE":          1,
    "LONG TERM DETERIORATION":    1,
    "DIVIDEND STRESS":            1,
}
WARNING_WEIGHT_DEFAULT = 2

CONFLICT_TO_CAUSAL = {
    "EARNINGS_QUALITY_CONFLICT":  {"LOW CASH CONVERSION", "REVENUE QUALITY CONCERN"},
    "ACCRUALS_CASH_CONFLICT":     {"HIGH ACCRUALS", "LOW CASH CONVERSION"},
    "CONSISTENCY_TREND_CONFLICT": {"EARNINGS VOLATILE", "LONG TERM DETERIORATION"},
}


def _compute_warning_score(warnings: list) -> float:
    present_types = {w["type"] for w in warnings}
    total = 0.0
    for w in warnings:
        flag   = w["type"]
        weight = WARNING_WEIGHTS.get(flag, WARNING_WEIGHT_DEFAULT)
        if w.get("tier") == "diagnostic":
            causal_sources = CONFLICT_TO_CAUSAL.get(flag, set())
            if causal_sources & present_types:
                logger.debug(f"[SCORER] Diagnostic {flag} suppressed (causal already counted)")
                continue
        total += weight
    logger.debug(f"[SCORER] warning_score={total}")
    return float(total)


# ─────────────────────────────────────────────
# 4.3 Composite label
# ─────────────────────────────────────────────

def _assign_eq_label(eq_score_final: float, warnings: list) -> tuple:
    """Returns (eq_label, eq_modifier). eq_modifier: None|\"CAUTION\"|\"ADJUSTED\" """
    major_hits, medium_hits = _classify_warnings(warnings)
    if eq_score_final >= 75:   base = "STRONG"
    elif eq_score_final >= 55: base = "ACCEPTABLE"
    elif eq_score_final >= 35: base = "WEAK"
    else:                      base = "POOR"
    tier_order = ["POOR", "WEAK", "ACCEPTABLE", "STRONG"]
    if len(major_hits) >= 1 or len(medium_hits) >= 2:
        idx        = tier_order.index(base)
        downgraded = tier_order[max(0, idx - 1)]
        logger.debug(f"[SCORER] Label ADJUSTED {base} → {downgraded}")
        return downgraded, "ADJUSTED"
    elif len(medium_hits) == 1:
        return base, "CAUTION"
    else:
        return base, None


# ─────────────────────────────────────────────
# 4.4 Magnitude-first conflict detection
# ─────────────────────────────────────────────

CONFLICT_RULES = [
    {"module_a": "revenue_quality",      "module_b": "cash_conversion",
     "conflict_type": "EARNINGS_QUALITY_CONFLICT"},
    {"module_a": "long_term_trends",     "module_b": "cash_conversion",
     "conflict_type": "EARNINGS_QUALITY_CONFLICT"},
    {"module_a": "accruals",             "module_b": "cash_conversion",
     "conflict_type": "ACCRUALS_CASH_CONFLICT"},
    {"module_a": "earnings_consistency", "module_b": "long_term_trends",
     "conflict_type": "CONSISTENCY_TREND_CONFLICT"},
]
CONFLICT_MAGNITUDE_THRESHOLD = 0.15
CONFLICT_NOISE_FLOOR          = 0.03


def _get_trend_signal(result: dict):
    """
    Returns trend_strength if available, else None.
    Does NOT fall back to score-band approximations — synthetic signals
    cause false conflict triggers.
    """
    if result is None: return None
    strength = result.get("trend_strength")
    if strength is not None: return float(strength)
    return None


def _detect_conflicts(results_by_name: dict, active_flags: list) -> list:
    for rule in CONFLICT_RULES:
        conflict_type = rule["conflict_type"]
        if conflict_type in active_flags:
            continue
        a = results_by_name.get(rule["module_a"])
        b = results_by_name.get(rule["module_b"])
        if not a or not b: continue
        if a.get("not_applicable") or b.get("not_applicable"): continue
        if a.get("unknown") or b.get("unknown"): continue
        signal_a = _get_trend_signal(a)
        signal_b = _get_trend_signal(b)
        if signal_a is None or signal_b is None: continue
        if abs(signal_a) < CONFLICT_NOISE_FLOOR and abs(signal_b) < CONFLICT_NOISE_FLOOR:
            continue
        # Only fire on true divergence — opposite signs required
        if signal_a * signal_b >= 0:
            continue
        divergence = abs(signal_a - signal_b)
        if divergence >= CONFLICT_MAGNITUDE_THRESHOLD:
            active_flags.append(conflict_type)
            logger.debug(
                f"[SCORER] Conflict: {rule['module_a']}={signal_a:.3f} vs "
                f"{rule['module_b']}={signal_b:.3f} divergence={divergence:.3f} → {conflict_type}"
            )
    return active_flags


# ─────────────────────────────────────────────
# 4.5 Weighted data reliability
# ─────────────────────────────────────────────

MODULE_RELIABILITY_WEIGHTS = {
    "cash_conversion":      3.0,
    "accruals":             2.5,
    "fcf_sustainability":   2.0,
    "revenue_quality":      1.5,
    "long_term_trends":     1.5,
    "earnings_consistency": 1.0,
    "dividend_stability":   0.5,
}
TOTAL_RELIABILITY_WEIGHT = sum(MODULE_RELIABILITY_WEIGHTS.values())  # 12.0


def _compute_weighted_reliability(module_scores: dict, results_by_name: dict,
                                   filing_age_days: int = 0) -> float:
    earned = 0.0
    for module_name, weight in MODULE_RELIABILITY_WEIGHTS.items():
        if module_name in module_scores:
            earned += weight
        else:
            result = results_by_name.get(module_name)
            if result and result.get("not_applicable"):
                earned += weight   # N/A is expected absence, not a data gap
    reliability = earned / TOTAL_RELIABILITY_WEIGHT

    # Staleness adjustment
    if filing_age_days > 120:
        reliability *= 0.80
    elif filing_age_days > 90:
        reliability *= 0.90

    logger.debug(f"[SCORER] Weighted reliability: {reliability:.3f} ({earned:.1f}/{TOTAL_RELIABILITY_WEIGHT}) age={filing_age_days}d")
    return round(reliability, 3)


# ─────────────────────────────────────────────
# 4.6 Constraint pipeline
# ─────────────────────────────────────────────

CRITICAL_MODULE_FLOORS = {
    "cash_conversion":    {"t1": 40, "cap1": 65, "t2": 30, "cap2": 50, "label": "Cash Conversion"},
    "accruals":           {"t1": 40, "cap1": 65, "t2": 30, "cap2": 50, "label": "Accruals Quality"},
    "fcf_sustainability": {"t1": 35, "cap1": 70, "t2": 25, "cap2": 55, "label": "FCF Sustainability"},
}


def _apply_critical_floors(score: float, module_scores: dict) -> tuple:
    reasons = []
    for module_name, floors in CRITICAL_MODULE_FLOORS.items():
        ms = module_scores.get(module_name)
        if ms is None: continue
        if ms < floors["t2"]:
            if score > floors["cap2"]:
                score = floors["cap2"]
                reasons.append(f"{floors['label']}={ms:.0f} → cap {floors['cap2']} (severe)")
                logger.warning(f"[SCORER] Critical floor (severe): {module_name}={ms:.0f} → cap {floors['cap2']}")
        elif ms < floors["t1"]:
            if score > floors["cap1"]:
                score = floors["cap1"]
                reasons.append(f"{floors['label']}={ms:.0f} → cap {floors['cap1']} (moderate)")
                logger.info(f"[SCORER] Critical floor (moderate): {module_name}={ms:.0f} → cap {floors['cap1']}")
    return round(score, 1), reasons


ECONOMIC_INTEGRITY_MODULES  = ["cash_conversion", "accruals", "fcf_sustainability", "revenue_quality"]
ECONOMIC_INTEGRITY_WEIGHTS  = {"cash_conversion": 0.35, "accruals": 0.30,
                                "fcf_sustainability": 0.20, "revenue_quality": 0.15}


def _compute_economic_integrity(module_scores: dict) -> tuple:
    available = {m: module_scores[m] for m in ECONOMIC_INTEGRITY_MODULES if m in module_scores}
    if len(available) < 3:
        return None, f"Insufficient core modules ({len(available)}/4)"
    total_weight = sum(ECONOMIC_INTEGRITY_WEIGHTS[m] for m in available)
    weighted_avg = sum(available[m] * ECONOMIC_INTEGRITY_WEIGHTS[m] for m in available) / total_weight
    min_score    = min(available.values())
    integrity    = round(0.80 * weighted_avg + 0.20 * min_score, 1)
    logger.info(f"[SCORER] Economic integrity: avg={weighted_avg:.1f} min={min_score:.1f} → {integrity:.1f} ceiling={integrity+15:.1f}")
    return integrity, "computed"


def _apply_economic_integrity_ceiling(score: float, integrity) -> float:
    if integrity is None: return score
    ceiling = integrity + 15.0
    if score > ceiling:
        logger.info(f"[SCORER] Economic integrity ceiling: {score:.1f} → {ceiling:.1f}")
        return round(ceiling, 1)
    return score


def _validate_global_consistency(results_by_name: dict, eq_score: float):
    def gs(name):
        r = results_by_name.get(name)
        if not r or r.get("not_applicable") or r.get("unknown"): return None
        return r.get("score")
    def gt(name):
        r = results_by_name.get(name)
        if not r or r.get("not_applicable") or r.get("unknown"): return None
        return r.get("trend")
    cc = gs("cash_conversion"); ac = gs("accruals")
    rq = gt("revenue_quality"); fcf = gs("fcf_sustainability")
    if cc is not None and ac is not None and cc < 40 and ac < 40:
        logger.warning(f"[SCORER] Global consistency: cc={cc} + ac={ac} → cap 60")
        return {"force_cap": 60.0, "reason": "Low cash conversion + high accruals — structurally weak earnings"}
    if rq == "down" and fcf is not None and fcf < 40:
        logger.warning(f"[SCORER] Global consistency: rq=down + fcf={fcf} → cap 65")
        return {"force_cap": 65.0, "reason": "Revenue deteriorating + FCF weak — cash generation at structural risk"}
    return None


def _apply_extreme_cases(results_by_name: dict, module_scores: dict,
                          eq_score: float, pass_tier: str) -> tuple:
    checks = [
        {"module": "cash_conversion",    "label": "Cash Flow Quality",
         "severe":   {"t": 20, "cap": 45, "force_watch": True},
         "major":    {"t": 30, "cap": 55, "force_watch": True},
         "moderate": {"t": 40, "cap": 65, "force_watch": False}},
        {"module": "accruals",           "label": "Accruals Quality",
         "severe":   {"t": 20, "cap": 45, "force_watch": True},
         "major":    {"t": 30, "cap": 55, "force_watch": True},
         "moderate": {"t": 40, "cap": 65, "force_watch": False}},
        {"module": "fcf_sustainability", "label": "FCF Sustainability",
         "severe":   {"t": 15, "cap": 50, "force_watch": True},
         "major":    {"t": 25, "cap": 60, "force_watch": False},
         "moderate": {"t": 35, "cap": 68, "force_watch": False}},
    ]
    triggered = []
    for check in checks:
        ms = module_scores.get(check["module"])
        if ms is None: continue
        result = results_by_name.get(check["module"])
        trend  = result.get("trend", "flat") if result else "flat"

        if ms < check["severe"]["t"]:
            band, band_name = check["severe"], "severe"
        elif ms < check["major"]["t"]:
            if trend != "down": continue
            band, band_name = check["major"], "major"
        elif ms < check["moderate"]["t"]:
            if trend != "down": continue
            band, band_name = check["moderate"], "moderate"
        else:
            continue

        eq_score = min(eq_score, band["cap"])
        if band["force_watch"] and pass_tier == "PASS":
            pass_tier = "WATCH"
        reason = f"{check['label']} ({check['module']}) score={ms:.0f} ({band_name}) → cap {band['cap']}"
        triggered.append(reason)
        logger.warning(f"[SCORER] Extreme case ({band_name}): {check['module']}={ms:.0f} → cap {band['cap']}")

    return round(eq_score, 1), pass_tier, triggered


def apply_constraint_pipeline(score_before: float, module_scores: dict,
                               results_by_name: dict, pass_tier: str) -> tuple:
    """
    Single coordinated entry point for all structural constraints.
    Priority: critical floors → economic integrity → global consistency → extreme cases.
    Stops applying new constraints after 2 meaningful reductions (delta >= 3 pts).
    Returns (final_score, pass_tier_hint, constraint_log, integrity).
    """
    MAX_MEANINGFUL_CONSTRAINTS = 2
    MIN_DELTA_THRESHOLD        = 3.0
    applied_count = 0

    score = score_before
    constraint_log = []

    # Layer 1: Critical floors
    sb = score
    score, floor_reasons = _apply_critical_floors(score, module_scores)
    for r in floor_reasons:
        delta = round(score - sb, 1)
        constraint_log.append({"name": "critical_floor", "score_in": sb,
                                "score_out": score, "delta": delta, "reason": r, "dominant": False})
        if abs(delta) >= MIN_DELTA_THRESHOLD:
            applied_count += 1
        sb = score

    # Layer 2: Economic integrity ceiling (conditional)
    if applied_count < MAX_MEANINGFUL_CONSTRAINTS:
        sb = score
        integrity, _ = _compute_economic_integrity(module_scores)
        core_scores = [module_scores[m] for m in ECONOMIC_INTEGRITY_MODULES if m in module_scores]
        if core_scores and min(core_scores) < 40:
            score = _apply_economic_integrity_ceiling(score, integrity)
            if score < sb:
                delta = round(score - sb, 1)
                constraint_log.append({"name": "economic_integrity", "score_in": sb,
                                        "score_out": score, "delta": delta,
                                        "reason": f"integrity={integrity:.1f} ceiling={integrity+15:.1f}", "dominant": False})
                if abs(delta) >= MIN_DELTA_THRESHOLD:
                    applied_count += 1
        else:
            logger.debug("[SCORER] Economic integrity ceiling skipped — all core modules healthy")
            integrity = None
    else:
        logger.debug("[SCORER] Constraint cap reached — skipping economic integrity")
        integrity, _ = _compute_economic_integrity(module_scores)

    # Layer 3: Global consistency
    if applied_count < MAX_MEANINGFUL_CONSTRAINTS:
        sb = score
        cc = _validate_global_consistency(results_by_name, score)
        if cc:
            score = min(score, cc["force_cap"])
            if score < sb:
                delta = round(score - sb, 1)
                constraint_log.append({"name": "global_consistency", "score_in": sb,
                                        "score_out": score, "delta": delta,
                                        "reason": cc["reason"], "dominant": False})
                if abs(delta) >= MIN_DELTA_THRESHOLD:
                    applied_count += 1
    else:
        logger.debug("[SCORER] Constraint cap reached — skipping global consistency")

    # Layer 4: Extreme cases
    if applied_count < MAX_MEANINGFUL_CONSTRAINTS:
        sb = score
        score, pass_tier, extreme_reasons = _apply_extreme_cases(
            results_by_name, module_scores, score, pass_tier)
        for r in extreme_reasons:
            delta = round(score - sb, 1)
            constraint_log.append({"name": "extreme_case", "score_in": sb,
                                    "score_out": score, "delta": delta, "reason": r, "dominant": False})
            if abs(delta) >= MIN_DELTA_THRESHOLD:
                applied_count += 1
            sb = score
    else:
        logger.debug("[SCORER] Constraint cap reached — skipping extreme cases")
        extreme_reasons = []

    # Mark dominant constraint
    if constraint_log:
        dom = max(constraint_log, key=lambda c: abs(c["delta"]))
        dom["dominant"] = True
        logger.info(
            f"[SCORER] Constraints: {score_before:.1f} → {score:.1f} | "
            f"applied={applied_count} dominant={dom['name']} Δ{dom['delta']}"
        )

    return round(score, 1), pass_tier, constraint_log, integrity


# ─────────────────────────────────────────────
# 4.7 Pass tier and classification
# ─────────────────────────────────────────────

SECTOR_RELAXATION = {
    "telecom":   (-5, -0.05),
    "utilities": (-5, -0.05),
    "energy":    (-3,  0.0),
    "default":   ( 0,  0.0),
}


def _apply_sector_relaxation(sector: str, pass_score: float, rel_thr: float) -> tuple:
    sd, rd = SECTOR_RELAXATION.get(sector.lower(), SECTOR_RELAXATION["default"])
    if sd != 0 or rd != 0:
        logger.debug(f"[SCORER] Sector {sector}: score_threshold {pass_score}→{pass_score+sd}")
    return pass_score + sd, rel_thr + rd


def _assign_pass_tier(eq_score: float, warnings: list, warning_score: float,
                      data_reliability: float, sector: str = "default") -> str:
    major_hits, _ = _classify_warnings(warnings)
    pass_thr, rel_thr = _apply_sector_relaxation(sector, 80.0, 0.80)

    # Smooth warning tolerance: 65–74 → 0, 75–84 → 1, 85+ → 2
    warning_tolerance = max(0, int((eq_score - 65) / 10))

    if eq_score < 55 or data_reliability < 0.55:
        logger.debug(f"[SCORER] FAIL — score={eq_score} reliability={data_reliability:.0%}")
        return "FAIL"
    if len(major_hits) >= 1 and eq_score < 70:
        logger.debug("[SCORER] FAIL — major warning + score < 70")
        return "FAIL"
    if (eq_score >= pass_thr and warning_score <= warning_tolerance and data_reliability >= rel_thr):
        logger.debug(f"[SCORER] PASS — score={eq_score} ws={warning_score} tol={warning_tolerance}")
        return "PASS"
    logger.debug(f"[SCORER] WATCH — score={eq_score} ws={warning_score} tol={warning_tolerance}")
    return "WATCH"


def _assign_final_classification(pass_tier: str, eq_score: float,
                                  warning_score: float, eq_modifier) -> str:
    if pass_tier == "FAIL":   return "AVOID"
    if pass_tier == "PASS":
        if eq_score >= 88 and warning_score == 0: return "HIGH_PRIORITY"
        if eq_modifier is None and eq_score >= 80: return "PRIORITY"
        return "REVIEW"
    if pass_tier == "WATCH":  return "REVIEW"
    return "SKIP"


# ─────────────────────────────────────────────
# 4.8 Fatal flaws (context-gated)
# ─────────────────────────────────────────────

def _check_fatal_flaws(module_scores: dict, results_by_name: dict,
                        data_reliability: float, classification: str) -> tuple:
    def gs(n): return module_scores.get(n)
    def gt(n):
        r = results_by_name.get(n)
        return r.get("trend", "flat") if r else "flat"

    cc  = gs("cash_conversion")
    ac  = gs("accruals")
    fcf = gs("fcf_sustainability")

    # Condition 1: Cash conversion collapse
    if cc is not None:
        if cc < 20:
            reason = f"Cash conversion collapsed (score={cc:.0f})"
            logger.warning(f"[SCORER] Fatal flaw (unconditional): {reason}")
            return "AVOID", reason
        elif 20 <= cc < 30:
            if gt("cash_conversion") == "down" and data_reliability >= 0.60:
                reason = f"Cash conversion critically weak (score={cc:.0f}) with confirmed downward trend"
                logger.warning(f"[SCORER] Fatal flaw (trend-confirmed): {reason}")
                return "AVOID", reason

    # Condition 2: Dual critical failure
    if cc is not None and ac is not None and cc < 30 and ac < 30 and data_reliability >= 0.60:
        reason = f"Dual critical failure: cash_conversion={cc:.0f} accruals={ac:.0f}"
        logger.warning(f"[SCORER] Fatal flaw (dual): {reason}")
        return "AVOID", reason

    # Condition 3: Triple core failure
    failing = sum(1 for s in [cc, ac, fcf] if s is not None and s < 40)
    if failing >= 3 and data_reliability >= 0.60:
        reason = "Triple core failure: all three core modules below 40"
        logger.warning(f"[SCORER] Fatal flaw (triple): {reason}")
        return "AVOID", reason

    return classification, None


# ─────────────────────────────────────────────
# 4.9 Score confidence
# ─────────────────────────────────────────────

def _compute_score_confidence(module_scores: dict, data_reliability: float,
                               warnings: list) -> str:
    if not module_scores: return "LOW"
    min_score = min(module_scores.values())
    max_score = max(module_scores.values())
    spread    = max_score - min_score

    if spread > 50 and data_reliability < 0.85: return "LOW"
    if min_score < 30 and len(warnings) >= 2: return "LOW"
    min_tier         = 1 if min_score < 50 else 0
    reliability_tier = 1 if data_reliability < 0.75 else 0
    warning_tier     = 1 if len(warnings) >= 2 else 0
    total = min_tier + reliability_tier + warning_tier
    if total == 0: return "HIGH"
    elif total == 1: return "MODERATE"
    else: return "LOW"


# ─────────────────────────────────────────────
# 4.10 Data confidence label
# ─────────────────────────────────────────────

def _assign_data_confidence(data_reliability: float) -> str:
    if data_reliability >= 0.85:  return "HIGH"
    elif data_reliability >= 0.70: return "MODERATE"
    elif data_reliability >= 0.55: return "LOW"
    else: return "UNRELIABLE"


# ─────────────────────────────────────────────
# 11.2 Key Strengths extraction (Section 4.11)
# ─────────────────────────────────────────────

MODULE_STRENGTH_LABELS = {
    "cash_conversion":      "Strong operating cash flow conversion",
    "accruals":             "Low accruals — earnings are cash-backed",
    "revenue_quality":      "Revenue growth backed by real cash collections",
    "long_term_trends":     "Business trajectory improving across multiple dimensions",
    "fcf_sustainability":   "Free cash flow generation is healthy and self-sustaining",
    "earnings_consistency": "Earnings are stable and predictable",
    "dividend_stability":   "Dividend policy is financially sustainable",
}


def _extract_top_strengths(results_by_name: dict, module_scores: dict) -> list:
    """
    Returns up to 2 top strengths — modules scoring >= 75 with trend up or flat.
    Sorted by score descending so the strongest signal appears first.
    Never includes a module that also has an active flag.
    """
    flagged = {
        name for name, result in results_by_name.items()
        if result.get("flag")
    }
    candidates = [
        (name, score)
        for name, score in module_scores.items()
        if score >= 75
        and name not in flagged
        and results_by_name.get(name, {}).get("trend") in ("up", "flat")
    ]
    candidates.sort(key=lambda x: x[1], reverse=True)
    return [
        MODULE_STRENGTH_LABELS.get(name, f"{name.replace('_', ' ')} is strong")
        for name, _ in candidates[:2]
    ]


# ─────────────────────────────────────────────
# 4.12 Dynamic verdict
# ─────────────────────────────────────────────

def _verdict_sentence(eq_score: float, active_flags: list, passed: bool,
                       eq_label: str, eq_modifier, top_risks: list) -> str:
    has_warnings = len(active_flags) > 0
    if not passed or eq_score < 35:
        risk_text = top_risks[0].lower().rstrip('.') if top_risks else "serious cash-to-earnings divergence"
        return (f"Earnings quality is poor. Reported profits show limited backing by real "
                f"cash flows — specifically {risk_text}. Treat with significant caution.")
    if eq_label == "STRONG" and eq_modifier is None and not has_warnings:
        return "High-quality earnings with strong cash backing and no active risk signals."
    if eq_label == "STRONG" and eq_modifier in ("ADJUSTED", "CAUTION"):
        return ("Earnings quality is strong overall, but early warning signs are present "
                "and warrant monitoring before treating this as fully clean.")
    if eq_label == "STRONG" and has_warnings:
        risk_text = top_risks[0].lower() if top_risks else "some warning signals"
        return (
            f"Earnings quality is strong overall, but {risk_text} warrants monitoring. "
            "Core cash metrics remain healthy."
        )
    if eq_label == "ACCEPTABLE" and not has_warnings:
        return ("Earnings are mostly cash-backed with no active warning signals, "
                "but some structural metrics fall short of STRONG thresholds.")
    if eq_label in ("ACCEPTABLE", "WEAK") and has_warnings:
        risk_text = top_risks[0].lower() if top_risks else "several dimensions"
        return (f"Mixed earnings quality — signals of weakness detected in {risk_text}. "
                "Cash generation is present but not consistent across all measured dimensions.")
    return ("Earnings quality could not be fully assessed. "
            "See warnings and reliability score for context.")


# ─────────────────────────────────────────────
# Existing helpers (preserved)
# ─────────────────────────────────────────────

def _compute_timing_penalty(timing_result: dict, config: dict) -> float:
    """Compute earnings timing modifier penalty (0–5 points)."""
    if not timing_result or timing_result.get("unknown"):
        return 0.0
    et_cfg = config.get("earnings_timing_modifier", {})
    days = timing_result.get("debug", {}).get("days_to_earnings")
    if days is None:
        return 0.0
    high_days    = et_cfg.get("high_risk_days", 3)
    mod_days     = et_cfg.get("moderate_risk_days", 10)
    low_mod_days = et_cfg.get("low_moderate_risk_days", 30)
    high_pen     = et_cfg.get("high_risk_penalty", 5)
    mod_pen      = et_cfg.get("moderate_risk_penalty", 3)
    low_mod_pen  = et_cfg.get("low_moderate_risk_penalty", 1)
    if days <= high_days:
        return float(high_pen)
    elif days <= mod_days:
        return float(mod_pen)
    elif days <= low_mod_days:
        return float(low_mod_pen)
    return 0.0


def _evaluate_failed(
    eq_score: float, flags: list, module_scores: dict, config: dict
) -> tuple:
    """
    Apply FAILED conditions in severity order. Return (passed, reason).
    """
    fail_cfg = config["scoring"]["failed_thresholds"]

    cc = module_scores.get("cash_conversion")
    if cc is not None and cc < fail_cfg["cash_conversion_auto_fail"]:
        reason = f"Cash Conversion score {cc} below auto-fail threshold ({fail_cfg['cash_conversion_auto_fail']})"
        logger.warning(f"[SCORER] FAILED — {reason}")
        return False, reason

    ac = module_scores.get("accruals")
    if ac is not None and ac < fail_cfg["accruals_auto_fail"]:
        reason = f"Accruals score {ac} below auto-fail threshold ({fail_cfg['accruals_auto_fail']})"
        logger.warning(f"[SCORER] FAILED — {reason}")
        return False, reason

    if len(flags) >= fail_cfg["simultaneous_flags_limit"]:
        reason = f"{len(flags)} simultaneous flags: {', '.join(flags)}"
        logger.warning(f"[SCORER] FAILED — {reason}")
        return False, reason

    if eq_score < fail_cfg["eq_score_floor"]:
        reason = f"EQ Score {eq_score} below minimum ({fail_cfg['eq_score_floor']})"
        logger.warning(f"[SCORER] FAILED — {reason}")
        return False, reason

    logger.info(f"[SCORER] PASSED — EQ={eq_score}, flags={flags}")
    return True, ""


def _extract_top_risks(
    results_by_name: dict, module_scores: dict, active_flags: list
) -> list:
    """
    Extract up to 2 top risk items for report display.
    """
    risks = []
    covered_modules = set()

    for module_name in FLAG_PRIORITY:
        if len(risks) >= 2:
            break
        result = results_by_name.get(module_name)
        if result and result.get("flag"):
            risks.append(result["plain_english"])
            covered_modules.add(module_name)

    if len(risks) < 2:
        scored_modules = [
            (module_name, s)
            for module_name, s in module_scores.items()
            if module_name not in covered_modules and s < 75
        ]
        scored_modules.sort(key=lambda x: x[1])
        for module_name, s in scored_modules:
            if len(risks) >= 2:
                break
            risks.append(MODULE_RISK_LABELS.get(module_name, f"{module_name} score is below average"))

    return risks


def _band_label(score: float) -> str:
    if score >= 75: return "STRONG"
    elif score >= 55: return "ACCEPTABLE"
    elif score >= 35: return "WEAK"
    else: return "POOR"


# ─────────────────────────────────────────────
# Section 5: Main score() function
# ─────────────────────────────────────────────

def score(module_results: list, validated_packet: dict, config: dict,
          timing_result: dict = None, sector: str = "default") -> dict:
    """
    Compute composite EQ Score.

    timing_result: optional ModuleResult from module_earnings_timing.run().
    sector: company sector for relaxation rules (default="default").

    Returns eq_result dict with all existing + new fields.
    """
    ticker             = validated_packet["ticker"]
    adjusted_weights   = {k: v for k, v in validated_packet["adjusted_weights"].items()
                          if k in COMPOSITE_MODULES}
    staleness_penalty  = validated_packet["staleness_penalty"]
    skipped_modules    = validated_packet["skipped_modules"]
    time_series        = validated_packet.get("time_series", {})

    logger.info(f"[SCORER] Computing EQ score for {ticker}")

    results_by_name = {r["module_name"]: r for r in module_results}

    # --- Steps 1-2: Weighted sum with N/A and UNKNOWN redistribution ---
    eq_score_raw   = 0.0
    module_scores  = {}
    active_flags   = []
    skipped_live   = []

    for module_name, weight in adjusted_weights.items():
        if module_name in results_by_name:
            result = results_by_name[module_name]
            s = result.get("score")
            if s is None or result.get("not_applicable") or result.get("unknown"):
                skipped_live.append(module_name)
                continue
            eq_score_raw += s * weight
            module_scores[module_name] = s
            if result.get("flag"):
                active_flags.append(result["flag"])
                logger.info(f"[SCORER] Flag: {result['flag']} from {module_name}")

    if skipped_live:
        total_used = sum(adjusted_weights[m] for m in module_scores)
        skipped_w  = sum(adjusted_weights[m] for m in skipped_live if m in adjusted_weights)
        if total_used > 0 and skipped_w > 0:
            scale = 1.0 + (skipped_w / total_used)
            eq_score_raw = round(eq_score_raw * scale, 1)
            logger.info(f"[SCORER] Redistributed {skipped_w:.3f} weight from {skipped_live}")

    eq_score_raw = round(eq_score_raw, 1)

    # NEW: Conflict detection BEFORE constraint pipeline
    active_flags = _detect_conflicts(results_by_name, active_flags)

    # NEW: Build warnings early so penalty can be applied before constraints
    warnings_early      = _build_warnings(active_flags, module_scores)
    warning_score_early = _compute_warning_score(warnings_early)
    if warning_score_early >= 8:
        ws_penalty   = min(5.0, (warning_score_early - 5) * 0.5)
        eq_score_raw = round(max(0.0, eq_score_raw - ws_penalty), 1)
        logger.debug(
            f"[SCORER] Warning penalty (pre-constraint): ws={warning_score_early:.1f} "
            f"→ penalty={ws_penalty:.1f} eq_score_raw={eq_score_raw}"
        )

    # NEW: Unified constraint pipeline
    eq_score_raw, _, constraint_log, economic_integrity = apply_constraint_pipeline(
        score_before=eq_score_raw,
        module_scores=module_scores,
        results_by_name=results_by_name,
        pass_tier="WATCH"
    )

    # Step 3: Staleness penalty
    after_staleness = round(max(0.0, eq_score_raw - staleness_penalty), 1)

    # Step 4: Earnings timing modifier
    et_penalty     = _compute_timing_penalty(timing_result, config)
    eq_score_final = round(max(0.0, after_staleness - et_penalty), 1)

    # Build modifier detail string
    modifier_parts = []
    if staleness_penalty > 0:
        modifier_parts.append(f"−{staleness_penalty} stale")
    if et_penalty > 0:
        modifier_parts.append(f"−{et_penalty} earnings timing")
    modifier_detail = ", ".join(modifier_parts) if modifier_parts else ""
    total_modifier  = staleness_penalty + et_penalty

    logger.info(
        f"[SCORER] {ticker}: raw={eq_score_raw}, stale={staleness_penalty}, "
        f"timing={et_penalty}, final={eq_score_final}, flags={active_flags}"
    )

    # Step 5-6: FAILED evaluation
    passed, failed_reason = _evaluate_failed(eq_score_final, active_flags, module_scores, config)
    band_label = _band_label(eq_score_final)

    # Step 7: Weighted reliability
    data_reliability = _compute_weighted_reliability(
        module_scores, results_by_name,
        filing_age_days=validated_packet.get("filing_age_days", 0)
    )
    working_modules  = len(module_scores)
    total_modules    = len(COMPOSITE_MODULES)
    critical_metrics_missing = any(
        m not in time_series or len(time_series.get(m, [])) == 0
        for m in CRITICAL_METRICS
    )

    # Step 8: Top risks
    top_risks = _extract_top_risks(results_by_name, module_scores, active_flags)

    # NEW: Top strengths
    top_strengths = _extract_top_strengths(results_by_name, module_scores)

    # NEW: Warnings with tier and dynamic severity
    warnings      = _build_warnings(active_flags, module_scores)
    warning_score = _compute_warning_score(warnings)

    # NEW: Composite label
    eq_label, eq_modifier = _assign_eq_label(eq_score_final, warnings)

    # NEW: Pass tier
    pass_tier = _assign_pass_tier(eq_score_final, warnings, warning_score,
                                   data_reliability, sector)

    # NEW: Classification
    classification = _assign_final_classification(
        pass_tier, eq_score_final, warning_score, eq_modifier)

    # NEW: Fatal flaw override
    classification, fatal_flaw_reason = _check_fatal_flaws(
        module_scores, results_by_name, data_reliability, classification)

    # NEW: Confidence fields
    data_confidence  = _assign_data_confidence(data_reliability)
    score_confidence = _compute_score_confidence(module_scores, data_reliability, warnings)

    # Step 9: Dynamic verdict
    verdict_sentence = _verdict_sentence(
        eq_score_final, active_flags, passed, eq_label, eq_modifier, top_risks)

    # Extract backward-compat fields from constraint_log
    floor_reasons   = [c["reason"] for c in constraint_log if c["name"] == "critical_floor"]
    extreme_reasons = [c["reason"] for c in constraint_log if c["name"] == "extreme_case"]
    dominant_constraint = next(
        (c["name"] for c in constraint_log if c.get("dominant")), None)

    return {
        # --- All existing fields (unchanged) ---
        "ticker":                   ticker,
        "eq_score_raw":             eq_score_raw,
        "eq_score_final":           eq_score_final,
        "staleness_penalty":        staleness_penalty,
        "earnings_timing_penalty":  et_penalty,
        "total_modifier":           total_modifier,
        "modifier_detail":          modifier_detail,
        "band_label":               band_label,
        "passed":                   passed,
        "failed_reason":            failed_reason,
        "module_scores":            module_scores,
        "active_flags":             active_flags,
        "top_risks":                top_risks,
        "top_strengths":            top_strengths,
        "data_reliability":         data_reliability,
        "critical_metrics_missing": critical_metrics_missing,
        "verdict_sentence":         verdict_sentence,
        "skipped_modules":          skipped_modules,
        "reduced_window_warning":   validated_packet["reduced_window_warning"],
        "filing_date":              validated_packet["filing_date"],
        "filing_age_days":          validated_packet["filing_age_days"],
        "staleness_tier":           validated_packet["staleness_tier"],
        # --- New fields ---
        "warnings":                 warnings,
        "warning_score":            warning_score,
        "eq_label":                 eq_label,
        "eq_modifier":              eq_modifier,
        "pass_tier":                pass_tier,
        "final_classification":     classification,
        "fatal_flaw_reason":        fatal_flaw_reason,
        "data_confidence":          data_confidence,
        "score_confidence":         score_confidence,
        "economic_integrity_score": economic_integrity,
        "constraint_log":           constraint_log,
        "constraint_dominant":      dominant_constraint,
        "critical_floors_applied":  floor_reasons,
        "extreme_cases_triggered":  extreme_reasons,
        "sector":                   sector,
    }
