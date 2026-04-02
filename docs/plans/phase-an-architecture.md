# Phase AN：架構整理 + 金融品質補強

> 建立日期：2026-04-02
> 狀態：**已完成**（2026-04-02 大型架構重構完成）
> 優先級：中 — 架構不影響功能但影響長期維護性；金融補強直接影響部署品質
> 前提：Phase AM 完成（已完成）

> **核心原則**：Phase AN 的目標不是增加更多功能，而是提升系統對 live / paper 准入判斷的可信度、降低共享狀態與啟動流程帶來的結構風險，並將研究 alpha 與可交易 alpha 之間的差距顯式化。

> **架構重構約束**：結構可重整，邊界可抽離，但不得在同一步驟中順帶修改既有交易規則、風控規則、回測語意或 execution semantics。若需改行為，應另立變更項目與驗證基準。

> **API contract 原則**：FastAPI OpenAPI schema 是唯一 source of truth。Web、Android、Shared 只能由 schema 生成 client 或做薄封裝。

---

## 0. 動機

系統在兩週內從 0 開發到 ~30,000 LOC，功能完整但邊界開始鬆動。外部三次審查指出：
- **架構面**：app.py 啟動過度集中、全域 singleton 滲透、超大檔案需拆分
- **金融面**：Phase AM 已補齊 cost/regime/capacity/stress 主體，但仍缺公告日可交易性檢查、壓力存活率補強、因子風控量化、benchmark 縱深

Phase AN 分兩條線：架構整理（AN-1~7）+ 金融品質補強（AN-8~15）。

---

## 1. 架構整理

### AN-1：拆 app.py startup（P0）✅ 已完成

**結果**：app.py 從 658 行降到 242 行。抽成：
- `src/api/bootstrap/market.py` (148行) — quote feed、price polling、ShioajiFeed wiring
- `src/api/bootstrap/monitoring.py` (321行) — monitoring loop、kill-switch、scheduler、shutdown
- app.py 保留 create_app()、lifespan orchestrator、路由註冊、WebSocket endpoint

### AN-2：降低 AppState singleton（P1）

**現狀**：`src/api/state.py:200` 的 AppState 被 routes、scheduler、risk 直接存取。

**目標**：改 FastAPI `app.state` + dependency injection。先從 API routes 開始（影響面最小），再逐步替換 scheduler 和 risk。

### AN-3：超大檔案切模組（P1）✅ 已完成

| 檔案 | 原行數 | 拆後行數 | 切法 |
|------|:------:|:--------:|------|
| evaluate.py | 2205 | 維持 | 維持單檔（READ ONLY 安全理由） |
| validator.py | 1951 | **690** | checks/statistical.py(379) + checks/economic.py(390) + checks/descriptive.py(447) |
| jobs.py | 1149 | **501** | pipeline/records.py(416) + pipeline/reconcile.py(219) |
| optimizer.py | 945 | **194** | methods/basic.py(91) + methods/classical.py(199) + methods/advanced.py(490) |
| auto_alpha.py | 1003 | 延後 | 規模可接受，暫不拆 |

**驗收結果**：public API 不變，所有既有測試通過。使用 mixin pattern 保持方法簽名一致。

### AN-4：統一 API contract（P1）

**現狀**：Web（api.ts）、Shared（endpoints.ts）、Android（QuantApiService.kt）各自維護 endpoint。

**目標**：
1. 後端 OpenAPI schema 作為唯一來源（FastAPI 已自動生成）
2. Web：用 openapi-typescript-codegen 從 schema 生成 client
3. Android：用 OpenAPI Generator + Retrofit
4. Shared：生成型別定義，取代手寫

### AN-5：收斂 except Exception（P1）

分三類處理：
- **expected external failure**（API timeout、網路斷線）→ log debug，允許吞
- **data quality issue**（NaN、格式錯）→ 結構化記錄到 audit log
- **invariant breach**（NAV < 0、qty < 0）→ raise TradingInvariantError

掃描 `src/` 所有 `except Exception`，逐一分類。

### AN-6：trading_pipeline domain boundary（P2）

**現狀**：`execute_from_weights` 同時做 overlay、風控、broker、portfolio mutation。

**目標**：明確定義純 domain service（weights → orders → risk decisions），I/O 和 side effects 留在 adapter 層。評估拆分成本 — 目前規模可能不需要完全實作 hexagonal architecture。

### AN-7：文件與編碼整治（P2）

- `.gitattributes` 強制 UTF-8 + LF（✅ 已建立）
- 檢查 PowerShell/Git 編碼設定
- 補「開發入口文件」— 新開發者 10 分鐘內能跑起來

