"""Market-data provider seam.

A thin `PriceProvider` Protocol decouples the cache from the vendor.
yfinance is the v1 implementation; Tiingo can drop in later behind the
same interface. CAVEAT: auto_adjust=True returns back-adjusted OHLC, i.e.
values restated for later splits/dividends — a subtle lookahead. We keep
it (free, simple) and document it; downstream code must not pretend these
were the prices known on the bar's date.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd
import yfinance as yf

_LONG_COLUMNS = ["ticker", "date", "open", "high", "low", "close", "volume"]


@runtime_checkable
class PriceProvider(Protocol):
    def fetch(self, tickers: list[str], start: str, end: str) -> pd.DataFrame:
        """Return long-form daily bars with columns: ticker, date, open,
        high, low, close, volume."""
        ...


class YFinanceProvider:
    """yfinance-backed provider returning normalized long-form bars."""

    def fetch(self, tickers: list[str], start: str, end: str) -> pd.DataFrame:
        if not tickers:
            raise ValueError("tickers must not be empty")
        raw = yf.download(
            tickers,
            start=start,
            end=end,
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            progress=False,
            threads=True,
        )
        return self._to_long(raw, tickers)

    @staticmethod
    def _to_long(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame(columns=_LONG_COLUMNS)
        rename = {"Open": "open", "High": "high", "Low": "low",
                  "Close": "close", "Volume": "volume"}
        parts: list[pd.DataFrame] = []
        for ticker in tickers:
            if ticker not in raw.columns.get_level_values(0):
                continue
            sub = raw[ticker].rename(columns=rename).dropna(how="all")
            sub = sub.reset_index().rename(columns={"Date": "date", "index": "date"})
            sub.insert(0, "ticker", ticker)
            parts.append(sub[_LONG_COLUMNS])
        if not parts:
            return pd.DataFrame(columns=_LONG_COLUMNS)
        out = pd.concat(parts, ignore_index=True)
        out["date"] = pd.to_datetime(out["date"])
        return out.sort_values(["ticker", "date"]).reset_index(drop=True)
