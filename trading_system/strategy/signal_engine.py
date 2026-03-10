from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from trading_system.core.event_bus import Event, EventBus, EventType
from trading_system.execution.order_executor import OrderExecutor
from trading_system.features.fair_value_gap import FVG
from trading_system.features.liquidity_model import LiquidityResult, LiquiditySweep
from trading_system.features.market_structure import (
    StructureBreak,
    StructureEvent,
    StructureResult,
    Trend,
)
from trading_system.features.order_block_detector import OrderBlock
from trading_system.features.volatility_model import VolatilityResult
from trading_system.risk.risk_manager import RiskManager
from trading_system.strategy.multi_timeframe_strategy import MTFBias, MultiTimeframeStrategy

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    symbol: str
    direction: str  # "BUY" or "SELL"
    entry: float
    stop_loss: float
    take_profit: float
    confidence: float
    reasons: List[str] = field(default_factory=list)


class SignalEngine:
    """Evaluate institutional confluence and generate trade signals.

    A trade requires alignment of:
      - Higher timeframe trend
      - Liquidity sweep
      - Order block
      - Fair value gap
      - Structure shift (BOS/CHOCH)
    """

    def __init__(
        self,
        event_bus: EventBus,
        mtf_strategy: MultiTimeframeStrategy,
        risk_manager: RiskManager,
        order_executor: OrderExecutor,
        min_confidence: float = 0.6,
    ) -> None:
        self._event_bus = event_bus
        self._mtf = mtf_strategy
        self._risk_manager = risk_manager
        self._executor = order_executor
        self._min_confidence = min_confidence

    def evaluate(
        self,
        symbol: str,
        candles_by_tf: Dict[str, pd.DataFrame],
        features: Dict[str, Dict[str, Any]],
    ) -> Optional[Signal]:
        bias = self._mtf.compute_bias(candles_by_tf, features)
        if not bias.aligned:
            return None

        exec_tf = "M5"
        if exec_tf not in features:
            return None

        feat = features[exec_tf]
        df = candles_by_tf[exec_tf]
        close = float(df["close"].iloc[-1])

        vol: VolatilityResult = feat.get("volatility")
        if vol and not vol.tradeable:
            logger.debug("Volatility too low for %s – skipping", symbol)
            return None

        signal = self._check_long(symbol, close, bias, feat, vol)
        if signal is None:
            signal = self._check_short(symbol, close, bias, feat, vol)

        if signal is not None:
            self._event_bus.publish(Event(
                event_type=EventType.SIGNAL,
                payload={
                    "symbol": signal.symbol,
                    "direction": signal.direction,
                    "entry": signal.entry,
                    "sl": signal.stop_loss,
                    "tp": signal.take_profit,
                    "confidence": signal.confidence,
                    "reasons": signal.reasons,
                },
            ))
            if self._risk_manager.allow_trade(symbol, signal.direction, signal.stop_loss):
                self._executor.execute_signal(signal)

        return signal

    def _check_long(
        self,
        symbol: str,
        close: float,
        bias: MTFBias,
        feat: Dict[str, Any],
        vol: Optional[VolatilityResult],
    ) -> Optional[Signal]:
        if bias.macro_trend != Trend.BULLISH:
            return None

        reasons: List[str] = ["HTF bullish"]
        confidence = 0.2

        liq: LiquidityResult = feat.get("liquidity")
        if liq:
            below_sweeps = [s for s in liq.sweeps if s.close_back_inside and s.sweep_price < close]
            if below_sweeps:
                reasons.append("Liquidity sweep below support")
                confidence += 0.2

        obs: List[OrderBlock] = feat.get("order_blocks", [])
        bullish_ob = self._find_active_ob(obs, close, "bullish")
        if bullish_ob:
            reasons.append("Bullish order block")
            confidence += 0.2

        fvgs: List[FVG] = feat.get("fvg", [])
        bullish_fvg = self._price_in_fvg(fvgs, close, "bullish")
        if bullish_fvg:
            reasons.append("Price inside bullish FVG")
            confidence += 0.2

        ms: StructureResult = feat.get("market_structure")
        if ms:
            bullish_shift = any(
                e.direction == Trend.BULLISH
                for e in ms.events[-3:]
                if ms.events
            )
            if bullish_shift:
                reasons.append("Bullish structure shift")
                confidence += 0.2

        if confidence < self._min_confidence:
            return None

        atr = vol.atr if vol else abs(close * 0.002)
        sl = close - atr * 1.5
        tp = close + atr * 3.0

        return Signal(
            symbol=symbol,
            direction="BUY",
            entry=close,
            stop_loss=round(sl, 6),
            take_profit=round(tp, 6),
            confidence=min(confidence, 1.0),
            reasons=reasons,
        )

    def _check_short(
        self,
        symbol: str,
        close: float,
        bias: MTFBias,
        feat: Dict[str, Any],
        vol: Optional[VolatilityResult],
    ) -> Optional[Signal]:
        if bias.macro_trend != Trend.BEARISH:
            return None

        reasons: List[str] = ["HTF bearish"]
        confidence = 0.2

        liq: LiquidityResult = feat.get("liquidity")
        if liq:
            above_sweeps = [s for s in liq.sweeps if s.close_back_inside and s.sweep_price > close]
            if above_sweeps:
                reasons.append("Liquidity sweep above resistance")
                confidence += 0.2

        obs: List[OrderBlock] = feat.get("order_blocks", [])
        bearish_ob = self._find_active_ob(obs, close, "bearish")
        if bearish_ob:
            reasons.append("Bearish order block")
            confidence += 0.2

        fvgs: List[FVG] = feat.get("fvg", [])
        bearish_fvg = self._price_in_fvg(fvgs, close, "bearish")
        if bearish_fvg:
            reasons.append("Price inside bearish FVG")
            confidence += 0.2

        ms: StructureResult = feat.get("market_structure")
        if ms:
            bearish_shift = any(
                e.direction == Trend.BEARISH
                for e in ms.events[-3:]
                if ms.events
            )
            if bearish_shift:
                reasons.append("Bearish structure shift")
                confidence += 0.2

        if confidence < self._min_confidence:
            return None

        atr = vol.atr if vol else abs(close * 0.002)
        sl = close + atr * 1.5
        tp = close - atr * 3.0

        return Signal(
            symbol=symbol,
            direction="SELL",
            entry=close,
            stop_loss=round(sl, 6),
            take_profit=round(tp, 6),
            confidence=min(confidence, 1.0),
            reasons=reasons,
        )

    @staticmethod
    def _find_active_ob(
        order_blocks: List[OrderBlock], price: float, direction: str
    ) -> Optional[OrderBlock]:
        for ob in reversed(order_blocks):
            if ob.direction != direction or ob.mitigated:
                continue
            if ob.low <= price <= ob.high:
                return ob
        return None

    @staticmethod
    def _price_in_fvg(fvgs: List[FVG], price: float, direction: str) -> Optional[FVG]:
        for gap in reversed(fvgs):
            if gap.direction != direction or gap.filled:
                continue
            if gap.low <= price <= gap.high:
                return gap
        return None
