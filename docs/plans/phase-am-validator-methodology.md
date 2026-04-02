# Phase AM：Validator 方法論改善 + 架構整理

> 建立日期：2026-04-02
> 狀態：**完成**（P0 + P2 + P2b 全部完成，P1 架構整理移至 Phase AN，P3 待前提條件）
> 優先級：高 — 直接影響因子部署品質和系統可維護性

---

## 0. 動機

2026-04-01~04-02 期間，透過外部 code review 和方法論審查，發現 Validator 和 evaluate.py 存在多個設計問題：

- DSR 的 N 定義和 PBO 不一致（262 vs n_independent），導致過度懲罰
- vs_ew_universe 的 EW benchmark 有日頻再平衡溢價 + 倖存者偏差
- sharpe / bootstrap_p 和 DSR 拒絕域重疊 >90%，過度保守
- L5 和 Validator 共用同一段 OOS 數據，構成 double dipping
- IC 沒有行業中性化，行業 beta 污染因子信號
- L3 的固定年份邊界和 0.50 correlation 門檻系統性刪除 value / mean reversion 因子

修正後 revenue_acceleration 成為系統第一個通過全部 Hard Gate 的因子（7/7）。

---

## 1. 已完成項目（2026-04-02）

### 1.1 Validator 架構改善

| 項目 | 修改前 | 修改後 |
|------|--------|--------|
| DSR N | 262（全部實驗） | n_independent（聚類後，和 PBO 統一） |
| sharpe | Hard | **Soft** |
| bootstrap_p | Hard | **Soft** |
| vs_ew_universe | Hard + 日頻再平衡 | **Soft** + 月頻再平衡 + beta neutral |
| construction_sensitivity | ≤ 0.50 | **≤ 0.60** + avg_pairwise_corr 可信度 |
| recent_period_sharpe | SR ≥ 0 | **sharpe_decay** t-stat（Lo 2002 SE） |
| temporal_consistency | SR > 0 計數 | **sign-magnitude weighted** |
| Soft gate | 僅供參考 | **≥ 3 soft fail 阻擋** |
| OOS 窗口 | L5+Validator 共用 549d | **分兩半**（L5 前半 / Validator 後半） |
| EW benchmark | 倖存者偏差 | **下市股 ffill** |
| Factor attribution | 無 | **Fama-French 迴歸**（描述性） |
| Hard gate 數 | 10 | **7**（更精準，非更寬鬆） |

### 1.2 evaluate.py 改善

| 項目 | 修改前 | 修改後 |
|------|--------|--------|
| IC 計算 | raw Spearman | **行業中性化**（減行業均值） |
| L1 bypass | 只看 \|IC_60d\| | 加 **sign consistency** |
| L3 correlation | 0.50 | **0.65** |
| L3 replacement | 1.3x ICIR | **1.15x** |
| L3 positive_years | 固定年份 | **rolling 12-month** ≥ 50% |
| L3 failure | 無標記 | **L3_dedup / L3_stability** |
| L5 ICIR decay | Hard check | **移除**（留給 Validator） |
| Normalization | agent 隨機 | **自動 [raw/rank/zscore]** |
| OOS 範圍 | 全 549d | **前半 275d**（後半留 Validator） |

### 1.3 Trading Safety（Phase AL 補完）

| 項目 | 說明 |
|------|------|
| Heartbeat catalog fallback | catalog 價格不重置 heartbeat（`realtime=False`） |
| Smoke test 整合 | daily_ops 盤前自動跑，fail 阻擋交易 |
| 零股補單 | weights_to_orders 餘數產生 odd-lot 訂單 |
| 股利雙重採計防呆 | auto_adjust + enable_dividends → raise |

### 1.4 基礎設施

| 項目 | 說明 |
|------|------|
| 自動啟動排程 | `autostart.py install`（server + watchdog + backup） |
| Autoresearch model | loop.ps1 加 `--model claude-sonnet-4-6` |
| Deploy ACK | watchdog 寫入驗證 + host ACK + 48h 告警 |
| Repo hygiene | Makefile/pre-push/docs mobile→android |
| OrderExecutor Protocol | trading_pipeline.py broker: Any → OrderExecutor |
| Decorator registration | @register_strategy("name") 可用 |

