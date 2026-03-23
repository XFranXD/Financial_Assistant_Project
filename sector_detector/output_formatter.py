"""
output_formatter.py — System 3 Sector Rotation Detector
Formats the raw rotation engine result into the final output dict.
"""


def format_output(
    sector_name: str,
    sector_etf: str,
    engine_result: dict,
    tf_data: dict,
) -> dict:
    """
    Returns the final output dict with exactly the fields specified.

    Parameters
    ----------
    sector_name : str
        Lowercase sector name, e.g. "technology".
    sector_etf : str
        ETF ticker, e.g. "XLK".
    engine_result : dict
        Result dict from rotation_engine (may be a SKIP result).
    tf_data : dict
        Timeframe data from data_fetcher (used to build timeframes_used).
    """

    if engine_result.get("rotation_status") == "SKIP":
        return {
            "sector_name": sector_name,
            "sector_etf": sector_etf,
            "rotation_score": None,
            "rotation_status": "SKIP",
            "rotation_signal": "UNKNOWN",
            "momentum_score": None,
            "relative_strength_score": None,
            "volume_score": None,
            "data_confidence": "SKIP",
            "timeframes_used": [],
            "reasoning": engine_result.get("reasoning", "Data unavailable."),
        }

    rotation_status = engine_result.get("rotation_status")
    if rotation_status == "FAVORABLE":
        rotation_signal = "SUPPORT"
    elif rotation_status == "UNFAVORABLE":
        rotation_signal = "WEAKEN"
    elif rotation_status == "NEUTRAL":
        rotation_signal = "WAIT"
    elif rotation_status == "SKIP":
        rotation_signal = "UNKNOWN"
    else:
        rotation_signal = "UNKNOWN"

    timeframes_used = [tf for tf in ["1M", "3M", "6M"] if tf_data[tf]["available"]]

    return {
        "sector_name": sector_name,
        "sector_etf": sector_etf,
        "rotation_score": round(float(engine_result["rotation_score"]), 1),
        "rotation_status": engine_result.get("rotation_status"),
        "rotation_signal": rotation_signal,
        "momentum_score": round(float(engine_result["momentum_score"]), 1),
        "relative_strength_score": round(float(engine_result["relative_strength_score"]), 1),
        "volume_score": round(float(engine_result["volume_score"]), 1),
        "data_confidence": engine_result["data_confidence"],
        "timeframes_used": timeframes_used,
        "reasoning": engine_result["reasoning"],
    }
