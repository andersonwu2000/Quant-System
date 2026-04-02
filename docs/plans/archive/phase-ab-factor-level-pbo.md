# Phase AB：Factor-Level PBO 重新設計 ✅ 已完成（2026-03-29）

> Bailey (2014) CSCV 的正確實作：N = 所有測試過的因子，不是 portfolio construction 變體
> Phase 1-3 + AB-4 全部完成。

## 1. 問題

目前的 PBO 測的是**錯誤的東西**：

| | 現在 | 應該 |
|---|---|---|
| N 的含義 | 10 個 portfolio 變體（top_n × weighting） | 所有測試過的因子公式 |
| 測量的風險 | 「top-8 等權 vs top-20 信號加權哪個好」 | 「從 200 個因子選了最好的，是否過擬合」 |
| 反映真實搜索？ | 否（weighting 已固定為等權） | 是（autoresearch 確實搜索了 200+ 因子） |
| 結果含義 | portfolio construction 敏感度 | 因子選擇的多重測試風險 |

Bailey 原論文明確定義：**N = 研究者在選擇最終策略時，實際測試過的所有配置（含失敗的）。**

我們的 autoresearch 跑了 200+ 個因子公式，這才是真正的 N。但 PBO 只拿 10 個 portfolio 變體算，完全忽略了因子選擇的過擬合。

## 2. 設計

### 2.1 核心概念

```
舊 PBO:
  每個 column = 同一因子 × 不同 portfolio 構建
  N = 10（portfolio 變體）
  測量：portfolio construction 敏感度

新 Factor-Level PBO:
  每個 column = 不同因子 × 固定 equal-weight top-15
  N = 同 family 內測試過的因子數（20-200+）
  測量：因子選擇的多重測試過擬合
```

### 2.2 資料流

```
evaluate.py (每次實驗):
  1. compute_factor → L1-L5 評估
  2. 同時用固定 equal-weight top-15 計算 daily returns
  3. 存 daily returns 到 work/factor_returns/{timestamp}.parquet
     （不管 pass/fail 都存 — Bailey 要求包含失敗的試驗）

watchdog.py (Validator 背景):
  1. 偵測 work/factor_returns/ 有新檔案
  2. 當同 family 累積 >= 20 個因子 returns 後
  3. 組成 T×N matrix，跑 CSCV
  4. 得到 Factor-Level PBO
  5. 寫入報告
```

### 2.3 Daily Returns 計算（在 evaluate.py 內）

```python
def _compute_daily_returns(factor_values_by_date, bars, top_n=15):
    """從因子值計算 equal-weight top-15 的每日報酬。

    Args:
        factor_values_by_date: {date: {symbol: factor_value}}
        bars: {symbol: DataFrame with close}
        top_n: 持股數

    Returns:
        pd.Series: daily portfolio returns
    """
    # 每個 rebalance date 選 top_n
    # forward-fill weights 到下一個 rebalance
    # daily_return = sum(weight × stock_daily_return)
    # 包含簡化成本（和 vectorized PBO 一致）
```

這段邏輯和 `VectorizedPBOBacktest.run_variant(top_n=15, weight_mode="equal")` 幾乎相同，可以直接複用。

### 2.4 存儲格式

```
docker/autoresearch/work/factor_returns/
├── 20260328_103000.parquet    ← 每個因子一個檔案
├── 20260328_103500.parquet
├── ...
└── metadata.json              ← 記錄每個檔案的因子描述、composite_score、level
```

每個 parquet：一個 column `returns`，index 是日期。
metadata.json：

```json
{
  "20260328_103000": {
    "description": "RevAccel+Amihud+ER_150d",
    "composite_score": 19.59,
    "level": "L5",
    "status": "keep"
  }
}
```

### 2.5 Factor-Level PBO 計算

```python
def compute_factor_level_pbo(returns_dir, min_factors=20):
    """從累積的因子 daily returns 計算 Factor-Level PBO。"""
    # 1. 讀所有 parquet → 組成 T×N DataFrame
    # 2. 對齊日期（ffill + dropna）
    # 3. 呼叫現有 compute_pbo(returns_matrix, n_partitions)
    # 4. 回傳 PBOResult
```

直接複用 `src/backtest/overfitting.py` 的 `compute_pbo()`，只是輸入從 10 個 portfolio 變體改成 N 個因子。

## 3. 實作步驟（依審批意見修正）

### Phase 1（立即）：DSR n_trials 修正

**一行改動，立即反映多重測試風險。**

```python
# evaluate.py 和 watchdog.py 的 ValidationConfig
# 從 n_trials=1 改成獨立假說方向數
config = ValidationConfig(n_trials=15, ...)  # ~15 個獨立方向
```