---

## 2. 待做項目

### P0（影響正確性）

| # | 項目 | 說明 | 工程量 |
|---|------|------|:------:|
| AM-1 | ~~vs_ew_universe beta neutral bug~~ | ✅ 移除 beta neutral，回到 gross vs EW 直接比較 | 完成 |
| AM-2 | ~~Factor attribution insufficient data~~ | ✅ 最小數據量 60→20，close_dict 門檻 30→20 | 完成 |
| AM-3 | ~~合併至 AM-21~~ | — | — |

### P1（架構整理）

| # | 項目 | 說明 | 工程量 |
|---|------|------|:------:|
| AM-4 | 拆 app.py bootstrap | 抽成 bootstrap/runtime.py、market.py、monitoring.py | 大 |
| AM-5 | 拆 engine.py | 按 data loading / simulation / settlement 切 stage | 大 |
| AM-6 | 拆 validator.py | 按 check 類別分檔（statistical / economic / regime） | 中 |
| AM-7 | 降低 AppState singleton 依賴 | 改 FastAPI dependency injection，先從 API routes 開始 | 大 |

### P2（Alpha 可部署性 — 從「找因子」到「讓因子能活」）

> 核心目標：不是再多做 20 個因子，而是把現有 alpha 的「成本後報酬、容量、風格分散、極端市況存活率」做厚。

| # | 項目 | 說明 | 工程量 |
|---|------|------|:------:|
| AM-8 | ~~Cost-adjusted IR 主指標~~ | ✅ cost breakdown + turnover p50/p95/max + IC half-life + cost-adj SR | 完成 |
| AM-9 | ~~Regime split 分析~~ | ✅ 5 regime（bull/bear/sideways/high_vol/earnings_month）| 完成 |
| AM-10 | ~~Capacity analysis~~ | ✅ 1x/3x/5x/10x alpha decay curve | 完成 |
| AM-11 | ~~Portfolio overlay~~ | ✅ `src/portfolio/overlay.py` — OverlayConfig + apply_overlay（exposure/sector/beta）。整合進 trading_pipeline.py | 完成 |
| AM-12 | ~~Multi-strategy risk-budgeting~~ | ✅ `src/portfolio/risk_budget.py` — 3 桶 inverse-vol weighting + diversification ratio | 完成 |
| AM-13 | ~~Left-tail stress test~~ | ✅ 6 固定壓力情境（COVID/航運/升息/除息/選舉/單日跌幅） | 完成 |
| AM-14 | ~~Benchmark-relative 追蹤~~ | ✅ excess vs 0050 + bear-market relative DD | 完成 |
| AM-15 | ~~Auto-Alpha 搜索空間限制~~ | ✅ program.md 加經濟直覺白名單 5 家族 | 完成 |
| AM-16 | ~~因子退場機制~~ | ✅ rolling 6m SR + 63d cost-adj IR 檢查 | 完成 |
| AM-17 | ~~OOS regime 標記~~ | ✅ 標記 bull/sideways/bear + 0050 年化報酬 | 完成 |

### P2b（研究品質）

| # | 項目 | 說明 | 工程量 |
|---|------|------|:------:|
| AM-18 | ~~台股 SMB/HML/MOM 因子完善~~ | ✅ SMB 改 close×avg_vol，HML 改 PBR-based | 完成 |
| AM-19 | ~~L3 IC sign persistence test~~ | ✅ runs test 加入 L3 failure message | 完成 |
| AM-20 | ~~因子 normalization 變體擴展~~ | ✅ 加 winsorize + percentile_rank（5 種 variant）| 完成 |
| AM-21 | ~~L2 ICIR > 1.0 → ESS check~~ | ✅ ESS < 30 fail，否則標 suspicious 放行 | 完成 |

### P3（未來規劃）

