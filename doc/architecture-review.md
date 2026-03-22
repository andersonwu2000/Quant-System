# 系統架構審查報告

> 審查日期：2026-03-23（最後更新：2026-03-23）
> 範圍：Monorepo `D:\Finance` — Backend (root) / Web (`apps/web`) / Mobile (`apps/mobile`) / Shared (`apps/shared`)

## 三端架構總覽

| 層級 | 技術 | 角色 |
|------|------|------|
| **Backend** | Python / FastAPI / SQLite+PG | 量化引擎、回測、風控、API |
| **Web** | React 18 / Vite / Tailwind | 桌面端 Dashboard SPA |
| **Mobile** | React Native / Expo 52 | 手機端監控 App |

三者共享同一 Backend API (`/api/v1/*`) + WebSocket (`/ws/{channel}`)。

---

# 一、架構層級問題

## 1. 認證體系不完整 [P0]

**現狀：** 三端認證機制各自為政，且均有安全缺陷。

| 端 | 機制 | 問題 |
|----|------|------|
| Backend | API Key + JWT 雙軌，但無 login endpoint 發 JWT | 硬編碼預設值 `api_key="dev-key"`, `jwt_secret="change-me-in-production"`（`config.py:48-49`） |
| Backend | WebSocket 無任何認證（`ws.py`） | 任何人可訂閱 portfolio/alerts 等敏感 channel |
| Backend | CORS `allow_origins=["*"]` + `allow_credentials=True`（`app.py:34`） | 違反 CORS 規範，允許任意網站發帶憑證請求 |
| Web | API Key 存 localStorage（`client.ts:1-13`） | XSS 可直接竊取；無 CSRF 防護 |
| Mobile | 預設 HTTP 連線（`login.tsx:15`） | 憑證明文傳輸，公共 WiFi 可攔截 |

**解決方案：**
- **統一 JWT flow**：新增 `POST /api/v1/auth/login`，回傳 short-lived access token + refresh token
- **Web**：token 存 httpOnly cookie（防 XSS）+ SameSite（防 CSRF）
- **Mobile**：繼續用 SecureStore 存 JWT，強制 HTTPS（非 localhost）
- **WebSocket**：連線時帶 token query param，server 驗證後才開始推送；升級 `wss://`
- **CORS**：從 config 讀取允許 origin 列表，預設 `["http://localhost:3000"]`
- **密鑰**：移除預設值，`mode != "backtest"` 時啟動檢查，預設值則拒絕啟動
- **API Key**：降級為 service-to-service 用途，支援 per-user 發放與 rotation

---

## 2. 單點故障 — 無高可用設計 [P1]

**問題：** Backend 是 single-process monolith，crash 後全端斷線。無 process supervisor、無自動重啟。Paper/Live 模式下風控和下單完全中斷。

**解決方案：**
- 加入 process manager（systemd / supervisord）實現 auto-restart
- uvicorn 多 worker 模式（`--workers 2`）
- 外部 health check 監控（uptime-kuma）
- 長期：container orchestration

---

## 3. 回測系統設計缺陷 [P1]

**問題（工程面 + 體驗面）：**
- `POST /backtest` 在主 process daemon thread 執行，阻塞 API server（`routes/backtest.py:56`）
- 無超時機制，回測可能永遠掛起；異常只存 `str(e)` 無 traceback（`routes/backtest.py:52-54`）
- 前端每 2 秒遞迴 polling，長回測 >40 分鐘可能 stack overflow（`useBacktest.ts:24-40`）
- 無進度回報，用戶不知道執行到哪裡

**解決方案：**
- 短期：`asyncio.to_thread()` + `ThreadPoolExecutor` 移到背景；加入 30 分鐘超時
- 中期：Celery + Redis 任務佇列，限制同時 2 個回測
- 進度透過 WebSocket `backtest` channel 推送（百分比 + 當前日期）
- 前端改為 `while` 迴圈 + `AbortController`，或純 WebSocket 訂閱
- 異常用 `traceback.format_exc()` + `logging.exception()` 記錄完整資訊

