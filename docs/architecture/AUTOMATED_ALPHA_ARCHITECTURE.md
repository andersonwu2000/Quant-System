# 自動化 Alpha 系統架構 v3.0

> **日期**: 2026-03-27
> **狀態**: Phase P 已實作因子挖掘，本文設計 Research → Validate → Paper Trading 完整閉環
> **前置**: 13 策略、83 因子、StrategyValidator 13 項、FinMind 8 dataset、895 支價格

---

## 1. 設計動機

### 現狀（已完成）

```
手動研究 → 17 次實驗 → revenue_momentum 策略 → StrategyValidator 11/13 → 等 CA 憑證
Phase P Agent → 3 個新因子（ICIR 0.47-0.80）→ docs/research/ 報告 → 人工審閱
```

### 目標（本架構）

```
Auto Research Agent 24/7 挖掘因子
    → 通過 L1-L5 五層驗證
        → 自動建構 FilterStrategy
            → StrategyValidator 13 項全過
                → 自動部署到 Paper Trading（限額）
                    → 30 天績效追蹤
                        → 人工審閱決定是否進 Live
```

**核心原則**：研究自動化、驗證自動化、Paper Trading 自動化，但 **Live 交易需人工確認**。

---

## 2. 系統架構總覽

```
┌────────────────────────────────────────────────────────────────────┐
│                    AUTOMATED ALPHA SYSTEM v3                        │
│                                                                    │
│  ┌─────────┐   ┌─────────┐   ┌──────────┐   ┌──────────────────┐ │
│  │ RESEARCH │──→│ VALIDATE│──→│  BUILD   │──→│  PAPER TRADING   │ │
│  │  AGENT   │   │  GATE   │   │ STRATEGY │   │  (Auto-Deploy)   │ │
│  │ (Phase P)│   │ (13項)  │   │          │   │                  │ │
│  └─────────┘   └─────────┘   └──────────┘   └──────────────────┘ │
│       │              │              │               │              │
│  Experience     Harvey校正     FilterStrategy   Position Limit   │
│  Memory         PBO/DSR/OOS    Auto-Config      Max 5% NAV      │
│  (JSON)         Bootstrap      Monthly Rebal    Kill Switch      │
│       │              │              │               │              │
│       ↓              ↓              ↓               ↓              │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                    MONITORING + FEEDBACK                      │ │
│  │  ├── 每日 NAV snapshot                                       │ │
│  │  ├── Factor decay 監控（近 60 天 IC）                        │ │
│  │  ├── 與回測結果 R² 比對                                      │ │
│  │  ├── DD 告警 → 自動降倉/停止                                 │ │
│  │  └── 月報 → 人工審閱                                         │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│                              ↓                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                    HUMAN REVIEW GATE                          │ │
│  │  Paper Trading 30 天報告 → 人工確認 → Live Trading            │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. 六階段流水線

### Stage 1: Research Agent（24/7 自動）

已實作：`scripts/alpha_research_agent.py`

```
CronCreate 排程 → 每 2 小時
    → 讀 Experience Memory
    → 選方向 + 產假說
    → 實作因子代碼（src/strategy/factors/research/）
    → 五層驗證（L1-L5）
    → 蒸餾回 Memory
    → 通過者寫報告到 docs/research/
```

**安全**：Harvey (2016) 動態門檻、禁區機制、不動核心代碼

### Stage 2: Validation Gate（自動）

已實作：`src/backtest/validator.py`

通過 L5 的因子**自動建構 FilterStrategy 並用該策略跑 StrategyValidator**：

```
因子通過 L5
    → strategy_builder.build_from_research_factor(factor_name)
    → 產出 FilterStrategy（用該因子篩選 + 排序）
    → StrategyValidator.validate(filter_strategy, universe, ...)
    → 比較 Sharpe vs 0050.TW Sharpe（風險調整基準）
