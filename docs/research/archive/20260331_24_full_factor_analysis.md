# 全因子分析報告 — 2026-03-31（Phase AD 數據平台完成後）

> 方法論：autoresearch evaluate.py L1-L5 閘門（月度 IC 取樣）
> 數據：FinLab 2005-2018 + FinMind 2019-2026 合併（完整 21 年歷史）
> Universe：200 支台股（研究 universe）
> IS：207 個月度 sample dates，OOS：18 個月度 sample dates

---

## 核心結論

| 結論 | 證據 |
|------|------|
| **2 個因子通過 L5 OOS** | revenue_acceleration + per_value |
| **數據合併是關鍵** | 合併前 revenue_acceleration L0（無數據），合併後 L5 PASS |
| 純技術面因子在台股偏弱 | momentum 12-1 只到 L2，其他全 L1 |
| 法人面因子 L1 失敗 | trust_net、foreign_net IC < 0.02 |
| per_value 是新發現 | 之前 PE/PB 被禁用（look-ahead bias），用 per_history 時間序列後 L5 通過 |

---

## 全因子結果

| 因子 | Level | IC_20d | Best ICIR | OOS IC | OOS ICIR | Status |
|------|:-----:|-------:|----------:|-------:|---------:|:------:|
| **revenue_acceleration** | **L5 PASS** | 0.049 | 0.635 | +0.030 | +0.274 | **PASS** |
| **per_value** | **L5 PASS** | 0.049 | 0.463 | +0.047 | +0.598 | **PASS** |
| momentum_12_1 | L2 | 0.054 | 0.217 | — | — | fail |
| low_volatility_120d | L2 | 0.027 | 0.178 | — | — | fail |
| revenue_yoy | L1 | 0.010 | — | — | — | fail |
| momentum_1m | L1 | 0.006 | — | — | — | fail |
| trust_net_20d | L1 | 0.005 | — | — | — | fail |
| foreign_net_20d | L1 | 0.010 | — | — | — | fail |
| pbr_value | L1 | 0.019 | — | — | — | fail |
| overnight_return_60d | L1 | 0.018 | — | — | — | fail |
| margin_usage | L1 | 0.001 | — | — | — | fail |

---

## L5 PASS 因子詳細

### revenue_acceleration

| Horizon | ICIR |
|---------|-----:|
| 5d | +0.178 |
| 20d | +0.360 |
| **60d** | **+0.635** |

- IS 正年數：10 年（207 個月度 sample）
- OOS IC：+0.030（17 個 sample dates）
- OOS ICIR：+0.274
- **長期 horizon（60d）最強** — 營收加速度是慢變因子

### per_value（新發現）

| Horizon | ICIR |
|---------|-----:|
| 5d | +0.245 |
| 20d | +0.400 |
| **60d** | **+0.463** |

- IS 正年數：9 年
- OOS IC：+0.047（17 個 sample dates）
- **OOS ICIR：+0.598** — OOS 比 revenue_acceleration 更強
- 反向 PER（低本益比 = 高分數）— 經典 value 因子

---

## 關鍵發現

### 1. 數據合併改變了結果

| 因子 | 合併前（FinMind only） | 合併後（FinLab + FinMind） |
|------|:----:|:----:|
| revenue_acceleration | L0（無數據） | **L5 PASS** |
| per_value | L1 | **L5 PASS** |

原因：FinMind revenue 從 2019 開始，IS 期間（到 2024）只有 5 年數據，不夠算穩定的 IC。合併 FinLab 2005-2018 後有 21 年歷史，IC 估計更穩定。

### 2. per_value 之前被禁用是錯的

之前 `pe`/`pb` 在 evaluate.py 中被 mask 為空（M-08 fix），因為它們是 "latest-only snapshot"（look-ahead bias）。但 `per_history` 是**每日時間序列**，用 `as_of` 截斷後沒有 look-ahead bias。per_value 利用了 per_history 的 PER 欄位。

### 3. 法人面因子全部 L1

trust_net_20d 和 foreign_net_20d 都 IC < 0.02。可能原因：
- TWSE 三大法人數據主要從 2016 開始（覆蓋不足）
- 20 天窗口太短，法人操作是長期累積
- 台股散戶占比高，法人信號被噪音淹沒

---

## 與實驗 #21 的比較

| 指標 | 實驗 #21（2026-03-27） | 本次（2026-03-31） |
|------|:----:|:----:|
| 數據 | FinMind only（874 支 revenue） | FinLab + FinMind（合併 21 年） |
| revenue_acceleration ICIR | +0.438（20d） | +0.635（60d） |
| OOS | FAIL | **PASS**（OOS IC +0.030） |
| per_value | 未測試（PE/PB 被禁用） | **L5 PASS**（ICIR 0.463） |

---

## 下一步

1. **跑 StrategyValidator**（15 項）— 用 revenue_acceleration + per_value 組合
2. **考慮雙因子策略** — revenue_acceleration（成長）× per_value（價值）= 成長價值交叉因子
3. **autoresearch agent 也可能發現這兩個因子** — 目前 105 個實驗都在 L2 以下，但數據合併修復後可能突破
