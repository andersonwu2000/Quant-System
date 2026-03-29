# IC-Alpha Gap 分析：為什麼 110 個 L5 因子全部 Validator 不通過

**日期**：2026-03-30
**觸發**：autoresearch 產出 110 個 L5 因子（median ICIR ≥ 0.30），但 Validator 全部 16/17（vs_ew_universe 失敗）

---

## 現象

| 指標 | evaluate.py (L5) | Validator |
|------|:----------------:|:---------:|
| IC/ICIR | ✅ 通過 | — |
| OOS 驗證 | ✅ 通過 | — |
| vs_ew_universe | **未測** | ❌ 全部不通過 |

因子能正確**排名**股票（高 IC），但 top-15 等權組合**跑輸全 universe 等權**。

## 根因：Transfer Coefficient 損耗

Clarke, de Silva & Thorley (2002) — Grinold 基本法則完整版：

```
E(R) = TC × IC × √BR × σ
```

等權 Top-15 的 TC << 1.0：
- **Long-only**：丟掉做空端信號（IC 衡量全截面，但只做多一半）
- **等權**：不反映信號強度（IC 0.90 和 IC 0.50 的股票權重相同）
- **Top-N 截斷**：只用排名最前 15 支，丟棄其餘 185 支的信號

## 台股特殊因素

- Revenue ratio 在**小型高波動股**可能更有效 → top-15 波動高、risk-adjusted 不如大盤
- 200 支 universe 本身已篩過流動性（ADV ≥ 340M），等權這 200 支的表現可能已經很好
- 半導體佔比高 → revenue acceleration 可能只是產業周期曝險

## 管線缺口

```
現在：  L1-L4 (IC/ICIR) ──→ L5 (OOS) ──→ StrategyValidator (16+1項)
                                          ↑
                              大跨步，中間缺少 portfolio-level 診斷
```

evaluate.py 測的是「因子信號品質」，StrategyValidator 測的是「策略表現」。中間的轉換（篩選 + 建構 + 成本）可能毀掉信號。

## 建議修正：L5 加兩個輕量 gate

| 檢查 | 做什麼 | 計算量 | 門檻 |
|------|--------|:------:|------|
| excess_return | top-15 月報酬 - universe 月報酬 | +5 秒 | > 0（不輸大盤） |
| monotonicity | 5 分位報酬是否單調遞減 | +2 秒 | Spearman > 0.5 |

evaluate.py 已有 top-15 portfolio returns，只需同時算 universe returns 比較。不改架構、不加 Validator。

## 文獻支持

- Clarke, de Silva & Thorley (2002) "Portfolio Constraints and the Fundamental Law" — TC 量化
- Qian, Sorensen & Hua (2007) "Information Horizon" — IC horizon 和換倉頻率不匹配
- Zhang, Wang & Cao (2021) "Turnover-Adjusted IR" — 成本侵蝕
- Harvey, Liu & Zhu (2016) "...and the Cross-Section of Expected Returns" — 多重測試
- AQR JPM 2023 "Fact, Fiction and Factor Investing" — IC 是初篩，組合表現是最終標準

## 決策

- [ ] 在 evaluate.py L5 加 excess_return + monotonicity gate
- [ ] 不改 StrategyValidator（已正確擋住）
- [ ] 不改 autoresearch 架構（evaluate.py 仍是 black-box）
- [ ] 同時提供 agent 新數據（per_history, margin）讓它探索非 revenue 方向
