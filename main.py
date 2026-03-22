"""
main.py — Pipeline Orchestrator. Entry point for automated runs.
Implements all 32 pipeline steps from §22 in strict order.

DISCLAIMER: This system does NOT perform trading, does NOT give investment advice,
and does NOT make price predictions. It is a research data aggregation and scoring
tool only. This disclaimer appears in every generated report and email.
"""

import json
import os
import sys
from datetime import datetime

import pytz

from config import (
    VALIDATED_TICKERS_FILE,
    SECTOR_TICKERS_FILE,
    SECTOR_BREADTH_STOCKS_FILE,
    CLOSING_SLOT,
    TIMEZONE,
    RUN_SLOTS,
    COMPOSITE_CONFIDENCE_MIN,
    VALIDATED_TICKER_MAX_AGE_DAYS,
    AV_DAILY_BUDGET,
    ALPHA_VANTAGE_API_KEY,
)
from utils.logger import get_logger
from utils.state_manager import load_state, save_state, mark_slot_complete, add_reported_companies

log = get_logger('main')

from eq_analyzer.main import run_eq_analyzer
from contracts.eq_schema import (
    EQ_SCORE_FINAL, EQ_LABEL, PASS_TIER, FINAL_CLASSIFICATION,
    TOP_RISKS, TOP_STRENGTHS, WARNINGS, DATA_CONFIDENCE,
    COMBINED_PRIORITY_SCORE, EQ_PERCENTILE, BATCH_REGIME,
    EQ_AVAILABLE, FATAL_FLAW_REASON,
)

DISCLAIMER = (
    'DISCLAIMER: This system does NOT perform trading, does NOT give investment advice, '
    'and does NOT make price predictions. It is a research data aggregation and scoring tool only.'
)


# ── Step helpers ────────────────────────────────────────────────────────────