```

**注意**：Validator 必須用因子自己的策略，不能用固定的 revenue_momentum。

| # | 檢查 | 門檻 |
|---|------|------|
| 1 | CAGR | > 15% |
| 2 | Sharpe | > 0.7 |
| 3 | MDD | < 50% |
| 4 | Walk-Forward | ≥ 60% 年正 |
| 5 | PBO | < 50% |
| 6 | Deflated Sharpe | > 0.95（含 Harvey 校正） |
| 7 | Bootstrap P(SR>0) | > 80% |
| 8 | OOS 2025 H2 | > 0% |
| 9 | vs 1/N 超額 | > 0% |
| 10 | 成本佔比 | < 50% × gross |
| 11 | Factor decay | 近 252 天 SR > 0 |
| 12 | Universe | ≥ 50 支 |
| 13 | Worst regime | > -30% |

**全部 13 項通過才能進入 Stage 3。**

### Stage 3: Build Strategy（自動）

將通過驗證的因子自動包裝成 FilterStrategy：

```python
# 自動生成的策略配置
config = FilterStrategyConfig(
    filters=[
        FilterCondition(new_factor_name, "gt", threshold),  # 新因子篩選
        FilterCondition("volume_20d_avg", "gt", 300),       # 流動性
    ],
    rank_by=new_factor_name,
    top_n=10,
    rebalance="monthly",
    max_weight=0.10,
)
```

### Stage 4: Paper Trading（自動部署，限額）

**部署條件**（全部滿足才部署）：

| 條件 | 門檻 | 說明 |
|------|------|------|
| Sharpe | > 0050.TW Sharpe | 風險調整必須打敗大盤 |
| CAGR | > 8% | 最低絕對報酬 |
| StrategyValidator | ≥ 10/13 | 多數統計檢驗通過 |

**限額機制**（防止自動部署造成大額損失）：

| 限制 | 值 | 說明 |
|------|------|------|
| 單策略最大 NAV | 5% | 新發現的策略最多用 5% 資金 |
| 同時最大自動策略數 | 3 | 最多 3 個 auto-discovered 策略並行 |
| 單策略最大持倉 | 3 檔 | 比手動策略的 15 檔少 |
| Kill Switch | 3% DD | 比手動的 5% 更嚴格 |
| 自動停止 | 30 天後 | 30 天後自動停止，等人工審閱 |

### Stage 5: Monitoring（自動）

```
每日：
    ├── NAV snapshot → data/paper_trading/auto/{strategy}/daily.json
    ├── Factor IC 監控（近 60 天 rolling IC）
    ├── 與回測 R² 比對
    └── DD 超過 3% → 自動停止 + 通知

每週：
    └── 週報 → docs/research/{strategy}/weekly_{date}.md

每月：
    └── 月報（含 vs 回測比較）→ 通知使用者審閱
```

### Stage 6: Human Review Gate（人工）

**Paper Trading 30 天後，系統自動產出審閱報告：**

```markdown
# Auto-Strategy Review: {name}

## 績效
- Paper P&L vs Backtest P&L: R² = ?
- Sharpe (paper): ? vs Sharpe (backtest): ?
- Trades: ?

