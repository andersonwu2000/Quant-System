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


def _safe_float(val: str | Any, allow_nan: bool = False) -> float:
    """Convert string to float, handling commas and dashes.

    Args:
        allow_nan: If True, return NaN for missing/invalid values (use for
                   fields where 0.0 is a legitimate value, e.g. net buy/sell).
                   If False, return 0.0 (use for OHLCV where 0 means invalid).
    """
    if val is None or val == "" or val == "--" or val == "---":
        return float("nan") if allow_nan else 0.0
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return float("nan") if allow_nan else 0.0


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

            foreign_net = _safe_float(record[4], allow_nan=True)
            trust_net = _safe_float(record[10], allow_nan=True)
            dealer_net = _safe_float(record[11], allow_nan=True)
            total_net = _safe_float(record[18], allow_nan=True)

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


# ── TWSE PER/PBR/Dividend Yield (本益比/股價淨值比/殖利率) ───────────

def fetch_twse_per_all() -> pd.DataFrame:
    """Fetch today's PER/PBR/dividend yield for all TWSE stocks.

    Returns DataFrame: symbol, date, per, pbr, dividend_yield
    """
    import requests

    url = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
    _throttle()

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("TWSE PER fetch failed: %s", e)
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    rows = []
    for item in data:
        code = item.get("Code", "")
        if not code or not code[0].isdigit():
            continue

        roc_date = item.get("Date", "")
        try:
            roc_year = int(roc_date[:3]) if len(roc_date) >= 7 else int(roc_date[:2])
            iso_date = f"{roc_year + 1911}-{roc_date[-4:-2]}-{roc_date[-2:]}"
        except (ValueError, IndexError):
            continue

        per = _safe_float(item.get("PEratio"))
        pbr = _safe_float(item.get("PBratio"))
        dy = _safe_float(item.get("DividendYield"))

        rows.append({
            "symbol": f"{code}.TW",
            "date": iso_date,
            "PER": per if per > 0 else None,
            "PBR": pbr if pbr > 0 else None,
            "dividend_yield": dy if dy > 0 else None,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        logger.info("TWSE PER: fetched %d stocks for %s", len(df), df["date"].iloc[0])
    return df


def fetch_tpex_per_all() -> pd.DataFrame:
    """Fetch today's PER/PBR/dividend yield for all TPEX (OTC) stocks.

    Returns DataFrame: symbol, date, per, pbr, dividend_yield
    """
    import requests

    url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis"
    _throttle()

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("TPEX PER fetch failed: %s", e)
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    rows = []
    for item in data:
        code = item.get("SecuritiesCompanyCode", "")
        if not code or not code[0].isdigit():
            continue

        roc_date = item.get("Date", "")
        try:
            roc_year = int(roc_date[:3]) if len(roc_date) >= 7 else int(roc_date[:2])
            iso_date = f"{roc_year + 1911}-{roc_date[-4:-2]}-{roc_date[-2:]}"
        except (ValueError, IndexError):
            continue

        per = _safe_float(item.get("PriceEarningRatio"))
        dy = _safe_float(item.get("YieldRatio"))

        rows.append({
            "symbol": f"{code}.TWO",
            "date": iso_date,
            "PER": per if per > 0 else None,
            "PBR": None,  # TPEX doesn't provide PBR in this endpoint
            "dividend_yield": dy if dy > 0 else None,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        logger.info("TPEX PER: fetched %d stocks for %s", len(df), df["date"].iloc[0])
    return df


# ── TWSE Margin Trading (融資融券) ──────────────────────────────────

def fetch_twse_margin_all() -> pd.DataFrame:
    """Fetch today's margin trading data for all TWSE stocks.

    Returns DataFrame: symbol, date, margin_buy, margin_sell, margin_balance,
                       short_buy, short_sell, short_balance
    """
    import requests

    url = "https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN"
    _throttle()

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("TWSE margin fetch failed: %s", e)
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    rows = []
    for item in data:
        code = item.get("\u80a1\u7968\u4ee3\u865f", "").strip()  # 股票代號
        if not code or not code[0].isdigit():
            continue

        rows.append({
            "symbol": f"{code}.TW",
            "date": date.today().isoformat(),
            "margin_buy": _safe_float(item.get("\u8cc7\u8cb7\u9032", 0)),       # 資買進
            "margin_sell": _safe_float(item.get("\u8cc7\u8ce3\u51fa", 0)),      # 資賣出
            "margin_cash_repay": _safe_float(item.get("\u8cc8\u73fe\u91d1\u511f\u9084", 0)),  # 資現金償還
            "margin_balance": _safe_float(item.get("\u8cc8\u524d\u65e5\u9918\u984d", 0)),     # 資前日餘額
            "short_sell": _safe_float(item.get("\u5238\u8ce3\u51fa", 0)),       # 券賣出
            "short_buy": _safe_float(item.get("\u5238\u8cb7\u9032", 0)),        # 券買進
            "short_balance": _safe_float(item.get("\u5238\u524d\u65e5\u9918\u984d", 0)),      # 券前日餘額
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        logger.info("TWSE margin: fetched %d stocks", len(df))
    return df


# ── TWSE Market Summary (大盤成交統計) ──────────────────────────────

def fetch_twse_market_summary() -> pd.DataFrame:
    """Fetch TWSE market-wide trading summary (TAIEX, volume, etc.).

    Returns DataFrame: date, taiex, volume, value, transactions, change
    """
    import requests

    url = "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK"
    _throttle()

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("TWSE market summary fetch failed: %s", e)
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    rows = []
    for item in data:
        roc_date = item.get("Date", "")
        try:
            # Format: "1150331" (ROC year + MMDD) or "115/03/31"
            if "/" in roc_date:
                parts = roc_date.split("/")
                iso_date = f"{int(parts[0]) + 1911}-{parts[1]}-{parts[2]}"
            elif len(roc_date) == 7:
                roc_year = int(roc_date[:3])
                iso_date = f"{roc_year + 1911}-{roc_date[3:5]}-{roc_date[5:7]}"
            else:
                continue
        except (ValueError, IndexError):
            continue

        rows.append({
            "date": iso_date,
            "taiex": _safe_float(item.get("TAIEX")),
            "volume": _safe_float(item.get("TradeVolume")),
            "value": _safe_float(item.get("TradeValue")),
            "transactions": _safe_float(item.get("Transaction")),
            "change": _safe_float(item.get("Change")),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        logger.info("TWSE market summary: %d days", len(df))
    return df


# ── Combined PER/Margin fetchers ────────────────────────────────────

def fetch_all_per() -> pd.DataFrame:
    """Fetch TWSE + TPEX combined PER/PBR/dividend_yield."""
    twse = fetch_twse_per_all()
    tpex = fetch_tpex_per_all()
    parts = [df for df in [twse, tpex] if not df.empty]
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


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
