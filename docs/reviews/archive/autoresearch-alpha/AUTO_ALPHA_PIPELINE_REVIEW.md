# 自動化因子研究管線：架構檢討與重設計

**日期**：2026-03-27
**範圍**：`scripts/alpha_research_agent.py` + `src/alpha/auto/*` 全模組
**結論**：當前系統無法 24/7 自主運行，預計 2-4 週後進入死循環。建議採用 **autoresearch 模式**取代現有架構。

---

## 1. 現有架構

```
┌─────────────────────────────────────────────────┐
│             alpha_research_agent.py              │
│                                                  │
│  while True:                                     │
│    1. _generate_hypothesis(direction)             │
│       └─ 讀 hypothesis_templates.json            │
│       └─ 跳過已測試的 → 回傳第一個未測試的       │
│       └─ 全部測完 → return None                  │
│                                                  │
│    2. _implement_revenue_factor(hypothesis)       │
│       └─ 40+ if/elif 名稱匹配                   │
│       └─ 不匹配 → return None                   │
│                                                  │
│    3. evaluator.evaluate(factor_values)           │
│       └─ L1: |IC_20d| ≥ 0.02                    │
│       └─ L2: ICIR ≥ 0.15 × √(1+ln(N+83))      │
│       └─ L3: 相關性 ≤ 0.50, 年度穩定性         │
│       └─ L4: Fitness ≥ 3.0                      │
│       └─ L5: Walk-forward IC 不反轉             │
│                                                  │
│    4. idle? → _generate_parameter_variants()     │
│       └─ 5 層固定網格（每批最多 5 個）           │
│       └─ 全部用完 → sleep 30 min                │
└─────────────────────────────────────────────────┘
```

### 1.1 組件清單

| 組件 | 檔案 | 職責 |
|------|------|------|
| 主控 | `alpha_research_agent.py` | 假說→實作→驗證→部署 |
| 評估 | `factor_evaluator.py` | L1-L5 五層驗證閘門 |
| 策略構建 | `strategy_builder.py` | 因子→策略物件 |
| 部署決策 | `decision.py` | ICIR/hit_rate/cost 過濾 |
| 執行 | `executor.py` | 決策→下單→風控 |
| 安全 | `safety.py` | 回撤熔斷 + 冷卻 |
| 記憶 | `experience_memory.py` | 軌跡、成功模式、禁區 |
| 告警 | `alerts.py` | regime 變化、IC 反轉 |

---

## 2. 致命缺陷

### 2.1 Harvey 修正失控 — 第 500 輪後新因子不可能通過

L2 門檻公式：`adjusted_threshold = 0.15 × √(1 + ln(total_rounds + 83))`

| 輪數 | total_tested | L2 ICIR 門檻 | 通過率估計 |
|------|-------------|-------------|-----------|
| 0 | 83 | 0.34 | ~20% |
| 100 | 183 | 0.36 | ~15% |
| 500 | 583 | 0.39 | ~5% |
| 1000 | 1083 | 0.42 | ~1% |

**根因**：Harvey (2016) 修正假設所有測試是同一假說族群。`total_rounds` 只增不減，且營收因子和技術因子不應共用計數器。

### 2.2 假說池有限 — 全部基於營收單一維度

**模板總量**：33 base + ~120 variants ≈ **~150 個假說**，全部是營收因子。

| 維度 | 已實作因子 | 被研究使用 | 差距 |
|------|----------|----------|------|
| 營收 | 12 | ✅ 12 | — |
| 技術指標 | 36 | ❌ 0 | 36 |
| 基本面 | 16 | ❌ 0 | 16 |
| Kakushadze 101 | 30 | ❌ 0 | 30 |
| 法人籌碼 | 3 | ❌ 0 | 3 |
| 總經 | 9 | ❌ 0 | 9 |
| **合計** | **106** | **12** | **94 閒置（89%）** |

### 2.3 代碼生成器靠名稱匹配

`_implement_revenue_factor()` 有 40+ if/elif，靠字串匹配產代碼。新名稱不匹配 → 回傳 None → 因子失敗。

### 2.4 idle 邏輯只嘗試一次

