# Algorithmic Trading System

Institutional-grade, event-driven algorithmic trading bot built on the MetaTrader 5 API.

## Architecture

```
trading_system/
├── config/          Settings, symbol specs, risk limits
├── core/            Event bus, scheduler, trading engine
├── connectors/      MT5 API wrapper
├── data/            Market data, candle service, caching
├── features/        Market structure, liquidity, order blocks, FVG, S/R, volatility
├── strategy/        Multi-timeframe strategy, signal engine
├── risk/            Position sizing, risk manager, portfolio guard
├── execution/       Order executor, slippage model, trade manager
├── portfolio/       Portfolio manager, exposure controller
├── analytics/       Performance metrics, trade statistics
├── backtesting/     Backtester, walk-forward analysis
├── monitoring/      Structured logging, telemetry
└── bot.py           Main entry point
```

## Target Markets

| Symbol | Timeframe |
|--------|-----------|
| BTCUSD | M5 (execution), H1/H4/D1 (bias) |
| EURUSD | M5 (execution), H1/H4/D1 (bias) |
| GBPUSD | M5 (execution), H1/H4/D1 (bias) |

## Strategy

The system uses a **Smart Money Concepts (SMC)** approach with institutional confluence:

- **Market Structure** — swing highs/lows, BOS (Break of Structure), CHOCH (Change of Character)
- **Liquidity Pools** — equal highs/lows, range extremes, session levels
- **Order Blocks** — last opposite candle before institutional impulse moves
- **Fair Value Gaps** — price imbalances between three consecutive candles
- **Support/Resistance** — clustered swing levels with volatility-based tolerance
- **Volatility Filter** — ATR-based regime detection to avoid low-volatility environments

Trades are only taken when **multiple signals align** across timeframes.

## Risk Management

- 1% risk per trade
- Maximum 1 open trade
- 3% daily loss limit
- 6% weekly loss limit
- Automatic trading halt when limits are breached

## Trade Management

- **1R** — stop loss moved to breakeven
- **2R** — 50% partial take profit
- **3R** — trailing stop activated behind structure

## Requirements

- Python 3.10+
- MetaTrader 5 terminal running
- Windows OS (MT5 Python API is Windows-only)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Live Trading

```bash
python -m trading_system.bot
```

### Backtesting

```python
from trading_system.backtesting.backtester import Backtester, BacktestConfig
from trading_system.connectors.mt5_connector import MT5Connector

connector = MT5Connector()
connector.connect()

data = {
    "M5": connector.get_candles("EURUSD", "M5", 5000),
    "D1": connector.get_candles("EURUSD", "D1", 500),
}

bt = Backtester(BacktestConfig(initial_balance=10_000))
result = bt.run(data)

print(f"Win rate: {result.metrics.win_rate:.1%}")
print(f"Profit factor: {result.metrics.profit_factor:.2f}")
print(f"Max drawdown: {result.metrics.max_drawdown_pct:.1%}")
print(f"Sharpe ratio: {result.metrics.sharpe_ratio:.2f}")

connector.disconnect()
```

### Walk-Forward Analysis

```python
from trading_system.backtesting.walk_forward import WalkForward

wf = WalkForward(n_splits=5)
result = wf.run(data)

for w in result.windows:
    print(f"IS PF={w.in_sample_metrics.profit_factor:.2f}  "
          f"OOS PF={w.out_of_sample_metrics.profit_factor:.2f}")
```

## Configuration

Edit `trading_system/config/settings.py` to change symbols, timeframes, and execution parameters.  
Edit `trading_system/config/risk_limits.py` to adjust risk parameters.
