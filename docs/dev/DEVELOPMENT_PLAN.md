# 開發計畫書

> **版本**: v4.5
> **日期**: 2026-03-26
> **目標**: 涵蓋多個可自動交易市場的投資組合研究與優化系統
> **可交易市場**: 台股、美股、ETF（含債券/商品 ETF 代理）、台灣期貨、美國期貨
> **不納入**: 直接債券交易（OTC）、實體商品、零售外匯
> **架構設計**: `docs/dev/MULTI_ASSET_ARCHITECTURE.md`

---

## 階段概覽

```
Phase A ✅       Phase B ✅       Phase C ✅       Phase D ✅       Phase E ✅           Phase F ✅         Phase G ✅
基礎設施          跨資產 Alpha     組合最佳化        系統整合+風控     實盤交易              自動化 Alpha       學術基準升級
─────────       ────────────    ─────────       ─────────       ─────────           ─────────         ─────────
Instrument      宏觀因子模型      6 種最佳化器     MultiAssetStrategy  Shioaji 券商對接     每日排程引擎       VaR/CVaR+最佳化
多幣別 Portfolio  跨資產信號       風險模型(LW)     跨資產風控規則      Paper Trading       因子自動篩選       Robust/Resampled
DataFeed 擴展   戰術配置引擎      幣別對沖         FX per-bar 修復    即時行情(tick)       Regime 調適       GARCH/Factor Cov
FRED 數據源     API + 前端型別                    Alpha層強化        IB 美股(第二階段)    績效回饋循環       PBO/Randomized
管線整合                                         因子/型別同步       EOD 對帳             安全熔斷          共整合+回測防護
```

---

## Phase A~D：已完成摘要

### Phase A：多資產基礎設施 ✅
InstrumentRegistry (自動推斷) + 多幣別 Portfolio (`nav_in_base`, `currency_exposure`) + DataFeed 擴展 (FX time series) + FRED 數據源 + 管線整合 (weights_to_orders 乘數, SimBroker per-instrument 費率) + 模型統一

### Phase B：跨資產 Alpha ✅
`src/allocation/`: MacroFactorModel (成長/通膨/利率/信用) + CrossAssetSignals (動量/波動率/均值回歸) + TacticalEngine (戰略 + 宏觀 + 跨資產 + regime → 資產類別權重) + `POST /api/v1/allocation`

### Phase C：組合最佳化 ✅
`src/portfolio/`: PortfolioOptimizer (EW/IV/RP/MVO/BL/HRP) + RiskModel (Ledoit-Wolf 收縮共變異數 + 風險貢獻) + CurrencyHedger (分級對沖)

### Phase D：系統整合 + 風控 ✅
- MultiAssetStrategy (`src/strategy/multi_asset.py`): 兩層配置策略，已註冊至 registry
- 跨資產風控: `max_asset_class_weight`, `max_currency_exposure`, `max_gross_leverage`
- Bug fixes: FX per-bar 更新 / 總權重驗證 / FRED ffill(66)
- 前端: AllocationPage + 11 因子同步 + 跨資產風控規則 + i18n (en/zh)
- Alpha 層強化: 5 新技術因子 (reversal/illiquidity/ivol/skewness/max_ret) + Rolling IC 動態加權 + 市場環境分析 (`src/alpha/regime.py`) + 因子歸因 (`src/alpha/attribution.py`)

---

## Phase E：實盤交易（當前目標）

> 券商：台股使用 **永豐金 Shioaji** SDK（評估見 `docs/dev/BROKER_API_EVALUATION.md`）
> 認證方式：API Key + Secret Key → CA 憑證啟用（`.pfx`） → 下單
> 模擬模式：`sj.Shioaji(simulation=True)` 可完整測試下單/行情/帳務
> SDK Skill 參考：`shioaji` skill（完整 API 文檔）

### E1: SinopacBroker 核心 ✅

