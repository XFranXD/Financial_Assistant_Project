"""
utils/retry.py — Exponential backoff decorator for API calls.
All retries exhausted → returns None. Never raises.
HTTP 429 rate limit detected → doubles the wait time.
"""

import functools
import time
from typing import Any, Callable, TypeVar

from utils.logger import get_logger

log = get_logger('retry')

F = TypeVar('F', bound=Callable[..., Any])


def retry_on_failure(max_attempts: int = 3, delay: float = 2.0) -> Callable[[F], F]:
    """
    Decorator factory. Wraps a function with exponential backoff retries.

    - On any exception: waits `delay` seconds then doubles it.
    - On HTTP 429 (rate limit): doubles wait time immediately.
    - If all attempts exhausted: logs warning and returns None.

    Usage:
        @retry_on_failure(max_attempts=2, delay=2.0)
        def fetch_data(ticker): ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            wait = delay
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    exc_str  = str(exc)

                    # Detect rate limit responses embedded in exception message
                    is_rate_limit = (
                        '429' in exc_str
                        or 'rate limit' in exc_str.lower()
                        or 'too many requests' in exc_str.lower()
                    )

                    if is_rate_limit:
                        wait_this = wait * 2  # double wait for rate limit
                        log.warning(
                            f'{func.__name__} attempt {attempt}/{max_attempts} — '
                            f'rate limit detected, waiting {wait_this:.1f}s'
                        )
                        time.sleep(wait_this)
                    else:
                        log.warning(
                            f'{func.__name__} attempt {attempt}/{max_attempts} '
                            f'failed: {exc} — waiting {wait:.1f}s'
                        )
                        time.sleep(wait)

                    wait = wait * 2  # exponential backoff

            log.warning(
                f'{func.__name__} — all {max_attempts} attempts exhausted. '
                f'Last error: {last_exc}. Returning None.'
            )
            return None

        return wrapper  # type: ignore[return-value]

    return decorator
