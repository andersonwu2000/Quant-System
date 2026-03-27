# Phase R：程式碼庫整頓 + 實用性提升

> 狀態：🟡 R1-R6 + R10 完成，R7-R9 進行中
> 目標：解決架構審查缺點 + 將系統從「能跑回測」推進到「能驗證策略」

---

## R1：刪除 src_v1_backup ✅ 完成

`apps/web/src_v1_backup/` 不應存在於 repo 中。Git 本身就是版本控制，commit `d748f7b` 保留了完整的 rename 歷史，隨時可恢復。

**動作**：`git rm -r apps/web/src_v1_backup/`

---

## R2：Phase 進度統一追蹤 ✅ 完成

17 個 Phase（A~Q）散落在獨立 markdown，沒有全局進度總覽。今天就發現 4 份文件狀態過時。

**動作**：在 `docs/PHASE_TRACKER.md` 建立一頁式進度表，格式：

```
| Phase | 名稱 | 狀態 | 通過率 | 備註 |
```

所有 Phase 的詳細內容仍保留在各自的 plan 文件，tracker 只做索引。

---

## R3：.env.example 完善 ✅ 完成

目前缺少完整的環境變數範例。新開發者（包括未來的自己）無法快速上手。

**動作**：檢查 `src/core/config.py` 的所有 `QUANT_` 前綴設定，確保 `.env.example` 涵蓋全部，並加上註解。

---

## R4：策略驗證狀態誠實標記 ✅ 完成

系統建了完整的 Paper Trading 基礎設施，但策略只通過 4/7 驗證門檻（實驗 #15）。應在 RESEARCH_SUMMARY.md 明確標記「回測邊緣、尚未實盤驗證」。

**動作**：更新 `docs/research/RESEARCH_SUMMARY.md`，加入誠實的驗證狀態段落。

---

## R5：Auto-Alpha 標記為實驗性 ✅ 完成

Phase P 投入大量工程但產出尚未驗證。應標記為實驗性，避免誤導。

**動作**：在 `docs/plans/phase-p-auto-research.md` 加入實驗性警告。

---

---

# 第二部分：實用性提升

## 現狀診斷

**專業性中上，實用性低。** 系統有 14 種優化器、83 個因子、117 個 API endpoint，但：

- 0 天 Paper Trading 實績
- 唯一深入驗證的策略（revenue_momentum）只過 3/7 門檻
- 其他 12 個策略的實際表現未知
- config.py 的 `data_source` 包含 `"fubon"`/`"twse"` 選項但無對應實作
- Web v2 有骨架但功能深度不夠

**核心矛盾**：在策略尚未驗證的情況下，花了大量時間建基礎設施。

---

## R6：清理無效的 config 選項 ✅ 完成

`src/core/config.py` 的 `data_source` 欄位包含 `"fubon"` 和 `"twse"`，但 `src/data/sources/` 沒有對應實作。

**動作**：
- `data_source: Literal["yahoo", "finmind"]`（移除不存在的選項）
- 同步更新 `.env.example`

**難度**：低（5 分鐘）

---

## R7：聚焦 revenue_momentum → Paper Trading 驗證路徑 🟡 進行中

這是整個系統實用性的關鍵路徑。目標：**走通一條從回測到實盤的完整閉環。**

```
revenue_momentum
    → Paper Trading 30 天（Phase N 剩餘項目）
    → 收集真實滑點/執行數據
    → 回測 vs 實盤 R² 比對
    → 根據實盤數據調整參數
    → 如果 R² > 0.8 且有正報酬 → 小額實盤
```

### R7.1 完成 Phase N 剩餘項目

| 項目 | 內容 | 前置 |
|------|------|------|
| N1.2 | 即時模式適配：APScheduler 每月 11 日觸發 `on_bar()` | 無 |
| N2 | 月營收自動更新：每月 11 日 08:30 下載 FinMind parquet | 無 |
| N3 | 通知：選股/下單/成交/Kill Switch → Discord/Telegram | 無 |
| N4 | 對帳：每日 NAV snapshot + 回測 vs 實盤 R² | N1.2 |
| N5 | CA 憑證整合：Shioaji 完整循環 | CA 申請 |

### R7.2 30 天 Paper Trading 驗證標準

| 指標 | 門檻 | 為什麼 |
|------|------|--------|
| 回測 vs 實盤報酬 R² | > 0.8 | 確認回測引擎可信 |
| 實際滑點 | < 10 bps | 確認流動性假設正確 |
| 系統穩定性 | 0 次未處理異常 | 生產級可靠 |
| 策略執行率 | 100% | 每月按時選股+下單 |

