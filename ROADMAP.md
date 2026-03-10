# AUTOMATED STOCK RESEARCH SYSTEM
## Complete Implementation Roadmap — Version 5 Final

| Property | Value |
|---|---|
| Target Agent | Claude Sonnet 4.6 in Antigravity IDE |
| Language / OS | Python 3.11 · ubuntu-latest (GitHub Actions) |
| Cost | $0 — free APIs only. No paid features. Ever. |
| Sections | 27 — implement in strict order, do not skip any |
| New in V5 | 10 algorithmic modules + full report redesign for human readability |
| Report delivery | Email (Gmail) — phone & watch optimised. Browser link for overflow |
| Quality target | ~9.5/10 analytical quality · Beginner-readable output |

> **CRITICAL DISCLAIMER:** This system does NOT perform trading, does NOT give investment advice, and does NOT make price predictions. It is a research data aggregation and scoring tool only. This disclaimer MUST appear in every generated report and email.

---

### What is new in V5 vs V4

| Area | V4 State | V5 Change |
|---|---|---|
| Algorithmic modules | 7 analyzers | +10 new modules (sections §10–§19) |
| Volume analysis | 20-day avg, 0-100 score | 30-day avg, ratio-based, plain label |
| Momentum | Single 20-day return | Risk-adjusted + multi-timeframe (1m/3m/6m) |
| Sector breadth | Daily advance/decline | Stocks above 50-day MA — structural breadth |
| Event scoring | Static keyword weight | + exponential recency decay |
| Sector rotation | Rank history only | + rotation speed (rate of change) |
| Risk model | 6 components | + drawdown risk (90-day peak decline) |
| Confidence model | Additive weighted avg | Multiplicative signal agreement |
| Unusual activity | Not detected | Explicit unusual volume flag + ranking boost |
| Report language | Technical scores | Plain English with jargon in parentheses |
| Report delivery | HTML on GitHub Pages | Email-first (phone/watch) + browser overflow |
| Report structure | Flat ranked list | Market pulse → Low Risk → Moderate Risk → Summary |
| Closing report | Run summary table | Full day story + ranked list + watch tomorrow |
| Agent continuity | Not present in V3 | AGENT_PROGRESS.md protocol (carried from V4) |

---

## §00 AGENT CONTINUITY PROTOCOL — READ THIS FIRST

This project is too large to finish in one Antigravity session on the free tier. This protocol ensures the agent can always resume cleanly without redoing work or losing decisions made in previous sessions.

### The Progress File

A file named `AGENT_PROGRESS.md` lives in the project root from the first session onward. The agent maintains it. The human pastes its contents at the start of every new session. It is the single source of truth for where work left off.

### Update Rules — Mandatory

- **Rule 1** — Before starting any file, write exactly: `NOW WORKING ON: [filename] — §[section number]`
- **Rule 2** — After completing a file successfully, write: `COMPLETED: [filename] | NEXT: [next filename]`
- **Rule 3** — After completing a full section, write: `SECTION COMPLETE: §[N] [section name]`
- **Rule 4** — These updates are the very FIRST and very LAST thing written in any work block. Never write code before the before-update. Never end a session without the after-update.
- **Rule 5** — If usage runs out mid-file, the progress file will show `NOW WORKING ON`. This tells the human that file is incomplete. At next session, inspect and complete that file before moving to the next one.

### AGENT_PROGRESS.md Template

```markdown
# AGENT PROGRESS FILE

## Session Log
- Session 1: [date] — completed §00 through §04

## Completed Sections
- §00 Agent Continuity Protocol
- §01 Purpose and Constraints

## Completed Files
- COMPLETED: requirements.txt
- COMPLETED: config.py
- COMPLETED: utils/logger.py

## Current Status
NOW WORKING ON: utils/state_manager.py — §04

## Decisions Made (any deviation from roadmap)
- None yet

## Next File After Current
utils/retry.py — §04

## Do Not Redo
(list files human has manually confirmed complete)
```

### How the Human Uses This

At the start of every new session paste the full contents of `AGENT_PROGRESS.md` as your first message with the instruction: *"Continue the stock research system from where you left off. Here is your progress file: [paste]"*. If a file shows `NOW WORKING ON`, tell the agent to inspect and complete that file first.

---

## §01 PURPOSE & HARD CONSTRAINTS

Build a fully automated daily stock research assistant. It monitors macroeconomic news, detects which sectors are affected, validates those sectors with ETF and momentum data, filters candidate companies, scores them with a multi-signal analytical model, and delivers plain-English research reports by email — readable on a phone or smartwatch.

| Constraint | Requirement |
|---|---|
| Cost | $0. No paid APIs, no paid datasets, no paid services. Ever. |
| ML/Training | No machine-learning. Deterministic algorithmic logic only. |
| Automation | Fully automated after one-time setup. Zero daily human intervention. |
| Crash policy | A single API failure must NEVER crash the run. Log and continue. |
| State safety | Mid-run crash must NEVER corrupt daily_state.json. Atomic writes only. |
| Duplicates | A company must never appear more than once per calendar day. |
| No trading | Research reports only. No order placement, no buy/sell signals. |
| Language | All report text in plain English. Technical terms in parentheses only. |
| Delivery | Primary: email (Gmail SMTP). Overflow: GitHub Pages browser link. |

---

## §02 TECHNOLOGY STACK & DEPENDENCIES

| Item | Specification |
|---|---|
| Language | Python 3.11 exactly |
| Automation | GitHub Actions free tier |
| Hosting | GitHub Pages (free, deploy from main branch) |
| Email | Gmail SMTP via smtplib (standard library — no install) |
| Price/financial data | yfinance (free, no API key required) |
| News — Finnhub | finnhub-python (free tier, API key required) |
| News — RSS | feedparser — Reuters and FT RSS feeds |
| Fundamentals cache | Alpha Vantage free tier (25 req/day, API key required) |
| Report templating | Jinja2 |
| Data processing | pandas, numpy, statistics (stdlib) |
| Utilities | python-dateutil, pytz, GitPython, requests, scikit-learn |

`requirements.txt` must explicitly include: `yfinance finnhub-python requests pandas numpy feedparser jinja2 scikit-learn GitPython python-dateutil pytz`

> **NEVER** call `datetime.now()` — always use `datetime.now(pytz.utc)`. DO NOT install or import `transformers`. No module may use `print()` for operational output.

---

## §03 COMPLETE PROJECT FILE STRUCTURE

Every file listed must be created. Do not rename directories.