| 檔案 | 內容 | 狀態 |
|------|------|------|
| `src/execution/sinopac_broker.py` | `SinopacBroker(BrokerAdapter)` — 封裝 Shioaji SDK | ✅ |
| `src/execution/sinopac_quote.py` | 即時行情訂閱 — tick/bidask callback → TickData/BidAskData | ✅ |
| `src/execution/execution_service.py` | 模式路由：backtest → SimBroker, paper/live → SinopacBroker | ✅ |
| `src/execution/market_hours.py` | 台股交易時段驗證 + 盤外委託佇列 | ✅ |
| `src/execution/reconcile.py` | EOD 持倉對帳 + 自動修正 | ✅ |
| `src/api/routes/execution.py` | 6 個 Execution API 端點 | ✅ |
| `tests/unit/test_sinopac_*.py` | 83 tests（全部 mock SDK） | ✅ |

**SDK 認證**（已對齊官方 API）:
```python
api = sj.Shioaji(simulation=True)
api.login(api_key="YOUR_KEY", secret_key="YOUR_SECRET")
api.activate_ca(ca_path="/path/to/Sinopac.pfx", ca_passwd="PASSWORD")
```

**委託類型映射**（已實作）:

| 本專案 | Shioaji 常數 |
|--------|-------------|
| `OrderType.MARKET` | `sj.constant.StockPriceType.MKT` |
| `OrderType.LIMIT` | `sj.constant.StockPriceType.LMT` |
| `Side.BUY / SELL` | `sj.constant.Action.Buy / Sell` |
| 整股 | `sj.constant.StockOrderLot.Common` |
| 盤中零股 | `sj.constant.StockOrderLot.IntradayOdd` |
| ROD/IOC/FOK | `sj.constant.OrderType.ROD / IOC / FOK` |

**回報機制**（已實作）:
```python
# OrderState 分發: StockOrder → 委託回報, StockDeal → 成交回報
api.set_order_callback(lambda stat, msg: ...)
```

### E2: 即時行情整合

填補 WebSocket `market` 頻道，連接 Shioaji 即時行情。

| 元件 | 說明 | 狀態 |
|------|------|------|
| `SinopacQuoteManager` | tick/bidask 訂閱 + callback → TickData | ✅ 架構 |
| WS broadcast | `market` 頻道接收 tick → 廣播前端 | 待整合 |
| 前端 MarketTicker | 接收 WebSocket market 頻道 | 待實作 |

**Shioaji 行情 Callback**（已對齊官方 API）:
- 股票: `api.quote.set_on_tick_stk_v1_callback(fn)` / `set_on_bidask_stk_v1_callback(fn)`
- 期貨: `api.quote.set_on_tick_fop_v1_callback(fn)` / `set_on_bidask_fop_v1_callback(fn)`
- 事件: `@api.quote.on_event` — 斷線(2)/重連(4)/訂閱成功(16)

**待實作**:
- [ ] WS `market` 頻道整合 `SinopacQuoteManager.to_ws_payload()`
- [ ] 自動重訂閱（`event_code == 4` → `resubscribe_all()`）
- [ ] 盤中零股行情（`intraday_odd=True`）

### E3: Paper Trading 完整循環

使用 Shioaji `simulation=True` 模式的完整交易循環。

**流程**:
```
排程觸發 (scheduler)
  → Strategy.on_bar(ctx) → target weights
    → weights_to_orders() → list[Order]
      → RiskEngine.check_orders() → approved orders
        → ExecutionService.submit_orders()
          → SinopacBroker(simulation=True).submit_order()
            → set_order_callback → Order 狀態更新
              → apply_trades() → Portfolio 更新
                → EOD reconcile() → 對帳
                  → 通知 (Discord/LINE/Telegram)
```

| 子任務 | 說明 | 狀態 |
|--------|------|------|
| ExecutionService 路由 | backtest/paper/live 模式切換 | ✅ |
| EOD 對帳 | `reconcile()` + `auto_correct()` | ✅ |
| 交易時段管理 | 盤前/盤中/零股/定盤 + 佇列 | ✅ |
| 排程整合 | `src/scheduler/` daily rebalance job | 待實作 |
| 績效記錄 | 每日 NAV + 持倉快照 → DB | 待實作 |
| Paper Trading API | `/api/v1/execution/paper-trading/status` | ✅ |
| 交割查詢整合 | `api.settlements()` → 交割金額/日期 | 待實作 |

