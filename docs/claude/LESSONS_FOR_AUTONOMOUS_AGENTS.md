# Lessons for Autonomous Agent Systems

> 從 Quant-System 的 autoresearch 開發中提煉的經驗。
> 適用於任何讓 AI agent 自主迭代代碼的系統。
> 每一條都來自至少一個真實事故，不是理論。

---

## 1. 隔離靠物理機制，不靠指令

**事故：** prompt 裡寫「不要改 evaluate.py」，agent 照改。hooks 攔截寫入，agent 用 `bash -c "cat evaluate.py"` 繞過讀取限制。`git reset --hard` 摧毀了 3 次未 commit 的修改。

**原則：**
- Prompt 限制 = 建議，不是執行
- Hooks = 比 prompt 好，但能被繞過（Bash 可跑任何命令）
- OS 權限 = 防寫不防讀
- Docker volume mount = 唯一的硬隔離（未掛載的就不存在）

**建議架構：**
```
Container（agent 跑在這裡）
├── /work/       (rw)  — agent 唯一可改的目錄
├── /data/       (ro)  — 輸入數據
├── /evaluator   (ro)  — 評估引擎（COPY 進去，不是 mount）
└── 無 src/、無 .git、無 config
```

---

## 2. 評估標準和 agent 必須物理分離

**事故：** evaluate.py 在 host 上跑，agent 可以讀源碼知道所有閾值和 OOS 邏輯。L5 的「只輸出 pass/fail」設計被 5 個通道繞過（pending marker、日期輸出、Validator 結果、factor_returns、源碼本身）。

**原則：**
- 評估引擎 COPY 進容器，不是 mount（agent 可以讀 mount 的檔案）
- 評估結果只回傳最少資訊（pass/fail + score，不帶中間值）
- 任何輸出到 stdout 的東西都假設 agent 會讀到
- 敏感數據（OOS 結果、PBO）存在 agent 不可見的路徑

**資訊洩漏 checklist：**
```
□ agent 能看到 OOS 的時間範圍嗎？
□ agent 能從 failure message 推斷 OOS 的方向/大小嗎？
□ agent 能讀到中間計算結果的檔案嗎？
□ agent 能讀到評估引擎的源碼嗎？
□ agent 累積多次 pass/fail 能學到什麼？
```

---

## 3. Agent 的 git 操作會摧毀你的修改

**事故：** agent 在主 repo 跑 `git reset --hard HEAD~1` 來回滾失敗實驗，同時摧毀了所有未 commit 的修改。發生 3 次，每次都要重新修改 4+ 個檔案。

**原則：**
- Agent 的 git repo 和主 repo 必須分開（用 work/ 子目錄 + 獨立 .git）
- 如果共用 repo，**永遠不要用 `git reset --hard`**。改用：
  ```bash
  git checkout HEAD~1 -- factor.py && git reset --soft HEAD~1
  ```
- 任何非 agent 的代碼修改**必須立即 commit**，不要累積
- 在 agent 運行期間修改代碼 = 高風險操作

---

## 4. 數據品質問題會在最意想不到的地方爆炸

**事故：** 895 支股票中 133 支有 close=0（下市/低流動性）。`pct_change()` 對 close=0 產生 inf → 汙染 56/75 個 factor returns → PBO 矩陣全壞 → PBO=1.0（看起來像「所有因子都過擬合」，其實是數據汙染）。

**原則：**
- 在**每個數據載入點**加 guard，不是只在一處
  - 我們在 vectorized.py 修了，但 evaluate.py、engine.py、validator.py 也有同樣的 `pct_change()` → 每處都要加
- 異常值的正確處理是 **NaN（排除）**，不是 0（假裝正常）或 inf（傳播汙染）
- 加不變量測試：`assert not np.isinf(returns).any()`
- 數據品質問題的症狀往往看起來像方法論問題（「PBO=1.0 所以全部過擬合」），要先查數據再查方法

---

## 5. 「可以開始了嗎」要問 5 次

**事故：** 每次說「可以開始研究」，使用者再問一次就發現新問題。第 1 次：Docker image 沒重建。第 2 次：factor.py 是舊實驗不是 baseline。第 3 次：factor_returns 路徑不對。第 4 次：OOS 洩漏沒封堵。第 5 次：evaluate.py 8 個問題。

**原則：**
- 寫一份 **啟動前 checklist**，每次啟動前逐項勾
- Checklist 不是一次寫好的 — 每次發現新問題就加一條
- Smoke test 不是可選的 — 必須跑一次完整流程確認端到端通
- 「我覺得沒問題」 ≠ 驗證過沒問題