---

## 4. 回測正確性風險 [P1]

### 4a. 存活者偏差（Survivorship Bias）

**問題：** 回測只用「現在還存在的 symbol」。已下市股票不在 universe 中，回測結果系統性偏高。這是量化回測最常見的陷阱。

**解決方案：**
- 支援匯入歷史 universe 快照（某日的成分股列表）
- 在回測結果中標示「未處理 survivorship bias」警告
- 長期：整合含下市股票的資料源

### 4b. 無股息/拆股處理

**位置：** `src/data/sources/yahoo.py`、`src/data/quality.py`

**問題：** 未明確處理除權除息日價格跳空、拆股/合股、現金股利再投資假設。長時間高股息股票回測收益率失真。

**解決方案：**
- 明確使用 Yahoo Finance `Adj Close` 欄位
- DataQuality 加入拆股偵測（單日 >30% 跳空 + 成交量異常）
- 文件標明「使用已調整價格」假設

### 4c. 交易成本模型不完整

**問題：** 只模擬手續費 + 稅 + 固定 slippage。缺少 market impact（大單衝擊成本）、bid-ask spread、部分成交模擬（目前 100% fill 或 0%）。

**解決方案：**
- SimBroker 加入 volume participation rate 限制（如最多吃 ADV 的 10%，超出部分不成交）
- 可選：加入 Almgren-Chriss market impact model
- 記錄 fill ratio 到 BacktestResult

---

## 5. 全域可變狀態無鎖保護 [P1]

**位置：** `src/api/state.py:17-34`

```python
_state: AppState | None = None
def get_app_state() -> AppState:
    global _state
    if _state is None:
        _state = AppState()
    return _state
```

**問題：**
- Lazy init race condition（多 thread 可能建立多個 instance）
- `AppState.portfolio` 可變物件，多 route handler 同時讀寫無鎖
- Trade 應用非原子（`oms.py:59-106`）：cash 扣了但 position 未更新時拋異常 → 不一致

**解決方案：**
- `threading.Lock()` 保護 singleton 初始化
- Portfolio mutation 用 copy-on-write：先在副本操作，成功後原子替換
- 或 `asyncio.Lock()` 保護所有 mutation endpoint

---

## 6. API 缺少速率限制與分頁 [P2]

**問題：**
- 無 rate limiting — 任何 client 可無限發送請求，觸發大量回測、連續呼叫 Kill Switch
- Yahoo Finance API 被過度呼叫可能封 IP
- `GET /orders`、`GET /risk/alerts` 無分頁 — 資料量累積後單次回應可達上萬筆

**解決方案：**
- 加入 FastAPI rate limiter（如 slowapi），關鍵端點限制 10 req/min
- API 回應加入 `limit`/`offset` 分頁參數，預設 100 筆
- Yahoo 下載加入本地快取（見 #10）

---

## 7. 無審計日誌 [P2]

**問題：** 策略啟停、Kill Switch、規則修改等操作沒有記錄「誰在何時做了什麼」。`risk_events` 只記風控觸發，不記人為操作。

**解決方案：**
- 新增 `audit_logs` 資料表：`(timestamp, user_id, action, resource, detail, ip)`
- 所有 mutation endpoint 加入 audit logging middleware
- `GET /api/v1/audit/logs`（限 admin），保留 90 天

---

## 8. 無可觀測性（Observability）[P2]

**問題：** 無 structured logging、無 metrics endpoint、無 tracing。問題發生時無法診斷。

**解決方案：**
- 統一使用 `structlog` 或 Python `logging` JSON format
- 加入 `/metrics` endpoint（Prometheus format）：API latency、active WS connections、backtest queue depth
- 關鍵操作加入 trace ID（request → strategy → risk → execution 全鏈路）

---

## 9. 無優雅關機（Graceful Shutdown）[P2]

**問題：** uvicorn 收到 SIGTERM 時：進行中回測直接中斷（daemon thread）、WebSocket 無通知斷開、Portfolio state 可能未持久化。