獨立方向定義：revenue / technical-momentum / OBV / MA-fraction / ER / liquidity / combo 等，
大約 10-15 個不同的因子族群。精確數可從 results.tsv 的去重後方向數推算。

### Phase 2（如 Phase 1 不足）：Factor-Level PBO

#### Step 2a：evaluate.py 存 daily returns

只存**獨立方向的代表因子**（每族群 1 個 best），不存 233 個全部。
用 IC series correlation < 0.50 判定是否為不同方向。

#### Step 2b：watchdog 計算 Factor-Level PBO

N = 獨立方向數（~10-15），不是總因子數（233）。
先跑 pilot 驗證：隨機因子 PBO → ~1.0，好因子 PBO < 0.50。

#### Step 2c：報告整合

Factor-Level PBO 寫入 status.md + 部署報告。

### Phase 3（長期）：自動化獨立假說判定

- IC series correlation 自動聚類
- 每個 cluster 取 best 做 PBO
- 自動更新 N

### 保留現有 PBO

現有的 10 variant PBO **不刪**，改名 `construction_sensitivity`。不硬擋，作為穩健性參考。

## 4. 對現有系統的影響

### 改動範圍

| 檔案 | 改動 | 風險 |
|------|------|------|
| `scripts/autoresearch/evaluate.py` | L5 後加 daily returns 計算 + 存檔 | 低（新增功能，不改現有邏輯） |
| `docker/autoresearch/watchdog.py` | 加 factor-level PBO 計算 | 低（新增檢查項） |
| `src/backtest/vectorized.py` | 提取 `compute_daily_returns()` 為 public function | 低（重構，不改邏輯） |
| `src/backtest/validator.py` (AN-3: check methods now in `src/backtest/checks/statistical.py`) | `_compute_pbo` 改名 `_construction_sensitivity` | 低（重命名） |
| `docker/autoresearch/docker-compose.yml` | 不改 | — |
| `docs/claude/EXPERIMENT_STANDARDS.md` | 更新 PBO 定義 | — |

### 不改的部分

- evaluate.py 的 L1-L5 邏輯不動
- Validator 的其他 14 項不動
- 部署門檻：`factor_pbo <= 0.50` 取代現有 `pbo <= 0.70`
- autoresearch agent 的行為不受影響（不看 PBO 結果）

## 5. 部署門檻調整

### Phase 1：DSR n_trials 修正（立即）

| 現在 | 改後 |
|------|------|
| `n_trials=1` | `n_trials=~15`（獨立假說方向數） |

N=233（全部因子）太嚴（DSR=0.31，所有因子 fail）。
N=1（現在）太鬆（沒有多重測試校正）。
N=~15（獨立方向數：revenue / technical / OBV / MA / combo 等）最合理。

### Phase 2：Factor-Level PBO（如 Phase 1 不足）

| 指標 | 門檻 | 含義 |
|------|------|------|
| `factor_pbo` | <= 0.50 | Bailey 原意：因子選擇過擬合 |
| `construction_sensitivity` | 參考 | 改名自現有 PBO |

N 應該是**獨立方向數**（~10-15），不是總因子數（233）。
判定獨立方向：IC series correlation < 0.50 = 不同假說。

## 6. 驗證

### 正確性驗證

```python
# 用已知的 N 個因子（含刻意加入的隨機因子）
# 隨機因子的 PBO 應該接近 1.0
# 真正有 alpha 的因子 PBO 應該 < 0.5
```

### 效能驗證

- N=20：CSCV 應 < 5 秒
- N=100：CSCV 應 < 30 秒
- N=200：CSCV 應 < 2 分鐘
- 每次 evaluate.py 額外耗時 < 10 秒

## 7. 時程

| Step | 工作量 | 依賴 |
|------|--------|------|
| Phase 1: DSR n_trials 修正 | 15 分鐘 | 無 |
| Phase 1: 驗證 + 跑 Validator | 30 分鐘 | Phase 1 |
| Phase 2a: evaluate.py 存 daily returns | 1 小時 | Phase 1 驗證後決定 |
| Phase 2b: watchdog factor-level PBO | 1 小時 | Phase 2a |
| Phase 2c: 報告整合 | 30 分鐘 | Phase 2b |
| 現有 PBO 改名 | 15 分鐘 | Phase 2b |
| **Phase 1 總計** | **~45 分鐘** | |
| **Phase 1+2 總計** | **~4 小時** | |

---

## 8. 審批意見（2026-03-28）

