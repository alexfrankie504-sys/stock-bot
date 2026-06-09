"""
main.py — Stock Bot entry point
================================
Runs the full pipeline: fetch data, generate signals,
backtest, and output charts + a final recommendation.

Usage:
    python3 main.py
"""

import logging
from data import fetch_stock
from signals import get_signal, latest_signal
from backtester import run_backtest, print_report
from chart import plot_backtest, plot_multi

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

# ── Configure your tickers and starting cash here ─────────────────────────────

TICKERS       = [
    "AAPL","MSFT","GOOGL","NVDA","AMZN","META","TSLA","JPM","V",
    "XOM","JNJ","WMT","PG","HD","CVX","MRK","PEP","COST","AVGO",
    "ADBE","CSCO","MCD","NKE","AMD","QCOM","ORCL","GS","CAT","CRM",
    "SPY","QQQ"
]
STARTING_CASH = 10_000
PERIOD        = "2y"

# ─────────────────────────────────────────────────────────────────────────────


def run():
    print("\n" + "="*60)
    print("         STOCK BOT — FULL ANALYSIS")
    print("="*60)

    # ── Step 1: Latest signals — what should I do TODAY? ──────────────────
    print("\n📊 TODAY'S SIGNALS\n")
    print(f"  {'Ticker':<8} {'Price':>8} {'Signal':>6} {'RSI':>6} {'SMA Fast':>10} {'SMA Slow':>10}")
    print(f"  {'-'*8} {'-'*8} {'-'*6} {'-'*6} {'-'*10} {'-'*10}")

    buys  = []
    holds = []
    sells = []

    for ticker in TICKERS:
        try:
            result = latest_signal(ticker)
            signal = result["signal"]
            print(
                f"  {ticker:<8} "
                f"${result['close']:>7.2f} "
                f"{signal:>6} "
                f"{str(result['rsi'] or '-'):>6} "
                f"{str(result['sma_fast'] or '-'):>10} "
                f"{str(result['sma_slow'] or '-'):>10}"
            )
            if signal == "BUY":
                buys.append(ticker)
            elif signal == "SELL":
                sells.append(ticker)
            else:
                holds.append(ticker)
        except Exception as e:
            print(f"  {ticker:<8} ERROR: {e}")

    # ── Step 2: Recommendation summary ────────────────────────────────────
    print(f"\n{'='*60}")
    print("  RECOMMENDATION SUMMARY")
    print(f"{'='*60}")

    if buys:
        print(f"\n  ✅ BUY  : {', '.join(buys)}")
        print(f"     These tickers have 2+ indicators aligned bullish")
        print(f"     with above-average volume confirming the move.")
    if holds:
        print(f"\n  ⏸️  HOLD : {', '.join(holds)}")
        print(f"     No strong signal — stay patient.")
    if sells:
        print(f"\n  ❌ SELL : {', '.join(sells)}")
        print(f"     Multiple indicators pointing bearish.")

    if not buys and not sells:
        print("\n  No strong signals today. The market needs more time.")
        print("  This is normal — good signals are rare, that's what")
        print("  makes them valuable when they do appear.")

    # ── Step 3: Run backtests ──────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  BACKTEST RESULTS (last 2 years, $10,000 starting cash)")
    print(f"{'='*60}")

    all_results = {}
    for ticker in TICKERS:
        try:
            results = run_backtest(
                ticker        = ticker,
                starting_cash = STARTING_CASH,
                period        = PERIOD,
            )
            all_results[ticker] = results
            print_report(results)
        except Exception as e:
            print(f"\n  {ticker}: ERROR — {e}")

    # ── Step 4: Generate charts ────────────────────────────────────────────
    print(f"{'='*60}")
    print("  GENERATING CHARTS ...")
    print(f"{'='*60}\n")

    for ticker, results in all_results.items():
        plot_backtest(ticker, results)

    if len(all_results) > 1:
        plot_multi(list(all_results.keys()))

    # ── Step 5: Final leaderboard ──────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  LEADERBOARD — best to worst strategy return")
    print(f"{'='*60}")
    print(f"\n  {'Rank':<6} {'Ticker':<8} {'Return':>8} {'vs Market':>10} {'Win Rate':>10} {'Drawdown':>10}")
    print(f"  {'-'*6} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")

    sorted_results = sorted(
        all_results.items(),
        key=lambda x: float(x[1]["summary"]["total_return"].replace("%", "").replace("+", "")),
        reverse=True
    )

    for rank, (ticker, results) in enumerate(sorted_results, 1):
        s = results["summary"]
        print(
            f"  {rank:<6} {ticker:<8} "
            f"{s['total_return']:>8} "
            f"{s['vs_benchmark']:>10} "
            f"{s['win_rate']:>10} "
            f"{s['max_drawdown']:>10}"
        )

    print(f"\n{'='*60}")
    print("  All charts saved to your StockBot folder.")
    print("  Run python3 main.py any time to get fresh signals.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run()