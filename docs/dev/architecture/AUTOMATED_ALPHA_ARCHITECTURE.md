# 自動化 Alpha 研究系統架構設計

> **版本**: v2.0
> **日期**: 2026-03-26
> **目標**: 將手動 Alpha 研究流程自動化為每日排程驅動的閉環系統
> **狀態**: Phase F 已完成實作，Phase G/H 學術升級已整合
> **前置**: Phase E 交易執行層已完成，Shioaji SDK 已安裝

---

## 1. 設計動機

### 1.1 現狀問題

當前 Alpha 研究流程為**手動觸發、單次執行**：

```
使用者 → POST /api/v1/alpha (手動) → Pipeline 執行 → 報告產出 → 人工判讀 → 人工調整策略
```

**痛點**：
1. 因子有效性隨時間衰減，但研究結果只在觸發時刻有效
2. 市場環境切換時（Bull → Bear），因子權重未自動調適
3. 交易 universe 固定，未納入即時流動性與監管狀態
4. 研究結果與交易執行之間存在人工斷層
5. 無歷史研究結果的持久化與比較機制

### 1.2 目標狀態

建立**每日自動執行的閉環 Alpha 系統**：

```
排程觸發 (每日盤前)
  → Scanner 動態 Universe
    → Alpha Pipeline (全因子 IC + Rolling IC)
      → 自動因子篩選 (IC > 閾值)
        → Regime 偵測 → 因子權重調適
          → 目標權重產出
            → 風控檢查 → 下單
              → 績效追蹤 → 回饋下一輪研究
```

---

## 2. 系統架構

### 2.1 總覽

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        自動化 Alpha 研究系統                                    │
│                                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌─────────────┐  │
│  │  Stage 1  │→│  Stage 2  │→│  Stage 3  │→│ Stage 3.5  │→│   Stage 4    │  │
│  │ Universe  │  │ Research  │  │ Decision  │  │  Backtest   │  │  Execution   │  │
│  │ Selection │  │ & Scoring │  │ & Weights │  │    Gate     │  │  & Feedback  │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘  └─────────────┘  │
│       ↑                                                          │           │
│       └────────────────── 績效回饋循環 ←─────────────────────────┘           │
│                                                                              │
│  ╔══════════════════════════════════════════════════════════════════════╗    │
│  ║ 基礎設施：Scheduler │ DB 持久化 │ 通知 │ API │ 前端監控              ║    │
│  ╚══════════════════════════════════════════════════════════════════════╝    │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 五階段流水線

#### Stage 1: Universe Selection（動態選股池）

**輸入**: 無（自動觸發）
**輸出**: `list[str]` — 今日交易標的清單

```python
class UniverseSelector:
    """每日動態選股池。"""

    def select(self) -> UniverseResult:
        # 1. Scanner 取得活躍標的（成交量前 N）
        active = scanner.top_volume(count=200)

        # 2. 排除處置股 / 注意股
        disposition = scanner.get_disposition_stocks()
        attention = scanner.get_attention_stocks()
        filtered = [s for s in active if s not in disposition | attention]

        # 3. 流動性過濾（日均量 > 閾值）
        # 4. 上市天數過濾（> min_listing_days）
        # 5. 價格過濾（排除全額交割股、低價股）
        return UniverseResult(symbols=filtered, ...)
```

**數據源**: `ShioajiScanner` (即時) + `UniverseFilter` (靜態規則)

**設計決策**:
- Scanner 提供「動態候選」，UniverseFilter 提供「靜態約束」
- 兩者取交集：`dynamic ∩ static_constraints`
- 處置股硬排除（下單會被券商拒絕），注意股軟排除（產生警告但不阻擋）

#### Stage 2: Research & Scoring（因子研究與評分）

**輸入**: Universe + 歷史數據
**輸出**: `ResearchSnapshot` — 全因子分析快照

```python
class AlphaResearcher:
    """每日因子研究。"""

    def run(self, universe: list[str], config: AutoAlphaConfig) -> ResearchSnapshot:
        # 1. 下載歷史資料（lookback 天）
        data = self._fetch_data(universe, lookback=config.lookback)

        # 2. AlphaPipeline.research() — 全因子 IC / ICIR / 衰減 / 分位數
        pipeline = AlphaPipeline(config.alpha_config)
        report = pipeline.research(data)

        # 3. Regime 分類（當前市場環境）
        current_regime = classify_regimes(compute_market_returns(data))

        # 4. 持久化研究快照
        snapshot = ResearchSnapshot(
            date=today,
            report=report,
            regime=current_regime.iloc[-1],
            universe=universe,
        )
        self._store.save(snapshot)
        return snapshot
```

