"""
paper_trader.py — Paper trading tracker with stop loss + sentiment
==================================================================
Logs every signal the bot generates day by day.
Automatically sells positions that hit their stop loss.
Uses sentiment analysis to confirm signals before trading.

Usage:
    python3 paper_trader.py
"""

import json
import logging
import os
import datetime
from signals import latest_signal
from sizer import get_position_size, DEFAULT_SETTINGS
from sentiment import get_sentiment, combined_signal
from alerts import send_buy_alert, send_sell_alert, send_daily_summary

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

TICKERS = [
    "AAPL","MSFT","GOOGL","NVDA","AMZN","META","TSLA","JPM","V",
    "XOM","JNJ","WMT","PG","HD","CVX","MRK","PEP","COST","AVGO",
    "ADBE","CSCO","MCD","NKE","AMD","QCOM","ORCL","GS","CAT","CRM",
    "SPY","QQQ"
]
STARTING_CASH  = 10_000.00
LOG_FILE       = "paper_trades.json"
STOP_LOSS_PCT  = 0.05
TRAIL_STOP     = True


# ── JSON helper ────────────────────────────────────────────────────────────────

def json_convert(obj):
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return str(obj)
    raise TypeError(f"Not serializable: {type(obj)}")


# ── Load / save state ──────────────────────────────────────────────────────────

def load_state() -> dict:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
    return {
        "starting_cash": STARTING_CASH,
        "cash":          STARTING_CASH,
        "positions":     {},
        "trades":        [],
        "daily_log":     [],
        "created":       str(datetime.date.today()),
    }


def save_state(state: dict):
    with open(LOG_FILE, "w") as f:
        json.dump(state, f, indent=2, default=json_convert)
    log.info("State saved → %s", LOG_FILE)


# ── Stop loss checker ──────────────────────────────────────────────────────────

def check_stop_losses(state: dict, current_prices: dict, date: str):
    triggered = []
    for ticker, pos in list(state["positions"].items()):
        current_price = current_prices.get(ticker)
        if not current_price:
            continue
        stop_price = pos["stop_loss"]
        if TRAIL_STOP:
            new_stop = current_price * (1 - STOP_LOSS_PCT)
            if new_stop > stop_price:
                pos["stop_loss"]     = round(new_stop, 2)
                pos["highest_price"] = round(current_price, 2)
        if current_price <= pos["stop_loss"]:
            triggered.append((ticker, current_price))
    for ticker, price in triggered:
        pos = state["positions"][ticker]
        print(f"\n  🛑 STOP LOSS triggered for {ticker}!")
        print(f"     Entry: ${pos['entry_price']:.2f} → Current: ${price:.2f}")
        print(f"     Stop was set at: ${pos['stop_loss']:.2f}")
        execute_sell(state, ticker, price, date, reason="STOP_LOSS")


# ── Trade execution ────────────────────────────────────────────────────────────

def execute_buy(state: dict, ticker: str, price: float, date: str):
    if ticker in state["positions"]:
        log.info("Already holding %s — skipping buy.", ticker)
        return
    if state["cash"] < price:
        log.warning("Not enough cash to buy %s.", ticker)
        return
    size   = get_position_size(
        portfolio_value = state["cash"],
        entry_price     = price,
        settings        = DEFAULT_SETTINGS,
    )
    shares = size["shares"]
    cost   = shares * price
    if shares == 0:
        log.warning("Position size too small for %s at $%.2f", ticker, price)
        return
    stop_price = round(price * (1 - STOP_LOSS_PCT), 2)
    state["cash"] -= cost
    state["positions"][ticker] = {
        "shares":        shares,
        "entry_price":   price,
        "entry_date":    date,
        "cost":          round(cost, 2),
        "stop_loss":     stop_price,
        "highest_price": price,
    }
    trade = {
        "date":       date,
        "ticker":     ticker,
        "action":     "BUY",
        "price":      round(price, 2),
        "shares":     shares,
        "value":      round(cost, 2),
        "stop_loss":  stop_price,
        "reason":     "SIGNAL",
        "cash_after": round(state["cash"], 2),
    }
    state["trades"].append(trade)
    send_buy_alert(ticker, price, stop_price, shares, round(cost, 2))
    print(f"\n  🟢 BUY  {ticker}")
    print(f"     {shares} shares @ ${price:.2f} = ${cost:,.2f}")
    print(f"     Stop loss set at: ${stop_price:.2f} (-{STOP_LOSS_PCT*100:.0f}%)")
    print(f"     Cash remaining: ${state['cash']:,.2f}")


