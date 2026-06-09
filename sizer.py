"""
sizer.py — Position sizing
===========================
Answers the question: "How much should I invest in this trade?"

Three sizing methods:
  1. Fixed percent  — always invest X% of your portfolio
  2. Kelly criterion — mathematically optimal bet size based on win rate
  3. Risk-based      — never risk more than X% of portfolio on one trade

Usage:
    from sizer import get_position_size
"""

import logging
import math

log = logging.getLogger(__name__)

# ── Default risk settings (change these to match your comfort level) ──────────

DEFAULT_SETTINGS = {
    "method":        "risk_based",  # "fixed" | "kelly" | "risk_based"
    "fixed_pct":     0.95,          # Fixed: use 95% of cash per trade
    "max_risk_pct":  0.02,          # Risk-based: never risk more than 2% of portfolio
    "stop_loss_pct": 0.05,          # Risk-based: assume 5% stop loss on entry
    "kelly_floor":   0.05,          # Kelly: minimum bet size (5%)
    "kelly_ceiling": 0.25,          # Kelly: maximum bet size (25%)
    "max_positions": 5,             # Max number of stocks held at once
}


# ── Sizing methods ─────────────────────────────────────────────────────────────

def _fixed_size(portfolio_value: float, settings: dict) -> float:
    """
    Invest a fixed percentage of your portfolio every time.
    Simple, predictable, easy to understand.

    Example: $10,000 portfolio × 95% = $9,500 invested
    """
    return portfolio_value * settings["fixed_pct"]


def _kelly_size(
    portfolio_value: float,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    settings: dict,
) -> float:
    """
    Kelly Criterion — the mathematically optimal position size.

    Formula: f = (win_rate / loss_size) - (loss_rate / win_size)

    A win_rate of 60% with avg win of 10% and avg loss of 5%:
    f = (0.6 / 0.05) - (0.4 / 0.10) = 12 - 4 = 8 → capped at ceiling

    Kelly can suggest very large bets — always cap it.
    """
    if avg_win <= 0 or avg_loss <= 0:
        log.warning("Kelly: invalid win/loss values, falling back to fixed sizing.")
        return _fixed_size(portfolio_value, settings)

    loss_rate = 1 - win_rate
    kelly_pct = (win_rate / avg_loss) - (loss_rate / avg_win)

    # Half-Kelly is safer in practice — reduces variance
    half_kelly = kelly_pct / 2

    # Clamp between floor and ceiling
    clamped = max(settings["kelly_floor"], min(settings["kelly_ceiling"], half_kelly))

    log.info(
        "Kelly: raw=%.1f%% half=%.1f%% clamped=%.1f%%",
        kelly_pct * 100, half_kelly * 100, clamped * 100
    )

    return portfolio_value * clamped


def _risk_based_size(
    portfolio_value: float,
    entry_price: float,
    settings: dict,
) -> float:
    """
    Risk-based sizing — the most professional method.

    Logic:
    - You're willing to lose at most X% of your portfolio on this trade
    - You'll cut the loss if price drops Y% from entry (stop loss)
    - Therefore: position size = max_loss_dollars / stop_loss_pct

    Example:
    - Portfolio: $10,000
    - Max risk: 2% = $200
    - Stop loss: 5% below entry
    - Position size: $200 / 0.05 = $4,000

    This means if the stock drops 5% you lose exactly $200 (2% of portfolio).
    """
    max_loss_dollars = portfolio_value * settings["max_risk_pct"]
    position_size    = max_loss_dollars / settings["stop_loss_pct"]

    # Never invest more than 95% of portfolio in one trade
    max_allowed = portfolio_value * 0.95
    return min(position_size, max_allowed)


# ── Public API ─────────────────────────────────────────────────────────────────

