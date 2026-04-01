# Phase AL：Trading Safety — 杜絕 Paper/Live Trading Bug

> 建立日期：2026-04-01
> 狀態：未開始
> 優先級：**最高** — 不完成此 Phase 不得進入 live trading

---

## 0. 動機

本系統累計發現 81 個 bug。其中至少 6 個直接影響 paper/live trading（#71-73, #76-77, plus 散佈各處的 `if mode == "paper"` 遺漏）。現有 1,912 個測試中 407 處使用 mock，**0 個測試跑真實的 BacktestEngine**。測試驗證的是「我們以為系統怎麼工作」，不是「系統實際怎麼工作」。

更危險的是：修 bug 本身會引入新 bug。Phase AA 4.2+4.6 在同一個 session 中被標為「未實作」又被改回「已實作」— 修正本身是錯的。

### 核心原則

1. **測試不能只依賴 mock** — mock 測試驗證的是「你的假設」，不是「系統的行為」
2. **防禦不能只靠測試** — 1,912 個測試全過不代表 live trading 不會出事
3. **安全必須是 runtime 的** — 在生產代碼中加斷言，用真實資料即時檢查
4. **異常必須 fail-closed** — 任何意外狀態都停止交易，不是靜默繼續

---

## 1. Runtime Invariant（運行時不變量）

**在交易路徑的每個關鍵節點加入不變量檢查。** 違反時立即停止交易並告警。

### 1.1 Portfolio Invariant

在 `apply_trades()` 後、每次 NAV 計算時檢查：

```python
# src/core/models.py — Portfolio
def _check_invariants(self) -> None:
    """交易後自動執行。違反任一條即 raise。"""
    # I1: NAV 永遠非負
    if self.nav < 0:
        raise TradingInvariantError(f"NAV={self.nav} is negative")

    # I2: 現金永遠非負（不允許透支）
    if self.cash < 0:
        raise TradingInvariantError(f"Cash={self.cash} is negative")

    # I3: 持倉數量必須 >= 0（做多策略不允許負持倉）
    for sym, pos in self.positions.items():
        if pos.quantity < 0:
            raise TradingInvariantError(f"{sym} quantity={pos.quantity} is negative")

    # I4: NAV = cash + sum(market_value)，誤差 < 1 元
    computed = self.cash + sum(p.market_value for p in self.positions.values())
    if abs(computed - self.nav) > 1:
        raise TradingInvariantError(
            f"NAV mismatch: computed={computed}, stored={self.nav}")

    # I5: 單一持倉不超過 NAV 的 20%（硬上限，超過即異常）
    if self.nav > 0:
        for sym, pos in self.positions.items():
            weight = abs(pos.market_value) / self.nav
            if weight > 0.20:
                raise TradingInvariantError(
                    f"{sym} weight={weight:.1%} > 20% hard limit")
```

### 1.2 Order Invariant

在 `submit_orders()` 內、風控檢查前：

```python
# src/execution/service.py — _check_order_invariants()
def _check_order_invariants(self, orders: list[Order]) -> None:
    """每筆訂單的基本 sanity check。"""
    for o in orders:
        # I6: 數量必須 > 0
        if o.quantity <= 0:
            raise TradingInvariantError(f"Order qty={o.quantity} <= 0")

        # I7: 價格必須 > 0（市價單除外）
        if o.price is not None and o.price <= 0:
            raise TradingInvariantError(f"Order price={o.price} <= 0")

        # I8: Symbol 不得為空
        if not o.instrument.symbol:
            raise TradingInvariantError("Order has empty symbol")
```

### 1.3 Fill Invariant

在 `SimBroker.execute()` 和 `SinopacBroker` 成交回報後：

```python
# I9: 成交價不得偏離市價超過 10%
if abs(fill_price - market_price) / market_price > 0.10:
    raise TradingInvariantError(
        f"Fill price {fill_price} deviates >10% from market {market_price}")

# I10: 成交數量不得超過委託數量
if fill_qty > order.quantity:
    raise TradingInvariantError(
        f"Fill qty {fill_qty} > order qty {order.quantity}")

# I11: 手續費不得為負
if commission < 0:
    raise TradingInvariantError(f"Commission {commission} is negative")
```

