# 策略生成方式檢討報告

**日期**：2026-03-28
**範圍**：因子發現 → 策略構建 → 組合權重 → 下單執行 全流程
**結論**：現有管線用最粗糙的方式（signal_weight 正規化）將因子轉成權重，不考慮波動率、換手率、交易成本。14 種組合優化方法和成本感知建構模組已實作但完全未接入。

---

## 1. 現有流程

```
compute_factor(symbols, as_of, data)          [autoresearch / 研究因子]
    ↓ 回傳 dict[str, float]
    ↓
strategy_builder.build_from_research_factor()  [包裝成 Strategy]
    ↓ 內部建立 ResearchFactorStrategy 類
    ↓
ResearchFactorStrategy.on_bar(ctx)             [每月執行一次]
    ├─ 流動性篩選（vol > 300,000 股）
    ├─ batch compute_factor(eligible, as_of, data)
    ├─ sort by score × direction
    ├─ 取 top 15
    ├─ abs(score) 作為信號強度
    └─ signal_weight(signals, max_weight=0.10)
        ├─ normalize to sum = 0.95
        └─ cap each at 0.10
    ↓ 回傳 dict[str, float] weights
    ↓
weights_to_orders(target, current, prices)     [權重 → 委託單]
    ├─ diff = target - current
    ├─ skip if |diff| < 0.001
    ├─ round to lot_size (1000 股)
    ├─ cap at 10% ADV
    └─ cap buy at available_cash
    ↓
risk_engine.check_orders(orders)               [風控檢查]
    ↓
SimBroker.execute(orders)                      [成交模擬]
    ├─ sqrt impact model
    ├─ commission + tax
    └─ volume cap
```

---

## 2. 問題清單

### 2.1 管線斷裂（三個孤島）

| 模組 | 行數 | 功能 | 狀態 |
|------|------|------|------|
| `src/strategy/optimizer.py` | 127 | signal_weight, equal_weight, risk_parity | **被使用**（strategy_builder 用 signal_weight） |
| `src/portfolio/optimizer.py` | 508 | 14 種優化（HRP, max_sharpe, min_variance, Black-Litterman...） | **完全未使用** |
| `src/alpha/construction.py` | 230 | 成本感知建構（turnover penalty, alpha decay, max_turnover） | **完全未使用** |

三個模組沒有橋接。策略層只用最簡單的 `signal_weight`，跳過了風險模型和成本感知。

### 2.2 權重配置的 6 個具體問題

| # | 問題 | 位置 | 影響 |
|---|------|------|------|
| 1 | **不考慮波動率** — 高波動股和低波動股拿到一樣的權重，高波動股主導組合風險 | strategy_builder:159 | Sharpe 偏低、MDD 偏高 |
| 2 | **固定 top_n=15** — 不管信號分佈如何，永遠選 15 支 | strategy_builder:37 | 弱信號股票拉低品質；或錯失更多強信號股票 |
| 3 | **無換手率控制** — 每月全部重建權重，不考慮現有持倉 | strategy_builder:149-159 | 台股 round-trip 0.585%，月度全換倉成本 ~2%/年 |
| 4 | **signal_weight 截斷不重分配** — 超過 max_weight 的部分直接丟棄 | optimizer.py:74 | 總投資可能只有 70-80%，剩餘現金拉低報酬 |
| 5 | **abs(score) 消除信號比例** — direction 調整後取絕對值，所有信號變正 | strategy_builder:158 | 排名第 1（score=100）和第 15（score=5）拿到幾乎一樣的權重（因為 normalize 後 cap 在 10%）|
| 6 | **策略不知道當前持倉** — on_bar 只回傳目標權重，無法做成本感知調整 | 設計限制 | 無法實作 no-trade zone 或 partial rebalancing |

### 2.3 成本結構被忽視

台股成本：
- 買入：佣金 0.1425%
- 賣出：佣金 0.1425% + 證交稅 0.3% = **0.4425%**
- Round-trip：**0.585%**
- 如果月度 turnover 30%（單邊），年化成本 = 0.585% × 12 × 30% = **2.1%/年**

賣出成本是買入的 **3 倍**。但 `signal_weight` 和 `weights_to_orders` 完全不知道這個不對稱性。

### 2.4 lot size 的隱性成本