```
project/
├── main.py                              # orchestrator — entry point
├── config.py                            # constants, API key loading from env vars
├── requirements.txt
├── validate_tickers.py                  # one-time setup script
├── AGENT_PROGRESS.md                    # MANDATORY — agent continuity file
│
├── utils/
│   ├── logger.py
│   ├── state_manager.py
│   └── retry.py
│
├── collectors/
│   ├── news_collector.py
│   ├── market_collector.py              # indices: Dow, S&P 500, Nasdaq
│   └── financial_parser.py             # ONLY file that calls yf.Ticker() for financials
│
├── analyzers/
│   ├── event_detector.py
│   ├── sector_mapper.py
│   ├── sector_validator.py             # 3-signal + multi-timeframe confirmation
│   ├── sector_momentum.py              # momentum scores + cross-sector ranking
│   ├── market_regime.py                # VIX regime detection
│   ├── market_breadth.py               # daily advance/decline breadth
│   ├── news_impact_scorer.py           # event impact gate (threshold 0.6)
│   ├── volume_confirmation.py          # NEW §10 — volume ratio vs 30-day avg
│   ├── risk_adjusted_momentum.py       # NEW §11 — return divided by volatility
│   ├── multi_timeframe_momentum.py     # NEW §12 — 1m/3m/6m weighted momentum
│   ├── sector_breadth_ma.py            # NEW §13 — stocks above 50-day MA
│   ├── event_decay.py                  # NEW §14 — exponential event recency decay
│   ├── sector_rotation_speed.py        # NEW §15 — momentum rate of change
│   ├── trend_stability.py              # NEW §16 — distance from MA50 over time
│   ├── drawdown_risk.py                # NEW §17 — 90-day peak decline
│   ├── signal_agreement.py             # NEW §18 — multiplicative confidence model
│   ├── unusual_volume.py               # NEW §19 — unusual activity flag
│   ├── risk_model.py
│   ├── opportunity_model.py
│   └── zscore_ranker.py
│
├── filters/
│   └── candidate_filter.py
│
├── reports/
│   ├── report_builder.py               # UPGRADED — plain English templates
│   ├── email_builder.py                # NEW — phone/watch optimised email HTML
│   ├── summary_builder.py              # closing report builder
│   ├── email_sender.py
│   └── templates/
│       ├── intraday_email.html         # NEW — email template (top 7 companies)
│       ├── intraday_full.html          # NEW — browser overflow full report
│       ├── closing_email.html          # NEW — closing report email template
│       └── closing_full.html           # NEW — closing full browser report
│
├── state/daily_state.json
│
├── data/
│   ├── event_keywords.json
│   ├── event_to_sector.json
│   ├── sector_etfs.json
│   ├── sector_breadth_stocks.json
│   ├── sector_tickers.json
│   ├── sector_tickers_validated.json
│   ├── sector_momentum_history.json
│   ├── plain_english_terms.json        # NEW — jargon-to-plain-English lookup
│   └── fundamentals_cache/
│
├── reports/output/
├── logs/
└── .github/workflows/market_scan.yml
```

---

## §04 UTILS MODULE — IMPLEMENT FIRST

### 4.1 utils/logger.py — unchanged from V4

Centralised logging to file and stdout. UTC timestamps. `get_logger(module_name)` returns a configured Logger instance.

### 4.2 utils/state_manager.py — extended for V5

```python
DEFAULT_STATE = {
    'date': '',
    'reported_companies': [],
    'alpha_vantage_calls_today': 0,
    'runs': {
        '10:30': {'companies': [], 'status': 'pending'},
        '12:30': {'companies': [], 'status': 'pending'},
        '14:30': {'companies': [], 'status': 'pending'},
        '16:10': {'companies': [], 'status': 'pending'},
    },
    'failed_tickers': [],
    'api_failures': {},
    'sector_scores_today': {},       # momentum scores per sector
    'breadth_score_today': None,     # daily advance/decline breadth
    'sector_breadth_ma_today': {},   # NEW: stocks-above-50MA per sector
    'unusual_volume_flags': [],      # NEW: tickers with unusual volume today
    'event_scores_today': {},        # NEW: impact scores per event cluster
    'indices_today': {},             # NEW: Dow, S&P 500, Nasdaq readings
}
```

Atomic write pattern unchanged: write to `.tmp` file then `shutil.move` to final path. Never write state directly. Always use `save_state()`.

### 4.3 utils/retry.py — unchanged from V4

Exponential backoff decorator. 429 rate limit doubles wait time. All retries exhausted returns `None`, never raises.

---

## §05 DATA FILES — REQUIRED SCHEMAS

### 5.1 data/event_keywords.json — unchanged from V4

Three tiers: major (weight 3, min 20 terms), moderate (weight 2, min 20 terms), minor (weight 1, min 18 terms).

### 5.2 data/event_to_sector.json — unchanged from V4

20 event types. Every sector entry has `direction` (positive/negative) and `confidence`. Static weights — dynamic adjustment handled at runtime by `event_decay.py`.

### 5.3 data/sector_momentum_history.json — carried from V4

Rolling 10-day sector rank history. Updated every run. Used by `sector_rotation_speed.py` for rate-of-change detection.

### 5.4 data/plain_english_terms.json — NEW

Lookup table mapping every technical term used in the system to a plain English description. Used by `report_builder.py` and `email_builder.py`. Every term that appears in a report must exist in this file.

```json
{
  "momentum": "how strongly and consistently the price has been rising",
  "volume": "how many shares are being traded — higher means more people are active",
  "volatility": "how much the price jumps up and down day to day",
  "debt_to_equity": "how much debt the company carries compared to what it owns",
  "profit_margin": "how many cents the company keeps from every dollar it earns",
  "moving_average": "the average price over recent weeks — shows the general trend direction",
  "drawdown": "how far the stock has fallen from its recent highest price",
  "sector": "the industry group this company belongs to",
  "ETF": "a fund that tracks an entire sector — used to measure sector health",
  "breadth": "how many stocks in a sector are moving in the same direction",
  "regime": "the current overall market environment based on fear levels",
  "VIX": "the market fear index — higher means more uncertainty overall",
  "relative_strength": "how this stock is performing compared to others in its sector",
  "signal_agreement": "how many of our indicators are pointing in the same direction"
}
```

---

## §06 validate_tickers.py — ONE-TIME SETUP

Run once before first deploy. Checks every ticker against yfinance. Writes `sector_tickers_validated.json`. V5 adds a $5 price floor filter and logs cap tier (large/mid) per ticker.

> **CRITICAL:** `main.py` exits with code 1 if `sector_tickers_validated.json` is missing. Warns (no exit) if `validated_date` is more than 30 days old.

Filters applied during validation:
- Quote type must be EQUITY
- Exchange must be in: NMS, NYQ, NGM, NCM, ASE
- Market cap >= $500 million
- Average volume >= 500,000 shares/day
- Current price >= $5.00
- Sector must match SECTOR_EQUIVALENCE mapping
- Industry keyword check for subset sectors (semiconductors, defense, etc.)

---

## §07 collectors/financial_parser.py — DATA ISOLATION

ONLY file allowed to call `yf.Ticker()` for financial statement data. No other module may touch yfinance DataFrames directly. Always returns a dict with all keys. Missing values are `None`, never errors. Handles both DataFrame orientations (metrics as rows OR columns).

**V5 addition:** add `current_price` to the output dict. Use `info.get('currentPrice')` or `info.get('regularMarketPrice')`. Required by `candidate_filter.py` for the $5 price floor check at runtime.

`cross_validate()` compares only structurally-identical fields with Alpha Vantage: `market_cap` (5% tolerance), `debt_to_equity` (15% tolerance). Never compare revenue or net_income — TTM vs annual differences are expected and normal.

---

## §08 collectors/news_collector.py

Three sources: Reuters RSS, FT RSS, Finnhub general news. All three failing triggers empty report and `sys.exit(0)`.

Deduplication uses `difflib.SequenceMatcher` at 0.85 similarity threshold. Three-stage pre-filter: source approval, temporal check, 6-hour freshness. `SectorSignalAccumulator` requires minimum 2 headlines and combined score 6 before a sector is queued for validation. This is gate one.

### §08b collectors/market_collector.py — UPGRADED

Fetches Dow Jones (`^DJI`), S&P 500 (`^GSPC`), and Nasdaq (`^IXIC`) every run. Returns current value, percentage change today, and a plain English direction label. Stored in `state['indices_today']` for use by all report templates.

```python
# market_collector.py — core function
def get_index_snapshot() -> dict:
    '''
    Returns current readings for the three major US indices.
    Called once per run. Results stored in state for report templates.
    Direction label: Rising / Falling / Flat (within 0.1%)
    '''
    indices = {
        'dow':    '^DJI',
        'sp500':  '^GSPC',
        'nasdaq': '^IXIC',
    }
    result = {}
    for name, ticker in indices.items():
        try:
            d = yf.Ticker(ticker).history(period='2d')
            if d is None or len(d) < 2:
                result[name] = {'value': None, 'change_pct': None, 'label': 'unavailable'}
                continue
            prev  = float(d['Close'].iloc[-2])
            curr  = float(d['Close'].iloc[-1])
            chg   = ((curr - prev) / prev) * 100 if prev != 0 else 0.0
            label = 'Rising' if chg > 0.1 else 'Falling' if chg < -0.1 else 'Flat'
            result[name] = {
                'value':      round(curr, 2),
                'change_pct': round(chg, 2),
                'label':      label,
            }
        except Exception as e:
            log.warning(f'Index {name}: {e}')
            result[name] = {'value': None, 'change_pct': None, 'label': 'unavailable'}
    return result
```

