"""Computes price_action_score as a display-only summary metric. Not used for any decision logic."""

def compute_score(trend: dict, levels: dict, entry: dict) -> int:
    entry_quality_map = {"GOOD": 90, "EARLY": 65, "EXTENDED": 30, "WEAK": 15}
    level_position_map = {
        "NEAR_SUPPORT": 90,
        "MID_RANGE": 60,
        "BREAKOUT": 80,
        "NEAR_RESISTANCE": 25
    }

    score = (
        trend.get("trend_strength", 0) * 0.40 +
        entry_quality_map.get(entry.get("entry_quality", "WEAK"), 15) * 0.40 +
        level_position_map.get(levels.get("key_level_position", "MID_RANGE"), 60) * 0.20
    )
    return max(0, min(100, round(score)))
