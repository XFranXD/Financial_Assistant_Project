"""
analyzers/expectations.py
Computes the Expectations vs Reality signal for a single ticker.
Uses Finnhub historical EPS data and Sub1-provided fundamentals.
Non-fatal — returns UNAVAILABLE on any error or missing data.
"""
import requests
import logging
from utils.logger import get_logger

log = get_logger('expectations')

def get_expectations_signal(
    ticker:        str,
    finnhub_token: str,
    pe_ratio:      float | None,
    eps_quarterly: list,
) -> dict:
    """
    Computes expectations signal from two components:
      Component 1 — Earnings surprise streak (Finnhub /stock/earnings)
      Component 2 — Bounded PEG ratio (pe_ratio / eps_growth_rate)

    Args:
        ticker:        stock ticker symbol
        finnhub_token: Finnhub API token string (may be empty string)
        pe_ratio:      trailing P/E from Sub1 financial_parser (may be None)
        eps_quarterly: list of up to 8 quarterly EPS floats, most recent first,
                       from Sub1 financial_parser (may be empty list)

    Returns:
        {
            'expectations_signal': 'BEATING' | 'INLINE' | 'MISSING' | 'UNAVAILABLE',
            'earnings_beat_rate':  float | None,   e.g. 0.75 = beat 3 of 4
            'peg_ratio':           float | None,
        }
    On any exception: returns UNAVAILABLE dict. Never raises.
    """
    _default = {
        'expectations_signal': 'UNAVAILABLE',
        'earnings_beat_rate':  None,
        'peg_ratio':           None,
    }

    try:
        # COMPONENT 1: Earnings surprise streak
        beat_score = 0
        beat_rate = None
        
        if finnhub_token == '' or finnhub_token is None:
            log.info(f'[EXP] {ticker}: no Finnhub token — skipping beat streak')
        else:
            try:
                url = f"https://finnhub.io/api/v1/stock/earnings?symbol={ticker}&token={finnhub_token}"
                resp = requests.get(url, timeout=10)
                if not resp.ok:
                    log.info(f'[EXP] {ticker}: Finnhub returned HTTP {resp.status_code}')
                else:
                    data = resp.json()
                    recent = data[:4]
                    valid_quarters = []
                    for item in recent:
                        if isinstance(item, dict) and item.get('actual') is not None and item.get('estimate') is not None:
                            valid_quarters.append(item)
                    if len(valid_quarters) >= 2:
                        beat_count = sum(1 for q in valid_quarters if q['actual'] > q['estimate'])
                        beat_rate = beat_count / len(valid_quarters)
                        if beat_count in (3, 4):
                            beat_score = 1
                        elif beat_count == 2:
                            beat_score = 0
                        else:
                            beat_score = -1
            except Exception as e:
                beat_score = 0
                beat_rate = None
                log.info(f'[EXP] {ticker}: Finnhub request failed — {e}')

        # COMPONENT 2: Bounded PEG ratio
        eps_growth_rate = None
        if len(eps_quarterly) >= 5:
            recent_eps = sum(eps_quarterly[0:4])
            older_eps = sum(eps_quarterly[1:5])
            if older_eps != 0:
                eps_growth_rate = ((recent_eps - older_eps) / abs(older_eps)) * 100

        peg_score = 0
        peg_ratio_val = None
        
        if eps_growth_rate is None:
            peg_score = 0
            peg_ratio_val = None
        elif eps_growth_rate <= 0:
            peg_score = -1
            peg_ratio_val = None
        elif pe_ratio is None:
            peg_score = 0
            peg_ratio_val = None
        else:
            capped_growth = min(eps_growth_rate, 50.0)
            peg_ratio_val = round(pe_ratio / capped_growth, 2)
            if peg_ratio_val <= 1.5:
                peg_score = 1
            elif peg_ratio_val <= 3.0:
                peg_score = 0
            elif peg_ratio_val > 3.0:
                peg_score = -1
                
        # COMBINED SIGNAL
        combined_score = beat_score + peg_score
        
        signal = 'INLINE'
        if combined_score == 2:
            signal = 'BEATING'
        elif combined_score in (1, 0):
            signal = 'INLINE'
        elif combined_score in (-1, -2):
            signal = 'MISSING'
            
        if beat_rate is None and peg_ratio_val is None:
            signal = 'UNAVAILABLE'
            
        return {
            'expectations_signal': signal,
            'earnings_beat_rate': round(beat_rate, 2) if beat_rate is not None else None,
            'peg_ratio': peg_ratio_val,
        }
    except Exception as e:
        log.warning(f'[EXP] {ticker}: unexpected error — {e}')
        return _default