| # | 項目 | 說明 | 前提 |
|---|------|------|------|
| AM-22 | Live trading 啟動 | Sinopac CA 證書 + Phase AL G1-G6 畢業 | CA 證書 |
| AM-23 | 高頻因子評估管線 | fork evaluate.py，成本調整門檻 | 需求確認 |
| AM-24 | 全因子 Fama-French attribution | 用 TWSE 市值數據建構正式 SMB/HML | 數據取得 |

> **P1 架構整理（AM-4~7）獨立為 Phase AN**，讓 AM 聚焦 alpha 可部署性。

---

## 3. 施做順序

```
AM-1 → AM-2（P0 正確性 bug）
  ↓
AM-8 → AM-9 → AM-10（核心三件事：成本 + regime + capacity）
  ↓
AM-13 → AM-14 → AM-16 → AM-17（存活率：stress test + benchmark + 退場 + regime 標記）
  ↓
AM-15 → AM-21（搜索空間 + ESS check）
  ↓
AM-11 → AM-12（portfolio overlay + multi-strategy，放大器）
  ↓
AM-18 → AM-20（研究品質，持續改進）
```

**原則：先讓單因子可部署（AM-8~10），再確保存活（AM-13~17），最後做組合（AM-11~12）。**

---

## 4. 成功標準

- [x] AM-1~2：P0 正確性問題修復
- [x] AM-8：Validator 報告含 cost breakdown + turnover 分布 + IC half-life + cost-adj SR
- [x] AM-9：每個因子報告含 5 regime split（bull/bear/sideways/high_vol/earnings）
- [x] AM-10：每個因子報告含 1x/3x/5x/10x 容量曲線
- [x] AM-13：6 個固定壓力情境全部跑完並記錄
- [x] AM-16：退場機制生效（rolling 6m SR + 63d cost-adj IR）
- [x] AM-11：portfolio overlay 可配置 beta target + 產業上限
- [x] AM-12：risk_budget.py — 3 桶 inverse-vol + diversification ratio
- [x] revenue_acceleration 維持 7/7 Hard PASS
- [ ] autoresearch L2 pass rate ≥ 25%（待觀察）
- [x] 測試全部通過
- [x] Validator 報告含 cost-adjusted SR（非 raw Sharpe 排名）
- [x] capacity analysis 量化 alpha decay
- [x] regime split 進 Validator 主報告

---

## 5. 與外部審查的對應

| 外部建議 | 對應項目 | 狀態 |
|---------|---------|:----:|
| Cost-adjusted IR + 成本分列 | AM-8 | 待做 |
| Regime split（含橫盤） | AM-9 | 待做 |
| Capacity 容量曲線 | AM-10 | 待做 |
| Portfolio overlay（research + deployment） | AM-11 | 待做 |
| Multi-strategy risk-budgeting（3 桶） | AM-12 | 待做 |
| Left-tail（6 固定情境含台股特有） | AM-13 | 待做 |
| Benchmark-relative + bear DD | AM-14 | 待做 |
| Auto-Alpha 白名單 5 家族 | AM-15 | 待做 |
| 因子退場機制 | AM-16 | 待做 |
| OOS regime 標記 | AM-17 | 待做 |
| Turnover stability（p50/p95/max） | AM-8 整合 | 待做 |
| IC half-life | AM-8 整合 | 待做 |
| AM-3/AM-19 合併 + permutation 分層 | AM-21 | 待做 |
| beta 可配置 | AM-11 整合 | 待做 |
| AM-12 成功標準改 MDD | AM-12 已更新 | 待做 |
| P1 架構獨立為 Phase AN | **已採納** | ✅ |
| 拆 app.py / engine.py / validator.py / singleton | **移至 Phase AN** | — |
| ExecutionBroker Protocol | **已完成** | ✅ |
| Decorator registration | **已完成** | ✅ |
| Repo hygiene | **已完成** | ✅ |
| EW benchmark 偏誤 | **已修正** | ✅ |
| DSR N 統一 | **已修正** | ✅ |
| 行業中性化 IC | **已實作** | ✅ |
| OOS double dipping | **已修正** | ✅ |
| L3 correlation 放寬 | **已修正** | ✅ |
| Factor attribution | **已實作** | ✅ |

---

## 6. 審批意見

### 6.1 審批結論

