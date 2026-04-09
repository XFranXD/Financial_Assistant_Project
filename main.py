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

from sector_detector import run_rotation_analyzer
from contracts.sector_schema import (
    ROTATION_AVAILABLE, ROTATION_SCORE, ROTATION_STATUS,
    ROTATION_SIGNAL, SECTOR_ETF, ROTATION_CONFIDENCE,
    ROTATION_REASONING, TIMEFRAMES_USED
)

from price_structure import analyze as ps_analyze
from contracts.price_structure_schema import (
    PS_AVAILABLE,
    PS_TREND_STRUCTURE, PS_TREND_STRENGTH, PS_KEY_LEVEL_POSITION,
    PS_ENTRY_QUALITY, PS_VOLATILITY_STATE, PS_COMPRESSION_LOCATION,
    PS_CONSOLIDATION_CONFIRMED, PS_SUPPORT_REACTION, PS_BASE_DURATION_DAYS,
    PS_VOLUME_CONTRACTION, PS_PRICE_ACTION_SCORE, PS_MOVE_EXTENSION_PCT,
    PS_DISTANCE_TO_SUPPORT_PCT, PS_DISTANCE_TO_RESIST_PCT,
    PS_STRUCTURE_STATE, PS_RECENT_CROSSOVER, PS_DATA_CONFIDENCE,
    PS_REASONING, PS_VERDICT_DISPLAY,
    PS_ENTRY_PRICE, PS_STOP_LOSS, PS_PRICE_TARGET, PS_RISK_REWARD_RATIO, PS_RR_OVERRIDE,
    PRICE_STRUCTURE_DEFAULTS,
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
            'market_cap':     float(body.get('MarketCapitalization', 0) or 0) or None,
            'debt_to_equity': float(body.get('DebtToEquityRatio', 0) or 0) or None,
            'profit_margin':  float(body.get('ProfitMargin', 0) or 0) * 100 if body.get('ProfitMargin') else None,
            'eps_ttm':        float(body.get('EPS', 0) or 0) or None,
        }
    return _call()


# ── Pre-dashboard enrichment helper ────────────────────────────────────────
# Centralised so both run() and _run_force_ticker_pipeline() stay in sync.

def _enrich_for_dashboard(candidates: list) -> None:
    """
    Populates display fields on each candidate dict so _update_rank_board()
    receives complete data. Mutates candidates in-place.

    Fields set: return_1m/3m/6m, price_history,
                eq_verdict_display, rotation_signal_display,
                ps_verdict_display, market_verdict_display, alignment.
    """
    for _c in candidates:
        try:
            _mtf = _c.get('mtf') or {}
            _c['return_1m'] = _mtf.get('r1m')
            _c['return_3m'] = _mtf.get('r3m')
            _c['return_6m'] = _mtf.get('r6m')

            _fin = _c.get('financials') or {}
            _c['price_history'] = _fin.get('price_history') or []

            # ── EQ verdict ────────────────────────────────────────────────
            if not _c.get(EQ_AVAILABLE):
                _eq_vd = 'UNAVAILABLE'
            elif _c.get(FATAL_FLAW_REASON):
                _eq_vd = 'RISKY'
            else:
                _tier = (_c.get(PASS_TIER) or '').strip().upper()
                _eq_vd = {
                    'PASS':  'SUPPORTIVE',
                    'WATCH': 'NEUTRAL',
                    'FAIL':  'WEAK',
                }.get(_tier, 'UNAVAILABLE')
            _c['eq_verdict_display'] = _eq_vd

            # ── Rotation signal ───────────────────────────────────────────
            _c['rotation_signal_display'] = (
                (_c.get(ROTATION_SIGNAL) or 'UNKNOWN')
                .strip().upper()
            )

            # ── PS verdict display ────────────────────────────────────────
            # Maps entry_quality directly for the dashboard pill.
            # GOOD / EXTENDED / EARLY / WEAK / UNAVAILABLE
            if not _c.get(PS_AVAILABLE):
                _ps_vd = 'UNAVAILABLE'
            else:
                _eq_raw = (_c.get(PS_ENTRY_QUALITY) or '').strip().upper()
                _ps_vd  = _eq_raw if _eq_raw in ('GOOD', 'EXTENDED', 'EARLY', 'WEAK') else 'UNAVAILABLE'
            _c[PS_VERDICT_DISPLAY] = _ps_vd

            # ── Market verdict ────────────────────────────────────────────
            # Thresholds match summary_verdict() exactly:
            # conf >= 70 AND risk <= 35 → RESEARCH NOW
            # conf >= 55                → WATCH
            # else                      → SKIP
            _conf_v = _c.get('composite_confidence') or 0
            _risk_v = _c.get('risk_score') or 100
            if _conf_v >= 70 and _risk_v <= 35:
                _mvd = 'RESEARCH NOW'
            elif _conf_v >= 55:
                _mvd = 'WATCH'
            else:
                _mvd = 'SKIP'
            _c['market_verdict_display'] = _mvd

            # ── Alignment (4-dimensional: S1 + S2 + S3 + S4) ─────────────
            # S4 adds +1 if entry_quality == GOOD, -1 if WEAK or EXTENDED.
            # EARLY is intentionally neutral (0) — promising but unconfirmed.
            _al = 0
            _mvd_n = (_c.get('market_verdict_display') or '').strip().upper()
            _rot_n = (_c.get('rotation_signal_display') or '').strip().upper()
            _eq_n  = (_c.get('eq_verdict_display') or '').strip().upper()
            _ps_n  = _ps_vd

            if _mvd_n == 'RESEARCH NOW': _al += 1
            elif _mvd_n == 'SKIP':       _al -= 1
            if _rot_n == 'SUPPORT':      _al += 1
            elif _rot_n == 'WEAKEN':     _al -= 1
            if _eq_n == 'SUPPORTIVE':           _al += 1
            elif _eq_n in ('WEAK', 'RISKY'):    _al -= 1
            if _ps_n == 'GOOD':                 _al += 1
            elif _ps_n in ('WEAK', 'EXTENDED'): _al -= 1

            if _al >= 2:   _c['alignment'] = 'ALIGNED'
            elif _al >= 0: _c['alignment'] = 'PARTIAL'
            else:          _c['alignment'] = 'CONFLICT'

        except Exception as _enrich_err:
            log.warning(
                f'Pre-dashboard enrichment failed for '
                f'{_c.get("ticker", "?")}: {_enrich_err} '
                f'— fields: return_1m/3m/6m price_history '
                f'eq_verdict_display rotation_signal_display '
                f'ps_verdict_display market_verdict_display alignment'
            )
            _c.setdefault('return_1m', None)
            _c.setdefault('return_3m', None)
            _c.setdefault('return_6m', None)
            _c.setdefault('price_history', [])
            _c.setdefault('eq_verdict_display', 'UNAVAILABLE')
            _c.setdefault('rotation_signal_display', 'UNKNOWN')
            _c.setdefault(PS_VERDICT_DISPLAY, 'UNAVAILABLE')
            _c.setdefault('market_verdict_display', 'WATCH')
            _c.setdefault('alignment', 'PARTIAL')


