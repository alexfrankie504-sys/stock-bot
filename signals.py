"""
signals.py — Technical indicators and buy/sell/hold signals
============================================================
"""

import logging
import pandas as pd
import ta

log = logging.getLogger(__name__)

DEFAULT_PARAMS = {
    "sma_fast": 50,
    "sma_slow": 200,
    "rsi_period": 14,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "bb_period": 20,
    "bb_std": 2.0,
    "volume_sma": 20,
    "strategy": "combined",
    "require_volume": True,
}


def add_indicators(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    p = {**DEFAULT_PARAMS, **(params or {})}
    df = df.copy()

    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]
    vol   = df["Volume"]

    df["SMA_fast"] = close.rolling(p["sma_fast"]).mean()
    df["SMA_slow"] = close.rolling(p["sma_slow"]).mean()

    df["RSI"] = ta.momentum.RSIIndicator(close, window=p["rsi_period"]).rsi()

    macd_obj = ta.trend.MACD(close)
    df["MACD"]        = macd_obj.macd()
    df["MACD_signal"] = macd_obj.macd_signal()
    df["MACD_hist"]   = macd_obj.macd_diff()

    bb = ta.volatility.BollingerBands(close, window=p["bb_period"], window_dev=p["bb_std"])
    df["BB_upper"] = bb.bollinger_hband()
    df["BB_mid"]   = bb.bollinger_mavg()
    df["BB_lower"] = bb.bollinger_lband()

    df["Volume_SMA"]   = vol.astype(float).rolling(p["volume_sma"]).mean()
    df["Volume_ratio"] = vol / df["Volume_SMA"]

    df["Returns"]    = close.pct_change()
    df["Volatility"] = df["Returns"].rolling(20).std()

    return df


def _signal_sma_cross(df: pd.DataFrame) -> pd.Series:
    sig = pd.Series("HOLD", index=df.index)
    fast_above = df["SMA_fast"] > df["SMA_slow"]
    cross_up   = fast_above & ~fast_above.shift(1).fillna(False)
    cross_down = ~fast_above & fast_above.shift(1).fillna(False)
    sig[cross_up]   = "BUY"
    sig[cross_down] = "SELL"
    return sig


def _signal_rsi(df: pd.DataFrame, params: dict) -> pd.Series:
    sig = pd.Series("HOLD", index=df.index)
    rsi = df["RSI"]
    ob  = params["rsi_overbought"]
    os_ = params["rsi_oversold"]
    sig[(rsi > os_) & (rsi.shift(1) <= os_)] = "BUY"
    sig[(rsi < ob)  & (rsi.shift(1) >= ob)]  = "SELL"
    return sig


def _signal_macd(df: pd.DataFrame) -> pd.Series:
    sig = pd.Series("HOLD", index=df.index)
    macd_above = df["MACD"] > df["MACD_signal"]
    sig[macd_above & ~macd_above.shift(1).fillna(False)]  = "BUY"
    sig[~macd_above & macd_above.shift(1).fillna(False)]  = "SELL"
    return sig


def _signal_bollinger(df: pd.DataFrame) -> pd.Series:
    sig = pd.Series("HOLD", index=df.index)
    sig[df["Close"] < df["BB_lower"]] = "BUY"
    sig[df["Close"] > df["BB_upper"]] = "SELL"
    return sig


def _signal_combined(df: pd.DataFrame, params: dict) -> pd.Series:
    votes = pd.DataFrame({
        "sma":  _signal_sma_cross(df),
        "rsi":  _signal_rsi(df, params),
        "macd": _signal_macd(df),
        "bb":   _signal_bollinger(df),
    })
    buy_votes  = (votes == "BUY").sum(axis=1)
    sell_votes = (votes == "SELL").sum(axis=1)
    sig = pd.Series("HOLD", index=df.index)
    sig[(buy_votes >= 2)  & (sell_votes == 0)] = "BUY"
    sig[(sell_votes >= 2) & (buy_votes == 0)]  = "SELL"
    return sig


def _apply_volume_filter(sig: pd.Series, df: pd.DataFrame) -> pd.Series:
    if "Volume_ratio" not in df.columns:
        return sig
    sig = sig.copy()
    sig[(sig != "HOLD") & (df["Volume_ratio"] < 1.0)] = "HOLD"
    return sig


def get_signal(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    p = {**DEFAULT_PARAMS, **(params or {})}
    df = add_indicators(df, p)

    strategy = p["strategy"]
    if strategy == "sma_cross":
        sig = _signal_sma_cross(df)
    elif strategy == "rsi":
        sig = _signal_rsi(df, p)
    elif strategy == "macd":
        sig = _signal_macd(df)
    elif strategy == "bollinger":
        sig = _signal_bollinger(df)
    elif strategy == "combined":
        sig = _signal_combined(df, p)
    else:
        raise ValueError(f"Unknown strategy '{strategy}'.")

    if p.get("require_volume"):
        sig = _apply_volume_filter(sig, df)

    df["Signal"] = sig
    return df


def latest_signal(ticker: str, params: dict = None) -> dict:
    from data import fetch_stock
    df = fetch_stock(ticker)
    df = get_signal(df, params)
    row = df.iloc[-1]
    return {
        "ticker":       ticker.upper(),
        "date":         df.index[-1].date(),
        "signal":       row["Signal"],
        "close":        round(float(row["Close"]), 2),
        "rsi":          round(float(row["RSI"]), 2) if pd.notna(row.get("RSI")) else None,
        "sma_fast":     round(float(row["SMA_fast"]), 2) if pd.notna(row.get("SMA_fast")) else None,
        "sma_slow":     round(float(row["SMA_slow"]), 2) if pd.notna(row.get("SMA_slow")) else None,
        "macd":         round(float(row["MACD"]), 4) if pd.notna(row.get("MACD")) else None,
        "volume_ratio": round(float(row["Volume_ratio"]), 2) if pd.notna(row.get("Volume_ratio")) else None,
    }


def signal_summary(df: pd.DataFrame) -> pd.DataFrame:
    if "Signal" not in df.columns:
        raise ValueError("Run get_signal() first.")
    cols = ["Close", "RSI", "SMA_fast", "SMA_slow", "MACD", "Volume_ratio", "Signal"]
    available = [c for c in cols if c in df.columns]
    return df[df["Signal"] != "HOLD"][available]


if __name__ == "__main__":
    from data import fetch_stock

    print("=== Signals for AAPL ===\n")
    df = get_signal(fetch_stock("AAPL", period="2y"))
    trades = signal_summary(df)
    print(f"Total signals: {len(trades)}  "
          f"({(trades['Signal']=='BUY').sum()} BUY, "
          f"{(trades['Signal']=='SELL').sum()} SELL)\n")
    print(trades.tail(10).to_string())

    print("\n=== Latest signal ===")
    result = latest_signal("AAPL")
    for k, v in result.items():
        print(f"  {k}: {v}")