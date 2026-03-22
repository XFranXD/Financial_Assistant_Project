"""
data_validator.py
Validates an edgar_packet before any module runs against it.

Checks:
- Staleness tier → determines if modules run, warn, penalize, or skip entirely
- Quarter count → enforces 6Q minimum, notes reduced window for 6–7Q
- Missing metrics → determines which modules are runnable
- Weight redistribution for skipped modules

Module data requirements define exactly which time_series keys each module needs.
Module 1 (cash_conversion) requires 'revenue' for CCR denominator stabilization.

Outputs a validated_packet dict ready for module consumption.
Debug logging: [VALIDATOR] prefix on all decisions.
"""

import logging

logger = logging.getLogger(__name__)

# Filing-type-aware staleness limits (Section 3 — SYSTEM2_AGENT_MASTER_PROMPT)
STALENESS_LIMITS = {
    "10-K":    365,
    "10-Q":    120,
    "8-K":      60,
    "default": 180,
}
MIN_QUARTERS_REQUIRED = 6


def _should_skip_staleness(filing_type: str, filing_age_days: int,
                            quarters_available: int) -> tuple:
    if quarters_available < MIN_QUARTERS_REQUIRED:
        return (True,
                f"Insufficient history: {quarters_available} quarters "
                f"(minimum {MIN_QUARTERS_REQUIRED} required)")
    limit = STALENESS_LIMITS.get(filing_type, STALENESS_LIMITS["default"])
    if filing_age_days > limit:
        return (True,
                f"Filing too old: {filing_age_days} days "
                f"(limit for {filing_type}: {limit} days)")
    logger.debug(
        f"[VALIDATOR] Staleness OK: type={filing_type} age={filing_age_days}d "
        f"limit={limit}d quarters={quarters_available}"
    )
    return False, ""

# Exact metrics required per module from the EDGAR time_series dict.
# earnings_timing is NOT in this dict — it is now a post-score modifier,
# not a composite module. It still runs via module_earnings_timing.py
# but its result feeds eq_scorer's modifier pipeline, not the weighted sum.
# dividend_stability fetches live data inside its own run() function.
MODULE_DATA_REQUIREMENTS = {
    "cash_conversion":      ["net_income", "operating_cash_flow", "revenue"],
    "accruals":             ["net_income", "operating_cash_flow", "total_assets"],
    "revenue_quality":      ["revenue", "accounts_receivable"],
    "long_term_trends":     ["revenue", "net_income", "total_assets"],
    "fcf_sustainability":   ["operating_cash_flow", "capex", "revenue"],
    "earnings_consistency": ["net_income"],
    "dividend_stability":   []    # fetched live from yfinance
}