---

## §09 Core Analyzer Modules — Carried from V4

The following modules are fully specified in V4 and carry forward unchanged into V5. The agent must implement them exactly as specified.

| Module | Purpose | Key rule |
|---|---|---|
| analyzers/news_impact_scorer.py | Second gate after keyword scoring. Events below 0.6 impact are dropped. | `impact = (source_count*0.4) + (keyword_weight*0.3) + (spy_move*0.3)` |
| analyzers/sector_momentum.py | Scores all 13 sectors on 5d and 10d return + relative strength vs SPY. | Only top 5 ranked sectors proceed to ETF confirmation |
| analyzers/market_breadth.py | Daily advance/decline breadth across sector_breadth_stocks. | Score >0.6 = strong. 0.4-0.6 = neutral. <0.4 = weak. Multiplies opp score. |
| analyzers/sector_validator.py | 3-signal ETF confirmation + multi-timeframe gate. | Must pass 2 of 3 signals AND 5d/10d must align with 1d direction |
| analyzers/market_regime.py | VIX regime classification. Called once per run. | low_vol / normal / elevated / crisis — each has risk_mult and opp_mult |
| analyzers/zscore_ranker.py | Z-score normalisation across full candidate pool. | Max 3 per sector. Max 25 total. risk_score > risk_cap excluded. |

---

## §10 analyzers/volume_confirmation.py — NEW

Measures how strong a price movement is based on trading participation. A price rise on low volume may be weak. A price rise with high volume has stronger real-world participation behind it.

```python
# analyzers/volume_confirmation.py
#
# WHAT THIS MEASURES:
# Volume = the number of shares being bought and sold on a given day.
# We compare today's volume to the average of the past 30 days.
# If many more people than usual are trading, the price move is more meaningful.

import yfinance as yf
from utils.logger import get_logger
from utils.retry import retry_on_failure

log = get_logger('volume_confirmation')

@retry_on_failure(max_attempts=2, delay=2.0)
def compute_volume_confirmation(ticker: str) -> dict:
    '''
    Returns volume_ratio and a plain English label.
    volume_ratio = today_volume / 30_day_average_volume

    Interpretation:
      < 0.8  → fewer people trading than usual (weak participation)
      0.8-1.2 → normal trading activity
      > 1.2  → more people trading than usual (strong interest)
      > 2.0  → unusually high activity (major market attention)

    volume_score is normalised 0.0-1.0 for use in signal_agreement.py
    '''
    try:
        d = yf.Ticker(ticker).history(period='35d')
        if d is None or len(d) < 31:
            return {'volume_ratio': None, 'volume_score': 0.5, 'label': 'unavailable'}

        today_vol   = float(d['Volume'].iloc[-1])
        avg_30d_vol = float(d['Volume'].iloc[-31:-1].mean())

        if avg_30d_vol == 0:
            return {'volume_ratio': None, 'volume_score': 0.5, 'label': 'unavailable'}

        ratio = today_vol / avg_30d_vol
        score = min(1.0, ratio / 3.0)   # normalise to 0-1 (ratio 3.0 = score 1.0)

        if ratio < 0.8:   label = 'lower activity than usual'
        elif ratio < 1.2: label = 'normal trading activity'
        elif ratio < 2.0: label = 'higher activity than usual'
        else:             label = 'unusually high trading activity'

        log.info(f'{ticker} volume ratio={ratio:.2f} score={score:.2f} label={label}')
        return {
            'volume_ratio': round(ratio, 2),
            'volume_score': round(score, 3),
            'label':        label,
        }
    except Exception as e:
        log.warning(f'volume_confirmation({ticker}): {e}')
        return {'volume_ratio': None, 'volume_score': 0.5, 'label': 'unavailable'}
```

---

## §11 analyzers/risk_adjusted_momentum.py — NEW

Two stocks can have the same 3-month return but very different stability. One rose steadily every week. The other jumped and crashed repeatedly. This module rewards the steady one by dividing return by volatility.

```python
# analyzers/risk_adjusted_momentum.py
#
# Formula: risk_adjusted_momentum = return_3m / volatility_3m
# return_3m    = (price_now - price_63d_ago) / price_63d_ago * 100
# volatility_3m = standard deviation of daily % returns over 63 days
#
# Higher score = stronger AND more stable trend (ideal)
# Near zero    = weak trend or very chaotic price movement
# Negative     = price has been falling over 3 months

import yfinance as yf, statistics
from utils.logger import get_logger
from utils.retry import retry_on_failure

log = get_logger('risk_adjusted_momentum')

@retry_on_failure(max_attempts=2, delay=2.0)
def compute_risk_adjusted_momentum(ticker: str) -> dict:
    '''
    Output normalised 0.0-1.0 for signal_agreement.py
    Score of 0.5 = neutral / data unavailable
    '''
    try:
        d = yf.Ticker(ticker).history(period='4mo')
        if d is None or len(d) < 63:
            return {'ram_score': 0.5, 'raw_value': None, 'label': 'unavailable'}

        closes      = list(d['Close'])
        price_now   = closes[-1]
        price_63d   = closes[-63]
        return_3m   = ((price_now - price_63d) / price_63d) * 100 if price_63d > 0 else 0

        daily_returns = [
            ((closes[i] - closes[i-1]) / closes[i-1]) * 100
            for i in range(1, len(closes))
        ]
        volatility_3m = statistics.stdev(daily_returns[-63:]) if len(daily_returns) >= 63 else None

        if not volatility_3m or volatility_3m == 0:
            return {'ram_score': 0.5, 'raw_value': None, 'label': 'unavailable'}

        raw   = return_3m / volatility_3m
        score = max(0.0, min(1.0, (raw + 10) / 20))   # normalise: raw -10..+10 → 0..1

        if raw > 3:    label = 'very stable upward trend'
        elif raw > 1:  label = 'steady upward trend'
        elif raw > 0:  label = 'mild positive trend'
        elif raw > -1: label = 'flat or slightly declining'
        else:          label = 'declining with instability'

        log.info(f'{ticker} RAM raw={raw:.2f} score={score:.2f}')
        return {
            'ram_score':    round(score, 3),
            'raw_value':    round(raw, 2),
            'return_3m':    round(return_3m, 2),
            'volatility':   round(volatility_3m, 2),
            'label':        label,
        }
    except Exception as e:
        log.warning(f'risk_adjusted_momentum({ticker}): {e}')
        return {'ram_score': 0.5, 'raw_value': None, 'label': 'unavailable'}
```

---

## §12 analyzers/multi_timeframe_momentum.py — NEW

Combines short, medium, and long trend signals into one score. A stock rising across all three timeframes is much more convincing than one that spiked recently but was flat before that.

