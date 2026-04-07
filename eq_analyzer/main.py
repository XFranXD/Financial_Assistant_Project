"""
eq_analyzer/main.py — System 2 Submain
Called by System 1's main.py via run_eq_analyzer(tickers).
Returns normalized list of per-ticker result dicts. Never sends email,
never writes report files, never produces HTML.

RENDERING RULE: System 2 returns RAW DATA ONLY.
System 1 owns all rendering. No html_block is produced for System 1 consumption.
The text_block is retained only for standalone testing via __main__.

Pipeline per ticker:
    1. EDGAR fetch
    2. Data validation
    3. Module execution (M1-M7 composite)
    4. Earnings timing (post-score modifier)
    5. Composite scoring
    6. Batch percentile ranking (mutates results in-place, also returns list)
    7. Handoff dict construction via eq_handoff.py

Returns:
    List of normalized dicts. Each dict contains fields defined in
    contracts/eq_schema.py plus: ticker, passed, skipped, error, eq_result.
"""

import json
import logging
from pathlib import Path
from statistics import median

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent  # eq_analyzer/ directory

from eq_analyzer.edgar_fetcher import EdgarFetcher
from eq_analyzer.data_validator import validate
from eq_analyzer.eq_scorer import score
from eq_analyzer.eq_report_builder import (
    build_text_block,
    build_skip_block_text,
)
from eq_analyzer import module_cash_conversion
from eq_analyzer import module_accruals
from eq_analyzer import module_revenue_quality
from eq_analyzer import module_long_term_trends
from eq_analyzer import module_fcf_sustainability
from eq_analyzer import module_earnings_consistency
from eq_analyzer import module_earnings_timing
from eq_analyzer import module_dividend_stability

MODULE_RUNNERS = {
    "cash_conversion":      module_cash_conversion.run,
    "accruals":             module_accruals.run,
    "revenue_quality":      module_revenue_quality.run,
    "long_term_trends":     module_long_term_trends.run,
    "fcf_sustainability":   module_fcf_sustainability.run,
    "earnings_consistency": module_earnings_consistency.run,
    "earnings_timing":      module_earnings_timing.run,
    "dividend_stability":   module_dividend_stability.run,
}


def load_config() -> dict:
    path = ROOT_DIR / "config.json"
    logger.info(f"[EQ_ANALYZER] Loading config: {path}")
    with open(path) as f:
        return json.load(f)


def load_fallbacks() -> dict:
    path = ROOT_DIR / "edgar_concept_fallbacks.json"
    logger.info(f"[EQ_ANALYZER] Loading EDGAR fallbacks: {path}")
    with open(path) as f:
        return json.load(f)


def process_ticker(ticker: str, fetcher: EdgarFetcher, config: dict) -> dict:
    """
    Run full pipeline for one ticker.
    Never raises — all exceptions are caught and returned as error result.
    """
    logger.info(f"[EQ_ANALYZER] ── Processing {ticker} ──")

    # Step 1: EDGAR fetch
    edgar_packet = fetcher.fetch(ticker)
    if edgar_packet is None:
        logger.warning(f"[EQ_ANALYZER] {ticker}: EDGAR fetch returned None")
        return {
            "ticker": ticker, "error": "EDGAR fetch failed",
            "passed": False, "eq_score_final": 0,
            "text_block": f"{ticker}: Data unavailable — EDGAR fetch failed.",
        }

    # Step 2: Validation
    validated = validate(edgar_packet, config)

    # Step 3: Skip-all path
    if validated["skip_all"]:
        skip_reason = validated.get("skip_reason", "")
        text_block = build_skip_block_text(
            ticker, validated["filing_age_days"], validated["staleness_tier"],
            skip_reason=skip_reason
        )
        logger.info(
            f"[EQ_ANALYZER] {ticker}: skipped "
            f"(staleness={validated['staleness_tier']}, quarters={validated['quarters_available']})"
        )
        return {
            "ticker": ticker, "passed": False, "eq_score_final": 0,
            "filing_age_days": validated["filing_age_days"],
            "staleness_tier":  validated["staleness_tier"],
            "skip_reason":     skip_reason,
            "text_block": text_block, "skipped": True
        }

    # Step 4: Run composite modules (M1–M7, excluding earnings_timing)
    COMPOSITE_MODULE_NAMES = [
        "cash_conversion", "accruals", "revenue_quality", "long_term_trends",
        "fcf_sustainability", "earnings_consistency", "dividend_stability"
    ]
    LIVE_FETCH_MODULES = {"dividend_stability"}

    module_results = []
    for module_name in validated["runnable_modules"]:
        if module_name not in COMPOSITE_MODULE_NAMES:
            continue  # earnings_timing handled separately below
        runner = MODULE_RUNNERS[module_name]
        try:
            if module_name in LIVE_FETCH_MODULES:
                result = runner(
                    validated["time_series"],
                    validated["quarters_available"],
                    ticker=ticker,
                    config=config
                )
            elif module_name == "long_term_trends":
                result = runner(
                    validated["time_series"],
                    validated["quarters_available"],
                    config=config
                )
            else:
                result = runner(validated["time_series"], validated["quarters_available"])
            module_results.append(result)
            logger.info(
                f"[EQ_ANALYZER] {ticker}: {module_name} → score={result['score']}, "
                f"flag={result['flag']}, anomaly={result.get('anomaly_triggered', False)}"
            )
        except Exception as e:
            logger.error(f"[EQ_ANALYZER] {ticker}: {module_name} exception: {e}")
            module_results.append({
                "module_name": module_name, "score": 50.0, "label": "ACCEPTABLE",
                "flag": None, "trend": "flat", "plain_english": "Module error — neutral score.",
                "not_applicable": False, "unknown": False, "anomaly_triggered": False,
                "debug": {"error": str(e)}
            })

    # Step 4b: Run earnings_timing as post-score modifier (not composite)
    timing_result = None
    try:
        timing_result = MODULE_RUNNERS["earnings_timing"](
            validated["time_series"],
            validated["quarters_available"],
            ticker=ticker,
            config=config
        )
        logger.info(
            f"[EQ_ANALYZER] {ticker}: earnings_timing → "
            f"days={timing_result.get('debug', {}).get('days_to_earnings')}, "
            f"unknown={timing_result.get('unknown', False)}"
        )
    except Exception as e:
        logger.error(f"[EQ_ANALYZER] {ticker}: earnings_timing exception: {e}")
        timing_result = None

    # Step 5: Composite score (timing_result is post-score modifier)
    sector = config.get("sector_overrides", {}).get(ticker.upper(), "default")
    eq_result = score(module_results, validated, config, timing_result=timing_result, sector=sector)

    return {
        "ticker":         ticker,
        "passed":         eq_result["passed"],
        "eq_score_final": eq_result["eq_score_final"],
        "eq_result":      eq_result,
        "module_results": module_results,
        "skipped":        False
    }