## 建議
- [ ] 加入正式策略庫 → Live Trading
- [ ] 延長 Paper Trading 30 天
- [ ] 降倉繼續觀察
- [ ] 停止並加入 Experience Memory 禁區
```

**Live Trading 永遠需要人工確認。**

---

## 4. 與現有系統的整合點

| 組件 | 已有 | 新增 |
|------|:----:|:----:|
| Research Agent | ✅ `scripts/alpha_research_agent.py` | — |
| Experience Memory | ✅ `src/alpha/auto/experience_memory.py` | — |
| Factor Evaluator (L1-L5) | ✅ `src/alpha/auto/factor_evaluator.py` | — |
| StrategyValidator (13 項) | ✅ `src/backtest/validator.py` | — |
| FilterStrategy | ✅ `src/alpha/filter_strategy.py` | — |
| Monthly Scheduler | ✅ `src/scheduler/jobs.py` | — |
| Notification | ✅ `src/notifications/` | — |
| SimBroker | ✅ `src/execution/broker/simulated.py` | — |
| SinopacBroker | ✅ `src/execution/broker/sinopac.py` | — |
| **Auto Strategy Builder** | ❌ | 新增 |
| **Auto Paper Deploy** | ❌ | 新增 |
| **Auto Monitoring** | ❌ | 新增 |
| **Review Report Generator** | ❌ | 新增 |

### 需新增的 4 個模組

```
src/alpha/auto/
├── experience_memory.py    # ✅ 已有
├── factor_evaluator.py     # ✅ 已有
├── strategy_builder.py     # 新增：自動建構 FilterStrategy
├── paper_deployer.py       # 新增：自動部署到 Paper Trading
├── auto_monitor.py         # 新增：每日監控 + 告警
└── review_generator.py     # 新增：30 天報告生成
```

---

## 5. 排程配置

| 任務 | 排程 | 說明 |
|------|------|------|
| Alpha Research | `0 */2 * * *` | 每 2 小時一輪 |
| Revenue Update | `30 8 11 * *` | 每月 11 日更新營收 |
| Revenue Rebalance | `5 9 11 * *` | 每月 11 日再平衡 |
| Auto Monitor | `0 14 * * 1-5` | 每日收盤後 |
| Weekly Report | `0 18 * * 5` | 每週五下午 |
| Monthly Review | `0 9 1 * *` | 每月 1 日 |

---

## 6. 安全防護層

### 6.1 研究層防護

| 機制 | 說明 |
|------|------|
| Harvey (2016) | ICIR 門檻隨 sqrt(1+log(N)) 提高 |
| Experience Memory 禁區 | 不重複測試已知無效方向 |
| AST 複雜度控制 | 因子深度 ≤ 5 |
| 不動核心代碼 | 研究因子寫到 `research/` 子目錄 |

### 6.2 驗證層防護

| 機制 | 說明 |
|------|------|
| StrategyValidator 13 項 | 全部通過才進入 Paper |
| PBO < 50% | Bailey 2015 過擬合檢測 |
| OOS holdout | 獨立期間驗證 |
| Factor decay | 近期仍有效 |

### 6.3 Paper Trading 防護

| 機制 | 說明 |
|------|------|
| 5% NAV 限額 | 單策略最大資金 |
| 3% DD Kill Switch | 比手動更嚴格 |
| 30 天自動停止 | 到期需人工確認 |
| 最多 3 策略並行 | 防止過度分散 |

### 6.4 Live Trading 防護

| 機制 | 說明 |
|------|------|
| **永遠需要人工確認** | 自動系統不能自行進入 Live |
| Paper vs Backtest R² | 低 R² = 回測不可信 |
| 30 天 Paper 報告 | 必須審閱通過 |

---

## 7. 數據流

```
FinMind 月營收（每月 11 日更新）
    ↓
Alpha Research Agent（因子假說 → 實作 → L1-L5 驗證）
    ↓
Experience Memory（成功/失敗/禁區）
    ↓
通過 L5 → StrategyValidator 13 項
    ↓
全過 → Auto Strategy Builder（FilterStrategy 配置）
    ↓
Auto Paper Deployer（限額部署 → SimBroker/SinopacBroker）
    ↓
Auto Monitor（每日 NAV + IC 追蹤 + DD 告警）
    ↓
30 天報告 → 人工審閱 → Live 或停止
```

---

## 8. 實作順序

| 步驟 | 內容 | 依賴 | 狀態 |
|:----:|------|------|:----:|
| 1 | Experience Memory | — | ✅ |
| 2 | Factor Evaluator (L1-L5) | — | ✅ |
| 3 | Research Agent (主循環) | 1+2 | ✅ |
| 4 | Research 假說模板 | 3 | ✅ |
| 5 | Harvey 多重測試校正 | 2 | ✅ |
| 6 | Auto Strategy Builder | 3 | 🔵 待實作 |
| 7 | Auto Paper Deployer | 6 | 🔵 待 CA 憑證 |
| 8 | Auto Monitor | 7 | 🔵 待 Paper Trading |
| 9 | Review Report Generator | 8 | 🔵 待 30 天數據 |
| 10 | Claude Code CronCreate 排程 | 3 | 🔵 待設定 |

---

## 9. 與 FinLab 的差異

| 維度 | FinLab | 我們 |
|------|--------|------|
| 因子搜索 | 900+ 指標 + AI 搜索 | 83 因子 + Auto Research Agent |
| 驗證嚴謹度 | `verify_strategy()` | StrategyValidator 13 項 + Harvey + PBO |
| 自動化程度 | 手動選策略 | **Research → Validate → Paper 全自動** |
| 下行保護 | Beta -0.43 策略 | Composite regime hedge |
| 多策略 | 54 策略輪動 | 多策略等權 + auto-discovered |
| 數據 | 全台股含下市 | 895 支含 40 下市（FinMind） |
| **獨特優勢** | 社群 + 數據量 | **24/7 自動研究 + 嚴格統計驗證 + 閉環自動化** |
