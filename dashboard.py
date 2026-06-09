"""
dashboard.py — Live portfolio dashboard
========================================
Usage:
    streamlit run dashboard.py
"""

import json
import os
import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from signals import latest_signal

LOG_FILE      = "paper_trades.json"
TICKERS       = [
    "AAPL","MSFT","GOOGL","NVDA","AMZN","META","TSLA","JPM","V",
    "XOM","JNJ","WMT","PG","HD","CVX","MRK","PEP","COST","AVGO",
    "ADBE","CSCO","MCD","NKE","AMD","QCOM","ORCL","GS","CAT","CRM",
    "SPY","QQQ"
]
STARTING_CASH = 10_000.00

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title = "Stock Bot Dashboard",
    page_icon  = "📈",
    layout     = "wide",
)

# ── Load state ────────────────────────────────────────────────────────────────

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

# ── Fetch live signals ─────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def fetch_signals():
    results = {}
    for ticker in TICKERS:
        try:
            results[ticker] = latest_signal(ticker)
        except Exception as e:
            results[ticker] = {"error": str(e)}
    return results

# ── Portfolio value ────────────────────────────────────────────────────────────

def portfolio_value(state, prices):
    total = state["cash"]
    for ticker, pos in state["positions"].items():
        price = prices.get(ticker, {}).get("close", pos["entry_price"])
        total += pos["shares"] * price
    return total

# ── Main dashboard ─────────────────────────────────────────────────────────────

st.title("📈 Stock Bot Dashboard")
st.caption(f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

state   = load_state()
signals = fetch_signals()
prices  = {t: s for t, s in signals.items() if "error" not in s}
total   = portfolio_value(state, prices)
gain    = total - STARTING_CASH
pct     = gain / STARTING_CASH * 100

# ── Top metrics ───────────────────────────────────────────────────────────────

st.markdown("---")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Portfolio Value",  f"${total:,.2f}",         f"{pct:+.1f}%")
col2.metric("Cash on Hand",     f"${state['cash']:,.2f}")
col3.metric("Open Positions",   len(state["positions"]))
col4.metric("Closed Trades",    len([t for t in state["trades"] if t["action"] == "SELL"]))
st.markdown("---")

# ── Live signals ──────────────────────────────────────────────────────────────

st.subheader("📊 Today's Signals")

signal_rows = []
for ticker, sig in signals.items():
    if "error" in sig:
        continue
    signal_rows.append({
        "Ticker":   ticker,
        "Price":    f"${sig['close']:,.2f}",
        "Signal":   sig["signal"],
        "RSI":      sig["rsi"],
        "SMA 50":   sig["sma_fast"],
        "SMA 200":  sig["sma_slow"],
        "MACD":     sig["macd"],
    })

if signal_rows:
    df_signals = pd.DataFrame(signal_rows)

    def color_signal(val):
        if val == "BUY":
            return "background-color: #1a472a; color: #69db7c"
        elif val == "SELL":
            return "background-color: #6b1a1a; color: #ff6b6b"
        return ""

    st.dataframe(
        df_signals.style.map(color_signal, subset=["Signal"]),
        use_container_width=True,
        hide_index=True
    )

st.markdown("---")

# ── Open positions ────────────────────────────────────────────────────────────

st.subheader("💼 Open Positions")

if state["positions"]:
    pos_rows = []
    for ticker, pos in state["positions"].items():
        current = prices.get(ticker, {}).get("close", pos["entry_price"])
        pl      = (current - pos["entry_price"]) * pos["shares"]
        pl_pct  = (current - pos["entry_price"]) / pos["entry_price"] * 100
        pos_rows.append({
            "Ticker":      ticker,
            "Shares":      pos["shares"],
            "Entry Price": f"${pos['entry_price']:,.2f}",
            "Current":     f"${current:,.2f}",
            "P/L ($)":     f"${pl:+,.2f}",
            "P/L (%)":     f"{pl_pct:+.1f}%",
            "Entry Date":  pos["entry_date"],
        })
    st.dataframe(pd.DataFrame(pos_rows), use_container_width=True, hide_index=True)
else:
    st.info("No open positions — waiting for a BUY signal.")

st.markdown("---")

# ── Equity curve ──────────────────────────────────────────────────────────────

st.subheader("📈 Portfolio Equity Curve")

if state["daily_log"]:
    df_log = pd.DataFrame([
        {"Date": e["date"], "Value": e["portfolio_value"]}
        for e in state["daily_log"]
    ])
    df_log["Date"] = pd.to_datetime(df_log["Date"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x         = df_log["Date"],
        y         = df_log["Value"],
        mode      = "lines+markers",
        name      = "Portfolio",
        line      = dict(color="#2196F3", width=2),
        fill      = "tozeroy",
        fillcolor = "rgba(33, 150, 243, 0.1)",
    ))
    fig.add_hline(
        y                = STARTING_CASH,
        line_dash        = "dash",
        line_color       = "#FF9800",
        annotation_text  = "Starting cash"
    )
    fig.update_layout(
        xaxis_title = "Date",
        yaxis_title = "Portfolio Value ($)",
        hovermode   = "x unified",
        height      = 400,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Equity curve will appear after a few days of running paper_trader.py daily.")

st.markdown("---")

# ── Trade history ─────────────────────────────────────────────────────────────

st.subheader("📋 Trade History")

if state["trades"]:
    df_trades = pd.DataFrame(state["trades"]).sort_values("date", ascending=False)

    def color_action(val):
        if val == "BUY":
            return "background-color: #1a472a; color: #69db7c"
        elif val == "SELL":
            return "background-color: #6b1a1a; color: #ff6b6b"
        return ""

    st.dataframe(
        df_trades.style.map(color_action, subset=["action"]),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No trades yet — the bot is waiting for strong signals.")

st.markdown("---")

# ── Signal breakdown cards ────────────────────────────────────────────────────

st.subheader("🔍 Signal Breakdown")

cols = st.columns(len(TICKERS))
for i, ticker in enumerate(TICKERS):
    sig = signals.get(ticker, {})
    if "error" in sig:
        continue
    with cols[i]:
        signal = sig["signal"]
        color  = "green" if signal == "BUY" else "red" if signal == "SELL" else "gray"
        st.markdown(f"### {ticker}")
        st.markdown(f"**Price:** ${sig['close']:,.2f}")
        st.markdown(f"**Signal:** :{color}[{signal}]")
        st.markdown(f"**RSI:** {sig['rsi']}")
        st.markdown(f"**SMA50:** {sig['sma_fast']}")
        st.markdown(f"**SMA200:** {sig['sma_slow']}")

st.markdown("---")
st.caption("Run python3 paper_trader.py daily to update your portfolio. Dashboard refreshes every 5 minutes.")