---

## 2. 金融品質補強

### AN-8：公告日可交易性檢查（P0）— **warning-only**

**決策等級**：warning-only（40 天延遲已防護大部分 look-ahead，公告日檢查是額外保險）

**問題**：PIT 用固定 40 天延遲，但沒有檢查再平衡日是否在公告日當天。

**修正**：
- evaluate.py：因子使用 revenue 時，檢查 `as_of` 是否為公告日（每月 1-10 日）。如果是，warning
- Validator：確認 WF 每個 fold 都用 execution_delay=1

### AN-9：壓力存活率補強（P0）

**決策等級**：

| 指標 | 等級 | 說明 |
|------|:----:|------|
| Max consecutive loss months | **reporting metric** | 描述性，不適合做 gate |
| Sharpe without top-20 trades | **warning-only** | 若移除 top-20 後 Sharpe < 0 → 告警 |
| Sharpe at 2× cost | **hard gate** | 已在 cost_2x_safety 實作，此處補強一致性 |

**修正**：在 Validator 的 stress_test 區塊新增 3 個指標。

### AN-10：因子風控量化（P1）

**決策等級**：

| 指標 | 等級 |
|------|:----:|
| 產業 Herfindahl | **warning-only**（HHI > 0.25 告警） |
| 風格暴露 | **warning-only**（\|beta\| > 0.3 告警） |
| 流動性擁擠 | **reporting metric** |
| 財報事件暴露 | **reporting metric** |

**修正**：在 Validator 報告新增 4 個指標。

### AN-11：Benchmark 縱深（P1）— naive baseline 為 **hard gate**

**決策等級**：naive momentum baseline 比較 = **hard gate**（策略若無法穩定優於 naive baseline，不得宣稱為可部署 alpha）

**修正**：固定比較 4 個 benchmark：
1. 0050.TW（大盤 ETF）
2. 月頻再平衡 EW（已有）
3. **同換手率 naive 策略**：隨機選同數量股票，月頻，100 次取中位 Sharpe
4. **同股票池 naive momentum**：12-1 momentum 在同 universe，作為 baseline

### AN-12：Auto Research 因子假說記錄（P1）— **reporting metric**

**問題**：agent 產出因子時不附經濟假說和失效原因。

**修正**：
- program.md 加入：每個因子 commit message 必須包含 `[hypothesis: ...]` 和 `[risk: ...]` 標記
- results.tsv 的 description 欄位已有空間
- learnings.jsonl 的 direction 欄位用於記錄
- Validator 報告加「Economic rationale」欄位（從 agent 的 commit message 提取）

### AN-13：策略家族治理（P1）— **warning-only**（high-vol corr > 0.8 標記 same bet）

**問題**：策略用名稱分類，但金融上應該用風險暴露分群。

**修正**：
- 用 factor_attribution 的 beta_mkt / beta_smb / beta_hml / beta_mom 做 4 維聚類
- 計算策略間在高波動期的相關性（rolling 60d corr when VIX > 75th percentile）
- 結果記錄在 Validator 報告的 factor_attribution 區塊
- 如果兩個「不同」策略在高波動期 corr > 0.8 → 標記「same bet」

### AN-14：持倉流動性報告（P2）— **reporting metric**

**問題**：AM-10 的 capacity 是策略層面的，缺乏持倉層面的流動性報告。

**修正**：Validator 報告加：
- 單檔持倉占 ADV %（p50 / p95 / max）
- 組合換手對 ADV 的衝擊（月度換手金額 / universe median ADV）
- 小型股暴露（持倉中 ADV < 10M TWD 的股票佔比）

### AN-15：公告日集中成交風險（P2）— **reporting metric**

**問題**：月營收公告後隔日（每月 11-12 日），大量策略同時再平衡，造成流動性擁擠。

**修正**：
- 計算策略在每月 11-12 日的換手量 vs 非公告日的換手量比值
- 如果公告日換手 > 非公告日的 3 倍 → 標記「announcement crowding risk」
- 描述性，不做 gate

---

## 2b. Full Project Review 新增項目（2026-04-02 FULL_PROJECT_REVIEW）

### P0（Blockers — live 前必修）

| # | Issue | Review ID | Status | 說明 |
|---|-------|:---------:|:------:|------|
| AN-16 | **Smoke test fail-open** | E-1 | designed | `ops.py:~81` smoke test 拋例外時 trading 繼續。改為 fail-closed：例外 = 阻擋交易 |
| AN-17 | **Graceful shutdown** | P-1 | designed | Server 關閉時未取消未完成訂單、未 flush risk monitor。加 shutdown handler |
| AN-18 | **Lock ordering 文件化** | A-1 | designed | `portfolio.lock`（threading）vs `state.mutation_lock`（asyncio）無正式順序。文件化 + assertion |

