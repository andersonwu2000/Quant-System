# Autoresearch 架構檢討 — 與 FinLab AI Factor Mining Agent 比較

**日期**：2026-03-29
**來源**：[FinLab AI Factor Mining Agent](https://www.finlab.finance/blog/ai-factor-mining-agent)、[FactorMiner 論文](https://arxiv.org/abs/2602.14670) (Wang et al., 2026)
**範圍**：架構設計、評估管線、記憶機制、安全性、效率、結果

---

## 1. 架構比較

### FinLab / FactorMiner：Ralph Loop（4 階段自我演化）

```
Retrieve（檢索記憶）→ Generate（LLM 生成因子）→ Evaluate（4 階段過濾）→ Distill（寫回知識庫）
```

- **框架**：Agno agent framework + Claude Sonnet 4.5
- **記憶**：3 層（Session / User / Learned）持久化到 SQLite
- **運算子**：60+ GPU 加速金融運算子（CsRank 26x、TsRank 17x 加速）
- **吞吐量**：~1,000 個候選因子 / 6 分鐘（GPU A100）
- **目標市場**：A 股（10 分鐘 K 線）+ 台股（日頻）

### 我們：Karpathy 3-File（固定評估 + 自由假說）

```
Agent 改 factor.py → commit → python evaluate.py → 記錄 results.tsv → 重複
```

- **框架**：Claude Code CLI + 3 個檔案（evaluate.py / factor.py / program.md）
- **記憶**：results.tsv（append-only TSV），無結構化知識庫
- **運算子**：raw pandas（無預定義運算子庫）
- **吞吐量**：~17 個實驗 / 小時（CPU，含 LLM 回應時間）
- **目標市場**：台股（日頻）

### 差異分析

| 維度 | FinLab | 我們 | 差距 |
|------|--------|------|------|
| 評估吞吐量 | ~10,000/hr (GPU) | ~17/hr (CPU+LLM) | **~600x** |
| 記憶機制 | 結構化知識庫 + 語義檢索 | 平面 TSV | 顯著 |
| 運算子庫 | 60+ 預定義 + GPU | 無，agent 自由寫 pandas | 顯著 |
| 去重機制 | 相關性 0.50 + 替換機制 | 相關性 0.50（無替換） | 中等 |
| 安全隔離 | 未提及 | Docker + Thresholdout + READ-ONLY | **我們領先** |
| OOS 保護 | 未提及 Thresholdout | Laplace noise + budget tracking | **我們領先** |
| 因子複雜度控制 | 運算子組合（天然受限） | 80 行限制（prompt 層級） | 不同策略 |

---

## 2. 評估管線比較

### FinLab 4 階段

| 階段 | 條件 | 通過率 |
|------|------|:------:|
| 1. IC 快篩 | \|IC\| ≥ 0.04 | ~40% |
| 2. 相關性檢查 | max \|ρ\| < 0.50（與已知因子） | ~25% |
| 2.5 替換 | IC ≥ 0.10 且 ≥ 1.3× 被替換因子 | — |
| 3. 批次去重 | 批次內 ρ < 0.70 | ~15% |
| 4. 完整驗證 | 全資產回測，ICIR ≥ 0.50 | ~8% |

**淨通過率**：100 個候選 → ~8 個有效因子

### 我們 5+1 階段

| 階段 | 條件 | 門檻 |
|------|------|------|
| L0 | 代碼行數 | ≤ 80 行 |
| L1 | IC 快篩（前 30 日） | \|IC_20d\| ≥ 0.02 |
| L2 | ICIR（最佳 horizon） | \|ICIR\| ≥ 0.15 |
| L3a | 相關性去重 | ρ ≤ 0.50 |
| L3b | 年度穩定性 | ≥ 4/6.5 年正 |
| L4 | WorldQuant Fitness | ≥ 3.0 |
| L5 | OOS 驗證（Thresholdout） | IC sign + ICIR decay ≤ 60% + positive ratio ≥ 50% |
| Stage 2 | 大規模驗證（865+ 支） | ICIR ≥ 0.20 |

### 關鍵差異

**1. IC 門檻：FinLab 0.04 vs 我們 0.02**

FinLab 用 0.04 是因為 A 股 10 分鐘 K 線的 IC 天然較高（高頻 = 更多信號）。我們用 0.02 是日頻台股，信號更弱。**門檻本身合理，但我們沒有根據市場特性做 calibration** — 0.02 是拍腦袋定的。

**建議：** 用 permutation test 校準 L1 門檻。隨機打亂因子值計算 IC 分佈，把門檻設在 95th percentile。

**2. FinLab 有「替換機制」，我們沒有**

FinLab 的 Stage 2.5：如果新因子 IC ≥ 0.10 且 ≥ 1.3× 某個已知因子，允許替換。這解決了「因子庫飽和後無法改善」的問題。

我們的系統：一旦因子和已知因子相關性 > 0.50，直接 reject。沒有「更好的同類因子替換較差的」機制。

**這是我們的結構性缺陷。** 隨著實驗次數增加，越來越多的新因子被 L3 correlation check 擋掉，但其中可能有比現有因子更好的。

**建議：** 加入替換邏輯 — 如果新因子 ICIR ≥ 1.3× 相關因子的 ICIR，允許替換。

**3. FinLab 有批次去重（Stage 3），我們沒有**

FinLab 在單一批次內做因子間去重（ρ < 0.70），防止一批次產出的因子彼此高度相關。我們沒有批次概念（每次只產一個因子），所以不需要。**但** 這也意味著我們缺少對因子庫整體多樣性的主動管理。

**4. FinLab 沒有 OOS Thresholdout，我們有**

FinLab 的評估管線沒有提到 holdout 保護機制。他們的 OOS 驗證是直接的（2025 年作為固定 test set），沒有加噪音。

我們的 L5 用了 Dwork et al. (2015) Thresholdout — 每次 OOS 查詢加 Laplace(0, 0.05) 噪音。**這是我們的優勢。**

**5. FinLab 沒有提到 Stage 2 大規模驗證**

我們的 Stage 2 要求 L5 通過後在 865+ 支股票上驗證 ICIR ≥ 0.20，防止小樣本偏差。FinLab 沒有等價機制（但他們的 A 股 universe 本身就很大：CSI500/CSI1000）。

---

## 3. 記憶機制：最大差距

### FinLab：結構化經驗記憶（Ralph Loop 的 Distill 階段）

```python
Agent(
    knowledge=learnings_kb,        # 持久化知識庫
    search_knowledge=True,         # 語義檢索
    enable_agentic_memory=True,    # 跨 session 記憶
    db=SqliteDb("factor_mining.db"),
)
```

**記錄內容：**
- 成功方向（Recommended Directions）：「Higher-moment regimes 用 Skew/Kurt 做 IfElse 條件」
- 禁止方向（Forbidden Directions）：「VWAP 偏差變體 > 0.5 相關性」「簡單 delta 反轉 > 0.5」
- 台股特定經驗：「營收新高 + 品質 + 動量 = 台股最佳信號組合」

**效果（消融研究）：**
- 有記憶：60.0% 高品質產出率，冗餘拒絕率 55.2%
- 無記憶：20.0% 高品質產出率，冗餘拒絕率 43.8%
- **記憶帶來 3x 效率提升**

### 我們：平面 TSV + program.md 靜態指引

```
# results.tsv — 唯一的「記憶」
commit | score | icir | level | status
abc... | 12.49 | 0.51 | L5    | KEEP
```

**記錄內容：** 實驗結果（pass/fail、score、ICIR）。不記錄為什麼失敗、不記錄探索方向、不記錄模式。

**program.md 的 Forbidden Zones：** 靜態列表，不會根據實驗結果動態更新。

### 影響分析

| 場景 | FinLab | 我們 |
|------|--------|------|
| Agent 嘗試已知無效方向 | 檢索記憶 → 跳過 | 可能重複嘗試 |
| Agent 發現有效模式 | 記錄模式 → 未來複用 | 只記錄結果，模式在 context 消失後丟失 |
| Session 重啟 | 從知識庫恢復所有經驗 | 只讀 results.tsv（無模式資訊） |
| 200+ 實驗後 | 冗餘探索被記憶阻擋（55.2% 拒絕率） | 無阻擋，可能重複探索 |

**這是我們最大的結構性劣勢。** 我們的 agent 每次 session 重啟都會丟失所有經驗模式。results.tsv 只有結果，沒有「為什麼這個方向失敗」的知識。

**但需要注意：** FinLab 的記憶系統也有風險 — 記憶可能過時（市場 regime 變化）或過度約束（阻止本該探索的方向）。我們的「無記憶」設計雖然低效，但不會被過時經驗誤導。

---

## 4. 因子生成效率

### FinLab：運算子庫 + GPU 加速

60+ 預定義運算子（TsRank、CsRank、Slope、IfElse 等），GPU 加速後端到端評估 202ms/因子。

**優勢：**
- 因子定義為運算子組合，天然結構化，可做 tree search
- GPU 加速使暴力搜索可行（1000 因子 / 6 分鐘）
- 運算子庫限制了搜索空間，減少無效探索

**劣勢：**
- 因子被限制在運算子庫的表達能力內
- 無法表達「需要 40 天營收延遲後的加速度」這類複雜邏輯
- 高頻（10 分鐘 K 線）的因子不直接適用於日頻台股

### 我們：自由 pandas 代碼

Agent 可以寫任何 pandas 代碼作為因子，80 行以內。

**優勢：**
- 表達能力無限（可以寫任何邏輯）
- 可以利用台股特有數據（營收月報、法人買賣超）
- 不受預定義運算子的限制

**劣勢：**
- 每次評估需要跑完整 python 腳本（~30-120 秒 vs 202ms）
- Agent 可能生成無意義的代碼（pandas 錯誤、空 DataFrame）
- 沒有結構化搜索，完全依賴 LLM 的「直覺」

### 效率對比

| 指標 | FinLab | 我們 | 比率 |
|------|--------|------|------|
| 單因子評估時間 | ~0.2 秒 | ~30-120 秒 | 150-600x |
| 每小時候選量 | ~10,000 | ~17 | ~600x |
| 有效因子產出率 | ~8%（100→8） | ~26% L4（但 OOS 未知） | — |
| 每小時有效因子 | ~800 | ~4 | ~200x |

**但**：FinLab 的 10,000/hr 是運算子組合搜索，多數是機械生成。我們的 17/hr 每個都是 LLM 深思後的假說。質量可能不同。

---

## 5. 台股因子結果比較

### FinLab 台股結果（單因子，月度再平衡，Top 15，2015-2025）

| 因子 | CAGR | MDD |
|------|:----:|:---:|
| 營收創新高 | 14.7% | -41.7% |
| 價格動量 60d | 11.6% | -75.2% |
| 營收動量 MA3 | 9.6% | -61.7% |
| 投信買超 10d | 8.4% | -39.3% |
| 品質 ROE | 7.1% | -46.2% |
| 價值 1/PE | 1.9% | -47.1% |
| 低波動 | -0.7% | -12.4% |

### 我們的台股結果

| 因子 | CAGR | Sharpe | 備註 |
|------|:----:|:------:|------|
| revenue_momentum | 23.8% | 1.42 | IS 2020-2024 |
| revenue_momentum OOS | -7.4% | -0.73 | OOS 2025 H1 |
| 最佳 autoresearch 因子 | — | ICIR 0.51 | Dual Sharpe 12+8 skip15 |

### 比較分析

**1. FinLab 的營收創新高 14.7% vs 我們的 revenue_momentum 23.8%：**

不可直接比較：
- 時間段不同（FinLab 2015-2025 vs 我們 2020-2024）
- 2020-2024 包含強牛市，膨脹了報酬
- 持倉數不同（FinLab Top 15 vs 我們 Top 20 + 等權）
- **我們的 OOS -7.4% 說明 IS 的 23.8% 很可能是過擬合**

**2. FinLab 的發現和我們高度一致：**
- 營收因子 > 動量因子 > 品質因子 > 價值因子 ← 兩邊都得出這個結論
- 低波動因子在台股無效 ← 兩邊都確認
- 價值因子（PE）接近零 alpha ← 兩邊都確認
- 投信買超是落後指標 ← FinLab 明確指出（CAGR 從 18.6% → 6.6%）

**3. FinLab 的組合策略迭代（7 輪）：**

```
基線 10.8% → +動量確認 18.6%（最大提升）→ +品質過濾 18.0% → 集中持倉 17.6%/-33.2% MDD
```

關鍵發現：**動量確認（60 天正報酬）是最大的單一改善**（+100% CAGR）。這和我們 revenue_momentum 策略中的「近 60 日漲幅 > 0」條件完全吻合（`strategies/revenue_momentum.py:232`）。

**4. FinLab 發現集中持倉（8 檔）優於分散：**

我們的 `max_holdings=20`。FinLab 的經驗顯示 8 檔集中持倉 MDD 從 -55.4% 降到 -33.2%。**這值得我們測試。**

---

## 6. 我們應該學的

### 6.1 結構化記憶系統（優先級：HIGH）

**FinLab 的效果：** 3x 效率提升。有記憶的系統在 160 輪後產出 96 個高品質因子，無記憶只產出 32 個。

**我們缺的：**
- 成功模式記錄（「revenue acceleration + momentum confirmation 有效」）
- 失敗模式記錄（「VWAP 偏差和 momentum 高度相關，不值得探索」）
- 跨 session 經驗傳遞

**最小可行改進（不需要 Agno 框架）：**

```
work/
├── factor.py
├── results.tsv
└── learnings.jsonl      ← 新增：append-only 經驗記錄
```

每次實驗後，evaluate.py 或 agent 追加一條：
```json
{"direction": "revenue_acceleration", "result": "L4_PASS", "icir": 0.51, "insight": "3m/12m ratio with momentum filter", "correlates_with": ["revenue_yoy"]}
{"direction": "vwap_deviation", "result": "L3_FAIL", "reason": "corr 0.67 with momentum_12m", "insight": "VWAP variants are momentum in disguise"}
```

program.md 指示 agent 在生成新因子前先讀 learnings.jsonl。

**成本：改動極小（~20 行）。收益：避免重複探索，跨 session 保留經驗。**

### 6.2 因子替換機制（優先級：HIGH）

**問題：** 我們的 L3 correlation check 只做 reject，不做 replace。隨著因子庫增長，新因子被 reject 的機率越來越高，但其中可能有比現有因子更好的。

**FinLab 的做法：** 如果新因子 IC ≥ 0.10 且 ≥ 1.3× 被替換因子的 IC，允許替換。

**建議：** 在 evaluate.py 的 L3 check 中加入替換邏輯：

```python
if max_corr > CORRELATION_THRESHOLD:
    # 找到最相關的已知因子
    most_correlated = ...
    # 如果新因子顯著更好，允許替換
    if new_icir >= 1.3 * correlated_icir and new_icir >= 0.20:
        # 替換，不 reject
        replace_factor(most_correlated, new_factor)
    else:
        # 正常 reject
        return L3_FAIL
```

### 6.3 L1 門檻校準（優先級：MEDIUM）

**問題：** 我們的 L1 門檻 IC ≥ 0.02 是拍腦袋定的。FinLab 用 0.04（A 股高頻），他們有消融研究支持這個數字。

**建議：** 用 permutation test 校準。隨機打亂因子值 1000 次，計算 IC 分佈，把門檻設在 95th percentile。這樣門檻就有統計基礎。

### 6.4 預定義運算子庫（優先級：LOW）

FinLab 的 60+ 運算子庫讓因子生成有結構。但我們的自由 pandas 模式有自己的優勢（可以寫營收延遲、法人跟單等複雜邏輯）。

**不建議全面模仿。** 但可以在 program.md 中提供常用的台股因子模板（5-10 個），讓 agent 有起點：

```python
# 模板：營收加速度
accel = rev_3m / rev_12m

# 模板：法人淨買超動量
trust_momentum = trust_net.rolling(20).sum()

# 模板：波動率調整動量
vol_adj_mom = returns_60d / volatility_60d
```

---

## 7. FinLab 應該學我們的

### 7.1 Thresholdout OOS 保護

FinLab 的評估管線沒有 holdout 保護。如果他們跑 1000+ 因子（論文中 160 輪），OOS holdout 會被 adaptive query 降解。我們的 Laplace noise + budget tracking 是正確的做法。

### 7.2 安全隔離架構

FinLab 的文章沒有提到 agent 安全性。Agent 是否能修改評估標準？是否能讀取 OOS 數據？我們的 Docker 隔離 + evaluate.py READ-ONLY + information filtering 是經過多次事故後的成熟設計。

### 7.3 大規模驗證（Stage 2）

我們的 Stage 2 要求 L5 通過後在 865+ 支股票上重新驗證。FinLab 沒有提到等價機制。這防止了小 universe 偏差（我們的經驗：50 支 ICIR 0.60，874 支反轉為 -0.232）。

### 7.4 Watchdog 監控

我們的 watchdog 每 60 秒監控 agent 行為（crash detection、saturation、evaluate.py integrity check）。FinLab 沒有提到等價機制。

---

## 8. 綜合建議：改進路線圖

| 優先級 | 改進項 | 來源 | 預估工作量 | 預期效果 |
|:------:|--------|------|:----------:|---------|
| **P0** | 結構化經驗記憶（learnings.jsonl） | FinLab Ralph Loop | 小（~20 行） | 避免重複探索，3x 效率 |
| **P0** | 因子替換機制 | FinLab Stage 2.5 | 小（~30 行） | 解決因子庫飽和問題 |
| **P1** | L1 門檻 permutation 校準 | FinLab 消融研究啟發 | 中 | 統計基礎的門檻 |
| **P1** | 失敗方向動態記錄 | FinLab Forbidden Directions | 小 | 減少無效探索 |
| **P2** | 台股因子模板庫 | FinLab 運算子庫啟發 | 小 | agent 起點更好 |
| **P2** | 集中持倉測試（8-10 檔） | FinLab 迭代結果 | 小 | 可能改善 MDD |
| ~~P3~~ | ~~GPU 運算子加速~~ | ~~FinLab 60+ operators~~ | ~~大~~ | ~~不適用：我們是日頻 + 自由 pandas~~ |

### 不應該學的

1. **GPU 運算子庫** — 我們是日頻策略，17 實驗/hr 的瓶頸在 LLM 回應時間，不在因子計算。GPU 加速對我們的場景 ROI 極低
2. **Agno 框架** — 引入一個完整的 agent 框架增加複雜度。learnings.jsonl 用 20 行代碼就能實現記憶的核心價值
3. **10 分鐘 K 線** — FinLab/FactorMiner 的核心是高頻因子挖掘。台股日頻策略不需要 10 分鐘 K 線

---

## 9. 結論

**FinLab 做得比我們好的：** 記憶系統（3x 效率）、替換機制（防飽和）、因子結果和我們高度一致（營收 > 動量 > 價值，驗證了我們的方向）。

**我們做得比 FinLab 好的：** OOS 保護（Thresholdout）、安全隔離（Docker + READ-ONLY）、大規模驗證（865+ 支）、watchdog 監控。

**最大啟示：** FinLab 用 Agno 框架的 3 層記憶實現了 3x 效率提升，而我們可以用 20 行的 learnings.jsonl 實現 80% 的效果。**不需要引入重量級框架，只需要讓 agent 記住為什麼失敗、什麼方向有效。**

**台股因子的共識（兩個獨立系統的交叉驗證）：**
1. 營收因子是台股最強信號（兩邊都確認）
2. 低波動和價值因子在台股無效（兩邊都確認）
3. 動量確認（60 日正報酬）是最大改善槓桿（兩邊都確認）
4. 投信買超是落後指標，加入反而降低績效（FinLab 明確指出）
5. 注意 FinLab 模式的過擬合風險

---

## 參考

- FinLab: [AI Factor Mining Agent](https://www.finlab.finance/blog/ai-factor-mining-agent)
- Wang et al. (2026): [FactorMiner: Automated Factor Mining with LLM Agents](https://arxiv.org/abs/2602.14670)
- Dwork et al. (2015): The reusable holdout: Preserving validity in adaptive data analysis. Science.
- Karpathy: [autoresearch](https://github.com/karpathy/autoresearch)
- Agno Framework: [Agent with Memory](https://docs.agno.com/basics/agents/usage/agent-with-memory)