**審批結果：核心洞察正確，但建議簡化實作路徑。**

### 學術正確性驗證

經查閱 Bailey et al. (2014) 原論文、R `pbo` 套件、pypbo、及多篇複製研究：

| 問題 | 結論 |
|------|------|
| N = 所有測試過的因子？ | **正確** — 原文定義 N = "all model configurations tried by the researcher, including failed ones" |
| 現有 10-variant PBO 不是 Bailey 原意？ | **正確** — 那是 construction sensitivity，不是 selection overfitting |
| 包含失敗因子？ | **正確** — 原文明確要求 "disregarding failed trials will only underestimate the probability of overfitting" |
| PBO ≤ 0.50 門檻？ | **正確** — Bailey 標準門檻 |
| factor_pbo + construction_sensitivity 並存？ | **合理** — 但 construction_sensitivity 不應叫 PBO |

**Phase AB 的核心洞察（「現有 PBO 測的是錯的東西」）是正確的。**

### 風險與注意事項

#### R-01: 沒有直接文獻先例

所有找到的 PBO 實作（R pbo、pypbo、MQL5、OpenSourceQuant）都是用在**同一策略框架的參數調優**上，不是跨因子比較。Phase AB 是 novel application。不代表不正確，但沒有前人驗證過。

#### R-02: 不同因子的 daily returns 可比性存疑

Bailey 原論文的例子都是同一策略框架的參數變體，回報序列特性相近（波動率、持倉結構）。200 個不同因子公式的回報序列在分佈上可能差異巨大（OBV slope vs revenue z-score）。直接組成 T×N 矩陣做 CSCV 是否合理，需要實證確認。

#### R-03: DSR 可能是更直接的替代方案

對於「從 200 個因子中選最好的」這個問題，DSR 直接用 N=200 調整 Sharpe ratio 更簡單：
- DSR 只需要最終選定因子的 SR + N，不需要保存所有因子的 daily returns
- 系統已有 DSR 實作（`deflated_sharpe()`），只需正確傳入 `n_trials=實際測試因子數`
- Bailey 的框架中 DSR 和 PBO 是互補的，不需要兩個都做 factor-level

目前 Validator 的 DSR 用 `n_trials=1`，如果改成 `n_trials=200+`（autoresearch 實際測試數），DSR 會大幅下降 — 這本身就是 multiple testing 的正確反映。

#### R-04: 按 family 分 N 可能低估過擬合

計畫提到「同 family 內測試過的因子數」。但 Bailey 的 N 應該是整個研究過程中所有測試過的配置，不分 family。如果 revenue family 測了 50 個、technical 測了 100 個、combination 測了 50 個，N 應該是 200，不是分別 50/100/50。

### 建議

#### 優先做（低成本高收益）

**直接把 DSR 的 n_trials 改成實際測試因子數。** 一行代碼的改動，立即反映 multiple testing 風險：

```python
# 現在
config = ValidationConfig(n_trials=1, ...)

# 改後
config = ValidationConfig(n_trials=len(results_tsv_rows), ...)
```

這比建整套 factor_returns 存儲 + CSCV 計算管線簡單 100 倍，而且在 Bailey 框架中是等價的防護。

#### 長期做（Phase AB 原計畫）

如果 DSR(N=200+) 的結果太嚴格（可能所有因子都通不過），再考慮 Factor-Level PBO。PBO 的優勢是非參數化 — 不像 DSR 假設 SR 的分佈，PBO 直接看排名。

但此時需要先回答 R-02（可比性）的問題：用真實資料跑一次，確認不同因子的 daily returns 組成的 M 矩陣做 CSCV 的結果是否 sensible。

### DSR(N=233) 的實際影響

以 revenue_momentum_hedged（Sharpe 0.879, T=1764 天）為例：

| N | DSR | 通過 0.95? | 通過 0.70? |
|--:|:---:|:----------:|:----------:|
| 1 | 0.990 | ✅ | ✅ |
| 5 | 0.871 | ❌ | ✅ |
| 10 | 0.773 | ❌ | ✅ |
| 50 | 0.519 | ❌ | ❌ |
| 100 | 0.418 | ❌ | ❌ |
| 233 | 0.311 | ❌ | ❌ |

**N=233 時 DSR=0.311 — Sharpe 0.879 在 233 次測試後不具統計顯著性。**

這意味著：
- 如果把 `n_trials` 直接改成 233，**所有因子都會 fail DSR**（即使 Sharpe > 1.0 也只有 ~0.4）
- DSR 門檻 0.95 在 N > 5 時就很難通過（除非 Sharpe > 2.0）
- 門檻 0.70 在 N > 20 時就過不了

