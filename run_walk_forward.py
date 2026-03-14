from trading_system.connectors.mt5_connector import MT5Connector
from trading_system.backtesting.backtester import Backtester, BacktestConfig
from trading_system.backtesting.walk_forward import WalkForward

# ბოლო ~1.5 წელი: M15 = 50000 კანდლი, D1 = 550
M15_COUNT = 50_000
D1_COUNT = 550

def main():
    connector = MT5Connector()
    if not connector.connect():
        print("MT5 connection failed")
        return

    data = {
        "M15": connector.get_candles("BTCUSDm", "M15", M15_COUNT),
        "D1": connector.get_candles("BTCUSDm", "D1", D1_COUNT),
    }
    connector.disconnect()

    if data["M15"] is None:
        print("No data - check symbol name (e.g. BTCUSDm)")
        return

    print(f"სრული პერიოდი: {data['M15'].index[0]} — {data['M15'].index[-1]}\n")

    wf = WalkForward(n_splits=5, oos_ratio=0.2)
    result = wf.run(data, execution_tf="M15", htf="D1", step=2)

    print("\n" + "=" * 65)
    print("WALK-FORWARD ანალიზი")
    print("=" * 65)
    print("""
რას ნიშნავს:
  • In-Sample (სწავლა)  — სტრატეგია ამ პერიოდზე „სწავლობს“
  • Out-of-Sample (შემოწმება) — ახალ, უნახულ მონაცემებზე ტესტი
  • PF = Profit Factor, WR = Win Rate
""")

    initial = 10_000
    for i, w in enumerate(result.windows):
        start_ts = data["M15"].index[w.out_of_sample_start]
        end_ts = data["M15"].index[min(w.out_of_sample_end - 1, len(data["M15"]) - 1)]
        oos_final = initial + w.out_of_sample_metrics.total_pnl
        print(f"ფანჯარა {i + 1}/5 | შემოწმების პერიოდი: {start_ts.date()} — {end_ts.date()}")
        print(f"   სწავლა:     ტრეიდები={w.in_sample_metrics.total_trades:3}  "
              f"PF={w.in_sample_metrics.profit_factor:.2f}  WR={w.in_sample_metrics.win_rate:.1%}")
        print(f"   შემოწმება: ტრეიდები={w.out_of_sample_metrics.total_trades:3}  "
              f"PF={w.out_of_sample_metrics.profit_factor:.2f}  WR={w.out_of_sample_metrics.win_rate:.1%}")
        print(f"              {initial:,.0f}$ → {oos_final:,.0f}$  ({w.out_of_sample_metrics.total_pnl:+,.0f}$)")
        print()

    print("-" * 65)
    m = result.aggregate_oos_metrics
    final = initial + m.total_pnl
    print("შეჯამება (ყველა შემოწმების ფანჯარა ერთად):")
    print(f"   საწყისი ბალანსი: {initial:,.2f}$")
    print(f"   საბოლოო ბალანსი:  {final:,.2f}$")
    print(f"   ცვლილება:         {m.total_pnl:+,.2f}$")
    print()
    print(f"   ტრეიდები: {m.total_trades}")
    print(f"   Win rate: {m.win_rate:.1%}")
    print(f"   Profit factor: {m.profit_factor:.2f}")
    print(f"   Max drawdown: {m.max_drawdown_pct:.1%}")
    print(f"   Sharpe: {m.sharpe_ratio:.2f}")
    if m.total_trades == 0:
        print("\n⚠ შენიშვნა: OOS-ში 0 ტრეიდი — სტრატეგია შეიძლება არ გადაიდოს ახალ მონაცემებზე.")

if __name__ == "__main__":
    main()