**解決方案：**
- 註冊 shutdown hook：等待進行中回測完成或標記為 interrupted
- WebSocket broadcast close message
- Portfolio state 持久化到 DB

---

## 10. 無資料快取策略 [P2]

**問題：** 每次回測都重新從 Yahoo Finance 下載全部資料。重複回測浪費時間和頻寬。且 Yahoo 免費資料有 15 分鐘延遲，paper/live 模式下風控判斷可能過晚。

**解決方案：**
- 回測：下載後存入 DataStore，後續優先讀本地
- 加入快取過期策略（如 daily bar 當日 >18:00 後才更新）
- 文件標明「Yahoo 免費資料 15 分鐘延遲」對即時交易的影響
- Live 模式考慮付費即時資料源

---

## 11. ~~前端重複代碼 — 無共享層~~ [已解決]

已建立 `@quant/shared` package（bun workspace），共享 TypeScript types、API client（`ClientAdapter` 注入模式）、WSManager（含指數退避）、endpoints、format utils。Web / Mobile 透過 barrel re-export 引用，feature code 不直接 import `@quant/shared`。

---

## 12. 無 CI/CD、無 Docker [P3]

**問題：** 沒有 Dockerfile、docker-compose、GitHub Actions。部署完全手動。環境不可重現。

**解決方案：**
- `Dockerfile` + `docker-compose.yml`（backend + PG + frontend）
- `.github/workflows/ci.yml`：lint → test → build
- 環境變數透過 Docker secrets 管理

---

## 13. 資料庫 Migration 未使用 [P3]

**問題：** Alembic 已設定但 `migrations/versions/` 為空。`DataStore` 用 `create_all()` 建表。

**解決方案：**
- 產生初始 migration：`alembic revision --autogenerate -m "initial"`
- 移除 `create_all()`，改用 `alembic upgrade head`

---

## 14. 無災難復原機制 [P3]

**問題：** 無備份策略、無 state snapshot。SQLite 無 WAL，concurrent write 可能丟資料。

**解決方案：**
- SQLite 啟用 WAL mode
- Production 強制 PostgreSQL + 定期 pg_dump
- Portfolio state 定時 snapshot

---

## 15. Mobile 功能與體驗差距 [P3]

**問題：**
- 無回測頁面、無 Orders 頁面、無 NAV 圖表
- 無 i18n（Web 有 en/zh）
- 無推播通知 — 鎖屏後完全失去風控警報
- Web 風控警報僅在 Risk 頁面顯示，非全域

**解決方案：**
- Mobile 加入 Orders tab + NAV 折線圖
- 整合 `expo-notifications` + FCM/APNs，通知分級（INFO 靜默、CRITICAL 響鈴）
- Web 在 App 層級訂閱 alerts channel，顯示 toast；EMERGENCY 級用 modal
- Mobile 加入 i18n，翻譯檔放入 shared package

---

# 二、代碼層級問題

## Backend

| # | 問題 | 位置 | 嚴重度 | 說明 | 解決方案 |
|---|------|------|--------|------|----------|
| B1 | 風控規則跨回測狀態洩漏 | `rules.py:120-132` | HIGH | `max_daily_trades` 閉包中 `trade_count` dict 跨回測持久化，第二次回測繼承第一次的 count | 每次回測建立新 rule 實例；或將狀態存在 RiskEngine 而非閉包 |
| B2 | Decimal/float 混用於 API 序列化 | `routes/portfolio.py:28-30` | HIGH | `float(pos.quantity)` 丟失精度，違反「所有金額用 Decimal」原則 | Pydantic schema 用 `str` 類型傳遞金額；自訂 JSON encoder |
| B3 | 訂單數量取整精度 | `strategy/engine.py:63-64` | HIGH | `int(qty / lot_size)` 丟失 Decimal 精度，小額持倉可能靜默取整為 0 | 改用 `qty = (qty // Decimal(str(lot_size))) * Decimal(str(lot_size))` |
| B4 | 價格缺失靜默跳過 | `backtest/engine.py:219-235` | MEDIUM | symbol 無資料時 `continue`，後續風控因缺少價格可能失效 | 記錄 warning log；缺價格的 symbol 排除出策略計算 |
| B5 | API 輸入驗證不足 | `api/schemas.py:83-93` | MEDIUM | BacktestRequest 無 validator：strategy 可空、cash 可負、日期可反向 | 加入 `@field_validator`；start/end 改用 `date` 類型 |
| B6 | WebSocket 異常靜默吞掉 | `api/ws.py:49-56` | MEDIUM | bare `except Exception` 捕獲所有錯誤 | 改為 `except (WebSocketDisconnect, ConnectionError)` |
| B7 | `_nav_sod` 動態屬性 | `backtest/engine.py:104-105` | LOW | 在 Portfolio 上用 `hasattr` 動態設定屬性，型別系統無法追蹤 | 加入 Portfolio `__init__` 或用 BacktestEngine 獨立 dict |