```python
# analyzers/multi_timeframe_momentum.py
#
# Formula: momentum_score = (return_3m * 0.5) + (return_6m * 0.3) + (return_1m * 0.2)
# Why 3 months has highest weight: long enough to confirm a real trend,
# short enough to be relevant now.

import yfinance as yf
from utils.logger import get_logger
from utils.retry import retry_on_failure

log = get_logger('multi_timeframe_momentum')

@retry_on_failure(max_attempts=2, delay=2.0)
def compute_mtf_momentum(ticker: str) -> dict:
    '''
    Returns combined_momentum_score normalised 0.0-1.0.
    If a timeframe is unavailable, weight is redistributed.
    '''
    try:
        d = yf.Ticker(ticker).history(period='7mo')
        if d is None or len(d) < 21:
            return {'mtf_score': 0.5, 'label': 'unavailable', 'r1m': None, 'r3m': None, 'r6m': None}

        closes = list(d['Close'])
        curr   = closes[-1]

        def ret(n):
            if len(closes) < n + 1: return None
            p = closes[-(n+1)]
            return ((curr - p) / p) * 100 if p > 0 else None

        r1m = ret(21)    # ~1 month trading days
        r3m = ret(63)    # ~3 months
        r6m = ret(126)   # ~6 months

        available    = [(r3m, 0.5), (r6m, 0.3), (r1m, 0.2)]
        valid        = [(r, w) for r, w in available if r is not None]
        if not valid:
            return {'mtf_score': 0.5, 'label': 'unavailable', 'r1m': None, 'r3m': None, 'r6m': None}

        total_weight  = sum(w for _, w in valid)
        weighted_sum  = sum(r * (w / total_weight) for r, w in valid)
        score         = max(0.0, min(1.0, (weighted_sum + 30) / 60))  # -30%..+30% → 0..1

        if weighted_sum > 15:   label = 'strong upward trend across all timeframes'
        elif weighted_sum > 5:  label = 'positive trend building over time'
        elif weighted_sum > 0:  label = 'mildly positive — early stage'
        elif weighted_sum > -5: label = 'flat — no clear direction'
        else:                   label = 'declining across multiple timeframes'

        log.info(f'{ticker} MTF 1m={r1m} 3m={r3m} 6m={r6m} score={score:.2f}')
        return {
            'mtf_score':  round(score, 3),
            'raw_score':  round(weighted_sum, 2),
            'r1m':        round(r1m, 2) if r1m is not None else None,
            'r3m':        round(r3m, 2) if r3m is not None else None,
            'r6m':        round(r6m, 2) if r6m is not None else None,
            'label':      label,
        }
    except Exception as e:
        log.warning(f'mtf_momentum({ticker}): {e}')
        return {'mtf_score': 0.5, 'label': 'unavailable', 'r1m': None, 'r3m': None, 'r6m': None}
```

---

## §13 analyzers/sector_breadth_ma.py — NEW

The daily advance/decline breadth measures one-day movement. This module measures structural health: what percentage of stocks in a sector are trading above their 50-day moving average. This reflects weeks of trend, not just today.

```python
# analyzers/sector_breadth_ma.py
#
# Interpretation:
# > 70% above MA50 → sector is genuinely strong
# 50-70%           → healthy participation
# 30-50%           → mixed / neutral
# < 30%            → sector is structurally weak

import yfinance as yf
from utils.logger import get_logger
from utils.retry import retry_on_failure

log = get_logger('sector_breadth_ma')

@retry_on_failure(max_attempts=2, delay=2.0)
def _above_ma50(ticker: str) -> bool | None:
    try:
        d = yf.Ticker(ticker).history(period='3mo')
        if d is None or len(d) < 50: return None
        return float(d['Close'].iloc[-1]) > float(d['Close'].tail(50).mean())
    except Exception as e:
        log.warning(f'MA50 check {ticker}: {e}')
        return None

def compute_sector_breadth_ma(sector_breadth_stocks: dict) -> dict:
    '''
    Returns dict: {sector: {'breadth_ma_score': 0-1, 'label': str, 'pct': float}}
    Called once per run. Results stored in state['sector_breadth_ma_today'].
    '''
    results = {}
    for sector, tickers in sector_breadth_stocks.items():
        above = 0; checked = 0
        for ticker in tickers:
            r = _above_ma50(ticker)
            if r is None: continue
            checked += 1
            if r: above += 1

        if checked == 0:
            results[sector] = {'breadth_ma_score': 0.5, 'label': 'unavailable', 'pct': None}
            continue

        pct   = above / checked
        score = pct   # already 0-1

        if pct > 0.70:    label = 'sector is genuinely strong'
        elif pct > 0.50:  label = 'healthy participation'
        elif pct >= 0.30: label = 'mixed signals'
        else:             label = 'sector is structurally weak'

        log.info(f'Sector breadth MA {sector}: {above}/{checked} = {pct:.2f} ({label})')
        results[sector] = {
            'breadth_ma_score': round(score, 3),
            'pct':              round(pct * 100, 1),
            'label':            label,
        }
    return results
```

---

## §14 analyzers/event_decay.py — NEW

A news event from this morning has strong influence. The same event from last week should matter less — markets have had time to react and price it in.

```python
# analyzers/event_decay.py
#
# Formula: adjusted_score = original_score * exp(-days_since_event / 10)
#
# Examples with original_score = 10:
#   0 days ago  → 10.0  (full weight)
#   3 days ago  →  7.4
#   7 days ago  →  4.9
#  14 days ago  →  2.5
#  30 days ago  →  0.5  (almost no influence)

import math
from utils.logger import get_logger

log = get_logger('event_decay')
DECAY_FACTOR = 10   # controls fade speed — do not change

def apply_event_decay(original_score: float, days_since_event: int) -> float:
    if days_since_event < 0:
        log.warning(f'Negative days_since_event={days_since_event} — treating as 0')
        days_since_event = 0
    adjusted = original_score * math.exp(-days_since_event / DECAY_FACTOR)
    log.info(f'Event decay: {original_score:.2f} -> {adjusted:.2f} ({days_since_event}d old)')
    return round(adjusted, 3)

def decay_event_cluster(events: list[dict]) -> list[dict]:
    '''
    Each dict must have: 'score' (float) and 'days_old' (int).
    Returns updated list with 'adjusted_score' added to each event.
    '''
    for event in events:
        event['adjusted_score'] = apply_event_decay(
            event.get('score', 0),
            event.get('days_old', 0)
        )
    return events
```

**Pipeline integration:** in `event_detector.py`, after `SectorSignalAccumulator.confirmed()` returns candidate sectors, apply decay to each event's score based on its timestamp before passing to `news_impact_scorer.py`. Use `adjusted_score`, not the original.

---

## §15 analyzers/sector_rotation_speed.py — NEW

Detects sectors gaining or losing momentum quickly. A sector that jumped from rank 8 to rank 2 in seven days is accelerating — that acceleration signals institutional money may be rotating in.

```python
# analyzers/sector_rotation_speed.py
#
# Formula: rotation_speed = momentum_score_today - momentum_score_7_days_ago
# Positive → sector is accelerating upward
# Near zero → stable
# Negative → losing strength

import json
from utils.logger import get_logger

log = get_logger('sector_rotation_speed')
HISTORY_FILE = 'data/sector_momentum_history.json'

def compute_rotation_speed(current_scores: dict) -> dict:
    '''
    current_scores: dict from sector_momentum.py — {sector: {'score': float}}
    Compares to entry from 7 days ago in history file.
    Returns {sector: {'rotation_speed': float, 'label': str, 'accelerating': bool}}
    '''
    try:
        with open(HISTORY_FILE) as f: history = json.load(f)
    except Exception as e:
        log.warning(f'Rotation speed: cannot load history ({e})')
        return {}

    entries = history.get('history', [])
    if len(entries) < 2:
        log.info('Rotation speed: not enough history yet — skipping')
        return {}

    target_entry  = entries[-min(7, len(entries))]
    past_rankings = target_entry.get('rankings', {})

    results = {}
    for sector, data in current_scores.items():
        curr_rank = data.get('rank', 99)
        past_rank = past_rankings.get(sector, 99)
        speed     = past_rank - curr_rank   # negative rank change = moved up = positive speed

        if speed > 3:      label = 'rapidly gaining strength'
        elif speed > 1:    label = 'gaining momentum'
        elif speed >= -1:  label = 'stable'
        elif speed >= -3:  label = 'losing momentum'
        else:              label = 'rapidly losing strength'

        results[sector] = {
            'rotation_speed': speed,
            'label':          label,
            'accelerating':   speed > 2,
        }
        log.info(f'Rotation {sector}: rank {past_rank} -> {curr_rank} speed={speed} ({label})')
    return results
```

---