`idle_count == 1` 時生成一批（5 個），之後直接 sleep 30 分鐘不再生成。剩餘的潛在變體永遠不會被產出。

### 2.5 資料快取永不重載

`_data_cache` 一旦載入永不更新。股票上市/下市、新資料不反映。長時間運行記憶體膨脹。

### 2.6 軌跡截斷 + 計數器膨脹

500 筆截斷但 `total_rounds` 不重置。跑 1000 輪：只有 500 筆紀錄，Harvey 用 N=1000。

---

## 3. 業界對標

### 3.1 Karpathy autoresearch（2026.03，58k stars）

極簡三文件：`prepare.py`（固定評估）、`train.py`（agent 唯一可改）、`program.md`（人類協議）。
- **2 天 700 個實驗，20 個有效優化，11% 加速**
- Agent 是 Claude Code / Codex，無額外編排器
- git commit 保留改善，git reset 丟棄失敗
- results.tsv 記錄所有實驗
- 單一指標 val_bpb，固定 5 分鐘時間預算

### 3.2 學術前沿（2024-2026）

| 系統 | 方法 | 假說空間 | 核心優勢 |
|------|------|---------|---------|
| AlphaLogics | LLM + 市場邏輯層 | 無限 | 先發現邏輯再約束搜索 |
| AlphaAgent | LLM 3-agent | 無限 | AST 原創性去重 |
| FactorMiner | LLM + 經驗記憶 | 無限 | 成功模式驅動生成（最接近我們） |
| RD-Agent(Q) | LLM + MAB + Qlib | 無限 | 微軟開源，$10 成本達 2x ARR |
| Alpha2 | RL + MCTS | 10^63 | 維度一致性裁剪 |
| AlphaGen | PPO | 無限 | 協同 alpha 集合優化 |

**共同趨勢**：無限假說空間、結構化驗證、AST 去重、協同優化。

### 3.3 Deflated Sharpe Ratio vs √(1+ln(N))

DSR (Bailey & Lopez de Prado, 2014) 額外考慮偏態/峰態，直接給 p-value，比我們的 √(1+ln(N)) 更嚴格且有理論基礎。

---

## 4. 決策：採用 autoresearch 模式

### 4.1 為什麼不漸進改良

原計畫（Section 5 舊版）是 4 個 Phase 漸進修改現有 `alpha_research_agent.py`：擴因子維度、加組合生成器、改 Harvey 分組。預計 2 週。

**問題**：這是在錯誤架構上打補丁。現有架構的根本問題是「假說生成 + 代碼生成 + 評估」全耦合在一個 1800 行的檔案裡，改任何一層都要動全部。

### 4.2 autoresearch 模式的優勢

| 維度 | 現有架構 | autoresearch 模式 |
|------|---------|------------------|
| 假說生成 | 模板 + 網格（~150 個） | **LLM 自由生成（無限）** |
| 代碼生成 | 40+ if/elif 名稱匹配 | **Agent 直接寫 Python** |
| 評估 | 耦合在 agent 裡 | **獨立 evaluate.py（不可改）** |
| 實驗追蹤 | memory.json（截斷、膨脹） | **results.tsv + git history** |
| 架構複雜度 | 8 個組件，1800+ 行 | **3 個文件，~300 行** |
| 持續性 | daemon 模式（會停） | **Agent session（LLM 驅動）** |
| 擴展性 | 需改代碼加因子 | **Agent 自己探索所有維度** |
| look-ahead 安全 | 依賴因子代碼自律 | **evaluate.py 強制 40 天截斷** |

### 4.3 解決 autoresearch 原版的量化適配問題

autoresearch 原版（ML 訓練）和量化因子研究有結構差異，需要適配：

| 差異 | autoresearch 原版 | 我們的適配 |
|------|------------------|-----------|
| 目標 | 改善一個模型 | 發現多個獨立因子 |
| 評估能捕捉所有 bug | ✅ val_bpb 全包 | ⚠️ look-ahead bias 看不出來 |
| 指標 | 單一（val_bpb） | 多個（ICIR, Sharpe...） |
| keep/discard | 二元 | 可共存多個因子 |

**適配方案**：

1. **Look-ahead bias 在評估層強制** — `evaluate.py` 在呼叫 `compute_factor()` 前截斷營收資料到 `as_of - 40 天`。不管 factor.py 怎麼寫，都不可能用到未來資料。