## Web

| # | 問題 | 位置 | 嚴重度 | 說明 | 解決方案 |
|---|------|------|--------|------|----------|
| W1 | 無 Content Security Policy | `index.html` | HIGH | 無 CSP header，允許任意 inline script | 加入 `<meta http-equiv="Content-Security-Policy">` |
| W2 | WebSocket 訊息無型別驗證 | `useDashboard.ts:12` | HIGH | `msg as Portfolio` 無 runtime 驗證，後端格式變更直接 crash | 使用 Zod parse，無效訊息忽略 |
| W3 | Kill Switch 無防重複點擊 | `RiskPage.tsx:51-59` | MEDIUM | 按鈕無 loading/disabled 狀態 | 加入 loading state，執行中 disable |
| W4 | NavHistory 記憶體膨脹 | `useDashboard.ts:15-21` | MEDIUM | 高頻 WebSocket 更新造成大量 array allocation | `requestAnimationFrame` 或 debounce 限制更新頻率 |
| W5 | useCallback 缺少依賴 | `useDashboard.ts:11-23` | LOW | 缺 `setNavHistory` dependency | 補齊 deps |
| W6 | 回測表單無輸入驗證 | `BacktestPage.tsx:53-88` | LOW | cash 可負、universe 無上限、date 未驗證 | 前端 validation + bounds check |
| W7 | 無登出功能 | `App.tsx:14-17` | LOW | 無法清除 API Key | Settings 加登出按鈕 |

## Mobile

| # | 問題 | 位置 | 嚴重度 | 說明 | 解決方案 |
|---|------|------|--------|------|----------|
| M1 | 無 App State 處理 | `api/ws.ts` | HIGH | 背景時 WebSocket 持續重連耗電；iOS 殺連線後前景無資料 | 監聽 `AppState`，背景 disconnect、前景 reconnect |
| ~~M2~~ | ~~WebSocket 重連無指數退避~~ | ~~`api/ws.ts`~~ | ~~已解決~~ | 已移至 `@quant/shared` WSManager，實作指數退避 `Math.min(BASE * 2^retries, MAX)` | — |
| M3 | Alert 陣列無限增長 | `useAlerts.ts:29-31` | HIGH | 只 prepend 不清除，長時間可 OOM | `.slice(0, 100)` 保留最近 100 筆 |
| M4 | Polling + WebSocket 同時運行 | `usePortfolio.ts:6-40` | HIGH | 10 秒 polling 和 WebSocket 並行，請求翻倍，舊 poll 可覆蓋新 WS 資料 | WebSocket 為主，polling 僅在 WS 斷線時 fallback |
| M5 | Kill Switch 易誤觸 | `alerts.tsx:33-34` | HIGH | 大紅按鈕在 Alerts 頁面最上方，滑動易誤觸 | 移至 Settings；改為長按或輸入確認碼 |
| M6 | 認證閃爍 | `_layout.tsx:6-11` | MEDIUM | 初始 `authenticated=false`，async check 前先閃 Login 畫面 | loading 時顯示 SplashScreen |
| M7 | ScrollView 未用 FlatList | `index.tsx:21-55`, `positions.tsx:31-60` | MEDIUM | 列表無虛擬化，100+ 持倉效能差 | 改用 FlatList + React.memo |
| M8 | 錯誤靜默吞掉 | `positions.tsx:12-21` | MEDIUM | catch 註解「error boundary 處理」但無 Error Boundary | 加入 setError + UI 顯示；_layout 包裹 ErrorBoundary |
| M9 | 無 SafeAreaView | 所有 screen | MEDIUM | notch/Dynamic Island 遮擋內容 | 用 `useSafeAreaInsets()` |
| M10 | Android 鍵盤遮輸入框 | `login.tsx:26-28` | LOW | `behavior={undefined}` on Android | 改為 `"height"` |
| M11 | Deep Link 無認證保護 | `app.json` | LOW | URL scheme 可繞過 login | `_layout.tsx` 加 auth check |

