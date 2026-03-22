"""
eq_handoff.py
Assembles the System 1 handoff dict from a completed eq_result.
System 1 uses final_classification and combined_priority_score for routing.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SYSTEM1_SCORE_WEIGHT = 0.60
SYSTEM2_EQ_WEIGHT    = 0.40

CONFIDENCE_MULTIPLIERS = {
    "HIGH":        1.00,
    "MODERATE":    0.95,
    "LOW":         0.85,
    "UNRELIABLE":  0.70,
}


def build_eq_handoff(eq_result: dict, system1_score: float = None) -> dict:
    """
    Assembles the System 1 handoff dict from a completed eq_result.

    system1_score: System 1's candidate score normalized to 0–100.
                   If None, eq_score_final is used as fallback.

    combined_priority_score incorporates data_confidence as a multiplier
    so uncertainty is reflected in the combined routing score.
    """
    eq_score      = eq_result.get("eq_score_final", 0.0)
    confidence    = eq_result.get("data_confidence", "MODERATE")
    multiplier    = CONFIDENCE_MULTIPLIERS.get(confidence, 1.00)
    s1            = system1_score if system1_score is not None else eq_score
    raw_combined  = (s1 * SYSTEM1_SCORE_WEIGHT) + (eq_score * SYSTEM2_EQ_WEIGHT)
    combined      = round(max(0.0, min(100.0, raw_combined * multiplier)), 1)

    logger.debug(
        f"[HANDOFF] {eq_result['ticker']} s1={s1:.1f} eq={eq_score:.1f} "
        f"conf={confidence} mult={multiplier} → combined={combined}"
    )

    return {
        "ticker":                  eq_result["ticker"],
        "run_timestamp":           datetime.utcnow().isoformat(),
        "eq_score_raw":            eq_result.get("eq_score_raw", 0.0),
        "eq_score_final":          eq_score,
        "eq_label":                eq_result.get("eq_label", eq_result.get("band_label", "")),
        "eq_modifier":             eq_result.get("eq_modifier"),
        "pass_tier":               eq_result.get("pass_tier", "WATCH"),
        "final_classification":    eq_result.get("final_classification", "REVIEW"),
        "warning_score":           eq_result.get("warning_score", 0.0),
        "active_flags":            eq_result.get("active_flags", []),
        "top_risks":               eq_result.get("top_risks", []),
        "top_strengths":           eq_result.get("top_strengths", []),
        "data_reliability":        eq_result.get("data_reliability", 0.0),
        "data_confidence":         confidence,
        "score_confidence":        eq_result.get("score_confidence", "MODERATE"),
        "modules_executed":        len(eq_result.get("module_scores", {})),
        "critical_metrics_missing": eq_result.get("critical_metrics_missing", False),
        "economic_integrity_score": eq_result.get("economic_integrity_score"),
        "constraint_dominant":     eq_result.get("constraint_dominant"),
        "fatal_flaw_reason":       eq_result.get("fatal_flaw_reason"),
        "eq_percentile":           eq_result.get("eq_percentile", 50),
        "filing_date":             eq_result.get("filing_date", ""),
        "filing_age_days":         eq_result.get("filing_age_days", 0),
        "staleness_tier":          eq_result.get("staleness_tier", "OK"),
        "combined_priority_score": combined,
        "sector":                  eq_result.get("sector", "default"),
    }