## §16 analyzers/trend_stability.py — NEW

Measures how smooth a price trend is over time. A stock that rises steadily is more reliable than one that jumps and crashes repeatedly even if both ended at the same price.

```python
# analyzers/trend_stability.py
#
# Formula: deviation_each_day = |price - MA50| / MA50
#          trend_stability = average of those deviations over 50 days
# Score is INVERTED: lower deviation = higher score (better).

import yfinance as yf
from utils.logger import get_logger
from utils.retry import retry_on_failure

log = get_logger('trend_stability')

@retry_on_failure(max_attempts=2, delay=2.0)
def compute_trend_stability(ticker: str) -> dict:
    '''
    Returns trend_stability_score normalised 0.0-1.0 where 1.0 = very stable.
    NOTE: trend_stability_score is computed for report display.
    It is not currently used in opportunity or risk scoring.
    '''
    try:
        d = yf.Ticker(ticker).history(period='3mo')
        if d is None or len(d) < 50:
            return {'stability_score': 0.5, 'label': 'unavailable', 'raw_deviation': None}

        closes     = list(d['Close'])
        deviations = []
        for i in range(len(closes) - 50, len(closes)):
            window = closes[i-49:i+1]
            ma50   = sum(window) / 50
            if ma50 > 0:
                deviations.append(abs(closes[i] - ma50) / ma50)

        if not deviations:
            return {'stability_score': 0.5, 'label': 'unavailable', 'raw_deviation': None}

        avg_deviation = sum(deviations) / len(deviations)
        score         = max(0.0, min(1.0, 1.0 - (avg_deviation / 0.10)))  # invert: 0%=1.0, 10%+=0.0

        if score > 0.80:   label = 'very smooth and stable trend'
        elif score > 0.60: label = 'reasonably stable trend'
        elif score > 0.40: label = 'some volatility in the trend'
        else:              label = 'choppy and unstable — treat with caution'

        log.info(f'{ticker} trend stability: dev={avg_deviation:.4f} score={score:.2f}')
        return {
            'stability_score': round(score, 3),
            'raw_deviation':   round(avg_deviation, 4),
            'label':           label,
        }
    except Exception as e:
        log.warning(f'trend_stability({ticker}): {e}')
        return {'stability_score': 0.5, 'label': 'unavailable', 'raw_deviation': None}
```

---

## §17 analyzers/drawdown_risk.py — NEW

Measures how far a stock has fallen from its recent highest price. A stock trading 35% below its 90-day high carries meaningful risk regardless of how good its fundamentals look.

```python
# analyzers/drawdown_risk.py
#
# Formula: max_drawdown_90d = (highest_price_in_90d - current_price) / highest_price_in_90d
#
# Interpretation:
# < 10%  → very strong trend, barely off its recent high
# 10-20% → normal market volatility — acceptable
# > 20%  → meaningful decline — adds risk
# > 35%  → significant decline — flag clearly in report
#
# Score is INVERTED: lower drawdown = higher score (better).

import yfinance as yf
from utils.logger import get_logger
from utils.retry import retry_on_failure

log = get_logger('drawdown_risk')

@retry_on_failure(max_attempts=2, delay=2.0)
def compute_drawdown_risk(ticker: str) -> dict:
    '''
    Returns drawdown_score 0.0-1.0 where 1.0 = no drawdown (near 90-day high).
    drawdown_pct is the raw percentage decline from the 90-day peak.
    Added to risk_model as a 10% weighted component.
    '''
    try:
        d = yf.Ticker(ticker).history(period='5mo')
        if d is None or len(d) < 63:
            return {'drawdown_score': 0.5, 'drawdown_pct': None, 'label': 'unavailable'}

        recent      = d['Close'].tail(90)
        current     = float(recent.iloc[-1])
        peak_90d    = float(recent.max())

        if peak_90d == 0:
            return {'drawdown_score': 0.5, 'drawdown_pct': None, 'label': 'unavailable'}

        drawdown_pct = ((peak_90d - current) / peak_90d) * 100
        score        = max(0.0, min(1.0, 1.0 - (drawdown_pct / 40)))  # 0%=1.0, 40%+=0.0

        if drawdown_pct < 10:   label = 'near its recent high — strong position'
        elif drawdown_pct < 20: label = 'moderate dip from recent high — normal'
        elif drawdown_pct < 35: label = 'significant decline from recent high'
        else:                   label = 'major decline — review carefully before research'

        log.info(f'{ticker} drawdown={drawdown_pct:.1f}% score={score:.2f}')
        return {
            'drawdown_score': round(score, 3),
            'drawdown_pct':   round(drawdown_pct, 1),
            'label':          label,
        }
    except Exception as e:
        log.warning(f'drawdown_risk({ticker}): {e}')
        return {'drawdown_score': 0.5, 'drawdown_pct': None, 'label': 'unavailable'}
```

**Integration with risk_model.py:** add `drawdown_score` as a 10% weighted component. Updated weights: debt(22%), vol(18%), liq(18%), eps(14%), margin(9%), mcap(9%), drawdown(10%). The drawdown component uses `(1 - drawdown_score)` so higher drawdown = higher risk.

---

## §18 analyzers/signal_agreement.py — NEW

Confidence increases when multiple independent signals agree. This module uses multiplication — if even one signal is very weak, the overall confidence is pulled down significantly. This is stricter than a simple average.

```python
# analyzers/signal_agreement.py
#
# Formula: raw = momentum * sector_strength * event_score * volume_score
#
# Why this works:
# momentum=0.9, sector=0.9, event=0.9, volume=0.1 → result=0.07 (very low)
# momentum=0.8, sector=0.8, event=0.8, volume=0.8 → result=0.41 (moderate)
# ALL signals must align for a high score.

from utils.logger import get_logger

log = get_logger('signal_agreement')

def compute_signal_agreement(
    momentum_score:  float,
    sector_strength: float,
    event_score:     float,
    volume_score:    float,
) -> dict:
    '''
    All inputs must be in range 0.0-1.0.
    Missing inputs default to 0.5 (neutral) — never block the calculation.
    Returns agreement_score 0.0-1.0 and a plain English confidence label.

    NOTE: The multiplicative formula compresses scores significantly.
    With all inputs at 0.8: 0.8^4 = 0.41.
    Treat scores above 0.35 as strong agreement for this system.
    '''
    m = max(0.0, min(1.0, momentum_score  or 0.5))
    s = max(0.0, min(1.0, sector_strength or 0.5))
    e = max(0.0, min(1.0, event_score     or 0.5))
    v = max(0.0, min(1.0, volume_score    or 0.5))

    score = m * s * e * v  # multiplicative combination — already 0-1

    if score > 0.35:   label = 'strong agreement across all signals'
    elif score > 0.20: label = 'moderate agreement — most signals aligned'
    elif score > 0.08: label = 'partial agreement — some signals conflicting'
    else:              label = 'weak agreement — signals not aligned'

    log.info(f'Signal agreement: m={m:.2f} s={s:.2f} e={e:.2f} v={v:.2f} -> {score:.3f}')
    return {
        'agreement_score': round(score, 3),
        'label':           label,
        'inputs':          {'momentum': m, 'sector': s, 'event': e, 'volume': v},
    }

def sector_rank_to_score(rank: int, total_sectors: int = 13) -> float:
    '''Convert sector rank (1=best) to 0-1 score for signal_agreement input.'''
    return max(0.0, (total_sectors - rank) / (total_sectors - 1))
```

> **Note on thresholds:** The multiplicative formula compresses scores. With all four inputs at 0.8 (a strong day), the raw result is 0.41. The thresholds above have been adjusted to reflect this — 0.35 = strong agreement. This is correct behaviour; treat it as intentionally conservative.

---

## §19 analyzers/unusual_volume.py — NEW

Detects abnormal trading activity. When a stock suddenly trades at 3x or more of its normal volume, something significant is likely happening.