### P1（Important — 本月）

| # | Issue | Review ID | Status | 說明 |
|---|-------|:---------:|:------:|------|
| AN-19 | **API input validation** | S-1 | designed | weights dict 接受 NaN/Infinity/negative。加 Pydantic validator decorator |
| AN-20 | **Kill switch race test** | E-3 | implemented | API rebalance + RealtimeRiskMonitor 同時觸發 kill switch 未測試 |
| AN-21 | **submit_orders timeout** | E-5 | implemented | ExecutionService.submit_orders 無 timeout，可能 block event loop |
| AN-22 | **Price limit ±10%** | B-2 | designed | Validator backtest 未強制台股漲跌停。估計高估 CAGR 2-5% |
| AN-23 | **Admin password 強制更換** | C-1 | designed | 預設密碼 Admin1234 無 first-login 強制更換 |
| AN-24 | **DB password 移出 source** | P-3 | implemented | docker-compose.yml 的 DB password 應改為 env-only |
| AN-25 | **2025 OOS loss 歸因報告** | — | implemented | 交付物：歸因報告（分類：regime shift / crowding / cost / data / implementation / benchmark）+ 決策：保留/降權/加 hedge/改 gate/下架 |

### P1b（審批補充項 — 本月）

| # | Issue | Review ID | Status | 說明 |
|---|-------|:---------:|:------:|------|
| AN-37 | **統一 lock 型別** | E-2 | designed | AppState.mutation_lock（asyncio）和 Portfolio.lock（threading）型別不匹配。方案 C 優先：拆分職責，確保同一 lock 不被兩種 runtime 共享 |
| AN-38 | **因子多樣化路線圖** | F-1 | implemented | 目標：6 個月內 ≥1 個非 revenue 因子通過 Validator。追蹤 AM-15 白名單效果。考慮 L3 correlation 按家族分開評估 |
| AN-39 | **WebSocket subscription 權限** | S-3 | designed | per-subscription 權限控制，不允許訂閱無權限的 symbol/channel |

#### AN-38 Detail: Factor Diversification Roadmap

- **Target**: ≥1 non-revenue factor passing Validator within 6 months
- **Track AM-15 whitelist effect**: monitor L2 pass rate by factor family after whitelist enforcement
- **L3 correlation by family**: revenue factors cluster naturally; consider not penalizing cross-family correlation (i.e., evaluate L3 correlation threshold separately for same-family vs cross-family pairs)
- **Success metric**: at least 1 factor from value / quality / low-vol family reaches L4+

### P2（Hardening — 下月）

| # | Issue | Review ID | Status | 說明 |
|---|-------|:---------:|:------:|------|
| AN-26 | **Broker reconnect backoff** | E-6 | designed | SinopacBroker 重連用固定間隔，改指數退避 |
| AN-27 | **Market data bounded queue** | A-2 | designed | tick callback queue 無上限，高量交易可能 OOM |
| AN-28 | **Reconnect thread leak** | A-3 | designed | SinopacBroker._reconnect_thread 未在 shutdown 時 join |
| AN-29 | **Docker resource limits** | P-2 | designed | docker-compose 無 CPU/memory 上限 |
| AN-30 | **Log aggregation** | P-4 | designed | 日誌只有 stdout，container 重啟即遺失 |
| AN-31 | **Survivorship bias data** | B-1 | designed | Yahoo 缺下市股。取得 TWSE 下市股歷史或 FinLab 完整數據 |
| AN-32 | **Per-user rate limiting** | S-2 | designed | API rate limit 是全域的，應改為 per-user |
| AN-33 | **E2E test expansion** | — | designed | 缺 paper→live、broker reconnect、kill switch liquidation、crash recovery 場景 |

### P1c（流程治理 — 審批補充 5-8）

| # | 項目 | Status | 說明 |
|---|------|:------:|------|
| AN-40 | **Phase completion criteria** | implemented | 每個項目標註狀態 designed/implemented/verified/deployed。hard gate 項目必須有測試。架構重構必須有行為未改變的對照 |
| AN-41 | **Regression protection matrix** | implemented | 列出關鍵風險（startup lifecycle / kill switch race / order timeout / PIT / price limit / benchmark gate）與對應保護（測試 / assertion / monitoring） |
| AN-42 | **Unified validation report schema** | designed | 所有 hard gate / warning / metric 統一輸出到同一份 JSON report。固定欄位 + timestamp + config fingerprint + universe + decision (pass/pass-with-warning/fail) |
| AN-43 | **Validation methodology versioning** | designed | gate 定義變更有版本號。報告記錄 validator version。方法學升級後定義是否需 revalidate。AM 既有通過策略標示 grandfathered 或 mandatory revalidation |
| AN-44 | **Promotion policy** | designed | research→paper：滿足所有 hard gate。paper→live：hard gate + 30 天 paper（Phase AL G1-G6）+ 0 invariant violation。hard gate 失敗：降級。≥3 warning 累積：凍結 promotion |

