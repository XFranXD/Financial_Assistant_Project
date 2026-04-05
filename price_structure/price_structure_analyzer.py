"""Main entry point for Subsystem 4. Orchestrates all sub-modules and returns a complete output dict."""

import sys
import yfinance as yf
from contracts.price_structure_schema import PRICE_STRUCTURE_KEYS, PRICE_STRUCTURE_DEFAULTS
from price_structure.trend_analyzer import analyze_trend
from price_structure.volatility_analyzer import analyze_volatility
from price_structure.level_detector import detect_levels
from price_structure.entry_classifier import classify_entry
from price_structure.scorer import compute_score

def analyze(ticker: str) -> dict:
    defaults = PRICE_STRUCTURE_DEFAULTS.copy()
    defaults["ticker"] = ticker
    
    try:
        df = yf.Ticker(ticker).history(period="6mo", interval="1d")
        df = df.dropna(subset=["Close"])
        
        if len(df) < 63:
            defaults["ps_data_confidence"] = "UNAVAILABLE"
            return defaults
            
        trend_result = analyze_trend(df)
        volatility_result = analyze_volatility(df)
        levels_result = detect_levels(df, volatility_result["consolidation_confirmed"])
        entry_result = classify_entry(df, trend_result, levels_result, volatility_result)
        score = compute_score(trend_result, levels_result, entry_result)
        
        conf = "HIGH" if levels_result.get("level_confidence_tier", 3) == 1 else "LOW"
        
        result = {}
        for k in PRICE_STRUCTURE_KEYS:
            if k == "ticker":
                result[k] = ticker
            elif k == "ps_data_confidence":
                result[k] = conf
            elif k == "price_action_score":
                result[k] = score
            elif k == "ps_reasoning":
                pass # Set below
            elif k in trend_result:
                result[k] = trend_result[k]
            elif k in volatility_result:
                result[k] = volatility_result[k]
            elif k in levels_result:
                result[k] = levels_result[k]
            elif k in entry_result:
                result[k] = entry_result[k]
            else:
                result[k] = defaults[k]
                
        entry_quality = result["entry_quality"]
        key_level = result["key_level_position"]
        trend = result["trend_structure"]
        strength = result["trend_strength"]
        vol_state = result["volatility_state"]
        extension = result["move_extension_pct"]
        support_dist = result["distance_to_support_pct"]
        base_days = result["base_duration_days"]
        vol_contract = result["volume_contraction"]

        if entry_quality == "EXTENDED":
            reasoning = f"Move extended {extension:.0f}% from 6-month low near resistance — high timing risk."
        elif entry_quality == "GOOD" and key_level == "BREAKOUT":
            conf_str = "confirmed" if vol_contract else "not detected"
            str_str = "strong" if vol_contract else "moderate"
            reasoning = f"Breakout on {base_days}-day base with volume contraction {conf_str} — {str_str} structural setup."
        elif entry_quality == "GOOD" and key_level == "NEAR_SUPPORT":
            vol_str = "compressing" if vol_state == "COMPRESSING" else "normal"
            reasoning = f"Uptrend with confirmed support reaction and {vol_str} volatility — favorable entry structure."
        elif entry_quality == "GOOD" and key_level == "MID_RANGE":
            reasoning = f"Strong trend continuation — extension {extension:.0f}% with controlled volatility and trend strength {strength}."
        elif entry_quality == "EARLY":
            reasoning = "Sideways with volatility compressing near range highs — potential setup forming, no entry yet."
        elif entry_quality == "WEAK" and trend == "DOWN":
            reasoning = "Downtrend with weak structure — avoid."
        elif entry_quality == "WEAK" and vol_state == "EXPANDING":
            reasoning = "Expanding volatility with no confirmed structure — unstable, avoid."
        elif entry_quality == "WEAK" and key_level == "NEAR_RESISTANCE" and extension > 35:
            reasoning = f"Late in move with price near resistance and {extension:.0f}% extension — poor risk/reward."
        elif entry_quality == "WEAK" and trend == "UP" and support_dist < 2.0:
            reasoning = "Uptrend present but no support reaction confirmed — wait for pullback and reaction."
        elif entry_quality == "WEAK" and trend == "SIDEWAYS":
            reasoning = "Sideways structure without compression or clear level — no actionable setup."
        else:
            reasoning = "Structure present but no high-confidence entry signal detected."
            
        result["ps_reasoning"] = reasoning
        
        return result
        
    except Exception as e:
        print(f"Error in Subsystem 4 for {ticker}: {str(e)}", file=sys.stderr)
        defaults["ps_data_confidence"] = "UNAVAILABLE"
        return defaults