### R7.3 實盤決策矩陣

| Paper Trading 結果 | 下一步 |
|-------------------|--------|
| R² > 0.8 且月報酬 > 0 | 小額實盤（50 萬） |
| R² > 0.8 但月報酬 < 0 | 繼續觀察 3 個月 |
| R² < 0.8 | 回測引擎有問題，先修引擎 |
| 系統不穩定 | 先修基礎設施 |

**難度**：中高（需要持續 30 天）

---

## R8：停止橫向擴展 🔵 持續原則

在 R7 驗證完成之前，**不新增**：
- 新策略（13 個已經夠多）
- 新因子（83 個已經夠多）
- 新優化器（14 個已經夠多）
- 新 API endpoint（117 個已經夠多）
- 新前端頁面

允許的工作：
- Bug fix
- 提升現有功能的深度（例如 Web 頁面從骨架到可用）
- Phase N（Paper Trading 路徑上的必要工作）
- 數據品質改善

**理由**：每個新功能都是維護負擔。在策略未驗證之前，更多功能 = 更多浪費。

---

## R9：數據品質基礎 🔵 待執行

回測結果的可信度取決於數據品質，但目前沒有監控機制。

### R9.1 數據完整性檢查

每次載入 parquet 時驗證：
- 缺值率 < 5%（否則警告）
- 無未來數據洩漏（日期嚴格遞增）
- 價格合理範圍（無負數、無極端值）

### R9.2 營收公布日追蹤

目前用固定 40 天延遲，但實際公布日因公司而異。

**動作**：記錄每家公司的實際營收公布日期，用於更精確的 look-ahead 控制。

**難度**：中

---

## R10：自動化管線設計缺陷修正 ✅ 完成

### R10.1 營收更新 → 再平衡因果鏈（最嚴重）

**問題**：`monthly_revenue_update`（08:30）和 `monthly_revenue_rebalance`（09:05）是獨立 cron，靠 35 分鐘時間差保證順序。如果下載失敗或超時，rebalance 會用舊數據選股且不自知。

**修正**：update 成功後直接觸發 rebalance，失敗則跳過並告警。移除 rebalance 的獨立 cron。

### R10.2 硬編碼日期 `--start 2024-01-01`

**問題**：`jobs.py:155` 寫死起始日期，不會自動擴展。

**修正**：改為動態計算（當前日期 - 2 年）。

### R10.3 三條路徑互斥無程式碼保證

**問題**：註解說三條路徑不可同時運行，但沒有 lock。併發寫入同一個 Portfolio 會出問題。

**修正**：加入 `asyncio.Lock`，任一路徑執行中時其他路徑等待或跳過。

### R10.4 General Rebalance 空 portfolio fallback

**問題**：`execute_rebalance` 用 `portfolio.positions.keys()` 當 universe，portfolio 為空時策略拿不到數據。`monthly_revenue_rebalance` 有 fallback 但 general 沒有。

**修正**：統一 fallback 邏輯到共用函式。

### R10.5 執行結果持久化

**問題**：trade 結果只有 log，系統重啟後歷史紀錄消失。

**修正**：每次 rebalance 後存 trade log 到 `data/paper_trading/trades/{date}.json`。

### R10.6 失敗重試 + 告警升級

**問題**：所有 job exception 靜默吞掉，不重試、不升級告警。

**修正**：update 失敗 → 重試 1 次 → 失敗則發通知 + 跳過 rebalance。

---

## 不在此 Phase 處理

| 項目 | 原因 |
|------|------|
| Commit 紀律 | 流程問題，靠意識改善 |
| Mobile app | 使用者明確排除 |
| Auto-Alpha 深入驗證 | 等 R7 走通後再評估 |
| 多策略組合優化 | 先把一個策略驗證到底 |

---

## 執行順序

```
R6（清理 config）✅
  → R10（管線缺陷修正）← 現在
    → R7.1（完成 Phase N 剩餘）
      → R7.2（30 天 Paper Trading）
        → R7.3（根據結果決定下一步）

R8（持續原則，立即生效）
R9（數據品質，與 R7 並行）
```

**成功標準**：30 天後能回答「revenue_momentum 策略在實盤是否有效」這個問題。這是整個系統從「玩具」變成「工具」的轉折點。