**運行頻率**: 每日一次（盤前 08:50）或每週一次（視配置）
**歷史深度**: 預設 lookback=252 天（1 年），可配置

**關鍵指標**:
| 指標 | 計算方式 | 用途 |
|------|---------|------|
| IC (Information Coefficient) | `corr(factor, forward_return)` | 因子預測力 |
| ICIR (IC Information Ratio) | `IC_mean / IC_std` | 因子穩定性 |
| IC Hit Rate | `P(IC > 0)` | 因子方向一致性 |
| Monotonicity Score | 分位數報酬單調性 | 因子有效性 |
| L/S Sharpe | 多空組合 Sharpe Ratio | 經濟價值 |
| Turnover | 因子值日間變化 | 交易成本 |
| Factor Decay | IC vs holding period | 最佳持有期 |
| Regime IC | 分環境的 IC | 條件有效性 |

#### Stage 3: Decision & Weights（決策與權重產出）

**輸入**: `ResearchSnapshot` + 當前持倉
**輸出**: `dict[str, float]` — 目標權重

```python
class AlphaDecisionEngine:
    """因子篩選 + 權重產出。"""

    def decide(self, snapshot: ResearchSnapshot, config: DecisionConfig) -> DecisionResult:
        report = snapshot.report
        regime = snapshot.regime

        # 1. 因子篩選：ICIR > 閾值 且 Hit Rate > 50%
        eligible = self._filter_factors(report, config)

        # 2. Regime-aware 權重調整
        weights = self._regime_adjust(eligible, report, regime, config)

        # 3. Rolling IC 動態加權（近 N 天 IC 表現）
        if config.use_rolling_ic:
            weights = self._rolling_ic_reweight(weights, report)

        # 4. 產出目標組合權重
        target_weights = pipeline.generate_weights(
            data=data,
            current_date=today,
            current_weights=current_portfolio_weights,
        )

        return DecisionResult(
            selected_factors=eligible,
            factor_weights=weights,
            target_weights=target_weights,
            regime=regime,
        )
```

**因子篩選邏輯**:
```
eligible = {
    f for f in all_factors
    if report.factor_ics[f].icir > config.min_icir           # 穩定性 (default: 0.3)
    and report.factor_ics[f].hit_rate > config.min_hit_rate   # 方向性 (default: 0.52)
    and report.factor_turnovers[f].cost_drag_annual_bps < config.max_cost_drag  # 成本效率 (default: 200 bps)
}
```

**Net Alpha 過濾**: 因子必須有正的淨 alpha（gross IC x vol - cost_drag > 0）。即使 ICIR 通過門檻，若交易成本超過預期收益仍會被排除。

**Regime-aware 調整**:
| 環境 | 調整策略 |
|------|---------|
| Bull | 提高動量/品質因子權重，降低防禦因子 |
| Bear | 提高低波動/價值因子權重，降低動量 |
| Sideways | 提高均值回歸因子權重，等權其餘 |

**具體實作**:
```python
REGIME_FACTOR_BIAS: dict[MarketRegime, dict[str, float]] = {
    MarketRegime.BULL: {
        "momentum": 1.5, "quality_roe": 1.3,
        "volatility": 0.7, "mean_reversion": 0.5,
    },
    MarketRegime.BEAR: {
        "volatility": 1.5, "value_pe": 1.3,
        "momentum": 0.5, "max_ret": 1.2,
    },
    MarketRegime.SIDEWAYS: {
        "mean_reversion": 1.5, "rsi": 1.3,
        "momentum": 0.8,
    },
}
```

#### Stage 3.5: Validation Backtest（下單前驗證回測）🆕

> **原則**: Decision 基於歷史 IC 選因子，但歷史統計量不保證近期有效。
> 下單前必須用近期 OOS 數據驗證組合是否真的能賺錢。

**輸入**: DecisionResult (selected_factors + target_weights) + 近 N 天歷史數據
**輸出**: ValidationResult (pass/fail + 原因)