def _load_json(path: str, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log.error(f'Cannot load {path}: {e}')
        return default if default is not None else {}


def _determine_slot() -> str | None:
    """
    Identifies which scheduled run slot we are in.
    Each slot is defined as a range 'HH:MM-HH:MM'.
    Returns the matching slot string or None if outside all windows.
    """
    now_et = datetime.now(pytz.timezone(TIMEZONE))
    current_minutes = now_et.hour * 60 + now_et.minute
    for slot in RUN_SLOTS:
        start_str, end_str = slot.split('-')
        sh, sm = map(int, start_str.split(':'))
        eh, em = map(int, end_str.split(':'))
        start_minutes = sh * 60 + sm
        end_minutes   = eh * 60 + em
        if start_minutes <= current_minutes <= end_minutes:
            return slot
    return None


def _is_market_open() -> bool:
    """Returns True on weekdays. Full market-open check via slot schedule is sufficient."""
    now_et = datetime.now(pytz.timezone(TIMEZONE))
    return now_et.weekday() < 5  # Mon-Fri


def _check_validated_file():
    """Step 1: Exit with code 1 if validated tickers file is missing."""
    if not os.path.exists(VALIDATED_TICKERS_FILE):
        log.critical(
            f'CRITICAL: {VALIDATED_TICKERS_FILE} not found.\n'
            'Run: python validate_tickers.py  before first deploy.'
        )
        sys.exit(1)

    # Warn if stale (>30 days)
    try:
        data = _load_json(VALIDATED_TICKERS_FILE, {})
        validated_date = data.get('validated_date', '')
        if validated_date:
            age = (datetime.now(pytz.utc).date() -
                   datetime.strptime(validated_date, '%Y-%m-%d').date()).days
            if age > VALIDATED_TICKER_MAX_AGE_DAYS:
                log.warning(
                    f'Validated tickers file is {age} days old (limit {VALIDATED_TICKER_MAX_AGE_DAYS}). '
                    f'Consider re-running validate_tickers.py.'
                )
    except Exception as e:
        log.warning(f'Could not check validated file age: {e}')


# ── Alpha Vantage fetcher (called from Step 17) ────────────────────────────

def _fetch_av_data(ticker: str, state: dict) -> dict | None:
    """Fetches Alpha Vantage overview if budget allows. Returns None on skip."""
    if state.get('alpha_vantage_calls_today', 0) >= AV_DAILY_BUDGET:
        log.info(f'AV budget exhausted — skipping AV for {ticker}')
        return None
    if not ALPHA_VANTAGE_API_KEY:
        return None

    import requests
    from utils.retry import retry_on_failure

    @retry_on_failure(max_attempts=2, delay=2.0)
    def _call():
        url    = 'https://www.alphavantage.co/query'
        params = {'function': 'OVERVIEW', 'symbol': ticker, 'apikey': ALPHA_VANTAGE_API_KEY}
        resp   = requests.get(url, params=params, timeout=10)
        body   = resp.json()
        # Detect rate limit in body (HTTP 200 but contains limit message)
        if 'Information' in body or 'Note' in body:
            state['alpha_vantage_calls_today'] = AV_DAILY_BUDGET  # mark exhausted
            save_state(state)
            return None
        if 'Error Message' in body:
            log.warning(f'AV error for {ticker}: {body.get("Error Message")}')
            return None
        return {
            'market_cap':    float(body.get('MarketCapitalization', 0) or 0) or None,
            'debt_to_equity': float(body.get('DebtToEquityRatio', 0) or 0) or None,
            'profit_margin':  float(body.get('ProfitMargin', 0) or 0) * 100 if body.get('ProfitMargin') else None,
            'eps_ttm':        float(body.get('EPS', 0) or 0) or None,
        }
    return _call()


# ── Main pipeline ──────────────────────────────────────────────────────────

def run():
    log.info('=' * 60)
    log.info('AUTOMATED STOCK RESEARCH SYSTEM — starting run')
    log.info(DISCLAIMER)
    log.info('=' * 60)

    # ── Time gate — skip ghost triggers from dual DST crons ───────────────
    # workflow_dispatch runs bypass this check intentionally.
    if os.environ.get('GITHUB_EVENT_NAME') == 'schedule':
        now_et = datetime.now(pytz.timezone(TIMEZONE))
        slot_match = _determine_slot()
        if slot_match is None:
            log.info(
                f'[SCHEDULER] Current ET time {now_et.strftime("%H:%M")} '
                f'is outside all scheduled windows — exiting.'
            )
            sys.exit(0)
        log.info(f'[SCHEDULER] Time gate passed — matched slot {slot_match}')
    # ── End time gate ─────────────────────────────────────────────────────

    # ── Step 1: Startup check ──────────────────────────────────────────────
    _check_validated_file()

    # ── Step 2: Determine run slot ────────────────────────────────────────
    slot = _determine_slot()
    if slot is None:
        # GitHub Actions sends duplicate cron entries for DST — pick first slot match
        slot = RUN_SLOTS[0]
        log.warning(f'Could not determine slot from time — defaulting to {slot}')
    log.info(f'Run slot: {slot}')

    # ── Step 3: Load state, check market open, check duplicate slot ────────
    state = load_state()
    # if not _is_market_open():
    #     log.info('Market closed (weekend) — exiting')
    #     sys.exit(0)

    if state['runs'].get(slot, {}).get('status') == 'complete':
        log.info(f'Slot {slot} already complete today — exiting')
        sys.exit(0)

    # ── Step 4: Fetch index snapshot ──────────────────────────────────────
    from collectors.market_collector import get_index_snapshot
    indices = get_index_snapshot()
    state['indices_today'] = indices
    save_state(state)

    # ── Step 5: VIX regime ────────────────────────────────────────────────
    from analyzers.market_regime import get_regime
    regime = get_regime()
    log.info(f'Regime: {regime["regime"]} vix={regime["vix"]}')

    # ── Step 6: Daily advance/decline breadth ─────────────────────────────
    from analyzers.market_breadth import compute_market_breadth
    breadth = compute_market_breadth()
    state['breadth_score_today'] = breadth['breadth_score']
    save_state(state)

    # ── Step 7: Sector MA breadth ─────────────────────────────────────────
    from analyzers.sector_breadth_ma import compute_sector_breadth_ma
    breadth_stocks = _load_json(SECTOR_BREADTH_STOCKS_FILE, {})
    breadth_stocks.pop('_comment', None)
    sector_breadth_ma = compute_sector_breadth_ma(breadth_stocks)
    state['sector_breadth_ma_today'] = sector_breadth_ma
    save_state(state)

    # ── Step 8: Sector momentum ───────────────────────────────────────────
    from analyzers.sector_momentum import compute_sector_momentum, get_sector_pe, get_sector_median_return
    sector_scores = compute_sector_momentum()
    state['sector_scores_today'] = {s: sector_scores[s]['score'] for s in sector_scores}
    save_state(state)

    # ── Step 9: Sector rotation speed ────────────────────────────────────
    from analyzers.sector_rotation_speed import compute_rotation_speed
    rotation = compute_rotation_speed(sector_scores)

    # ── Step 10: Collect news ─────────────────────────────────────────────
    from collectors.news_collector import collect_news
    articles, candidate_sectors = collect_news()
    log.info(f'News: {len(articles)} articles, {len(candidate_sectors)} candidate sectors')

    # If no candidate sectors were found, write empty report and exit
    if not candidate_sectors:
        log.info('No candidate sectors — writing empty report')
        _write_empty_report(slot, state, indices, breadth)
        state = mark_slot_complete(state, slot)
        save_state(state)
        sys.exit(0)

    # ── Step 11: Keyword scoring already done in collect_news() ───────────

    # ── Step 12: Apply event recency decay ───────────────────────────────
    from analyzers.event_detector import detect_events, summarise_sector_events
    event_map     = detect_events(articles)
    e2s_data      = _load_json('data/event_to_sector.json', {})
    sector_events = summarise_sector_events(event_map, e2s_data)
    state['event_scores_today'] = {k: v['total_adjusted'] for k, v in sector_events.items()}
    save_state(state)

    # ── Step 13: News impact scoring gate ────────────────────────────────
    from analyzers.news_impact_scorer import filter_sectors_by_impact
    impact_filtered = filter_sectors_by_impact(candidate_sectors)

    # ── Step 14: Momentum gate — top 5 only ──────────────────────────────
    momentum_filtered = {
        s: v for s, v in impact_filtered.items()
        if sector_scores.get(s, {}).get('top5', False)
    }
    log.info(f'Momentum gate: {len(impact_filtered)} → {len(momentum_filtered)} sectors')

    # ── Step 15: ETF 3-signal + multi-timeframe confirmation ─────────────
    from analyzers.sector_validator import validate_sector
    from analyzers.sector_mapper import map_events_to_sectors

    confirmed_sectors: dict[str, dict] = {}
    detected_event_types = list(event_map.keys())
    sector_impacts = map_events_to_sectors(detected_event_types)

    for sector in momentum_filtered:
        direction    = sector_impacts.get(sector, {}).get('direction', 'positive')
        validation   = validate_sector(sector, direction)
        if validation['confirmed']:
            confirmed_sectors[sector] = {
                **momentum_filtered[sector],
                'direction':  direction,
                'validation': validation,
            }
        else:
            log.info(f'Sector {sector}: ETF confirmation failed')

    if not confirmed_sectors:
        log.info('No sectors confirmed — writing empty report')
        _write_empty_report(slot, state, indices, breadth)
        state = mark_slot_complete(state, slot)
        save_state(state)
        sys.exit(0)

    log.info(f'Confirmed sectors: {list(confirmed_sectors.keys())}')

    # ── Steps 16-27: Per-company analysis ────────────────────────────────
    validated_data = _load_json(VALIDATED_TICKERS_FILE, {})
    validated_sectors = validated_data.get('sectors', {})

    from collectors.financial_parser import get_financials, enrich_with_alpha_vantage
    from filters.candidate_filter import passes_candidate_filter
    from analyzers.volume_confirmation import compute_volume_confirmation
    from analyzers.unusual_volume import detect_unusual_volume
    from analyzers.risk_adjusted_momentum import compute_risk_adjusted_momentum
    from analyzers.multi_timeframe_momentum import compute_mtf_momentum
    from analyzers.trend_stability import compute_trend_stability
    from analyzers.drawdown_risk import compute_drawdown_risk
    from analyzers.risk_model import compute_risk_score
    from analyzers.opportunity_model import compute_opportunity_score, compute_composite_confidence
    from analyzers.signal_agreement import compute_signal_agreement, sector_rank_to_score

    all_candidates: list[dict] = []

    for sector, sector_data in confirmed_sectors.items():
        sector_ticker_list = validated_sectors.get(sector, [])
        if not sector_ticker_list:
            log.warning(f'No validated tickers for sector {sector}')
            continue

        # Get sector context
        sector_pe           = get_sector_pe(sector)
        sector_median_ret   = get_sector_median_return(sector)
        etf_return          = sector_scores.get(sector, {}).get('ret5d')
        bma                 = sector_breadth_ma.get(sector, {})
        bma_score           = bma.get('breadth_ma_score', 0.5)
        sector_momentum_val = sector_scores.get(sector, {}).get('score', 0)
        sector_rank         = sector_scores.get(sector, {}).get('rank', 13)

        for ticker_entry in sector_ticker_list:
            ticker = ticker_entry['ticker'] if isinstance(ticker_entry, dict) else ticker_entry

            # ── Step 17: Dedup + financials ──────────────────────────────
            fin = get_financials(ticker)

            # ── Step 18: Candidate filter ─────────────────────────────────
            ok, reason = passes_candidate_filter(
                ticker, fin, sector, state.get('reported_companies', [])
            )
            log.info(f'DEBUG filter {ticker}: ok={ok} reason={reason}')
            if not ok:
                continue

            # AV enrichment if budget allows
            av_data = _fetch_av_data(ticker, state)
            if av_data:
                state['alpha_vantage_calls_today'] = state.get('alpha_vantage_calls_today', 0) + 1
                save_state(state)
                fin = enrich_with_alpha_vantage(ticker, av_data, fin)

            # ── Step 19: Volume + unusual volume ─────────────────────────
            vol_result = compute_volume_confirmation(ticker)
            uv_result  = detect_unusual_volume(ticker, vol_result.get('volume_ratio'))
            if uv_result['unusual_flag']:
                state['unusual_volume_flags'].append(ticker)
                save_state(state)

            # ── Step 20: Momentum ─────────────────────────────────────────
            ram_result = compute_risk_adjusted_momentum(ticker)
            mtf_result = compute_mtf_momentum(ticker)

            # ── Step 21: Stability + drawdown ─────────────────────────────
            stability_result = compute_trend_stability(ticker)
            dd_result        = compute_drawdown_risk(ticker)

            # ── Step 22: Risk score ───────────────────────────────────────
            risk_result = compute_risk_score(fin, regime, dd_result.get('drawdown_score'))

            # ── Step 23: Opportunity score ────────────────────────────────
            opp_result = compute_opportunity_score(
                fin,
                regime,
                breadth,
                sector_pe,
                sector_median_ret,
                ram_result.get('ram_score'),
                mtf_result.get('mtf_score'),
                vol_result.get('volume_score'),
                bma_score,
                etf_return,
            )

            # ── Step 24: Signal agreement ─────────────────────────────────
            sec_str       = sector_rank_to_score(sector_rank)
            norm_ev_score = min(1.0, sector_events.get(sector, {}).get('total_adjusted', 0) / 20.0)
            agreement     = compute_signal_agreement(
                momentum_score  = ram_result.get('ram_score', 0.5),
                sector_strength = sec_str,
                event_score     = norm_ev_score,
                volume_score    = vol_result.get('volume_score', 0.5),
            )

            # ── Step 25: Composite confidence ─────────────────────────────
            conf_result = compute_composite_confidence(
                risk_score            = risk_result['risk_score'],
                opportunity_score     = opp_result['opportunity_score'],
                agreement_score       = agreement['agreement_score'],
                sector_momentum_score = sector_momentum_val,
            )

            # ── Step 26: Exclude below confidence minimum ─────────────────
            log.info(f'DEBUG confidence {ticker}: conf={conf_result["composite_confidence"]} min={COMPOSITE_CONFIDENCE_MIN} risk={risk_result["risk_score"]} opp={opp_result["opportunity_score"]}')
            if conf_result['composite_confidence'] < COMPOSITE_CONFIDENCE_MIN:
                log.info(
                    f'{ticker}: confidence {conf_result["composite_confidence"]} '
                    f'< {COMPOSITE_CONFIDENCE_MIN} — excluded'
                )
                continue

            # ── Assemble candidate dict ───────────────────────────────────
            candidate = {
                'ticker':              ticker,
                'sector':              sector,
                'company_name':        ticker,   # enriched later from yf info if available
                'current_price':       fin.get('current_price'),
                'financials':          fin,
                'risk_score':          risk_result['risk_score'],
                'risk_label':          risk_result['risk_label'],
                'risk_components':     risk_result['components'],
                'opportunity_score':   opp_result['opportunity_score'],
                'bucket_scores':       opp_result['bucket_scores'],
                'agreement_score':     agreement['agreement_score'],
                'agreement_label':     agreement['label'],
                'composite_confidence': conf_result['composite_confidence'],
                'confidence_label':    conf_result['confidence_label'],
                'volume_confirmation': vol_result,
                'unusual_volume':      uv_result,
                'ram':                 ram_result,
                'mtf':                 mtf_result,
                'trend_stability':     stability_result,
                'drawdown':            dd_result,
                'earnings_warning':    risk_result.get('earnings_warning', False),
                'divergence_warning':  risk_result.get('divergence_warning', False),
                'sector_rank':         sector_rank,
                'sector_data':         sector_data,
                'rotation':            rotation.get(sector, {}),
                'disclaimer':          DISCLAIMER,
            }
            all_candidates.append(candidate)

    # ── Step 27: Z-score ranking ──────────────────────────────────────────
    from analyzers.zscore_ranker import rank_candidates
    from collections import defaultdict
    for _c in all_candidates:
        log.info(f"DEBUG candidate: {_c.get('ticker')} risk={_c.get('risk_score')} opp={_c.get('opportunity_score')} cap={regime['risk_cap']}")
    ranked_companies = rank_candidates(all_candidates, regime['risk_cap'])
    log.info(f'Post-ranking count: {len(ranked_companies)}')

    # ── Step 27b: Within-industry deduplication ─────────────────────────────
    # Keep top 2 per industry subgroup.
    # Sort by composite_confidence (primary) then r3m from mtf dict (secondary).
    # Industry key is in candidate['financials']['industry'] - access via .get().
    industry_groups: dict = defaultdict(list)
    for _c in ranked_companies:
        _industry = _c.get('financials', {}).get('industry', 'Unknown')
        industry_groups[_industry].append(_c)

    deduplicated: list = []
    for _industry, _group in industry_groups.items():
        _sorted = sorted(
            _group,
            key=lambda c: (
                c.get('composite_confidence', 0),
                c.get('mtf', {}).get('r3m', 0) or 0,
            ),
            reverse=True,
        )
        deduplicated.extend(_sorted[:2])
        _kept = [c.get('ticker') for c in _sorted[:2]]
        _dropped = [c.get('ticker') for c in _sorted[2:]]
        if _dropped:
            log.info(f'Industry dedup [{_industry}]: kept={_kept} dropped={_dropped}')

    # Re-sort by composite_confidence to restore overall ranking order
    deduplicated.sort(key=lambda c: c.get('composite_confidence', 0), reverse=True)

    final_companies = deduplicated
    log.info(f'Final company count after industry dedup: {len(final_companies)}')

    # ── Step 27c: Score stability filter ─────────────────────────────────
    # First appearance today: always allowed.
    # Subsequent appearance: current confidence must be >= prior slot confidence.
    today_prior_scores = state.get('today_scores', {})
    stable_companies: list = []
    for _c in final_companies:
        _ticker       = _c.get('ticker', '')
        _current_conf = _c.get('composite_confidence', 0)
        _prior_conf   = today_prior_scores.get(_ticker)

        if _prior_conf is None:
            stable_companies.append(_c)
            log.debug(f'score_stability: {_ticker} first appearance - allowed (score {_current_conf})')
        elif _current_conf >= _prior_conf:
            stable_companies.append(_c)
            log.debug(f'score_stability: {_ticker} stable/improving ({_prior_conf} -> {_current_conf}) - allowed')
        else:
            log.info(f'score_stability: {_ticker} suppressed - score declined ({_prior_conf} -> {_current_conf})')

    final_companies = stable_companies
    log.info(f'Final company count after score stability filter: {len(final_companies)}')

    # ── Step 27d: Earnings Quality enrichment ────────────────────────────
    # Run System 2 (EQ Analyzer) against all final candidates.
    # System 2 returns raw data only. System 1 owns all rendering.
    # combined_priority_score is available as a secondary signal but does
    # NOT replace or reorder System 1's composite_confidence ranking.
    try:
        eq_tickers = [c['ticker'] for c in final_companies if c.get('ticker')]
        if eq_tickers:
            log.info(f'[EQ] Running earnings quality analysis on {len(eq_tickers)} tickers')
            eq_results = run_eq_analyzer(eq_tickers)
            eq_map = {
                r.get('ticker'): r
                for r in eq_results
                if isinstance(r.get('ticker'), str) and r.get('ticker')
            }

            for candidate in final_companies:
                t         = candidate.get('ticker', '')
                eq        = eq_map.get(t, {})
                eq_result = eq.get('eq_result', {})

                if (eq_result
                        and isinstance(eq_result, dict)
                        and not eq.get('error')
                        and not eq.get('skipped')):
                    candidate[EQ_AVAILABLE]             = True
                    candidate[EQ_SCORE_FINAL]           = eq_result.get(EQ_SCORE_FINAL, 0)
                    candidate[EQ_LABEL]                 = eq_result.get(EQ_LABEL, '')
                    candidate[PASS_TIER]                = eq_result.get(PASS_TIER, '')
                    candidate[FINAL_CLASSIFICATION]     = eq_result.get(FINAL_CLASSIFICATION, '')
                    candidate[TOP_RISKS]                = eq_result.get(TOP_RISKS, [])
                    candidate[TOP_STRENGTHS]            = eq_result.get(TOP_STRENGTHS, [])
                    candidate[WARNINGS]                 = eq_result.get(WARNINGS, [])
                    candidate[DATA_CONFIDENCE]          = eq_result.get(DATA_CONFIDENCE, 0)
                    candidate[COMBINED_PRIORITY_SCORE]  = eq.get(COMBINED_PRIORITY_SCORE, 0)
                    candidate[EQ_PERCENTILE]            = eq_result.get(EQ_PERCENTILE, 0)
                    candidate[BATCH_REGIME]             = eq_result.get(BATCH_REGIME, '')
                    candidate[FATAL_FLAW_REASON]        = eq_result.get(FATAL_FLAW_REASON, '')
                else:
                    candidate[EQ_AVAILABLE] = False
                    log.info(f'[EQ] {t}: no EQ data — skipped or error')

            log.info(
                f'[EQ] Enrichment complete. '
                f'{sum(1 for c in final_companies if c.get(EQ_AVAILABLE))} enriched / '
                f'{len(final_companies)} total'
            )
        else:
            log.info('[EQ] No candidates for EQ analysis')

    except Exception as eq_err:
        log.warning(f'[EQ] EQ analysis failed (non-fatal): {eq_err}')
        for candidate in final_companies:
            candidate[EQ_AVAILABLE] = False
    # ── End Step 27d ─────────────────────────────────────────────────────

    # ── Step 28: Build reports ────────────────────────────────────────────
    from reports.report_builder import build_intraday_report
    html_files = build_intraday_report(
        companies     = final_companies,
        slot          = slot,
        indices       = indices,
        breadth       = breadth,
        regime        = regime,
        all_articles  = articles,
        sector_scores = sector_scores,
        rotation      = rotation,
    )

    # ── Step 28b — Dashboard update (non-fatal) ──────────────────────────────
    try:
        from reports.dashboard_builder import build_dashboard
        build_dashboard(
            companies = final_companies,
            slot      = slot,
            indices   = state.get('indices_today', {}),
            breadth   = breadth,
            regime    = regime,
            rotation  = rotation,
        )
    except Exception as _dash_err:
        log.warning(f'Dashboard build skipped: {_dash_err}')
    # ── End step 28b ──────────────────────────────────────────────────────────

    # ── Step 29: Send email ───────────────────────────────────────────────
    from reports.email_sender import send_email
    email_sent = send_email(
        companies = final_companies,
        slot      = slot,
        indices   = indices,
        html_path = html_files.get('email'),
    )
    if not email_sent:
        log.warning('Email delivery failed — report still committed to repo')

    # ── Step 30: Closing report if 16:10 slot ─────────────────────────────
    if slot == CLOSING_SLOT:
        from reports.summary_builder import build_closing_report
        build_closing_report(state, indices, sector_scores, rotation)

    # ── Step 31: Commit outputs to GitHub ─────────────────────────────────
    _commit_outputs()

    # ── Step 32: Update state ─────────────────────────────────────────────
    tickers_reported = [c['ticker'] for c in final_companies]
    state = add_reported_companies(state, tickers_reported)
    state['runs'][slot]['companies'] = tickers_reported

    # Save current slot's per-ticker confidence scores for next slot's
    # score stability filter. Overwrites previous slot - intentional.
    state['today_scores'] = {
        c.get('ticker', ''): c.get('composite_confidence', 0)
        for c in final_companies
        if c.get('ticker')
    }

    state = mark_slot_complete(state, slot)
    save_state(state)

    log.info(f'Run complete. Reported: {tickers_reported}')


def _write_empty_report(slot: str, state: dict, indices: dict, breadth: dict) -> None:
    """Write and commit an empty run report (no opportunities found)."""
    import os
    from config import REPORTS_OUTPUT_DIR
    os.makedirs(REPORTS_OUTPUT_DIR, exist_ok=True)
    now_str  = datetime.now(pytz.utc).strftime('%Y-%m-%dT%H%M%SZ')
    filename = os.path.join(REPORTS_OUTPUT_DIR, f'empty_{slot.replace(":", "")}_{now_str}.html')
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(
            f'<html><body><h1>Stock Research — {slot}</h1>'
            f'<p>No qualifying opportunities found this run.</p>'
            f'<p>{DISCLAIMER}</p></body></html>'
        )
    log.info(f'Empty report written: {filename}')
    _commit_outputs()


def _commit_outputs() -> None:
    """Step 31: Commit output files to GitHub. Guard: skip if nothing staged."""
    try:
        import git
        repo = git.Repo(search_parent_directories=True)
        repo.git.add('reports/output/', 'state/', 'data/fundamentals_cache/', 'logs/', '--')
        # Check if anything is staged
        if repo.index.diff('HEAD') or repo.untracked_files:
            ts  = datetime.now(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            repo.index.commit(f'Auto: market scan {ts}')
            origin = repo.remote(name='origin')
            origin.push()
            log.info('Git: committed and pushed')
        else:
            log.info('Git: nothing staged — skip commit')
    except Exception as e:
        log.warning(f'Git commit failed (non-fatal): {e}')


if __name__ == '__main__':
    run()