#### AN-41 Detail: Regression Protection Matrix

| Risk | Protection |
|------|-----------|
| Startup lifecycle | `test_server_startup` integration test |
| Kill switch race | AN-20 test (`test_concurrent_kill_switch_and_rebalance`) |
| Order timeout | AN-21 30s guard in `submit_orders` |
| PIT correctness | 40-day delay enforcement + AN-8 announcement date check |
| Price limit | AN-22 ±10% enabled in Validator backtest |
| Benchmark gate | AN-11 naive momentum baseline as hard gate |

### Ongoing

| # | 項目 | Status | 說明 |
|---|------|:------:|------|
| AN-34 | Autoresearch L1 pass rate 追蹤 | ongoing | 按因子家族分類，監控是否 stall |
| AN-35 | 每月 Validator gate review | ongoing | 門檻是否仍合適 |
| AN-36 | 每季安全審計 | ongoing | auth、API key rotation、WebSocket 權限 |

---

## 3. 施做順序

```
── P0 Blockers（live 前必修）──
AN-16（smoke test fail-closed）→ AN-17（graceful shutdown）→ AN-18（lock ordering）
  ↓
AN-8 → AN-9（金融 P0：公告日 + 壓力補強）
  ↓
── P1 Important（本月）──
AN-37（lock 型別統一）→ AN-19（API validation）→ AN-22（price limit ±10%）
  ↓
AN-25（OOS 歸因報告）→ AN-5（except 分類）→ AN-20 + AN-21（kill switch + timeout）
  ↓
AN-10 → AN-11（金融 P1：因子風控 + benchmark）
  ↓
AN-12 → AN-13（金融 P1：假說 + 家族治理）
  ↓
AN-23 → AN-24（admin password + DB secret）
  ↓
── P2 Hardening（下月）──
AN-3（拆檔案）→ AN-1 → AN-2（拆 app.py + singleton）→ AN-4（API contract）
  ↓
AN-26 → AN-28（broker hardening）→ AN-29 → AN-30（Docker + logs）
  ↓
AN-38（因子多樣化路線圖）
  ↓
AN-14 → AN-15（金融 P2：持倉流動性 + 公告擁擠）
  ↓
AN-31（survivorship data：至少完成設計與替代方案判定）
  ↓
AN-40 → AN-41（completion criteria + regression matrix，先定義再施做）
  ↓
AN-42 → AN-43 → AN-44（report schema + versioning + promotion policy）
  ↓
AN-39（WebSocket 權限）→ AN-33（E2E tests）→ AN-6（domain boundary）
```

**原則：P0 blockers 最先（live 前必修），P1 本月完成，P2 下月。**

---

## 4. 成功標準

### P0 Blockers
- [ ] Smoke test 例外 = 阻擋交易（fail-closed）
- [ ] Server shutdown 時取消未完成訂單 + flush risk monitor
- [ ] Lock ordering 文件化（portfolio.lock → mutation_lock 順序明確）

### 架構
- [ ] 最大檔案 < 500 行（evaluate.py 除外）
- [ ] API routes 不直接存取全域 singleton
- [ ] 三份客戶端 endpoint 從 OpenAPI schema 生成
- [ ] `src/` 中 `except Exception: pass` 數量 < 10（交易路徑為 0）
- [ ] 新開發者入門文件存在且可用
- [ ] API input validation 擋 NaN/Infinity/negative weights

### 金融品質
- [ ] 每個金融檢查標註決策等級（hard gate / warning-only / reporting metric）
- [ ] 每個策略報告含公告日可交易性檢查結果
- [ ] 壓力存活率含 max consecutive loss months + top-20 removed Sharpe + 2× cost Sharpe
- [ ] 因子風控含產業 Herfindahl + 風格暴露 + 流動性擁擠指標
- [ ] 固定比較 4 個 benchmark（0050 / EW / naive random / naive momentum）
- [ ] naive baseline 為 hard gate（策略若無法穩定優於 naive momentum，不得部署）
- [ ] 策略家族用風險暴露分群（非名稱），high-vol corr > 0.8 標記 same bet
- [ ] Auto Research 每個因子附經濟假說和失效原因
- [ ] Validator backtest 強制台股 ±10% 漲跌停
- [ ] 2025 OOS loss 歸因報告完成（含明確決策：保留/降權/下架）
- [ ] ≥1 個非 revenue 因子家族通過 Validator（6 個月目標）
- [ ] lock 型別統一（asyncio vs threading 不共享）

