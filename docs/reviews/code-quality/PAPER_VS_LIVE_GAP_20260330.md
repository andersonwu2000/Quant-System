# Paper vs Live 精準度差距排查

**日期**：2026-03-30（初稿）→ 2026-03-31（驗證更新）
**方法**：追蹤 paper trading 的完整執行路徑，逐項比對 live 行為

---

## 執行路徑

```
Paper mode:
  ExecutionService(mode=paper)
    → SimBroker(SimConfig)  ← 模擬撮合（漲跌停+部分成交+零股時段）
    → refresh_all_trading_data() 更新數據
    → yfinance 即時價 → current_bars
    → execute_from_weights() → SimBroker.execute()

Live mode:
  ExecutionService(mode=live)
    → SinopacBroker(simulation=False)
    → connect() + activate_ca()
    → submit_order() → 真的 place_order() → callback 等成交
```

---

## 逐項差距

| # | 面向 | Paper (SimBroker) | Live (SinopacBroker) | 差距嚴重度 | 狀態 |
|---|------|------------------|---------------------|:----------:|:----:|
| 1 | **成交價格** | sqrt impact model（base 2bps + volume-aware） | 交易所撮合價 | MEDIUM | ⚠️ 部分修 |
| 2 | **成交時間** | 立即 FILLED | 可能延遲數秒到數分鐘 | LOW | 接受 |
| 3 | **部分成交** | 超過 10% ADV 時縮減成交量 | 零股可能部分成交或不成交 | MEDIUM | ✅ 已修 |
| 4 | **漲跌停** | ±9.5% 拒單 + fill price ±10% 二次檢查 | 交易所拒絕 | — | ✅ 已修 |
| 5 | **零股交易時段** | `check_odd_lot_session=True`，非 09:10-13:30 拒單 | 盤中零股 09:10-13:30 | — | ✅ 已修 |
| 6 | **成交量限制** | `max_fill_pct_of_volume=0.10` | 流動性不足會成交延遲或失敗 | LOW | ✅ 已修 |
| 7 | **market impact** | sqrt model（`impact_coeff=50`） | 真實 market impact | LOW | ⚠️ 近似 |
| 8 | **order.price 來源** | yfinance 即時價 + refresh 後 parquet fallback | 盤中即時價 | LOW | ✅ 已修 |
| 9 | **T+2 交割** | 不模擬（現金立即扣） | T+2 才真正扣款 | LOW | 接受（偏保守） |
| 10 | **手續費折扣** | 面值 0.1425%（無折扣） | 多數券商電子下單 6 折 | LOW | 接受（偏保守） |
| 11 | **min commission** | 整張 20 元 / 零股 1 元 | 券商實際可能不同 | LOW | 接受 |
| 12 | **訂單類型** | 限價單 | 限價/市價/IOC/FOK | LOW | 接受 |

---

## 修復歷程

### 2026-03-31 Phase AD + code review 修復

| # | 修了什麼 | 位置 |
|---|---------|------|
| #8 | `refresh_all_trading_data()` 在 feed 建立前執行；paper mode 用 yfinance 即時價建 `current_bars` | `jobs.py:415-425, 550-556` |
| #4 | SimBroker 加漲跌停檢查：±9.5% 拒單 + fill price ±limit_pct 二次檢查 | `simulated.py:131-197` |
| #3 | Paper mode 啟用 `partial_fill=True`，超過 10% ADV 縮減成交量 | `jobs.py:523, simulated.py:157-166` |
| #5 | SimBroker 加 `check_odd_lot_session` flag，paper mode 開啟，回測關閉 | `simulated.py:47, 175-181, jobs.py:525` |
| #1 | SimConfig 預設 sqrt impact model（非固定 slippage） | `simulated.py:30-32` |

### 仍存在的差距

| # | 為什麼不修 | 如何緩解 |
|---|-----------|---------|
| #1 slippage 精度 | sqrt model 是近似，真實 impact 只有實盤才知道 | 微額實盤數據校準 impact_coeff |
| #3 零股成交率 | 模擬只看 ADV，不知道零股實際成交率 | 微額實盤數據校準 |
| #9 T+2 | Paper 現金扣太快 = 偏保守 | 不需修 |
| #10 手續費 | Paper 成本偏高 = 偏保守 | 不需修 |

---

## 結論

**Paper trading 的 SimBroker 已涵蓋台股主要交易規則**（漲跌停、零股時段、部分成交、volume-aware slippage）。剩餘差距主要是 slippage 精度，只能透過微額實盤校準。

**Paper NAV 預期仍略偏樂觀**（100% 零股成交假設 vs 實際可能 70-80%），但偏差幅度比初版小很多。
