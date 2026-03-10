"""
Institutional-grade algorithmic trading bot.

Wires together all subsystems and runs the main event-driven loop.
"""
from __future__ import annotations

import logging
import signal
import sys
from typing import Optional

from trading_system.config.settings import SETTINGS
from trading_system.connectors.mt5_connector import MT5Connector
from trading_system.core.engine import TradingEngine
from trading_system.core.event_bus import EventBus
from trading_system.core.scheduler import Scheduler
from trading_system.data.candle_service import CandleService
from trading_system.data.data_cache import DataCache
from trading_system.execution.order_executor import OrderExecutor
from trading_system.execution.slippage_model import SlippageModel
from trading_system.execution.trade_manager import TradeManager
from trading_system.features.fair_value_gap import FairValueGap
from trading_system.features.liquidity_model import LiquidityModel
from trading_system.features.market_structure import MarketStructure
from trading_system.features.order_block_detector import OrderBlockDetector
from trading_system.features.support_resistance import SupportResistance
from trading_system.features.volatility_model import VolatilityModel
from trading_system.monitoring.logger import setup_logging
from trading_system.monitoring.telemetry import Telemetry
from trading_system.portfolio.exposure_controller import ExposureController
from trading_system.portfolio.portfolio_manager import PortfolioManager
from trading_system.risk.portfolio_guard import PortfolioGuard
from trading_system.risk.position_sizer import PositionSizer
from trading_system.risk.risk_manager import RiskManager
from trading_system.strategy.multi_timeframe_strategy import MultiTimeframeStrategy
from trading_system.strategy.signal_engine import SignalEngine

logger = logging.getLogger(__name__)


class TradingBot:
    """Top-level orchestrator that initializes all components and runs the bot."""

    def __init__(self) -> None:
        setup_logging()
        logger.info("Initializing Trading Bot")

        self.event_bus = EventBus()
        self.connector = MT5Connector(
            login=SETTINGS.mt5.login,
            password=SETTINGS.mt5.password,
            server=SETTINGS.mt5.server,
            path=SETTINGS.mt5.path,
            magic=SETTINGS.magic_number,
        )
        self.telemetry = Telemetry()

        # Data
        self.cache = DataCache(ttl_seconds=SETTINGS.data.cache_ttl_seconds)
        self.candle_service = CandleService(
            connector=self.connector,
            cache=self.cache,
            rolling_window=SETTINGS.data.rolling_window,
        )

        # Features
        self.market_structure = MarketStructure()
        self.liquidity_model = LiquidityModel()
        self.order_block_detector = OrderBlockDetector()
        self.fvg_detector = FairValueGap()
        self.support_resistance = SupportResistance()
        self.volatility_model = VolatilityModel()

        # Risk
        self.position_sizer = PositionSizer()
        self.risk_manager = RiskManager(
            connector=self.connector, event_bus=self.event_bus
        )
        self.portfolio_guard = PortfolioGuard(
            connector=self.connector, risk_manager=self.risk_manager
        )

        # Execution
        self.slippage_model = SlippageModel()
        self.order_executor = OrderExecutor(
            connector=self.connector,
            event_bus=self.event_bus,
            position_sizer=self.position_sizer,
            slippage_model=self.slippage_model,
        )
        self.trade_manager = TradeManager(
            connector=self.connector,
            event_bus=self.event_bus,
            portfolio_guard=self.portfolio_guard,
        )

        # Strategy
        self.mtf_strategy = MultiTimeframeStrategy()
        self.signal_engine = SignalEngine(
            event_bus=self.event_bus,
            mtf_strategy=self.mtf_strategy,
            risk_manager=self.risk_manager,
            order_executor=self.order_executor,
        )

        # Portfolio
        self.portfolio_manager = PortfolioManager(connector=self.connector)
        self.exposure_controller = ExposureController(connector=self.connector)

        # Engine
        self.engine = TradingEngine(
            event_bus=self.event_bus,
            candle_service=self.candle_service,
            market_structure=self.market_structure,
            liquidity_model=self.liquidity_model,
            order_block_detector=self.order_block_detector,
            fvg_detector=self.fvg_detector,
            support_resistance=self.support_resistance,
            volatility_model=self.volatility_model,
            signal_engine=self.signal_engine,
            trade_manager=self.trade_manager,
            symbols=SETTINGS.symbols,
            timeframes=SETTINGS.timeframes.all,
        )

        # Scheduler
        self.scheduler = Scheduler(interval_seconds=SETTINGS.loop_interval_seconds)
        self.scheduler.register(self.engine.tick)

    def start(self) -> None:
        logger.info("Starting Trading Bot")
        if not self.connector.connect():
            logger.critical("Failed to connect to MT5 – aborting")
            sys.exit(1)

        account = self.connector.account_info()
        if account:
            logger.info(
                "Account: balance=%.2f equity=%.2f leverage=%d",
                account.balance, account.equity, account.leverage,
            )

        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        try:
            self.scheduler.start()
        except Exception:
            logger.exception("Unhandled exception in main loop")
        finally:
            self.stop()

    def stop(self) -> None:
        logger.info("Shutting down Trading Bot")
        self.scheduler.stop()
        self.connector.disconnect()
        logger.info("Trading Bot stopped")

    def _handle_shutdown(self, signum: int, frame: object) -> None:
        logger.info("Received signal %d – shutting down", signum)
        self.stop()
        sys.exit(0)


def main() -> None:
    bot = TradingBot()
    bot.start()


if __name__ == "__main__":
    main()