### 流程治理
- [ ] 每個 AN 項目有明確狀態標註（designed / implemented / verified / deployed）
- [ ] Regression protection matrix 存在且覆蓋所有 P0 風險
- [ ] Unified validation report schema 定義完成，所有驗證輸出到同一份 JSON
- [ ] Validator methodology 有版本號，報告記錄版本
- [ ] Promotion policy 文件化（research→paper→live 升降級規則明確）

### 生產安全
- [ ] submit_orders 有 timeout
- [ ] Broker reconnect 指數退避
- [ ] Market data queue 有上限
- [ ] Docker 有 CPU/memory limits
- [ ] DB password 不在 source control

---

## 5. 與外部審查的對應

| 外部建議 | 對應項目 | 來源 |
|---------|---------|:----:|
| 拆 app.py bootstrap | AN-1 | 架構審查 #1 |
| 降低 singleton | AN-2 | 架構審查 #1 |
| 超大檔案切模組 | AN-3 | 架構審查 #2 |
| 統一 API contract | AN-4 | 架構審查 #2 |
| 收斂 except Exception | AN-5 | 架構審查 #2 |
| domain boundary | AN-6 | 架構審查 #2 |
| 文件編碼 | AN-7 ✅ | 架構審查 #2 |
| 公告日 alpha 幻覺 | AN-8 | 金融審查 #3 |
| 連續虧損 / top-20 / 2× cost | AN-9 | 金融審查 #5 |
| 因子風控 | AN-10 | 金融審查 #6 |
| benchmark 縱深 | AN-11 | 金融審查 #7 |
| 因子假說記錄 | AN-12 | 金融審查 #8 |
| 策略家族治理 | AN-13 | 金融審查 #4 |
| 持倉流動性報告 | AN-14 | 金融審查 #2 |
| 公告日集中成交 | AN-15 | 金融審查 #3 |
| Smoke test fail-open | AN-16 | Review E-1 |
| Graceful shutdown | AN-17 | Review P-1 |
| Lock ordering | AN-18 | Review A-1 |
| API input validation | AN-19 | Review S-1 |
| Kill switch race | AN-20 | Review E-3 |
| submit_orders timeout | AN-21 | Review E-5 |
| Price limit ±10% | AN-22 | Review B-2 |
| Admin password | AN-23 | Review C-1 |
| DB password in source | AN-24 | Review P-3 |
| 2025 OOS root cause | AN-25 | Review §13 |
| Broker backoff | AN-26 | Review E-6 |
| Bounded queue | AN-27 | Review A-2 |
| Thread leak | AN-28 | Review A-3 |
| Docker limits | AN-29 | Review P-2 |
| Log aggregation | AN-30 | Review P-4 |
| Survivorship data | AN-31 | Review B-1 |
| Per-user rate limit | AN-32 | Review S-2 |
| E2E test expansion | AN-33 | Review §8 |
| async/sync lock mismatch | AN-37 | Review E-2 + 補充 1 |
| 因子多樣化路線圖 | AN-38 | Review F-1 + 補充 3 |
| WebSocket subscription 權限 | AN-39 | Review S-3 + 補充 4 |
| net alpha 優先 | **AM-8 已做** | 金融審查 #1 |
| capacity/liquidity | **AM-10 已做** | 金融審查 #2 |
| factor decomposition | **AM-18 已做** | 金融審查 #4 |
| 搜索空間限制 | **AM-15 已做** | 金融審查 #8 |
---

## 6. 審批意見（2026-04-02）

### 審批結論

**Approved with conditions.**

本計畫方向正確，且對目前系統的兩個核心問題有直接對應：
1. 工程面：啟動流程、全域狀態、超大模組、例外處理與 API contract 分散，已開始拖累可維護性與上線風險。
2. 金融面：研究 alpha、可交易 alpha、容量、擁擠、事件時點正確性與基準比較之間，仍存在明顯落差，需透過 validator / benchmark / attribution / crowding 機制補齊。

Phase AN 同時處理架構整治、金融驗證補強與既有 review blockers，在目前脈絡下是合理的，因為三者並非彼此獨立問題，而是共同決定 paper/live 准入品質的同一條鏈路。

### 核准理由

