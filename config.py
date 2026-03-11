"""
config.py — Constants and API key loading from environment variables.
All secret values are loaded from env vars only. Never hardcode keys.
"""

import os

# ── API Keys (loaded from GitHub Actions secrets / local env) ──────────────
FINNHUB_API_KEY       = os.environ.get('FINNHUB_API_KEY', '')
ALPHA_VANTAGE_API_KEY = os.environ.get('ALPHA_VANTAGE_API_KEY', '')
GMAIL_EMAIL           = os.environ.get('GMAIL_EMAIL', '')
GMAIL_APP_PASSWORD    = os.environ.get('GMAIL_APP_PASSWORD', '')

# ── Run Slot Schedule (Eastern Time) ──────────────────────────────────────
RUN_SLOTS = ['10:30', '12:30', '14:30', '16:10']
CLOSING_SLOT = '16:10'
TIMEZONE = 'America/New_York'

# ── File Paths ─────────────────────────────────────────────────────────────
STATE_FILE                   = 'state/daily_state.json'
VALIDATED_TICKERS_FILE       = 'data/sector_tickers_validated.json'
SECTOR_TICKERS_FILE          = 'data/sector_tickers.json'
SECTOR_ETFS_FILE             = 'data/sector_etfs.json'
SECTOR_BREADTH_STOCKS_FILE   = 'data/sector_breadth_stocks.json'
EVENT_KEYWORDS_FILE          = 'data/event_keywords.json'
EVENT_TO_SECTOR_FILE         = 'data/event_to_sector.json'
SECTOR_MOMENTUM_HISTORY_FILE = 'data/sector_momentum_history.json'
PLAIN_ENGLISH_TERMS_FILE     = 'data/plain_english_terms.json'
FUNDAMENTALS_CACHE_DIR       = 'data/fundamentals_cache'
LOGS_DIR                     = 'logs'
REPORTS_OUTPUT_DIR           = 'reports/output'

# ── Validation Thresholds ─────────────────────────────────────────────────
MIN_MARKET_CAP_M        = 500        # $500 million
MIN_AVG_VOLUME          = 500_000    # shares per day
MIN_PRICE               = 5.00       # USD
VALID_EXCHANGES         = {'NMS', 'NYQ', 'NGM', 'NCM', 'ASE'}
VALIDATED_TICKER_MAX_AGE_DAYS = 30

# ── Alpha Vantage Rate Limits ─────────────────────────────────────────────
AV_DAILY_BUDGET         = 20         # internal hard limit (AV max = 25)
AV_CACHE_TTL_DAYS       = 7

# ── Scoring Thresholds & Caps ─────────────────────────────────────────────
NEWS_IMPACT_THRESHOLD        = 0.6   # gate: sectors below this are dropped
SECTOR_ACCUMULATOR_MIN_HEADLINES = 2
SECTOR_ACCUMULATOR_MIN_SCORE     = 4
TOP_SECTORS_LIMIT            = 5     # only top 5 momentum sectors proceed
MAX_COMPANIES_PER_SECTOR     = 3
MAX_TOTAL_COMPANIES          = 25
UNUSUAL_VOLUME_RANKING_BOOST = 0.3
COMPOSITE_CONFIDENCE_MIN     = 35    # below this → excluded from report

# ── Email Report Limits ────────────────────────────────────────────────────
EMAIL_MAX_COMPANIES     = 7          # overflow goes to browser link

# ── Report Domain (GitHub Pages) ──────────────────────────────────────────
# Set GITHUB_PAGES_URL in env or update this value after first deploy
GITHUB_PAGES_URL = os.environ.get('GITHUB_PAGES_URL', 'https://your-username.github.io/your-repo')

# ── Sector Equivalence Mapping (yfinance sector → internal sector name) ────
SECTOR_EQUIVALENCE = {
    'Technology':             'technology',
    'Healthcare':             'healthcare',
    'Financial Services':     'financials',
    'Consumer Cyclical':      'consumer_discretionary',
    'Consumer Defensive':     'consumer_staples',
    'Industrials':            'industrials',
    'Basic Materials':        'materials',
    'Energy':                 'energy',
    'Utilities':              'utilities',
    'Real Estate':            'real_estate',
    'Communication Services': 'communication_services',
    'Semiconductors':         'semiconductors',
    'Defense':                'defense',
}

# Sectors that have a $5 price floor and cap tier tracking
ALL_SECTORS = list(SECTOR_EQUIVALENCE.values())

# ── Risk Model Weights (must sum to 1.0) ─────────────────────────────────
RISK_WEIGHTS = {
    'debt':         0.22,
    'volatility':   0.18,
    'liquidity':    0.18,
    'eps':          0.14,
    'margin':       0.09,
    'mcap':         0.09,
    'drawdown':     0.10,
}

# ── Opportunity Model Bucket Weights ─────────────────────────────────────
OPP_BUCKET_WEIGHTS = {
    'fundamentals': 0.40,
    'momentum':     0.40,
    'confirmation': 0.20,
}

# ── Composite Confidence Weights ─────────────────────────────────────────
CONFIDENCE_WEIGHTS = {
    'risk':         0.35,
    'opportunity':  0.35,
    'agreement':    0.20,
    'sector':       0.10,
}

# ── VIX Regime Definitions ────────────────────────────────────────────────
VIX_REGIMES = {
    'low_vol':   {'vix_max': 15,  'risk_mult': 0.85, 'opp_mult': 1.15, 'label': 'Calm market'},
    'normal':    {'vix_max': 25,  'risk_mult': 1.00, 'opp_mult': 1.00, 'label': 'Normal market'},
    'elevated':  {'vix_max': 35,  'risk_mult': 1.20, 'opp_mult': 0.85, 'label': 'Elevated uncertainty'},
    'crisis':    {'vix_max': 999, 'risk_mult': 1.50, 'opp_mult': 0.65, 'label': 'Market stress'},
}

# Risk cap per regime: companies above this risk_score are excluded
RISK_CAPS = {
    'low_vol':  80,
    'normal':   70,
    'elevated': 55,
    'crisis':   40,
}

# ── News Sources ──────────────────────────────────────────────────────────
RSS_FEEDS = {
    'reuters': 'https://feeds.reuters.com/reuters/businessNews',
    'ft':      'https://www.ft.com/rss/home/uk',
}
NEWS_FRESHNESS_HOURS = 16
NEWS_DEDUP_THRESHOLD = 0.92   # difflib SequenceMatcher ratio

# ── Event Decay ───────────────────────────────────────────────────────────
EVENT_DECAY_FACTOR = 10       # half-life controls — do not change

# ── Sector Rotation History ───────────────────────────────────────────────
ROTATION_HISTORY_DAYS = 10    # rolling window for sector_momentum_history.json
ROTATION_SPEED_LOOKBACK = 7   # compare today vs 7 days ago
