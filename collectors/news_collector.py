"""
collectors/news_collector.py — Fetches news from Reuters RSS, FT RSS, Finnhub.
Three-stage pre-filter → deduplication → SectorSignalAccumulator gate.

Gate rule: sector must have min 2 headlines AND combined score >= 6 to queue.
If ALL three sources fail → empty report + sys.exit(0).
"""

import difflib
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import feedparser
import pytz
import requests

from config import (
    FINNHUB_API_KEY,
    EVENT_KEYWORDS_FILE,
    EVENT_TO_SECTOR_FILE,
    NEWS_FRESHNESS_HOURS,
    NEWS_DEDUP_THRESHOLD,
    SECTOR_ACCUMULATOR_MIN_HEADLINES,
    SECTOR_ACCUMULATOR_MIN_SCORE,
    RSS_FEEDS,
)
from utils.logger import get_logger

log = get_logger('news_collector')

APPROVED_SOURCES = {'reuters', 'ft', 'finnhub'}
FINNHUB_GENERAL_URL = 'https://finnhub.io/api/v1/news?category=general'


# ── Load keyword and sector mappings ───────────────────────────────────────

def _load_json(path: str) -> dict:
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log.error(f'Cannot load {path}: {e}')
        return {}


# ── News Article normalisation ─────────────────────────────────────────────

def _norm_article(title: str, body: str, source: str, pub_dt: Optional[datetime]) -> dict:
    return {
        'title':      title.strip(),
        'body':       (body or '').strip()[:500],
        'source':     source,
        'published':  pub_dt,
        'text':       f'{title} {body}'.lower(),
    }


def _parse_rss_date(entry) -> Optional[datetime]:
    """Try multiple date fields from feedparser entry."""
    for attr in ('published_parsed', 'updated_parsed', 'created_parsed'):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


# ── Three-stage pre-filter ─────────────────────────────────────────────────

def _passes_filter(article: dict, now_utc: datetime) -> bool:
    """Stage 1: source approval. Stage 2: date exists. Stage 3: freshness."""
    if article['source'] not in APPROVED_SOURCES:
        return False
    if article['published'] is None:
        return False
    age_h = (now_utc - article['published'].replace(tzinfo=timezone.utc)).total_seconds() / 3600
    if age_h > NEWS_FRESHNESS_HOURS:
        return False
    return True


# ── Deduplication via SequenceMatcher ─────────────────────────────────────

def _deduplicate(articles: list[dict], threshold: float = NEWS_DEDUP_THRESHOLD) -> list[dict]:
    unique = []
    for art in articles:
        title = art['title']
        if all(
            difflib.SequenceMatcher(None, title, u['title']).ratio() < threshold
            for u in unique
        ):
            unique.append(art)
    log.info(f'Dedup: {len(articles)} → {len(unique)} articles')
    return unique


# ── Source fetchers ────────────────────────────────────────────────────────

def _fetch_rss(feed_url: str, source_name: str) -> list[dict]:
    articles = []
    try:
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries:
            title = getattr(entry, 'title', '') or ''
            body  = getattr(entry, 'summary', '') or ''
            pub   = _parse_rss_date(entry)
            if title:
                articles.append(_norm_article(title, body, source_name, pub))
        log.info(f'{source_name} RSS: fetched {len(articles)} articles')
    except Exception as e:
        log.warning(f'{source_name} RSS fetch failed: {e}')
    return articles


def _fetch_finnhub() -> list[dict]:
    articles = []
    if not FINNHUB_API_KEY:
        log.warning('FINNHUB_API_KEY not set — skipping Finnhub')
        return articles
    try:
        resp = requests.get(
            FINNHUB_GENERAL_URL,
            params={'token': FINNHUB_API_KEY},
            timeout=10,
        )
        if resp.status_code == 429:
            log.warning('Finnhub 429 — waiting 60s then retrying once')
            time.sleep(60)
            resp = requests.get(
                FINNHUB_GENERAL_URL,
                params={'token': FINNHUB_API_KEY},
                timeout=10,
            )
        if resp.status_code != 200:
            log.warning(f'Finnhub returned HTTP {resp.status_code}')
            return articles

        items = resp.json()
        if not isinstance(items, list):
            log.warning('Finnhub response is not a list')
            return articles

        for item in items:
            title   = item.get('headline', '') or ''
            body    = item.get('summary', '') or ''
            ts      = item.get('datetime')
            pub_dt  = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
            if title:
                articles.append(_norm_article(title, body, 'finnhub', pub_dt))

        log.info(f'Finnhub: fetched {len(articles)} articles')
    except Exception as e:
        log.warning(f'Finnhub fetch failed: {e}')
    return articles


