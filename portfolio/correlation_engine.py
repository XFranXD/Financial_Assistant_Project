"""
portfolio/correlation_engine.py
Layer 1: Fetch price history, compute pairwise Pearson correlation matrix,
identify correlated clusters via union-find (no networkx dependency).
"""

import logging
import numpy as np
import pandas as pd
import yfinance as yf
from contracts.portfolio_schema import CORRELATION_THRESHOLD, LOOKBACK_DAYS

log = logging.getLogger(__name__)


def _union_find_clusters(
    tickers: list,
    corr_matrix: dict,
    conf_map: dict,
) -> tuple[list[list[str]], dict[str, int]]:
    """
    Build clusters via union-find.
    A and B join the same cluster if corr >= CORRELATION_THRESHOLD.
    Transitive closure: if A-B and B-C are correlated, A/B/C share one cluster.

    After formation:
    - Within each cluster: sort members by conf_map[t] descending
    - Across clusters: sort by the highest conf_map value in each cluster descending
    - This guarantees deterministic ordering across runs regardless of input order.

    Returns:
        clusters          — list[list[str]], deterministically ordered
        ticker_to_cluster — dict[str, int], index into clusters list
    """
    parent = {t: t for t in tickers}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i, ta in enumerate(tickers):
        for tb in tickers[i + 1:]:
            val = corr_matrix.get(ta, {}).get(tb)
            if val is not None and val >= CORRELATION_THRESHOLD:
                union(ta, tb)

    cluster_map: dict[str, list] = {}
    for t in tickers:
        root = find(t)
        cluster_map.setdefault(root, []).append(t)

    raw_clusters = list(cluster_map.values())

    # Sort members within each cluster by confidence descending
    for cluster in raw_clusters:
        cluster.sort(key=lambda t: conf_map.get(t, 0), reverse=True)

    # Sort clusters by their top member's confidence descending
    raw_clusters.sort(key=lambda cl: conf_map.get(cl[0], 0), reverse=True)

    ticker_to_cluster: dict[str, int] = {}
    for idx, group in enumerate(raw_clusters):
        for t in group:
            ticker_to_cluster[t] = idx

    return raw_clusters, ticker_to_cluster


def compute(candidates: list[dict], lookback: int = LOOKBACK_DAYS) -> dict:
    """
    Input:
        candidates: list[dict] — each must have 'ticker' key
        lookback:   int        — calendar days for yfinance period (default LOOKBACK_DAYS)

    Output (always returns all 7 keys even on failure):
        correlation_matrix  — dict[str, dict[str, float]]
        clusters            — list[list[str]]
        ticker_to_cluster   — dict[str, int]
        correlation_flags   — dict[str, list[str]]
        avg_correlation     — float | None
        unavailable         — list[str]
        returns_data        — dict[str, pd.Series]
    """
    tickers = [c.get('ticker', '') for c in candidates if c.get('ticker')]
    conf_map: dict[str, float] = {
        c.get('ticker', ''): float(c.get('composite_confidence', 0))
        for c in candidates if c.get('ticker')
    }

    _safe_return = {
        'correlation_matrix': {},
        'clusters':           [[t] for t in tickers],
        'ticker_to_cluster':  {t: i for i, t in enumerate(tickers)},
        'correlation_flags':  {t: [] for t in tickers},
        'avg_correlation':    None,
        'unavailable':        tickers[:],
        'returns_data':       {},
    }

    unavailable: list[str] = []
    returns_data: dict[str, pd.Series] = {}

    try:
        raw = yf.download(
            tickers,
            period='6mo',
            interval='1d',
            auto_adjust=True,
            progress=False,
            group_by='ticker',
        )
    except Exception as e:
        log.warning(f'[PL] yfinance batch download failed: {e}')
        return _safe_return

    for ticker in tickers:
        try:
            close = raw['Close'][ticker].dropna() if len(tickers) > 1 else raw['Close'].dropna()
            if len(close) < 20:
                log.info(f'[PL] {ticker}: insufficient rows ({len(close)}) — marking UNAVAILABLE')
                unavailable.append(ticker)
                continue
            log_returns = np.log(close / close.shift(1)).dropna()
            returns_data[ticker] = log_returns
        except Exception as e:
            log.info(f'[PL] {ticker}: returns extraction failed ({e}) — marking UNAVAILABLE')
            unavailable.append(ticker)

    usable = [t for t in tickers if t in returns_data]

    if len(usable) < 2:
        log.warning(f'[PL] Fewer than 2 usable tickers. Unavailable: {unavailable}')
        _safe_return['unavailable'] = list(set(unavailable + [t for t in tickers if t not in returns_data]))
        _safe_return['returns_data'] = returns_data
        return _safe_return

    df = pd.DataFrame({t: returns_data[t] for t in usable}).dropna(how='all')
    corr_df = df.corr(method='pearson')

    corr_matrix: dict[str, dict[str, float]] = {}
    for ta in usable:
        corr_matrix[ta] = {}
        for tb in usable:
            if ta != tb:
                try:
                    val = corr_df.loc[ta, tb]
                    if not np.isnan(val):
                        corr_matrix[ta][tb] = round(float(val), 4)
                except Exception:
                    pass

    correlation_flags: dict[str, list[str]] = {t: [] for t in tickers}
    for ta in usable:
        for tb in usable:
            if ta != tb:
                val = corr_matrix.get(ta, {}).get(tb)
                if val is not None and val >= CORRELATION_THRESHOLD:
                    correlation_flags[ta].append(tb)

    clusters, ticker_to_cluster = _union_find_clusters(usable, corr_matrix, conf_map)

    all_pairs = []
    for i, ta in enumerate(usable):
        for tb in usable[i + 1:]:
            val = corr_matrix.get(ta, {}).get(tb)
            if val is not None:
                all_pairs.append(val)
    avg_correlation = round(float(np.mean(all_pairs)), 4) if all_pairs else None

    all_unavailable = list(set(unavailable + [t for t in tickers if t not in returns_data]))
    for t in all_unavailable:
        if t not in ticker_to_cluster:
            idx = len(clusters)
            clusters.append([t])
            ticker_to_cluster[t] = idx

    log.info(
        f'[PL] Correlation complete. Usable: {len(usable)}/{len(tickers)} | '
        f'Clusters: {len(clusters)} | Avg corr: {avg_correlation}'
    )

    return {
        'correlation_matrix': corr_matrix,
        'clusters':           clusters,
        'ticker_to_cluster':  ticker_to_cluster,
        'correlation_flags':  correlation_flags,
        'avg_correlation':    avg_correlation,
        'unavailable':        all_unavailable,
        'returns_data':       returns_data,
    }