1. **議題選取準確**
   - AN-1~AN-7 直指當前程式結構的主要維護風險，尤其 `app.py` startup、`AppState` singleton、超大檔案與 API contract 分散，都是已經在當前 codebase 中觀察到的真實問題。
   - AN-8~AN-15 補的不是「更多功能」，而是把研究結果轉為可交易決策所需的金融約束，這個方向正確。
   - AN-16~AN-36 與既有 review finding 對齊，讓 phase 不只是新想法，而是對既有審查結果的閉環處理。

2. **金融優先級合理**
   - 計畫有抓到真正重要的金融缺口：PIT / look-ahead、防 lucky-hit、成本放大敏感度、基準比較、因子暴露拆解、容量與公告擁擠。
   - 這些項目比新增策略、擴大 universe、增加回測報表更值得優先處理。

3. **架構整治方向合理**
   - `bootstrap` 拆分、狀態注入、OpenAPI 單一真源、超大模組拆解、domain boundary 收斂，這些都屬於高價值整治，而不是形式上的重構。
   - 若做得對，會直接降低 live/paper 路徑的事故率與回歸成本。

### 審批條件

下列條件建議在執行前補進文件，作為正式的 phase 驗收標準：

1. **所有金融檢查需標註決策等級**
   - 每個 AN-8~AN-15 條目都應明確標示為：
     - `hard gate`: 不通過不得進 paper/live
     - `warning-only`: 僅告警，不阻擋
     - `reporting metric`: 純報告欄位
   - 原因：若不先定義，後續容易做成報表擴充，而不是准入標準升級。

2. **API contract 必須指定唯一真源**
   - 建議明定：**FastAPI OpenAPI schema 是唯一 source of truth**。
   - Web、Android、Shared 只能由 schema 生成 client 或做薄封裝，不再各自手寫與維護 endpoint 定義。

3. **架構重構不得順帶改變交易語意**
   - AN-1、AN-2、AN-6 在執行時，需補一條原則：
     - 結構可重整
     - 邊界可抽離
     - 但不得在同一步驟中順帶修改既有交易規則、風控規則、回測語意或 execution semantics
   - 若需改行為，應另立變更項目與驗證基準。

4. **AN-25 需改為可驗收交付物**
   - 目前「2025 OOS loss root cause」方向正確，但仍偏像研究題目。
   - 建議補成以下交付：
     - 一份 OOS 失效歸因報告
     - 主因分類：regime shift / crowding / cost underestimate / data issue / implementation bias / benchmark illusion
     - 明確決策：保留、降權、加 hedge、改 gate、或下架

### 對內容的具體評語

#### A. 架構面

1. **AN-1 / AN-2 值得優先**
   - `app.py` startup 與 `AppState` singleton 是目前系統最明顯的結構瓶頸。
   - 這兩項不是單純程式美化，而是為了降低初始化順序錯誤、共享狀態競態、測試隔離困難與 lifecycle 管理失控。

2. **AN-3 的目標合理，但建議補驗收方式**
   - 目前已有大檔清單與拆分方向，這很好。
   - 建議再補：
     - 每個檔案拆分後的最大行數目標
     - 是否要求新增模組測試
     - 是否要求 public API 不變

3. **AN-4 是必要項，不建議只做一半**
   - 若只生成 web client，但 Android 與 shared 仍手寫，問題不會真正消失。
   - 這項應一次做完整，否則寧可先不宣稱完成。

4. **AN-5 要求合理**
   - 但建議文件補一點：不是要求 `except Exception` 全部消失，而是要求「吞例外必須有分類與理由」。
   - 對交易系統來說，沉默失敗比明確降級更危險。

5. **AN-6 很重要，但應避免過度理想化**
   - `trading_pipeline` 的 domain boundary 重整有必要。
   - 但建議執行時先以「可驗證的純邏輯抽離」為主，不要一次引入過重的抽象層，否則會拉高改動面。

#### B. 金融面

1. **AN-8 是本 phase 最關鍵的金融條目之一**
   - 事件時點正確性若沒有做嚴格，後面所有 alpha 評估都不可靠。
   - 這項應被視為準入底線，而不是附加優化。

2. **AN-9 設計合理**
   - `max consecutive loss months`、`Sharpe without top-20 trades`、`Sharpe at 2x cost` 都是高價值檢查。
   - 它們能有效過濾只靠少數幸運樣本支撐的策略。

3. **AN-10 / AN-13 的方向正確**
   - 這兩項本質上是在問：策略實際上在賭什麼。
   - 對現階段系統來說，這比增加更多策略數量更重要。