**有條件批准。**

我認同這個 phase 的方向，而且金融上值得優先做。Phase AM 的核心價值，不只是修 validator bug，而是把研究標準從「回測分數高」提升成「可部署、可擴資、可穿越不同 regime 的 alpha」。

但批准有前提：**P0 與 P2 必須視為同一條金融風險鏈處理。** 如果只修統計問題，卻不把 cost、regime、capacity 一起納入，validator 仍可能把不可交易的策略送進候選池。

### 6.2 我認可的金融方向

- `AM-8 Cost-adjusted IR` 應視為本 phase 核心項，不是附加優化。金融上很多 alpha 失效，首先不是訊號消失，而是成本後 edge 不夠。
- `AM-9 Regime split` 很重要。沒有 regime 拆分，單一總樣本 Sharpe 很容易掩蓋策略只在少數市場環境有效。
- `AM-10 Capacity analysis` 必須進 validator 主報告，而不是研究附錄。未做 capacity stress 的 alpha，不應視為可部署。
- `AM-13 Left-tail stress test` 是必要項。金融上最該防的是單月或單事件把多年 alpha 吐回去。
- `AM-14 Benchmark-relative` 方向正確。若主要部署在台股，策略至少要回答「為何不直接持有 0050 / 006208」。
- `AM-15 Auto-Alpha 搜索邊界` 也合理。研究空間若過寬，最後優化的通常是資料噪音，不是可持續的經濟機制。

### 6.3 批准條件

- `AM-8` 不只要 turnover penalty，還要把 **tax + commission + slippage + impact** 分開列示，避免單一 cost rate 掩蓋成本來源。
- `AM-9` 的 regime 定義要先固定，不可針對結果回頭改門檻，否則會變成另一種 data snooping。
- `AM-10` 建議固定輸出 `1x / 3x / 5x / 10x` 容量曲線，而不是只有 pass/fail。
- `AM-11 Portfolio overlay` 應明確區分：
  `research overlay`：用來驗證 alpha 在 beta/sector 控制後是否仍成立。
  `deployment overlay`：用來控制實盤總曝險。
- `AM-12` 建議先從 3 個風格桶落地：`trend / fundamental / mean-reversion`，不要一開始就做過度複雜的全域最適化。
- `AM-13` 應把 stress case 固定成標準測項，避免每次研究各自挑案例。
- `AM-14` 除了相對 0050，也應補 `bear-market relative drawdown`，因為跌市保護才是真正的金融價值。
- `AM-15` 應加入經濟直覺白名單，優先允許：`revenue trend / valuation re-rating / quality / liquidity / sentiment`。不建議讓 agent 任意混出黑盒組合後再靠 statistical gate 淘汰。

### 6.4 金融面的執行順序建議

1. `AM-1 ~ AM-3`
   先修 validator 基本統計錯誤與 attribution 資料問題。
2. `AM-8 + AM-9 + AM-10`
   先建立成本後、regime、capacity 三大主報告欄位。
3. `AM-13 + AM-14`
   再補 left-tail 與 benchmark-relative，讓「能不能持有」比「回測高不高」更清楚。
4. `AM-15`
   最後才放寬 Auto-Alpha 搜索與替換規則。

`AM-11` 與 `AM-12` 可以放在上面完成後再接，因為 overlay / risk-budgeting 是放大器，不是 validator 的第一層防線。

### 6.5 不建議視為完成的情況

若出現以下任一情況，我不建議視為完成 Phase AM：

- validator 仍以 raw Sharpe 或單一 OOS 分數作為主排名依據。
- cost-adjusted 指標只做單一固定扣分，未拆出 turnover、tax、impact。
- regime split 只存在於研究腳本或 notebook，未進正式 validator 報告。
- capacity analysis 沒有量化 alpha decay，只輸出可交易/不可交易。
- Auto-Alpha 仍可大量生成缺乏經濟直覺的候選，再依 statistical gate 淘汰。

### 6.6 審批摘要

**批准推進，但需按金融優先序落地：先修統計基礎，再把 cost / regime / capacity 變成 validator 主體，最後才擴大 alpha 搜索與組合層。**