2. **多指標壓成單一 composite_score** — 加權組合 ICIR(50%) + Fitness(30%) + 年度穩定性(20%)，讓 keep/discard 決策簡單化。

3. **多因子共存** — 不只保留「最佳」，每個通過 L4 的因子都 git tag 保留。Agent 可以回到任何成功因子的 commit 做變體。

### 4.4 新架構

```
autoresearch-alpha/
├── evaluate.py      ← 固定（READ ONLY）
│   ├─ 載入 data/market/ + data/fundamental/ 資料
│   ├─ 每 20 交易日取樣 IC
│   ├─ 40 天營收延遲在這裡強制（agent 無法繞過）
│   ├─ 計算 IC/ICIR/Fitness/年度穩定性
│   └─ 輸出 composite_score + 詳細指標
│
├── factor.py        ← Agent 唯一可改
│   └─ compute_factor(symbols, as_of, data) → dict[str, float]
│
├── program.md       ← 人類寫的研究協議
│   ├─ 實驗循環指令（改→commit→跑→記錄→keep/discard）
│   ├─ 因子探索策略（先單因子→再組合→再微調）
│   ├─ 永不停止指令
│   └─ 簡單性準則
│
└── results.tsv      ← 實驗記錄（gitignored）
    └─ commit | composite_score | icir_20d | sharpe | status | description
```

**Agent 循環**：
```
1. 讀 results.tsv 了解歷史
2. 改 factor.py（實作新因子想法）
3. git commit -m "experiment: ..."
4. python evaluate.py > run.log 2>&1
5. 從 run.log 提取 composite_score
6. composite_score 改善 → keep，否則 → git reset
7. 記錄到 results.tsv
8. 回到 1
```

### 4.5 可用資料（agent 在 factor.py 中可存取）

```python
data["bars"][symbol]            # pd.DataFrame: open, high, low, close, volume
data["revenue"][symbol]         # pd.DataFrame: date, revenue, yoy_growth
data["institutional"][symbol]   # pd.DataFrame: date, trust_net, foreign_net, dealer_net
data["pe"][symbol]              # float: 最新 PE ratio
data["pb"][symbol]              # float: 最新 PB ratio
data["roe"][symbol]             # float: 最新 ROE %
```

Agent 可以自由組合這些資料計算任何因子：動量、價值、品質、營收、法人籌碼、波動率...

### 4.6 安全設計

| 風險 | 防護 |
|------|------|
| Look-ahead bias（營收） | evaluate.py 在呼叫前截斷資料到 as_of - 40 天 |
| Agent 改評估標準 | evaluate.py 標記 READ ONLY，program.md 明確禁止 |
| 過擬合 | IC 用 Spearman rank（對異常值穩健）+ 年度穩定性 |
| Data mining | 保留 results.tsv 完整紀錄，可事後計算 DSR |
| 因子複雜度爆炸 | program.md 的簡單性準則：小改善 + 大複雜度 = 不保留 |

---

## 5. 實施計畫

### Phase 1：框架搭建（1 天） ✅ 已完成（v2 更新）

- [x] `evaluate.py` v2 — L1 early-exit + IC-series 去重 + 大規模 IC 驗證 + 40 天延遲強制
- [x] `factor.py` — baseline 因子（12-1 momentum）
- [x] `program.md` v2 — 研究協議 + 禁區列表 + 評估管線說明 + 可用資料文檔
- [x] `README.md` — 說明文件

### Phase 2：整合到系統（1-2 天）

| 任務 | 說明 |
|------|------|
| 搬到 `scripts/autoresearch/` | 作為正式功能 |
| 驗證資料載入 | 確認 parquet 讀取正常 |
| 跑 baseline | 確認 evaluate.py 端到端可執行 |
| 加 results.tsv | 初始化實驗記錄 |
| git worktree | 在獨立 worktree 跑，不影響主 repo |

### Phase 3：首次 agent run（1 天）

| 任務 | 說明 |
|------|------|
| 啟動 Claude Code session | 指向 autoresearch 目錄 |
| 跑 50-100 輪 | 驗證循環穩定性 |
| 檢查 results.tsv | 確認記錄完整 |
| 檢查 git history | 確認 keep/discard 正確 |