### E4: Shioaji 進階功能（新增）

基於 SDK 完整文檔，以下功能對專案有直接價值：

#### E4a: Shioaji 歷史數據源

Shioaji 提供 2020-03-02 起的 1 分鐘 K 棒和逐筆 tick，可作為新的 `DataFeed` 實作。

| 功能 | API | 價值 |
|------|-----|------|
| 歷史 K 棒 | `api.kbars(contract, start, end)` | 1 分鐘級回測 |
| 歷史 Tick | `api.ticks(contract, date)` | 微觀結構研究 |
| 即時快照 | `api.snapshots(contracts)` (max 500) | 批量定價 / Portfolio 估值 |
| 連續期貨 | `api.Contracts.Futures.TXF.TXFR1` | 期貨回測無縫接續 |

**實作**: `src/data/sources/shioaji_feed.py` 實作 `DataFeed` ABC。
**優勢**: 比 Yahoo Finance 更低延遲，且為 broker 原生數據。

#### E4b: 市場掃描器（Universe Filter）

Shioaji Scanner 可動態篩選交易標的，整合至 Alpha Pipeline 的 universe filtering。

```python
# 漲幅排行 / 成交量排行 / 成交金額排行 / 振幅排行
api.scanners(scanner_type=sj.constant.ScannerType.VolumeRank, count=50)
```

**實作**: `src/data/scanner.py` — 每日開盤前自動更新活躍股票清單。
**整合點**: `AlphaStrategy` 的 universe 參數可從 scanner 動態產生。

#### E4c: 額度與風控整合

| API | 用途 | 整合點 |
|-----|------|--------|
| `api.trading_limits()` | 可用交易額度 / 融資融券額度 | 下單前預檢 |
| `api.account_balance()` | 可用餘額 | RiskEngine 資金檢查 |
| `api.settlements()` | T+N 交割金額/日期 | pending_settlements 同步 |
| `api.credit_enquires()` | 融資融券餘額 | 信用交易監控 |
| `api.punish()` / `api.notice()` | 處置股/注意股 | 自動排除風險標的 |

#### E4d: 融資融券與當沖

擴展 `Order` 模型支援 Shioaji 信用交易條件：

| 條件 | Shioaji 常數 | 場景 |
|------|-------------|------|
| 現股 | `StockOrderCond.Cash` | 預設 |
| 融資 | `StockOrderCond.MarginTrading` | 槓桿多頭 |
| 融券 | `StockOrderCond.ShortSelling` | 空頭策略 |
| 現股當沖 | `daytrade_short=True` | 日內交易 |

**需求**: 擴展 `src/domain/models.py` 新增 `OrderCondition` 枚舉。

#### E4e: 非阻塞下單

Shioaji `timeout=0` 模式讓下單延遲從 ~136ms 降至 ~12ms（12x 加速），對批量 rebalance 至關重要。

```python
trade = api.place_order(contract, order, timeout=0)  # 立即返回
# 結果由 set_order_callback 推送
```

**實作**: `SinopacBroker.submit_order()` 預設使用 `timeout=0` + callback。

#### E4f: 觸價委託（Stop Orders）

利用 tick callback 實現軟體層的 stop-loss / stop-profit：

**實作**: `src/execution/stop_order.py` — 監聽 tick，觸發價位到達時自動下單。
**整合點**: RiskEngine kill switch 可透過 stop order 即時平倉。

### E5: 期貨/選擇權交易

利用 Shioaji 完整的期貨選擇權 API：

| 功能 | 說明 |
|------|------|
| 期貨下單 | `FuturesPriceType.LMT/MKT` + `FuturesOCType.Auto/Cover` |
| 選擇權下單 | Call/Put + 買權/賣權 |
| 組合單 | `ComboContract` + `ComboOrder` (價差/跨式/勒式) |
| 期貨展期 | 連續合約 R1/R2 + 自動 roll |
| 夜盤 | `market_type: "Night"` |

**依賴**: InstrumentRegistry 已支援 `AssetClass.FUTURE / OPTION`。

### E6: IB 美股對接（第二階段）