```python
class ValidationBacktest:
    """Decision → Execution 之間的閘門。"""

    def validate(
        self,
        decision: DecisionResult,
        data: dict[str, pd.DataFrame],
        config: ValidationConfig,
    ) -> ValidationResult:
        # 1. 用選出的因子 + 權重，跑最近 60 天 walk-forward 回測
        result = backtest_engine.run(
            strategy=AlphaStrategy(factors=decision.selected_factors, weights=decision.factor_weights),
            data=data,
            start=today - timedelta(days=config.validation_lookback),  # 60 天
            end=today,
        )

        checks: list[str] = []
        passed = True

        # 2. Sharpe > 0？（最低門檻：不虧錢）
        if result.sharpe < config.min_sharpe:   # default: 0.0
            checks.append(f"Sharpe {result.sharpe:.2f} < {config.min_sharpe}")
            passed = False

        # 3. 勝過 1/N 等權基準？（DeMiguel 2009）
        benchmark_sharpe = backtest_1n(data, start, end).sharpe
        if result.sharpe < benchmark_sharpe:
            checks.append(f"Sharpe {result.sharpe:.2f} < 1/N benchmark {benchmark_sharpe:.2f}")
            # 不直接 fail，但降級為警告

        # 4. 回撤 < 閾值？
        if result.max_drawdown > config.max_drawdown:  # default: 0.10
            checks.append(f"MaxDD {result.max_drawdown:.1%} > {config.max_drawdown:.1%}")
            passed = False

        # 5. 預期交易成本 < 預期 alpha？
        expected_turnover = decision.expected_turnover
        expected_cost = expected_turnover * config.cost_per_turnover_bps  # 手續費+稅+滑點
        expected_alpha = result.annual_return - benchmark_return
        if expected_cost > expected_alpha and expected_alpha > 0:
            checks.append(f"Cost {expected_cost:.0f}bps > Alpha {expected_alpha:.0f}bps")
            passed = False

        return ValidationResult(
            passed=passed,
            checks=checks,
            backtest_sharpe=result.sharpe,
            backtest_return=result.annual_return,
            backtest_drawdown=result.max_drawdown,
        )
```

**未通過時的處理**:
```
pass   → 正常進入 Stage 4 Execution
fail   → 三種策略（可配置）：
         1. skip: 今日不交易，維持現有持倉
         2. reduce: 將目標權重 × 0.5（半倉）
         3. fallback: 退化為 1/N 等權組合
```

**設計理由**:
- 回測用最近 60 天，不是全歷史 → 反映當前市場結構
- 1/N 是最難打敗的基準（DeMiguel 2009）→ 如果連 1/N 都贏不了，不該交易
- 手續費預估用實際換手率 × 台股成本 (~50 bps 來回) → 避免 alpha_33 這類高換手因子偷渡

#### Stage 4: Execution & Feedback（執行與回饋）

**輸入**: 通過驗證的目標權重
**輸出**: 交易記錄 + 績效快照

```python
class AlphaExecutor:
    """權重 → 下單 → 績效追蹤。"""

    async def execute(self, decision: DecisionResult) -> ExecutionResult:
        # 1. weights_to_orders() — 權重轉訂單
        orders = weights_to_orders(
            target_weights=decision.target_weights,
            portfolio=current_portfolio,
            prices=current_prices,
        )

        # 2. 風控檢查
        approved = risk_engine.check_orders(orders, portfolio)

        # 3. 交易時段驗證 + 下單
        trades = execution_service.submit_orders(approved, portfolio)

        # 4. 更新 Portfolio
        apply_trades(portfolio, trades)

        # 5. 記錄績效快照
        self._record_performance(decision, trades)

        # 6. 通知
        await self._notify(decision, trades)

        return ExecutionResult(trades=trades, ...)
```

**績效回饋循環**:
```
每日收盤後：
  1. EOD 對帳（reconcile）
  2. 計算當日 PnL + 歸因（attribution）
  3. 更新因子績效追蹤表
  4. 若連續 N 天因子 IC 反轉 → 產生告警
  5. 回饋至下一日的 Stage 2（研究用更新的績效數據）
```

---

## 3. 數據模型

### 3.1 配置

```python
@dataclass
class AutoAlphaConfig:
    """自動化 Alpha 系統配置。"""

    # 排程
    schedule: str = "50 8 * * 1-5"  # 每個交易日 08:50 (台灣時間)
    eod_schedule: str = "00 14 * * 1-5"  # 每日 14:00 (收盤後)

    # Universe
    universe_count: int = 150          # Scanner 候選數量
    min_adv: int = 500_000             # 最低日均成交量（股）
    min_listing_days: int = 120        # 最低上市天數
    exclude_disposition: bool = True   # 排除處置股
    exclude_attention: bool = False    # 排除注意股（預設不排除，僅警告）

    # Research
    lookback: int = 252                # 研究回望天數
    alpha_config: AlphaConfig          # 完整的 AlphaPipeline 配置

    # Decision (nested DecisionConfig)
    decision: DecisionConfig           # 見下方
    #   min_icir: float = 0.5          # 最低 ICIR 門檻 (actual default, 文件原寫 0.3)
    #   min_hit_rate: float = 0.52     # 最低 IC 勝率
    #   max_cost_drag: float = 200.0   # 最大成本拖累 (bps/年)
    #   oos_decay_factor: float = 0.42 # McLean-Pontiff (2016) OOS 衰減係數
    #   → adjusted_icir = |IS_ICIR| × 0.42 必須 ≥ min_icir 才算 eligible

    # Execution
    max_turnover: float = 0.30         # 單日最大換手率
    min_trade_value: float = 50_000    # 最小交易金額（TWD）

    # Safety
    max_consecutive_losses: int = 5    # 連續虧損天數 → 暫停告警
    ic_reversal_days: int = 10         # IC 反轉天數 → 因子告警
    emergency_stop_drawdown: float = 0.05  # 5% 回撤 → 緊急停止
```

