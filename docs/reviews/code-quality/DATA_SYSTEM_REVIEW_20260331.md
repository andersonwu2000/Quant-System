# Data System Code Review — 2026-03-31

> Scope: `src/data/` 全部模組（registry, data_catalog, refresh, quality_gate, schemas, master, cli, sources/）
> Method: 逐檔閱讀 + 交叉比對整合點

---

## Summary

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | 1     | Fixed  |
| HIGH     | 4     | 3 Fixed, 1 Won't Fix |
| MEDIUM   | 4     | 2 Fixed, 2 Won't Fix |
| LOW      | 3     | Won't Fix |

---

## CRITICAL

### D1. registry.py — `_source_name_to_dir` 缺少 finlab 映射 ✅ FIXED

```python
def _source_name_to_dir(source: str) -> Path:
    return {"yahoo": YAHOO_DIR, "finmind": FINMIND_DIR, "twse": TWSE_DIR}[source]
```

`FINLAB_DIR` 已定義（line 23）且被 `DataCatalog` 使用，但 `_source_name_to_dir` 和 `_dir_to_source_name` 都沒有 finlab 映射。呼叫 `write_path(..., source="finlab")` 會 KeyError。

**Fix:** 加入 finlab 映射到兩個函式。

---

## HIGH

### D2. refresh.py — 未使用的 import（YAHOO_DIR, FINMIND_DIR）✅ FIXED

Line 18 import 了 `YAHOO_DIR, FINMIND_DIR` 但全檔未使用。

**Fix:** 移除。

### D3. quality_gate.py — L3 sanity check 未驗證 last_close > 0 ✅ FIXED

```python
if prev_row["close"] > 0:
    daily_ret = abs(last_row["close"] / prev_row["close"] - 1)
```

`last_row["close"]` 可能是 0 或 NaN，計算出的 `daily_ret` 會是 1.0（100% 跌幅）觸發誤報，或 NaN 靜默跳過。

**Fix:** 加 `last_row["close"] > 0` 檢查。

### D4. cli.py — status 抽樣取前 50 檔有偏差 ✅ FIXED

```python
sample = files[:50] if len(files) > 50 else files
```

`glob` 回傳順序不保證，前 50 可能全是舊檔。freshest_date 會被低估。

**Fix:** 按修改時間倒序取前 50。

### D5. refresh.py — fundamental 硬編碼 source="finmind" — Won't Fix

Line 272 hardcodes `source="finmind"`。未來加 TWSE 財報時需改。

**判定：** 目前只有 FinMind 提供 fundamental，hardcode 正確。加新 source 時會自然改。過早抽象無益。

---

## MEDIUM

### D6. data_catalog.py — `bare` 計算重複寫，未用 strip_tw_suffix ✅ FIXED

3 處用 `symbol.replace(".TW", "").replace(".TWO", "")`（line 56, 119, 314），和 `finmind_common.strip_tw_suffix()` 重複且缺少 `.upper()` 安全檢查。

**Fix:** import 並使用 `strip_tw_suffix()`。

### D7. quality_gate.py:73 — metadata 讀取異常靜默吞掉 ✅ FIXED

`_read_last_date_fast` 的 `except Exception: pass` 吞掉所有錯誤，debug 困難。

**Fix:** 加 `logger.debug` 記錄異常。

### D8. refresh.py — 日期格式不一致（price 用 index，fundamental 用 date column）— Won't Fix

Price merge 後是 DatetimeIndex，fundamental 保持 "date" column。DataCatalog.get() 已處理兩種格式。

**判定：** FinMind API 回傳的 fundamental 天生帶 "date" column，強制轉 index 會破壞多 date column 的資料（如 revenue 有 date + announcement_date）。現行設計正確。

### D9. twse.py — ROC 日期解析無驗證 — Won't Fix

Line 85-86 用字串切片解析民國日期。格式不對會靜默產出錯誤 ISO 日期。

**判定：** TWSE OpenAPI 回傳格式穩定（10+ 年未變），加驗證的收益太低。若格式真的變了，下游 schema validation 會攔截。

---

## LOW（不修）

### D10. master.py — universe_at() 用 TEXT 比較 ISO 日期

SQLite 裡 listed_date/delisted_date 是 TEXT，`<= as_of.isoformat()` 靠字典序比較。ISO 8601 的字典序等於時間序，所以正確。但如果有人存非 ISO 格式就會壞。

**判定：** 所有寫入路徑都用 `.isoformat()`，風險極低。

### D11. schemas.py — _load_upload_dates() 找不到檔案時無 warning

回傳空 DataFrame，pit_filter 靜默 fallback 到 conservative deadline。

**判定：** FinLab 數據是可選的，沒有時用保守估計是正確行為。加 warning 會在每次沒裝 FinLab 的環境下刷屏。

### D12. catalog_feed.py — 回傳不完整 OHLCV 無錯誤

OHLCV 缺欄位時只 debug log，仍回傳。

**判定：** 呼叫端（backtest engine）已有 column 檢查。CatalogFeed 是 thin wrapper，不應重複驗證。

---

## 審批記錄

| # | 判定 | 修法 |
|---|------|------|
| D1 | ✅ Fixed | registry.py 加 finlab 到兩個映射函式 |
| D2 | ✅ Fixed | refresh.py 移除未用 import |
| D3 | ✅ Fixed | quality_gate.py 加 last_close > 0 檢查 |
| D4 | ✅ Fixed | cli.py 按 st_mtime 倒序抽樣 |
| D5 | Won't Fix | 目前 hardcode 正確 |
| D6 | ✅ Fixed | data_catalog.py 用 strip_tw_suffix() |
| D7 | ✅ Fixed | quality_gate.py 加 debug log |
| D8 | Won't Fix | 兩種格式各有原因 |
| D9 | Won't Fix | TWSE 格式穩定 |
| D10 | Won't Fix | ISO 字典序 = 時間序 |
| D11 | Won't Fix | 保守 fallback 是正確行為 |
| D12 | Won't Fix | 驗證在 caller 做 |
