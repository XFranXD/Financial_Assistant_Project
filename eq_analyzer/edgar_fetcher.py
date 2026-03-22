"""
edgar_fetcher.py
SEC EDGAR API client and XBRL data extractor for System 2.

Responsibilities:
- Ticker → CIK resolution with three-tier lookup:
    Tier 1: ticker_cik_cache.json (local, no network)
    Tier 2: company_tickers.json bulk file from SEC (authoritative mapping)
    Tier 3: EDGAR full-text search index (fallback only, less reliable)
- Company facts fetch from EDGAR /api/xbrl/companyfacts endpoint
- Time series extraction using edgar_concept_fallbacks.json vocabulary
- Date-intersection alignment across all metrics (prevents index misalignment)
- Staleness detection from submissions endpoint
- CIK cache read/write (ticker_cik_cache.json)
- Rate limiting at 0.25s per request

CRITICAL DESIGN NOTE — Date alignment:
EDGAR facts can have missing quarters for individual metrics.
Series must never be aligned by index. They must be aligned by date intersection.
The _align_by_date_intersection() method enforces this before returning the packet.
Modules receive pre-aligned arrays where index 0 of every metric is the same quarter.

Extraction strategy:
- Flow metrics (net_income, revenue, operating_cash_flow, capex):
    Strategy A: standalone quarterly entries (window 55-115 days, 10-Q and 10-K).
    Strategy B: YTD derivation — subtract consecutive YTD values to recover
                standalone quarters. Used when Strategy A yields < 6 entries.
- Instant metrics (balance sheet): accept 10-Q and 10-K, no window filter.

All series filtered to last 4 years before alignment to prevent ancient stale
entries from collapsing the date intersection.
"""

import json
import time
import logging
import requests
from datetime import datetime, date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Flow metrics use period windows (income statement, cash flow).
# Instant metrics use point-in-time dates (balance sheet).
FLOW_METRICS = {"net_income", "revenue", "operating_cash_flow", "capex"}

# Recency cutoff: reject series where all entries are older than this many years
RECENCY_YEARS = 4