```python
# analyzers/unusual_volume.py
#
# Thresholds:
# ratio > 2.0 → strong attention — significantly more activity than normal
# ratio > 3.0 → very unusual — something significant may be happening
# ratio > 5.0 → extreme — major event, news, or institutional move
#
# NOTE: Unusual volume alone is not a buy signal.
# It means: pay attention. Investigate why.

from utils.logger import get_logger

log = get_logger('unusual_volume')

THRESHOLDS = [
    (5.0, 'extreme activity — investigate immediately'),
    (3.0, 'very unusual trading volume'),
    (2.0, 'significantly more active than normal'),
]

def detect_unusual_volume(ticker: str, volume_ratio: float | None) -> dict:
    '''
    volume_ratio: output from volume_confirmation.compute_volume_confirmation()
    Reuses volume data — do NOT re-fetch yfinance data here.
    Returns flag dict. unusual_flag=True boosts ranking in zscore_ranker.py.
    '''
    if volume_ratio is None:
        return {'unusual_flag': False, 'label': 'volume data unavailable', 'ratio': None}

    for threshold, label in THRESHOLDS:
        if volume_ratio >= threshold:
            log.info(f'{ticker} UNUSUAL VOLUME: ratio={volume_ratio:.1f}x — {label}')
            return {
                'unusual_flag': True,
                'label':        label,
                'ratio':        volume_ratio,
                'severity':     label.split(' ')[0],
            }

    return {
        'unusual_flag': False,
        'label':        'normal volume range',
        'ratio':        volume_ratio,
        'severity':     None,
    }
```

**Integration with zscore_ranker.py:** if `unusual_flag` is `True`, add 0.3 to the company's `ranking_index` before final sort.

---

## §20 Risk and Opportunity Models — Updated Weight Tables

### 20.1 analyzers/risk_model.py — Updated to include drawdown

| Component | Weight | Input | Formula |
|---|---|---|---|
| Debt risk | 22% | debt_to_equity | `min(100, max(0, d_e * 25))` |
| Volatility | 18% | beta | `min(100, max(0, (beta-0.5)*50))` |
| Liquidity risk | 18% | avg_volume | `max(0, 100-(vol_M * 8))` |
| Earnings instability | 14% | eps_quarterly list | `min(100, (std/abs(mean))*50)` |
| Margin weakness | 9% | profit_margin | `max(0, 100-margin_pct*4)` |
| Market cap risk | 9% | market_cap | `max(0, 100-cap_B*8)` |
| Drawdown risk | 10% | drawdown_pct (from §17) | `(1 - drawdown_score) * 100` |

Earnings proximity penalty and momentum divergence flag unchanged from V4. Final score: `min(100, (raw + earnings_penalty) * regime.risk_mult)`

### 20.2 analyzers/opportunity_model.py — Bucketed Weighting Model

Signals are grouped into three buckets. Each bucket has a fixed total contribution to the final score. This prevents momentum signals from dominating when a stock is trending strongly.

> **ANTI-DOUBLE-COUNTING RULE:** Signals measuring similar properties are placed in the same bucket and share its weight. No bucket may exceed its cap even if all its signals score perfectly. This is **enforced in code, not just a comment.**

**Bucket 1 — Fundamentals (40% of final score)**

| Signal | Share inside bucket | Formula |
|---|---|---|
| Revenue growth YoY | 32.5% | `min(100, max(0, growth_pct * 2.5))` |
| Profit margin | 22.5% | `min(100, max(0, margin_pct * 5.0))` |
| EPS growth YoY | 22.5% | `min(100, max(0, eps_growth_pct * 2.0))` |
| Relative P/E vs sector | 22.5% | `100 - min(100, max(0, (pe/sector_pe-1)*100))` |

`bucket1_score = weighted_avg(signals)` → contributes `bucket1 * 0.40` to final

**Bucket 2 — Momentum (40% of final score)**

All signals measuring price direction live here and share the 40% cap.

| Signal | Share inside bucket | Formula / Source |
|---|---|---|
| Risk-adjusted momentum | 25% | `ram_score * 100` (from §11) |
| Multi-timeframe momentum | 25% | `mtf_score * 100` (from §12) |
| Price momentum 20d | 20% | `min(100, max(0, 50 + ret_20d * 5))` |
| MA trend 50d vs 200d | 15% | P>SMA50>SMA200=100, P>SMA50=65, P>SMA200=40, else=15 |
| Rel. strength vs sector median | 15% | `min(100, max(0, 50+(ret-sector_med)*3))` |

`bucket2_score = weighted_avg(signals)` → contributes `bucket2 * 0.40` to final

**Bucket 3 — Confirmation (20% of final score)**

| Signal | Share inside bucket | Formula / Source |
|---|---|---|
| Volume confirmation | 40% | `volume_score * 100` (from §10) |
| Rel. strength vs ETF | 35% | `min(100, max(0, 50+(stock_ret-etf_ret)*3))` |
| Sector MA breadth | 25% | `breadth_ma_score * 100` (from §13) |

`bucket3_score = weighted_avg(signals)` → contributes `bucket3 * 0.20` to final

**Implementation sketch:**

```python
# Bucket scores are computed independently then combined
raw   = (bucket1_score * 0.40) + (bucket2_score * 0.40) + (bucket3_score * 0.20)
final = min(100, raw * regime.get('opp_mult', 1.0) * breadth_mult)

# Store bucket breakdown for report display:
# 'Financial Health'     = bucket1_score
# 'Price Trend Strength' = bucket2_score
# 'Market Confirmation'  = bucket3_score
```

Final score: `min(100, raw * regime.opp_mult * breadth.opp_multiplier)`. Both multipliers stack. Cap at 100 after both applied.

---

## §21 COMPOSITE CONFIDENCE SCORE — V5 DEFINITION

```python
# V5 Composite Confidence Formula:
composite_confidence = round(
    ((100 - risk_score)          * 0.35) +   # lower risk = higher confidence
    (opportunity_score           * 0.35) +   # stronger opportunity = higher confidence
    (agreement_score * 100       * 0.20) +   # signal agreement from §18
    (sector_momentum_contrib     * 0.10),    # sector strength contribution
    1
)

# sector_momentum_contrib = min(100, max(0, 50 + sector_momentum_score * 10))
# agreement_score is from signal_agreement.py (0.0-1.0 * 100 = 0-100 scale)

# Required report label:  'Composite Confidence Score'
# Forbidden label:        'chance of success' — never use this phrase
# Required disclaimer:    'This score reflects relative risk-adjusted positioning
#                          only. It is NOT a prediction of price movement or return.'
```

| Score | Label | Report section |
|---|---|---|
| 75–100 | Strong confidence | Low Risk section — green |
| 50–74 | Moderate confidence | Low Risk if risk<=30, else Moderate |
| 35–49 | Weak confidence | Moderate Risk section — amber |
| < 35 | Excluded | Do not appear in report |

---

## §22 main.py — COMPLETE PIPELINE EXECUTION ORDER

Every step is mandatory. Do not reorder.

