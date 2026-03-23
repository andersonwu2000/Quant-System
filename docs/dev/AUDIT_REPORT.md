# 量化交易系統 — 全面審計報告

**日期**: 2026-03-24
**範圍**: 全專案（Python 後端 + React Web + React Native Mobile + Shared Package）
**審計方法**: 靜態程式碼分析、架構審查、測試覆蓋率分析

---

## 目錄

1. [資料正確性](#1-資料正確性)
2. [回測可信度](#2-回測可信度)
3. [風險管理](#3-風險管理)
4. [安全性](#4-安全性)
5. [測試覆蓋](#5-測試覆蓋)
6. [效能](#6-效能)
7. [可觀測性](#7-可觀測性)
8. [總結與優先級](#8-總結與優先級)

---

## 1. 資料正確性

### 1.1 Look-Ahead Bias 防護

**狀態: 良好** | 風險: 低

系統實施多層防護，確保回測中不存在未來資料洩漏：

| 防護層 | 檔案 | 機制 |
|--------|------|------|
| Feed 層 | `src/data/feed.py:89-90` | `HistoricalFeed.get_bars()` 以 `df[df.index <= current_date]` 截斷 |
| Context 層 | `src/strategy/base.py:56-57` | `Context.bars()` 二次截斷至 `current_time` |
| Engine 層 | `src/backtest/engine.py:119` | 每根 bar 前呼叫 `feed.set_current_date(bar_date)` |
| 測試驗證 | `tests/unit/test_strategy.py:18-33` | `test_bars_truncated_by_current_time` 明確驗證 |

**潛在風險**: `Context.latest_price()` (`src/strategy/base.py:85`) 直接呼叫 `self._feed.get_latest_price(symbol)`，未顯式傳入 `current_time`。但因 feed 的 `_current_date` 已在策略執行前設定，實際上是安全的。

### 1.2 Survivorship Bias

**狀態: 已知但未防護** | 風險: 中

系統使用 Yahoo Finance 作為資料來源（`src/data/sources/yahoo.py:66-96`），僅能取得**目前仍在上市的標的**。已下市、被併購的股票不在資料集中。

- 回測引擎已輸出警告（`src/backtest/engine.py:78-83`）
- **影響**: 長期回測報酬率可能被高估 2-5%
- **緩解建議**: 使用 point-in-time 資料庫（Refinitiv、FactSet、TEJ）

### 1.3 資料缺漏處理

**狀態: 基本處理，存在隱患** | 風險: 中

| 問題 | 位置 | 說明 |
|------|------|------|
| NaN 靜默丟棄 | `src/data/sources/yahoo.py:117-118` | `df.dropna()` 無法區分「無資料」與「合法缺值」 |
| 價格前向填充 | `src/backtest/engine.py:268-269` | `self._price_matrix.ffill()` 會在停牌期間產生過時價格 |
| 成交量未填充 | `src/backtest/engine.py:272-276` | 正確做法，停牌日成交量為 NaN |

**風險情境**: 股票停牌 5 天，舊價格持續存在，策略可能產生錯誤信號。

### 1.4 股利與公司行動

**狀態: 隱式處理，未模擬現金流** | 風險: 中

- Yahoo Finance 的 `auto_adjust=True`（`src/data/sources/yahoo.py:92`）已將股價調整為除權息後價格
- **關鍵缺口**: 系統未模擬股利現金分配，投資組合不會收到股利收入
- **影響**: 高殖利率股票池的總報酬被低估約 1-3%/年
- 相關檔案：`src/execution/sim.py:58-133`、`src/execution/oms.py:58-105` — 僅處理買賣，無股利邏輯

### 1.5 時區處理

**狀態: 正確** | 風險: 低

所有資料統一轉換為 tz-naive UTC：
- `src/data/feed.py:64-66` — `HistoricalFeed.load()` 正規化
- `src/data/sources/yahoo.py:106-108` — `YahooFeed._download()` 正規化

### 1.6 資料品質檢查

**狀態: ✅ 已修復** | 風險: 低

`src/data/quality.py:33-109` 執行 7 項檢查（必要欄位、NaN、正價格、高低價一致性、成交量、時間單調性、價格跳空）：

- `QualityResult.suspect_dates` 收集 5σ 以上的價格跳變日期
- 回測引擎 `_load_data()` 對每個標的執行品質檢查，收集所有可疑日期
- 可疑日期在回測迭代中自動跳過，不產生交易信號

### 1.7 資料快取

**狀態: 雙層快取** | 風險: 低

| 層級 | 位置 | 機制 |
|------|------|------|
| 記憶體快取 | `src/data/sources/yahoo.py:33-56` | 每個 YahooFeed 實例的 `_cache` dict |
| 磁碟快取 | `src/data/sources/yahoo.py:126-156` | Parquet 檔案，TTL 24 小時 |

**注意事項**:
- 記憶體快取無上限，大量標的可能耗盡 RAM
- 歷史資料（如 2020 年）24 小時後重新下載，效率不佳
- 無 Yahoo Finance API rate limit 處理

---

## 2. 回測可信度

### 2.1 交易成本模擬

**狀態: 良好** | 風險: 低

`src/execution/sim.py:44-133` 實現完整交易成本模型：

- 滑價：買入加價、賣出減價（`slippage_bps` 可配置）
- 手續費：雙向收取（台股預設 0.1425%）
- 證交稅：僅賣方收取（台股預設 0.3%）
- 所有金額使用 `Decimal` 精度
- 成交量限制：單筆訂單不超過當日成交量 10%（`max_fill_pct_of_volume`）

### 2.2 再平衡假設

**狀態: 需注意** | 風險: 中

- 系統假設能以「當日收盤價 ± 滑價」成交
- 未考慮流動性不足導致的無法成交
- 成交量限制（10%）部分緩解此問題

### 2.3 樣本外驗證

**狀態: 未實作** | 風險: 中

- 無 Walk-Forward Analysis
- 無 Cross-Validation
- 無 Out-of-Sample / In-Sample 分割機制
- 回測比較功能已在前端實作（`CompareChart.tsx`、`CompareTable.tsx`），但僅限視覺比較

### 2.4 回測結果持久化

**狀態: ✅ 已修復** | 風險: 低

| 層級 | 狀態 |
|------|------|
| 後端 | `AppState.backtest_tasks` 記憶體快取（上限 50 筆）+ SQLite 持久化 |
| 前端 | `localStorage` 上限 20 筆，已剝離 `nav_series` 以節省空間 |
| 資料庫 | `backtest_results` 表自動儲存完成的回測結果 |
| API | `GET /backtest/history` 端點支援按策略篩選、分頁查詢 |

---

## 3. 風險管理

### 3.1 風控規則覆蓋

**狀態: 基本完備** | 風險: 中

`src/risk/rules.py` 實作 6 條規則：

| 規則 | 預設值 | 說明 |
|------|--------|------|
| `max_position_weight` | 10% NAV | 單一標的持倉上限 |
| `max_order_notional` | 10% NAV | 單筆訂單金額上限 |
| `daily_drawdown_limit` | 3% | 日內虧損上限 |
| `fat_finger_check` | ±5% | 價格偏差檢測 |
| `max_daily_trades` | 100 次/日 | 交易頻率上限 |
| `max_order_vs_adv` | 10% ADV | 訂單佔日均量比例 |

**✅ 已新增 `price_circuit_breaker` 規則**（預設 ±10%）：
- 偵測閃崩、漲跌停鎖死、異常跳空等極端行情
- 比較當前價與前收盤價，偏離超過閾值則拒絕下單
- 需 `MarketState.prev_close` 提供前收盤價

### 3.2 Kill Switch

**狀態: ✅ 已修復（背景監控）** | 風險: 中

**實作位置**: `src/risk/engine.py:119-131`、`src/api/routes/risk.py:61-77`、`src/api/app.py:146-161`

**觸發條件**: 日虧損 > 5%（硬編碼）

| 問題 | 嚴重度 | 狀態 |
|------|--------|------|
| 非即時監控 | ✅ 已修復 | 背景任務每 5 秒檢查一次，自動停止策略+取消訂單+WS 廣播告警 |
| 可被繞過 | ✅ 已修復 | 背景持續監控，無需提交訂單即可觸發 |
| 未強制平倉 | 中 | 觸發後僅停止策略和取消訂單，不主動清倉（需人工介入） |
| 狀態非持久化 | 低 | 重啟後重新計算當前回撤，影響有限 |

### 3.3 併發安全

**狀態: ✅ 已修復（訂單加鎖）** | 風險: 低

`src/api/state.py:34-36` 定義了 `mutation_lock`（asyncio.Lock）：

- ✅ `src/api/routes/orders.py:74-82` 的 `create_order()` 已在 `async with state.mutation_lock` 內執行風控檢查 + 訂單提交
- 剩餘注意事項：
  - `src/execution/oms.py:18-20` 的 OrderManager 使用普通 dict（但已被 mutation_lock 保護）
  - WebSocket 廣播（`src/api/ws.py:35-59`）在迭代連線列表時可能被併發修改

---

## 4. 安全性

### 4.1 認證機制

**狀態: 完善** | 風險: 低

| 機制 | 位置 | 說明 |
|------|------|------|
| JWT + HttpOnly Cookie | `src/api/routes/auth.py:31-40` | XSS 防護、SameSite=Lax |
| API Key 驗證 | `src/config.py:114-128` | 常數時間比較（`hmac.compare_digest`） |
| 密碼雜湊 | `src/api/password.py:9-24` | PBKDF2-SHA256，600k 迭代，16 byte salt |
| Token 撤銷 | `src/api/auth.py:123-134` | 透過 `token_valid_after` 時間戳 |
| 帳號鎖定 | `src/api/routes/auth.py:57-73` | 5 次失敗鎖定 15 分鐘 |

### 4.2 安全隱患

| 問題 | 嚴重度 | 位置 | 說明 |
|------|--------|------|------|
| CORS 方法過寬 | ✅ 已修復 | `src/api/app.py:79` | 已收窄為 `["GET","POST","PUT","DELETE","OPTIONS"]` |
| 預設密碼 | 中 | `src/config.py:61` | admin 預設密碼 `Admin1234`，且登入時輸出至日誌 |
| 後端無密碼強度驗證 | ✅ 已修復 | `src/api/password.py` | `validate_password()` ≥8字元、英數混合，auth/admin 路由皆驗證 |
| Dev 模式 WS 無認證 | 中 | `src/api/app.py:106-114` | `QUANT_ENV=dev` 時 WebSocket 跳過 token 驗證 |
| JWT Secret 預設值 | 低 | `src/config.py:62` | `change-me-in-production`，但有啟動檢查 |
| 登入端點未獨立限流 | ✅ 已修復 | `src/api/routes/auth.py` | 登入端點獨立限流 10 次/分鐘 |

### 4.3 審計日誌

**狀態: 基本實作，存在缺口** | 風險: 中

`src/api/middleware.py:24-50` 記錄所有 POST/PUT/DELETE 請求。

**已記錄**: 請求方法、路徑、狀態碼、耗時、使用者、IP
**未記錄**:
- 風控決策（訂單拒絕/通過）
- 登入/登出事件（僅在 auth 日誌，非集中審計）
- 讀取操作（查看投資組合、風控警報等）
- API Key 使用紀錄
- 請求/回應 body

**✅ 已修復**: `RiskEngine` 透過 `persist_fn` callback 將風控決策（拒絕/告警）持久化至 `risk_events_table`（`src/data/store.py:331-343`）。

---

## 5. 測試覆蓋

### 5.1 後端測試

**狀態: 良好** | 135+ 測試

| 模組 | 檔案 | 行數 | 覆蓋情況 |
|------|------|------|----------|
| 風控規則 | `tests/unit/test_risk.py` | 136 | 6 條規則全部有邊界測試 |
| 策略介面 | `tests/unit/test_strategy.py` | 156 | Context 截斷、Optimizer |
| 執行層 | `tests/unit/test_execution.py` | 160 | SimBroker、OMS |
| 因子庫 | `tests/unit/test_factors.py` | 108 | 5 個因子函數 |
| 策略回歸 | `tests/unit/test_new_strategies.py` | 260 | 7 策略：空資料、不足資料、權重約束 |
| 領域模型 | `tests/unit/test_models.py` | 142 | Instrument、Position、Portfolio |
| 設定 | `tests/unit/test_config.py` | 59 | 環境變數解析 |
| 研究工具 | `tests/unit/test_research.py` | 250 | 研究分析模組 |
| 密碼 | `tests/unit/test_password.py` | 31 | 雜湊與驗證 |
| API 整合 | `tests/integration/test_api.py` | 798 | 全部 18 端點 |

**缺口**:
- 無固定輸入 → 預期權重的策略確定性測試
- `decision.modified_qty` 路徑未測試
- `rule.enabled=False` 切換未測試
- ADV=0 或缺少市場資料的 fallback 未測試

### 5.2 前端測試

**狀態: 需加強** | 71 測試，覆蓋 12.8% 檔案

| 類別 | 檔案數 | 說明 |
|------|--------|------|
| 單元測試 | 8 | format utils、hooks、Page 元件 |
| E2E 測試 | 3 | smoke、backtest、orders |
| **未覆蓋** | **75+** | Admin 頁面、Risk 頁面、WebSocket、ErrorBoundary |

### 5.3 Mobile 測試

**狀態: 無測試** | 0 測試

---

## 6. 效能

### 6.1 回測引擎

**狀態: 良好** | 風險: 低

- 向量化矩陣查詢（`src/backtest/engine.py:250-276`）
- O(log N) 二分搜尋（`searchsorted`）
- 400 交易日暖機期（`src/backtest/engine.py:208-211`）

**限制**:
- 大量標的（>500）會產生密集矩陣，無稀疏矩陣優化
- 單執行緒處理，無跨標的平行運算
- 5 年以上 × 100+ 標的時記憶體線性增長

### 6.2 WebSocket 廣播

**狀態: 需優化** | 風險: 中

`src/api/ws.py:35-59`:
- O(N) 逐一發送，無批次處理
- 無背壓機制（慢客戶端會阻塞）
- JSON 序列化每次重複（可快取）
- 無連線數上限

### 6.3 API 效能

**狀態: 基本** | 風險: 低

- 全域限流 60 次/分鐘
- 回測限流 10 次/分鐘
- 每次 JWT 驗證需查詢資料庫（`src/api/auth.py:123-134`）

---

## 7. 可觀測性

### 7.1 日誌系統

**狀態: 良好** | 風險: 低

- structlog 結構化日誌（`src/logging_config.py`）
- 支援 text/json 輸出格式
- 變異請求自動記錄

### 7.2 指標端點

**狀態: 基本** | 風險: 中

`GET /api/v1/system/metrics` 提供：uptime、request_count、ws_connections、strategies_running、active_backtests

**缺失**:
- 無 Prometheus 指標
- 無每端點延遲直方圖
- 無錯誤率追蹤
- 無快取命中率
- 無策略 P&L 即時追蹤

### 7.3 告警機制

**狀態: 基本** | 風險: 高

- 風控警報僅透過 WebSocket 推送
- 無 Email / Slack / LINE 通知
- 警報僅存於記憶體（`RiskEngine._alerts`），上限 10,000 筆，重啟即失

---

## 8. 總結與優先級

### 嚴重（應儘速處理）

| # | 問題 | 面向 | 狀態 |
|---|------|------|------|
| 1 | Kill Switch 非即時且可被繞過 | 風控 | ✅ 已修復：背景每 5 秒監控 |
| 2 | 訂單建立無鎖保護（Race Condition） | 風控 | ✅ 已修復：mutation_lock 包裹風控+提交 |
| 3 | 回測結果無持久化 | 回測 | ✅ 已修復：SQLite 持久化 + GET /backtest/history |

### 重要（應規劃處理）

| # | 問題 | 面向 | 狀態 |
|---|------|------|------|
| 4 | Survivorship Bias 未防護 | 資料 | ⏳ 需外部資料源（TEJ/FactSet） |
| 5 | 股利現金流未模擬 | 資料 | ⏳ 待處理 |
| 6 | 價格前向填充可能產生錯誤信號 | 資料 | ⏳ 待處理 |
| 7 | 後端無密碼強度驗證 | 安全 | ✅ 已修復：validate_password() |
| 8 | CORS `allow_methods=["*"]` | 安全 | ✅ 已修復：收窄為 5 個方法 |
| 9 | 風控決策未寫入審計日誌 | 安全 | ✅ 已修復：persist_fn → risk_events_table |
| 10 | 風控警報無外部通知 | 可觀測 | ⏳ 待處理 |
| 11 | 無閃崩/漲跌停保護 | 風控 | ✅ 已修復：price_circuit_breaker 規則 |
| 12 | 品質檢查僅警告不阻擋 | 資料 | ✅ 已修復：suspect_dates 跳過機制 |

### 改善（可逐步推進）

| # | 問題 | 面向 | 狀態 |
|---|------|------|------|
| 13 | 前端測試覆蓋率 12.8% | 測試 | ⏳ 待處理 |
| 14 | Mobile 0 測試 | 測試 | ⏳ 待處理 |
| 15 | 無 Walk-Forward / Cross-Validation | 回測 | ⏳ 待處理 |
| 16 | WebSocket 廣播效能 | 效能 | ⏳ 待處理 |
| 17 | 無 Prometheus 指標 | 可觀測 | ⏳ 待處理 |
| 18 | 記憶體快取無上限 | 效能 | ⏳ 待處理 |
| 19 | 策略缺少確定性回歸測試 | 測試 | ⏳ 待處理 |
| 20 | 登入端點未獨立限流 | 安全 | ✅ 已修復：10 次/分鐘獨立限流 |

---

## 附錄：關鍵檔案索引

| 模組 | 檔案 | 關鍵行 |
|------|------|--------|
| 回測引擎 | `src/backtest/engine.py` | 59-201 (主流程), 268-269 (ffill), 278-286 (lookup) |
| 歷史 Feed | `src/data/feed.py` | 47-107 |
| 策略 Context | `src/strategy/base.py` | 26-86 |
| Yahoo 資料源 | `src/data/sources/yahoo.py` | 25-169 |
| 資料品質 | `src/data/quality.py` | 33-105 |
| 風控規則 | `src/risk/rules.py` | 40-180 |
| 風控引擎 | `src/risk/engine.py` | 22-155 |
| 模擬券商 | `src/execution/sim.py` | 30-138 |
| 訂單管理 | `src/execution/oms.py` | 18-105 |
| API 認證 | `src/api/auth.py` | 69-140 |
| 密碼雜湊 | `src/api/password.py` | 9-24 |
| 審計中介 | `src/api/middleware.py` | 24-50 |
| WebSocket | `src/api/ws.py` | 17-89 |
| 應用狀態 | `src/api/state.py` | 20-31 |
| 系統設定 | `src/config.py` | 20-128 |