---

## 6. 方法論錯誤比代碼 bug 更危險

**事故：** PBO 實作了 3 次，每次代碼審計都說「正確」，但方法論定義是錯的（N 代表什麼）。60+ 個代碼 bug 都在數小時內被找到修復，但 PBO 的方法論錯誤存活了多個版本。

**原則：**
- 實作學術方法前**讀原論文**，不是 blog/SO/ChatGPT 摘要
- 至少交叉比對 2 個獨立來源
- 代碼審計不夠 — 代碼可以「正確地實作錯誤的東西」
- 用已知範例驗證（純噪音 → PBO ≈ 1.0，單一策略 → DSR ≈ raw Sharpe）

---

## 7. Holdout 數據會被 adaptive query 降解

**事故：** 233 次因子實驗，每次 L5 回傳 pass/fail = 233 bits 資訊洩漏。Dwork et al. (2015) 的安全 budget 是 ~4 次。超出 62 倍。

**原則：**
- 固定的 holdout 數據集**不適合**大量自主實驗
- 每次查詢 holdout 都會降解它的有效性
- 緩解方案：
  - Thresholdout（加噪音到回饋）— 我們已實作
  - Rolling holdout（隨時間移動）— 我們已實作
  - Fresh data（paper trading / live）— 最終解法
- 追蹤查詢次數，設 budget 上限

---

## 8. 多個系統文件的一致性是最大的維護負擔

**事故：** 部署邏輯在 3 個地方（evaluate.py、watchdog.py、auto_alpha.py），改了一處忘了另外兩處。check name 改了（walkforward → temporal_consistency），但 4 個 caller 只改了 2 個。

**原則：**
- 邏輯只定義在一處，其他地方引用
- 如果無法避免重複（如 Docker COPY 的檔案 vs host 的檔案），寫 checklist 確保同步
- 改名/重構後 `grep -rn "舊名"` 確認全部替換
- 常量（門檻值、check 名稱）用 config/常量定義，不硬編碼

---

## 9. Docker image 是快照，不會自動更新

**事故：** 改了 evaluate.py 和 watchdog.py（host 上），但 Docker 容器裡還是舊版。因為這些檔案是 COPY 進去的，不是 volume mount。導致容器跑的是 2 小時前的代碼。

**原則：**
- COPY 的檔案修改後必須 `docker compose build`
- Volume mount 的檔案會自動同步
- 每次修改後驗證容器內版本：`docker exec container grep -c "特徵字串" /app/file.py`
- 考慮用 volume mount 開發、COPY 部署（兩階段）

---

## 10. 防禦性設計的優先級

從這個專案學到的防禦性設計優先級，從最有效到最無效：

```
1. 物理隔離（Docker volume 未掛載 → 不存在）      — 100% 有效
2. OS 權限（chmod -w → 不可寫）                    — 防寫有效，不防讀
3. 加密/混淆（評估結果加噪音）                      — 降低洩漏但不消除
4. Hooks（PreToolUse 攔截）                         — 可被 Bash 繞過
5. Prompt 指令（「不要改這個檔案」）                 — 隨時可被無視
6. 程式碼註釋（# READ ONLY）                        — 零防護力
```

**通則：** 每上一層，防護力降 50%。如果某個安全要求很重要，用第 1-2 層，不要只靠 4-6 層。

---

## 11. 實用工具和模式

### 自主 agent 的 3 檔案架構（Karpathy autoresearch）

```
evaluator.py   — 固定，agent 不可改（COPY 進容器）
solution.py    — agent 唯一可改的檔案
protocol.md    — 研究協議（agent 只讀）
results.tsv    — 實驗記錄（agent 可追加）
```

這個模式的核心洞察：**把「做什麼」和「怎麼評估」分離**。Agent 只控制前者。

### Thresholdout（防 adaptive query 降解）

```python
# 不是確定性的 pass/fail，而是加噪音
noise = np.random.laplace(0, scale)
passed = (metric > threshold + noise)
```

每次查詢洩漏 < 1 bit（而非 1 bit），安全 budget 從 O(1) 升到 O(n)。

### 不變量測試（防數據汙染）

```python
def test_no_inf_in_returns():
    returns = compute_returns(price_matrix)
    assert not np.isinf(returns.values).any()

def test_no_zero_close():
    prices = load_prices()
    assert (prices > 0).all().all()
```

在 CI 跑，每次 commit 驗證。比修完 bug 後才發現便宜 100 倍。