台股整張 = 1000 股。portfolio 1000 萬 TWD：
- 目標 5% = 50 萬。股價 500 元 → 1000 股 = 1 張，剛好
- 股價 200 元 → 2500 股，只能買 2 張（40 萬）或 3 張（60 萬），偏離 ±2%
- 台積電 ~1000 元 → 1 張 = 100 萬 = 10% portfolio，買不了 5%

`weights_to_orders` 有 lot size 取整，但**取整損失不回饋到權重分配**。

### 2.5 硬編碼參數不一致

| 參數 | strategy/optimizer.py | portfolio/optimizer.py | construction.py | 實際用的 |
|------|----------------------|----------------------|-----------------|---------|
| max_weight | 0.05 | 0.30 | — | **0.10**（strategy_builder 覆蓋） |
| cost_bps | — | — | 30.0（單邊） | **14.25 + 30.0**（SimBroker 分開算） |
| max_total | 0.95 | — | 0.95 | 0.95 |
| turnover_penalty | — | — | 0.0005 | **未使用** |

---

## 3. 學術與業界最佳實務

### 3.1 Signal → Weight 轉換

| 方法 | 優點 | 缺點 | 適用場景 |
|------|------|------|---------|
| **Rank-based** | robust to outliers | 丟失信號幅度 | 大 universe（>100） |
| **Z-score normalization** | 保留信號強度 | outlier 敏感 | 信號近似常態 |
| **Inverse-vol weighting** | 等風險貢獻 | 忽略 correlation | 中等 universe |
| **Grinold-Kahn optimal** | 理論最優 | 需要好的 Σ 和 α 估計 | 高品質 alpha |
| **Robert Carver forecast scaling** | volatility targeting | 需要 target vol | 多資產 |

**建議**：`rank(signal) / volatility` — 結合信號排名和波動率倒數，最穩健。

### 3.2 換手率管理

| 方法 | 效果 | 複雜度 |
|------|------|--------|
| **No-trade zone**（偏離 < 2% 不動） | turnover 降 50%+ | 低 |
| **Exponential blending**（w = 0.3×target + 0.7×current） | turnover 降 70% | 低 |
| **L1 turnover penalty in optimizer** | 精確控制 | 中 |
| **Priority-best rebalancing**（只調最偏離的） | 學術證實最優 | 中 |

**2024 實證**：Cost-aware optimizer 把 turnover 從 18x/年 降到 1.85x/年，net return 大幅改善。

### 3.3 持股數量

| 研究 | 建議 |
|------|------|
| Statman (1987) | 最少 30 支消除非系統性風險 |
| DeMiguel (2009) | 1/N（25 支）難以被 mean-variance 打敗 |
| Acadian (2024) | 極端集中（<25 支）是災難配方 |
| Factor investing 標準 | top decile（前 10%），150 支 universe → 15 支 |

**建議**：15 支在台股偏少（個股波動大）。**25-30 支**更穩健，降低 stock-specific risk。

### 3.4 台股特殊考量

- Round-trip cost 0.585%，賣出是買入 3 倍 → optimizer 必須反映不對稱
- 整張 1000 股 → 小資金（<3000 萬）需要零股
- 高價股（台積電 ~1000 元）1 張 = 100 萬 → 嚴重破壞 weight precision
- 零股撮合改善（2024：5 秒間隔），但 spread 仍大
- 營收因子天然月頻 + 40 天延遲 → 實際 holding period ~2 月

---

## 4. 改進方案

### Phase 1：低成本高回報（1-2 天）

#### 4.1 Inverse-vol signal weighting

取代 `signal_weight` 的純信號比例分配：

```python
def vol_adjusted_weight(signals, volatilities, constraints):
    """rank(signal) / volatility，結合信號排名和風險感知。"""
    ranked = {s: rank for rank, s in enumerate(sorted(signals, key=signals.get))}
    raw = {s: ranked[s] / max(volatilities.get(s, 0.20), 0.05) for s in signals}
    total = sum(raw.values())
    weights = {s: (v / total) * constraints.max_total_weight for s, v in raw.items()}
    return {s: min(w, constraints.max_weight) for s, w in weights.items() if w >= constraints.min_weight}
```

**所需改動**：strategy_builder 的 on_bar 要額外取 20 天波動率（`ctx.bars(sym, 20)` 已有）。