### 3.2 持久化結構

```python
@dataclass
class ResearchSnapshot:
    """每日研究快照（持久化至 DB）。"""
    id: str                            # UUID
    date: date                         # 研究日期
    regime: MarketRegime               # 當日市場環境
    universe: list[str]                # 使用的 universe
    universe_size: int
    # 因子分析
    factor_scores: dict[str, FactorScore]  # {name: {ic, icir, hit_rate, ...}}
    selected_factors: list[str]        # 通過篩選的因子
    factor_weights: dict[str, float]   # 因子合成權重
    # 組合
    target_weights: dict[str, float]   # 目標持倉權重
    # 執行結果
    trades_count: int = 0
    turnover: float = 0.0
    # 績效（隔日收盤後填入）
    daily_pnl: float | None = None
    cumulative_return: float | None = None


@dataclass
class FactorScore:
    """單因子每日評分。"""
    name: str
    ic: float
    icir: float
    hit_rate: float
    decay_half_life: int
    turnover: float
    cost_drag_bps: float
    regime_ic: dict[str, float]        # {regime: ic}
    long_short_sharpe: float
    eligible: bool                     # 是否通過篩選
```

### 3.3 告警模型

```python
@dataclass
class AlphaAlert:
    """Alpha 系統告警。"""
    timestamp: datetime
    level: Literal["info", "warning", "critical"]
    category: str                      # "factor", "regime", "execution", "drawdown"
    message: str
    details: dict[str, Any]

# 告警條件
ALERT_RULES = {
    "regime_change": "市場環境從 {old} 變為 {new}",
    "factor_degraded": "因子 {name} ICIR 從 {old:.2f} 降至 {new:.2f}",
    "ic_reversal": "因子 {name} 連續 {days} 天 IC 為負",
    "high_turnover": "今日換手率 {turnover:.1%} 超過閾值 {threshold:.1%}",
    "drawdown_warning": "累計回撤 {dd:.1%} 接近停止閾值 {threshold:.1%}",
    "emergency_stop": "回撤達 {dd:.1%}，觸發緊急停止",
    "no_eligible_factors": "今日無因子通過篩選門檻",
    "disposition_added": "{count} 檔持倉被列為處置股",
}
```

---

## 4. 排程設計

### 4.1 每日時間線

```
08:30  ┌─ Stage 0: 系統健康檢查
       │  - Shioaji 連線狀態
       │  - 資料庫可用性
       │  - 通知管道測試
       │
08:50  ├─ Stage 1: Universe Selection
       │  - Scanner 取得候選（~5 秒）
       │  - 處置/注意股過濾
       │  - 產出今日 universe
       │
08:52  ├─ Stage 2: Research
       │  - 下載歷史數據（~30 秒，含快取）
       │  - 全因子 IC 計算（~20 秒）
       │  - Regime 分類
       │  - 持久化快照
       │
08:55  ├─ Stage 3: Decision
       │  - 因子篩選
       │  - Regime 權重調適
       │  - 目標權重產出
       │  - 通知：今日配置摘要
       │
08:57  ├─ Stage 3.5: Validation Backtest 🆕
       │  - 近 60 天 walk-forward 回測
       │  - Sharpe > 0？1/N 基準比較？
       │  - 預期手續費 vs 預期 alpha
       │  - 通過 → 進入 Stage 4
       │  - 未通過 → skip / reduce / fallback
       │
09:00  ├─ Stage 4a: Execution (開盤)
       │  - weights_to_orders()
       │  - 風控檢查
       │  - SinopacBroker.submit_order()（非阻塞）
       │  - 通知：下單確認
       │
09:00  │  ─── 盤中 ───
~13:25 │  - 即時行情監控
       │  - StopOrderManager 觸價檢查
       │  - Portfolio 即時更新（成交回報）
       │
13:30  ├─ Stage 4b: EOD Processing
       │  - reconcile() 持倉對帳
       │  - 當日 PnL 計算
       │  - 因子歸因（attribution）
       │  - 更新 ResearchSnapshot.daily_pnl
       │  - 通知：每日績效報告
       │
13:35  └─ Stage 4c: Safety Check
          - 檢查連續虧損天數
          - 檢查累計回撤
          - 若觸發安全規則 → 暫停次日交易 + 告警
```

