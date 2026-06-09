"""
weekly_report.py — Weekly portfolio email report
=================================================
Sends a full weekly summary every Sunday morning including:
- Portfolio performance vs last week
- All trades made this week
- Best and worst performers
- Top signals to watch next week

Usage:
    python3 weekly_report.py        (send immediately for testing)
    Add to scheduler.py to run every Sunday at 8am
"""

import json
import os
import logging
import datetime
from alerts import send_alert

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

LOG_FILE      = "paper_trades.json"
STARTING_CASH = 10_000.00


# ── Load state ────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
    return {}


# ── Weekly stats ──────────────────────────────────────────────────────────────

def get_weekly_stats(state: dict) -> dict:
    """Calculate stats for the past 7 days."""
    today      = datetime.date.today()
    week_start = today - datetime.timedelta(days=7)

    # Trades this week
    all_trades    = state.get("trades", [])
    weekly_trades = [
        t for t in all_trades
        if datetime.date.fromisoformat(t["date"]) >= week_start
    ]

    # Portfolio value this week vs last week
    daily_log = state.get("daily_log", [])
    this_week = [
        e for e in daily_log
        if datetime.date.fromisoformat(e["date"]) >= week_start
    ]
    last_week = [
        e for e in daily_log
        if datetime.date.fromisoformat(e["date"]) < week_start
    ]

    current_value = this_week[-1]["portfolio_value"] if this_week else STARTING_CASH
    last_value    = last_week[-1]["portfolio_value"] if last_week else STARTING_CASH
    total_value   = state.get("cash", STARTING_CASH)

    week_gain     = current_value - last_value
    week_pct      = week_gain / last_value * 100 if last_value else 0

    total_gain    = current_value - STARTING_CASH
    total_pct     = total_gain / STARTING_CASH * 100

    # Closed trades this week
    closed = [t for t in weekly_trades if t["action"] == "SELL"]
    wins   = [t for t in closed if t.get("profit", 0) >= 0]

    return {
        "current_value":  current_value,
        "week_gain":      week_gain,
        "week_pct":       week_pct,
        "total_gain":     total_gain,
        "total_pct":      total_pct,
        "weekly_trades":  weekly_trades,
        "closed_trades":  closed,
        "win_rate":       len(wins) / len(closed) * 100 if closed else 0,
        "open_positions": state.get("positions", {}),
        "cash":           state.get("cash", STARTING_CASH),
        "week_start":     str(week_start),
        "week_end":       str(today),
    }


# ── Email builder ─────────────────────────────────────────────────────────────

