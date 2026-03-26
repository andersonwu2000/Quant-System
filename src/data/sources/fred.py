"""
FRED 宏觀經濟數據源 — 透過 FRED API 取得美國宏觀數據。

支援兩種模式：
1. fredapi 套件（已安裝時優先使用）
2. 直接 HTTP 請求（fallback）

所有數據有 Parquet 磁碟快取以減少 API 呼叫。
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# 常用 FRED 系列定義
FRED_SERIES: dict[str, dict[str, str]] = {
    "fed_funds": {"id": "FEDFUNDS", "name": "聯邦基金利率", "freq": "monthly"},
    "treasury_10y": {"id": "DGS10", "name": "10年期公債殖利率", "freq": "daily"},
    "treasury_2y": {"id": "DGS2", "name": "2年期公債殖利率", "freq": "daily"},
    "yield_spread_10y2y": {"id": "T10Y2Y", "name": "10-2年利差", "freq": "daily"},
    "cpi": {"id": "CPIAUCSL", "name": "消費者物價指數", "freq": "monthly"},
    "unemployment": {"id": "UNRATE", "name": "失業率", "freq": "monthly"},
    "vix": {"id": "VIXCLS", "name": "VIX 波動率指數", "freq": "daily"},
    "credit_spread": {"id": "BAAFFM", "name": "BAA 信用利差", "freq": "monthly"},
    "pmi": {"id": "MANEMP", "name": "製造業就業", "freq": "monthly"},
}

_CACHE_DIR = Path(".cache/fred")


class FredDataSource:
    """FRED 宏觀數據源。"""

    def __init__(self, api_key: str | None = None, cache_dir: Path | None = None):
        self._api_key = api_key
        self._cache_dir = cache_dir or _CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get_series(
        self,
        series_id: str,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.Series:
        """
        取得單一 FRED 時間序列。

        Args:
            series_id: FRED 系列 ID (e.g., "DGS10")
            start: 開始日期 "YYYY-MM-DD"
            end: 結束日期 "YYYY-MM-DD"

        Returns:
            pd.Series with DatetimeIndex, values=float
        """
        # 嘗試快取
        cached = self._load_cache(series_id, start, end)
        if cached is not None:
            return cached

        # 下載
        data = self._fetch(series_id, start, end)
        if data is not None and not data.empty:
            self._save_cache(series_id, start, end, data)
        return data if data is not None else pd.Series(dtype=float)

    def get_macro_panel(
        self,
        start: str | None = None,
        end: str | None = None,
        series_keys: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        取得多個宏觀序列，合併為 DataFrame。

        Args:
            series_keys: FRED_SERIES 中的 key 列表 (None=全部)

        Returns:
            DataFrame, index=date, columns=series key names
        """
        keys = series_keys or list(FRED_SERIES.keys())
        result: dict[str, pd.Series] = {}
        for key in keys:
            if key not in FRED_SERIES:
                logger.warning("Unknown FRED series key: %s", key)
                continue
            sid = FRED_SERIES[key]["id"]
            s = self.get_series(sid, start, end)
            if not s.empty:
                result[key] = s
        if not result:
            return pd.DataFrame()
        df = pd.DataFrame(result)
        df = df.sort_index().ffill(limit=66)  # 前填（月度→日度，上限 66 交易日 ≈ 3 個月）
        return df

    # ── 內部方法 ─────────────────────────────────────────

    def _fetch(self, series_id: str, start: str | None, end: str | None) -> pd.Series | None:
        """嘗試用 fredapi，fallback 到 HTTP。"""
        # 方式 1: fredapi
        if self._api_key:
            try:
                return self._fetch_fredapi(series_id, start, end)
            except ImportError:
                pass
            except Exception:
                logger.debug("fredapi fetch failed for %s", series_id, exc_info=True)

        # 方式 2: HTTP (不需要 api_key，但有速率限制)
        try:
            return self._fetch_http(series_id, start, end)
        except Exception:
            logger.warning("Failed to fetch FRED series %s", series_id, exc_info=True)
            return None

    def _fetch_fredapi(self, series_id: str, start: str | None, end: str | None) -> pd.Series:
        from fredapi import Fred  # type: ignore[import-not-found]

        fred = Fred(api_key=self._api_key)
        data = fred.get_series(series_id, observation_start=start, observation_end=end)
        if data is not None:
            data = data.dropna()
            data.index = pd.to_datetime(data.index)
            if data.index.tz is not None:
                data.index = data.index.tz_localize(None)
        return data if data is not None else pd.Series(dtype=float)

    def _fetch_http(self, series_id: str, start: str | None, end: str | None) -> pd.Series:
        import httpx

        url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
        params: dict[str, str] = {"id": series_id}
        if start:
            params["cosd"] = start
        if end:
            params["coed"] = end

        resp = httpx.get(url, params=params, timeout=30)
        resp.raise_for_status()

        from io import StringIO

        df = pd.read_csv(StringIO(resp.text), parse_dates=["DATE"], index_col="DATE")
        col = df.columns[0]
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        s.index.name = None
        logger.info("Fetched FRED %s via HTTP: %d observations", series_id, len(s))
        return s

    def _cache_key(self, series_id: str, start: str | None, end: str | None) -> str:
        raw = f"{series_id}_{start}_{end}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def _load_cache(self, series_id: str, start: str | None, end: str | None) -> pd.Series | None:
        key = self._cache_key(series_id, start, end)
        path = self._cache_dir / f"{series_id}_{key}.parquet"
        if not path.exists():
            return None
        # 只用 24 小時以內的快取
        import os
        import time

        age = time.time() - os.path.getmtime(path)
        if age > 86400:
            return None
        try:
            df = pd.read_parquet(path)
            # 確保 index 是 DatetimeIndex（parquet 反序列化後可能退化為 numpy array）
            if not df.empty and not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            return df.iloc[:, 0]
        except Exception:
            return None

    def _save_cache(self, series_id: str, start: str | None, end: str | None, data: pd.Series) -> None:
        key = self._cache_key(series_id, start, end)
        path = self._cache_dir / f"{series_id}_{key}.parquet"
        try:
            df = data.to_frame(name=series_id)
            df.to_parquet(path)
        except Exception:
            logger.debug("Failed to cache FRED %s", series_id, exc_info=True)