### 4.2 排程配置

```python
SCHEDULES = {
    "health_check":    "30 8 * * 1-5",   # 08:30 Mon-Fri
    "universe":        "50 8 * * 1-5",   # 08:50
    "research":        "52 8 * * 1-5",   # 08:52
    "decision":        "55 8 * * 1-5",   # 08:55
    "execution":       "00 9 * * 1-5",   # 09:00
    "eod_processing":  "30 13 * * 1-5",  # 13:30
    "safety_check":    "35 13 * * 1-5",  # 13:35
    "weekly_report":   "00 9 * * 1",     # 週一 09:00
}
```

---

## 5. 安全機制

### 5.1 多層防護

```
Layer 1: 因子層
  ├─ 最低 ICIR 門檻 (不合格因子不參與)                              ✅ 已實作
  ├─ IC 反轉偵測 (連續 N 天 IC < 0 → 告警)                         ✅ 已實作
  ├─ 因子相關性監控 (避免過度集中)                                    ✅ 已實作
  ├─ cost_drag 嚴格過濾 (cost_drag > alpha 預期 → 排除)             🆕 待實作
  └─ OOS 衰減校正 (McLean-Pontiff ×0.42)                           ✅ 已實作

Layer 2: 組合層 — 驗證回測閘門 (Stage 3.5)
  ├─ 近 60 天 walk-forward 回測                                     🆕 待實作
  ├─ Sharpe > 0 最低門檻                                            🆕 待實作
  ├─ 勝過 1/N 等權基準 (DeMiguel 2009)                              🆕 待實作
  ├─ 預期手續費 < 預期 alpha（換手率 × 單邊成本 bps）                  🆕 待實作
  ├─ 單檔權重上限 (5%)                                              ✅ 已實作
  ├─ 單日換手率上限 (30%)                                            ✅ 已實作
  └─ 處置股自動排除                                                  ✅ 已實作

Layer 3: 執行層
  ├─ 交易時段驗證 (盤外佇列)                                         ✅ 已實作
  ├─ 交易額度預檢 (trading_limits)                                   ✅ 已實作
  ├─ 風控 10 規則檢查                                               ✅ 已實作
  └─ Kill Switch (5% 日回撤)                                        ✅ 已實作

Layer 4: 系統層
  ├─ 累計回撤熔斷 (5% → 暫停)                                       ✅ 已實作
  ├─ 連續虧損告警 (5 天 → 通知)                                      ✅ 已實作
  ├─ Kill Switch 冷靜期恢復 (3 天冷靜 → 50%~100% 漸進恢復)            ✅ 已實作
  ├─ 券商斷線自動暫停                                                ✅ 已實作
  └─ 研究結果異常偵測 (universe 過小、IC 全為 0)                       ✅ 已實作
```

### 5.1.1 防護缺口分析（實測發現）

| 防護 | 現狀 | 問題 | 應有 |
|------|------|------|------|
| **cost_drag 過濾** | `max_cost_drag=200 bps` 存在但太寬 | alpha_33 cost_drag=2,432 bps 仍可能通過（若 ICIR 夠高） | 應拒絕 cost_drag > 預期 alpha 的因子。公式：`cost_drag > ic_mean × 252 × 10000` → 排除 |
| **回測閘門** | 無 | Decision 直接進入 Execution，無近期 OOS 驗證 | Stage 3.5: 近 60 天 walk-forward，Sharpe < 0 不執行 |
| **手續費預估** | 無獨立檢查 | 高換手因子的交易成本可能吃掉全部 alpha | `expected_turnover × cost_bps > expected_alpha` → 跳過 |
| **Kill Switch 恢復** | ✅ 已實作 | 3 天冷靜期 + 5 天漸進恢復 (50%→100%) | `SafetyChecker.check_recovery()` + `AlphaScheduler` 整合 |

### 5.2 緊急停止與冷靜期恢復機制

**Kill Switch 觸發**（`SafetyChecker.check()`）：
- 累計回撤 >= `emergency_stop_drawdown` (5%) → `should_pause=True`
- 連續虧損 >= `max_consecutive_losses` (5 天) → 告警

**Kill Switch 恢復**（`SafetyChecker.check_recovery()`）：