def compute_batch_percentile_ranks(results: list) -> list:
    """
    Assigns eq_percentile to each non-skipped result based on eq_score_final.
    Percentile = percent of candidates with equal or lower score.
    Also attaches batch_regime label (WEAK / NORMAL / STRONG BATCH).
    NOTE: mutates results in-place AND returns the list.
    Always use as: results = compute_batch_percentile_ranks(results)
    """
    scored = [
        r for r in results
        if "eq_result" in r and not r.get("skipped") and not r.get("error")
    ]
    if not scored:
        return results

    scores = [r["eq_result"]["eq_score_final"] for r in scored]
    batch_median = median(scores)

    if batch_median >= 70:   batch_regime = "STRONG BATCH"
    elif batch_median >= 50: batch_regime = "NORMAL BATCH"
    else:                    batch_regime = "WEAK BATCH"

    for r in scored:
        eq = r["eq_result"]["eq_score_final"]
        pct = round(sum(1 for s in scores if s < eq) / len(scores) * 100)
        r["eq_result"]["eq_percentile"]   = pct
        r["eq_result"]["batch_regime"]     = batch_regime
        r["eq_result"]["batch_median"]     = round(batch_median, 1)
        logger.debug(f"[EQ_ANALYZER] {r['ticker']}: eq_percentile={pct}th batch_regime={batch_regime}")

    logger.info(
        f"[EQ_ANALYZER] Batch: n={len(scored)} median={batch_median:.1f} regime={batch_regime}"
    )
    return results


def normalize_result(r: dict) -> dict:
    """
    Enforces output shape at the submain boundary.
    Guarantees System 1 never receives missing keys from System 2.
    Called on every result before returning from run_eq_analyzer.

    combined_priority_score is a handoff-level field computed by eq_handoff.py
    and attached directly to the top-level result dict — not nested inside
    eq_result. Always read it from eq (top-level), never from eq_result.

    eq_result uses `or {}` not `default={}` to handle explicit None values.
    """
    return {
        "ticker":                  r.get("ticker", ""),
        "eq_result":               r.get("eq_result") or {},
        "passed":                  r.get("passed", False),
        "skipped":                 r.get("skipped", False),
        "error":                   r.get("error", None),
        "combined_priority_score": r.get("combined_priority_score", 0),
        "text_block":              r.get("text_block", ""),
    }


def run_eq_analyzer(tickers: list) -> list:
    """
    Entry point called by System 1's main.py.
    Accepts list of ticker strings.
    Returns normalized list of result dicts — one per ticker.
    Never raises — all exceptions caught per ticker and returned as error result.
    """
    logger.info(f"[EQ_ANALYZER] Starting run for {len(tickers)} tickers: {tickers}")

    try:
        config    = load_config()
        fallbacks = load_fallbacks()
    except Exception as e:
        logger.critical(f"[EQ_ANALYZER] Fatal: failed to load config or fallbacks: {e}")
        return [normalize_result({"ticker": t, "passed": False,
                                  "error": "config load failed"}) for t in tickers]

    fetcher = EdgarFetcher(config, fallbacks)
    results = []

    for ticker in tickers:
        try:
            result = process_ticker(ticker, fetcher, config)
            results.append(result)
        except Exception as e:
            logger.error(f"[EQ_ANALYZER] Unhandled exception for {ticker}: {e}")
            results.append({
                "ticker": ticker, "passed": False,
                "eq_score_final": 0, "error": str(e)
            })

    fetcher.save_cik_cache()

    # Mutates in-place and returns list — always assign back
    results = compute_batch_percentile_ranks(results)

    # Rebuild text_block after percentiles assigned (for standalone testing only)
    for r in results:
        if (
            "eq_result" in r
            and r.get("eq_result")
            and not r.get("skipped")
            and not r.get("error")
            and "module_results" in r
        ):
            r["text_block"] = build_text_block(r["eq_result"], r["module_results"])

    # Enforce output shape at boundary before returning to System 1
    results = [normalize_result(r) for r in results]

    logger.info(
        f"[EQ_ANALYZER] Run complete. "
        f"{sum(1 for r in results if r.get('passed'))} passed / {len(results)} total"
    )
    return results


# Standalone testing only — not used by System 1
if __name__ == "__main__":
    import argparse
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", type=str)
    args = parser.parse_args()
    tickers = [t.strip().upper() for t in args.tickers.split(",")
               if t.strip()] if args.tickers else []
    results = run_eq_analyzer(tickers)
    for r in results:
        print(r.get("text_block") or r.get("ticker"))
