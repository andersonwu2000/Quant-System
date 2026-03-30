"""TWSE/TPEX OpenAPI provider — daily full-market snapshots.

Fetches all stocks in a single request (no per-symbol rate limit concern).
Only provides the latest trading day's data — for historical backfill, use FinMind.

Endpoints used:
  TWSE: https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
  TPEX: https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes
  Institutional: https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date=YYYYMMDD
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Rate limit: be gentle even with OpenAPI
_MIN_REQUEST_INTERVAL = 1.0  # seconds between requests
_last_request_time = 0.0


def _throttle() -> None:
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.monotonic()


def _safe_float(val: str | Any) -> float:
    """Convert string to float, handling commas and dashes."""
    if val is None or val == "" or val == "--" or val == "---":
        return 0.0
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


# ── TWSE (上市) ──────────────────────────────────────────────────────

def fetch_twse_daily_all() -> pd.DataFrame:
    """Fetch today's full-market OHLCV from TWSE OpenAPI.

    Returns DataFrame with columns: symbol, date, open, high, low, close, volume
    """
    import requests

    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    _throttle()

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("TWSE OpenAPI fetch failed: %s", e)
        return pd.DataFrame()

    if not data:
        logger.warning("TWSE OpenAPI returned empty data")
        return pd.DataFrame()

    rows = []
    for item in data:
        code = item.get("Code", "")
        if not code:
            continue

        # Date format: ROC year YYYMMDD → convert to ISO
        roc_date = item.get("Date", "")
        try:
            roc_year = int(roc_date[:3]) if len(roc_date) >= 7 else int(roc_date[:2])
            iso_date = f"{roc_year + 1911}-{roc_date[-4:-2]}-{roc_date[-2:]}"
        except (ValueError, IndexError):
            continue

        o = _safe_float(item.get("OpeningPrice"))
        h = _safe_float(item.get("HighestPrice"))
        lo = _safe_float(item.get("LowestPrice"))
        c = _safe_float(item.get("ClosingPrice"))
        v = _safe_float(item.get("TradeVolume"))

        if o <= 0 or c <= 0:
            continue

        symbol = f"{code}.TW"
        rows.append({
            "symbol": symbol,
            "date": iso_date,
            "open": o,
            "high": h,
            "low": lo,
            "close": c,
            "volume": v,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    logger.info("TWSE OpenAPI: fetched %d stocks for %s", len(df), df["date"].iloc[0])
    return df


# ── TPEX (上櫃) ──────────────────────────────────────────────────────

def fetch_tpex_daily_all() -> pd.DataFrame:
    """Fetch today's full-market OHLCV from TPEX OpenAPI.

    Returns DataFrame with columns: symbol, date, open, high, low, close, volume
    """
    import requests

    url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
    _throttle()

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("TPEX OpenAPI fetch failed: %s", e)
        return pd.DataFrame()

    if not data:
        logger.warning("TPEX OpenAPI returned empty data")
        return pd.DataFrame()

    rows = []
    for item in data:
        code = item.get("SecuritiesCompanyCode", "")
        if not code:
            continue

        trade_date = item.get("Date", "")
        # TPEX date format: YYYY/MM/DD or YYYY-MM-DD
        try:
            iso_date = trade_date.replace("/", "-")
            # Validate
            datetime.strptime(iso_date, "%Y-%m-%d")
        except (ValueError, AttributeError):
            continue

        o = _safe_float(item.get("Open"))
        h = _safe_float(item.get("High"))
        lo = _safe_float(item.get("Low"))
        c = _safe_float(item.get("Close"))
        v = _safe_float(item.get("TradingShares"))

        if o <= 0 or c <= 0:
            continue

        # TPEX stocks use .TWO suffix but our system uses .TW for simplicity
        symbol = f"{code}.TW"
        rows.append({
            "symbol": symbol,
            "date": iso_date,
            "open": o,
            "high": h,
            "low": lo,
            "close": c,
            "volume": v,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    logger.info("TPEX OpenAPI: fetched %d stocks for %s", len(df), df["date"].iloc[0])
    return df


# ── TWSE Institutional (三大法人) ────────────────────────────────────

def fetch_twse_institutional(trade_date: date | None = None) -> pd.DataFrame:
    """Fetch institutional investor buy/sell data from TWSE.

    Uses the traditional endpoint (not OpenAPI) because it provides per-stock detail.
    Rate limit: 2s minimum between requests.

    Returns DataFrame with columns:
        symbol, date, foreign_net, trust_net, dealer_net, total_net
    """
    import requests

    if trade_date is None:
        trade_date = date.today()

    date_str = trade_date.strftime("%Y%m%d")
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date_str}"

    # TWSE traditional endpoint needs longer delay
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < 2.0:
        time.sleep(2.0 - elapsed)
    _last_request_time = time.monotonic()

    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        logger.error("TWSE institutional fetch failed for %s: %s", date_str, e)
        return pd.DataFrame()

    if payload.get("stat") != "OK" or "data" not in payload:
        logger.debug("TWSE institutional: no data for %s", date_str)
        return pd.DataFrame()

    # Fields: [證券代號, 證券名稱, 外資買, 外資賣, 外資淨, ..., 投信買, 投信賣, 投信淨, ..., 三大法人淨]
    # Indices: 0=code, 2=foreign_buy, 3=foreign_sell, 4=foreign_net,
    #          8=trust_buy, 9=trust_sell, 10=trust_net,
    #          11=dealer_net, 18=total_net
    rows = []
    for record in payload["data"]:
        try:
            code = record[0].strip().replace('"', '')
            if not code or not code[0].isdigit():
                continue

            foreign_net = _safe_float(record[4])
            trust_net = _safe_float(record[10])
            dealer_net = _safe_float(record[11])
            total_net = _safe_float(record[18])

            rows.append({
                "symbol": f"{code}.TW",
                "date": trade_date.isoformat(),
                "foreign_net": foreign_net,
                "trust_net": trust_net,
                "dealer_net": dealer_net,
                "total_net": total_net,
            })
        except (IndexError, ValueError):
            continue

    df = pd.DataFrame(rows)
    if not df.empty:
        logger.info("TWSE institutional: fetched %d stocks for %s", len(df), date_str)
    return df


# ── Unified fetch ────────────────────────────────────────────────────

def fetch_all_daily() -> pd.DataFrame:
    """Fetch TWSE + TPEX combined daily OHLCV.

    Returns single DataFrame with all stocks. One API call per exchange.
    """
    twse = fetch_twse_daily_all()
    tpex = fetch_tpex_daily_all()

    parts = [df for df in [twse, tpex] if not df.empty]
    if not parts:
        return pd.DataFrame()

    combined = pd.concat(parts, ignore_index=True)
    logger.info("TWSE+TPEX combined: %d stocks", len(combined))
    return combined