```python
def check_recovery(self, days_since_pause: int) -> RecoveryResult:
    cfg = self._config

    if days_since_pause < cfg.kill_switch_cooldown_days:  # default: 3
        return RecoveryResult(can_resume=False, position_scale=0.0, reason=...)

    days_in_ramp = days_since_pause - cfg.kill_switch_cooldown_days
    if days_in_ramp >= cfg.kill_switch_recovery_ramp_days:  # default: 5
        scale = 1.0
    else:
        start_pct = cfg.kill_switch_recovery_position_pct  # default: 0.50
        scale = start_pct + (1.0 - start_pct) * (days_in_ramp / cfg.kill_switch_recovery_ramp_days)

    return RecoveryResult(can_resume=True, position_scale=scale, reason=...)
```

**恢復配置參數**（`AutoAlphaConfig`）：
| 參數 | 預設 | 說明 |
|------|------|------|
| `kill_switch_cooldown_days` | 3 | 觸發後等待天數 |
| `kill_switch_recovery_position_pct` | 0.50 | 恢復起始倉位比例 |
| `kill_switch_recovery_ramp_days` | 5 | 從起始倉位漸進到 100% 的天數 |

**冷靜期恢復流程**:
```
Kill Switch 觸發（回撤 ≥ 5%）
  → 暫停所有交易 + 取消未成交訂單
    → 冷靜期（default: 3 個交易日）：不下單，持續 Research + Decision
      → 冷靜期結束：
         Day 3: 以 50% 倉位恢復
         Day 4: 60% 倉位
         Day 5: 70% 倉位
         Day 6: 80% 倉位
         Day 7: 90% 倉位
         Day 8+: 100% 倉位（完全恢復）
         → 再次觸發回撤 → 重新進入冷靜期
```

**整合點**：`AlphaScheduler.run_full_cycle()` 在 Stage 4 (Execution) 之前檢查恢復狀態，
若尚在冷靜期則跳過執行，若已恢復則按 `position_scale` 縮放 `factor_weights`。

---

## 6. API 設計

### 6.1 新增端點

| 端點 | 方法 | 說明 | 狀態 |
|------|------|------|------|
| `/api/v1/auto-alpha/config` | GET | 取得自動化配置 | ✅ |
| `/api/v1/auto-alpha/config` | PUT | 更新配置（partial update） | ✅ |
| `/api/v1/auto-alpha/start` | POST | 啟動排程自動化 | ✅ |
| `/api/v1/auto-alpha/stop` | POST | 暫停自動化 | ✅ |
| `/api/v1/auto-alpha/status` | GET | 當前狀態 (running/stopped + regime + selected_factors) | ✅ |
| `/api/v1/auto-alpha/history` | GET | 歷史研究快照列表 (limit param) | ✅ |
| `/api/v1/auto-alpha/history/{date}` | GET | 指定日期的研究快照明細 | ✅ |
| `/api/v1/auto-alpha/performance` | GET | 累計績效摘要 (return/win_rate/drawdown) | ✅ |
| `/api/v1/auto-alpha/alerts` | GET | 告警記錄 (limit param) | ✅ |
| `/api/v1/auto-alpha/run-now` | POST | 立即執行一次（背景執行緒，返回 task_id） | ✅ |
| `/api/v1/auto-alpha/run-now/{task_id}` | GET | 查詢 run-now 任務進度 (stage/symbols_loaded/completed) | ✅ (新增) |
| `/api/v1/auto-alpha/ws` | WS | 即時推送流水線狀態 (stage_started/completed/alert) | ✅ |

### 6.2 WebSocket 頻道

```
channel: "auto-alpha"
events:
  - { type: "stage_started", stage: "universe", timestamp: ... }
  - { type: "stage_completed", stage: "research", duration_sec: 45, ... }
  - { type: "decision", factors: [...], regime: "bull", weights: {...} }
  - { type: "execution", trades: 12, turnover: 0.15 }
  - { type: "alert", level: "warning", message: "..." }
  - { type: "eod_report", pnl: 25000, cumulative_return: 0.032 }
```

---

## 7. 前端監控

### 7.1 Auto-Alpha Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│  Auto-Alpha Dashboard                          [Running ●]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ 今日 PnL  │ │ 累計報酬  │ │ Regime   │ │ Universe │      │
│  │ +25,320  │ │ +3.2%    │ │ 🐂 Bull  │ │ 142 檔   │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│                                                             │
│  ── 今日因子配置 ──────────────────────────────────────      │
│  momentum ████████████░░ 35% (IC: +0.045, ICIR: 0.82)     │
│  volatility ████████░░░░ 25% (IC: -0.038, ICIR: 0.65)     │
│  value_pe █████░░░░░░░░ 20% (IC: +0.031, ICIR: 0.55)     │
│  rsi █████░░░░░░░░░░░░ 20% (IC: +0.028, ICIR: 0.48)     │
│                                                             │
│  ── 執行流水線 ──────────────────────────────────────        │
│  08:50 ✅ Universe: 142 stocks (excl. 3 disposition)       │
│  08:52 ✅ Research: 14 factors analyzed in 45s              │
│  08:55 ✅ Decision: 4 factors selected, regime=bull         │
│  09:00 ✅ Execution: 12 orders submitted, turnover=15%      │
│  13:30 ⏳ EOD Processing: pending...                        │
│                                                             │
│  ── 績效走勢 ──────────────────────────────────────          │
│  [累計報酬折線圖 + 每日 PnL 柱狀圖]                           │
│                                                             │
│  ── 告警記錄 ──────────────────────────────────────          │
│  ⚠️ 03-25: Factor 'momentum' ICIR dropped from 0.85 to 0.42│
│  ℹ️ 03-24: Regime changed from SIDEWAYS to BULL             │
│                                                             │
│  [Start] [Pause] [Run Now] [Config ⚙️]                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. 模組依賴圖

