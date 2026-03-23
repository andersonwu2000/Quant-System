# 規劃 vs 實際：系統對照分析

**日期**: 2026-03-24
**對照文件**: `Project Requirements (Archived).md`（v3.0 架構設計）vs 目前程式碼

---

## 目錄

1. [總覽](#1-總覽)
2. [設計哲學：高度一致](#2-設計哲學高度一致)
3. [逐模組對照](#3-逐模組對照)
4. [規劃有但未實作的功能](#4-規劃有但未實作的功能)
5. [實作有但規劃沒提的功能](#5-實作有但規劃沒提的功能)
6. [架構偏離與取捨](#6-架構偏離與取捨)
7. [開發路線圖進度](#7-開發路線圖進度)
8. [結論](#8-結論)

---

## 1. 總覽

| 面向 | 規劃完成度 | 說明 |
|------|:---------:|------|
| 設計哲學 | 95% | v3 的簡化原則幾乎完全貫徹 |
| 目錄結構 | 90% | 高度吻合，小幅調整 |
| 領域模型 | 85% | 核心一致，少了幾個欄位 |
| 策略框架 | 95% | 幾乎完美實現 |
| 風控引擎 | 80% | 規則實作完整，kill switch 未串接回測 |
| API 層 | 70% | 核心端點齊全，部分規劃端點未實作 |
| 前端 | 60% | Web + Mobile 完成，桌面版砍掉 |
| 資料庫 | 50% | 簡化為 SQLite 預設，Schema 大幅精簡 |
| 實盤交易 | 5% | 僅有空殼介面 |
| 開發者工具 | 40% | CLI 基本可用，缺 SDK 生成等 |

---

## 2. 設計哲學：高度一致

v3 規劃的五條設計原則在實作中**全部被遵循**：

| 原則 | 實際體現 |
|------|---------|
| 能用函式解決的不用類別 | ✅ 風控規則用 function factory，不用繼承 |
| 能用單體解決的不用微服務 | ✅ 全部在單一 FastAPI 進程內 |
| 能用 SQL 解決的不用自建存儲 | ✅ SQLAlchemy + 單一 DB |
| 能用標準庫解決的不用框架 | ✅ 未引入 Celery/Redis/Kafka |
| 每層抽象必須有具體收益 | ✅ 只有 Strategy 需要繼承，DataFeed 是唯一 ABC |

量化面的不可簡化原則也基本遵守：

| 原則 | 狀態 | 備註 |
|------|:----:|------|
| 時間因果性 | ✅ | `Context` 截斷 + `HistoricalFeed.set_current_date()` |
| 市場摩擦建模 | ⚠️ | 有滑價/手續費/稅，但模型偏簡化 |
| 統計嚴謹性 | ❌ | `backtest/validation.py` 未實作（規劃中有因果性/確定性檢查） |
| 風控獨立性 | ✅ | risk 模組不依賴 strategy |

---

## 3. 逐模組對照

### 3.1 領域模型 (`src/domain/models.py`)

| 規劃 | 實際 | 差異 |
|------|------|------|
| `Instrument` 含 `asset_class`, `currency`, `multiplier` | `Instrument` 僅有 `symbol`, `lot_size`, `tick_size` | 🟡 簡化了，砍掉期貨/選擇權/多幣種支援 |
| `Position.instrument` 是 `Instrument` 物件 | `Position` 用 `symbol: str` | 🟡 進一步簡化 |
| `Order` 含 `client_order_id`（冪等鍵） | `Order` 無冪等鍵 | 🔴 缺失，影響實盤可靠性 |
| `Order` 含 `strategy_id` | `Order` 無 `strategy_id` | 🟡 無法追蹤訂單來源策略 |
| `Order.price: Decimal | None`（None=市價單） | `Order.price` 必填 | 🟡 不支援市價單 |
| `Portfolio` 含 `as_of: datetime` | `Portfolio` 有 `nav_sod`, `daily_drawdown` 等額外欄位 | 🟢 實作比規劃更豐富 |
| 全部使用 `Decimal` | ✅ 一致 | ✅ |
| `< 200 行` | ~250 行 | ✅ 基本控制住 |

### 3.2 策略框架 (`src/strategy/`)

| 規劃 | 實際 | 差異 |
|------|------|------|
| `Strategy` ABC: `name()` + `on_bar(ctx) → dict[str, float]` | ✅ 完全一致 | ✅ |
| `Context`: `bars()`, `universe()`, `portfolio()`, `now()`, `log()` | `Context`: `bars()`, `universe()`, `portfolio`, `current_time` | 🟡 `log()` 未實作，`now()` 改名 |
| `weights_to_orders()` 轉換 | ✅ 在 `strategy/engine.py` | ✅ |
| 因子計算是純函式 | ✅ `factors.py` 全是純函式 | ✅ |
| 優化器：CVXPY | `optimizer.py` 用 `equal_weight`, `signal_weight`, `risk_parity` | 🟡 未用 CVXPY，用簡化版 |
| 8 個策略 | ✅ 8 個策略全部實作 | ✅ |

**評價**: 策略框架是最忠於規劃的模組。

### 3.3 風控引擎 (`src/risk/`)

| 規劃 | 實際 | 差異 |
|------|------|------|
| 聲明式 `RiskRule` dataclass + function factory | ✅ 完全一致 | ✅ |
| 7 條預設規則 | 6 條規則（少了 `max_sector_weight` 和 `weekly_drawdown_limit`，多了 `max_correlation`） | 🟡 微調 |
| `RiskEngine.check()` 逐條檢查 | ✅ 第一個 REJECT 停止 | ✅ |
| Kill Switch (日回撤 5%) | ✅ 定義了，但回測主迴圈未呼叫 | 🔴 功能存在但未啟用 |
| `RiskMonitor` 即時監控 | ✅ 有，推送 WebSocket 告警 | ✅ |

### 3.4 執行層 (`src/execution/`)

| 規劃 | 實際 | 差異 |
|------|------|------|
| `SimBroker`：滑價 + 手續費 + 成交量模擬 | ✅ 實作完整 | ✅ |
| `PaperBroker`：用即時行情模擬成交 | ❌ 空殼，僅回傳 order_id | 🔴 Phase 3 未完成 |
| 券商 Adapter（富邦 API） | ❌ 未實作 | 🔴 Phase 4 未開始 |
| `OMS` 訂單管理 | ⚠️ 基本框架有，純記憶體，無持久化 | 🟡 |
| `client_order_id` 冪等支援 | ❌ 未實作 | 🔴 |
| 對帳機制 | ❌ 未實作 | 🔴 Phase 4 |

### 3.5 回測引擎 (`src/backtest/`)

| 規劃 | 實際 | 差異 |
|------|------|------|
| `BacktestEngine.run()` 主迴圈 | ✅ 實作完整 | ✅ |
| `analytics.py` 績效分析 | ✅ Sharpe, MDD, Sortino, 勝率等 | ✅ |
| `validation.py` 因果性/確定性檢查 | ❌ 檔案不存在 | 🔴 重要缺失 |
| 滑價敏感度測試 | ❌ 未實作 | 🟡 |
| 回測是獨立進程 | ❌ 在 API 的背景任務中執行 | 🟡 不影響功能，但大回測會搶 API 資源 |

### 3.6 API 層 (`src/api/`)

#### 規劃的端點 vs 實際

| 端點群組 | 規劃 | 實際 | 狀態 |
|----------|------|------|:----:|
| **市場數據** | `GET /market/quotes/{symbol}`, `/bars/{symbol}`, `/symbols` | ❌ 無 market routes | 🔴 |
| **投資組合** | `GET /portfolio`, `/positions`, `/pnl`, `/risk` | `GET /portfolio`, `/portfolio/positions` | 🟡 缺 PnL 曲線和風險快照 |
| **策略管理** | `GET/POST strategies/{id}/start|stop`, `PUT params`, `GET performance` | `GET /strategies` | 🟡 缺啟停控制、參數調整、績效查詢 |
| **訂單** | `GET/POST/DELETE /orders` | `GET /orders`, `POST /orders` | 🟡 缺撤單 |
| **風控** | `GET rules`, `PUT rules/{id}`, `GET breaches`, `POST kill-switch` | `GET /risk/status`, `/risk/rules`, `/risk/alerts` | 🟡 缺規則修改、手動 kill-switch |
| **回測** | `POST /backtest`, `GET /{task_id}`, `GET /{task_id}/result` | ✅ 完整實作 | ✅ |
| **因子研究** | `GET /factors`, `/{name}/report`, `POST /{name}/compute` | `GET /factors` | 🟡 缺報告和重算 |
| **系統** | `GET /health`, `/status`, `/logs` | `GET /health`, `/status`, `/metrics` | 🟡 logs 改為 metrics |
| **認證** | API Key + JWT | ✅ + httpOnly cookie + role hierarchy | 🟢 比規劃更完整 |
| **使用者管理** | 未規劃 | ✅ 完整 CRUD + 角色管理 | 🟢 額外功能 |

#### 橫切面

| 規劃 | 實際 | 差異 |
|------|------|------|
| RFC 7807 錯誤格式 | 標準 FastAPI HTTPException | 🟡 |
| Cursor-based 分頁 | 未實作分頁 | 🟡 |
| 令牌桶限流 100 req/s | slowapi 60 req/min | 🟡 限流更保守 |
| API 版本 `/api/v1/`, `/api/v2/` | ✅ `/api/v1/` | ✅ |
| 審計 middleware | ✅ `AuditMiddleware` 記錄 POST/PUT/DELETE | ✅ |

### 3.7 前端

| 規劃 | 實際 | 差異 |
|------|------|------|
| **Web (React + Tailwind)** | ✅ React 18 + Vite + Tailwind | ✅ |
| **桌面 (Tauri + React)** | ❌ 完全未做 | 🔴 砍掉 |
| **Mobile (React Native)** | ✅ Expo 52 | ✅ |
| **共享包 `@quant/core`** | ✅ `@quant/shared`（改名） | ✅ |
| 狀態管理：Zustand | 未使用 Zustand，用 React hooks + context | 🟡 更輕量 |
| API Client 自動生成（OpenAPI） | 手寫 API client | 🟡 |
| SDK 自動生成（TypeScript/Rust/Python） | ❌ 未實作 | 🔴 |
| Notebook 整合（Python SDK） | ❌ 未實作 | 🔴 |
| 角色導向介面（研究員/交易員/風控） | 單一介面 + role-based 權限控制 | 🟡 權限有，但 UI 未分化 |

### 3.8 資料庫

| 規劃 | 實際 | 差異 |
|------|------|------|
| PostgreSQL + TimescaleDB | PostgreSQL 支援，但預設 SQLite | 🟡 開發方便但生產不理想 |
| `bars` 表 (hypertable) | `bars` 表（無 TimescaleDB） | 🟡 |
| `trades` 表 | ✅ `trades` 表 | ✅ |
| `position_snapshots` 表 | ❌ 未實作 | 🔴 無法重建歷史持倉 |
| `factor_values` 表 | ❌ 未實作 | 🟡 |
| `backtest_results` 表 | ✅ | ✅ |
| `risk_events` 表 | ✅ | ✅ |
| `system_logs` 表 | ❌ 用 structlog 寫到 stdout | 🟡 |
| `users` 表 | ✅（規劃未提，額外新增） | 🟢 |

### 3.9 CLI 工具

| 規劃 | 實際 | 差異 |
|------|------|------|
| `quant backtest` | ✅ `python -m src.cli.main backtest` | ✅ |
| `quant paper` | ❌ | 🔴 |
| `quant live` | ❌ | 🔴 |
| `quant status` | ✅ | ✅ |
| `quant logs` | ❌ | 🟡 |
| `quant factor report` | ✅ `factors` 命令 | ✅ |
| `quant kill` | ❌ | 🔴 |
| `quant init my-strategy` | ❌ | 🟡 |
| 基於 Typer | 基於 argparse（`add_parser`） | 🟡 更簡單 |

### 3.10 測試

| 規劃 | 實際 | 差異 |
|------|------|------|
| 測試金字塔：單元 > 整合 > E2E | ✅ 結構正確 | ✅ |
| 單元測試（領域模型、因子、風控） | ✅ 95+ 測試 | ✅ |
| 整合測試（API + DB） | ✅ 70+ 測試 | ✅ |
| E2E 回測驗證 | ⚠️ 有 E2E 但回測引擎本身未測 | 🔴 |
| 因果性檢查（打亂時間軸） | ❌ | 🔴 |
| 確定性檢查（跑兩次比對） | ❌ | 🔴 |
| 性質測試（Hypothesis） | ❌ | 🟡 |
| 滑價敏感度掃描 | ❌ | 🟡 |

---

## 4. 規劃有但未實作的功能

按影響程度排序：

### 🔴 重要缺失

| 功能 | 規劃章節 | 影響 |
|------|----------|------|
| **PaperBroker（即時模擬交易）** | §5.5, Phase 3 | 無法驗證策略在即時數據上的表現 |
| **券商 Adapter（實盤交易）** | §5.2, Phase 4 | 無法執行真實交易 |
| **`position_snapshots` 表** | §七 | 無法重建任意日期的歷史持倉 |
| **`backtest/validation.py`** | §6.3 | 無因果性/確定性自動檢查 |
| **桌面應用 (Tauri)** | §四 | 缺少低延遲交易監控介面 |
| **SDK 自動生成** | §3.5 | 前端手寫 API client，易不一致 |
| **Notebook 整合（Python SDK）** | §4.3 | 研究員無法在 Jupyter 中操作系統 |
| **策略啟停 API** | §3.2 | 無法從 UI 控制策略運行 |
| **訂單撤銷** | §3.2 | 無法取消已提交的訂單 |
| **對帳機制** | Phase 4 | 實盤時無法驗證系統持倉 vs 券商持倉 |

### 🟡 次要缺失

| 功能 | 規劃章節 | 影響 |
|------|----------|------|
| 市場數據 API（quotes/bars/symbols） | §3.2 | 前端無法直接查詢行情 |
| PnL 歷史曲線 API | §3.2 | 前端無法顯示績效走勢 |
| 風控規則修改 API | §3.2 | 無法從 UI 調整風控參數 |
| 手動 Kill Switch API | §3.2 | 無法從 UI 觸發緊急熔斷 |
| 因子分析報告 API | §3.2 | 因子 IC/衰減分析未暴露 |
| `factor_values` 表 | §七 | 因子值未持久化 |
| `system_logs` 表 | §七 | 系統日誌未入 DB |
| Cursor-based 分頁 | §3.1 | 大量數據查詢可能卡住 |
| RFC 7807 錯誤格式 | §3.1 | 錯誤回應格式不標準 |
| Hypothesis 性質測試 | §6.3 | 隨機操作序列未測試 |
| `quant init` 策略腳手架 | §6.1 | 新策略需手動建檔 |
| CVXPY 投資組合優化 | §5.3 | 目前用較簡化的優化方法 |
| TimescaleDB | §七 | 時序查詢效能未優化 |
| 富邦資料源 (`sources/fubon.py`) | §5.2 | config 有但未實作 |

---

## 5. 實作有但規劃沒提的功能

這些是開發過程中額外新增的：

| 功能 | 位置 | 價值 |
|------|------|------|
| **完整使用者管理** | `src/api/routes/auth.py` | 帳號 CRUD、角色分配、密碼重設 |
| **5 級角色階層** | `src/api/auth.py` | viewer < researcher < trader < risk_manager < admin |
| **帳號鎖定機制** | `src/api/routes/auth.py` | 5 次失敗 → 15 分鐘鎖定 |
| **httpOnly Cookie** | `src/api/auth.py` | 比純 JWT Bearer 更安全 |
| **Token revocation** | `migrations/003_*` | 可撤銷已發放的 JWT |
| **i18n（中/英）** | `apps/web/src/i18n/` | 完整的多語系支援 |
| **Mobile App** 的離線快取 | `apps/mobile/` | 離線時顯示快取資料 |
| **PageSkeleton 載入動畫** | `apps/web/src/shared/ui/` | 良好的載入體驗 |
| **Audit Middleware** | `src/api/middleware.py` | 變更操作自動記錄 |
| **WebSocket ping/pong** | `src/api/ws.py` | 連線保活 |
| **Parquet 磁碟快取** | `src/data/feed.py` | 減少 Yahoo API 呼叫 |
| **資料品質檢查** | `src/data/quality.py` | 7 項自動檢查 |
| **E2E 測試 (Playwright)** | `apps/web/e2e/` | 規劃只提單元/整合 |
| **Mobile 測試 (71 tests)** | `apps/mobile/src/components/__tests__/` | 規劃未提 |
| **Docker multi-stage build** | `Dockerfile` | 最佳化映像大小 |
| **股利處理** | `src/backtest/engine.py` | 回測中處理除息 |
| **動態再平衡頻率** | `src/backtest/engine.py` | daily/weekly/monthly 可選 |

---

## 6. 架構偏離與取捨

### 6.1 刻意的簡化（合理）

| 規劃 | 實際 | 判斷 |
|------|------|------|
| TimescaleDB hypertable | 普通 PostgreSQL 表 | ✅ 合理 — 標的 < 1000，不需時序優化 |
| Zustand 狀態管理 | React hooks + context | ✅ 合理 — 應用不夠複雜，不需外部狀態庫 |
| Typer CLI | argparse | ✅ 合理 — 減少依賴 |
| 多進程回測 | API 背景任務 | ⚠️ 可接受 — 但大回測會影響 API 回應 |
| CVXPY 優化器 | 手寫 equal/signal/risk_parity | ✅ 合理 — 先跑起來，之後再加 |

### 6.2 意外的偏離（需注意）

| 規劃 | 實際 | 影響 |
|------|------|------|
| `Instrument` 含完整資產資訊 | 僅 `symbol` 字串 | 未來加期貨/選擇權時需重構 |
| `Order.strategy_id` 追蹤來源 | 訂單無策略來源 | 多策略時無法歸因 |
| `position_snapshots` 每日快照 | 無持倉持久化 | 重啟後狀態歸零 |
| 回測是獨立進程 | 在 API 進程內的 ThreadPoolExecutor | 大回測可能拖慢 API |

### 6.3 被砍掉的平台

| 平台 | 規劃 | 實際 | 影響 |
|------|------|------|------|
| Web | 全功能研究+交易 | ✅ 研究為主 | 缺交易操作 UI |
| 桌面 (Tauri) | 低延遲交易監控 | ❌ 砍掉 | 無桌面通知、無 Kill Switch 按鈕 |
| Mobile | 告警+速覽 | ✅ 基本完成 | 缺推播通知（僅 WebSocket） |
| Notebook | 研究主力 | ❌ 無 Python SDK | 研究員必須用 Web UI |
| CLI | 自動化腳本 | ⚠️ 基本功能 | 缺 paper/live/kill 指令 |

---

## 7. 開發路線圖進度

規劃定義了 5 個 Phase，以下是目前達成狀況：

### Phase 0 — 地基（規劃 2 週）✅ 完成

| 項目 | 狀態 |
|------|:----:|
| 領域模型 + DB schema + migration | ✅ |
| 配置體系 (Pydantic Settings) | ✅ |
| Docker Compose 開發環境 | ✅ |

### Phase 1 — 能跑回測（規劃 4 週）✅ 完成

| 項目 | 狀態 |
|------|:----:|
| Yahoo Finance 數據源 + 數據存取層 | ✅ |
| Strategy ABC + Context + 示範策略 | ✅（8 個策略全部完成） |
| BacktestEngine + SimBroker + 績效分析 | ✅ |
| CLI backtest 命令 | ✅ |

### Phase 2 — API 和基礎 UI（規劃 3 週）✅ 大致完成

| 項目 | 狀態 |
|------|:----:|
| FastAPI + 核心端點 | ✅ |
| 前端共享層 @quant/shared | ✅ |
| Web 前端：回測頁 + 因子頁 | ✅ |
| 認證：API Key + JWT | ✅（超出規劃，加了角色/鎖定/Cookie） |
| ❌ API Client 自動生成 | 手寫 |

### Phase 3 — 風控 + 紙上交易（規劃 3 週）⚠️ 部分完成

| 項目 | 狀態 |
|------|:----:|
| 風控引擎 + 聲明式規則 | ✅ |
| 即時行情接入 | ❌ 未實作 |
| PaperBroker（模擬成交） | ❌ 空殼 |
| WebSocket 推送 | ✅ |
| 交易員看板 + 風控看板 | ⚠️ 有看板，缺操作功能 |

### Phase 4 — 實盤（規劃 4 週）❌ 未開始

| 項目 | 狀態 |
|------|:----:|
| 券商 Adapter | ❌ |
| OMS 完整流程 | ❌ |
| 對帳機制 | ❌ |
| Kill Switch (API + UI) | ❌（引擎有，API/UI 無） |
| 桌面應用 (Tauri) | ❌ 砍掉 |

### Phase 5 — 打磨（持續）⚠️ 部分跳躍完成

| 項目 | 狀態 |
|------|:----:|
| 行動裝置 App | ✅ 跳到這裡先做了 |
| 投資組合優化器 (CVXPY) | ❌ |
| TCA 分析 | ❌ |
| 多策略資金分配 | ❌ |
| 績效歸因 | ❌ |
| 因子庫擴充 | ⚠️ 基礎因子有 |

---

## 8. 結論

### 做得好的地方

1. **設計哲學的貫徹** — v3 反思 v2 過度設計的教訓被完全吸收，沒有重蹈覆轍
2. **策略框架** — 幾乎完美實現規劃，`on_bar() → weights` 的設計簡潔有效
3. **風控規則** — function factory 模式優雅且易擴展
4. **超出規劃的安全性** — 使用者管理、角色階層、帳號鎖定都是額外加分
5. **Mobile App** — 規劃中是 Phase 5 的事，提前完成了

### 主要偏離

1. **Phase 3/4 的空白** — 紙上交易和實盤是規劃的核心目標，但幾乎未動
2. **桌面應用砍掉** — 可以理解（Tauri 學習成本高），但失去了低延遲監控介面
3. **Notebook 整合未做** — 規劃特別強調「研究員大部分時間在 Jupyter」，這條路徑完全沒走
4. **持倉不持久化** — 規劃中有 `position_snapshots` 表，實作完全跳過
5. **回測驗證未做** — `validation.py`（因果性/確定性檢查）是量化回測的品質保證，缺失影響大

### 一句話總結

> 系統忠實地完成了 Phase 0-2（地基 + 回測 + API/UI），在 Phase 3 做了一半（風控有、紙上交易沒有），Phase 4（實盤）未開始，Phase 5 跳著做了 Mobile App。整體架構品質高，但**離規劃的最終願景——「能被 2-5 人團隊用於生產交易」——還差 Phase 3 後半 + Phase 4 的完整工作量**。
