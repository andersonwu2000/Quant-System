# Phase M：因子庫管理 + 進階策略

> 狀態：🔵 待執行
> 前置：Phase L（策略轉型）部分完成即可開始
> 依據：FactorMiner 論文（因子去重/替換機制）+ FinLab 研究（散戶反向/事件驅動）
> 目標：因子庫去冗餘、進階策略實作、擁擠度監測

---

## 背景

### 因子庫冗餘問題

目前 80 個因子（66 FACTOR_REGISTRY + 14 FUNDAMENTAL_REGISTRY）存在大量冗餘：
- `momentum` ≈ `momentum_12m`（IC 0.0392 vs 0.0393）
- `idio_skew` = `skewness`（完全相同）
- 20 個 Kakushadze alpha 在台股全軍覆沒（換手率 55-84%，成本吞噬 alpha）

FactorMiner 論文的因子管理機制值得借鑑：
- **入庫門檻**：IC ≥ τ 且與現有因子 ρ < θ
- **替換機制**：新因子 IC ≥ 1.3× 舊因子才替換
- **禁區記錄**：結構化記錄已知無效方向

### 進階策略

FinLab 研究指出兩個進階方向：
- **Strategy C: 散戶反向** — 集保 < 10 張持股減少 + 法人接手 + 營收 YoY > 30%
- **Strategy D: 事件驅動** — 營收跳升 > 50% 後第 4-7 天進場（跳過過度反應）

---

## M1：因子庫去冗餘

### M1.1 相關性矩陣分析

計算 80 個因子的截面 IC 時間序列相關性矩陣，識別 ρ > 0.5 的冗餘對。

**腳本**：`scripts/factor_dedup.py`

```python
def compute_factor_correlation_matrix(
    factor_ics: dict[str, pd.Series],  # factor_name → IC time series
    threshold: float = 0.5,
) -> tuple[pd.DataFrame, list[tuple[str, str, float]]]:
    """返回相關性矩陣和超過閾值的冗餘對。"""
```

### M1.2 入庫門檻制度化

修改 `src/strategy/research.py`，新增：

```python
FACTOR_ADMISSION_CRITERIA = {
    "min_abs_ic": 0.03,          # |IC| ≥ 0.03
    "max_correlation": 0.50,      # 與現有因子 ρ < 0.50
    "min_ic_improvement": 1.30,   # 替換門檻：IC ≥ 1.3× 舊因子
}

def check_factor_admission(
    new_factor_ic: pd.Series,
    library_ics: dict[str, pd.Series],
) -> tuple[bool, str]:
    """檢查新因子是否符合入庫標準。"""
```

### M1.3 因子替換機制

當新因子 IC 顯著優於某個現有因子，且只與該因子高度相關：

```python
def try_replace_factor(
    new_factor: str,
    new_ic: float,
    library: dict[str, float],  # existing factor → IC
    correlations: dict[str, float],  # existing factor → correlation with new
) -> str | None:
    """嘗試替換。返回被替換的因子名，或 None。"""
```

### M1.4 預期清理結果

| 動作 | 因子 | 原因 |
|------|------|------|
| 移除 | momentum_12m | ≈ momentum（ρ > 0.99） |
| 移除 | idio_skew | = skewness（完全相同） |
| 標記為台股無效 | alpha_1~alpha_101（20 個） | 換手率 > 55%，淨 alpha 全負 |
| 保留但標記 | ivol | 寬 universe ICIR -0.06，但大型股有信號 |

---

## M2：Experience Memory 結構化

### M2.1 設計

新增 `src/alpha/experience_memory.py`：

```python
@dataclass
class SuccessPattern:
    """成功的因子模式。"""
    name: str
    description: str
    factors: list[str]
    conditions: str  # 適用條件（如 "大型股"、"牛市"）
    evidence: str     # 實驗編號

@dataclass
class ForbiddenRegion:
    """已知無效的方向。"""
    name: str
    reason: str
    factors: list[str]  # 相關因子
    evidence: str

class ExperienceMemory:
    success_patterns: list[SuccessPattern]
    forbidden_regions: list[ForbiddenRegion]

    def query_relevant(self, context: str) -> tuple[list[SuccessPattern], list[ForbiddenRegion]]: ...
    def add_success(self, pattern: SuccessPattern) -> None: ...
    def add_forbidden(self, region: ForbiddenRegion) -> None: ...
```