def get_position_size(
    portfolio_value: float,
    entry_price:     float,
    settings:        dict = None,
    win_rate:        float = 0.5,
    avg_win:         float = 0.08,
    avg_loss:        float = 0.04,
) -> dict:
    """
    Calculate how much to invest in a trade.

    Parameters
    ----------
    portfolio_value : Total current portfolio value in dollars
    entry_price     : Price you're buying at
    settings        : Override DEFAULT_SETTINGS
    win_rate        : Historical win rate of your strategy (0.0 to 1.0)
    avg_win         : Average winning trade return (e.g. 0.08 = 8%)
    avg_loss        : Average losing trade return (e.g. 0.04 = 4%)

    Returns
    -------
    dict with:
        dollars      — how much to invest in dollars
        shares       — how many shares to buy
        pct          — what % of portfolio this represents
        stop_loss    — price to cut the loss at
        max_loss     — maximum dollar loss if stop is hit
        method       — which sizing method was used
    """
    s = {**DEFAULT_SETTINGS, **(settings or {})}

    method = s["method"]

    if method == "fixed":
        dollars = _fixed_size(portfolio_value, s)
    elif method == "kelly":
        dollars = _kelly_size(portfolio_value, win_rate, avg_win, avg_loss, s)
    elif method == "risk_based":
        dollars = _risk_based_size(portfolio_value, entry_price, s)
    else:
        raise ValueError(f"Unknown method '{method}'. Use: fixed | kelly | risk_based")

    shares       = math.floor(dollars / entry_price)  # whole shares only
    actual_spend = shares * entry_price
    stop_price   = entry_price * (1 - s["stop_loss_pct"])
    max_loss     = shares * (entry_price - stop_price)
    pct          = actual_spend / portfolio_value * 100

    result = {
        "method":      method,
        "portfolio":   f"${portfolio_value:,.2f}",
        "entry_price": f"${entry_price:,.2f}",
        "dollars":     f"${actual_spend:,.2f}",
        "shares":      shares,
        "pct":         f"{pct:.1f}%",
        "stop_loss":   f"${stop_price:,.2f}",
        "max_loss":    f"${max_loss:,.2f}",
        "max_loss_pct": f"{max_loss / portfolio_value * 100:.2f}%",
    }

    return result


def size_all_signals(
    signals: list[dict],
    portfolio_value: float,
    settings: dict = None,
) -> list[dict]:
    """
    Given a list of BUY signals, calculate position sizes for each,
    splitting the portfolio evenly across all signals.

    Parameters
    ----------
    signals         : List of dicts with 'ticker' and 'close' keys
    portfolio_value : Total portfolio value

    Returns
    -------
    List of position size dicts, one per signal
    """
    s = {**DEFAULT_SETTINGS, **(settings or {})}

    # Split portfolio evenly — don't put everything in one stock
    max_pos    = s["max_positions"]
    allocation = portfolio_value / min(len(signals), max_pos)

    results = []
    for sig in signals:
        size = get_position_size(
            portfolio_value = allocation,
            entry_price     = sig["close"],
            settings        = settings,
        )
        size["ticker"] = sig["ticker"]
        results.append(size)

    return results


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from signals import latest_signal

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    portfolio = 10_000

    print("=" * 55)
    print("  POSITION SIZER — how much to invest per trade")
    print("=" * 55)

    tickers = ["AAPL", "MSFT", "SPY", "GOOGL", "NVDA"]

    for ticker in tickers:
        sig   = latest_signal(ticker)
        price = sig["close"]

        print(f"\n  {ticker} @ ${price}")
        print(f"  {'-'*40}")

        for method in ["fixed", "risk_based", "kelly"]:
            size = get_position_size(
                portfolio_value = portfolio,
                entry_price     = price,
                settings        = {"method": method, **DEFAULT_SETTINGS},
                win_rate        = 0.65,
                avg_win         = 0.10,
                avg_loss        = 0.05,
            )
            print(
                f"  {method:<12} → "
                f"invest {size['dollars']:>10} "
                f"({size['pct']:>6} of portfolio)  |  "
                f"stop @ {size['stop_loss']}  |  "
                f"max loss {size['max_loss']} ({size['max_loss_pct']})"
            )

    print(f"\n{'='*55}")
    print("  RECOMMENDED: risk_based at 2% max risk per trade")
    print(f"{'='*55}\n")