```
src/alpha/auto/                      實際狀態
├── config.py          ← AutoAlphaConfig + DecisionConfig + FactorScore + ResearchSnapshot     ✅
├── universe.py        ← UniverseSelector (Scanner + data keys fallback)                       ✅
├── researcher.py      ← AlphaResearcher (wraps AlphaPipeline + Regime)                        ✅
├── decision.py        ← AlphaDecisionEngine (ICIR篩選 + REGIME_FACTOR_BIAS + normalize)       ✅
├── executor.py        ← AlphaExecutor (weights→orders→risk→execution, backtest mode skip)     ✅
├── scheduler.py       ← AlphaScheduler (run_full_cycle + WS broadcast + job definitions)      ✅
├── store.py           ← AlphaStore (in-memory list, save/list snapshots + alerts)              ✅ (無DB)
├── alerts.py          ← AlertManager (regime/IC/drawdown alerts → 通知)                       ✅
├── safety.py          ← SafetyChecker (回撤熔斷 5% + 連續虧損 5 天暫停)                        ✅
├── factor_tracker.py  ← FactorPerformanceTracker (累計 IC + per-factor 回撤)                  ✅ (文件未記載)
├── dynamic_pool.py    ← DynamicFactorPool (ICIR 排名自動新增/移除因子)                         ✅ (文件未記載)
└── __init__.py        ← 匯出全部 public symbols                                               ✅

依賴關係：
  config.py         → src/alpha/pipeline.py (AlphaConfig, FactorSpec), src/alpha/regime.py
  universe.py       → src/data/scanner.py (optional), src/alpha/universe.py
  researcher.py     → src/alpha/pipeline.py, src/alpha/regime.py, src/strategy/research.py
  decision.py       → config.py, dynamic_pool.py, factor_tracker.py, store.py
  executor.py       → src/execution/execution_service.py, src/risk/engine.py, src/execution/oms.py
  scheduler.py      → universe.py, researcher.py, decision.py, executor.py, store.py
  store.py          → (in-memory, 無 DB 依賴 — DB migration 待實作)
  alerts.py         → src/notifications/factory.py
  safety.py         → store.py, alerts.py
  factor_tracker.py → store.py
  dynamic_pool.py   → store.py, src/strategy/research.py (FACTOR_REGISTRY)
```

---

## 9. 與現有系統的整合點

| 現有模組 | 整合方式 | 說明 |
|---------|---------|------|
| `AlphaPipeline` | 被 `AlphaResearcher` 包裝 | research() + generate_weights() 不變 |
| `AlphaStrategy` | 退化為 `AutoAlphaExecutor` 的子集 | 手動模式仍可用 |
| `ShioajiScanner` | 被 `UniverseSelector` 調用 | 提供動態候選 |
| `ExecutionService` | 被 `AlphaExecutor` 調用 | 模式路由不變 |
| `RiskEngine` | 被 `AlphaExecutor` 調用 | 10 規則 + kill switch |
| `StopOrderManager` | 整合至盤中監控 | 觸價 → 即時平倉 |
| `SchedulerService` | 新增 auto-alpha jobs | 不影響現有 rebalance job |
| `ConnectionManager` (WS) | 新增 `auto-alpha` 頻道 | 即時推送流水線狀態 |
| `NotificationProvider` | 被 `AlertManager` 調用 | Discord/LINE/Telegram |
| DB (`src/data/store.py`) | `AlphaStore` 擴展 | 新增 snapshots/alerts 表 |

---

## 10. 設計取捨