### 1.4 Pipeline Invariant

在 `execute_pipeline()` 的每個階段轉換點：

```python
# I12: 策略回傳的權重總和不超過 1.05（含容差）
total_weight = sum(abs(w) for w in weights.values())
if total_weight > 1.05:
    raise TradingInvariantError(f"Total weight {total_weight:.2f} > 1.05")

# I13: 權重中不得有 NaN 或 Inf
for sym, w in weights.items():
    if math.isnan(w) or math.isinf(w):
        raise TradingInvariantError(f"Weight for {sym} is {w}")

# I14: 訂單數量不得超過持倉股票數 × 2（防止訂單爆炸）
if len(orders) > len(weights) * 2 + 5:
    raise TradingInvariantError(
        f"Order count {len(orders)} >> weight count {len(weights)}")
```

### 1.5 TradingInvariantError 的處理

```python
class TradingInvariantError(Exception):
    """交易路徑中的不變量被違反。

    捕獲後：
    1. 停止所有交易（set kill_switch_fired = True）
    2. 發送 P0 通知
    3. 記錄完整 context 到 audit log
    不靜默吞掉。不自動恢復。必須人工確認後才能重啟。
    """
    pass
```

---

## 2. 每日煙霧測試（Daily Smoke Test）

**用昨天的真實資料跑完整 pipeline，但不下單。** 每天盤前自動執行。

### 2.1 流程

```
盤前 08:30 自動執行：
  1. 載入昨日的真實市場資料
  2. 用 active strategy 跑 on_bar() 產生 weights
  3. weights_to_orders() 產生訂單
  4. 風控檢查每一筆訂單
  5. SimBroker 模擬成交（用昨日的 OHLCV）
  6. 檢查所有 invariant
  7. 比對：weights 是否合理、NAV 變化是否合理
  
通過 → 記錄到 data/smoke_test/{date}.json
失敗 → P0 告警 + 阻止今日交易
```

### 2.2 檢查項目

| # | 檢查 | 閾值 | 失敗動作 |
|---|------|------|---------|
| S1 | weights 不含 NaN/Inf | 0 | P0 停止交易 |
| S2 | 訂單數量合理 | ≤ 持倉數 × 2 | P0 停止交易 |
| S3 | 所有訂單通過風控 | REJECT ≤ 10% | P1 告警 |
| S4 | NAV 變化合理 | \|Δ\| ≤ 5% | P0 停止交易 |
| S5 | 無 TradingInvariantError | 0 | P0 停止交易 |
| S6 | 成交價在合理範圍 | ±10% 市價 | P0 停止交易 |
| S7 | 手續費計算合理 | 0 < fee < 成交額 1% | P1 告警 |

---

## 3. Paper vs Backtest 一致性監控

**持續比對 paper trading 的實際表現 vs 同期回測的理論表現。**

### 3.1 每週比對

```
每週日自動執行：
  1. 取過去 7 天的 paper NAV 序列
  2. 用同期的真實資料跑回測
  3. 計算兩者的相關性和偏差

  R² > 0.7    → 正常（paper 和 backtest 行為一致）
  R² 0.3-0.7  → 告警（可能有成本模型偏差）
  R² < 0.3    → P0 停止（系統行為和預期嚴重不符）
```

### 3.2 偏差分類

| 偏差類型 | 症狀 | 可能原因 |
|---------|------|---------|
| NAV 系統性高估 | Paper NAV > Backtest NAV | 滑價/成本低估 |
| NAV 系統性低估 | Paper NAV < Backtest NAV | 成本高估或多收了費用 |
| 持倉不一致 | 不同的股票被選入 | 資料差異或 PIT 問題 |
| 交易時間偏差 | 同樣的股票但不同天成交 | 再平衡時間或訂單延遲 |

---

## 4. 生產代碼防禦加固

### 4.1 消除所有 bare except

```python
# 不允許：
try:
    do_something()
except Exception:
    pass  # 靜默吞掉錯誤

# 必須：
try:
    do_something()
except SpecificError as e:
    logger.error("Context: %s", e)
    raise  # 或明確處理
```

掃描交易路徑中所有 `except Exception: pass` 和 `except: pass`，改為 fail-closed。

