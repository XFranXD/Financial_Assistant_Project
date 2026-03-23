"""
main.py — System 3 Sector Rotation Detector
Public entry point: get_rotation_result(ticker, sector) -> dict
"""

from sector_detector.data_fetcher import fetch_etf_data
from sector_detector.rotation_engine import SECTOR_ETF_MAP, compute_rotation
from sector_detector.output_formatter import format_output


def get_rotation_result(ticker: str, sector: str) -> dict:
    """
    Accepts a stock ticker (used for context only, not for data fetch)
    and a sector name; returns the rotation result dict.
    """
    sector = sector.lower().strip()

    # Look up sector in SECTOR_ETF_MAP
    if sector not in SECTOR_ETF_MAP:
        return {
            "sector_name": sector,
            "sector_etf": None,
            "rotation_score": None,
            "rotation_status": "SKIP",
            "momentum_score": None,
            "relative_strength_score": None,
            "volume_score": None,
            "data_confidence": "SKIP",
            "timeframes_used": [],
            "reasoning": "Sector not recognized.",
        }

    etf_ticker = SECTOR_ETF_MAP[sector]

    # Fetch data
    fetched_data = fetch_etf_data(etf_ticker)

    # Run rotation engine
    engine_result = compute_rotation(fetched_data)

    # Format and return output
    return format_output(sector, etf_ticker, engine_result, fetched_data["timeframes"])
