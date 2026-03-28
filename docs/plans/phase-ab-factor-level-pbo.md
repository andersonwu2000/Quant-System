# Phase AB：Factor-Level PBO 重新設計

> Bailey (2014) CSCV 的正確實作：N = 所有測試過的因子，不是 portfolio construction 變體

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

## 3. 實作步驟

### Step 1：evaluate.py 存 daily returns（改動小）

在 L5 評估完成後（不管 pass/fail），用已有的 `_mask_data` + `_compute_forward_returns` 計算因子的 daily returns 並存檔。

**關鍵：所有因子都存，包含 L1/L2 就失敗的。** Bailey 要求 N 包含失敗的試驗。但 L0（複雜度失敗）不存（沒有因子值可算）。

實際上 L1 失敗的因子 IC < 0.02，其 daily returns 接近 0。存下來對 PBO 有意義（它們是 null hypothesis 的樣本）。

**效能考量：** 計算 daily returns 需要跑一次向量化回測（~5-10 秒），加在每次 evaluate.py 後面。目前每個實驗 ~2 分鐘，多 5-10 秒可接受。

### Step 2：watchdog 偵測 + 計算 PBO（改動中）

watchdog 每 60 秒檢查 `work/factor_returns/`。當累積 >= 20 個因子後開始算 Factor-Level PBO。

**累積計算 vs 全量計算：**
- 前 20 個：全量計算
- 之後每新增 5 個：重新計算（含所有歷史因子）
- 避免每次都重算（N=200 時 CSCV 可能慢）

### Step 3：報告整合

Factor-Level PBO 寫入：
- `docs/research/status.md`（自動更新）
- 每個部署報告（watchdog 的 `_write_background_report`）

### Step 4：保留現有 PBO 作為 construction_sensitivity

現有的 10 variant PBO **不刪**，改名為 `construction_sensitivity`。兩個指標並存：

| 指標 | 含義 | 門檻 |
|------|------|------|
| `factor_pbo` | 因子選擇的過擬合（Bailey 原意） | <= 0.50 |
| `construction_sensitivity` | portfolio 構建的參數敏感度 | 參考，不硬擋 |

## 4. 對現有系統的影響

### 改動範圍

| 檔案 | 改動 | 風險 |
|------|------|------|
| `scripts/autoresearch/evaluate.py` | L5 後加 daily returns 計算 + 存檔 | 低（新增功能，不改現有邏輯） |
| `docker/autoresearch/watchdog.py` | 加 factor-level PBO 計算 | 低（新增檢查項） |
| `src/backtest/vectorized.py` | 提取 `compute_daily_returns()` 為 public function | 低（重構，不改邏輯） |
| `src/backtest/validator.py` | `_compute_pbo` 改名 `_construction_sensitivity` | 低（重命名） |
| `docker/autoresearch/docker-compose.yml` | 不改 | — |
| `docs/claude/EXPERIMENT_STANDARDS.md` | 更新 PBO 定義 | — |

### 不改的部分

- evaluate.py 的 L1-L5 邏輯不動
- Validator 的其他 14 項不動
- 部署門檻：`factor_pbo <= 0.50` 取代現有 `pbo <= 0.70`
- autoresearch agent 的行為不受影響（不看 PBO 結果）

## 5. 部署門檻調整

| 現在 | 改後 |
|------|------|
| `pbo <= 0.70`（construction sensitivity） | `factor_pbo <= 0.50`（Bailey 原意） |

0.50 是 Bailey 原論文的標準門檻：> 0.50 代表超過一半的 IS/OOS 分割中最佳因子在 OOS 表現低於中位數。

**但前 20 個因子期間無法算 factor_pbo** — 用 `construction_sensitivity` 作為過渡，門檻維持 0.70。

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
| Step 1: evaluate.py 存 daily returns | 1 小時 | 無 |
| Step 2: watchdog factor-level PBO | 1 小時 | Step 1 |
| Step 3: 報告整合 + 門檻調整 | 30 分鐘 | Step 2 |
| Step 4: 現有 PBO 改名 | 15 分鐘 | Step 2 |
| 驗證 + 測試 | 1 小時 | Step 1-4 |
| **總計** | **~4 小時** | |
