"""
data.py — Stock price fetching and caching
==========================================
Fetches OHLCV data from Yahoo Finance via yfinance.
Caches results to CSV so repeat runs don't hit the network.

Usage:
    from data import fetch_stock, fetch_multiple, get_latest_price

Install dependencies:
    pip install yfinance pandas
"""

import os
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

# ── Configuration ─────────────────────────────────────────────────────────────

CACHE_DIR = Path("data/cache")
CACHE_MAX_AGE_HOURS = 24
DEFAULT_PERIOD = "2y"
DEFAULT_INTERVAL = "1d"

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _cache_path(ticker: str, period: str, interval: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{ticker.upper()}_{period}_{interval}.csv"


def _is_stale(path: Path) -> bool:
    if not path.exists():
        return True
    age = time.time() - path.stat().st_mtime
    return age > CACHE_MAX_AGE_HOURS * 3600


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.strip().replace(" ", "_") for c in df.columns]
    df.index.name = "Date"
    df = df[~df.index.duplicated(keep="last")]
    df = df.dropna(subset=["Close"])
    df = df.sort_index()
    return df

# ── Core fetch ────────────────────────────────────────────────────────────────

def fetch_stock(
    ticker: str,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    force_refresh: bool = False,
) -> pd.DataFrame:
    ticker = ticker.upper()
    path = _cache_path(ticker, period, interval)

    if not force_refresh and not _is_stale(path):
        log.info("Cache hit  → %s (%s, %s)", ticker, period, interval)
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index, utc=False)
        return _clean(df)

    log.info("Downloading → %s (%s, %s) ...", ticker, period, interval)
    raw = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )

    if raw.empty:
        raise ValueError(
            f"No data returned for '{ticker}'. "
            "Check the ticker symbol and try again."
        )

    df = _clean(raw)
    df.to_csv(path)
    log.info("Saved cache → %s", path)
    return df


def fetch_multiple(
    tickers: list[str],
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    force_refresh: bool = False,
) -> dict[str, pd.DataFrame]:
    results = {}
    for ticker in tickers:
        try:
            results[ticker.upper()] = fetch_stock(
                ticker, period, interval, force_refresh
            )
        except ValueError as e:
            log.warning("Skipping %s — %s", ticker, e)
    return results


def get_latest_price(ticker: str) -> float:
    df = fetch_stock(ticker, period="5d", interval="1d")
    return float(df["Close"].iloc[-1])


def get_price_range(
    ticker: str,
    start: str,
    end: str | None = None,
    interval: str = DEFAULT_INTERVAL,
) -> pd.DataFrame:
    ticker = ticker.upper()
    end = end or datetime.today().strftime("%Y-%m-%d")
    log.info("Fetching %s  %s → %s", ticker, start, end)

    raw = yf.download(
        ticker,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )

    if raw.empty:
        raise ValueError(f"No data for '{ticker}' between {start} and {end}.")

    return _clean(raw)


def get_fundamentals(ticker: str) -> dict:
    info = yf.Ticker(ticker.upper()).info
    keys = [
        "shortName", "sector", "industry",
        "marketCap", "trailingPE", "forwardPE",
        "trailingEps", "dividendYield",
        "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
        "averageVolume", "beta",
    ]
    return {k: info.get(k) for k in keys}


def clear_cache(ticker: str | None = None) -> None:
    if not CACHE_DIR.exists():
        return
    pattern = f"{ticker.upper()}_*.csv" if ticker else "*.csv"
    deleted = 0
    for f in CACHE_DIR.glob(pattern):
        f.unlink()
        deleted += 1
    log.info("Cleared %d cache file(s).", deleted)


# ── Quick smoke test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Single ticker ===")
    df = fetch_stock("AAPL", period="1y")
    print(df.tail(3))
    print(f"\nColumns : {list(df.columns)}")
    print(f"Rows    : {len(df)}")
    print(f"Date range: {df.index[0].date()} → {df.index[-1].date()}")

    print("\n=== Latest price ===")
    price = get_latest_price("AAPL")
    print(f"AAPL latest close: ${price:.2f}")

    print("\n=== Multiple tickers ===")
    bundle = fetch_multiple(["MSFT", "SPY", "QQQ"], period="6mo")
    for sym, d in bundle.items():
        print(f"  {sym}: {len(d)} rows, latest close ${d['Close'].iloc[-1]:.2f}")

    print("\n=== Fundamentals ===")
    f = get_fundamentals("AAPL")
    for k, v in f.items():
        print(f"  {k}: {v}")