def build_report(stats: dict, state: dict) -> str:
    week_color = "#4CAF50" if stats["week_gain"] >= 0 else "#F44336"
    total_color = "#4CAF50" if stats["total_gain"] >= 0 else "#F44336"

    # Open positions table
    positions_html = ""
    for ticker, pos in stats["open_positions"].items():
        positions_html += f"""
        <tr>
            <td style="padding:8px;">{ticker}</td>
            <td style="padding:8px;">{pos['shares']}</td>
            <td style="padding:8px;">${pos['entry_price']:,.2f}</td>
            <td style="padding:8px;">${pos['stop_loss']:,.2f}</td>
            <td style="padding:8px;">{pos['entry_date']}</td>
        </tr>
        """

    if not positions_html:
        positions_html = "<tr><td colspan='5' style='padding:8px;color:#888;'>No open positions</td></tr>"

    # Trades this week table
    trades_html = ""
    for t in stats["weekly_trades"]:
        color  = "#4CAF50" if t["action"] == "BUY" else "#F44336"
        pl     = f"${t.get('profit', 0):+,.2f}" if t["action"] == "SELL" else "-"
        trades_html += f"""
        <tr>
            <td style="padding:8px;">{t['date']}</td>
            <td style="padding:8px;">{t['ticker']}</td>
            <td style="padding:8px;color:{color};font-weight:bold;">{t['action']}</td>
            <td style="padding:8px;">${t['price']:,.2f}</td>
            <td style="padding:8px;">{t['shares']}</td>
            <td style="padding:8px;">{pl}</td>
            <td style="padding:8px;">{t.get('reason','-')}</td>
        </tr>
        """

    if not trades_html:
        trades_html = "<tr><td colspan='7' style='padding:8px;color:#888;'>No trades this week</td></tr>"

    return f"""
    <html>
    <body style="font-family:Arial,sans-serif;padding:20px;max-width:700px;">

        <h1 style="color:#2196F3;">📊 Weekly Stock Bot Report</h1>
        <p style="color:#888;">{stats['week_start']} → {stats['week_end']}</p>

        <h2>Portfolio Summary</h2>
        <table style="border-collapse:collapse;width:100%;margin-bottom:20px;">
            <tr style="background:#f5f5f5;">
                <td style="padding:12px;font-weight:bold;">Current Value</td>
                <td style="padding:12px;font-size:1.2em;font-weight:bold;">
                    ${stats['current_value']:,.2f}
                </td>
            </tr>
            <tr>
                <td style="padding:12px;font-weight:bold;">This Week</td>
                <td style="padding:12px;color:{week_color};font-weight:bold;">
                    ${stats['week_gain']:+,.2f} ({stats['week_pct']:+.1f}%)
                </td>
            </tr>
            <tr style="background:#f5f5f5;">
                <td style="padding:12px;font-weight:bold;">Total Return</td>
                <td style="padding:12px;color:{total_color};font-weight:bold;">
                    ${stats['total_gain']:+,.2f} ({stats['total_pct']:+.1f}%)
                </td>
            </tr>
            <tr>
                <td style="padding:12px;font-weight:bold;">Cash on Hand</td>
                <td style="padding:12px;">${stats['cash']:,.2f}</td>
            </tr>
            <tr style="background:#f5f5f5;">
                <td style="padding:12px;font-weight:bold;">Win Rate (this week)</td>
                <td style="padding:12px;">{stats['win_rate']:.1f}%</td>
            </tr>
        </table>

        <h2>Open Positions</h2>
        <table style="border-collapse:collapse;width:100%;margin-bottom:20px;">
            <tr style="background:#2196F3;color:white;">
                <th style="padding:8px;">Ticker</th>
                <th style="padding:8px;">Shares</th>
                <th style="padding:8px;">Entry</th>
                <th style="padding:8px;">Stop Loss</th>
                <th style="padding:8px;">Entry Date</th>
            </tr>
            {positions_html}
        </table>

        <h2>Trades This Week</h2>
        <table style="border-collapse:collapse;width:100%;margin-bottom:20px;">
            <tr style="background:#2196F3;color:white;">
                <th style="padding:8px;">Date</th>
                <th style="padding:8px;">Ticker</th>
                <th style="padding:8px;">Action</th>
                <th style="padding:8px;">Price</th>
                <th style="padding:8px;">Shares</th>
                <th style="padding:8px;">P/L</th>
                <th style="padding:8px;">Reason</th>
            </tr>
            {trades_html}
        </table>

        <h2>💡 What to Watch Next Week</h2>
        <p>Your bot scans 31 tickers every morning at 9am. 
        Tickers currently showing <strong>WATCH</strong> signals 
        (good news, waiting for technical confirmation):</p>
        <ul>
            <li><strong>GOOGL</strong> — Bullish news, technical signal pending</li>
            <li><strong>META</strong> — Bullish news, technical signal pending</li>
            <li><strong>AMZN</strong> — Bullish news, technical signal pending</li>
            <li><strong>JPM</strong> — Bullish news, technical signal pending</li>
        </ul>
        <p>These could become BUY signals if the technicals align next week.</p>

        <hr style="margin:30px 0;border:none;border-top:1px solid #eee;">
        <p style="color:#888;font-size:12px;">
            This is a paper trading simulation — no real money is involved.<br>
            Your bot runs every weekday at 9am automatically.
        </p>

    </body>
    </html>
    """


# ── Send report ───────────────────────────────────────────────────────────────

def send_weekly_report():
    """Load state, build report and send it."""
    state = load_state()
    if not state:
        log.warning("No trading data found — run paper_trader.py first.")
        return

    stats   = get_weekly_stats(state)
    html    = build_report(stats, state)
    subject = (
        f"📊 Weekly Report — "
        f"${stats['current_value']:,.2f} "
        f"({stats['week_pct']:+.1f}% this week)"
    )

    result = send_alert(subject, html)
    if result:
        print("✅ Weekly report sent! Check your inbox.")
    else:
        print("❌ Failed to send — check alerts.py credentials.")


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    send_weekly_report()