| 市場 | 券商 | SDK | 狀態 |
|------|------|-----|------|
| 美股 | Interactive Brokers | ib_insync | 待實作（Shioaji 完成後） |

`src/execution/ib_broker.py`: 實作 `IBBroker(BrokerAdapter)`。

### E7: 擴展績效歸因

擴展 `src/alpha/attribution.py`: 資產配置歸因 + 選股歸因 + 匯率歸因。

### Phase E 完成標誌

能在台股上執行完整的 Paper Trading 循環：
1. 策略產出權重 → 2. Shioaji 模擬下單 (timeout=0) → 3. 即時行情更新 → 4. 成交回報 callback → 5. 持倉同步 → 6. EOD 對帳 → 7. 交割查詢 → 8. 績效報告

---

## Phase F：自動化 Alpha 研究系統（下一階段）

> 架構設計：`docs/dev/AUTOMATED_ALPHA_ARCHITECTURE.md`

### F1: 核心引擎（`src/alpha/auto/`）

將手動 Alpha 研究流程自動化為每日排程驅動的閉環系統。

| 子任務 | 檔案 | 說明 | 狀態 |
|--------|------|------|------|
| F1a | `config.py` | `AutoAlphaConfig` + `DecisionConfig` — 排程/篩選/安全閾值 | ✅ |
| F1b | `universe.py` | `UniverseSelector` — Scanner 候選 × 靜態約束 × 處置股排除 | ✅ |
| F1c | `researcher.py` | `AlphaResearcher` — 包裝 AlphaPipeline + Regime 分類 + 持久化 | ✅ |
| F1d | `decision.py` | `AlphaDecisionEngine` — ICIR/Hit Rate 篩選 + Regime 權重調適 + Rolling IC | ✅ |
| F1e | `executor.py` | `AlphaExecutor` — weights→orders→risk→execution→performance | ✅ |
| F1f | `scheduler.py` | `AlphaScheduler` — 7 個排程 job（08:30~13:35） | ✅ |

**每日流水線**:
```
08:50 Scanner → Universe (150 stocks - disposition)
08:52 AlphaPipeline.research() → 全因子 IC/ICIR/Regime
08:55 因子篩選 (ICIR>0.3, Hit>52%) → Regime 調適 → 目標權重
09:00 風控檢查 → SinopacBroker 非阻塞下單
13:30 EOD 對帳 → 歸因 → 績效記錄 → 通知
```

### F2: 持久化 + 告警（`src/alpha/auto/`）

| 子任務 | 檔案 | 說明 | 狀態 |
|--------|------|------|------|
| F2a | `store.py` | `AlphaStore` — DB 持久化 (ResearchSnapshot + FactorScore + alerts) | ✅ |
| F2b | `alerts.py` | `AlertManager` — Regime 變化 / IC 反轉 / 回撤告警 → 通知 | ✅ |
| F2c | `safety.py` | `SafetyChecker` — 回撤熔斷 (5%) + 連續虧損暫停 (5 天) | ✅ |
| F2d | migration | `005_auto_alpha.py` — Alembic migration for snapshots/alerts tables | 待實作 |

### F3: API + 前端

| 子任務 | 說明 | 狀態 |
|--------|------|------|
| F3a | `src/api/routes/auto_alpha.py` — 10 個端點 (config/start/stop/status/history/performance/alerts/run-now) | ✅ |
| F3b | WS `auto-alpha` 頻道 — 即時推送流水線進度 | 待實作 |
| F3c | Web: Auto-Alpha Dashboard — 今日配置 + 流水線進度 + 績效走勢 + 告警 | 待實作 |

### F4: Regime 策略引擎

| 子任務 | 說明 | 狀態 |
|--------|------|------|
| F4a | `REGIME_FACTOR_BIAS` — Bull/Bear/Sideways 因子偏好矩陣 | ✅ |
| F4b | 因子績效追蹤表 — 累計 IC 走勢 + 回撤 per factor | ✅ |
| F4c | 動態因子池 — 自動新增/移除因子（基於歷史 ICIR 排名） | ✅ |

### Phase F 完成標誌

