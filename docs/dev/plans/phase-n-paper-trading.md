# Phase N：Paper Trading 準備 + 30 天驗證

> 狀態：🟡 N1-N3 代碼已完成，N4 部分完成，N5 等 CA 憑證
> 前置：Phase M（下行保護 + 因子驗證）✅、CA 憑證 ⏳
> 目標：將 composite_b0% 策略從回測環境遷移到即時 Paper Trading，驗證 30 天

---

## 背景

策略研究完成：
- rev_yoy ICIR 0.674, t=16.1, p<0.000001（13 次實驗）
- composite_b0% StrategyValidator 10/13（OOS -3.7%）
- 引擎 676 支 × 7Y 55 秒

**剩餘風險在實盤端**：Quantopian 888 策略回測 vs 實盤 R² < 0.025。

---

## N1：策略整合到主系統

### N1.1 revenue_momentum_hedged 正式化 ✅

已完成。`strategies/revenue_momentum_hedged.py` 已建立並 commit。

```
strategies/revenue_momentum_hedged.py
- 繼承 Strategy ABC
- 包裝 RevenueMomentumStrategy + 複合空頭偵測器（MA200 OR vol_spike）
- 預設：bear_scale=0.0, sideways_scale=0.3
- 月度 cache（同 revenue_momentum）
```

### N1.2 即時模式適配 ✅

已完成。`src/scheduler/__init__.py` 註冊排程 + `src/scheduler/jobs.py` 實作 `monthly_revenue_rebalance()`。

| 問題 | 解法 | 狀態 |
|------|------|:----:|
| 誰觸發 `on_bar()`？ | APScheduler 每月 11 日 09:05 | ✅ |
| Context 即時數據？ | YahooFeed + FinMind 營收 parquet | ✅ |
| 市場環境偵測？ | 0050.TW Yahoo 行情 | ✅ |
| 權重 → 訂單？ | `weights_to_orders()` + ExecutionService | ✅ |

### N1.3 整股下單 ✅

Config: `tw_lot_size` = 1000, `weights_to_orders()` 已支援 lot_size + ADV cap。

---

## N2：月營收自動更新 ✅

已完成。`src/scheduler/jobs.py` 的 `monthly_revenue_update()` + `scripts/download_finmind_data.py`。

| 項目 | 說明 | 狀態 |
|------|------|:----:|
| 排程 | APScheduler 每月 11 日 08:30 觸發 | ✅ |
| 下載 | `download_finmind_data.py` | ✅ |
| 觸發 | 下載完成後 09:05 觸發再平衡 | ✅ |

---

## N3：通知 + 監控 ✅

已完成。`src/notifications/` 有 Discord/LINE/Telegram 完整實作 + `factory.py` 自動偵測。

| 事件 | 通知內容 | 狀態 |
|------|---------|:----:|
| 月度選股 | 新標的 + 目標權重 | ✅ |
| 下單 | 標的、方向、數量、價格 | ✅ |
| 成交 | 成交價、滑點 | ✅ |
| Kill Switch | 原因、NAV、drawdown | ✅ |
| 連線異常 | 斷線/重連 | ✅ |

### 每日快照

每日 13:35 記錄 NAV、持倉、P&L → `data/paper_trading/snapshots/{date}.json`（待 N4 對帳腳本整合）

---

## N4：對帳 + 績效追蹤

### 每日對帳

比對策略目標 vs Shioaji 實際持倉，偏差 > 5% 告警。

### 回測 vs 實盤比對

同期回測結果 vs Paper Trading，量化：
- 報酬 R²（目標 > 0.8）
- 平均滑點（目標 < 10 bps）

### 30 天驗證標準

| 指標 | 門檻 |
|------|------|
| 回測 vs 實盤 R² | > 0.8 |
| 實際滑點 | < 10 bps |
| 系統穩定性 | 0 次未處理異常 |
| 連線成功率 | > 99% |
| 策略執行率 | 100%（每月按時選股） |

---

## N5：CA 憑證整合

1. 申請 CA → 下載 .pfx
2. 設定 `.env`：`QUANT_SINOPAC_CA_PATH` + `QUANT_SINOPAC_CA_PASSWORD`
3. 測試 deal callback
4. 整合 OMS → WebSocket 通知
5. 完整循環：登入 → 選股 → 下單 → 回報 → 對帳 → 通知

---

## 執行順序

```
N1（策略整合）+ N2（營收更新）+ N3（通知）←── 不需 CA，可先做
                    │
N5（CA 憑證）──→ 完整循環測試 ──→ N4（對帳）
                    │
              30 天 Paper Trading
```

---

## 關鍵檔案

| 檔案 | 變更 | 階段 |
|------|------|:----:|
| `strategies/revenue_momentum_hedged.py` | **新檔案** | N1 |
| `src/strategy/registry.py` | +1 策略 | N1 |
| `src/scheduler/jobs.py` | 月度排程 + 營收更新 | N1/N2 |
| `scripts/download_finmind_data.py` | 增量更新 | N2 |
| `src/notifications/` | 交易事件通知 | N3 |
| `scripts/daily_reconciliation.py` | **新檔案** | N4 |
