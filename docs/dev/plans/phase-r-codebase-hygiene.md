# Phase R：程式碼庫整頓

> 狀態：🟢 R1-R5 已完成
> 目標：解決架構審查發現的非 Mobile 相關缺點，降低維護成本

---

## R1：刪除 src_v1_backup ✅ 完成

`apps/web/src_v1_backup/` 不應存在於 repo 中。Git 本身就是版本控制，commit `d748f7b` 保留了完整的 rename 歷史，隨時可恢復。

**動作**：`git rm -r apps/web/src_v1_backup/`

---

## R2：Phase 進度統一追蹤 ✅ 完成

17 個 Phase（A~Q）散落在獨立 markdown，沒有全局進度總覽。今天就發現 4 份文件狀態過時。

**動作**：在 `docs/dev/PHASE_TRACKER.md` 建立一頁式進度表，格式：

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

**動作**：更新 `docs/dev/test/RESEARCH_SUMMARY.md`，加入誠實的驗證狀態段落。

---

## R5：Auto-Alpha 標記為實驗性 ✅ 完成

Phase P 投入大量工程但產出尚未驗證。應標記為實驗性，避免誤導。

**動作**：在 `docs/dev/plans/phase-p-auto-research.md` 加入實驗性警告。

---

## 不在此 Phase 處理

| 項目 | 原因 |
|------|------|
| Commit 紀律 | 流程問題，靠意識改善，不需要程式碼變更 |
| 複雜度超過使用規模 | 已建好的功能不值得拆除，但未來應克制新增 |
| Paper Trading 30 天驗證 | 需要時間執行，不是一次性修改 |
| Mobile app 凍結 | 使用者明確排除 |
