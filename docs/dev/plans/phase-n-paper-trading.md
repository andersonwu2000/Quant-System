# Phase N：Paper Trading → 實盤準備

> 狀態：🔵 待執行
> 前置：Phase L（策略回測驗證通過 §L4 標準）
> 目標：策略驗證通過後，進入 Paper Trading 完整循環，驗證 execution 層

---

## 背景

Phase L 策略回測通過驗證標準（CAGR > 15%, Sharpe > 0.7, PBO < 50%）後，需在模擬環境中驗證：
- 排程觸發 → 因子計算 → 訊號生成 → 下單 → 回報 → 對帳 → 通知
- Shioaji API 模擬模式已驗證（2026-03-26），但完整循環尚未跑通

---

## N1：CA 憑證申請 + Shioaji 完整模式

### N1.1 CA 憑證

- 向永豐金申請正式 CA 憑證
- 設定至 `.env`：`QUANT_SHIOAJI_CA_PATH`, `QUANT_SHIOAJI_CA_PASSWORD`
- 啟用：deal callback（成交回報）、tick streaming（逐筆行情）

### N1.2 Shioaji 完整模式測試

| 功能 | 模擬已驗證 | CA 後新增 |
|------|:---------:|:--------:|
| 登入 | ✅ | — |
| 下單（ROD/IOC） | ✅ | — |
| 帳務查詢 | ✅ | — |
| Scanner | ✅ | — |
| Deal callback | ❌ | ✅ |
| Tick streaming | ❌ | ✅ |
| 改單/刪單 | ✅ | — |

---

## N2：Paper Trading 完整循環

### N2.1 排程配置

```python
# 月度策略排程（營收公布後）
# 每月 11 日 08:50（盤前）觸發
schedule: "50 8 11 * *"

# 流程：
# 1. 讀取最新月營收（data/fundamental/）
# 2. 計算篩選條件
# 3. 產生目標持倉
# 4. 與現有持倉比對 → 產生交易清單
# 5. 透過 Shioaji 下單（Paper mode）
# 6. 等待成交回報
# 7. 更新 Portfolio
# 8. 發送通知（Discord/LINE）
```

### N2.2 EOD 對帳

每日收盤後：
- 比對 Shioaji 帳務 vs 系統 Portfolio
- 差異 > 1% 發送警告
- 記錄日誌到 `data/paper_trading_log/`

### N2.3 風控整合

- RealtimeRiskMonitor 已有 2%/3%/5% 分級
- Kill Switch 冷靜期恢復機制（5 天冷靜 → 50% → 100%）
- 月度 DD > 10% → 暫停策略 1 個月

---

## N3：Paper Trading 驗證標準

| 指標 | 門檻 | 驗證期間 |
|------|------|---------|
| 系統穩定性 | 連續 30 天無 crash | 1 個月 |
| 排程觸發成功率 | > 95% | 1 個月 |
| 下單成功率 | > 99% | 1 個月 |
| EOD 對帳一致性 | 差異 < 0.1% | 1 個月 |
| Paper P&L vs 回測 | 方向一致 | 1 個月 |
| 通知及時性 | 延遲 < 5 分鐘 | 1 個月 |

---

## N4：實盤前 Checklist

全部通過後才可進入實盤：

- [ ] Phase L 回測驗證通過（§L4 全部指標）
- [ ] Paper Trading 連續 30 天穩定
- [ ] EOD 對帳一致
- [ ] 風控機制在 Paper Trading 中被正確觸發過至少一次
- [ ] 交易成本估算 vs 實際（Paper）偏差 < 20%
- [ ] 使用者確認策略風險並簽署（人工確認）

---

## 執行順序

```
L4 回測通過 → N1（CA 憑證）→ N2（Paper Trading 循環）→ N3（驗證 30 天）→ N4（Checklist）
                                                                              ↓
                                                                     實盤（需使用者明確授權）
```