| 決策 | 選擇 | 理由 |
|------|------|------|
| 研究頻率 | 每日一次（非即時） | 日頻因子的 IC 不會在盤中大幅變動；降低 API 負荷 |
| 因子篩選 | ICIR + Hit Rate + Cost | 三維度確保因子有穩定性、方向性、經濟價值 |
| Regime 調整 | 乘數偏移（非硬切） | 避免環境誤判導致因子完全排除 |
| 持久化 | SQLite/PostgreSQL | 與現有 DB 棧一致；JSON 欄位存因子明細 |
| 下單時機 | 開盤瞬間 (09:00) | 避免盤中追價；與 Scanner 數據（昨日收盤）一致 |
| 安全停止 | 回撤熔斷 + 手動覆蓋 | 自動停止防災損；保留人工介入能力 |
| 研究 vs 執行分離 | 同一排程但邏輯獨立 | Stage 2 (research) 可單獨跑，不影響交易 |
| 回測閘門延遲 | Stage 3.5 增加 ~10s 延遲 | 防止部署不獲利策略，延遲可接受（每日僅執行一次） |
| Kill Switch 恢復 | 漸進式 (50%→100%) 而非一次恢復 | 避免恢復後立即再次觸發熔斷；3 天冷靜期確保市場穩定 |

---

## 11. 實測發現與已修復 Bug

> 2026-03-26 首次使用台股 20 支大型股進行完整循環測試

### 11.1 已修復的問題

| Bug | 根因 | 修復 |
|-----|------|------|
| Yahoo Finance 下載失敗 | `datetime` 物件帶時分秒，yfinance 無法解析 | `strftime("%Y-%m-%d")` 截斷 |
| "No valid factors computed" | `AlphaConfig.factors` 預設空 list | `_default_alpha_config()` 自動填入全部 FACTOR_REGISTRY |
| DataFrame truth value ambiguous | `fwd_cache.get(key) or compute(...)` 對 DataFrame 無效 | 改為 `if cached is not None` |
| Backtest 模式下單失敗 | `ExecutionService.submit_orders()` 要求 `current_bars` | executor 偵測 backtest mode 跳過下單 |
| dict 型別因子 AttributeError | Kakushadze alpha 函式回傳 dict 而非 Series | `isinstance(val, dict)` 轉 Series |
| run-now 結果不顯示 | 使用臨時 `AlphaStore()` 而非全局 `state.alpha_store` | 改用全局 store + `save_snapshot()` |
| 前端 poll 永遠卡在下載中 | catch block 空白，404 錯誤不停止 poll | 3 次失敗後 fallback 到 status endpoint |

### 11.2 已知限制

| 限制 | 影響 | 改善方向 |
|------|------|---------|
| **小 universe 下 ICIR 統計量不可靠** | 預設 0.5 符合 Harvey et al. (2016) t>3.0 標準。OOS 衰減 (×0.42) 後要求 IS ICIR > 1.19。20 支大型股的 cross-sectional 變異度太低導致 IC 不穩定——**問題在 universe 太小，不是門檻太高**。 | 等 Shioaji API Key 使用 Scanner 取 150+ 支活躍股（原始設計），或暫時擴大硬編碼 universe 至 50+ 支 |
| **AlphaStore 純 in-memory** | 重啟後歷史資料消失 | 待實作 Alembic migration (005_auto_alpha) |
| **run_full_cycle 耗時 5-6 分鐘** | 21 因子 × 20 支股票 × quantile backtest | 向量化版本 (VECTORIZED_FACTORS) 已實作但 pipeline.research() 仍用逐日窗口；可改用向量化路徑 |
| **Scanner 需要 Shioaji API Key** | 無 key 時 fallback 到 data keys（需預先提供 universe） | run-now 已硬編碼 20 支預設台股；正式運行需 API key |
| **缺少 DB 持久化** | 績效追蹤無法跨 session 累計 | F2d migration 待實作 |
| **沒有盤中即時監控** | StopOrderManager 存在但未接入 auto-alpha 流程 | 需 API key + 即時行情 |

### 11.3 首次實測結果（台股 10 支大型股）

```
Regime: BULL
因子 IC 分析（5 日 forward return）:
  momentum:        IC=+0.157, ICIR=0.63, hit=77.8%  ← 唯一通過 0.5 門檻
  volatility:      IC=-0.116, ICIR=-0.24, hit=37.1%
  rsi:             IC=-0.065, ICIR=-0.18, hit=41.5%
  mean_reversion:  IC=+0.053, ICIR=+0.14, hit=58.1%

結論：
- 動量因子在台股有信號（IC=+0.157），但 10 支大型股 universe 太小，統計量不可靠
- ICIR 門檻 0.5 符合 Harvey et al. (2016) 學術標準，不應下調
- 問題在 universe 規模不足，不是門檻設定——需 150+ 支股票才能產生穩定的 cross-sectional IC
- 等 Shioaji API key 使用 Scanner 動態 universe (150 支) 後重新驗證
```