def execute_sell(
    state:  dict,
    ticker: str,
    price:  float,
    date:   str,
    reason: str = "SIGNAL"
):
    if ticker not in state["positions"]:
        log.info("No position in %s — skipping sell.", ticker)
        return
    pos      = state["positions"][ticker]
    shares   = pos["shares"]
    proceeds = shares * price
    profit   = proceeds - pos["cost"]
    pct      = profit / pos["cost"] * 100
    state["cash"] += proceeds
    del state["positions"][ticker]
    trade = {
        "date":       date,
        "ticker":     ticker,
        "action":     "SELL",
        "price":      round(price, 2),
        "shares":     shares,
        "value":      round(proceeds, 2),
        "profit":     round(profit, 2),
        "return_pct": round(pct, 2),
        "reason":     reason,
        "cash_after": round(state["cash"], 2),
    }
    state["trades"].append(trade)
    send_sell_alert(ticker, price, profit, pct, reason)
    emoji = "✅" if profit >= 0 else "🔴"
    print(f"\n  {emoji} SELL {ticker} ({reason})")
    print(f"     {shares} shares @ ${price:.2f} = ${proceeds:,.2f}")
    print(f"     Profit/Loss: ${profit:,.2f} ({pct:+.1f}%)")
    print(f"     Cash now: ${state['cash']:,.2f}")


# ── Portfolio summary ──────────────────────────────────────────────────────────

def portfolio_value(state: dict, current_prices: dict) -> float:
    total = state["cash"]
    for ticker, pos in state["positions"].items():
        price = current_prices.get(ticker, pos["entry_price"])
        total += pos["shares"] * price
    return total


def print_portfolio(state: dict, current_prices: dict):
    total = portfolio_value(state, current_prices)
    start = state["starting_cash"]
    gain  = total - start
    pct   = gain / start * 100
    print(f"\n{'='*60}")
    print(f"  PAPER PORTFOLIO SUMMARY")
    print(f"{'='*60}")
    print(f"  Started      : {state['created']}")
    print(f"  Today        : {str(datetime.date.today())}")
    print(f"  Starting cash: ${start:,.2f}")
    print(f"  Cash on hand : ${state['cash']:,.2f}")
    print(f"  Total value  : ${total:,.2f}")
    print(f"  Total return : ${gain:+,.2f} ({pct:+.1f}%)")
    if state["positions"]:
        print(f"\n  Open positions:")
        print(f"  {'Ticker':<8} {'Shares':>6} {'Entry':>8} {'Now':>8} {'Stop':>8} {'P/L':>10} {'%':>7}")
        print(f"  {'-'*8} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*10} {'-'*7}")
        for ticker, pos in state["positions"].items():
            current = current_prices.get(ticker, pos["entry_price"])
            pl      = (current - pos["entry_price"]) * pos["shares"]
            pl_pct  = (current - pos["entry_price"]) / pos["entry_price"] * 100
            print(
                f"  {ticker:<8} {pos['shares']:>6} "
                f"${pos['entry_price']:>7.2f} "
                f"${current:>7.2f} "
                f"${pos['stop_loss']:>7.2f} "
                f"${pl:>+9,.2f} "
                f"{pl_pct:>+6.1f}%"
            )
    else:
        print(f"\n  No open positions.")
    if state["trades"]:
        closed = [t for t in state["trades"] if t["action"] == "SELL"]
        if closed:
            wins         = [t for t in closed if t.get("profit", 0) >= 0]
            stop_hits    = [t for t in closed if t.get("reason") == "STOP_LOSS"]
            win_rate     = len(wins) / len(closed) * 100
            total_profit = sum(t.get("profit", 0) for t in closed)
            print(f"\n  Closed trades  : {len(closed)}")
            print(f"  Win rate       : {win_rate:.1f}%")
            print(f"  Stop losses hit: {len(stop_hits)}")
            print(f"  Total realised : ${total_profit:+,.2f}")
    print(f"{'='*60}\n")