### 4.2 NaN/Inf 防火牆

在每個資料邊界加 NaN/Inf 檢查：

```
DataCatalog.get()   → 回傳前檢查 close 欄位無 NaN
on_bar()            → 回傳前檢查 weights 無 NaN
weights_to_orders() → 回傳前檢查 qty 和 price 無 NaN
apply_trades()      → 回傳前檢查 NAV 無 NaN
```

### 4.3 關鍵路徑 Type Guard

目前 Python 的動態型別允許任何值傳入。在關鍵函式入口加 runtime type check：

```python
def apply_trades(portfolio: Portfolio, trades: list[Trade]) -> Portfolio:
    if not isinstance(portfolio, Portfolio):
        raise TypeError(f"Expected Portfolio, got {type(portfolio)}")
    if not all(isinstance(t, Trade) for t in trades):
        raise TypeError("All items must be Trade instances")
```

---

## 5. 漸進式部署門檻

### 5.1 Paper Trading 畢業條件

| # | 條件 | 門檻 | 量測方式 |
|---|------|------|---------|
| G1 | 累計天數 | ≥ 30 個交易日 | 計算 paper NAV 序列長度 |
| G2 | 0 個 invariant violation | 0 次 TradingInvariantError | audit log |
| G3 | 0 個假告警 | 0 次 kill switch false positive | Discord 歷史 |
| G4 | NAV vs Backtest R² | ≥ 0.5 | 每週比對報告 |
| G5 | 煙霧測試通過率 | 100% | smoke_test/ 目錄 |
| G6 | 每日資料收集正常 | ≥ 95% 天數成功 | ops log |

**全部 6 項通過才能進入 live trading。** 任何一項不通過都回到 paper。

### 5.2 Live Trading 階梯式加碼

```
Level 0: Paper（目前）
  ↓ G1-G6 全通過
Level 1: Live 微額（初始資金 1%，約 10 萬）
  ↓ 連續 10 個交易日無 invariant violation
Level 2: Live 小額（初始資金 5%，約 50 萬）
  ↓ 連續 30 個交易日
Level 3: Live 正常（初始資金 50%）
  ↓ 連續 90 個交易日
Level 4: Live 全額
```

每個 Level 升級前必須重新通過 G1-G6。任何一次 TradingInvariantError → 降回上一級。

---

## 6. Heartbeat Kill Switch（報價超時保護）

現有的 `poll_prices_from_feed` 在 0 updates 時只 log warning，不阻止交易。

### 規則

```
盤中（09:00-13:30）：
  如果最後一次有效 tick 時間 > 5 分鐘前：
    → 暫停所有新訂單
    → P0 告警：「報價中斷超過 5 分鐘」
    → 報價恢復後自動解除（不需人工）

  如果最後一次有效 tick 時間 > 15 分鐘前：
    → 觸發 kill switch
    → P0 告警：「報價中斷超過 15 分鐘，停止交易」
    → 必須人工確認才能恢復
```

### 實作位置

在 `RealtimeRiskMonitor.on_price_update()` 中追蹤 `_last_tick_time`。
在 `_kill_switch_monitor` 迴圈中檢查距離上次 tick 的時間。

---

## 7. 網路斷線處理

### 規則

```
與券商 WebSocket 斷線：
  < 30 秒：自動重連（已有 SinopacBroker.reconnect_monitor）
  30 秒 ~ 5 分鐘：暫停新訂單，但不清倉
  > 5 分鐘：P0 告警，等待人工決定
  
重連後：
  1. 查詢券商當前持倉
  2. 與系統 Portfolio 比對
  3. 差異 < 1% → 自動恢復
  4. 差異 ≥ 1% → 人工確認後才恢復
```

---

## 8. 「靜默即 P0」監控原則

**系統停止產出 log/metric 本身就是最危險的狀態。**

### 規則

```
盤中（09:00-13:30）：
  如果連續 10 分鐘沒有任何 log 輸出 → P0 告警
  如果 heartbeat 超過 2 個週期（10 分鐘）未送出 → P0 告警
  如果 Prometheus metric 停止更新 → P0 告警
```

實作方式：外部 watchdog（cron job 或獨立 process）定期檢查 log 最後修改時間。