#### 4.2 No-trade zone

```python
def on_bar(self, ctx):
    target = self._compute_target_weights(ctx)
    current = self._get_current_weights(ctx)
    # 只調整偏離 > 2% 的持倉
    adjusted = {}
    for sym in set(target) | set(current):
        t = target.get(sym, 0)
        c = current.get(sym, 0)
        if abs(t - c) > 0.02:
            adjusted[sym] = t
        else:
            adjusted[sym] = c  # 保持不動
    return adjusted
```

**所需改動**：on_bar 需要透過 `ctx.portfolio()` 取得當前持倉權重。

#### 4.3 Top-n 增加到 25

只改 `strategy_builder.build_from_research_factor(top_n=25)` 和 `max_weight` 從 0.10 降到 0.06。

### Phase 2：接入現有模組（3-5 天）

#### 4.4 接入 construction.py 的 cost-aware rebalancing

```python
from src.alpha.construction import construct_portfolio, ConstructionConfig

config = ConstructionConfig(
    max_weight=0.06,
    max_total_weight=0.95,
    cost_bps=44.25,  # 台股 sell 側 0.4425%
    turnover_penalty=0.005,
    max_turnover=0.30,
)
weights = construct_portfolio(
    signal=signal_series,
    current_weights=current_weight_series,
    config=config,
)
```

**所需改動**：
- construction.py 的 `turnover_penalty` 從 0.0005 調到合理值（0.005 ≈ round-trip cost）
- strategy_builder 傳入 `current_weights`

#### 4.5 接入 portfolio/optimizer.py 的 risk_parity

```python
from src.portfolio.optimizer import PortfolioOptimizer, OptimizerConfig

opt = PortfolioOptimizer(OptimizerConfig(method="risk_parity", max_weight=0.06))
weights = opt.optimize(
    returns=recent_returns_df,  # 60 天日報酬 DataFrame
    signals=signal_dict,
)
```

**所需改動**：
- strategy_builder 的 on_bar 需要建構 returns DataFrame（從 ctx.bars 取）
- OptimizerConfig.max_weight 預設 0.30 太高，需要覆蓋

### Phase 3：進階功能（1-2 週）

#### 4.6 非對稱成本模型

```python
# 在 weights_to_orders 或 construction.py 加入
buy_cost = 0.001425
sell_cost = 0.001425 + 0.003  # = 0.004425
# 賣出門檻更高：只有 alpha 收益 > sell_cost 才值得賣
```

#### 4.7 Lot size 感知的權重分配

先算理想權重 → round to lot size → 用剩餘資金買零股補齊 → 回饋到實際權重。

#### 4.8 信號驅動 rebalance

只在 top-25 的成員變化 > 20% 時才觸發完整 rebalance。否則只調整偏離 > 3% 的個別持倉。

---

## 5. 預期效果

| 改進 | Sharpe 改善 | 成本降低 | 實作難度 |
|------|-----------|---------|---------|
| Inverse-vol weighting | +0.05-0.15 | — | 低（10 行） |
| No-trade zone | — | -30~50% turnover | 低（15 行） |
| Top-n 15→25 | +0.05-0.10（降低 stock-specific risk） | +5% turnover | 極低（改 1 個參數） |
| 接入 construction.py | +0.05-0.10 | -20~30% turnover | 中（50 行） |
| 接入 risk_parity | +0.10-0.20 | — | 中（30 行） |
| 非對稱成本 | — | -10~15% 不必要賣出 | 低（5 行） |
| Lot size 感知 | +0.02-0.05 | — | 中（40 行） |

**保守估計**：Phase 1 的三項改進可以讓 net Sharpe 提升 0.10-0.25，成本降低 30-50%，工作量 1-2 天。

---

## 6. 風險

| 風險 | 緩解 |
|------|------|
| Inverse-vol 在低波動期 over-concentrate | 加 min_vol floor（如 10%） |
| No-trade zone 導致持倉漂移 | 設 max_drift 上限（如 5%）|
| 增加到 25 支降低 alpha 集中度 | 用信號加權而非等權 |
| construction.py 的 turnover_penalty 太嚴凍結 rebalance | 校準 lambda = round-trip cost / alpha |
| 改動太多同時上線 | 逐一改、逐一回測比較 |