### Phase 4：對比驗證（2-3 天）

| 任務 | 說明 |
|------|------|
| 比較 autoresearch vs 舊 agent | 同等時間發現幾個有效因子？ |
| 計算 DSR | 對 results.tsv 所有實驗做 Deflated Sharpe |
| 通過因子入 Validator | 好的因子用 StrategyValidator 15 項驗證 |

---

## 6. 保留什麼、丟棄什麼

### 保留（從現有系統繼承）

| 組件 | 原因 |
|------|------|
| `FactorEvaluator` L1-L5 邏輯 | 整合進 evaluate.py |
| `StrategyValidator` 15 項 | 通過因子的最終驗證 |
| `experience_memory.py` 的禁區機制 | 寫進 program.md 指示 |
| `data/fundamental/` 資料 | evaluate.py 直接讀取 |
| 大規模 IC 驗證流程 | 通過因子的二次確認 |

### 丟棄（被 autoresearch 取代）

| 組件 | 原因 |
|------|------|
| `_generate_hypothesis()` | LLM 自己生成，不需模板 |
| `_implement_revenue_factor()` | LLM 直接寫 factor.py |
| `_generate_parameter_variants()` | LLM 自己決定參數 |
| `hypothesis_templates.json` | 不再需要固定模板池 |
| `HYPOTHESIS_TEMPLATES` 硬編碼 | 同上 |
| daemon 模式的 idle/sleep 邏輯 | Agent session 取代 |
| `memory.json` 的 trajectories | results.tsv + git history 取代 |

### 從舊系統採納的設計（v2 更新）

經比對，舊系統有 5 個優點是 autoresearch 原版缺少的，已整合進 evaluate.py v2：

| 舊系統優點 | 如何整合 | 效果 |
|-----------|---------|------|
| **L1 early-exit** | evaluate.py 先跑 30 個日期算 IC，< 0.02 立即停止 | 差因子 30 秒淘汰（vs 3 分鐘） |
| **IC-series 去重** | evaluate.py 載入 `baseline_ic_series.json`，算新因子 IC 與已知因子的相關性 | 防止 clone 因子通過（比 LLM 判斷更可靠） |
| **大規模 IC 驗證** | L4 通過後自動跑 865+ 支台股，要求 ICIR(20d) >= 0.20 | 防小 universe 假陽性 |
| **禁區列表** | 寫進 program.md（Forbidden Zones 段落） | Agent 不浪費時間在已知死路 |
| **事後 DSR** | results.tsv 記錄所有實驗，session 後可計算 Deflated Sharpe Ratio | 多重檢定修正 |

### 不確定（需要驗證）

| 組件 | 考量 |
|------|------|
| Harvey 修正 | evaluate.py 不內建 Harvey 門檻（避免失控），改用事後 DSR 檢定 |
| `strategy_builder.py` | 通過因子仍需包裝成 Strategy 物件做回測 |
| `decision.py` | 部署決策邏輯可能還需要 |
| `alerts.py` | 告警系統獨立於研究流程 |

---

## 7. 風險

### 7.1 LLM 生成代碼的安全性

autoresearch 原版的 evaluate（val_bpb）能捕捉所有 bug。量化領域有額外風險，逐一處理：

| 風險 | 防護 | 狀態 |
|------|------|------|
| Look-ahead bias（營收） | evaluate.py 在呼叫前截斷到 as_of - 40 天 | ✅ |
| Look-ahead bias（價格） | data["bars"] 傳入時已用 `.loc[:as_of]` | ⚠️ factor.py 自己要注意 |
| 零除錯誤 | crash 被 evaluate.py try/except 捕捉 | ✅ |
| 非法數據存取 | evaluate.py 只傳 masked_data | ✅ |
| 過度複雜因子 | program.md 簡單性準則 + 人類審查 git diff | ✅ |
| Clone 因子 | IC-series 去重 (corr <= 0.50) | ✅ |
| 小樣本假陽性 | Stage 2 大規模驗證 (865+ 支) | ✅ |
| 多重檢定 | results.tsv 全記錄 + 事後 DSR | ✅ |

