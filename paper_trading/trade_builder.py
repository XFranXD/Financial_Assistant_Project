from contracts.paper_trading_schema import (
    PT_TRADE_ID, PT_TICKER, PT_ENTRY_DATE, PT_ENTRY_RUN,
    PT_ENTRY_TIMESTAMP, PT_ENTRY_PRICE, PT_STOP_LOSS,
    PT_PRICE_TARGET, PT_RISK_REWARD, PT_POSITION_SIZE_PCT,
    PT_MARKET_VERDICT, PT_ENTRY_QUALITY, PT_EQ_VERDICT,
    PT_ROTATION_SIGNAL, PT_ALIGNMENT, PT_COMPOSITE_SCORE,
    PT_MARKET_REGIME, PT_INSIDER_SIGNAL, PT_EVENT_RISK,
    PT_EXPECTATIONS_SIGNAL, PT_STATUS_OPEN,
)
from paper_trading.state_manager import build_empty_trade
from utils.logger import get_logger
import pytz
from datetime import datetime

log = get_logger(__name__)

def build_trade(candidate: dict, slot: str, market_regime: str) -> dict:
    ticker = candidate.get('ticker')
    if not ticker:
        log.error("Cannot build trade without ticker")
        return {}
        
    try:
        base = build_empty_trade(ticker)
        
        now_utc = datetime.now(pytz.utc)
        now_et = datetime.now(pytz.timezone('America/New_York'))
        entry_date_str = now_et.strftime('%Y-%m-%d')
        run_tag = slot.replace(':', '').replace('-', '')
        
        base[PT_TRADE_ID] = f"{ticker}-{entry_date_str}-{run_tag}"
        base[PT_ENTRY_DATE] = entry_date_str
        base[PT_ENTRY_RUN] = slot
        base[PT_ENTRY_TIMESTAMP] = now_utc.isoformat()
        
        base[PT_ENTRY_PRICE] = candidate.get('entry_price')
        base[PT_STOP_LOSS] = candidate.get('stop_loss')
        base[PT_PRICE_TARGET] = candidate.get('price_target')
        base[PT_RISK_REWARD] = candidate.get('risk_reward_ratio')
        base[PT_POSITION_SIZE_PCT] = candidate.get('pl_position_weight')
        
        base[PT_MARKET_VERDICT] = candidate.get('market_verdict', '')
        base[PT_ENTRY_QUALITY] = candidate.get('entry_quality', '')
        base[PT_EQ_VERDICT] = candidate.get('eq_verdict_display', '')
        base[PT_ROTATION_SIGNAL] = candidate.get('rotation_signal_display', '')
        base[PT_ALIGNMENT] = candidate.get('alignment', '')
        base[PT_COMPOSITE_SCORE] = candidate.get('composite_confidence')
        base[PT_MARKET_REGIME] = market_regime
        base[PT_INSIDER_SIGNAL] = candidate.get('insider_signal', '')
        base[PT_EVENT_RISK] = candidate.get('event_risk', '')
        base[PT_EXPECTATIONS_SIGNAL] = candidate.get('expectations_signal', '')
        
        return base
    except Exception as e:
        log.error(f"Failed to build trade for {ticker}: {e}")
        return build_empty_trade(ticker)