---

## 9. Replay Testing（歷史重播測試）

### 概念

選 3-5 個有代表性的交易日，錄製完整的 tick 資料和訂單流，作為固定的測試用例。每次系統變更後重播，確認輸出一致。

### 選擇的交易日

| 日期 | 事件 | 測試什麼 |
|------|------|---------|
| 除權息日 | 股價跳空 | 除權息後 NAV 計算、kill switch 不誤觸 |
| 月營收公布日 | 策略再平衡 | 訂單生成、風控、成交 |
| 大盤暴跌日 | 高波動 | Kill switch 正確觸發、漲跌停拒單 |
| 平靜日 | 無事件 | 系統不做多餘的事 |
| 伺服器重啟日 | 中斷恢復 | Portfolio 恢復、warmup、報價穩定 |

### 驗證方式

```
replay(recorded_ticks, recorded_orders) → actual_trades
assert actual_trades == expected_trades  # 逐筆比對
assert final_nav == expected_nav         # NAV 一致
assert 0 invariant violations            # 無異常
```

---

## 10. Paper Trading 品質要求

### 30 天不是隨便 30 天

Paper trading 的 30 天必須包含：

| 事件 | 最低次數 | 為什麼 |
|------|---------|--------|
| 月營收公布 + 再平衡 | ≥ 1 次 | 驗證完整的交易週期 |
| 伺服器重啟 | ≥ 2 次 | 驗證 warmup + 狀態恢復 |
| 大盤日跌幅 > 2% | ≥ 1 次 | 驗證 kill switch 行為 |
| 除權息日 | ≥ 1 次 | 驗證股價調整後不誤觸風控 |
| 週末/假日 | 包含 | 驗證非交易日的排程邏輯 |

如果 30 天內沒有大盤暴跌日，延長 paper trading 直到遇到為止。

---

## 11. 實施順序

| 階段 | 內容 | 工時估計 | 前置 |
|------|------|---------|------|
| **AL-1** | TradingInvariantError + Portfolio invariant (I1-I5) | 小 | 無 |
| **AL-2** | Order invariant (I6-I8) + Fill invariant (I9-I11) | 小 | AL-1 |
| **AL-3** | Pipeline invariant (I12-I14) + NaN 防火牆 | 小 | AL-1 |
| **AL-4** | Heartbeat kill switch + 網路斷線處理 | 小 | AL-1 |
| **AL-5** | bare except 清理 + type guard | 小 | 無 |
| **AL-6** | 每日煙霧測試（S1-S7） | 中 | AL-1~3 |
| **AL-7** | Paper vs Backtest 一致性比對 | 中 | AL-6 |
| **AL-8** | Replay testing（3-5 個歷史交易日） | 中 | AL-6 |
| **AL-9** | 「靜默即 P0」外部 watchdog | 小 | 無 |
| **AL-10** | 畢業條件自動化 + 階梯加碼機制 | 小 | AL-6~7 |

**AL-1 到 AL-5 應立即實作** — 每個都是幾十行代碼，加在現有函式裡，不需要新模組。

---

## 12. 成功標準

Phase AL 完成的定義：

- [ ] 交易路徑上 14 個 invariant 全部在生產代碼中
- [ ] Heartbeat kill switch：報價中斷 > 5 分鐘自動暫停
- [ ] 煙霧測試每日盤前自動執行
- [ ] Paper vs Backtest R² ≥ 0.5 連續 4 週
- [ ] 交易路徑中 0 個 bare `except: pass`
- [ ] 3-5 個歷史交易日的 replay test 通過
- [ ] 「靜默即 P0」watchdog 運行中
- [ ] Paper trading 畢業條件（§5.1 G1-G6）全部自動化
- [ ] 30+ 天 paper trading，包含至少 1 次大盤暴跌日，0 invariant violation

**不滿足以上全部條件，不得進入 live trading。**

---

## 13. 與 Knight Capital 教訓的對照