| Step | Action | Output / stored in |
|---|---|---|
| 1 | Startup check — sector_tickers_validated.json exists | sys.exit(1) if missing |
| 2 | Determine run slot (10:30/12:30/14:30/16:10 ET) | slot variable |
| 3 | Load state, check market open, check duplicate slot trigger | state dict |
| 4 | Fetch index snapshot — Dow, S&P 500, Nasdaq | state['indices_today'] |
| 5 | Get VIX regime — get_regime() | regime dict |
| 6 | Compute daily advance/decline breadth — compute_market_breadth() | breadth dict |
| 7 | Compute sector MA breadth — compute_sector_breadth_ma() | state['sector_breadth_ma_today'] |
| 8 | Compute sector momentum scores (all 13 sectors) | scores dict |
| 9 | Compute sector rotation speed vs 7 days ago | rotation dict |
| 10 | Collect and filter news — RSS + Finnhub, dedup, 3-stage filter | articles list |
| 11 | Keyword scoring + SectorSignalAccumulator (min 2 headlines, score 6) | candidate_sectors |
| 12 | Apply event recency decay to each event's score | decayed scores |
| 13 | News impact scoring — sectors below 0.6 threshold dropped | impact-filtered sectors |
| 14 | Sector momentum gate — sectors not in top 5 dropped | momentum-filtered sectors |
| 15 | ETF 3-signal + multi-timeframe confirmation | confirmed_sectors |
| 16 | For each confirmed sector: get sector_pe, sector_median_return | sector context |
| 17 | For each ticker: check reported_companies, get financials, cross-validate | fin dict |
| 18 | Apply candidate_filter — cap, volume, price, OCF, D/E | filtered tickers |
| 19 | Compute volume_confirmation, detect unusual_volume | vol data per ticker |
| 20 | Compute risk_adjusted_momentum, multi_timeframe_momentum | momentum data |
| 21 | Compute trend_stability, drawdown_risk | stability + drawdown data |
| 22 | Compute risk_score (with drawdown component) | risk dict |
| 23 | Compute opportunity_score (with new components + both multipliers) | opp dict |
| 24 | Compute signal_agreement (momentum * sector * event * volume) | agreement dict |
| 25 | Compute composite_confidence | confidence score |
| 26 | Assemble candidate dict per company — all scores, all labels, plain English | all_candidates |
| 27 | Z-score ranking across full candidate pool (unusual_volume bonus +0.3) | final_companies |
| 28 | Build intraday report + email (top 7 in email, rest in browser link) | HTML files |
| 29 | Send email via Gmail SMTP | email sent bool |
| 30 | If slot == 16:10: build closing summary report + send closing email | closing HTML |
| 31 | Commit all outputs to GitHub repo (guard: skip if nothing staged) | git push |
| 32 | Update state: reported_companies, slot status, save_state() | state saved |

---

## §23 REPORT DESIGN — PLAIN ENGLISH OUTPUT SPECIFICATION

### 23.1 Intraday Email (10:30, 12:30, 14:30)

**Subject line format:** `■ Stock Research — [TIME] Update — [N] opportunities found`

**Email structure — in this exact order:**

**BLOCK 1 — Market Pulse** (always at top, 3 lines max):
```
Dow Jones:  42,150  ▲ +0.8%  Rising
S&P 500:     5,234  ▲ +0.6%  Rising
Nasdaq:     18,920  ▼ -0.2%  Falling
```

**BLOCK 2 — Today's Story** (2-3 sentences, plain English):
> *"Technology stocks are gaining today following news about increased government spending on AI infrastructure. The energy sector is also moving higher as oil prices rose after supply cut announcements."*

**BLOCK 3 — LOW RISK OPPORTUNITIES** (green header):
```
■■■ NVIDIA Corporation (NVDA) — Technology ■■■
■ Why it appeared: AI infrastructure spending news boosted the technology sector
■ Trend: Has been rising steadily for 20 days across multiple timeframes
■ Price: $875.20 ▲ +2.3% today
■ Financial health: Keeps 55 cents from every dollar it earns (profit margin)
  Carries very little debt compared to what it owns (debt-to-equity: low)
■ Trading activity: Significantly more people buying and selling than usual
■ Confidence: STRONG (82/100)
■■ Note: Earnings announcement in 4 days — added uncertainty
```

**BLOCK 4 — MODERATE RISK OPPORTUNITIES** (amber header):
Same format as above PLUS one extra line explaining WHY the risk is moderate:
```
■■ Why moderate risk: This company carries more debt than most in its sector.
   It has also declined 14% from its highest price in the past 90 days.
```

**BLOCK 5 — Overflow notice** (if more than 7 companies total):
`+ 3 more companies found today. View full report: [link]`

### 23.2 Closing Email (16:10)

**Subject line format:** `■ Daily Summary — [DATE] — [N] total opportunities`

**Closing email structure — in this exact order:**

- **BLOCK 1 — Market Close Summary:** Three index lines with closing values. One plain English sentence per index.
- **BLOCK 2 — What Moved The Market Today:** 3-5 sentences summarising detected news events. Plain English. No event type codes.
- **BLOCK 3 — Today's Full Ranked List:** All companies from all three intraday reports, sorted lowest to moderate risk. Name, ticker, sector, closing price, day % change, confidence score, risk label.
- **BLOCK 4 — Things To Watch Tomorrow:** Upcoming earnings for companies in today's list. Scheduled economic events if detectable. Any sector showing accelerating rotation speed.

### 23.3 Plain English Term Rules

- Never use a raw score number without a label. `'47'` means nothing. `'Moderate (47/100)'` does.
- Never show a field name without translating it. Use `plain_english_terms.json`.
- Technical terms may appear in parentheses after plain English only.
- Percentage changes always show direction arrow: ▲ for up, ▼ for down.
- If data is missing, say `'not available'` — never show `None` or `null`.
- Earnings warnings always appear prominently — never buried at the bottom.
- Divergence warnings always shown in amber.

---

## §24 REPORT TEMPLATE SYSTEM — Jinja2 Templates

Report content is generated by filling pre-written sentence templates with real data. No AI generation. No free-text writing by the system. Every sentence in a report comes from a template.

```python
# reports/sentence_templates.py

COMPANY_INTRO = (
    "[COMPANY] appeared today because the [SECTOR] sector is seeing "
    "[DIRECTION] movement following news about [EVENT_PLAIN]."
)
TREND_SENTENCE = (
    "The stock has been [TREND_LABEL] for the past [TREND_DAYS] days "
    "and is currently [MOMENTUM_LABEL]."
)
FINANCIAL_HEALTH = (
    "Financial health: keeps [MARGIN_PCT] cents from every dollar it earns "
    "(profit margin), and carries [DEBT_LABEL] debt compared to what it owns."
)
MODERATE_RISK_REASON = (
    "Why moderate risk: [RISK_REASON_1]. [RISK_REASON_2_IF_ANY]."
)
UNUSUAL_VOLUME_NOTE = (
    "Notable: [UNUSUAL_LABEL] today — this means something significant "
    "may be drawing attention to this stock."
)
DRAWDOWN_NOTE = (
    "The stock is currently [DRAWDOWN_PCT]% below its highest price "
    "in the past 90 days."
)
EARNINGS_WARNING = (
    "■■ Earnings announcement in [DAYS] days — companies often move "
    "sharply around earnings. Factor this into your research."
)
DIVERGENCE_WARNING = (
    "■■ Signal conflict: strong financial health but the price has been "
    "declining recently. Investigate why before researching further."
)

EVENT_PLAIN = {
    'interest_rate_increase':    'central bank raising interest rates',
    'interest_rate_decrease':    'central bank cutting interest rates',
    'inflation_increase':        'rising inflation data',
    'geopolitical_conflict':     'geopolitical tensions and conflict news',
    'geopolitical_resolution':   'easing of international tensions',
    'oil_supply_disruption':     'disruptions to global oil supply',
    'oil_supply_increase':       'increased oil supply announcements',
    'recession_signal':          'economic slowdown signals',
    'strong_jobs_report':        'strong employment data',
    'weak_jobs_report':          'weak employment data',
    'ai_investment_surge':       'increased AI and technology investment',
    'semiconductor_shortage':    'semiconductor supply constraints',
    'supply_chain_disruption':   'global supply chain disruptions',
    'bank_failure_credit_crisis':'banking sector stress',
    'strong_earnings_season':    'strong corporate earnings results',
    'weak_earnings_season':      'disappointing corporate earnings',
    'tariff_increase':           'new or increased trade tariffs',
    'tariff_reduction':          'reduction of trade tariffs',
    'currency_usd_strengthening':'strengthening US dollar',
}

RISK_REASONS = {
    'de_too_high':         'carries more debt than most companies in its sector',
    'high_beta':           'its price tends to move more sharply than the overall market',
    'low_volume':          'fewer shares are traded daily — can be harder to buy or sell quickly',
    'earnings_proximity':  'has an earnings announcement coming soon — added short-term uncertainty',
    'drawdown_high':       'has declined significantly from its recent highest price',
    'margin_weakness':     'keeps a smaller portion of revenue as profit than peers',
    'eps_instability':     'its quarterly earnings have been inconsistent recently',
}
```