def validate(edgar_packet: dict, config: dict) -> dict:
    """
    Validate an edgar_packet and produce a validated_packet.

    Returns a dict with keys:
        ticker, filing_date, filing_age_days, staleness_tier,
        staleness_penalty, skip_all, skip_reason,
        quarters_available, reduced_window_warning,
        runnable_modules (list), skipped_modules (list),
        skip_reasons (dict), adjusted_weights (dict),
        time_series (passthrough from edgar_packet)
    """
    ticker = edgar_packet["ticker"]
    staleness_tier = edgar_packet["staleness_tier"]
    quarters = edgar_packet["quarters_available"]
    time_series = edgar_packet["time_series"]
    data_cfg = config["data_requirements"]
    weight_cfg = config["scoring"]["weights"]

    logger.info(f"[VALIDATOR] Validating {ticker}: staleness={staleness_tier}, quarters={quarters}")

    # --- Staleness gate ---
    staleness_penalty = 0
    skip_all = False
    skip_reason = ""

    if staleness_tier == "UNAVAILABLE":
        logger.warning(f"[VALIDATOR] {ticker}: UNAVAILABLE — skipping all modules")
        skip_all = True
        skip_reason = "Filing unavailable — no data returned from SEC EDGAR"
    elif staleness_tier == "PENALTY":
        staleness_penalty = config["staleness"]["penalty_points"]
        logger.info(f"[VALIDATOR] {ticker}: PENALTY tier — -{staleness_penalty} points will be applied")

    # --- Quarter count gate ---
    reduced_window_warning = False
    if not skip_all and quarters < data_cfg["skip_below_quarters"]:
        logger.warning(
            f"[VALIDATOR] {ticker}: only {quarters} quarters available "
            f"(minimum {data_cfg['skip_below_quarters']}). Skipping all modules."
        )
        skip_all = True
        skip_reason = (
            f"Insufficient history: {quarters} quarters "
            f"(minimum {data_cfg['skip_below_quarters']} required)"
        )
    elif not skip_all and quarters < data_cfg["full_quarters"]:
        reduced_window_warning = True
        logger.info(
            f"[VALIDATOR] {ticker}: {quarters} quarters (reduced window). "
            f"Continuing with warning."
        )

    if skip_all:
        return _build_skip_packet(edgar_packet, staleness_penalty, quarters, skip_reason)

    # --- Per-module data availability check ---
    runnable_modules = []
    skipped_modules = []
    skip_reasons = {}

    for module, required_metrics in MODULE_DATA_REQUIREMENTS.items():
        missing = [
            m for m in required_metrics
            if m not in time_series or len(time_series[m]) < data_cfg["skip_below_quarters"]
        ]
        if missing:
            skipped_modules.append(module)
            skip_reasons[module] = f"Missing or insufficient metrics: {', '.join(missing)}"
            logger.warning(f"[VALIDATOR] {ticker}: {module} skipped — {skip_reasons[module]}")
        else:
            runnable_modules.append(module)
            logger.debug(f"[VALIDATOR] {ticker}: {module} is runnable")

    adjusted_weights = _redistribute_weights(runnable_modules, weight_cfg)
    logger.info(
        f"[VALIDATOR] {ticker}: runnable={runnable_modules}, "
        f"adjusted_weights={adjusted_weights}"
    )

    return {
        "ticker": ticker,
        "filing_date": edgar_packet["filing_date"],
        "filing_age_days": edgar_packet["filing_age_days"],
        "staleness_tier": staleness_tier,
        "staleness_penalty": staleness_penalty,
        "skip_all": False,
        "skip_reason": "",
        "quarters_available": quarters,
        "reduced_window_warning": reduced_window_warning,
        "runnable_modules": runnable_modules,
        "skipped_modules": skipped_modules,
        "skip_reasons": skip_reasons,
        "adjusted_weights": adjusted_weights,
        "time_series": time_series
    }


def _redistribute_weights(runnable: list, base_weights: dict) -> dict:
    """
    Redistribute base weights of skipped modules proportionally to runnable modules.
    If all modules are runnable, weights are returned unchanged.
    If no modules are runnable, returns empty dict.
    """
    if not runnable:
        return {}
    total = sum(base_weights[m] for m in runnable)
    if total == 0:
        return {m: 0.0 for m in runnable}
    return {m: base_weights[m] / total for m in runnable}


def _build_skip_packet(edgar_packet: dict, staleness_penalty: int,
                        quarters: int, skip_reason: str = "") -> dict:
    return {
        "ticker": edgar_packet["ticker"],
        "filing_date": edgar_packet.get("filing_date", "unknown"),
        "filing_age_days": edgar_packet["filing_age_days"],
        "staleness_tier": edgar_packet["staleness_tier"],
        "staleness_penalty": staleness_penalty,
        "skip_all": True,
        "skip_reason": skip_reason,
        "quarters_available": quarters,
        "reduced_window_warning": False,
        "runnable_modules": [],
        "skipped_modules": list(MODULE_DATA_REQUIREMENTS.keys()),
        "skip_reasons": {m: "All modules skipped" for m in MODULE_DATA_REQUIREMENTS},
        "adjusted_weights": {},
        "time_series": {}
    }