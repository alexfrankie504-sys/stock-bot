"""
chart.py — Visualise backtest results
======================================
"""

import logging
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from backtester import run_backtest
from data import fetch_stock

log = logging.getLogger(__name__)


def plot_backtest(ticker: str, results: dict):
    equity  = results["equity_curve"]
    trades  = results["trades"]
    summary = results["summary"]

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    fig.suptitle(
        f"{ticker} Backtest  |  {summary['total_return']} return  "
        f"vs benchmark {summary['benchmark_return']}",
        fontsize=14, fontweight="bold"
    )

    # Chart 1: Equity curve vs benchmark
    start_price = equity["price"].iloc[0]
    start_cash  = 10_000
    benchmark   = (equity["price"] / start_price) * start_cash

    ax1.plot(equity.index, equity["value"], label="Strategy",   color="#2196F3", linewidth=2)
    ax1.plot(equity.index, benchmark,       label="Buy & hold", color="#FF9800", linewidth=1.5, linestyle="--")
    ax1.set_ylabel("Portfolio value ($)")
    ax1.legend(loc="upper left")
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax1.grid(True, alpha=0.3)

    # Chart 2: Price with buy/sell markers
    ax2.plot(equity.index, equity["price"], color="#555555", linewidth=1.5, label="Price")

    if len(trades) > 0:
        buys  = trades[trades["action"] == "BUY"]
        sells = trades[trades["action"] == "SELL"]
        if len(buys) > 0:
            ax2.scatter(
                pd.to_datetime(buys["date"]),
                buys["price"],
                marker="^", color="#4CAF50", s=120, zorder=5, label="BUY"
            )
        if len(sells) > 0:
            ax2.scatter(
                pd.to_datetime(sells["date"]),
                sells["price"],
                marker="v", color="#F44336", s=120, zorder=5, label="SELL"
            )

    ax2.set_ylabel("Price ($)")
    ax2.legend(loc="upper left")
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax2.grid(True, alpha=0.3)

    # Chart 3: Drawdown
    rolling_max = equity["value"].cummax()
    drawdown    = (equity["value"] - rolling_max) / rolling_max * 100

    ax3.fill_between(equity.index, drawdown, 0, color="#F44336", alpha=0.4, label="Drawdown")
    ax3.plot(equity.index, drawdown, color="#F44336", linewidth=1)
    ax3.set_ylabel("Drawdown (%)")
    ax3.set_xlabel("Date")
    ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc="lower left")

    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=45)

    plt.tight_layout()
    filename = f"{ticker}_backtest.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Chart saved → {filename}")


def plot_multi(tickers: list[str]):
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_title("Strategy comparison — all tickers", fontsize=14, fontweight="bold")

    colors = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0", "#F44336"]

    for i, ticker in enumerate(tickers):
        results = run_backtest(ticker, starting_cash=10_000, period="2y")
        equity  = results["equity_curve"]
        summary = results["summary"]
        color   = colors[i % len(colors)]
        ax.plot(
            equity.index,
            equity["value"],
            label=f"{ticker} ({summary['total_return']})",
            color=color,
            linewidth=2
        )

    ax.axhline(y=10_000, color="#999999", linestyle="--", linewidth=1, label="Starting cash")
    ax.set_ylabel("Portfolio value ($)")
    ax.set_xlabel("Date")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)

    plt.tight_layout()
    filename = "comparison_chart.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Chart saved → {filename}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    for ticker in ["AAPL", "MSFT", "SPY"]:
        print(f"Charting {ticker}...")
        results = run_backtest(ticker, starting_cash=10_000, period="2y")
        plot_backtest(ticker, results)

    print("Generating comparison chart...")
    plot_multi(["AAPL", "MSFT", "SPY"])

    print("\nAll done! Open your StockBot folder in Finder to see the charts.")