系統每日盤前自動執行：
1. Scanner → 動態 Universe → 2. 全因子 IC 分析 → 3. ICIR 篩選 + Regime 調適 → 4. 目標權重 → 5. 風控 → 6. 自動下單 → 7. EOD 對帳 + 歸因 → 8. 績效通知 → 9. 回饋下一日研究

---

## Phase G：學術基準升級 ✅（基於教科書差距分析）

> 參考：`docs/dev/SYSTEM_STATUS_REPORT.md` §11 — 基於 *Portfolio Optimization: Theory and Application* (Palomar, 608 頁) 的系統性差距比對
> **完成日期**: 2026-03-26

### G1: 風險度量升級 ✅

| 子任務 | 說明 | 狀態 |
|--------|------|------|
| G1a | **VaR + CVaR** 計算 — 歷史法 + 參數法 (`compute_var/compute_cvar` in risk_model.py) | ✅ 2026-03-26 |
| G1b | **CVaR 組合最佳化** — Rockafellar-Uryasev LP 重構 (`OptimizationMethod.CVAR`) | ✅ 2026-03-26 |
| G1c | **MaxDD 組合** — 最小化最大回撤 (`OptimizationMethod.MAX_DRAWDOWN`, SLSQP) | ✅ 2026-03-26 |
| G1d | Downside Risk / Semi-variance — 只懲罰下行波動 | ❌ 移至 Phase H |

### G2: 穩健最佳化 ✅

| 子任務 | 說明 | 狀態 |
|--------|------|------|
| G2a | **Worst-case Robust** — 橢球不確定集 (`OptimizationMethod.ROBUST`) | ✅ 2026-03-26 |
| G2b | **Resampled (Michaud)** — Monte Carlo 重取樣平均 (`OptimizationMethod.RESAMPLED`) | ✅ 2026-03-26 |
| G2c | **James-Stein 均值收縮** — Jorion (1986) 公式 (`shrink_mean()` in risk_model.py) | ✅ 2026-03-26 |

### G3: 回測方法論強化 ✅

| 子任務 | 說明 | 狀態 |
|--------|------|------|
| G3a | **Multiple Randomized Backtest** — `src/backtest/randomized.py` | ✅ 2026-03-26 |
| G3b | **PBO (CSCV)** — Bailey et al. `src/backtest/overfitting.py` | ✅ 2026-03-26 |
| G3c | **k-fold CV** — `src/backtest/kfold.py` | ✅ 2026-03-26 |
| G3d | **Stress Test** — 4 情境 (Bear/HighVol/FlashCrash/RegimeChange) `src/backtest/stress_test.py` | ✅ 2026-03-26 |

### G4: 數據建模升級 (部分完成)

| 子任務 | 說明 | 狀態 |
|--------|------|------|
| G4a | **GARCH(1,1) 波動率** — `garch_covariance()` in risk_model.py | ✅ 2026-03-26 |
| G4b | **PCA 因子模型共變異數** — `factor_model_covariance()` Σ = BΣ_fB^T + Ψ | ✅ 2026-03-26 |
| G4c | 非高斯分布建模 (skewed-t) | ❌ 移至 Phase H |
| G4d | Tyler's M-estimator 穩健共變異數 | ❌ 移至 Phase H |

### G5: 高階組合方法 (部分完成)

| 子任務 | 說明 | 狀態 |
|--------|------|------|
| G5a | MVSK 高階矩 (SCA-Q-MVSK) | ❌ 移至 Phase H |
| G5b | **Index Tracking** — LASSO 稀疏追蹤 (Benidis/Feng/Palomar) | ✅ 2026-03-26 |
| G5c | **Maximum Sharpe** — Dinkelbach 分數規劃 SLSQP | ✅ 2026-03-26 |
| G5d | **GMV** — 獨立入口 | ✅ 2026-03-26 |

### G6: 策略升級 (部分完成)

| 子任務 | 說明 | 狀態 |
|--------|------|------|
| G6a | **Pairs Trading 共整合** — Engle-Granger + OLS hedge ratio | ✅ 2026-03-26 |
| G6b | HERC / NCO | ❌ 移至 Phase H |

### G7: 績效指標補齊 ✅

