from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import MetaTrader5 as mt5
import pandas as pd

logger = logging.getLogger(__name__)

TIMEFRAME_MAP: Dict[str, int] = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
}


@dataclass
class AccountInfo:
    balance: float
    equity: float
    margin: float
    free_margin: float
    leverage: int
    currency: str


@dataclass
class OrderResult:
    success: bool
    ticket: int
    price: float
    volume: float
    comment: str
    retcode: int


class MT5Connector:
    """Wrapper around the MetaTrader5 Python API."""

    def __init__(
        self,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        path: Optional[str] = None,
        magic: int = 234_000,
    ) -> None:
        self._login = login
        self._password = password
        self._server = server
        self._path = path
        self._magic = magic
        self._connected = False

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def connect(self) -> bool:
        init_kwargs: Dict[str, Any] = {}
        if self._path:
            init_kwargs["path"] = self._path
        if self._login:
            init_kwargs["login"] = self._login
        if self._password:
            init_kwargs["password"] = self._password
        if self._server:
            init_kwargs["server"] = self._server

        if not mt5.initialize(**init_kwargs):
            logger.error("MT5 initialize failed: %s", mt5.last_error())
            return False
        self._connected = True
        info = mt5.account_info()
        if info:
            logger.info(
                "Connected – account %s, balance %.2f %s",
                info.login,
                info.balance,
                info.currency,
            )
        return True

    def disconnect(self) -> None:
        mt5.shutdown()
        self._connected = False
        logger.info("MT5 disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------
    def account_info(self) -> Optional[AccountInfo]:
        info = mt5.account_info()
        if info is None:
            return None
        return AccountInfo(
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            leverage=info.leverage,
            currency=info.currency,
        )

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------
    def get_candles(
        self, symbol: str, timeframe: str, count: int = 1000
    ) -> Optional[pd.DataFrame]:
        tf = TIMEFRAME_MAP.get(timeframe)
        if tf is None:
            logger.error("Unknown timeframe: %s", timeframe)
            return None

        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            logger.warning("No rates returned for %s %s", symbol, timeframe)
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.rename(
            columns={
                "time": "datetime",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "tick_volume": "volume",
            },
            inplace=True,
        )
        df.set_index("datetime", inplace=True)
        return df[["open", "high", "low", "close", "volume"]]

    def get_tick(self, symbol: str) -> Optional[Dict[str, float]]:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return {"bid": tick.bid, "ask": tick.ask, "time": tick.time}

    # ------------------------------------------------------------------
    # Order execution
    # ------------------------------------------------------------------
    def place_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        price: float,
        sl: float,
        tp: float,
        comment: str = "",
        max_retries: int = 3,
        retry_delay: float = 0.5,
        max_slippage: int = 10,
    ) -> OrderResult:
        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": max_slippage,
            "magic": self._magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        for attempt in range(1, max_retries + 1):
            result = mt5.order_send(request)
            if result is None:
                logger.error("order_send returned None (attempt %d)", attempt)
                time.sleep(retry_delay)
                continue
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(
                    "Order filled: ticket=%d price=%.5f vol=%.2f",
                    result.order,
                    result.price,
                    result.volume,
                )
                return OrderResult(
                    success=True,
                    ticket=result.order,
                    price=result.price,
                    volume=result.volume,
                    comment=result.comment,
                    retcode=result.retcode,
                )
            logger.warning(
                "Order failed (attempt %d): retcode=%d comment=%s",
                attempt,
                result.retcode,
                result.comment,
            )
            time.sleep(retry_delay)

        return OrderResult(
            success=False, ticket=0, price=0.0, volume=0.0,
            comment="Max retries exceeded", retcode=-1,
        )

    def modify_position(
        self, ticket: int, symbol: str, sl: float, tp: float
    ) -> bool:
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": ticket,
            "sl": sl,
            "tp": tp,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info("Modified position %d – SL=%.5f TP=%.5f", ticket, sl, tp)
            return True
        logger.warning("Failed to modify position %d: %s", ticket, result)
        return False

    def close_position(self, ticket: int, symbol: str, volume: float) -> bool:
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            logger.warning("Position %d not found", ticket)
            return False
        p = pos[0]
        close_type = (
            mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        )
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return False
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 10,
            "magic": self._magic,
            "comment": "close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info("Closed position %d", ticket)
            return True
        logger.warning("Failed to close position %d: %s", ticket, result)
        return False

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Any]:
        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()
        return list(positions) if positions else []
