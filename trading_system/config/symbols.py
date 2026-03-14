from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class SymbolSpec:
    name: str
    pip_value: float
    min_lot: float
    max_lot: float
    lot_step: float
    contract_size: float
    digits: int


DEFAULT_SPECS: Dict[str, SymbolSpec] = {
    "BTCUSDm": SymbolSpec(
        name="BTCUSDm",
        pip_value=1.0,           # BTC price in USD, 1 pip = $1
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        contract_size=1.0,        # 1 lot = 1 BTC
        digits=2,
    ),
}


def get_symbol_spec(symbol: str) -> SymbolSpec:
    spec = DEFAULT_SPECS.get(symbol)
    if spec is None:
        raise ValueError(f"Unknown symbol: {symbol}")
    return spec