| 子任務 | 說明 | 狀態 |
|--------|------|------|
| G7a | **Omega Ratio** — `compute_omega_ratio()` in analytics.py | ✅ 2026-03-26 |
| G7b | **Rolling Sharpe** — `compute_rolling_sharpe()` 63-day window | ✅ 2026-03-26 |

### G8: 回測防護 ✅

| Sin | 狀態 | 實作 |
|-----|------|------|
| #1 Survivorship Bias | ✅ | 存活者偏差偵測 + 警告標記 |
| #4 Data Snooping | ✅ | PBO (CSCV) + Randomized Backtest + k-fold CV |
| #6 Outliers | ✅ | 價格異常偵測 (gap/circuit breaker) |
| #7 Shorting Cost | ✅ | SimBroker `short_borrow_rate` 融券借券成本 |

### Phase G 完成總結

- PortfolioOptimizer: **13 方法** (EW/IV/RP/MVO/BL/HRP/CVaR/MaxDD/Robust/Resampled/GMV/MaxSharpe/IndexTracking)
- RiskModel: GARCH(1,1) + PCA 因子模型共變異數 + VaR/CVaR + James-Stein
- 回測: Randomized + PBO (CSCV) + k-fold CV + Stress Test + 回測防護 (存活偏差/借券/異常)
- 績效: Omega Ratio + Rolling Sharpe + VaR/CVaR
- 策略: Pairs Trading Engle-Granger 共整合
- **未完成項目移至 Phase H**: MVSK, 非高斯建模, Downside Risk, HERC/NCO, Kalman Filter

---

## Phase H：學術精煉（論文驅動的第二輪升級）

> G 階段遺留項目 + 論文 (`docs/ref/`) 中尚未覆蓋的重要方法

### H1: Deflated Sharpe Ratio + MinBTL (🔴 P0)

| 子任務 | 說明 | 論文依據 | 難度 |
|--------|------|---------|------|
| H1a | `deflated_sharpe()` — SR 校正 N_trials, skewness, kurtosis | Bailey et al. (2015) §3 | 低 |
| H1b | `min_backtest_length()` — 給定 N 策略，最短回測時間才能避免偽陽性 | Bailey et al. (2014) | 低 |

**實作位置**: `src/backtest/analytics.py`。
**價值**: 多重測試校正是回測驗證最關鍵的缺口，防止過度挖掘。

### H2: MVSK 高階矩組合 (🟡 P1)

| 子任務 | 說明 | 論文依據 | 難度 |
|--------|------|---------|------|
| H2a | SCA-Q-MVSK 演算法 — Mean-Variance-Skewness-Kurtosis 最佳化 | `highOrderPortfolios` vignette, 書 Ch.9 | 高 |

**實作位置**: `src/portfolio/optimizer.py` 新增 `OptimizationMethod.MVSK`。
**價值**: 金融報酬有顯著偏態+峰態，MV 不足以捕捉尾部風險偏好。

### H3: 非高斯建模 (🟡 P1)

| 子任務 | 說明 | 論文依據 | 難度 |
|--------|------|---------|------|
| H3a | Tyler's M-estimator — 穩健共變異數估計 | `fitHeavyTail` vignette, 書 Ch.2 | 高 |
| H3b | Skewed-t 分布擬合 — 厚尾+偏態建模 | `fitHeavyTail` vignette | 高 |

**實作位置**: `src/portfolio/risk_model.py`。

### H4: Downside Risk + EVaR (🟡 P1)

| 子任務 | 說明 | 論文依據 | 難度 |
|--------|------|---------|------|
| H4a | Semi-variance 組合最佳化 — 只懲罰下行波動 | 書 Ch.10 | 低 |
| H4b | Entropic Value at Risk (EVaR) — 比 CVaR 更嚴格的 coherent risk measure | 書 Ch.10 | 中 |

**實作位置**: `src/portfolio/optimizer.py`。

### H5: 進階擴展 (🟢 P2)

| 子任務 | 說明 | 論文依據 | 難度 |
|--------|------|---------|------|
| H5a | Kalman Filter 動態 hedge ratio — Pairs Trading 升級 | 書 Ch.15 | 中 |
| H5b | HERC / NCO — HRP 等風險貢獻版 + 巢狀叢集最佳化 | 書 Ch.12, López de Prado | 中 |
| H5c | 非線性共變異數收縮 — Ledoit-Wolf (2017) RMT eigenvalue 收縮 | Ledoit-Wolf (2017) | 高 |