# ── SectorSignalAccumulator ────────────────────────────────────────────────

class SectorSignalAccumulator:
    """
    Accumulates keyword scores per sector across all headlines.
    Sector is queued only when:
      - headline_count >= SECTOR_ACCUMULATOR_MIN_HEADLINES (2), AND
      - combined_score  >= SECTOR_ACCUMULATOR_MIN_SCORE    (6)
    """

    def __init__(self, keywords: dict, event_to_sector: dict):
        self._keywords        = keywords
        self._event_to_sector = event_to_sector
        self._sector_scores:  dict[str, float] = {}
        self._sector_counts:  dict[str, int]   = {}
        self._sector_events:  dict[str, list]  = {}

    def process(self, article: dict) -> None:
        text  = article['text']
        score = 0.0
        matched_events: list[str] = []

        # Flat keyword scoring across all tiers
        for tier, tier_data in self._keywords.items():
            weight = tier_data.get('weight', 1)
            for term in tier_data.get('terms', []):
                if term.lower() in text:
                    score += weight

        if score == 0:
            return

        # Map to sectors via event_to_sector
        for event_type, sector_data in self._event_to_sector.items():
            event_terms = event_type.replace('_', ' ')
            if event_terms in text:
                matched_events.append(event_type)
                for sector, cfg in sector_data.get('sectors', {}).items():
                    confidence = cfg.get('confidence', 0.5)
                    weighted   = score * confidence
                    self._sector_scores[sector] = (
                        self._sector_scores.get(sector, 0.0) + weighted
                    )
                    self._sector_counts[sector] = (
                        self._sector_counts.get(sector, 0) + 1
                    )
                    if sector not in self._sector_events:
                        self._sector_events[sector] = []
                    self._sector_events[sector].append({
                        'event':     event_type,
                        'score':     weighted,
                        'days_old':  0,  # event_decay.py will update based on timestamp
                        'published': article.get('published'),
                    })

    def confirmed(self) -> dict:
        """
        Returns dict of confirmed sectors with their accumulated data.
        {sector: {'score': float, 'count': int, 'events': list}}
        """
        result = {}
        for sector, score in self._sector_scores.items():
            count = self._sector_counts.get(sector, 0)
            if count >= SECTOR_ACCUMULATOR_MIN_HEADLINES and score >= SECTOR_ACCUMULATOR_MIN_SCORE:
                result[sector] = {
                    'score':  round(score, 2),
                    'count':  count,
                    'events': self._sector_events.get(sector, []),
                }
                log.info(f'Sector confirmed: {sector} score={score:.1f} headlines={count}')
            else:
                log.info(
                    f'Sector gated: {sector} score={score:.1f} '
                    f'headlines={count} (need score>={SECTOR_ACCUMULATOR_MIN_SCORE}, '
                    f'headlines>={SECTOR_ACCUMULATOR_MIN_HEADLINES})'
                )
        return result


# ── Main entry point ───────────────────────────────────────────────────────

def collect_news() -> tuple[list[dict], dict]:
    """
    Fetches, filters, deduplicates news. Runs SectorSignalAccumulator.
    Returns (articles, confirmed_sectors).
    If all sources fail → sys.exit(0) after logging CRITICAL.
    """
    now_utc   = datetime.now(pytz.utc)
    keywords  = _load_json(EVENT_KEYWORDS_FILE)
    e2s       = _load_json(EVENT_TO_SECTOR_FILE)
    all_arts: list[dict] = []
    source_ok = 0

    # Fetch from each source independently
    for source_name, feed_url in RSS_FEEDS.items():
        arts = _fetch_rss(feed_url, source_name)
        if arts:
            source_ok += 1
        all_arts.extend(arts)

    fh_arts = _fetch_finnhub()
    if fh_arts:
        source_ok += 1
    all_arts.extend(fh_arts)

    if source_ok == 0:
        log.critical('All news sources failed — writing empty report and exiting')
        sys.exit(0)

    # Three-stage pre-filter
    filtered = [a for a in all_arts if _passes_filter(a, now_utc)]
    log.info(f'Filter: {len(all_arts)} raw → {len(filtered)} passed')

    # Deduplication
    unique = _deduplicate(filtered)

    # Accumulate keyword scores per sector
    acc = SectorSignalAccumulator(keywords, e2s)
    for art in unique:
        acc.process(art)

    confirmed = acc.confirmed()
    log.info(f'Confirmed sectors: {list(confirmed.keys())}')

    return unique, confirmed
