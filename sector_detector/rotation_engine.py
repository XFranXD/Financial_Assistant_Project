"""
rotation_engine.py — System 3 Sector Rotation Detector
Orchestrates all scorers and produces the final rotation result dict.

Single source of truth for SECTOR_ETF_MAP (never modified at runtime).
"""

from sector_detector.momentum_scorer import compute_momentum_score
from sector_detector.relative_strength_scorer import compute_relative_strength_score
from sector_detector.volume_scorer import compute_volume_score

SECTOR_ETF_MAP = {
    "technology":             "XLK",
    "healthcare":             "XLV",
    "financials":             "XLF",
    "consumer_discretionary": "XLY",
    "consumer_staples":       "XLP",
    "industrials":            "XLI",
    "materials":              "XLB",
    "energy":                 "XLE",
    "utilities":              "XLU",
    "real_estate":            "XLRE",
    "communication_services": "XLC",
    "semiconductors":         "SOXX",
    "defense":                "ITA",
}


def _skip_result(reason: str) -> dict:
    return {
        "rotation_score": None,
        "rotation_status": "SKIP",
        "momentum_score": None,
        "relative_strength_score": None,
        "volume_score": None,
        "data_confidence": "SKIP",
        "reasoning": reason,
    }


def compute_rotation(fetched_data: dict) -> dict:
    """
    Receives the full data_fetcher return structure, runs all scorers,
    and returns the raw engine result dict.
    """
    full_history = fetched_data["full_history"]
    tf_data = fetched_data["timeframes"]

    # ── SKIP propagation — check before any scoring ────────────────────────────
    if full_history["trading_days"] == 0:
        return _skip_result("ETF data unavailable")

    if all(not tf_data[tf]["available"] for tf in ["1M", "3M", "6M"]):
        return _skip_result("No timeframe data available")

    # ── Read availability flags directly from fetched_data ────────────────────
    ma_available = full_history["ma_available"]
    rsi_available = full_history["rsi_available"]
    slope_available = full_history["slope_available"]
    volume_sufficient = full_history["volume_sufficient"]

    # ── Step 1 — Run scorers ──────────────────────────────────────────────────
    momentum_score = compute_momentum_score(full_history, tf_data)
    relative_strength_score = compute_relative_strength_score(tf_data)
    volume_score = compute_volume_score(full_history, slope_available, volume_sufficient)

    # ── Compute rotation_score ─────────────────────────────────────────────────
    rotation_score = (momentum_score * 0.40) + (relative_strength_score * 0.40) + (volume_score * 0.20)

    # ── Step 2 — Single timeframe cap ─────────────────────────────────────────
    available_timeframes = [tf for tf in ["1M", "3M", "6M"] if tf_data[tf]["available"]]
    if len(available_timeframes) == 1:
        rotation_score = min(rotation_score, 60)

    # ── Step 3 — Classification with borderline stabilization ─────────────────
    # Evaluate in EXACT ORDER: borderline check first
    if 63 <= rotation_score <= 67:
        rotation_status = "NEUTRAL"
    elif rotation_score >= 65:
        rotation_status = "FAVORABLE"
    elif rotation_score >= 40:
        rotation_status = "NEUTRAL"
    else:
        rotation_status = "UNFAVORABLE"

    if rotation_status == "FAVORABLE":
        rotation_signal = "SUPPORT"
    elif rotation_status == "UNFAVORABLE":
        rotation_signal = "WEAKEN"
    elif rotation_status == "NEUTRAL":
        rotation_signal = "WAIT"
    elif rotation_status == "SKIP":
        rotation_signal = "UNKNOWN"
    else:
        rotation_signal = "UNKNOWN"

    # ── Step 4 — Data confidence (evaluate top-to-bottom, first match wins) ───
    missing_timeframes = sum(1 for tf in ["1M", "3M", "6M"] if not tf_data[tf]["available"])

    if missing_timeframes >= 2:
        data_confidence = "LOW"
    elif (
        missing_timeframes == 1
        or not volume_sufficient
        or not slope_available
        or not ma_available
    ):
        data_confidence = "MEDIUM"
    else:
        data_confidence = "HIGH"

    # ── Step 5 — Dominant factor identification ────────────────────────────────
    scores = {
        "momentum": momentum_score,
        "relative_strength": relative_strength_score,
        "volume": volume_score,
    }

    if rotation_status == "FAVORABLE":
        dominant_factor = max(scores, key=scores.get)
    elif rotation_status == "UNFAVORABLE":
        dominant_factor = min(scores, key=scores.get)
    else:  # NEUTRAL
        dominant_factor = max(scores, key=lambda k: abs(scores[k] - 50))

    # ── Step 6 — Reasoning generation ─────────────────────────────────────────
    if rotation_status == "FAVORABLE":
        reasoning = f"FAVORABLE rotation driven by strong {dominant_factor}."
    elif rotation_status == "UNFAVORABLE":
        reasoning = f"UNFAVORABLE rotation due to weak {dominant_factor}."
    else:
        reasoning = f"NEUTRAL rotation with mixed signals, led by {dominant_factor}."

    if data_confidence != "HIGH":
        reasoning += f" Data confidence is {data_confidence.lower()}."

    return {
        "rotation_score": rotation_score,
        "rotation_status": rotation_status,
        "rotation_signal": rotation_signal,
        "momentum_score": momentum_score,
        "relative_strength_score": relative_strength_score,
        "volume_score": volume_score,
        "data_confidence": data_confidence,
        "reasoning": reasoning,
    }