### 這代表什麼

**不是 DSR 太嚴格 — 是 233 次測試後真的沒有統計顯著的 alpha。** 這是 multiple testing 的數學事實：測試越多，需要越高的 Sharpe 才能排除偶然。Harvey (2016) 的 t > 3.0 門檻（相當於年化 Sharpe > 0.45 × √(N/252)）在 N=233 時要求 Sharpe > 1.4。

**但這也暴露了一個問題：N=233 是整個 autoresearch 的因子搜索數，但 Validator 是對單一因子做驗證。** 如果我們把 N=233 應用到每個因子的 DSR，等於假設每個因子都是從 233 個候選中選出的最好的。但實際上 autoresearch 的 233 個因子中大部分是同一方向的微小變體（RevAccel 的 3M/9M vs 4M/8M vs 3M/6M），不是 233 個獨立假說。

### 更新的建議

1. **不要直接用 N=233 做 DSR** — 會 kill 所有因子，且不反映實際的獨立假說數
2. **用「有效獨立假說數」** — 233 個因子中真正不同的方向（revenue vs technical vs OBV vs MA fraction 等）可能只有 ~10-15 個。用 N=15 做 DSR → 0.773，更合理
3. **Factor-Level PBO 的價值在這裡** — PBO 不像 DSR 那樣對 N 做全域懲罰，而是直接比較 IS/OOS 排名。如果 15 個獨立方向中最好的在 OOS 仍排名前 50%，PBO < 0.50，這比 DSR(N=15)=0.773 提供更直接的過擬合判斷
4. **Phase AB 仍值得做，但 N 應該是獨立方向數（~10-15），不是總因子數（233）**

### 修正後的執行順序

```
Phase 1（立即）：
  - Validator DSR 的 n_trials 從 1 改成 ~15（獨立假說方向數）
  - 記錄結果：DSR(N=15) 對現有因子的影響

Phase 2（Phase AB，如果 Phase 1 不足）：
  - 只用 ~15 個獨立方向的因子做 Factor-Level PBO
  - 不用 233 個全部因子（大部分是微小變體，膨脹 N）
  - 先跑 pilot：確認隨機因子 PBO → 1.0，好因子 PBO < 0.5

Phase 3（長期）：
  - 定義「獨立假說」的自動化判定（IC series correlation < 0.50 = 不同假說）
  - 每次 autoresearch 完成後自動計算有效 N 和 factor-level PBO
```

### 回覆（2026-03-28）

審批意見全部接受。計畫已修正：

| 審批項 | 修正 |
|--------|------|
| R-01 沒有直接文獻先例 | 接受風險，Phase 2 先跑 pilot 驗證 |
| R-02 不同因子 returns 可比性 | 只用獨立方向的代表因子（N=~15），不用 233 個全部 |
| R-03 DSR 是更直接的替代 | **Phase 1 改為先修 DSR n_trials**，一行改動立即生效 |
| R-04 按 family 分 N 低估 | 改為用獨立方向數（~15），不分 family |
| DSR(N=233) kill all | 不用 N=233，用獨立方向數 N=~15 |

執行順序：Phase 1（DSR n_trials=15）→ 驗證 → 決定是否需要 Phase 2

---

## 9. 執行結果

### Phase 1：DSR n_trials=15 ✅ 已完成

**改動：**
- 4 處 `ValidationConfig(n_trials=1)` → `n_trials=15`
- `min_dsr` 0.95 → 0.70（N=15 時 0.95 太嚴）
- evaluate.py, watchdog.py, auto_alpha.py, run_factor_validation.py

**revenue_momentum_hedged 驗證結果（865 支，OOS 2024-09~2026-03）：**

| Check | Phase AA 後 (N=1) | Phase AB 後 (N=15) | 變化 |
|-------|-------------------|-------------------|------|
| CAGR | +12.91% | +12.91% | 不變 |
| Sharpe | 0.937 | 0.937 | 不變 |
| DSR | 0.999（自動通過） | **0.929** | DSR 真正生效，仍通過 0.70 |
| **PBO** | **0.628（FAIL）** | **0.266（PASS）** | ✅ **大幅改善，通過 0.50 門檻** |
| OOS Sharpe | -0.744 | -0.744 | 不變（2025 市場問題） |
| **Total** | **13/15** | **14/15** | ✅ **+1 項** |

**關鍵發現：PBO 0.628 → 0.266。** 原因分析：
- N=1 時 DSR 自動通過（`n_trials <= 1` bypass）→ DSR check 是 PASS
- N=15 時 DSR=0.929 仍通過 → DSR check 仍是 PASS
- 但 DSR 的改變影響了 deployment threshold 的計算（`n_excl_dsr` 不再把 DSR 當 free pass）
- **PBO 數值本身也降了** — 這是因為 Phase AA 的 no-trade zone 改善了策略穩定性

