"""
sector_detector/__init__.py
Entry point for System 3 (Sector Rotation Detector).
All System 3 source files live inside this package.
System 1 calls run_rotation_analyzer(candidates) from here.
"""

from sector_detector.main import get_rotation_result


def run_rotation_analyzer(candidates: list[dict]) -> list[dict]:
    """
    Accepts a list of candidate dicts with 'ticker' and 'sector' keys.
    Returns a list of rotation result dicts, one per candidate.
    Non-fatal — returns empty list on any failure.
    """
    try:
        results = []
        for c in candidates:
            ticker = c.get('ticker', '')
            sector = c.get('sector', '')
            if not ticker or not sector:
                continue
            try:
                result = get_rotation_result(ticker, sector)
                result['ticker'] = ticker
                results.append(result)
            except Exception as e:
                import traceback
                import logging
                logging.getLogger('main').warning(f'[ROT] {ticker} exception: {traceback.format_exc()}')
                results.append({
                    'ticker':          ticker,
                    'rotation_status': 'SKIP',
                    'rotation_signal': 'UNKNOWN',
                    'rotation_score':  None,
                    'error':           str(e)
                })
        return results
    except Exception:
        import traceback
        import logging
        logging.getLogger('main').warning(f'[ROT] outer exception: {traceback.format_exc()}')
        return []
