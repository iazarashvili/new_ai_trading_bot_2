You are a world-class quantitative developer, algorithmic trader, and distributed systems architect.

Your task is to design and implement a professional institutional-grade algorithmic trading system in Python.

The system must follow the same engineering principles used by hedge funds and professional quantitative trading firms.

The bot must be production-grade, modular, scalable, and fault-tolerant.

====================================================

TARGET MARKETS

Symbols:
BTCUSD
EURUSD
GBPUSD

Execution timeframe:
M5

Higher timeframe analysis:
H1
H4
D1

====================================================

CORE DESIGN PRINCIPLES

The system must follow these principles:

• modular architecture
• event-driven design
• clear separation of concerns
• testable components
• production-grade logging
• fault tolerance
• risk-first design

====================================================

PROJECT STRUCTURE

Create a professional architecture.

trading_system/

config/
settings.py
symbols.py
risk_limits.py

core/
event_bus.py
scheduler.py
engine.py

data/
market_data.py
candle_service.py
data_cache.py

connectors/
mt5_connector.py

features/
market_structure.py
liquidity_model.py
order_block_detector.py
fair_value_gap.py
support_resistance.py
volatility_model.py

strategy/
multi_timeframe_strategy.py
signal_engine.py

risk/
position_sizer.py
risk_manager.py
portfolio_guard.py

execution/
order_executor.py
slippage_model.py
trade_manager.py

portfolio/
portfolio_manager.py
exposure_controller.py

analytics/
performance_metrics.py
trade_statistics.py

backtesting/
backtester.py
walk_forward.py

monitoring/
logger.py
telemetry.py

bot.py

====================================================

MARKET DATA ENGINE

Fetch OHLCV data using MetaTrader5 API.

Maintain rolling window of at least 1000 candles.

Convert data to pandas DataFrame.

Implement caching to avoid unnecessary API calls.

====================================================

MULTI-TIMEFRAME MARKET MODEL

Higher timeframe defines bias.

D1 → macro trend
H4 → structure direction
H1 → liquidity targets
M5 → execution

Only allow trades aligned with higher timeframe structure.

====================================================

MARKET STRUCTURE ALGORITHM

Detect swing highs and lows.

Classify structure:

HH = Higher High
HL = Higher Low
LH = Lower High
LL = Lower Low

Detect:

Break of Structure (BOS)
Change of Character (CHOCH)

Maintain a rolling structure model.

====================================================

LIQUIDITY MODEL

Identify liquidity pools at:

• equal highs
• equal lows
• range highs
• range lows
• previous session highs
• previous session lows

Liquidity sweep definition:

Price breaks a liquidity level
AND closes back inside the range.

====================================================

ORDER BLOCK MODEL

Definition:

Last opposite candle before institutional impulse.

Impulse rule:

candle_range > average_range × 1.8

Store order block zones with:

direction
price range
timestamp

====================================================

FAIR VALUE GAP MODEL

Detect imbalance between candles.

Bullish FVG:

candle3.low > candle1.high

Bearish FVG:

candle3.high < candle1.low

Track unfilled gaps.

====================================================

SUPPORT / RESISTANCE MODEL

Cluster swing levels.

Convert clusters into zones.

Use price tolerance based on volatility.

====================================================

VOLATILITY MODEL

Use ATR to detect volatility regime.

Avoid trading in extremely low volatility.

====================================================

SIGNAL ENGINE

A trade is only valid when multiple institutional signals align.

LONG CONDITIONS

• higher timeframe trend bullish
• liquidity sweep below support
• bullish order block
• price inside bullish FVG
• bullish structure shift

SHORT CONDITIONS

• higher timeframe trend bearish
• liquidity sweep above resistance
• bearish order block
• price inside bearish FVG
• bearish structure shift

====================================================

POSITION SIZING

Risk per trade = 1%

lot_size =

(account_balance × risk_percent)
/ stop_loss_distance

====================================================

TRADE MANAGEMENT

After entry:

1R → move SL to breakeven
2R → partial take profit
3R → trail stop behind structure

====================================================

PORTFOLIO RISK CONTROLS

Max open trades = 1

Max daily loss = 3%

Max weekly loss = 6%

If risk limits exceeded:

disable trading.

====================================================

EXECUTION ENGINE

Use MetaTrader5 order_send().

Implement:

• slippage protection
• retry logic
• order validation

====================================================

EVENT LOOP

The system must run an event-driven loop.

Main cycle:

update market data
update indicators
detect structure
detect liquidity
detect order blocks
detect FVG
generate signals
execute trades
manage open trades

====================================================

LOGGING AND MONITORING

Log:

trade entries
trade exits
errors
risk events

Use structured logging.

====================================================

BACKTESTING SYSTEM

Implement historical simulation.

Return metrics:

win rate
profit factor
max drawdown
Sharpe ratio

====================================================

CODE QUALITY

Code must be:

• modular
• typed where possible
• documented
• production quality

Use:

pandas
numpy
MetaTrader5
logging

The final system must resemble professional quantitative trading infrastructure.