class EdgarFetcher:
    """
    Fetches and parses EDGAR financial data for a given ticker.
    """

    def __init__(self, config: dict, fallbacks: dict):
        self.config = config["edgar"]
        self.staleness_config = config["staleness"]
        self.cache_path = Path(__file__).parent / "ticker_cik_cache.json"
        self.fallbacks = fallbacks
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.config["user_agent"],
            "Accept-Encoding": "gzip, deflate",
        })
        self._last_request_time = 0.0
        self._cik_cache = self._load_cik_cache()
        logger.debug(f"[EDGAR] EdgarFetcher initialized. CIK cache has {len(self._cik_cache)} entries.")

    # ------------------------------------------------------------------
    # PUBLIC ENTRY POINT
    # ------------------------------------------------------------------

    def fetch(self, ticker: str) -> Optional[dict]:
        """
        Full fetch pipeline for one ticker.
        Returns a data packet dict or None if CIK lookup or facts fetch fails.
        """
        logger.info(f"[EDGAR] Starting fetch for {ticker}")

        cik = self._resolve_cik(ticker)
        if not cik:
            logger.warning(f"[EDGAR] CIK lookup failed for {ticker}")
            return None

        facts = self._fetch_company_facts(cik)
        if not facts:
            logger.warning(f"[EDGAR] Company facts fetch failed for {ticker} (CIK {cik})")
            return None

        filing_date, filing_age_days = self._get_latest_filing_date(cik)
        staleness_tier = self._classify_staleness(filing_age_days)

        logger.info(
            f"[EDGAR] {ticker} latest filing: {filing_date} "
            f"({filing_age_days} days old, tier: {staleness_tier})"
        )

        if staleness_tier == "UNAVAILABLE":
            logger.warning(f"[EDGAR] {ticker} filing too stale ({filing_age_days}d). Skipping extraction.")
            return {
                "ticker": ticker,
                "cik": cik,
                "filing_date": str(filing_date) if filing_date else "unknown",
                "filing_age_days": filing_age_days,
                "staleness_tier": staleness_tier,
                "quarters_available": 0,
                "time_series": {},
                "tag_used": {},
                "missing_metrics": list(self.fallbacks.keys())
            }

        raw_series, tag_used, missing_metrics = self._extract_all_metrics(facts)
        aligned_series, shared_dates = self._align_by_date_intersection(raw_series)
        quarters_available = len(shared_dates)

        logger.info(
            f"[EDGAR] {ticker}: {quarters_available} aligned quarters across all metrics. "
            f"Missing metrics: {missing_metrics}"
        )

        return {
            "ticker": ticker,
            "cik": cik,
            "filing_date": str(filing_date) if filing_date else "unknown",
            "filing_age_days": filing_age_days,
            "staleness_tier": staleness_tier,
            "quarters_available": quarters_available,
            "time_series": aligned_series,
            "tag_used": tag_used,
            "missing_metrics": missing_metrics
        }

    def save_cik_cache(self):
        """Write updated CIK cache to disk."""
        try:
            with open(self.cache_path, "w") as f:
                json.dump(self._cik_cache, f, indent=2)
            logger.info(f"[EDGAR] CIK cache saved. {len(self._cik_cache)} entries.")
        except Exception as e:
            logger.warning(f"[EDGAR] Failed to save CIK cache: {e}")

    # ------------------------------------------------------------------
    # CIK RESOLUTION — THREE TIERS
    # ------------------------------------------------------------------

    def _resolve_cik(self, ticker: str) -> Optional[str]:
        ticker_upper = ticker.upper()

        if ticker_upper in self._cik_cache:
            cik = self._cik_cache[ticker_upper]
            logger.debug(f"[EDGAR] {ticker} CIK resolved from cache: {cik}")
            return cik

        cik = self._resolve_cik_from_bulk_file(ticker_upper)
        if cik:
            self._cik_cache[ticker_upper] = cik
            logger.debug(f"[EDGAR] {ticker} CIK resolved from company_tickers.json: {cik}")
            return cik

        cik = self._resolve_cik_from_search(ticker_upper)
        if cik:
            self._cik_cache[ticker_upper] = cik
            logger.debug(f"[EDGAR] {ticker} CIK resolved from search index: {cik}")
            return cik

        logger.warning(f"[EDGAR] All CIK resolution methods failed for {ticker}")
        return None

    def _resolve_cik_from_bulk_file(self, ticker: str) -> Optional[str]:
        self._rate_limit()
        try:
            url = self.config["company_tickers_url"]
            resp = self.session.get(url, timeout=self.config["request_timeout_seconds"])
            resp.raise_for_status()
            data = resp.json()
            for entry in data.values():
                if str(entry.get("ticker", "")).upper() == ticker:
                    return str(entry["cik_str"]).zfill(10)
        except Exception as e:
            logger.warning(f"[EDGAR] company_tickers.json lookup failed: {e}")
        return None

    def _resolve_cik_from_search(self, ticker: str) -> Optional[str]:
        self._rate_limit()
        try:
            url = self.config["cik_search_fallback_url"].replace("{ticker}", ticker)
            resp = self.session.get(url, timeout=self.config["request_timeout_seconds"])
            resp.raise_for_status()
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            for hit in hits:
                entity_id = hit.get("_source", {}).get("entity_id")
                if entity_id:
                    return str(entity_id).zfill(10)
        except Exception as e:
            logger.warning(f"[EDGAR] Search index CIK lookup failed for {ticker}: {e}")
        return None

    # ------------------------------------------------------------------
    # CIK CACHE
    # ------------------------------------------------------------------

    def _load_cik_cache(self) -> dict:
        try:
            if self.cache_path.exists():
                with open(self.cache_path) as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"[EDGAR] Could not load CIK cache: {e}")
        return {}

    # ------------------------------------------------------------------
    # COMPANY FACTS FETCH
    # ------------------------------------------------------------------

    def _fetch_company_facts(self, cik: str) -> Optional[dict]:
        self._rate_limit()
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        try:
            resp = self.session.get(url, timeout=self.config["request_timeout_seconds"])
            resp.raise_for_status()
            facts = resp.json()
            logger.debug(f"[EDGAR] Company facts fetched for CIK {cik}")
            return facts
        except Exception as e:
            logger.warning(f"[EDGAR] Company facts fetch failed for CIK {cik}: {e}")
            return None

    # ------------------------------------------------------------------
    # FILING DATE / STALENESS
    # ------------------------------------------------------------------

    def _get_latest_filing_date(self, cik: str) -> tuple[Optional[date], int]:
        self._rate_limit()
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        try:
            resp = self.session.get(url, timeout=self.config["request_timeout_seconds"])
            resp.raise_for_status()
            data = resp.json()
            filings = data.get("filings", {}).get("recent", {})
            forms = filings.get("form", [])
            dates = filings.get("filingDate", [])

            latest = None
            for form, filing_date_str in zip(forms, dates):
                if form in ("10-Q", "10-K"):
                    try:
                        d = datetime.strptime(filing_date_str, "%Y-%m-%d").date()
                        if latest is None or d > latest:
                            latest = d
                    except ValueError:
                        continue

            if latest:
                age = (date.today() - latest).days
                return latest, age
            else:
                logger.warning(f"[EDGAR] No 10-Q/10-K filings found for CIK {cik}")
                return None, 999

        except Exception as e:
            logger.warning(f"[EDGAR] Submissions fetch failed for CIK {cik}: {e}")
            return None, 999

    def _classify_staleness(self, age_days: int) -> str:
        cfg = self.staleness_config
        if age_days >= cfg["skip_threshold_days"]:
            return "UNAVAILABLE"
        elif age_days > cfg["warning_max_days"]:
            return "PENALTY"
        elif age_days > cfg["current_max_days"]:
            return "WARNING"
        else:
            return "CURRENT"

    # ------------------------------------------------------------------
    # METRIC EXTRACTION
    # ------------------------------------------------------------------

    def _recency_cutoff(self) -> str:
        """Return ISO date string for the recency cutoff (4 years ago)."""
        today = date.today()
        return str(today.replace(year=today.year - RECENCY_YEARS))

    def _extract_all_metrics(self, facts: dict) -> tuple[dict, dict, list]:
        """
        Extract raw quarterly series per metric using fallback vocabulary.
        Returns unaligned series — alignment happens in _align_by_date_intersection().
        """
        us_gaap = facts.get("facts", {}).get("us-gaap", {})
        raw_series = {}
        tag_used = {}
        missing_metrics = []
        cutoff = self._recency_cutoff()

        for metric_name, spec in self.fallbacks.items():
            candidates = [spec["primary"]] + spec.get("fallbacks", [])
            found = False
            is_flow = metric_name in FLOW_METRICS

            for tag in candidates:
                if tag not in us_gaap:
                    continue

                series = self._extract_quarterly_series(us_gaap[tag], spec["unit"], flow_metric=is_flow)

                if len(series) < 2:
                    logger.debug(f"[EDGAR] {metric_name}: tag {tag} only {len(series)} points — skipping")
                    continue

                # Reject series where most recent entry predates the recency cutoff
                if series[-1][0] < cutoff:
                    logger.debug(f"[EDGAR] {metric_name}: tag {tag} too old (most recent {series[-1][0]}) — trying fallback")
                    continue

                raw_series[metric_name] = series
                tag_used[metric_name] = tag
                logger.info(f"[EDGAR] {metric_name} → {tag} ({len(series)} raw quarters)")
                found = True
                break

            if not found:
                missing_metrics.append(metric_name)
                logger.warning(f"[EDGAR] {metric_name}: no usable tag found in any fallback")

        return raw_series, tag_used, missing_metrics

    def _extract_quarterly_series(self, concept_data: dict, unit: str, flow_metric: bool = False) -> list[tuple[str, float]]:
        """
        Extract quarterly values from a single EDGAR XBRL concept.

        For instant metrics (balance sheet):
            Accept 10-Q and 10-K, no window filter.

        For flow metrics (income statement, cash flow):
            Strategy A — standalone quarters: window 55-115 days, accept 10-Q and 10-K.
            Strategy B — YTD derivation: subtract consecutive YTD values to recover
                         standalone quarters. Used when Strategy A yields < 6 entries.

        All results filtered to last 4 years. Caps at 12 most recent entries.
        """
        units_data = concept_data.get("units", {}).get(unit, [])
        if not units_data:
            return []

        cutoff = self._recency_cutoff()

        if not flow_metric:
            # ── Instant metrics (balance sheet) ──────────────────────────
            quarterly = {}
            for entry in units_data:
                form = entry.get("form", "")
                if form not in ("10-Q", "10-K"):
                    continue
                end_date = entry.get("end", "")
                val = entry.get("val")
                if val is None or end_date == "":
                    continue
                if end_date < cutoff:
                    continue
                accn = entry.get("accn", "")
                if end_date not in quarterly or accn > quarterly[end_date][1]:
                    quarterly[end_date] = (float(val), accn)

            sorted_series = sorted(quarterly.items(), key=lambda x: x[0])
            return [(d, v_a[0]) for d, v_a in sorted_series][-12:]

        # ── Flow metrics ─────────────────────────────────────────────────
        # Strategy A: standalone quarterly entries (55-115 day window)
        standalone = {}
        for entry in units_data:
            form = entry.get("form", "")
            if form not in ("10-Q", "10-K"):
                continue
            end_date = entry.get("end", "")
            start_date = entry.get("start", "")
            val = entry.get("val")
            if val is None or end_date == "" or not start_date:
                continue
            if end_date < cutoff:
                continue
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d")
                window_days = (end - start).days
            except ValueError:
                continue
            if not (55 <= window_days <= 115):
                continue
            accn = entry.get("accn", "")
            if end_date not in standalone or accn > standalone[end_date][1]:
                standalone[end_date] = (float(val), accn)

        if len(standalone) >= 6:
            sorted_series = sorted(standalone.items(), key=lambda x: x[0])
            return [(d, v_a[0]) for d, v_a in sorted_series][-12:]

        # Strategy B: derive from YTD cumulative figures
        ytd_by_fiscal_year: dict = {}

        for entry in units_data:
            form = entry.get("form", "")
            if form not in ("10-Q", "10-K"):
                continue
            end_date = entry.get("end", "")
            start_date = entry.get("start", "")
            val = entry.get("val")
            if val is None or end_date == "" or not start_date:
                continue
            if end_date < cutoff:
                continue
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                window_days = (end_dt - start_dt).days
            except ValueError:
                continue

            # Accept YTD (55-290 days) and annual (340-380 days)
            if not (55 <= window_days <= 290 or 340 <= window_days <= 380):
                continue

            fiscal_year_start = start_date
            if fiscal_year_start not in ytd_by_fiscal_year:
                ytd_by_fiscal_year[fiscal_year_start] = {}
            accn = entry.get("accn", "")
            existing = ytd_by_fiscal_year[fiscal_year_start].get(end_date)
            if existing is None or accn > existing[1]:
                ytd_by_fiscal_year[fiscal_year_start][end_date] = (float(val), accn)

        # Subtract consecutive YTD values to get standalone quarters
        derived: dict = {}
        for fiscal_year_start, periods in ytd_by_fiscal_year.items():
            sorted_periods = sorted(periods.items(), key=lambda x: x[0])
            prev_val = 0.0
            for end_date, (val, accn) in sorted_periods:
                standalone_val = val - prev_val
                prev_val = val
                if end_date not in derived:
                    derived[end_date] = standalone_val

        if not derived:
            return []

        sorted_series = sorted(derived.items(), key=lambda x: x[0])
        result = [(d, v) for d, v in sorted_series if d >= cutoff]
        return result[-12:]

    # ------------------------------------------------------------------
    # DATE INTERSECTION ALIGNMENT
    # ------------------------------------------------------------------

    def _align_by_date_intersection(self, raw_series: dict) -> tuple[dict, list]:
        """
        Align all metric series by snapping instant (balance sheet) dates
        to the nearest flow metric date within a 45-day window.

        Strategy:
        1. Collect anchor dates from flow metrics
        2. Snap all instant metric dates to nearest anchor within 45 days
        3. Intersect on snapped dates
        4. Trim all series to shared dates
        """
        if not raw_series:
            return {}, []

        # Step 1 — anchor dates from flow metrics
        anchor_dates = set()
        for metric_name, series in raw_series.items():
            if metric_name in FLOW_METRICS:
                for d, _ in series:
                    anchor_dates.add(d)

        if not anchor_dates:
            for series in raw_series.values():
                for d, _ in series:
                    anchor_dates.add(d)

        sorted_anchors = sorted(anchor_dates)

        # Step 2 — snap instant metrics to nearest anchor
        def snap_to_anchor(date_str: str, anchors: list, window_days: int = 45) -> Optional[str]:
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return None
            best = None
            best_diff = window_days + 1
            for anchor_str in anchors:
                try:
                    a = datetime.strptime(anchor_str, "%Y-%m-%d").date()
                    diff = abs((d - a).days)
                    if diff <= window_days and diff < best_diff:
                        best_diff = diff
                        best = anchor_str
                except ValueError:
                    continue
            return best

        snapped_series = {}
        for metric_name, series in raw_series.items():
            if metric_name in FLOW_METRICS:
                snapped_series[metric_name] = series
            else:
                snapped: dict = {}
                for date_str, val in series:
                    snapped_date = snap_to_anchor(date_str, sorted_anchors)
                    if snapped_date and snapped_date not in snapped:
                        snapped[snapped_date] = val
                snapped_series[metric_name] = sorted(snapped.items(), key=lambda x: x[0])

        # Step 3 — intersect on snapped dates
        date_sets = {m: set(d for d, _ in s) for m, s in snapped_series.items()}
        all_date_sets = list(date_sets.values())
        shared = all_date_sets[0].copy()
        for ds in all_date_sets[1:]:
            shared &= ds

        shared_dates = sorted(shared)

        if not shared_dates:
            logger.warning("[EDGAR] Date intersection produced zero shared quarters after snapping")
            return {}, []

        # Step 4 — trim to shared dates
        aligned = {}
        for metric_name, series in snapped_series.items():
            series_dict = {d: v for d, v in series}
            aligned[metric_name] = [(d, series_dict[d]) for d in shared_dates if d in series_dict]

        logger.info(
            f"[EDGAR] Date alignment: {len(shared_dates)} shared quarters across "
            f"{len(raw_series)} metrics. Dates: {shared_dates[0]} → {shared_dates[-1]}"
        )

        return aligned, shared_dates

    # ------------------------------------------------------------------
    # RATE LIMITING
    # ------------------------------------------------------------------

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        wait = self.config["rate_limit_seconds"] - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_time = time.time()