4. **AN-11 benchmark 強化值得支持**
   - 與 0050、EW universe、naive baseline 比較，能避免把一般風格暴露誤判成獨特 alpha。
   - 建議在文件中補一句：若策略無法穩定優於 naive baseline，則不得宣稱為可部署 alpha。

5. **AN-12 Auto Research 約束很有必要**
   - 自動生成因子最缺的通常不是候選數量，而是經濟假說與風險敘述。
   - 將 hypothesis / risk / learning 納入產物，是正確方向。

6. **AN-14 / AN-15 具有實盤價值**
   - 容量與公告擁擠是台股策略最容易被低估的交易現實。
   - 這兩項做進 validator，會比只在研究報告中口頭提醒更有約束力。

#### C. P0 / P1 / P2 review items

1. **P0 blockers 的定義合理**
   - smoke test fail-open、graceful shutdown、lock ordering 都屬於應明確封口的風險。
   - 這些應視為 live eligibility 的必要條件。

2. **AN-19~AN-24 放在 P1 合理**
   - input validation、kill switch race test、submit timeout、price limit、admin password、DB secret，都屬於高價值補強。
   - 其中 `submit_orders timeout` 與 `kill switch race` 的重要性實際上接近 P0，執行時建議提早處理。

3. **AN-31 survivorship bias data 很重要**
   - 這不是純資料層 housekeeping，而是會直接影響金融結論可信度。
   - 雖列在 P2，但其金融影響高，建議至少在 phase 內完成設計與替代方案判定。

### 建議補充到文件中的一句原則

建議在本文件前段新增以下原則：

> Phase AN 的目標不是增加更多功能，而是提升系統對 live / paper 准入判斷的可信度、降低共享狀態與啟動流程帶來的結構風險，並將研究 alpha 與可交易 alpha 之間的差距顯式化。

### 最終審批結論

本計畫**批准執行**。

但批准基礎是：
- 金融檢查需區分 hard gate / warning-only / reporting metric
- OpenAPI schema 需被明定為 API contract 唯一真源
- 架構重構需以不改變既有交易與風控語意為原則
- AN-25 需改成可驗收交付物

在補齊以上條件後，Phase AN 可以作為下一階段的正式執行計畫。

---

## 7. 補充審查意見（2026-04-02，Full Project Review 後）

基於 `docs/reviews/system/FULL_PROJECT_REVIEW_20260402.md` 的全專案審查，對本計畫提出以下 4 點補充：

### 補充 1：E-2 async/sync lock 混用應獨立列項

AN-18 處理的是 lock ordering 文件化，但 Review E-2 指出的問題是**型別不匹配**：`AppState.mutation_lock` 是 `asyncio.Lock`，`Portfolio.lock` 是 `threading.Lock`。這是兩個不同問題：

- AN-18（ordering）：誰先拿誰 → 文件化即可
- E-2（type mismatch）：threading 程式碼等待 asyncio.Lock 是 undefined behavior → 需要重構

建議新增 **AN-37：統一 lock 型別**，歸類為 P0 或 P1。可行方案：
- 方案 A：全部改 `threading.Lock`（簡單，但失去 async 讓出控制權的好處）
- 方案 B：統一為 `asyncio.Lock`，同步路徑用 `asyncio.run_coroutine_threadsafe()` 包裝
- 方案 C：拆分職責，確保同一個 lock 不被兩種 runtime 共享

### 補充 2：審批條件 1 尚未回填至 AN-8~AN-15

審批明確要求每個金融檢查標註決策等級（hard gate / warning-only / reporting metric），但目前 AN-8~AN-15 的描述中均未標註。建議開發團隊在開始實作前先完成分級，否則會做成報表擴充而非准入標準升級。

初步建議分級（供討論）：

| 項目 | 建議等級 | 理由 |
|------|:--------:|------|
| AN-8 公告日可交易性 | warning-only | 40 天延遲已防護大部分 look-ahead，公告日檢查是額外保險 |
| AN-9 max consecutive loss | reporting metric | 描述性，不適合做 gate |
| AN-9 Sharpe without top-20 | warning-only | 若移除 top-20 後 Sharpe < 0 應告警 |
| AN-9 Sharpe at 2× cost | hard gate | 已在 Validator cost_2x_safety 實作，此處是補強 |
| AN-10 產業 Herfindahl | warning-only | HHI > 0.25 告警（前 3 產業過度集中）|
| AN-10 風格暴露 | warning-only | |beta| > 0.3 告警 |
| AN-10 流動性擁擠 | reporting metric | |
| AN-10 財報事件暴露 | reporting metric | |
| AN-11 naive baseline 比較 | hard gate | 策略應穩定優於 naive momentum，否則不可稱 alpha |
| AN-12 因子假說記錄 | reporting metric | 提升研究品質，不阻擋部署 |
| AN-13 策略家族分群 | warning-only | high-vol corr > 0.8 標記 same bet |
| AN-14 持倉流動性 | reporting metric | |
| AN-15 公告日擁擠 | reporting metric | |