### 7.2 Claude Code session 限制

- **Context window** — 長時間跑會壓縮上下文，丟失早期實驗細節
- **Session 中斷** — 需要能跨 session 恢復（results.tsv + git history 持久化）
- **成本** — 每個實驗消耗 LLM tokens，比現有 daemon 模式貴

### 7.3 資料品質

- evaluate.py 的資料載入只做一次（cached），長時間跑會過時
- 建議每個 session 開始時重新載入

---

## 8. 結論

### 舊方案 vs 新方案

| 維度 | 舊方案（漸進改良） | 新方案（autoresearch 模式） |
|------|------------------|--------------------------|
| 工作量 | ~2 週 | ~3 天 |
| 架構複雜度 | 8 組件，2000+ 行 | 3 文件，~300 行 |
| 假說空間 | 50,000+（組合網格） | **無限**（LLM 生成） |
| 因子維度 | 106（需手動登錄） | **全部**（Agent 自由探索） |
| look-ahead 安全 | 依賴因子代碼 | **評估層強制** |
| 維護成本 | 高（模板 + 代碼生成器） | 低（只維護 evaluate.py） |
| 可審查性 | memory.json（難讀） | **git history + results.tsv** |

### 建議方向

**採用 autoresearch 模式作為主力因子研究框架。** 融合舊系統的 5 個優點（early-exit、去重、大規模驗證、禁區、DSR）。保留 StrategyValidator 作為最終驗證。

```
autoresearch (探索)
  └─ evaluate.py v2: L1 early-exit + IC-series 去重 + 大規模驗證
     ↓
StrategyValidator (驗證) → 15 項嚴格檢查
     ↓
Paper Trading (觀察) → 30 天真實市場驗證
     ↓
Live (部署) → 正式交易
```

現有的 `alpha_research_agent.py` 保留為 fallback（不需要 LLM 的場景）。

### 已完成的變更

| 變更 | 來源 | 狀態 |
|------|------|------|
| 採用 autoresearch 三文件架構 | Karpathy autoresearch | ✅ |
| 評估函數不可修改 | autoresearch | ✅ |
| git commit + reset 實驗管理 | autoresearch | ✅ |
| L1 early-exit 快篩 | 舊系統 factor_evaluator | ✅ evaluate.py v2 |
| IC-series 數值去重 | 舊系統 L3 correlation check | ✅ evaluate.py v2 |
| 大規模 IC 驗證（865+ 支） | 舊系統 large_scale_check | ✅ evaluate.py v2 Stage 2 |
| 禁區列表 | 舊系統 forbidden_regions | ✅ program.md |
| 事後 DSR 多重檢定 | Bailey & Lopez de Prado | ✅ results.tsv 支持 |
| 全因子空間探索 | 業界共識 | ✅ program.md + data dict |
| 簡單性準則 + 永不停止 | autoresearch | ✅ program.md |

### 下一步

1. **整合到系統** — 搬到 `scripts/autoresearch/`，驗證資料載入可跑
2. **產出 baseline_ic_series.json** — 用已知因子填充去重資料庫
3. **跑首次 session** — 50-100 輪，驗證循環穩定性
4. **通過因子入 StrategyValidator** — 15 項完整驗證

### 參考文獻

- Karpathy, A. (2026). autoresearch. https://github.com/karpathy/autoresearch
- Bailey, D. & Lopez de Prado, M. (2014). The Deflated Sharpe Ratio.
- Harvey, C., Liu, Y. & Zhu, H. (2016). …and the Cross-Section of Expected Returns. RFS.
- AlphaLogics (2025). Market Logic-Guided Alpha Mining. arXiv:2603.20247
- AlphaAgent (2025). LLM Multi-Agent for Alpha Mining. arXiv:2502.16789
- FactorMiner (2025). Self-Evolving Agent. arXiv:2602.14670
- Microsoft RD-Agent (2024). https://github.com/microsoft/RD-Agent
- Alpha2 (2024). RL + MCTS for Alpha Discovery. arXiv:2406.16505
- AlphaGen (KDD 2023). PPO for Synergistic Alpha Sets.
- Warm-Start GP (2024). Efficient GP for Trading. arXiv:2412.00896