### 6.7 補充建議

#### 6.7.1 Turnover stability gate

AM-8 只看 cost-adjusted IR，但沒有檢查 **turnover 的穩定性**。一個因子如果平均 turnover 40% 但某些月份暴衝到 200%，cost-adjusted IR 會掩蓋這個風險。建議加一個 `turnover_cv`（變異係數）門檻，或至少在報告中列出 turnover 的分布（p50 / p95 / max）。

#### 6.7.2 IC half-life / alpha 衰減趨勢

AM-9 regime split 和 AM-14 benchmark-relative 都隱含一個問題：**因子的 alpha 是在衰減還是穩定？** 建議加一個 `IC half-life` 或 `rolling 12m ICIR trend` 的描述性指標。這不需要成為 hard gate，但應該出現在報告中，讓判斷一個因子是「還能用」還是「正在死」。

#### 6.7.3 AM-9 regime 定義缺少「橫盤」

目前定義了多頭、空頭、高波動、低流動性、財報月，但台股有大量時間處於 **橫盤震盪**（0050 年化 -5% ~ +15%，VIX < 25）。這個 regime 往往佔 40-50% 的時間，如果因子在橫盤無效，實際體驗會很差。建議補上。

#### 6.7.4 AM-11 beta 目標應可配置

計畫寫 beta = 0.5-0.8，但這對「個人投資者 / 家族資產管理」的定位來說可能太保守。如果部署資金不大（< 5000 萬台幣），完全可以接受 beta 0.8-1.0 + alpha overlay。建議改成**可配置的 beta target**，而不是寫死範圍。

#### 6.7.5 AM-12 成功標準調整

> 多策略組合 Sharpe > 單因子最高 Sharpe 的 1.2 倍

這個標準在理論上合理（分散化收益），但實務上台股因子之間的相關性往往不低（尤其 momentum 和 quality 在牛市高度正相關）。建議改成：

- 組合 Sharpe ≥ 單因子最高 Sharpe（不退化）
- 組合 max drawdown < 單因子最差 max drawdown 的 0.7 倍（真正的分散化價值在尾部）

#### 6.7.6 AM-13 補充台股特有壓力情境

目前壓力情境是 2020-03（COVID）、2022-06（全球升息）、開盤跳空。建議補上：

- **2022-01 航運股崩盤**（單一產業 -60%，測產業集中度風險）
- **除權息旺季**（7-9 月，高殖利率因子假 alpha）
- **選舉/地緣政治**（2024-01 大選前後波動）

#### 6.7.7 AM-3 / AM-19 合併 + permutation test 分層

AM-3 和 AM-19 描述幾乎一樣，建議合併。另外 permutation test 的計算成本不低（需要 1000+ 次 shuffle），如果放在 evaluate.py 的 L2，會大幅拖慢 autoresearch 循環。建議：

- L2 只做 ESS check（快速）
- permutation test 放在 Validator 層（只有通過 L4 的因子才做）

#### 6.7.8 OOS split 的 regime 標記

OOS 分兩半（L5 前半 / Validator 後半）解決了 double dipping，但引入了一個新問題：如果後半段剛好是 regime 轉換期（例如從牛轉熊），Validator 的 OOS 結果可能系統性偏差。建議在報告中標記 OOS 期間的 market regime，讓判斷時有 context。

#### 6.7.9 缺少因子退場機制

整份計畫聚焦在「因子入場」（怎麼篩選、怎麼部署），但沒有定義 **deployed factor 的退場條件**。建議新增項目：

- rolling 6m ICIR < 0（連續 6 個月信號反轉）→ 降權
- cost-adjusted IR < 0 持續 3 個月 → 移除
- 觸發退場後即時處理，不等年度 review

#### 6.7.10 P1 架構整理建議獨立

AM-4 ~ AM-7 的架構整理（拆 app.py / engine.py / validator.py / 降低 singleton）和 Validator 方法論改善是完全不同的工作流。建議把 P1 架構整理獨立成 Phase AN 或類似的，讓 Phase AM 聚焦在「alpha 可部署性」這條主線。
