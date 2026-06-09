"""
alerts.py — Email alerts for buy/sell signals
===============================================
Sends you an email when the bot generates a BUY or SELL signal.

Usage:
    python3 alerts.py   (sends a test email)
    from alerts import send_buy_alert, send_sell_alert, send_daily_summary
"""

import yagmail
import logging
from datetime import datetime

log = logging.getLogger(__name__)

# ── Your email config ─────────────────────────────────────────────────────────

GMAIL_ADDRESS = "alexfrankie504@gmail.com"
GMAIL_APP_PWD = "sulz iyst cikf xcdc"
ALERT_TO      = "alexfrankie504@gmail.com"


# ── Core sender ───────────────────────────────────────────────────────────────

def send_alert(subject: str, body: str) -> bool:
    try:
        yag = yagmail.SMTP(GMAIL_ADDRESS, GMAIL_APP_PWD)
        yag.send(to=ALERT_TO, subject=subject, contents=body)
        log.info("Alert sent → %s", subject)
        return True
    except Exception as e:
        log.error("Failed to send alert: %s", e)
        return False


# ── Alert types ───────────────────────────────────────────────────────────────

def send_buy_alert(ticker: str, price: float, stop_loss: float, shares: int, value: float) -> bool:
    subject = f"🟢 StockBot BUY Signal — {ticker}"
    body = f"""
    <h2 style="color:#4CAF50;">🟢 BUY Signal — {ticker}</h2>
    <table style="border-collapse:collapse;width:400px;">
        <tr style="background:#f5f5f5;">
            <td style="padding:10px;font-weight:bold;">Ticker</td>
            <td style="padding:10px;">{ticker}</td>
        </tr>
        <tr>
            <td style="padding:10px;font-weight:bold;">Entry Price</td>
            <td style="padding:10px;">${price:,.2f}</td>
        </tr>
        <tr style="background:#f5f5f5;">
            <td style="padding:10px;font-weight:bold;">Shares</td>
            <td style="padding:10px;">{shares}</td>
        </tr>
        <tr>
            <td style="padding:10px;font-weight:bold;">Total Value</td>
            <td style="padding:10px;">${value:,.2f}</td>
        </tr>
        <tr style="background:#f5f5f5;">
            <td style="padding:10px;font-weight:bold;">Stop Loss</td>
            <td style="padding:10px;color:#F44336;">${stop_loss:,.2f}</td>
        </tr>
        <tr>
            <td style="padding:10px;font-weight:bold;">Date</td>
            <td style="padding:10px;">{datetime.today().strftime('%Y-%m-%d %H:%M')}</td>
        </tr>
    </table>
    <p style="color:#888;font-size:12px;margin-top:20px;">
        This is a paper trade — no real money was used.
    </p>
    """
    return send_alert(subject, body)


def send_sell_alert(ticker: str, price: float, profit: float, pct: float, reason: str) -> bool:
    color   = "#4CAF50" if profit >= 0 else "#F44336"
    emoji   = "✅" if profit >= 0 else "🔴"
    subject = f"{emoji} StockBot SELL — {ticker} ({pct:+.1f}%)"
    body = f"""
    <h2 style="color:{color};">{emoji} SELL Signal — {ticker}</h2>
    <table style="border-collapse:collapse;width:400px;">
        <tr style="background:#f5f5f5;">
            <td style="padding:10px;font-weight:bold;">Ticker</td>
            <td style="padding:10px;">{ticker}</td>
        </tr>
        <tr>
            <td style="padding:10px;font-weight:bold;">Exit Price</td>
            <td style="padding:10px;">${price:,.2f}</td>
        </tr>
        <tr style="background:#f5f5f5;">
            <td style="padding:10px;font-weight:bold;">Profit/Loss</td>
            <td style="padding:10px;color:{color};">${profit:+,.2f} ({pct:+.1f}%)</td>
        </tr>
        <tr>
            <td style="padding:10px;font-weight:bold;">Reason</td>
            <td style="padding:10px;">{reason}</td>
        </tr>
        <tr style="background:#f5f5f5;">
            <td style="padding:10px;font-weight:bold;">Date</td>
            <td style="padding:10px;">{datetime.today().strftime('%Y-%m-%d %H:%M')}</td>
        </tr>
    </table>
    <p style="color:#888;font-size:12px;margin-top:20px;">
        This is a paper trade — no real money was used.
    </p>
    """
    return send_alert(subject, body)


def send_daily_summary(
    portfolio_value: float,
    gain: float,
    pct: float,
    signals: list
) -> bool:
    subject = f"📊 StockBot Daily Summary — ${portfolio_value:,.2f} ({pct:+.1f}%)"

    rows = ""
    for s in signals:
        color = "#4CAF50" if s["signal"] == "BUY" else "#F44336" if s["signal"] == "SELL" else "#888"
        rows += f"""
        <tr>
            <td style="padding:8px;">{s['ticker']}</td>
            <td style="padding:8px;">${s['close']:,.2f}</td>
            <td style="padding:8px;color:{color};font-weight:bold;">{s['signal']}</td>
            <td style="padding:8px;">{s.get('rsi', '-')}</td>
        </tr>
        """

    gain_color = "#4CAF50" if gain >= 0 else "#F44336"
    body = f"""
    <h2 style="color:#2196F3;">📊 Daily Summary — {datetime.today().strftime('%Y-%m-%d')}</h2>
    <table style="border-collapse:collapse;width:400px;margin-bottom:20px;">
        <tr style="background:#f5f5f5;">
            <td style="padding:10px;font-weight:bold;">Portfolio Value</td>
            <td style="padding:10px;">${portfolio_value:,.2f}</td>
        </tr>
        <tr>
            <td style="padding:10px;font-weight:bold;">Total Return</td>
            <td style="padding:10px;color:{gain_color};">${gain:+,.2f} ({pct:+.1f}%)</td>
        </tr>
    </table>
    <h3>Today's Signals</h3>
    <table style="border-collapse:collapse;width:400px;">
        <tr style="background:#2196F3;color:white;">
            <th style="padding:8px;">Ticker</th>
            <th style="padding:8px;">Price</th>
            <th style="padding:8px;">Signal</th>
            <th style="padding:8px;">RSI</th>
        </tr>
        {rows}
    </table>
    <p style="color:#888;font-size:12px;margin-top:20px;">
        This is a paper trading simulation — no real money was used.
    </p>
    """
    return send_alert(subject, body)


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    print("Sending test email to alexfrankie504@gmail.com ...")
    result = send_alert(
        subject = "✅ StockBot — Email alerts are working!",
        body    = "<h2>Your stock bot email alerts are set up and working!</h2><p>You will now receive alerts whenever the bot generates a BUY or SELL signal.</p>"
    )
    print("✅ Success! Check your inbox." if result else "❌ Failed — check the error above.")