# ── Force-ticker pipeline (debug mode) ────────────────────────────────────

def _run_force_ticker_pipeline(force_tickers: list, slot: str, state: dict) -> None:
    """
    Debug mode: skip all sector/news gates and run the full per-company
    analysis pipeline directly against the provided ticker list.
    Triggered only when FORCE_TICKERS env var is set on a manual
    workflow_dispatch run. Never activates on scheduled runs.

    Produces a full report and email identical to a normal run.
    Does NOT update state slot completion — debug runs are invisible
    to the score stability filter and daily dedup logic.
    """
    log.info(f'[DEBUG] Force-ticker mode active — tickers: {force_tickers}')
    log.info(f'[DEBUG] Skipping all sector/news gates')

    # Fetch market context needed for scoring
    from collectors.market_collector import get_index_snapshot
    from analyzers.market_regime import get_regime
    from analyzers.market_breadth import compute_market_breadth
    from analyzers.sector_breadth_ma import compute_sector_breadth_ma
    from analyzers.sector_momentum import compute_sector_momentum, get_sector_pe, get_sector_median_return
    from analyzers.sector_rotation_speed import compute_rotation_speed
    from collectors.news_collector import collect_news
    from analyzers.event_detector import detect_events, summarise_sector_events

    indices = get_index_snapshot()
    regime  = get_regime()
    breadth = compute_market_breadth()

    # ── Step 6b: Market Regime Classification (2A) ────────────────────────
    from analyzers.spy_sma import get_spy_vs_200d
    from analyzers.market_breadth import compute_breadth_200d
    from analyzers.market_regime_classifier import get_market_regime_classification
    from contracts.eq_schema import MARKET_REGIME, MARKET_BREADTH_PCT
    try:
        _spy_result    = get_spy_vs_200d()
        _bd200_result  = compute_breadth_200d()
        _mr_result     = get_market_regime_classification(
            spy_sma_result = _spy_result,
            vix_value      = regime.get('vix'),
            breadth_pct    = _bd200_result.get('breadth_pct'),
        )
        market_regime_dict = {
            MARKET_REGIME:      _mr_result['market_regime'],
            MARKET_BREADTH_PCT: _bd200_result.get('breadth_pct'),
            'spy_above_200d':   _spy_result.get('spy_above_200d'),
            'regime_vix':       regime.get('vix'),
            'regime_score':     _mr_result.get('regime_score', 0),
        }
        _mr_label_log = _mr_result['market_regime']
        _mr_score_log = _mr_result.get('regime_score', 0)
        _mr_bpct_log  = _bd200_result.get('breadth_pct')
        log.info(
            f'[MR] market_regime={_mr_label_log} '
            f'score={_mr_score_log} '
            f'breadth_pct={_mr_bpct_log}'
        )
    except Exception as _mr_err:
        log.warning(f'[MR] Market regime classification failed (non-fatal): {_mr_err}')
        market_regime_dict = {
            MARKET_REGIME:      'NEUTRAL',
            MARKET_BREADTH_PCT: None,
            'spy_above_200d':   None,
            'regime_vix':       regime.get('vix'),
            'regime_score':     0,
        }
    # ── End Step 6b ───────────────────────────────────────────────────────

    breadth_stocks = _load_json(SECTOR_BREADTH_STOCKS_FILE, {})
    breadth_stocks.pop('_comment', None)
    sector_breadth_ma = compute_sector_breadth_ma(breadth_stocks)
    sector_scores     = compute_sector_momentum()
    rotation          = compute_rotation_speed(sector_scores)

    articles, candidate_sectors = collect_news()
    from collectors.market_collector import get_index_history as _get_idx_hist
    _index_history = _get_idx_hist()
    event_map   = detect_events(articles)
    e2s_data    = _load_json('data/event_to_sector.json', {})
    sector_events = summarise_sector_events(event_map, e2s_data)

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

    for ticker in force_tickers:
        ticker = ticker.strip().upper()
        log.info(f'[DEBUG] Processing forced ticker: {ticker}')

        fin = get_financials(ticker)

        # Map company industry to System 1 sector key for System 3 compatibility
        _industry = fin.get('industry', '') or ''
        _sector_map = _load_json('data/sector_tickers.json', {})
        _sector_map.pop('_comment', None)
        sector = 'unknown'
        for _sec_key, _tickers in _sector_map.items():
            for _entry in _tickers:
                _t = _entry['ticker'] if isinstance(_entry, dict) else _entry
                if _t == ticker:
                    sector = _sec_key
                    break
            if sector != 'unknown':
                break
        if sector == 'unknown':
            sector = 'energy'  # fallback for force-ticker mode
        sector_pe        = get_sector_pe('energy')       # neutral fallback
        sector_median_ret = get_sector_median_return('energy')
        etf_return       = None
        bma_score        = 0.5
        sector_momentum_val = 50
        sector_rank      = 7
        sector_data      = {'direction': 'positive', 'validation': {'confirmed': True}}

        # AV enrichment if budget allows
        av_data = _fetch_av_data(ticker, state)
        if av_data:
            state['alpha_vantage_calls_today'] = state.get('alpha_vantage_calls_today', 0) + 1
            save_state(state)
            fin = enrich_with_alpha_vantage(ticker, av_data, fin)

        vol_result       = compute_volume_confirmation(ticker)
        uv_result        = detect_unusual_volume(ticker, vol_result.get('volume_ratio'))
        ram_result       = compute_risk_adjusted_momentum(ticker)
        mtf_result       = compute_mtf_momentum(ticker)
        stability_result = compute_trend_stability(ticker)
        dd_result        = compute_drawdown_risk(ticker)
        risk_result      = compute_risk_score(fin, regime, dd_result.get('drawdown_score'))

        opp_result = compute_opportunity_score(
            fin, regime, breadth, sector_pe, sector_median_ret,
            ram_result.get('ram_score'), mtf_result.get('mtf_score'),
            vol_result.get('volume_score'), bma_score, etf_return,
        )

        sec_str       = sector_rank_to_score(sector_rank)
        norm_ev_score = 0.0   # no sector event context in force mode
        agreement     = compute_signal_agreement(
            momentum_score  = ram_result.get('ram_score', 0.5),
            sector_strength = sec_str,
            event_score     = norm_ev_score,
            volume_score    = vol_result.get('volume_score', 0.5),
        )

        conf_result = compute_composite_confidence(
            risk_score            = risk_result['risk_score'],
            opportunity_score     = opp_result['opportunity_score'],
            agreement_score       = agreement['agreement_score'],
            sector_momentum_score = sector_momentum_val,
        )

        log.info(
            f'[DEBUG] {ticker}: conf={conf_result["composite_confidence"]} '
            f'risk={risk_result["risk_score"]} opp={opp_result["opportunity_score"]}'
        )

        candidate = {
            'ticker':               ticker,
            'sector':               sector,
            'company_name':         fin.get('company_name', ticker),
            'current_price':        fin.get('current_price'),
            'financials':           fin,
            'risk_score':           risk_result['risk_score'],
            'risk_label':           risk_result['risk_label'],
            'risk_components':      risk_result['components'],
            'opportunity_score':    opp_result['opportunity_score'],
            'bucket_scores':        opp_result['bucket_scores'],
            'agreement_score':      agreement['agreement_score'],
            'agreement_label':      agreement['label'],
            'composite_confidence': conf_result['composite_confidence'],
            'confidence_label':     conf_result['confidence_label'],
            'volume_confirmation':  vol_result,
            'unusual_volume':       uv_result,
            'ram':                  ram_result,
            'mtf':                  mtf_result,
            'trend_stability':      stability_result,
            'drawdown':             dd_result,
            'earnings_warning':     risk_result.get('earnings_warning', False),
            'divergence_warning':   risk_result.get('divergence_warning', False),
            'sector_rank':          sector_rank,
            'sector_data':          sector_data,
            'rotation':             {},
            'disclaimer':           DISCLAIMER,
        }
        all_candidates.append(candidate)

    if not all_candidates:
        log.warning('[DEBUG] No candidates built from forced tickers — check ticker symbols')
        return

    # ── EQ enrichment ────────────────────────────────────────────────────
    try:
        eq_tickers = [c['ticker'] for c in all_candidates]
        log.info(f'[DEBUG][EQ] Running EQ analysis on {len(eq_tickers)} forced tickers')
        eq_results, _debug_eq_fetcher = run_eq_analyzer(eq_tickers)
        eq_map = {
            r.get('ticker'): r
            for r in eq_results
            if isinstance(r.get('ticker'), str) and r.get('ticker')
        }
        for candidate in all_candidates:
            t         = candidate.get('ticker', '')
            eq        = eq_map.get(t, {})
            eq_result = eq.get('eq_result', {})
            if (eq_result and isinstance(eq_result, dict)
                    and not eq.get('error') and not eq.get('skipped')):
                candidate[EQ_AVAILABLE]            = True
                candidate[EQ_SCORE_FINAL]          = eq_result.get(EQ_SCORE_FINAL, 0)
                candidate[EQ_LABEL]                = eq_result.get(EQ_LABEL, '')
                candidate[PASS_TIER]               = eq_result.get(PASS_TIER, '')
                candidate[FINAL_CLASSIFICATION]    = eq_result.get(FINAL_CLASSIFICATION, '')
                candidate[TOP_RISKS]               = eq_result.get(TOP_RISKS, [])
                candidate[TOP_STRENGTHS]           = eq_result.get(TOP_STRENGTHS, [])
                candidate[WARNINGS]                = eq_result.get(WARNINGS, [])
                candidate[DATA_CONFIDENCE]         = eq_result.get(DATA_CONFIDENCE, 0)
                candidate[COMBINED_PRIORITY_SCORE] = eq.get(COMBINED_PRIORITY_SCORE, 0)
                candidate[EQ_PERCENTILE]           = eq_result.get(EQ_PERCENTILE, 0)
                candidate[BATCH_REGIME]            = eq_result.get(BATCH_REGIME, '')
                candidate[FATAL_FLAW_REASON]       = eq_result.get(FATAL_FLAW_REASON, '')
            else:
                candidate[EQ_AVAILABLE] = False
                log.info(f'[DEBUG][EQ] {t}: no EQ data — skipped or error')
    except Exception as eq_err:
        log.warning(f'[DEBUG][EQ] EQ analysis failed (non-fatal): {eq_err}')
        for candidate in all_candidates:
            candidate[EQ_AVAILABLE] = False
        _debug_eq_fetcher = None

    # ── Sector Rotation enrichment ────────────────────────────────────────
    try:
        rotation_candidates = [
            {'ticker': c.get('ticker', ''), 'sector': c.get('sector', '')}
            for c in all_candidates
            if c.get('ticker') and c.get('sector')
        ]
        if rotation_candidates:
            log.info(f'[ROT] Running rotation analysis on {len(rotation_candidates)} candidates')
            rotation_results = run_rotation_analyzer(rotation_candidates)

            if not rotation_results:
                log.warning('[ROT] No results returned from System 3')
            else:
                rotation_map = {
                    r.get('ticker'): r
                    for r in rotation_results
                    if isinstance(r.get('ticker'), str) and r.get('ticker')
                }

                for candidate in all_candidates:
                    t   = candidate.get('ticker', '')
                    rot = rotation_map.get(t, {})

                    if (rot
                            and rot.get('rotation_status') not in ('SKIP', None)
                            and not rot.get('error')):
                        candidate[ROTATION_AVAILABLE]  = True
                        candidate[ROTATION_SCORE]      = rot.get(ROTATION_SCORE)
                        candidate[ROTATION_STATUS]     = rot.get(ROTATION_STATUS, '')
                        candidate[ROTATION_SIGNAL]     = rot.get(ROTATION_SIGNAL, 'UNKNOWN')
                        candidate[SECTOR_ETF]          = rot.get(SECTOR_ETF, '')
                        candidate[ROTATION_CONFIDENCE] = rot.get(ROTATION_CONFIDENCE, '')
                        candidate[ROTATION_REASONING]  = rot.get(ROTATION_REASONING, '')
                        candidate[TIMEFRAMES_USED]     = rot.get(TIMEFRAMES_USED, [])
                    else:
                        candidate[ROTATION_AVAILABLE]  = False
                        candidate[ROTATION_SIGNAL]     = 'UNKNOWN'
                        log.info(f'[ROT] {t}: no rotation data — skipped or error')

                log.info(
                    f'[ROT] Enrichment complete. '
                    f'{sum(1 for c in all_candidates if c.get(ROTATION_AVAILABLE))} enriched / '
                    f'{len(all_candidates)} total'
                )
        else:
            log.info('[ROT] No candidates for rotation analysis')

    except Exception as rot_err:
        log.warning(f'[ROT] Rotation analysis failed (non-fatal): {rot_err}')
        for candidate in all_candidates:
            candidate[ROTATION_AVAILABLE] = False
            candidate[ROTATION_SIGNAL]    = 'UNKNOWN'

    # ── Step 27f: Price Structure enrichment (Debug) ──────────────────────
    # Run System 4 (Price Structure Analyzer) against all forced candidates.
    # analyze() is called per-ticker. Non-fatal — PS_AVAILABLE=False on any error.
    try:
        log.info(f'[PS] Running price structure analysis on {len(all_candidates)} forced tickers')
        ps_enriched = 0
        for candidate in all_candidates:
            t = candidate.get('ticker', '')
            try:
                ps_result = ps_analyze(t)
                if (ps_result
                        and isinstance(ps_result, dict)
                        and ps_result.get(PS_DATA_CONFIDENCE, 'UNAVAILABLE') != 'UNAVAILABLE'):
                    candidate[PS_AVAILABLE]               = True
                    candidate[PS_TREND_STRUCTURE]         = ps_result.get(PS_TREND_STRUCTURE,        PRICE_STRUCTURE_DEFAULTS[PS_TREND_STRUCTURE])
                    candidate[PS_TREND_STRENGTH]          = ps_result.get(PS_TREND_STRENGTH,         PRICE_STRUCTURE_DEFAULTS[PS_TREND_STRENGTH])
                    candidate[PS_KEY_LEVEL_POSITION]      = ps_result.get(PS_KEY_LEVEL_POSITION,     PRICE_STRUCTURE_DEFAULTS[PS_KEY_LEVEL_POSITION])
                    candidate[PS_ENTRY_QUALITY]           = ps_result.get(PS_ENTRY_QUALITY,          PRICE_STRUCTURE_DEFAULTS[PS_ENTRY_QUALITY])
                    candidate[PS_VOLATILITY_STATE]        = ps_result.get(PS_VOLATILITY_STATE,       PRICE_STRUCTURE_DEFAULTS[PS_VOLATILITY_STATE])
                    candidate[PS_COMPRESSION_LOCATION]    = ps_result.get(PS_COMPRESSION_LOCATION,   PRICE_STRUCTURE_DEFAULTS[PS_COMPRESSION_LOCATION])
                    candidate[PS_CONSOLIDATION_CONFIRMED] = ps_result.get(PS_CONSOLIDATION_CONFIRMED,PRICE_STRUCTURE_DEFAULTS[PS_CONSOLIDATION_CONFIRMED])
                    candidate[PS_SUPPORT_REACTION]        = ps_result.get(PS_SUPPORT_REACTION,       PRICE_STRUCTURE_DEFAULTS[PS_SUPPORT_REACTION])
                    candidate[PS_BASE_DURATION_DAYS]      = ps_result.get(PS_BASE_DURATION_DAYS,     PRICE_STRUCTURE_DEFAULTS[PS_BASE_DURATION_DAYS])
                    candidate[PS_VOLUME_CONTRACTION]      = ps_result.get(PS_VOLUME_CONTRACTION,     PRICE_STRUCTURE_DEFAULTS[PS_VOLUME_CONTRACTION])
                    candidate[PS_PRICE_ACTION_SCORE]      = ps_result.get(PS_PRICE_ACTION_SCORE,     PRICE_STRUCTURE_DEFAULTS[PS_PRICE_ACTION_SCORE])
                    candidate[PS_MOVE_EXTENSION_PCT]      = ps_result.get(PS_MOVE_EXTENSION_PCT,     PRICE_STRUCTURE_DEFAULTS[PS_MOVE_EXTENSION_PCT])
                    candidate[PS_DISTANCE_TO_SUPPORT_PCT] = ps_result.get(PS_DISTANCE_TO_SUPPORT_PCT,PRICE_STRUCTURE_DEFAULTS[PS_DISTANCE_TO_SUPPORT_PCT])
                    candidate[PS_DISTANCE_TO_RESIST_PCT]  = ps_result.get(PS_DISTANCE_TO_RESIST_PCT, PRICE_STRUCTURE_DEFAULTS[PS_DISTANCE_TO_RESIST_PCT])
                    candidate[PS_STRUCTURE_STATE]         = ps_result.get(PS_STRUCTURE_STATE,        PRICE_STRUCTURE_DEFAULTS[PS_STRUCTURE_STATE])
                    candidate[PS_RECENT_CROSSOVER]        = ps_result.get(PS_RECENT_CROSSOVER,       PRICE_STRUCTURE_DEFAULTS[PS_RECENT_CROSSOVER])
                    candidate[PS_DATA_CONFIDENCE]         = ps_result.get(PS_DATA_CONFIDENCE,        PRICE_STRUCTURE_DEFAULTS[PS_DATA_CONFIDENCE])
                    candidate[PS_REASONING]               = ps_result.get(PS_REASONING,              PRICE_STRUCTURE_DEFAULTS[PS_REASONING])
                    candidate[PS_ENTRY_PRICE]             = ps_result.get(PS_ENTRY_PRICE,             PRICE_STRUCTURE_DEFAULTS['entry_price'])
                    candidate[PS_STOP_LOSS]               = ps_result.get(PS_STOP_LOSS,               PRICE_STRUCTURE_DEFAULTS['stop_loss'])
                    candidate[PS_PRICE_TARGET]            = ps_result.get(PS_PRICE_TARGET,            PRICE_STRUCTURE_DEFAULTS['price_target'])
                    candidate[PS_RISK_REWARD_RATIO]       = ps_result.get(PS_RISK_REWARD_RATIO,       PRICE_STRUCTURE_DEFAULTS['risk_reward_ratio'])
                    candidate[PS_RR_OVERRIDE]             = ps_result.get(PS_RR_OVERRIDE,             False)
                    ps_enriched += 1
                else:
                    candidate[PS_AVAILABLE] = False
                    log.info(f'[PS] {t}: UNAVAILABLE confidence — skipped')
            except Exception as _ps_ticker_err:
                candidate[PS_AVAILABLE] = False
                log.info(f'[PS] {t}: error — {_ps_ticker_err}')

        log.info(
            f'[PS] Enrichment complete. '
            f'{ps_enriched} enriched / {len(all_candidates)} total'
        )
    except Exception as ps_err:
        log.warning(f'[PS] Price structure analysis failed (non-fatal): {ps_err}')
        for candidate in all_candidates:
            candidate[PS_AVAILABLE] = False
    # ── End Step 27f (Debug) ─────────────────────────────────────────────

    # ── Step 27g: Event Risk enrichment (Debug) ───────────────────────────
    try:
        from eq_analyzer.event_risk import get_event_risk
        from contracts.eq_schema import EVENT_RISK, EVENT_RISK_REASON, DAYS_TO_EARNINGS
        finnhub_token = os.environ.get('FINNHUB_TOKEN', '')
        er_enriched = 0
        for candidate in all_candidates:
            t = candidate.get('ticker', '')
            try:
                er_result = get_event_risk(t, finnhub_token)
                candidate[EVENT_RISK]        = er_result.get('event_risk',        'NORMAL')
                candidate[EVENT_RISK_REASON] = er_result.get('event_risk_reason', '')
                candidate[DAYS_TO_EARNINGS]  = er_result.get('days_to_earnings',  None)
                er_enriched += 1
            except Exception as _er_ticker_err:
                candidate[EVENT_RISK]        = 'NORMAL'
                candidate[EVENT_RISK_REASON] = ''
                candidate[DAYS_TO_EARNINGS]  = None
                log.info(f'[ER] {t}: error — {_er_ticker_err}')
        log.info(f'[ER] Event risk enrichment complete. {er_enriched}/{len(all_candidates)} processed')
    except Exception as er_err:
        log.warning(f'[ER] Event risk enrichment failed (non-fatal): {er_err}')
        for candidate in all_candidates:
            candidate[EVENT_RISK]        = 'NORMAL'
            candidate[EVENT_RISK_REASON] = ''
            candidate[DAYS_TO_EARNINGS]  = None
    # ── End Step 27g (Debug) ─────────────────────────────────────────────

    # ── Step 27h: Insider Activity enrichment (Debug) ─────────────────────
    try:
        from eq_analyzer.insider_activity import get_insider_signal
        from contracts.eq_schema import INSIDER_SIGNAL, INSIDER_NOTE
        ins_enriched = 0
        if _debug_eq_fetcher is None:
            log.warning('[INS] eq_fetcher not available in debug mode — insider enrichment skipped')
            raise RuntimeError('eq_fetcher unavailable')
        for candidate in all_candidates:
            t = candidate.get('ticker', '')
            try:
                ins_result = get_insider_signal(t, _debug_eq_fetcher)
                candidate[INSIDER_SIGNAL] = ins_result.get('insider_signal', 'UNAVAILABLE')
                candidate[INSIDER_NOTE]   = ins_result.get('insider_note',   '')
                ins_enriched += 1
            except Exception as _ins_ticker_err:
                candidate[INSIDER_SIGNAL] = 'UNAVAILABLE'
                candidate[INSIDER_NOTE]   = ''
                log.info(f'[INS] {t}: error — {_ins_ticker_err}')
        log.info(f'[INS] Insider enrichment complete. {ins_enriched}/{len(all_candidates)} processed')
    except Exception as ins_err:
        log.warning(f'[INS] Insider enrichment failed (non-fatal): {ins_err}')
        for candidate in all_candidates:
            candidate[INSIDER_SIGNAL] = 'UNAVAILABLE'
            candidate[INSIDER_NOTE]   = ''
    # ── End Step 27h (Debug) ─────────────────────────────────────────────

    # Build and send report
    from reports.report_builder import build_intraday_report
    html_files = build_intraday_report(
        companies          = all_candidates,
        slot               = slot,
        indices            = indices,
        breadth            = breadth,
        regime             = regime,
        all_articles       = articles,
        sector_scores      = sector_scores,
        rotation           = rotation,
        market_regime_dict = market_regime_dict,
    )

    # ── Pre-dashboard candidate enrichment ───────────────────────────────
    _enrich_for_dashboard(all_candidates)

    try:
        from reports.dashboard_builder import build_dashboard
        build_dashboard(
            companies          = all_candidates,
            slot               = slot,
            indices            = indices,
            breadth            = breadth,
            regime             = regime,
            prompt_text        = html_files.get('prompt', ''),
            full_url           = html_files.get('full_url', ''),
            is_debug           = True,
            index_history      = _index_history,
            confirmed_sectors  = candidate_sectors,
            market_regime_dict = market_regime_dict,
        )
    except Exception as _dash_err:
        log.warning(f'[DEBUG] Dashboard build skipped: {_dash_err}')

    from reports.email_sender import send_email
    send_email(
        companies = all_candidates,
        slot      = slot,
        indices   = indices,
        html_path = html_files.get('email'),
    )

    _commit_outputs()
    log.info(f'[DEBUG] Force-ticker run complete. Tickers: {force_tickers}')