### M2.2 初始化內容（從 15 次實驗蒸餾）

**成功模式**：
1. 月頻低換手動量（momentum, momentum_6m）— 台股唯一穩定 price-volume alpha
2. 營收 YoY 成長率 — 首個通過 ICIR 0.3 的基本面因子
3. 市值分層 — 消除 size effect 後因子信號浮現
4. DD 10% 控制 — 回撤保護效果穩定

**禁區**：
1. Kakushadze 短週期（換手 > 50%）— 台股成本扼殺
2. ivol 寬 universe — selection bias（32 支 ICIR 0.60 → 142 支 -0.06）
3. 外資淨買超 — 外資全球分散，台股預測力弱（FinLab: 逆向外資 CAGR -11.2%）
4. 低 PE / 低波動 — 台股傳統估值因子無效（FinLab: -1.4%）

---

## M3：進階策略

### M3.1 Strategy C：散戶反向 + 法人接手

> 前置：L1.3 集保數據

```python
FilterStrategyConfig(
    filters=[
        FilterCondition("retail_holding_4w_change", "lt", -0.3),  # 散戶 <10 張持股 4 週減 0.3%
        FilterCondition("institutional_10d_net", "gt", 0),         # 法人 10 日淨買 > 0
        FilterCondition("revenue_yoy", "gt", 30.0),               # 營收 YoY > 30%
        FilterCondition("volume_20d_avg", "gt", 300),
    ],
    rank_by="retail_holding_4w_change",  # 散戶減持越多越好（反向排序）
    top_n=15,
    rebalance="monthly",
)
```

### M3.2 Strategy D：事件驅動 — 營收跳升過度反應修正

> FinLab 對標：Claude 發現的 timing 規律（跳過前 3 天，第 4-7 天進場）

```python
@dataclass
class EventDrivenConfig:
    trigger: str = "revenue_yoy_jump_50"  # 營收 YoY 突然跳升 > 50%
    skip_days: int = 3                     # 跳過前 3 天過度反應
    hold_days: int = 4                     # 持有 4 天
    max_pe: float = 50.0                   # 排除高估值
    min_pe: float = 0.0                    # 排除虧損
```

此策略與 FilterStrategy 不同，需要獨立的事件驅動框架。

**新增**：`strategies/event_driven.py`

---

## M4：Centrality 擁擠度指標

### 設計

參考 FinLab 因子分析五件套中的 Centrality：

```python
# src/strategy/research.py 新增

def compute_factor_centrality(
    factor_values: pd.DataFrame,
    market_returns: pd.Series,
    window: int = 60,
) -> pd.Series:
    """計算因子擁擠度。

    方法：因子值的截面離散度（std across stocks）隨時間的變化。
    離散度下降 = 股票在該因子上趨同 = 擁擠。

    Returns:
        Centrality time series（高 = 擁擠風險）。
    """
```

擁擠度可用於：
1. 動態降低擁擠因子的權重
2. 當動量因子擁擠度高時，降低動量配置
3. 預警因子可能反轉

---

## 關鍵檔案變更

| 檔案 | 變更 | 階段 |
|------|------|:----:|
| `scripts/factor_dedup.py` | **新檔案**：因子冗餘分析 | M1 |
| `src/strategy/research.py` | 修改：入庫門檻 + 替換機制 | M1 |
| `src/alpha/experience_memory.py` | **新檔案**：經驗記憶 | M2 |
| `strategies/event_driven.py` | **新檔案**：事件驅動策略 | M3 |
| `src/strategy/research.py` | 修改：centrality 計算 | M4 |
| `tests/unit/test_factor_admission.py` | **新檔案** | M1 |
| `tests/unit/test_experience_memory.py` | **新檔案** | M2 |

---

## 執行順序

```
M1（去冗餘）──→ M2（Experience Memory）
                      ↓
L 完成後 ──→ M3（進階策略 C/D）──→ M4（擁擠度）
```

M1、M2 不依賴 L，可以先做。M3 依賴 L1.3（集保數據）。M4 獨立。
