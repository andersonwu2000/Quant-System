# Phase J：Alpha 自動化擴展至跨資產

> 狀態：⏸ 延後（等台股因子研究穩定後再擴展）
> 前置：Phase I 完成、台股因子研究 Phase 2 完成
> 論文：Asness et al. (2013) "Value and Momentum Everywhere"

## 目標
從「台股個股選股」擴展至「ETF 配置 + 跨市場」，實現完整的多資產自動化。

---

## J1: ETF Alpha Pipeline（🟡 P1）

### 論文依據
Asness et al. (2013): value + momentum 在 8 個市場/資產類別中普遍有效，且：
- Value 和 momentum **跨資產類別的相關性**高於被動暴露
- Value 和 momentum **互相負相關**（組合 Sharpe 提升）
- 三因子模型（global market, value everywhere, momentum everywhere）可解釋大部分報酬

### ETF Universe

**台灣 ETF**:
| 代碼 | 名稱 | 資產類別 |
|------|------|---------|
| 0050 | 元大台灣50 | 台股大型 |
| 0056 | 元大高股息 | 台股高息 |
| 00878 | 國泰永續高股息 | 台股 ESG |
| 00713 | 元大台灣高息低波 | 台股低波 |
| 00679B | 元大美債20年 | 美國長債 |
| 00687B | 國泰20年美債 | 美國長債 |

**美國 ETF**（透過 Yahoo Finance）:
| 代碼 | 名稱 | 資產類別 |
|------|------|---------|
| SPY | S&P 500 | 美股 |
| QQQ | Nasdaq 100 | 美股科技 |
| TLT | 20+ Year Treasury | 美國長債 |
| IEF | 7-10 Year Treasury | 美國中債 |
| GLD | Gold | 黃金 |
| DBC | Commodities | 商品 |

### ETF 因子
| 因子 | 定義 | 來源 |
|------|------|------|
| `etf_momentum` | 12-1 month return | Asness (2013) |
| `etf_value` | 殖利率 / PE ratio 倒數 | Asness (2013) |
| `etf_volatility` | 60-day realized vol（反向） | 低波動異常 |
| `etf_carry` | 殖利率 - 短期利率 | 利差策略 |

### 實作
| 檔案 | 內容 |
|------|------|
| `src/alpha/auto/config.py` | `AutoAlphaConfig` 新增 `asset_type: Literal["stock", "etf", "mixed"]` |
| `src/alpha/auto/universe.py` | `UniverseSelector` 新增 ETF 模式：從預設清單或 Scanner 選取 |
| `src/strategy/factors.py` | 新增 `etf_momentum()`, `etf_value()`, `etf_carry()` |
| `src/strategy/research.py` | `ETF_FACTOR_REGISTRY` 或擴展現有 REGISTRY |
| `src/alpha/auto/scheduler.py` | `run_full_cycle()` 根據 asset_type 選擇因子集 |
| `tests/` | ETF 因子 + ETF universe 測試 |

---

## J2: 兩層自動化整合（🟢 P2）

### 流程

```
每日 08:50（擴展版）：

Step 1: TacticalEngine（已有 src/allocation/）
  → 資產類別權重: {EQUITY: 0.60, ETF_BOND: 0.25, ETF_COMMODITY: 0.15}

Step 2: 股票部位 (60%)
  → AutoAlpha 個股選股（現有 Phase F 流程）
  → Scanner → 14+ 因子 → ICIR 篩選 → 權重

Step 3: 債券/商品 ETF 部位 (40%)
  → ETF Alpha Pipeline (J1)
  → ETF universe → 4 因子 → 權重

Step 4: 合併
  → stock_weights × 0.60 + etf_weights × 0.40
  → PortfolioOptimizer (Risk Parity or CVaR)
  → 最終權重

Step 5: 執行
  → ExecutionService → SinopacBroker (台灣) / 手動 (美國)
```

### 實作
| 檔案 | 內容 |
|------|------|
| `src/alpha/auto/scheduler.py` | `run_full_cycle()` 新增兩層模式 |
| `src/alpha/auto/executor.py` | 合併 stock + ETF 權重後送入 optimizer |
| `src/alpha/auto/config.py` | `AutoAlphaConfig` 新增 `two_layer_enabled`, `tactical_weights` |
| `tests/` | 兩層流程整合測試 |

### 注意
- 美國 ETF 需透過 Yahoo Finance 取得價格（非 Shioaji）
- 台灣 ETF 可透過 Shioaji 即時交易
- 美國 ETF 暫時只做配置建議，不自動下單（等 IB 對接）