# ── Main pipeline ──────────────────────────────────────────────────────────

def run():
    log.info('=' * 60)
    log.info('AUTOMATED STOCK RESEARCH SYSTEM — starting run')
    log.info(DISCLAIMER)
    log.info('=' * 60)

    # ── Force-ticker debug mode check ─────────────────────────────────────
    force_tickers_raw = os.environ.get('FORCE_TICKERS', '').strip()
    force_tickers = [t.strip().upper() for t in force_tickers_raw.split(',') if t.strip()]

    if force_tickers:
        log.info(f'[DEBUG] FORCE_TICKERS detected — entering debug mode')
        _check_validated_file()
        state = load_state()
        slot  = _determine_slot() or RUN_SLOTS[0]
        log.info(f'[DEBUG] Using slot: {slot}')
        _run_force_ticker_pipeline(force_tickers, slot, state)
        sys.exit(0)

    # ── Time gate ─────────────────────────────────────────────────────────
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

    # ── Step 1: Startup check ─────────────────────────────────────────────
    _check_validated_file()

    # ── Step 2: Determine run slot ────────────────────────────────────────
    slot = _determine_slot()
    if slot is None:
        slot = RUN_SLOTS[0]
        log.warning(f'Could not determine slot from time — defaulting to {slot}')
    log.info(f'Run slot: {slot}')

    # ── Step 3: Load state, check market open, check duplicate slot ────────
    state = load_state()
    if not _is_market_open():
        log.info('Market closed (weekend) — exiting')
        sys.exit(0)

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

    # ── Step 6b: Market Regime Classification (2A) ────────────────────────
    from analyzers.spy_sma import get_spy_vs_200d
    from analyzers.market_breadth import compute_breadth_200d
    from analyzers.market_regime_classifier import get_market_regime_classification
    from contracts.eq_schema import MARKET_REGIME, MARKET_BREADTH_PCT
    try:
        _spy_result    = get_spy_vs_200d()
        _bd200_result  = compute_breadth_200d()
        _mr_result     = get_market_regime_classification(
            spy_sma_result = _spy_result,
            vix_value      = regime.get('vix'),
            breadth_pct    = _bd200_result.get('breadth_pct'),
        )
        market_regime_dict = {
            MARKET_REGIME:      _mr_result['market_regime'],
            MARKET_BREADTH_PCT: _bd200_result.get('breadth_pct'),
            'spy_above_200d':   _spy_result.get('spy_above_200d'),
            'regime_vix':       regime.get('vix'),
            'regime_score':     _mr_result.get('regime_score', 0),
        }
        _mr_label_log = _mr_result['market_regime']
        _mr_score_log = _mr_result.get('regime_score', 0)
        _mr_bpct_log  = _bd200_result.get('breadth_pct')
        log.info(
            f'[MR] market_regime={_mr_label_log} '
            f'score={_mr_score_log} '
            f'breadth_pct={_mr_bpct_log}'
        )
    except Exception as _mr_err:
        log.warning(f'[MR] Market regime classification failed (non-fatal): {_mr_err}')
        market_regime_dict = {
            MARKET_REGIME:      'NEUTRAL',
            MARKET_BREADTH_PCT: None,
            'spy_above_200d':   None,
            'regime_vix':       regime.get('vix'),
            'regime_score':     0,
        }
    # ── End Step 6b ───────────────────────────────────────────────────────

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
    from collectors.market_collector import get_index_history as _get_idx_hist
    index_history = _get_idx_hist()
    log.info(f'News: {len(articles)} articles, {len(candidate_sectors)} candidate sectors')

    if not candidate_sectors:
        log.info('No candidate sectors — writing empty report')
        _write_empty_report(slot, state, indices, breadth)
        state = mark_slot_complete(state, slot)
        save_state(state)
        sys.exit(0)

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

    # ── Step 14: Momentum gate ────────────────────────────────────────────
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

        sector_pe           = get_sector_pe(sector)
        sector_median_ret   = get_sector_median_return(sector)
        etf_return          = sector_scores.get(sector, {}).get('ret5d')
        bma                 = sector_breadth_ma.get(sector, {})
        bma_score           = bma.get('breadth_ma_score', 0.5)
        sector_momentum_val = sector_scores.get(sector, {}).get('score', 0)
        sector_rank         = sector_scores.get(sector, {}).get('rank', 13)

        for ticker_entry in sector_ticker_list:
            ticker = ticker_entry['ticker'] if isinstance(ticker_entry, dict) else ticker_entry

            fin = get_financials(ticker)

            ok, reason = passes_candidate_filter(
                ticker, fin, sector, state.get('reported_companies', [])
            )
            log.info(f'DEBUG filter {ticker}: ok={ok} reason={reason}')
            if not ok:
                continue

            av_data = _fetch_av_data(ticker, state)
            if av_data:
                state['alpha_vantage_calls_today'] = state.get('alpha_vantage_calls_today', 0) + 1
                save_state(state)
                fin = enrich_with_alpha_vantage(ticker, av_data, fin)

            vol_result = compute_volume_confirmation(ticker)
            uv_result  = detect_unusual_volume(ticker, vol_result.get('volume_ratio'))
            if uv_result['unusual_flag']:
                state['unusual_volume_flags'].append(ticker)
                save_state(state)

            ram_result = compute_risk_adjusted_momentum(ticker)
            mtf_result = compute_mtf_momentum(ticker)

            stability_result = compute_trend_stability(ticker)
            dd_result        = compute_drawdown_risk(ticker)

            risk_result = compute_risk_score(fin, regime, dd_result.get('drawdown_score'))

            opp_result = compute_opportunity_score(
                fin, regime, breadth, sector_pe, sector_median_ret,
                ram_result.get('ram_score'), mtf_result.get('mtf_score'),
                vol_result.get('volume_score'), bma_score, etf_return,
            )

            sec_str       = sector_rank_to_score(sector_rank)
            norm_ev_score = min(1.0, sector_events.get(sector, {}).get('total_adjusted', 0) / 20.0)
            agreement     = compute_signal_agreement(
                momentum_score  = ram_result.get('ram_score', 0.5),
                sector_strength = sec_str,
                event_score     = norm_ev_score,
                volume_score    = vol_result.get('volume_score', 0.5),
            )

            conf_result = compute_composite_confidence(
                risk_score            = risk_result['risk_score'],
                opportunity_score     = opp_result['opportunity_score'],
                agreement_score       = agreement['agreement_score'],
                sector_momentum_score = sector_momentum_val,
            )

            log.info(f'DEBUG confidence {ticker}: conf={conf_result["composite_confidence"]} min={COMPOSITE_CONFIDENCE_MIN} risk={risk_result["risk_score"]} opp={opp_result["opportunity_score"]}')
            if conf_result['composite_confidence'] < COMPOSITE_CONFIDENCE_MIN:
                log.info(
                    f'{ticker}: confidence {conf_result["composite_confidence"]} '
                    f'< {COMPOSITE_CONFIDENCE_MIN} — excluded'
                )
                continue

            candidate = {
                'ticker':              ticker,
                'sector':              sector,
                'company_name':        ticker,
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

    # ── Step 27b: Within-industry deduplication ───────────────────────────
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

    deduplicated.sort(key=lambda c: c.get('composite_confidence', 0), reverse=True)

    final_companies = deduplicated
    log.info(f'Final company count after industry dedup: {len(final_companies)}')

    # ── Step 27c: Score stability filter ─────────────────────────────────
    today_prior_scores = state.get('today_scores', {})
    stable_companies: list = []
    for _c in final_companies:
        _ticker       = _c.get('ticker', '')
        _current_conf = _c.get('composite_confidence', 0)
        _prior_conf   = today_prior_scores.get(_ticker)

        if _prior_conf is None:
            stable_companies.append(_c)
        elif _current_conf >= _prior_conf:
            stable_companies.append(_c)
        else:
            log.info(f'score_stability: {_ticker} suppressed - score declined ({_prior_conf} -> {_current_conf})')

    final_companies = stable_companies
    log.info(f'Final company count after score stability filter: {len(final_companies)}')

    # ── Step 27d: Earnings Quality enrichment ────────────────────────────
    eq_fetcher = None
    try:
        eq_tickers = [c['ticker'] for c in final_companies if c.get('ticker')]
        if eq_tickers:
            log.info(f'[EQ] Running earnings quality analysis on {len(eq_tickers)} tickers')
            eq_results, eq_fetcher = run_eq_analyzer(eq_tickers)
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

    # ── Step 27e: Sector Rotation enrichment ─────────────────────────────
    try:
        rotation_candidates = [
            {'ticker': c.get('ticker', ''), 'sector': c.get('sector', '')}
            for c in final_companies
            if c.get('ticker') and c.get('sector')
        ]
        if rotation_candidates:
            log.info(f'[ROT] Running rotation analysis on {len(rotation_candidates)} candidates')
            rotation_results = run_rotation_analyzer(rotation_candidates)

            if not rotation_results:
                log.warning('[ROT] No results returned from System 3')
            else:
                rotation_map = {
                    r.get('ticker'): r
                    for r in rotation_results
                    if isinstance(r.get('ticker'), str) and r.get('ticker')
                }

                for candidate in final_companies:
                    t   = candidate.get('ticker', '')
                    rot = rotation_map.get(t, {})

                    if (rot
                            and rot.get('rotation_status') not in ('SKIP', None)
                            and not rot.get('error')):
                        candidate[ROTATION_AVAILABLE]  = True
                        candidate[ROTATION_SCORE]      = rot.get(ROTATION_SCORE)
                        candidate[ROTATION_STATUS]     = rot.get(ROTATION_STATUS, '')
                        candidate[ROTATION_SIGNAL]     = rot.get(ROTATION_SIGNAL, 'UNKNOWN')
                        candidate[SECTOR_ETF]          = rot.get(SECTOR_ETF, '')
                        candidate[ROTATION_CONFIDENCE] = rot.get(ROTATION_CONFIDENCE, '')
                        candidate[ROTATION_REASONING]  = rot.get(ROTATION_REASONING, '')
                        candidate[TIMEFRAMES_USED]     = rot.get(TIMEFRAMES_USED, [])
                    else:
                        candidate[ROTATION_AVAILABLE]  = False
                        candidate[ROTATION_SIGNAL]     = 'UNKNOWN'
                        log.info(f'[ROT] {t}: no rotation data — skipped or error')

                log.info(
                    f'[ROT] Enrichment complete. '
                    f'{sum(1 for c in final_companies if c.get(ROTATION_AVAILABLE))} enriched / '
                    f'{len(final_companies)} total'
                )
        else:
            log.info('[ROT] No candidates for rotation analysis')

    except Exception as rot_err:
        log.warning(f'[ROT] Rotation analysis failed (non-fatal): {rot_err}')
        for candidate in final_companies:
            candidate[ROTATION_AVAILABLE] = False
            candidate[ROTATION_SIGNAL]    = 'UNKNOWN'
    # ── End Step 27e ─────────────────────────────────────────────────────

    # ── Step 27f: Price Structure enrichment ─────────────────────────────
    # Run System 4 (Price Structure Analyzer) against all final candidates.
    # analyze() is called per-ticker. Non-fatal — PS_AVAILABLE=False on any error.
    # entry_quality == GOOD is a hard gate for BUY NOW in _build_ai_prompt().
    try:
        if final_companies:
            log.info(f'[PS] Running price structure analysis on {len(final_companies)} tickers')
            ps_enriched = 0
            for candidate in final_companies:
                t = candidate.get('ticker', '')
                try:
                    ps_result = ps_analyze(t)
                    if (ps_result
                            and isinstance(ps_result, dict)
                            and ps_result.get(PS_DATA_CONFIDENCE, 'UNAVAILABLE') != 'UNAVAILABLE'):
                        candidate[PS_AVAILABLE]               = True
                        candidate[PS_TREND_STRUCTURE]         = ps_result.get(PS_TREND_STRUCTURE,        PRICE_STRUCTURE_DEFAULTS[PS_TREND_STRUCTURE])
                        candidate[PS_TREND_STRENGTH]          = ps_result.get(PS_TREND_STRENGTH,         PRICE_STRUCTURE_DEFAULTS[PS_TREND_STRENGTH])
                        candidate[PS_KEY_LEVEL_POSITION]      = ps_result.get(PS_KEY_LEVEL_POSITION,     PRICE_STRUCTURE_DEFAULTS[PS_KEY_LEVEL_POSITION])
                        candidate[PS_ENTRY_QUALITY]           = ps_result.get(PS_ENTRY_QUALITY,          PRICE_STRUCTURE_DEFAULTS[PS_ENTRY_QUALITY])
                        candidate[PS_VOLATILITY_STATE]        = ps_result.get(PS_VOLATILITY_STATE,       PRICE_STRUCTURE_DEFAULTS[PS_VOLATILITY_STATE])
                        candidate[PS_COMPRESSION_LOCATION]    = ps_result.get(PS_COMPRESSION_LOCATION,   PRICE_STRUCTURE_DEFAULTS[PS_COMPRESSION_LOCATION])
                        candidate[PS_CONSOLIDATION_CONFIRMED] = ps_result.get(PS_CONSOLIDATION_CONFIRMED,PRICE_STRUCTURE_DEFAULTS[PS_CONSOLIDATION_CONFIRMED])
                        candidate[PS_SUPPORT_REACTION]        = ps_result.get(PS_SUPPORT_REACTION,       PRICE_STRUCTURE_DEFAULTS[PS_SUPPORT_REACTION])
                        candidate[PS_BASE_DURATION_DAYS]      = ps_result.get(PS_BASE_DURATION_DAYS,     PRICE_STRUCTURE_DEFAULTS[PS_BASE_DURATION_DAYS])
                        candidate[PS_VOLUME_CONTRACTION]      = ps_result.get(PS_VOLUME_CONTRACTION,     PRICE_STRUCTURE_DEFAULTS[PS_VOLUME_CONTRACTION])
                        candidate[PS_PRICE_ACTION_SCORE]      = ps_result.get(PS_PRICE_ACTION_SCORE,     PRICE_STRUCTURE_DEFAULTS[PS_PRICE_ACTION_SCORE])
                        candidate[PS_MOVE_EXTENSION_PCT]      = ps_result.get(PS_MOVE_EXTENSION_PCT,     PRICE_STRUCTURE_DEFAULTS[PS_MOVE_EXTENSION_PCT])
                        candidate[PS_DISTANCE_TO_SUPPORT_PCT] = ps_result.get(PS_DISTANCE_TO_SUPPORT_PCT,PRICE_STRUCTURE_DEFAULTS[PS_DISTANCE_TO_SUPPORT_PCT])
                        candidate[PS_DISTANCE_TO_RESIST_PCT]  = ps_result.get(PS_DISTANCE_TO_RESIST_PCT, PRICE_STRUCTURE_DEFAULTS[PS_DISTANCE_TO_RESIST_PCT])
                        candidate[PS_STRUCTURE_STATE]         = ps_result.get(PS_STRUCTURE_STATE,        PRICE_STRUCTURE_DEFAULTS[PS_STRUCTURE_STATE])
                        candidate[PS_RECENT_CROSSOVER]        = ps_result.get(PS_RECENT_CROSSOVER,       PRICE_STRUCTURE_DEFAULTS[PS_RECENT_CROSSOVER])
                        candidate[PS_DATA_CONFIDENCE]         = ps_result.get(PS_DATA_CONFIDENCE,        PRICE_STRUCTURE_DEFAULTS[PS_DATA_CONFIDENCE])
                        candidate[PS_REASONING]               = ps_result.get(PS_REASONING,              PRICE_STRUCTURE_DEFAULTS[PS_REASONING])
                        candidate[PS_ENTRY_PRICE]             = ps_result.get(PS_ENTRY_PRICE,             PRICE_STRUCTURE_DEFAULTS['entry_price'])
                        candidate[PS_STOP_LOSS]               = ps_result.get(PS_STOP_LOSS,               PRICE_STRUCTURE_DEFAULTS['stop_loss'])
                        candidate[PS_PRICE_TARGET]            = ps_result.get(PS_PRICE_TARGET,            PRICE_STRUCTURE_DEFAULTS['price_target'])
                        candidate[PS_RISK_REWARD_RATIO]       = ps_result.get(PS_RISK_REWARD_RATIO,       PRICE_STRUCTURE_DEFAULTS['risk_reward_ratio'])
                        candidate[PS_RR_OVERRIDE]             = ps_result.get(PS_RR_OVERRIDE,             False)
                        ps_enriched += 1
                    else:
                        candidate[PS_AVAILABLE] = False
                        log.info(f'[PS] {t}: UNAVAILABLE confidence — skipped')
                except Exception as _ps_ticker_err:
                    candidate[PS_AVAILABLE] = False
                    log.info(f'[PS] {t}: error — {_ps_ticker_err}')

            log.info(
                f'[PS] Enrichment complete. '
                f'{ps_enriched} enriched / {len(final_companies)} total'
            )
        else:
            log.info('[PS] No candidates for price structure analysis')

    except Exception as ps_err:
        log.warning(f'[PS] Price structure analysis failed (non-fatal): {ps_err}')
        for candidate in final_companies:
            candidate[PS_AVAILABLE] = False
    # ── End Step 27f ─────────────────────────────────────────────────────

    # ── Step 27g: Event Risk enrichment ──────────────────────────────────────
    # Classifies each candidate as NORMAL or HIGH RISK based on earnings proximity
    # and hardcoded macro events. Non-fatal — defaults to NORMAL on any error.
    try:
        from eq_analyzer.event_risk import get_event_risk
        from contracts.eq_schema import EVENT_RISK, EVENT_RISK_REASON, DAYS_TO_EARNINGS
        finnhub_token = os.environ.get('FINNHUB_TOKEN', '')
        er_enriched = 0
        for candidate in final_companies:
            t = candidate.get('ticker', '')
            try:
                er_result = get_event_risk(t, finnhub_token)
                candidate[EVENT_RISK]        = er_result.get('event_risk',        'NORMAL')
                candidate[EVENT_RISK_REASON] = er_result.get('event_risk_reason', '')
                candidate[DAYS_TO_EARNINGS]  = er_result.get('days_to_earnings',  None)
                er_enriched += 1
            except Exception as _er_ticker_err:
                candidate[EVENT_RISK]        = 'NORMAL'
                candidate[EVENT_RISK_REASON] = ''
                candidate[DAYS_TO_EARNINGS]  = None
                log.info(f'[ER] {t}: error — {_er_ticker_err}')
        log.info(f'[ER] Event risk enrichment complete. {er_enriched}/{len(final_companies)} processed')
    except Exception as er_err:
        log.warning(f'[ER] Event risk enrichment failed (non-fatal): {er_err}')
        for candidate in final_companies:
            candidate[EVENT_RISK]        = 'NORMAL'
            candidate[EVENT_RISK_REASON] = ''
            candidate[DAYS_TO_EARNINGS]  = None
    # ── End Step 27g ─────────────────────────────────────────────────────────

    # ── Step 27h: Insider Activity enrichment ────────────────────────────────
    # Fetches SEC Form 4 insider transaction data via EDGAR RSS.
    # Reuses EdgarFetcher from Step 27d. Non-fatal — defaults to UNAVAILABLE.
    try:
        from eq_analyzer.insider_activity import get_insider_signal
        from contracts.eq_schema import INSIDER_SIGNAL, INSIDER_NOTE
        ins_enriched = 0
        _ins_fetcher = eq_fetcher
        if _ins_fetcher is None:
            log.warning('[INS] eq_fetcher not available — insider enrichment skipped')
            raise RuntimeError('eq_fetcher unavailable')
        for candidate in final_companies:
            t = candidate.get('ticker', '')
            try:
                ins_result = get_insider_signal(t, _ins_fetcher)
                candidate[INSIDER_SIGNAL] = ins_result.get('insider_signal', 'UNAVAILABLE')
                candidate[INSIDER_NOTE]   = ins_result.get('insider_note',   '')
                ins_enriched += 1
            except Exception as _ins_ticker_err:
                candidate[INSIDER_SIGNAL] = 'UNAVAILABLE'
                candidate[INSIDER_NOTE]   = ''
                log.info(f'[INS] {t}: error — {_ins_ticker_err}')
        log.info(f'[INS] Insider enrichment complete. {ins_enriched}/{len(final_companies)} processed')
    except Exception as ins_err:
        log.warning(f'[INS] Insider enrichment failed (non-fatal): {ins_err}')
        for candidate in final_companies:
            candidate[INSIDER_SIGNAL] = 'UNAVAILABLE'
            candidate[INSIDER_NOTE]   = ''
    # ── End Step 27h ─────────────────────────────────────────────────────────

    # ── Step 28: Build reports ────────────────────────────────────────────
    from reports.report_builder import build_intraday_report
    html_files = build_intraday_report(
        companies          = final_companies,
        slot               = slot,
        indices            = indices,
        breadth            = breadth,
        regime             = regime,
        all_articles       = articles,
        sector_scores      = sector_scores,
        rotation           = rotation,
        market_regime_dict = market_regime_dict,
    )

    # ── Pre-dashboard candidate enrichment ───────────────────────────────
    _enrich_for_dashboard(final_companies)

    # ── Step 28b — Dashboard update (non-fatal) ───────────────────────────
    try:
        from reports.dashboard_builder import build_dashboard
        build_dashboard(
            companies          = final_companies,
            slot               = slot,
            indices            = state.get('indices_today', {}),
            breadth            = breadth,
            regime             = regime,
            prompt_text        = html_files.get('prompt', ''),
            full_url           = html_files.get('full_url', ''),
            is_debug           = False,
            index_history      = index_history,
            confirmed_sectors  = candidate_sectors,
            market_regime_dict = market_regime_dict,
        )
    except Exception as _dash_err:
        log.warning(f'Dashboard build skipped: {_dash_err}')

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

    # ── Step 30: Closing report ───────────────────────────────────────────
    if slot == CLOSING_SLOT:
        from reports.summary_builder import build_closing_report
        build_closing_report(state, indices, sector_scores, rotation)

    # ── Step 31: Commit outputs ───────────────────────────────────────────
    _commit_outputs()

    # ── Step 32: Update state ─────────────────────────────────────────────
    tickers_reported = [c['ticker'] for c in final_companies]
    state = add_reported_companies(state, tickers_reported)
    state['runs'][slot]['companies'] = tickers_reported

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
        repo.git.add('reports/output/', 'docs/', 'state/', 'data/fundamentals_cache/', 'logs/', '--')
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