---

## 16. 無 E2E / 前端測試 [P2]

**問題：** Web 和 Mobile 零測試覆蓋 — 無 unit test、無 component test、無 E2E test。Backend 有 54 個 unit test，但無 API integration test（不經過 HTTP 層）。重構或升級依賴時無法確認功能完整性。

**解決方案：**
- Web：Vitest + React Testing Library 做 component test；Playwright 做關鍵流程 E2E（登入→Dashboard→回測→風控）
- Mobile：Jest + React Native Testing Library
- Backend：`httpx.AsyncClient` + `TestClient` 做 API integration test
- CI 中強制執行（見 #12）

---

## 17. 無環境切換機制 [P2]

**問題：** 無 dev / staging / prod 環境區分。`config.py` 從 `.env` 讀取，但無環境切換邏輯。開發時使用的 `dev-key`、`change-me-in-production` 等預設值可能直接帶到生產環境。Web 的 Vite proxy 只適用開發，production build 需要不同的 API base URL。

**解決方案：**
- `config.py` 加入 `QUANT_ENV` 環境變數（`development` / `staging` / `production`），production 模式拒絕啟動若偵測到預設密鑰
- Web：利用 Vite `mode`，`.env.development` / `.env.production` 分別設定 `VITE_API_URL`
- Mobile：`app.config.ts` 根據 release channel 切換 `baseUrl`
- 提供 `.env.example` 並在 README 說明各環境設定

---

## 18. Shared Package 無獨立版本策略 [P3]

**問題：** `@quant/shared` 目前透過 bun workspace 直接 link，三端永遠同步。當 Web 或 Mobile 需要獨立部署（如 Mobile 送審期間 freeze 版本），無法鎖定 shared 版本。Breaking change 會同時影響所有消費者。

**解決方案：**
- 短期（現狀可接受）：monorepo 內 workspace link，所有變更一起測試一起發布
- 中期：shared 加入 changeset（`@changesets/cli`），major 版本升級時各消費者明確 opt-in
- 長期：若 mobile 獨立發布節奏，考慮 shared 發布到 private npm registry

---

# 三、正面評價

核心架構設計紮實：
- 模組邊界清楚（strategy / risk / execution / data 四層分離）
- 策略只回傳 target weights，不直接下單（關注點分離）
- 風控規則用 pure function factory，非繼承（組合優於繼承）
- 所有金額用 `Decimal`，避免浮點數誤差
- 時間因果性在 feed 層強制執行，回測不會偷看未來資料
- 前端 feature-based 目錄結構，模組化清晰
- Mobile 使用 SecureStore 存儲憑證（比 Web localStorage 更安全）
- 完善的回測分析指標（Sharpe, Sortino, Calmar, Max DD 等）
- 雙語 i18n 支援（Web 端）
- Monorepo 整合完善：`@quant/shared` 以 `ClientAdapter` 注入模式解決跨平台差異，barrel re-export 保持 feature code 不感知底層來源
- WSManager 指數退避重連策略，避免伺服器壓力