def print_trade_history(state: dict):
    if not state["trades"]:
        print("  No trades yet.\n")
        return
    print(f"  {'Date':<12} {'Ticker':<8} {'Action':<6} {'Price':>8} {'Shares':>6} {'Value':>10} {'P/L':>10} {'Reason':<12}")
    print(f"  {'-'*12} {'-'*8} {'-'*6} {'-'*8} {'-'*6} {'-'*10} {'-'*10} {'-'*12}")
    for t in state["trades"]:
        pl = f"${t.get('profit', 0):+,.2f}" if t["action"] == "SELL" else "-"
        print(
            f"  {t['date']:<12} {t['ticker']:<8} {t['action']:<6} "
            f"${t['price']:>7.2f} {t['shares']:>6} "
            f"${t['value']:>9,.2f} {pl:>10} "
            f"{t.get('reason', '-'):<12}"
        )
    print()


# ── Main daily run ─────────────────────────────────────────────────────────────

def run_daily():
    today = str(datetime.date.today())
    state = load_state()

    print(f"\n{'='*60}")
    print(f"  PAPER TRADER — {today}")
    print(f"{'='*60}")
    print(f"\n  Fetching signals...\n")

    current_prices = {}
    daily_signals  = []

    for ticker in TICKERS:
        try:
            result = latest_signal(ticker)
            current_prices[ticker] = result["close"]
            for k, v in result.items():
                if isinstance(v, (datetime.date, datetime.datetime)):
                    result[k] = str(v)
            daily_signals.append(result)
        except Exception as e:
            log.warning("Error fetching %s: %s", ticker, e)

    # Check stop losses first
    print("  Checking stop losses...")
    check_stop_losses(state, current_prices, today)

    # Process signals with sentiment
    print("\n  Processing signals with sentiment analysis...\n")
    print(f"  {'Ticker':<6} {'Price':>8}  {'Tech':<6} {'News':<10} {'Final':<12}")
    print(f"  {'-'*6} {'-'*8}  {'-'*6} {'-'*10} {'-'*12}")

    for result in daily_signals:
        ticker    = result["ticker"]
        signal    = result["signal"]
        price     = result["close"]
        sentiment = get_sentiment(ticker)
        final     = combined_signal(signal, sentiment)

        print(f"  {ticker:<6} ${price:>8.2f}  {signal:<6} {sentiment['label']:<10} {final:<12}")

        if final in ["STRONG BUY", "BUY"]:
            execute_buy(state, ticker, price, today)
        elif final in ["STRONG SELL", "SELL"]:
            execute_sell(state, ticker, price, today, reason="SIGNAL")

    # Send daily summary email
    total = portfolio_value(state, current_prices)
    gain  = total - state["starting_cash"]
    pct   = gain / state["starting_cash"] * 100
    send_daily_summary(total, gain, pct, daily_signals)

    # Log today's snapshot
    state["daily_log"].append({
        "date":            today,
        "signals":         daily_signals,
        "portfolio_value": round(portfolio_value(state, current_prices), 2),
    })

    print_portfolio(state, current_prices)
    print_trade_history(state)
    save_state(state)


if __name__ == "__main__":
    run_daily()