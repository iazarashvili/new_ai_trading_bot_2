from trading_system.connectors.mt5_connector import MT5Connector
from trading_system.backtesting.backtester import Backtester, BacktestConfig
from trading_system.config.settings import SETTINGS

# ბოლო 1 წელი: M15 = 365×24×4 ≈ 35000 კანდლი, D1 = 365
M15_ONE_YEAR = 35_000
D1_ONE_YEAR = 365

def main():
    connector = MT5Connector()
    if not connector.connect():
        print("MT5 connection failed")
        return

    for symbol in SETTINGS.symbols:
        print(f"\n{'='*50}")
        print(f"BACKTEST: {symbol}")
        print(f"{'='*50}")

        data = {
            "M15": connector.get_candles(symbol, "M15", M15_ONE_YEAR),
            "D1": connector.get_candles(symbol, "D1", D1_ONE_YEAR),
        }

        if data["M15"] is None:
            print(f"No data for {symbol} - check symbol name")
            continue

        print(f"პერიოდი: {data['M15'].index[0]} — {data['M15'].index[-1]}")

        bt = Backtester(BacktestConfig(initial_balance=10_000))
        result = bt.run(data, execution_tf="M15", step=5)

        initial = 10_000
        final = initial + result.metrics.total_pnl

        print(f"\nსაწყისი ბალანსი: {initial:,.2f}$")
        print(f"საბოლოო ბალანსი:  {final:,.2f}$")
        print(f"ცვლილება:         {result.metrics.total_pnl:+,.2f}$")
        print()
        print(f"ტრეიდები: {result.metrics.total_trades}")
        print(f"Win rate: {result.metrics.win_rate:.1%}")
        print(f"Profit factor: {result.metrics.profit_factor:.2f}")
        print(f"Max drawdown: {result.metrics.max_drawdown_pct:.1%}")
        print(f"Sharpe: {result.metrics.sharpe_ratio:.2f}")

    connector.disconnect()

if __name__ == "__main__":
    main()