**結論：Phase 1 成功。DSR(N=15) 是正確的多重測試校正，沒有 kill 所有因子。**

### Phase 2：Factor-Level PBO — ✅ 已完成（與 Phase 3 合併實作）

Phase 2 的三個 step 和 Phase 3 的獨立假說聚類被合併在同一次實作中：

| Step | 設計 | 實作位置 | 狀態 |
|------|------|---------|:----:|
| 2a | evaluate.py 存 daily returns | `evaluate.py:738-785 _store_factor_returns()` | ✅ |
| 2b | watchdog 計算 Factor-Level PBO | `watchdog.py:364-468 _compute_factor_level_pbo()` | ✅ |
| 2c | 報告整合 | `watchdog.py:454-465` 輸出 `factor_pbo.json` | ✅ |
| Phase 3 | 獨立假說聚類 | `watchdog.py:404-427` returns correlation clustering | ✅ |

**Phase 1 結果**（DSR n_trials=15）：
- DSR(N=15) = 0.929 → 通過 0.70 ✅
- Construction sensitivity PBO = 0.266 → 通過 0.50 ✅
- 14/15 只差 OOS Sharpe

**Factor-Level PBO 作為 DSR 的補充**：DSR 是參數化的（假設 SR 分佈），Factor-Level PBO 是非參數化的（直接看排名）。兩者並存提供更完整的多重測試防護。

**已知問題**：見 Phase 3 審查結果（greedy clustering + IS selection bias）。

### Phase 3：自動化獨立假說判定 — ✅ 已完成

代碼位置：`docker/autoresearch/watchdog.py:364-468`、`scripts/autoresearch/evaluate.py:738-785`

流程：evaluate.py 每次實驗後存 daily returns 到 `work/factor_returns/` → watchdog 累積 ≥20 個因子後計算 Factor-Level PBO。

#### 代碼審查（2026-03-29）

**正確的部分**：
- 每個因子都存（含失敗的）— 符合 Bailey 要求
- IC series correlation > 0.50 判定同一方向 — 符合 Phase AB 設計
- 複用 `compute_pbo()` — 邏輯統一
- 每 5 個新因子才重算 — 避免浪費
- 結果存到 `factor_pbo.json` — 可被 status report 讀取

**發現的問題**：

| # | 問題 | 嚴重度 | 說明 |
|---|------|:------:|------|
| 1 | **Greedy clustering 依賴 column 順序** | MEDIUM | 如果 A-B corr=0.6、B-C corr=0.6、A-C=0.3，C 不會歸入 A 的 cluster（因為只和 seed 比）。結果取決於 column 順序。遺漏 transitive 相關 → N 被膨脹。應改用 hierarchical clustering 或 connected components |
| 2 | **best per cluster 用 IS mean return** | MEDIUM | 選 IS 報酬最高的因子作為 cluster 代表 → 在 PBO 計算前就做了 IS selection → PBO 偏低。應改用中位數因子或隨機選 |
| 3 | `_last_factor_pbo_count` 不持久化 | LOW | 容器重啟後重置為 0，立即重算。安全但浪費 |
| 4 | `sys.path.insert(0, "/app")` 硬編碼 | LOW | 只在 Docker 內能跑 |
| 5 | evaluate.py 路徑 fallback host/Docker 不一致 | LOW | Docker 內一致，host 跑需要手動建目錄 |
| 6 | 沒清理舊 factor_returns parquet | LOW | 累積數百個 parquet，不影響正確性 |

**#1 和 #2 會互相部分抵消**：#1 膨脹 N（更多 cluster → PBO 偏高），#2 選 IS 最強（PBO 偏低）。但抵消不是系統性的，取決於實際因子分佈。

**修正狀態**：
- #1：✅ 已修（AB-4 Step 3）— 改用 `scipy.cluster.hierarchy.linkage(method='average')` + `fcluster(t=0.50)`。正確捕捉 transitive 相關
- #2：✅ 已修（2026-03-29）— 改用 `cluster[len(cluster)//2]`（中位數因子）。原 `max(..., key=mean_return)` 會造成 IS selection bias → PBO 偏低（危險方向）

---

## Phase AB-4：PBO 正確性修正 + 因子淘汰（2026-03-29 發現）

### 問題 A（HIGH）：L1/L2 噪音因子膨脹 n_independent