| Knight Capital 的失敗 | 我們的防護 |
|----------------------|-----------|
| 舊測試代碼在生產環境觸發 | Paper/live mode 分離 + `enable_kill_switch_liquidation` config |
| 45 分鐘內 $440M 損失 | 每分鐘 10 筆訂單限速 + 5% 日回撤 kill switch |
| 沒有即時監控 | Prometheus metrics + Discord P0 告警 |
| 沒有自動停止機制 | 3 層 kill switch（file + heartbeat + drawdown） |
| 部署後沒有驗證 | 啟動冷卻 120 秒 + 每日煙霧測試 |

**Knight Capital 的核心教訓不是「他們的代碼有 bug」，而是「bug 發生後沒有足夠快地停止系統」。** Phase AL 的目標是確保：即使有 bug，損失在系統自動反應之前被控制在可接受範圍內。

---

## 14. 審批（2026-04-01）

### 判定：方向完全正確，是 live 前最重要的工作。3 個事實修正 + 2 個過度設計 + 1 個遺漏。

---

### 做得好的部分

1. **§1 Runtime Invariant** — 整份計畫最有價值。14 個 invariant 各幾行代碼，成本極低，直接防止真金白銀損失。比再寫 100 個 mock 測試有用
2. **§5 漸進式部署** — Level 0→4 階梯合理，每級重新驗證 G1-G6 正確
3. **§13 Knight Capital 對照** — 「bug 一定會有，關鍵是多快停止」思路完全正確
4. **核心原則** — 三條都對：測試不能只靠 mock、安全必須 runtime、異常必須 fail-closed

---

### 事實修正

**1. I4 NAV 容差 1 元太緊**

Decimal 運算 + 整張交易 rounding 可產生超過 1 元誤差。1000 萬 NAV 裡 1 元 = 0.00001%。

**修正**：改為 NAV 的 0.01%（1000 萬 → 容差 1000 元），或固定 100 元。

**2. I5 單一持倉 20% 不該 raise**

策略不下單不代表市場不動。一支股票漲 100%，權重 6% → 12% — 這不是 bug，是市場。Raise TradingInvariantError 會在正常市場行為下停止交易。

**修正**：20% → warning + 觸發下次強制再平衡。30% 才 raise。

**3. §3 Paper vs Backtest R² 用 7 天無統計意義**

7 個數據點的 R² 方差極大，power 接近 0。

**修正**：改為 30 天滾動比對。或不用 R²，改用 daily return sign agreement rate ≥ 70%。

---

### 過度設計

**4. §4.3 Type Guard — 移除**

`isinstance(portfolio, Portfolio)` 防禦過度。mypy strict 已在 CI 抓型別錯誤。runtime type check 增加每次交易的開銷和維護成本（改 class hierarchy 要改 guard）。刪除 §4.3，靠 mypy + invariant 就夠。

**5. §9 Replay Testing — 降為 P3 或刪除**

概念好但需要先建「tick 錄製基礎設施」，這本身一個 Phase 的工作量。paper trading 30 天本身就是真實市場的 replay，不需要另外錄。Phase AL 不做 replay。

---

### 遺漏

**6. 缺流動性風險檢查**

I6-I8 檢查訂單本身，但沒檢查「這筆訂單佔日成交量多少」。日成交量 100 張的股票下 50 張 = 佔日量 50%，滑價嚴重。

**新增 I15**：`order_qty / avg_daily_volume < 0.05`（不超過日均量 5%）。

---

### 修正後的實施優先序

| 階段 | 優先 | 改動 |
|:----:|:----:|------|
| AL-1 | P0 | I1-I4（I4 容差改 0.01% NAV），I5 改為 warning |
| AL-2 | P0 | I6-I8 + **I15 流動性** |
| AL-3 | P0 | I9-I11, I12-I14 + NaN 防火牆 |
| AL-4 | P0 | Heartbeat kill switch |
| AL-5 | P1 | bare except 清理（保留合理的 optional degradation） |
| AL-6 | P1 | 每日煙霧測試 |
| AL-7 | P2 | Paper vs Backtest（改 30 天 + sign agreement） |
| AL-8 | — | ~~Replay testing~~ → **刪除**，paper trading 30 天已涵蓋 |
| AL-9 | P2 | 靜默即 P0（用 Discord watchdog，不用 Prometheus） |
| AL-10 | P2 | 畢業條件自動化 |

**AL-1 到 AL-4 是 live 前的硬門檻。**
