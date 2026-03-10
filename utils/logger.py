"""
utils/logger.py — Centralised logging. UTC timestamps. No print() anywhere.
Usage: from utils.logger import get_logger; log = get_logger('module_name')
"""

import logging
import os
import sys
from datetime import datetime

import pytz

LOGS_DIR = 'logs'
LOG_LEVEL = logging.INFO


def get_logger(module_name: str) -> logging.Logger:
    """
    Returns a configured Logger that writes to:
      - logs/run_<UTC_date>.log  (file, rotating daily by filename)
      - stdout                   (for GitHub Actions console visibility)

    All timestamps are UTC. Never use print() for operational output.
    """
    logger = logging.getLogger(module_name)

    # Avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    logger.setLevel(LOG_LEVEL)

    # UTC formatter
    formatter = _UTCFormatter(
        fmt='%(asctime)s UTC | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S',
    )

    # ── File handler ──────────────────────────────────────────────────
    os.makedirs(LOGS_DIR, exist_ok=True)
    today_utc = datetime.now(pytz.utc).strftime('%Y-%m-%d')
    log_file  = os.path.join(LOGS_DIR, f'run_{today_utc}.log')

    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(LOG_LEVEL)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # ── Stdout handler ─────────────────────────────────────────────────
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(LOG_LEVEL)
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    # Prevent propagation to root logger (avoids duplicate lines)
    logger.propagate = False

    return logger


class _UTCFormatter(logging.Formatter):
    """Forces log record timestamps to UTC regardless of system timezone."""

    converter = lambda *args: datetime.now(pytz.utc).timetuple()  # noqa: E731

    def formatTime(self, record, datefmt=None):  # noqa: N802
        dt = datetime.fromtimestamp(record.created, tz=pytz.utc)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat()