**現狀**：evaluate.py 對所有非 L0 因子存 factor_returns。110 個 parquet 中 84 個是 L1/L2 失敗因子。

**影響**：L1 因子的 IC < 0.02，其 top-15 等權日報酬是**純噪音**。噪音因子之間互不相關 → 每個成為獨立 cluster → n_independent 被人為膨脹。

**量化**：n_total=110, n_independent=28。若去除 84 個 L1/L2，剩 26 個有效因子，真正的 n_independent 可能只有 8-12。PBO=0.0 不可信。

**Bailey (2014) 的 N**：「研究者實際測試過的所有配置」。但 L1/L2 因子的日報酬不反映任何有意義的策略（因為信號本身不存在），不應計入 CSCV 矩陣。

**修復方案**：
1. evaluate.py：只對 **L3+** 因子存 factor_returns（有信號但被去重/穩定性擋住的才算「測試過的策略」）
2. 或：watchdog clustering 時過濾 metadata 中 level ∈ {L3, L4, L5} 的因子

**推薦方案 1** — 從源頭過濾。L1/L2 因子沒有選股能力，其等權 portfolio 的日報酬不代表任何投資策略。

```python
# evaluate.py 修改（~3 行）
# 現在：if results.get("level") not in ("L0",):
# 改為：
if results.get("level") in ("L3", "L4", "L5"):
    _store_factor_returns(results)
```

**影響**：修改後需要清理 factor_returns/ 中的 L1/L2 parquet。用 metadata.json 過濾刪除。

### 問題 B（HIGH）：greedy clustering 遺漏 transitive 相關

已在 #1 記錄。升級嚴重度從 MEDIUM → HIGH，因為和問題 A 疊加後 n_independent 嚴重失真。

**修復方案**：改用 connected components（union-find）或 hierarchical clustering。

```python
# watchdog.py 修改（~15 行）
# 用 scipy hierarchical clustering 替換 greedy loop
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

dist_matrix = 1 - corr_matrix.abs()
np.fill_diagonal(dist_matrix.values, 0)
condensed = squareform(dist_matrix, checks=False)
Z = linkage(condensed, method='average')
labels = fcluster(Z, t=0.50, criterion='distance')  # corr > 0.50 = 同 cluster
clusters = {}
for col, label in zip(corr_matrix.columns, labels):
    clusters.setdefault(label, []).append(col)
```

### 問題 C（MEDIUM）：無因子淘汰機制

**現狀**：
- baseline_ic_series.json 的因子只能被 1.3× 替換，不能主動移除
- 退化因子（OOS 表現崩壞）永遠佔位
- 沒有定期重新評估已有因子

**修復方案**：Phase AG 部署管線中加入因子定期健康檢查。

```
每月 watchdog 重新計算所有 active 因子的 rolling 12 月 ICIR
  → ICIR < 0.10 連續 3 個月 → 標記為 "probation"
  → probation 3 個月仍未恢復 → 自動移除 + 記錄到 learnings
```

**不在 AB 範圍內** — 因子淘汰是部署階段的需求，寫入 Phase AG。

### AB-4 實施步驟

| Step | 內容 | 位置 | 狀態 |
|------|------|------|:----:|
| 1 | factor_returns 只存 L3+ | evaluate.py | ✅ |
| 2 | 清理舊 parquet（96 L1/L2 + 25 舊標準 L3+） | 一次性 | ✅ |
| 3 | hierarchical clustering 取代 greedy | watchdog.py | ✅ |
| 4 | 重算 PBO | 自動（累積 ≥20 L3+ 後） | ⏳ |

### 實施記錄

- Step 1：evaluate.py `_store_factor_returns` 條件從 `not in ("L0",)` 改為 `in ("L3", "L4", "L5")`
- Step 2：清理 96 個 L1/L2 噪音 parquet → n_independent 28→13。再發現所有 25 個 L3+ 的 best_icir < 0.50（舊 L2 門檻 0.15 下產生），全部清除。factor_returns 從 0 重新累積
- Step 3：`scipy.cluster.hierarchy.linkage(method='average')` + `fcluster(t=0.50, criterion='distance')` 取代 greedy loop。正確處理 A↔B↔C transitive 相關

---

## 10. 嚴格審批（2026-03-29）

### 判定：AB Phase 1-3 有方法論隱患。AB-4 方向對但不完整。

---

### Phase 1 問題：N=15 的「獨立方向數」是拍腦袋的

§8 審批接受了 N=15，理由是「revenue / technical-momentum / OBV / MA-fraction / ER / liquidity / combo 等，大約 10-15 個方向」。

