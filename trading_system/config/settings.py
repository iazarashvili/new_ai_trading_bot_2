from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class TimeframeConfig:
    execution: str = "M5"
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
class TradingSettings:
    symbols: tuple[str, ...] = ("BTCUSD", "EURUSD", "GBPUSD")
    timeframes: TimeframeConfig = field(default_factory=TimeframeConfig)
    data: DataConfig = field(default_factory=DataConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    magic_number: int = 234_000
    loop_interval_seconds: float = 5.0


SETTINGS = TradingSettings()