---

## §25 Alpha Vantage, Candidate Filter, and Failure Handling

### 25.1 Alpha Vantage — unchanged from V4

25 req/day hard limit. Internal budget: 20 calls. Cache 7 days per ticker. Rate limit arrives as HTTP 200 with `'Information'` or `'Note'` in JSON body — always inspect body before parsing. Save state after every AV call.

### 25.2 filters/candidate_filter.py — V5 thresholds

| Filter | Rule | Exception |
|---|---|---|
| Already reported | Skip entirely — fetch no data | None |
| Market cap | < $500M → exclude | None |
| Average volume | < 500,000 shares/day → exclude | None |
| Current price | < $5.00 → exclude | None |
| Operating cash flow | < 0 → exclude | None |
| Debt-to-equity | > 2.5 → exclude | Financials sector: skip D/E filter |
| D/E missing | Keep but flag in report as 'debt data not available' | None |

### 25.3 API Failure Handling — Complete Reference

| Failure | Required Action |
|---|---|
| yfinance None / empty DF | Mark data_unavailable in state. Skip. Continue. |
| yfinance timeout | Retry once (3s). Still failing: skip, add to failed_tickers. |
| Finnhub HTTP 429 | Wait 60s. Retry once. Still failing: skip news enrichment. |
| AV 'Information'/'Note' in body | Rate limit (HTTP 200). Set calls_today=25. Use cache. |
| AV 'Error Message' | Log WARNING. Use cached data. Continue. |
| AV daily limit >= 20 | Skip AV. Note in report: 'using cached financial data'. |
| RSS feed unreachable | Skip that feed. Continue with remaining. |
| All news sources fail | Log CRITICAL. Write empty report. No email. sys.exit(0). |
| Gmail SMTP fails | Log CRITICAL. Commit report to repo. Do not crash run. |
| State file corrupt | Create fresh state. Log WARNING. Continue. |
| validated.json missing | Log CRITICAL. sys.exit(1). Print setup instruction. |
| VIX unavailable | Use 'normal' regime. Log WARNING. Continue. |
| Index data unavailable | Show 'unavailable' in report pulse. Continue. |
| Volume data unavailable | volume_score = 0.5 (neutral). Continue. |
| Sector breadth MA unavailable | Use 0.5 score. Log WARNING. Continue. |
| Drawdown data unavailable | drawdown_score = 0.5. Log WARNING. Continue. |

---

## §26 GITHUB ACTIONS WORKFLOW

```yaml
name: Market Scan

on:
  schedule:
    # 10:30 ET  EST: 15:30 UTC | EDT: 14:30 UTC
    - cron: '30 15 * * 1-5'
    - cron: '30 14 * * 1-5'
    # 12:30 ET
    - cron: '30 17 * * 1-5'
    - cron: '30 16 * * 1-5'
    # 14:30 ET
    - cron: '30 19 * * 1-5'
    - cron: '30 18 * * 1-5'
    # 16:10 ET
    - cron: '10 21 * * 1-5'
    - cron: '10 20 * * 1-5'
  workflow_dispatch:

jobs:
  scan:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }

      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }

      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run market scan
        env:
          FINNHUB_API_KEY:       ${{ secrets.FINNHUB_API_KEY }}
          ALPHA_VANTAGE_API_KEY: ${{ secrets.ALPHA_VANTAGE_API_KEY }}
          GMAIL_EMAIL:           ${{ secrets.GMAIL_EMAIL }}
          GMAIL_APP_PASSWORD:    ${{ secrets.GMAIL_APP_PASSWORD }}
        run: python main.py

      - name: Commit outputs
        run: |
          git config user.name  'github-actions[bot]'
          git config user.email 'github-actions[bot]@users.noreply.github.com'
          git add reports/output/ state/ data/fundamentals_cache/ logs/ || true
          git diff --staged --quiet || \
            git commit -m 'Auto: market scan $(date -u +%Y-%m-%dT%H:%M:%SZ)'
          git push
```

---

## §27 SUCCESS CRITERIA — PROJECT COMPLETE WHEN ALL ARE TRUE

1. System runs automatically on schedule without any human intervention
2. Reports committed to repository on every run including empty runs
3. No company appears more than once per calendar day
4. Companies with risk_score > regime risk_cap never appear in reports
5. Alpha Vantage called at most 20 times per day (hard limit 25)
6. A failed API call does not crash the run — logs and continues
7. State file never corrupted by mid-run crash (atomic writes)
8. All log timestamps UTC. Market-time logic uses America/New_York
9. Financial sector companies not excluded by D/E > 2.5 filter
10. validate_tickers.py produces clean file with zero delisted or <$5 tickers
11. Validated ticker file staleness checked each run — warn if >30 days
12. SectorSignalAccumulator: min 2 headlines + score 6 before sector queues
13. Event recency decay applied before impact scoring
14. News impact scoring gate: sectors below 0.6 threshold excluded
15. Sector momentum computed for all 13 sectors every run
16. Only top 5 momentum sectors eligible for company analysis
17. Sector rotation speed computed and stored — accelerating sectors flagged
18. Sector leadership tracking updates rolling 10-day history file
19. Daily advance/decline breadth computed and applied as opp multiplier
20. Sector MA breadth (stocks above 50-day MA) computed every run
21. ETF 3-signal + multi-timeframe confirmation required for sector activation
22. VIX regime fetched once per run — both multipliers applied
23. volume_confirmation.py uses 30-day average, outputs ratio and plain label
24. risk_adjusted_momentum.py computes return/volatility over 3 months
25. multi_timeframe_momentum.py combines 1m/3m/6m with specified weights
26. sector_breadth_ma.py measures stocks above 50-day MA per sector
27. event_decay.py applies exponential decay (factor=10) to all event scores
28. sector_rotation_speed.py computes rank change vs 7 days ago
29. trend_stability.py measures average distance from MA50 over 50 days
30. drawdown_risk.py measures 90-day peak decline and feeds into risk_model
31. signal_agreement.py uses multiplicative formula across 4 signals
32. unusual_volume.py raises flag at 2x threshold, boosts ranking by +0.3
33. financial_parser.py is the ONLY file calling yf.Ticker() for financials
34. Z-score ranking applied. Max 3 per sector. Max 25 total. Unusual vol boost applied.
35. Composite confidence uses V5 formula: 35% risk + 35% opp + 20% agreement + 10% momentum
35b. Opportunity model uses three-bucket structure: Fundamentals 40%, Momentum 40%, Confirmation 20%
35c. No single bucket can dominate final score — cap enforced in code, not just comments
36. Intraday email shows Market Pulse (3 indices) at top of every email
37. Intraday email shows max 7 companies — overflow continues to browser link
38. Low Risk and Moderate Risk companies in separate labelled sections
39. Moderate Risk section explains WHY each company is moderate risk in plain English
40. All report text uses plain English — technical terms in parentheses only
41. All scores shown with labels — never raw numbers alone
42. Percentage changes show direction arrows (▲ / ▼)
43. Earnings warnings appear prominently — never buried
44. Closing report (16:10) includes: market summary, full ranked list, watch tomorrow
45. Email subject line follows specified format including opportunity count
46. AGENT_PROGRESS.md updated before AND after every file written

---

*END OF ROADMAP — VERSION 5 FINAL*
*27 sections · 46 success criteria · 10 new algorithmic modules · Plain English report system · Phone and watch optimised email delivery*
*~9.5/10 expected analytical quality · Beginner-readable output · $0 infrastructure*