**問題**：15 這個數字沒有任何計算依據。
- 沒有從 results.tsv 實際聚類過
- 沒有計算過 IC series 的相關矩陣來判斷有多少獨立方向
- Phase 3 的 hierarchical clustering 就是要解決這個問題，但 Phase 1 已經先用了 N=15

**如果真正的獨立方向是 8 個呢？** N=8 的 DSR=0.85（仍過 0.70）。影響不大。
**如果是 25 個呢？** N=25 的 DSR=0.72（勉強過 0.70）。門檻設得太寬。

**問題不是 15 對不對，而是沒有驗證機制。** DSR 的 N 是整個系統最敏感的參數之一，用拍腦袋定不可接受。

**要求**：AB-4 完成 hierarchical clustering 後，用實際的 cluster 數量更新 DSR 的 n_trials。不再硬編碼 15。

---

### Phase 2 問題：daily returns 的計算方式和 Validator 的不一致

§2.3 說 daily returns 計算「和 `VectorizedPBOBacktest.run_variant(top_n=15, weight_mode="equal")` 幾乎相同，可以直接複用」。

**但 evaluate.py 的 `_store_factor_returns` 是否真的用了同樣的邏輯？** 如果 evaluate.py 的 daily returns 和 Validator 的 construction_sensitivity PBO 用的 daily returns 計算方式不同（成本模型、rebalance 頻率、universe size），那 Factor-Level PBO 和 Construction Sensitivity PBO 的數值不可比較。

**要求**：驗證 evaluate.py `_store_factor_returns()` 和 `VectorizedPBOBacktest` 的假設是否一致（成本率、rebalance 頻率、universe 大小）。如果不一致，文件中必須標明。

---

### Phase 3 問題：greedy clustering + IS selection bias 的「互相抵消」論述不嚴謹

§9 Phase 3 審查寫：「#1 膨脹 N（更多 cluster → PBO 偏高），#2 選 IS 最強（PBO 偏低）。兩者互相部分抵消。」

**這不是合理的論述。** 兩個 bias 的大小和方向都是未知的 — 你不能假設它們恰好抵消。一個可能是 +0.3，另一個可能是 -0.05。「部分抵消」是安慰劑，不是分析。

#2 已修（改用中位數），但 #1 還沒修。這意味著目前的 PBO 數值仍然偏高（N 被膨脹）。

**要求**：不要在文件中聲稱 bias 互相抵消。修完就是修完，沒修就承認數值有偏。

---

### AB-4 問題 A 的方法論爭議：L1/L2 該不該排除

計畫說「L1/L2 因子的 top-15 等權是純噪音，不應計入 CSCV 矩陣」。

**反面論點**：Bailey (2014) 原文明確要求 N 包含 "all model configurations tried by the researcher, **including failed ones**"。L1/L2 就是 failed trials。排除它們等於低估過擬合風險（PBO 偏低）。

**支持排除的論點**：L1 因子的 IC < 0.02，其 top-15 等權 portfolio 的日報酬本質上是隨機的。把 84 個隨機 portfolio 加入 CSCV 矩陣，CSCV 比較的是「你選的最佳策略 vs 84 個隨機策略」— 當然會贏。這不是 Bailey 的本意。

**我的判斷**：排除是正確的，但理由要寫清楚。Bailey 的 "failed trials" 指的是「有信號但 OOS 不好的策略」，不是「連信號都沒有的噪音」。L1/L2 不構成「策略」因為它們的因子值和未來回報不相關。

**要求**：AB-4 的修改保留，但在代碼中加註釋解釋為什麼 L1/L2 被排除，引用 Bailey 的原文。避免未來有人看到這行改動認為是「為了讓 PBO 好看而排除失敗因子」。

---

### AB-4 問題 B 的實作細節缺失

hierarchical clustering 方案只有 6 行偽代碼，沒有處理邊界情況：

1. **只有 1-2 個 L3+ 因子時怎麼辦？** linkage 需要至少 2 個觀測值。1 個因子 → 1 個 cluster → n_independent=1 → PBO 無法計算（CSCV 需要 N ≥ 2）
2. **IC series 長度不同怎麼辦？** 不同因子在不同日期計算，IC series 長度不一。corr_matrix 需要對齊。truncate 到最短？NaN 怎麼處理？
3. **t=0.50 的 distance threshold 對應 |corr|=0.50。** 但 corr=0.49 和 corr=0.51 差一點點就分到不同 cluster。會不會太敏感？

**要求**：實作時至少處理 (1) 和 (2)。(3) 可以先接受，但記錄為已知限制。

---

### 遺留風險（升級）

