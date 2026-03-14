from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class MT5Connection:
    login: Optional[int] = None
    password: Optional[str] = None
    server: Optional[str] = None
    path: Optional[str] = None


@dataclass(frozen=True)
class TimeframeConfig:
    execution: str = "M15"
    higher: tuple[str, ...] = ("H1", "H4", "D1")

    @property
    def all(self) -> tuple[str, ...]:
        return (self.execution, *self.higher)


@dataclass(frozen=True)
class DataConfig:
    rolling_window: int = 1000
    cache_ttl_seconds: int = 60


@dataclass(frozen=True)
class ExecutionConfig:
    max_slippage_points: int = 10
    order_retries: int = 3
    retry_delay_seconds: float = 0.5


@dataclass(frozen=True)
class TradingHours:
    """Allowed trading window (local time). Trading is blocked outside this range."""
    start_hour: int = 8    # 08:00 - trading starts
    end_hour: int = 21     # 21:00 - trading stops
    enabled: bool = True


@dataclass(frozen=True)
class TradingSettings:
    mt5: MT5Connection = field(default_factory=MT5Connection)
    symbols: tuple[str, ...] = ("EURUSDm",)
    timeframes: TimeframeConfig = field(default_factory=TimeframeConfig)
    data: DataConfig = field(default_factory=DataConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    trading_hours: TradingHours = field(default_factory=TradingHours)
    magic_number: int = 234_000
    loop_interval_seconds: float = 5.0


SETTINGS = TradingSettings(
    mt5=MT5Connection(
        login=262427958,       # e.g. 12345678
        password="Kaloria1@",    # e.g. "mypassword"
        server="Exness-MT5Trial16",    # e.g. "MetaQuotes-Demo"
        path=r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe",
    ),
)