---

## 7. 參考文獻

- DeMiguel, Garlappi, Uppal (2009). Optimal Versus Naive Diversification. RFS.
- Grinold & Kahn (2000). Active Portfolio Management.
- Carver, R. (2015). Systematic Trading.
- Baldi-Lanfranchi et al. (2024). Cost-aware Portfolios. arXiv:2412.11575.
- FAJ 2024. Smart Rebalancing.
- Acadian 2024. Concentrated Portfolio Managers.
- Kakushadze (2016). 101 Formulaic Alphas.
- MOSEK Portfolio Cookbook: Transaction Costs.
- TWSE 2024. Odd Lot Trading Statistics.

---

## 8. 審批意見（2026-03-28）

**審批結果：通過。Phase 1 立即執行，Phase 2 視 Phase 1 效果決定，Phase 3 延後。**

### 為什麼應該執行

1. **PBO 惡化的根因之一是策略構建太粗糙** — 等權 top-15 的 10 個變體（top_n × weighting）之間差異大，排名不穩定。如果構建更穩健（inverse-vol + no-trade zone），變體差異縮小 → PBO 可能改善。

2. **revenue_momentum_hedged 的 OOS Sharpe -0.73** — IS Sharpe 0.91 vs OOS -0.73 的巨大落差，部分原因是月度全換倉的成本（2.1%/年）吃掉了 alpha。no-trade zone 可直接改善。

3. **14 種優化方法已實作但完全未使用** — 沉沒成本 738 行代碼（portfolio/optimizer.py + alpha/construction.py）。接入它們的 ROI 極高。

4. **對 autoresearch 的直接幫助** — 新因子通過 L5 後，如果策略構建更好，Validator 的 Sharpe/MDD/PBO 都可能改善，更容易通過部署門檻。

### 逐項評估

| 改進 | 是否執行 | 理由 |
|------|:--------:|------|
| 4.1 Inverse-vol weighting | **✅ 立即** | 10 行代碼，理論明確，降低高波動股的過度暴露 |
| 4.2 No-trade zone | **✅ 立即** | 15 行代碼，成本降 30-50%，對 OOS Sharpe 直接有幫助 |
| 4.3 Top-n 15→25 | **⚠️ 謹慎** | 學術支持但會降低 alpha 集中度。建議先保持 15，用 inverse-vol 改善權重分配 |
| 4.4 接入 construction.py | **⏸ Phase 2** | 需要 on_bar 拿到 current_weights，改動較大 |
| 4.5 接入 risk_parity | **⏸ Phase 2** | 需要 returns DataFrame，改動大 |
| 4.6 非對稱成本 | **✅ 立即** | 5 行代碼，邏輯明確（賣出門檻 > 買入） |
| 4.7 Lot size 感知 | **⏸ Phase 3** | 向量化 PBO 已加了 lot size，Validator 有 SimBroker 處理 |
| 4.8 信號驅動 rebalance | **⏸ Phase 3** | 依賴 4.2 的 no-trade zone 基礎 |

### 執行優先級

```
立即（Phase 1）：
  4.1 inverse-vol weighting  → strategy_builder.py
  4.2 no-trade zone          → strategy_builder.py
  4.6 非對稱成本              → strategy_builder.py 或 construction.py

驗證：
  改完後重跑 revenue_momentum_hedged Validator
  對比 Sharpe / turnover / PBO 變化

Phase 2（Phase 1 驗證後）：
  4.4 + 4.5 接入現有模組
```

### 注意事項

1. **4.2 no-trade zone 需要 ctx 提供當前持倉** — 目前 `Strategy.on_bar(ctx)` 可以透過 `ctx.portfolio()` 取得，但要確認 BacktestEngine 是否在每次 on_bar 前更新 portfolio
2. **4.1 inverse-vol 的 vol 計算** — 用 20 天 close-to-close std × sqrt(252)，和 Validator 的 Sharpe 分母一致
3. **改動必須逐一上線** — 不要同時改 3 個東西，無法歸因。先 4.1 → 跑 Validator → 再 4.2 → 跑 Validator → 再 4.6
4. **autoresearch 的因子也受益** — strategy_builder 改了，所有 autoresearch 因子的 Validator 結果都會變。之前的 PBO 數值不再可比