### 補充 3：因子多樣化策略缺對應項目

Review 指出所有 4 個部署因子均為 revenue 家族（🟠 HIGH），PBO 多樣性不足。AN-13 是分群機制（被動觀測），但缺乏主動推動多樣化的項目。

建議新增 **AN-38：因子多樣化路線圖**（P1），內容：
- 定義目標：至少 3 個不相關因子家族通過 L5（revenue / value / quality / low-vol）
- 調整 L3 correlation 門檻（0.65 → 0.70 或按家族分開評估）
- Autoresearch program.md 的 5 家族白名單（AM-15 已做）效果追蹤
- 成功標準：6 個月內至少 1 個非 revenue 因子通過 Validator

### 補充 4：WebSocket per-subscription 權限控制未納入

Review S-3 指出 WebSocket 認證只檢查 JWT 有效性，不做 per-subscription 權限控制，用戶可訂閱任意 symbol/alert channel。

建議歸入 AN-36（每季安全審計）的具體檢查項，或獨立為 **AN-39：WebSocket subscription 權限**（P2）。

### 補充 5：建議補「完成定義」與「回歸保護」

目前 Phase AN 已經同時承載架構重整、金融驗證補強、live blockers 修補與 review follow-up。這種做法可以接受，但文件裡還可以再補兩層執行保護，讓 phase 的完成不是主觀判斷。

建議新增 **AN-40：Phase completion criteria**，至少包含以下條件：
- 每個 AN 項目都需標註狀態：`designed / implemented / verified / deployed`
- 每個 `hard gate` 項目都需有對應測試或驗證產物
- 每個架構重構項目都需有「行為未改變」的對照驗證
- 每個 P0/P1 live risk 項目都需有明確的 close evidence，而不是只有 code merged

建議新增 **AN-41：Regression protection matrix**，把本 phase 的關鍵風險與對應保護列出：
- startup / shutdown lifecycle
- kill switch race
- order submission timeout
- price limit / execution delay semantics
- PIT / announcement timing correctness
- benchmark / naive baseline gate
- Auto Research 輸出完整性

如果沒有這層 matrix，Phase AN 很容易變成「做了很多修正」，但難以證明它們在後續變更中持續有效。

### 補充 6：建議把金融驗證輸出標準化

AN-8~AN-15 現在的方向是對的，但若各項結果分散在 validator、stress test、factor attribution、研究報告、manual notes 中，後續很難作為真正的准入基準。

建議新增 **AN-42：Unified validation report schema**：
- 將 hard gate / warning / reporting metric 統一輸出到同一份 report
- 報告欄位固定，便於 paper/live 准入比較
- 每次策略驗證都保留 timestamp、config fingerprint、universe、benchmark set、cost assumptions
- 同一份報告中明確標出 `decision: pass / pass-with-warning / fail`

這樣 AN-8~AN-15 不會只是零散補強，而會真正變成交易決策系統的一部分。

### 補充 7：建議補「方法學版本化」

Phase AN 已經開始動到 validator gate、benchmark、cost safety、factor decomposition、crowding 與 OOS root-cause。這些都屬於方法學，不只是程式碼。

建議新增 **AN-43：Validation methodology versioning**：
- 每次 gate 定義變更需有版本號
- 報告需記錄 validator methodology version
- 若策略是用舊版本驗證通過，當方法學升級後需定義是否要 revalidate
- 對 AM 既有通過策略，需清楚標示 `grandfathered` 或 `mandatory revalidation`

沒有這一層，之後很容易出現同一策略在不同時間點「都叫通過」，但其實是用不同標準通過。

### 補充 8：建議補 live / paper promotion policy

文件目前已經補強很多 paper/live 准入因素，但還缺一條最終決策規則：什麼情況可以從 research 進 paper，什麼情況可以從 paper 進 live。

建議新增 **AN-44：Promotion policy**：
- research -> paper：需滿足哪些 hard gate
- paper -> live：除研究與回測外，還需滿足哪些運營條件
- 任一 hard gate 失敗後，是降級、凍結還是下架
- warning-only 項目累積到什麼程度時，也要阻止 promotion

這一條若不補，AN-8~AN-15 即使都完成，也可能停留在「資訊完整」，但沒有轉成真正的升降級機制。
