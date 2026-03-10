from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from trading_system.core.event_bus import Event, EventBus, EventType

if TYPE_CHECKING:
    from trading_system.connectors.mt5_connector import MT5Connector
    from trading_system.data.candle_service import CandleService
    from trading_system.execution.trade_manager import TradeManager
    from trading_system.features.fair_value_gap import FairValueGap
    from trading_system.features.liquidity_model import LiquidityModel
    from trading_system.features.market_structure import MarketStructure
    from trading_system.features.order_block_detector import OrderBlockDetector
    from trading_system.features.support_resistance import SupportResistance
    from trading_system.features.volatility_model import VolatilityModel
    from trading_system.strategy.signal_engine import SignalEngine

logger = logging.getLogger(__name__)


class TradingEngine:
    """Orchestrates a single iteration of the main trading loop.

    Each call to ``tick`` performs the full cycle:
      1. Update market data
      2. Compute features (structure, liquidity, OB, FVG, S/R, volatility)
      3. Generate signals
      4. Manage existing trades
    """

    def __init__(
        self,
        event_bus: EventBus,
        candle_service: "CandleService",
        market_structure: "MarketStructure",
        liquidity_model: "LiquidityModel",
        order_block_detector: "OrderBlockDetector",
        fvg_detector: "FairValueGap",
        support_resistance: "SupportResistance",
        volatility_model: "VolatilityModel",
        signal_engine: "SignalEngine",
        trade_manager: "TradeManager",
        symbols: tuple[str, ...] = (),
        timeframes: tuple[str, ...] = (),
    ) -> None:
        self.event_bus = event_bus
        self.candle_service = candle_service
        self.market_structure = market_structure
        self.liquidity_model = liquidity_model
        self.order_block_detector = order_block_detector
        self.fvg_detector = fvg_detector
        self.support_resistance = support_resistance
        self.volatility_model = volatility_model
        self.signal_engine = signal_engine
        self.trade_manager = trade_manager
        self.symbols = symbols
        self.timeframes = timeframes

    def tick(self) -> None:
        for symbol in self.symbols:
            try:
                self._process_symbol(symbol)
            except Exception:
                logger.exception("Error processing symbol %s", symbol)

    def _process_symbol(self, symbol: str) -> None:
        candles_by_tf = {}
        for tf in self.timeframes:
            df = self.candle_service.get_candles(symbol, tf)
            if df is None or df.empty:
                logger.warning("No data for %s %s", symbol, tf)
                return
            candles_by_tf[tf] = df

        self.event_bus.publish(Event(
            event_type=EventType.MARKET_DATA,
            payload={"symbol": symbol, "timeframes": list(candles_by_tf.keys())},
        ))

        features: dict = {}
        for tf, df in candles_by_tf.items():
            ms = self.market_structure.analyze(df)
            liq = self.liquidity_model.analyze(df)
            obs = self.order_block_detector.detect(df)
            fvgs = self.fvg_detector.detect(df)
            sr = self.support_resistance.compute_zones(df)
            vol = self.volatility_model.analyze(df)
            features[tf] = {
                "market_structure": ms,
                "liquidity": liq,
                "order_blocks": obs,
                "fvg": fvgs,
                "support_resistance": sr,
                "volatility": vol,
            }

        self.signal_engine.evaluate(symbol, candles_by_tf, features)
        self.trade_manager.manage_open_trades(symbol)