---

## 里程碑時間線

| 日期 | 里程碑 |
|------|--------|
| 2026-03-22~23 | 股票交易系統 (回測+7策略+風控+API+Web+Mobile) |
| 2026-03-24 | Alpha 研究層 (11 模組+API+前端) |
| 2026-03-24 | Phase A (基礎設施+管線整合+模型統一) |
| 2026-03-24 | Phase B (宏觀因子+跨資產信號+戰術配置+API) |
| 2026-03-24 | Phase C (6 種最佳化+風險模型+幣別對沖) |
| 2026-03-24 | 測試覆蓋補齊 (+29 tests: 期貨成本/golden value/E2E/FX) |
| 2026-03-25 | Phase D (MultiAssetStrategy+跨資產風控+FX 修復+Allocation 前端) |
| 2026-03-25 | Alpha 層強化 (5 新因子+Rolling IC+Regime+Attribution) |
| 2026-03-25 | E1: SinopacBroker 核心 + ExecutionService + 對帳 + 83 tests |
| TBD | E2: 即時行情 WS broadcast 整合 (需 API key) |
| TBD | E3: Paper Trading 完整循環 + 排程 + 交割 |
| 2026-03-25 | E4a: Shioaji 歷史數據源 (kbars/ticks/snapshot) |
| 2026-03-25 | E4b: Scanner 動態 universe + 處置股排除 |
| 2026-03-25 | E4c-f: 額度預檢 + 融資融券 + 非阻塞 + 觸價 |
| TBD | E5: 期貨選擇權交易 + 組合單 |
| TBD | E6: IB 美股對接 |
| 2026-03-26 | F1: 自動化 Alpha 核心引擎 (6 modules + scheduler) |
| 2026-03-26 | F2: 持久化 + 告警 + 安全熔斷 |
| 2026-03-26 | F3a: Auto-Alpha API (10 端點) |
| 2026-03-26 | F4: Regime 策略引擎 + 動態因子池 |
| 2026-03-26 | G1: 風險度量 (VaR/CVaR 計算 + CVaR 最佳化 + MaxDD 最佳化) |
| 2026-03-26 | G2: 穩健最佳化 (Robust/Resampled/James-Stein) |
| 2026-03-26 | G3: 回測方法論 (Randomized/PBO/k-fold/Stress Test) |
| 2026-03-26 | G4: GARCH(1,1) + PCA 因子模型共變異數 |
| 2026-03-26 | G5: GMV + MaxSharpe + Index Tracking |
| 2026-03-26 | G6: Pairs Trading 共整合 (Engle-Granger) |
| 2026-03-26 | G7-G8: Omega/Rolling Sharpe + 回測防護 (存活偏差/借券/異常) |
| TBD | H1: Deflated Sharpe Ratio + MinBTL (P0) |
| TBD | H2-H4: MVSK + 非高斯建模 + Downside Risk + EVaR (P1) |
| TBD | H5: Kalman Filter + HERC/NCO + 非線性收縮 (P2) |

---

## 設計缺陷追蹤

| 編號 | 狀態 | 問題 |
|------|------|------|
| D-01~D-07 | ✅ | Phase A 管線整合 |
| D-08 | 延後 | Alpha Pipeline GIL 限制 |
| D-10~D-18 | ✅ | 模型統一/bug fixes/FX/權重/風控/整合 |
| D-19 | Phase E5 | 期貨展期模擬 |
| D-20 | ✅ E1 | SinopacBroker + ExecutionService + 對帳 + 交易時段 + API |
| D-21 | E3 | Paper Trading 排程 + 交割查詢 |
| D-22 | E4a | Shioaji DataFeed 實作 (kbars/ticks/snapshot) |
| D-23 | E4b | Scanner 動態 universe + 處置/注意股排除 |
| D-24 | E4d | 融資融券/當沖 Order 擴展 |
| D-25 | E5 | 期貨選擇權交易 + 組合單 |
