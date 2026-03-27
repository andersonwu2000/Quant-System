# Paper Trading 啟動報告

**日期**: 2026-03-27 08:00
**模式**: paper (Shioaji simulation)

---

## 系統狀態

| 項目 | 狀態 |
|------|------|
| API Server | running (port 8000) |
| Shioaji | connected (simulation) |
| Mode | paper |
| NAV | $10,000,000 |
| Strategy | revenue_momentum_hedged |

## 選股結果

策略從 884 支台股中選出 8 支（全 universe 掃描，非限 TW50）：

| Stock | Weight | Description |
|-------|--------|-------------|
| 1316.TW | 10% | 上曜建設 |
| 1519.TW | 10% | 華城電機 |
| 1514.TW | 10% | 亞力電機 |
| 1312.TW | 10% | 國喬石化 |
| 1587.TW | 10% | 吉泰藥品 |
| 1342.TW | 10% | 八貫企業 |
| 1560.TW | 10% | 中砂精密 |
| 1590.TW | 10% | 亞德客-KY |
| Cash | 20% | — |

## 訂單狀態

- 8 筆買單已提交至 Shioaji 佇列
- 等待 09:00 開盤撮合
- 0 筆被風控拒絕

## Bug 修復（啟動前）

1. **timezone 比較錯誤** (`strategies/revenue_momentum.py:95`)
   - `_get_revenue_at` 的 `as_of` 在 paper mode 是 tz-aware，revenue date 是 tz-naive
   - 修正：`as_of.tz_localize(None)` 移除 timezone
   - 影響：paper mode 一律回空權重（策略無法運行）

2. **Shioaji volume 數據不可靠**
   - simulation mode kbar volume 是真實值的 ~1/500
   - 修正：以 Yahoo→Shioaji 邊界比例還原 volume
   - 影響：volume filter 幾乎擋掉所有股票

## Auto-Alpha 研究

- API 版 auto-alpha cycle: 已完成，無新因子
- 腳本版 (3 rounds): 執行中
  - Round 1: `rev_seasonal_deviation` — IC 評估中（879 stocks）

## 注意事項

- Shioaji **simulation mode** 不代表真實撮合，價格/成交量可能與實際不同
- 2026 年 volume 數據是估算值（比例還原），非真實值
- 開盤後需確認訂單是否實際成交
- 營收數據最新到 2026-01（二月公布），下次更新約 2026-04-10