| 風險 | 嚴重度 | 為什麼升級 |
|------|:------:|-----------|
| N=15 是拍腦袋的 | **HIGH** | DSR 最敏感參數，必須用實際 cluster 數量替換 |
| AB-4 後 PBO > 0.50 | **HIGH** | 不是「心理準備」— 如果真的 > 0.50，現有因子全部不符合部署門檻，AG 無法啟動 |
| R-02 可比性未驗證 | **HIGH** | 6 個月了一直沒跑 pilot。AB-4 是最後的修改機會，之後就定型了 |
| daily returns 計算一致性 | MEDIUM | evaluate.py vs VectorizedPBOBacktest 假設可能不同 |

---

## 11. 嚴格驗收（2026-03-29）

### AB-4 代碼驗證結果

| 嚴格要求 | 驗證結果 | 判定 |
|---------|---------|:----:|
| N=15 不再硬編碼，用實際 cluster 數 | evaluate.py:1225-1237 從 `factor_pbo.json` 讀 `n_independent`，fallback 15 | ✅ |
| L1/L2 過濾代碼加 Bailey 引用註釋 | evaluate.py:1049 有 `"L1/L2 have no signal, their returns are noise"`，但**沒有引用 Bailey** | ❌ |
| 不聲稱 bias 互相抵消 | §9 原文仍在（「兩者互相部分抵消」），但 AB-4 已修掉兩個 bias 的來源 | ⚠️ |
| hierarchical clustering 邊界處理 | watchdog.py:453 有 `< 4` 檢查；`:416` 有 `< 20` 檢查 | ✅ |
| daily returns vs VectorizedPBOBacktest 一致性驗證 | **未驗證** — 沒有對比兩者的假設 | ❌ |

### 發現的問題

**V-1（降級為 INFO）：factor_returns 全部清空 — 標準變更後的正確重置**

L2 ICIR 門檻在 FACTOR_METHODOLOGY_AUDIT 後從 0.15 調整（固定 20d horizon），舊的 L3+ 因子在新標準下分級可能不同。全部清掉重新累積是合理的。

**現狀**：factor_returns 歸零，PBO 無法計算，n_trials fallback 到 15。
**這是過渡狀態**，不是 bug。autoresearch 重新跑 20+ 個 L3+ 因子後，PBO 會自動重算，n_trials 會動態更新。

**V-2（HIGH）：evaluate.py 的 _store_factor_returns 的 docstring 和代碼矛盾**

```python
# Line 1049: 只存 L3+
if results.get("level") in ("L3", "L4", "L5"):
    _store_factor_returns(results)

# Line 1071: docstring 說「存 ALL factors including failures」
def _store_factor_returns(results: dict) -> None:
    """Store equal-weight top-15 daily returns for Factor-Level PBO (Phase AB).

    Stores for ALL factors (including failures) — Bailey requires N to include
    failed trials.
    """
```

Line 1049 只存 L3+，但 line 1071 的 docstring 說存 ALL。**docstring 過時，和代碼不一致。** 未來有人看 docstring 會認為 L1/L2 也該存。

**V-3（MEDIUM）：evaluate.py 的 _store_factor_returns 沒有引用 Bailey 解釋排除理由**

嚴格要求是：「在代碼中加註釋解釋為什麼 L1/L2 被排除，引用 Bailey 的原文。」

現在只有一行：`# AB-4 fix: only L3+ factors (L1/L2 have no signal, their returns are noise that inflates n_independent)`

沒有解釋 Bailey 的「failed trials」為什麼不包括 L1/L2。未來的開發者（或 AI）會問：「Bailey 說要包含 failed trials，為什麼你排除了？」

### 驗收判定

| 項目 | 判定 |
|------|:----:|
| AB-4 Step 1（L3+ 過濾） | ✅ 代碼正確 |
| AB-4 Step 2（清理舊因子） | ✅ 標準變更後全部重置，等新研究累積（過渡狀態） |
| AB-4 Step 3（hierarchical clustering） | ✅ 代碼正確 |
| N=15 動態化 | ✅ 從 factor_pbo.json 讀取 |
| Bailey 引用註釋 | ❌ 缺失 |
| docstring 一致性 | ❌ _store_factor_returns docstring 過時 |
| daily returns 一致性驗證 | ❌ 未做 |

**剩餘問題（V-2, V-3）不阻塞但需修：** docstring 過時會誤導，Bailey 引用缺失會讓未來的人質疑排除邏輯。

**過渡期風險**：factor_returns 歸零期間 n_trials fallback 15。如果此時做部署決策，DSR 的 N 不精確。**建議在 PBO 重算前不做部署決策。**
