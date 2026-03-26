# Phase P：自動化 Alpha 研究 — Claude Code 24 小時因子挖掘

> 狀態：🔵 設計完成，待實作
> 依據：AlphaAgent (KDD 2025) + QuantaAlpha (2026) + RD-Agent(Q) (Microsoft) + FactorMiner + WorldQuant BRAIN
> 目標：讓 Claude Code 自主研究新因子，7×24 持續產出可驗證的 alpha 假說

---

## 1. 設計依據

### 前沿系統調研

| 系統 | 來源 | 核心創新 | 我們採用的 |
|------|------|---------|-----------|
| [AlphaAgent](https://arxiv.org/abs/2502.16789) | KDD 2025 | 三 Agent（Idea/Factor/Eval）+ AST 去重 + 假說對齊 | 三階段架構、AST 去重、語義一致性 |
| [QuantaAlpha](https://arxiv.org/abs/2602.07085) | 2026-02 | 演化軌跡（mutation + crossover）+ 弱步驟定位 | 軌跡級經驗、失敗步驟定位 |
| [RD-Agent(Q)](https://github.com/microsoft/RD-Agent) | Microsoft | 因子+模型共優化、$10 達 2× ARR | 因子+組合共優化 |
| [WorldQuant BRAIN](https://www.worldquant.com/brain/) | WQ 平台 | Fitness = sqrt(\|ret\|/TO) × SR、85K 數據 | Fitness 評分公式、池正交性 |
| [FactorMiner](docs/ref/papers/alpha/) | 本地論文 | Experience Memory + 禁區 + Ralph Loop | Memory 結構、禁區機制 |
| [Claude Code Scheduling](https://code.claude.com/docs/en/scheduled-tasks) | Anthropic | CronCreate + 雲端背景執行 | 排程整合 |

### 為什麼需要自動化？

- 83 因子中僅 4 個營收因子有效（ICIR > 0.3），搜索空間遠未窮盡
- 手動研究 1 因子 ≈ 30 分鐘，自動化 ≈ 60 秒/輪
- AlphaAgent 證明 LLM 驅動挖掘 hit ratio 提高 81%
- 營收因子 ICIR 0.847（60d）說明基本面方向還有大量未探索空間

---

## 2. 三階段架構（改良自 AlphaAgent）

```
┌─────────────────────────────────────────────────────────────┐
│                  ALPHA RESEARCH PIPELINE                      │
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│  │ IDEA     │───→│ FACTOR   │───→│ EVAL     │               │
│  │ AGENT    │    │ AGENT    │    │ AGENT    │               │
│  └──────────┘    └──────────┘    └──────────┘               │
│       │               │               │                      │
│   假說生成         因子實作         多層驗證                  │
│   ├ 讀 Memory     ├ 寫函式        ├ IC/ICIR (4 期限)        │
│   ├ 學術依據      ├ AST 去重      ├ Fitness 評分            │
│   ├ 語義一致性    ├ pytest        ├ 相關性 < 0.5            │
│   └ 禁區過濾      └ 註冊         ├ 年度穩定性              │
│                                   ├ 成本篩選 (TO < 10%)     │
│       ┌───────────────────────────┘                          │
│       ↓                                                      │
│  ┌──────────┐                                                │
│  │ DISTILL  │── 軌跡級經驗回寫 Memory                        │
│  │ + EVOLVE │── 弱步驟定位（哪步失敗？）                     │
│  └──────────┘── 成功模式 / 禁區 / 方向評價                   │
│                                                              │
│  ┌──────────┐                                                │
│  │ MEMORY   │── success_patterns / forbidden / trajectories   │
│  │ (JSON)   │── 跨 session 持久化                            │
│  └──────────┘                                                │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 Idea Agent

產出市場假說，不是隨機生成公式。

**輸入**：Experience Memory + 研究方向配置
**輸出**：結構化假說

```python
@dataclass
class Hypothesis:
    name: str                    # "revenue_gross_margin_interaction"
    description: str             # "營收成長且毛利率改善的公司..."
    formula_sketch: str          # "rank(rev_yoy) × rank(gross_margin_change)"
    expected_direction: int      # +1 or -1
    academic_basis: str          # "Novy-Marx (2013) gross profitability"
    data_requirements: list[str] # ["revenue", "financial_statement"]
    estimated_turnover: str      # "low" | "medium" | "high"
```

**假說來源優先級**：
1. 現有成功因子的變體/交互（revenue_yoy 的衍生）
2. 學術文獻未測試的因子（docs/ref/papers/）
3. FinMind 數據中未利用的欄位
4. QuantaAlpha 式演化（對成功軌跡做 mutation）

### 2.2 Factor Agent

將假說轉為可執行的因子函式。

**關鍵機制**（來自 AlphaAgent）：
- **AST 去重**：比較新因子與現有因子的語法樹結構，corr > 0.8 之前就攔截
- **複雜度控制**：AST 深度 ≤ 5，運算子 ≤ 8 個，防止過擬合
- **語義一致性**：驗證生成的代碼是否真的對應假說描述

```python
# 新因子寫到隔離目錄，不動 technical.py
# src/strategy/factors/research/{hypothesis_name}.py

def revenue_gross_margin_interaction(bars: pd.DataFrame, **kwargs) -> dict[str, float]:
    """營收成長 × 毛利率改善交互因子。"""
    ...
```

### 2.3 Eval Agent

多層驗證管線。

**Fitness 評分**（來自 WorldQuant BRAIN）：

```python
def compute_fitness(ic_mean, icir, turnover, sharpe):
    """WorldQuant BRAIN 式 fitness 評分。"""
    returns_proxy = abs(ic_mean) * 10000  # bps
    to_adj = max(turnover, 0.125)
    fitness = math.sqrt(returns_proxy / to_adj) * sharpe
    return fitness
```

**驗證層級**：

| 層 | 檢查 | 門檻 | 耗時 |
|:--:|------|------|:----:|
| L1 | 快速 IC（20d, 全市場） | \|IC\| > 0.02 | 5s |
| L2 | 多期限 ICIR + 成本 | ICIR > 0.15, TO < 10% | 15s |
| L3 | 相關性 + 年度穩定性 | corr < 0.5, ≥7/10 年正 | 10s |
| L4 | Fitness + 池正交性 | fitness > 現有最低 | 5s |
| L5 | Walk-Forward（通過 L1-L4 才跑） | OOS SR > 0 | 60s |

**只有通過 L4 的因子才進入 L5**，避免浪費 60 秒跑完整 WF。

### 2.4 Distill + Evolve

**軌跡級經驗**（來自 QuantaAlpha）：

```python
@dataclass
class ResearchTrajectory:
    """完整的研究軌跡 — 記錄每一步，不只記結果。"""
    id: str
    hypothesis: Hypothesis
    implementation_success: bool
    eval_results: dict[str, float]  # IC/ICIR/fitness per horizon
    failure_step: str | None        # "hypothesis" | "implementation" | "L1" | "L2" | ...
    failure_reason: str
    duration_seconds: float
    timestamp: str
```

**弱步驟定位**：
- 假說不好 → 調整研究方向優先級
- 實作有 bug → 記錄常見錯誤模式
- L1 失敗（IC 弱）→ 加入禁區
- L2 失敗（高成本）→ 標記「需低頻版本」
- L3 失敗（高相關）→ 加入冗餘群

---

## 3. Experience Memory 結構

```json
{
  "version": 2,
  "stats": {
    "total_rounds": 0,
    "total_pass": 0,
    "total_fail": 0,
    "best_fitness": 0,
    "last_updated": ""
  },
  "success_patterns": [
    {
      "name": "revenue_growth_variants",
      "description": "營收相關因子在台股持續有效",
      "factors": ["revenue_yoy", "revenue_acceleration", "revenue_new_high", "revenue_momentum"],
      "avg_icir": 0.6,
      "avg_fitness": 8.5,
      "evidence": "experiments 12-13",
      "mutation_suggestions": ["加入行業調整", "與毛利率交互", "季節性去趨勢"]
    }
  ],
  "forbidden_regions": [
    {
      "name": "kakushadze_short_term",
      "reason": "換手率 55-84%，台股成本扼殺",
      "factor_patterns": ["高頻日內因子", "volume-price 短期相關"],
      "evidence": "factor_analysis_report"
    },
    {
      "name": "price_dilutes_revenue",
      "reason": "加入 momentum/volatility 會稀釋營收信號",
      "evidence": "experiment 13: ICIR 0.674 → 0.024"
    }
  ],
  "explored_directions": {
    "price_volume": {"status": "exhausted", "best_icir": 0.217, "rounds": 66},
    "institutional_flow": {"status": "weak", "best_icir": 0.086, "rounds": 9},
    "revenue_fundamentals": {"status": "strong", "best_icir": 0.847, "rounds": 4}
  },
  "pending_directions": [
    {"name": "revenue_quality_interaction", "priority": "P0", "hypothesis_count": 0},
    {"name": "seasonal_revenue_patterns", "priority": "P0", "hypothesis_count": 0},
    {"name": "supply_chain_propagation", "priority": "P1", "hypothesis_count": 0},
    {"name": "earnings_surprise_proxy", "priority": "P1", "hypothesis_count": 0},
    {"name": "inventory_turnover", "priority": "P1", "hypothesis_count": 0},
    {"name": "operating_leverage", "priority": "P2", "hypothesis_count": 0},
    {"name": "cash_flow_quality", "priority": "P2", "hypothesis_count": 0},
    {"name": "capex_intensity", "priority": "P2", "hypothesis_count": 0}
  ],
  "trajectories": []
}
```

---

## 4. 研究方向（初始 + 自演化）

### 初始方向（基於 17 次實驗結論）

| 優先級 | 方向 | 假說 | 數據 | 預期 ICIR |
|:------:|------|------|------|:---------:|
| P0 | **營收×毛利率交互** | 營收↑ + 毛利率↑ = 真需求增長 | FinMind 財報 | 0.3+ |
| P0 | **季節性營收偏離** | 實際營收 vs 同行業季節模式的偏離 | FinMind 月營收 | 0.3+ |
| P0 | **營收加速度二階** | d(revenue_acceleration)/dt | FinMind 月營收 | 0.3+ |
| P1 | **供應鏈傳導** | 上游營收 lead 下游 1-2 月 | FinMind 月營收 + 行業 | 0.2+ |
| P1 | **營收驚喜** | 實際 vs 近 6 月趨勢線的殘差 | FinMind 月營收 | 0.3+ |
| P1 | **存貨週轉改善** | 存貨↓ + 營收↑ | FinMind 財報 | 0.2+ |
| P2 | **營業槓桿** | 固定成本高、營收小增 → 利潤大增 | FinMind 財報 | 0.2+ |
| P2 | **現金流品質** | CFO/NI > 1 = 盈餘品質好 | FinMind 財報 | 0.2+ |
| P2 | **資本支出強度** | capex/revenue 變化 | FinMind 財報 | 0.15+ |

### 自演化機制

成功因子自動衍生新方向：
- 如果 `revenue_gross_margin` 通過 → 自動嘗試 `revenue_roe`、`revenue_eps_growth` 等變體
- 如果某行業因子更強 → 自動嘗試行業分層版本
- QuantaAlpha 式 mutation：微調窗口/閾值/正規化方式

---

## 5. Claude Code 排程整合

### 推薦方式：CronCreate

```bash
# 每 2 小時觸發一輪研究（5 個假說）
claude schedule create \
  --cron "0 */2 * * *" \
  --prompt "Run alpha research: python -m scripts.alpha_research_agent --rounds 5. \
            Read data/research/memory.json for context. \
            If any factor has fitness > 8, notify me."
```

### 研究循環的 Claude Code 提示

```
你是 Alpha Research Agent。執行以下步驟：

1. 讀取 data/research/memory.json 的 pending_directions
2. 選擇優先級最高且 hypothesis_count 最低的方向
3. 基於該方向和 success_patterns，產出 1 個因子假說
4. 實作因子到 src/strategy/factors/research/{name}.py
5. 跑 python -m scripts.alpha_research_agent --evaluate {name}
6. 讀取評估結果，更新 memory.json
7. 如果 fitness > 8，輸出 "DISCOVERY: {name} fitness={fitness}"

限制：
- 不修改 src/strategy/factors/technical.py 或 fundamental.py
- 不 git commit（只研究不部署）
- 每輪限制 1 個假說
```

---

## 6. 安全防護

| 防護 | 說明 | 來源 |
|------|------|------|
| 不自動部署 | 因子只寫到 `research/` 子目錄 | — |
| AST 複雜度限制 | 深度 ≤ 5, 運算子 ≤ 8 | AlphaAgent |
| 相關性去重 | 與現有因子 corr < 0.5 | WorldQuant |
| 成本閘門 | 換手率 > 10% 直接拒絕 | 實驗結論 |
| pytest 不退化 | 每輪跑 `pytest tests/ -x` | — |
| Memory 持久化 | JSON 檔，crash 不丟失 | FactorMiner |
| Rate limit | FinMind 600 req/hr，間隔 ≥ 0.7s | — |
| 人工審核 | fitness > 8 的因子通知使用者 | — |
| 軌跡上限 | 保留最近 500 條軌跡，舊的壓縮 | — |

---

## 7. 預期產出

| 指標 | 估計 |
|------|------|
| 每輪耗時 | 快速失敗 ~10s，完整驗證 ~90s |
| 每日有效輪數 | 200-500（含失敗） |
| 每日通過 L4 | 5-20 |
| 每日通過 L5（WF） | 0-3 |
| 每週高品質因子 | 1-5（fitness > 8） |

### 產出文件結構

```
data/research/
├── memory.json                    # Experience Memory
├── factors/                       # 研究用因子代碼
│   ├── revenue_gross_margin.py
│   ├── seasonal_deviation.py
│   └── ...
├── evaluations/                   # 每個因子的評估報告
│   ├── revenue_gross_margin.json
│   └── ...
├── trajectories/                  # 完整研究軌跡
│   ├── 20260327_001.json
│   └── ...
└── daily_summary/                 # 每日摘要
    ├── 2026-03-27.md
    └── ...
```

---

## 8. 實作順序

| 步驟 | 內容 | 依賴 | 估計 |
|:----:|------|------|:----:|
| P1 | ExperienceMemory 類 + Trajectory 結構 | 無 | 30 min |
| P2 | FactorEvaluator 類（包裝現有工具 + Fitness 公式） | 無 | 30 min |
| P3 | alpha_research_agent.py 主循環 | P1 + P2 | 45 min |
| P4 | 初始化 Memory（從 17 次實驗蒸餾） | P1 | 15 min |
| P5 | 第一批假說模板（8 個 P0/P1 方向） | P3 | 30 min |
| P6 | Claude Code CronCreate 排程 | P3 | 10 min |
| P7 | 通知整合（fitness > 8 時） | P3 | 15 min |
| **Total** | | | **~3 hr** |

---

## 9. 成功標準

| 指標 | 1 週後 | 1 月後 |
|------|--------|--------|
| Memory 軌跡數 | > 100 | > 1000 |
| 通過 L4 因子 | > 10 | > 50 |
| fitness > 8 因子 | ≥ 1 | ≥ 5 |
| 因子池正交性 | 新因子 vs 現有 corr < 0.5 | 維持 |
| 研究方向覆蓋 | 4/8 P0-P1 | 8/8 全覆蓋 |
