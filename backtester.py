"""
backtester.py — Simulate a trading strategy on historical data
==============================================================
Replays your signals day-by-day on historical prices and tracks
a virtual portfolio so you can see exactly how your strategy
would have performed.

Usage:
    python3 backtester.py

Install dependencies:
    pip3 install yfinance pandas ta
"""

import logging
import pandas as pd
from data import fetch_stock
from signals import get_signal

log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

DEFAULT_CASH       = 10_000.00   # Starting portfolio value in dollars
DEFAULT_COMMISSION = 0.001       # 0.1% per trade (realistic for most brokers)
POSITION_SIZE      = 0.95        # Use 95% of available cash per buy (keep 5% reserve)


# ── Portfolio tracker ─────────────────────────────────────────────────────────

class Portfolio:
    """Tracks cash, shares held, and trade history during a backtest."""

    def __init__(self, starting_cash: float):
        self.cash         = starting_cash
        self.shares       = 0.0
        self.trades       = []
        self.equity_curve = []

    def buy(self, date, price: float, commission: float):
        if self.shares > 0:
            return  # already in a position
        spend        = self.cash * POSITION_SIZE
        cost         = spend * (1 + commission)
        if cost > self.cash:
            return
        self.shares   = spend / price
        self.cash    -= cost
        self.trades.append({
            "date":   date,
            "action": "BUY",
            "price":  round(price, 2),
            "shares": round(self.shares, 4),
            "value":  round(spend, 2),
        })

    def sell(self, date, price: float, commission: float):
        if self.shares == 0:
            return  # nothing to sell
        proceeds      = self.shares * price * (1 - commission)
        self.cash    += proceeds
        self.trades.append({
            "date":   date,
            "action": "SELL",
            "price":  round(price, 2),
            "shares": round(self.shares, 4),
            "value":  round(proceeds, 2),
        })
        self.shares   = 0.0

    def total_value(self, current_price: float) -> float:
        return self.cash + self.shares * current_price

    def record(self, date, price: float):
        self.equity_curve.append({
            "date":  date,
            "value": round(self.total_value(price), 2),
            "price": round(price, 2),
        })


# ── Core backtest ─────────────────────────────────────────────────────────────

def run_backtest(
    ticker: str,
    starting_cash: float = DEFAULT_CASH,
    commission: float    = DEFAULT_COMMISSION,
    signal_params: dict  = None,
    period: str          = "2y",
) -> dict:
    """
    Run a full backtest for a single ticker.

    Parameters
    ----------
    ticker        : Stock symbol e.g. "AAPL"
    starting_cash : Virtual dollars to start with
    commission    : Fraction charged per trade e.g. 0.001 = 0.1%
    signal_params : Override default signal strategy params
    period        : How much history to test on e.g. "2y", "5y"

    Returns
    -------
    dict with keys:
        summary      — key performance stats
        trades       — DataFrame of every trade made
        equity_curve — DataFrame of portfolio value over time
        benchmark    — DataFrame of buy-and-hold comparison
    """
    log.info("Running backtest for %s ...", ticker)

    # Fetch data and compute signals
    df = fetch_stock(ticker, period=period)
    df = get_signal(df, signal_params)

    portfolio  = Portfolio(starting_cash)
    benchmark_shares = (starting_cash * POSITION_SIZE) / float(df["Close"].iloc[0])

    # Replay history day by day
    for date, row in df.iterrows():
        price  = float(row["Close"])
        signal = row["Signal"]

        if signal == "BUY":
            portfolio.buy(date, price, commission)
        elif signal == "SELL":
            portfolio.sell(date, price, commission)

        portfolio.record(date, price)

    # Force-close any open position at the end
    last_price = float(df["Close"].iloc[-1])
    last_date  = df.index[-1]
    if portfolio.shares > 0:
        portfolio.sell(last_date, last_price, commission)

    # Build results
    equity_df   = pd.DataFrame(portfolio.equity_curve).set_index("date")
    trades_df   = pd.DataFrame(portfolio.trades)

    start_price = float(df["Close"].iloc[0])
    end_price   = float(df["Close"].iloc[-1])

    final_value     = portfolio.cash
    total_return    = (final_value - starting_cash) / starting_cash * 100
    benchmark_value = benchmark_shares * end_price
    benchmark_return = (benchmark_value - starting_cash) / starting_cash * 100

    # Win rate
    if len(trades_df) >= 2:
        buys  = trades_df[trades_df["action"] == "BUY"]["value"].values
        sells = trades_df[trades_df["action"] == "SELL"]["value"].values
        pairs = min(len(buys), len(sells))
        if pairs > 0:
            wins     = sum(sells[:pairs] > buys[:pairs])
            win_rate = wins / pairs * 100
        else:
            win_rate = 0.0
    else:
        win_rate = 0.0

    # Max drawdown
    rolling_max = equity_df["value"].cummax()
    drawdown    = (equity_df["value"] - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()

    summary = {
        "ticker":           ticker.upper(),
        "period":           period,
        "start_date":       df.index[0].date(),
        "end_date":         df.index[-1].date(),
        "starting_cash":    f"${starting_cash:,.2f}",
        "final_value":      f"${final_value:,.2f}",
        "total_return":     f"{total_return:+.1f}%",
        "benchmark_return": f"{benchmark_return:+.1f}%",
        "vs_benchmark":     f"{total_return - benchmark_return:+.1f}%",
        "total_trades":     len(trades_df),
        "win_rate":         f"{win_rate:.1f}%",
        "max_drawdown":     f"{max_drawdown:.1f}%",
    }

    return {
        "summary":      summary,
        "trades":       trades_df,
        "equity_curve": equity_df,
        "benchmark":    benchmark_value,
    }


def print_report(results: dict):
    """Print a clean summary report to the terminal."""
    s = results["summary"]
    t = results["trades"]

    print("\n" + "="*50)
    print(f"  BACKTEST REPORT — {s['ticker']}")
    print("="*50)
    print(f"  Period         : {s['start_date']} → {s['end_date']}")
    print(f"  Starting cash  : {s['starting_cash']}")
    print(f"  Final value    : {s['final_value']}")
    print(f"  Total return   : {s['total_return']}")
    print(f"  Buy & hold     : {s['benchmark_return']}")
    print(f"  vs Benchmark   : {s['vs_benchmark']}")
    print(f"  Total trades   : {s['total_trades']}")
    print(f"  Win rate       : {s['win_rate']}")
    print(f"  Max drawdown   : {s['max_drawdown']}")
    print("="*50)

    if len(t) > 0:
        print("\n  Recent trades:")
        print(t.tail(10).to_string(index=False))
    print()


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    # Test on a few different tickers
    for ticker in ["AAPL", "MSFT", "SPY"]:
        results = run_backtest(
            ticker        = ticker,
            starting_cash = 10_000,
            period        = "2y",
        )
        print_report(results)