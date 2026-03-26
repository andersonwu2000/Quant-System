# 券商 API 評估報告

> 撰寫日期：2026-03-24
> 目標：評估台灣主要券商 API，為本專案從回測模式進入實盤交易選擇最適合的券商接口。

---

## 一、本專案現況分析

### 執行層架構

```
Strategy.on_bar() → target weights
  → weights_to_orders() → list[Order]
    → RiskEngine.check_orders() → approved orders
      → SimBroker.execute() → list[Trade]
        → apply_trades() → Portfolio updated
```

### 已完成的基礎設施

| 元件 | 狀態 | 說明 |
|------|------|------|
| `BrokerAdapter` ABC | ✅ 已定義 | `src/execution/broker.py` — 定義 `submit_order`, `cancel_order`, `query_positions`, `query_account`, `is_connected` |
| `SimBroker` | ✅ 完整 | 支援 fixed/sqrt 滑價模型、手續費 0.1425%、證交稅 0.3%、成交量限制、漲跌停 |
| `PaperBroker` | ⚠️ Stub | 僅有硬編碼回傳值，未實際連接任何券商 |
| Order 模型 | ✅ 完整 | 支援 MARKET/LIMIT、BUY/SELL、狀態機 (PENDING→SUBMITTED→FILLED/REJECTED) |
| 風控引擎 | ✅ 完整 | 持倉上限、單筆限額、肥手指偵測、kill switch |
| T+N 交割 | ✅ 回測中已實作 | `settlement_days` 參數，支援延遲交割 |

### 實盤交易尚缺的功能

| 缺口 | 優先級 | 說明 |
|------|--------|------|
| 真實券商 Adapter | 🔴 P0 | BrokerAdapter 從未被實例化 |
| 非同步成交回報 | 🔴 P0 | 目前為同步即時成交，實盤需 callback/polling |
| 模式切換路由 | 🟡 P1 | `config.mode` (backtest/paper/live) 存在但未影響執行路徑 |
| 部分成交處理 | 🟡 P1 | SimConfig 中 `partial_fill=False`，程式碼支援但未啟用 |
| 持倉對帳 | 🟡 P1 | 無 EOD 對帳機制 |
| 限價單執行 | 🟢 P2 | Order 模型支援 LIMIT 但 SimBroker 忽略 |
| 交易時段驗證 | 🟢 P2 | 可 24/7 下單，未檢查開收盤時間 |
| 逾時/重試機制 | 🟢 P2 | 掛單逾時未處理 |

---

## 二、券商 API 總覽

### 評估維度

- **Python 原生支援**：是否提供 native Python SDK（非 COM bridge）
- **跨平台**：是否支援 Linux/macOS（伺服器部署必要）
- **模擬交易**：是否支援 paper trading
- **期貨選擇權**：是否支援衍生性商品
- **即時行情**：是否提供 tick-level 即時報價
- **文件品質**：文件完整度與範例程式品質
- **社群活躍度**：GitHub stars、更新頻率、社群討論
- **接入門檻**：開戶流程、憑證安裝、申請複雜度

---

## 三、各券商詳細評估

### 1. 永豐金證券 — Shioaji ⭐ 首選推薦

| 項目 | 內容 |
|------|------|
| API 名稱 | Shioaji |
| 類型 | Native Python SDK（C++ 核心 + Python binding） |
| 安裝 | `pip install shioaji` |
| 支援平台 | Windows / Linux / macOS |
| 支援語言 | Python（主要）、C# |
| 文件 | [sinotrade.github.io](https://sinotrade.github.io/) — 中英雙語、完整範例 |
| GitHub | [Sinotrade/Shioaji](https://github.com/Sinotrade/Shioaji) — 231+ stars |
| 更新頻率 | 14 天發布週期，持續活躍維護 |

**支援的委託類型：**
- 股票：ROD（當日有效）、IOC（立即成交否則取消）、FOK（全部成交否則取消）
- 股票子類型：整股（Common）、零股（Odd）、鉅額（BlockTrade）、定盤（Fixing）
- 期貨/選擇權：LMT、MKT、MKP
- 價格類型：限價（LMT）、收盤價（Close）、漲停（LimitUp）、跌停（LimitDown）

**即時行情：** WebSocket tick-by-tick + 歷史資料 API

**模擬交易：** 登入時設定 `simulation=True` 即可切換模擬模式

**認證方式：** Token + Secret Key → CA 憑證啟用 → 2FA（手機/Email OTP）

**已知問題：**
- 憑證匯入在部分環境偶有路徑問題
- 核心為閉源 C++ 編譯檔

**與本專案整合評估：**
```python
# 範例：Shioaji 下單流程
import shioaji as sj

api = sj.Shioaji(simulation=True)
api.login("person_id", "password")

contract = api.Contracts.Stocks["2330"]  # 台積電
order = api.Order(
    price=590,
    quantity=1,     # 1 張 = 1000 股
    action=sj.constant.Action.Buy,
    price_type=sj.constant.StockPriceType.LMT,
    order_type=sj.constant.OrderType.ROD,
)
trade = api.place_order(contract, order)
```

**整合難度：低** — SDK 設計符合 Python 慣例，callback 機制可直接對接 `BrokerAdapter`。

---

### 2. 富邦證券 — Fubon Neo API

| 項目 | 內容 |
|------|------|
| API 名稱 | Fubon Neo API |
| 類型 | Native SDK + WebSocket |
| 安裝 | 官網下載 .whl 安裝（非 PyPI） |
| 支援平台 | Windows / Linux / macOS |
| 支援語言 | Python、C#、Node.js、C++、Golang |
| Python 版本 | 3.7 – 3.12 |
| 文件 | [fbs.com.tw/TradeAPI](https://www.fbs.com.tw/TradeAPI/en/) — 含英文版 |

**支援的委託類型：**
- 標準委託（Stock, DayTrade）
- MIT（Market-If-Touched，觸價單）
- TP/SL（停利停損單）
- Time-Slice（分時委託）
- 條件單（Condition Orders）

**即時行情：** WebSocket API，股票 + 期貨

**模擬交易：** 未明確確認

**認證方式：** 身份證字號 + 密碼 + CA 憑證路徑 + 憑證密碼 → OTP 驗證

**備註：** 2023 年合併日盛證券，原日盛客戶已遷移至富邦帳戶。

**與本專案整合評估：**
- 語言支援最廣（5 種語言）
- 進階委託類型（條件單、觸價單）對策略執行有額外價值
- 非 PyPI 安裝需額外處理 CI/CD 流程

**整合難度：中** — SDK 功能完整，但安裝方式非標準，需手動管理版本。

---

### 3. 元富證券 — MasterLink Digital API

| 項目 | 內容 |
|------|------|
| API 名稱 | MasterLink 數位 API |
| 類型 | Native SDK |
| 安裝 | 官網下載 |
| 支援平台 | Windows |
| 支援語言 | Python、C# |
| 文件 | [mlapi.masterlink.com.tw](https://mlapi.masterlink.com.tw/web_api/service/home) — 中文、含 Python 範例 |

**支援的委託類型：** 標準委託下單

**即時行情：** 即時報價 + 約 1 個月歷史資料

**模擬交易：** ✅ 提供模擬交易環境（盤中可用 tick-by-tick 資料）

**認證方式：** 需簽署風險預告書，下單 API 與報價 API 分開申請

**亮點：** Fugle 已為 MasterLink SDK 開發 MCP Server，可整合 AI Agent 工作流。

**整合難度：中高** — 僅支援 Windows，限制伺服器部署選擇。

---

### 4. 元大證券 — Yuanta API

| 項目 | 內容 |
|------|------|
| API 名稱 | Yuanta OneAPI / API 下單元件 |
| 類型 | COM/DLL 元件 |
| 安裝 | 手動複製 DLL 至 `C:\Yuanta`，執行批次安裝 |
| 支援平台 | **Windows only** |
| 支援語言 | C#（原生）、Python（透過 pythonnet/COM bridge）、VBA、MultiCharts |
| 文件 | 中文、極簡 |

**備註：** 台灣市佔率最高的券商，但 API 架構老舊（COM 元件）。期貨 API 需另外申請，處理時間約 1 週。券商不提供程式偵錯支援。

**整合難度：高** — COM bridge 架構脆弱，僅限 Windows，除錯困難。

---

### 5. 凱基證券 — KGI Smart Platform API

| 項目 | 內容 |
|------|------|
| API 名稱 | 智能平台 API |
| 類型 | COM/DLL 元件 |
| 支援平台 | **Windows only** |
| 主要用途 | 期貨 / 選擇權交易為主 |
| 文件 | 極少官方文件，依賴社群教學 |

**整合難度：高** — 以期權為主，證券 API 碎片化。

---

### 6. 群益證券 — Capital (skcom)

| 項目 | 內容 |
|------|------|
| API 名稱 | SKCOM（非官方 Python wrapper：`skcom`） |
| 安裝 | `pip install skcom` |
| GitHub | [tacosync/skcom](https://github.com/tacosync/skcom) |
| 支援平台 | **Windows 64-bit only** |
| 限制 | **僅支援股票**，不支援期貨/選擇權，維護者明確拒絕相關 PR |

**整合難度：高** — 社群維護、功能受限、平台受限。

---

### 7. 富果 (Fugle) — 市場數據 + 交易 API

| 項目 | 內容 |
|------|------|
| 類型 | REST + WebSocket（現代 HTTP 架構） |
| 安裝 | `pip install fugle-marketdata` / `pip install fugle-trade` |
| 支援平台 | 全平台 |
| 合作券商 | 玉山證券（E.SUN）、元富證券（MasterLink） |
| 文件 | [developer.fugle.tw](https://developer.fugle.tw/) — 現代化、組織良好 |

**⚠️ 重要：** Fugle Trading API 自 2025 年 11 月起不再更新，下單功能轉移至合作券商 SDK（MasterLink SDK）。

**最佳用途：** 作為行情數據源（REST/WebSocket，有免費方案），搭配其他券商執行下單。

---

### 8. 台新證券 — TSSCO API

| 項目 | 內容 |
|------|------|
| API 名稱 | 台新證券 API 下單元件 (`apiTSS.dll`) |
| 類型 | Native DLL / COM 元件 |
| 安裝 | 手動放置 `apiTSS.dll` 至 `TSSAP` 資料夾，執行 `regAPI` 登錄 |
| 支援平台 | **Windows only** |
| 支援語言 | C#、Visual Basic、Excel VBA（**無 Python 支援**） |
| 官方頁面 | [tssco.com.tw/585](https://www.tssco.com.tw/585/) |
| 文件 | 僅提供 PDF 規格書，無線上文件、無程式範例 |

**期貨 / 選擇權：** 透過獨立的 `DDSCTradeAPI` 元件（台新期貨，需分開申請）

**支援的委託功能：**
- 新單、刪單、改量、改價
- 委託查詢、成交查詢、庫存查詢
- 不支援條件單、停損停利、觸價單

**即時行情：** 期貨 API 內含行情查詢；股票 API 未提供獨立行情，依賴前置平台

**模擬交易：** ❌ 無模擬環境，無沙盒帳戶

**認證方式：** CA 電子憑證（強制）；API 開通需透過**業務員申請**，無法自助開通

**重要限制：**
> 「公司僅提供下單 API 連結元件供客戶自行或委外開發，不提供程式開發教學服務。」

**整合難度：極高** — 無 Python 支援、無模擬環境、無社群資源、需業務員手動開通、僅限 Windows。

---

### 9–10. 中信證券 / 國泰證券

| 券商 | API 狀態 |
|------|----------|
| 中信證券 (CTBC) | **無公開程式交易 API** |
| 國泰證券 (Cathay) | **無零售端交易 API**（僅企業級 CaaS 平台） |

**結論：** 不適用於個人程式交易。

---

## 四、綜合比較矩陣

| 券商 | Python 原生 | 跨平台 | 模擬交易 | 期權 | 即時行情 | 文件品質 | 活躍度 | 整合難度 |
|------|:-----------:|:------:|:--------:|:----:|:--------:|:--------:|:------:|:--------:|
| **永豐 Shioaji** | ✅ | ✅ Win/Linux/Mac | ✅ | ✅ | ✅ tick | ⭐⭐⭐ | ⭐⭐⭐ | 低 |
| **富邦 Neo** | ✅ | ✅ Win/Linux/Mac | ❓ | ✅ | ✅ WS | ⭐⭐⭐ | ⭐⭐ | 中 |
| **元富 MasterLink** | ✅ | ❌ Win only | ✅ | ✅ | ✅ | ⭐⭐ | ⭐⭐ | 中高 |
| **元大 Yuanta** | ⚠️ COM | ❌ Win only | ❓ | ⚠️ 分開 | ✅ | ⭐ | ⭐ | 高 |
| **凱基 KGI** | ⚠️ COM | ❌ Win only | ❓ | ✅（主力）| ✅ | ⭐ | ⭐ | 高 |
| **群益 skcom** | ⚠️ 社群 | ❌ Win64 | ❌ | ❌ | ✅ | ⭐ | ⭐ | 高 |
| **台新 TSSCO** | ❌ 無 | ❌ Win only | ❌ | ⚠️ 分開申請 | ⚠️ 期貨only | ⭐ | ⭐ | 極高 |
| **富果 Fugle** | ✅ | ✅ | Demo token | ❌ 行情only | ✅ 優秀 | ⭐⭐⭐ | ⚠️ 交易API停更 | 低（行情） |

---

## 五、與本專案 BrokerAdapter 的對接方案

### BrokerAdapter 介面回顧

```python
class BrokerAdapter(ABC):
    def submit_order(self, order: Order) -> str: ...
    def cancel_order(self, order_id: str) -> bool: ...
    def query_positions(self) -> dict[str, dict[str, Any]]: ...
    def query_account(self) -> dict[str, Any]: ...
    def is_connected(self) -> bool: ...
```

### Shioaji Adapter 對接草案

```python
class ShioajiBroker(BrokerAdapter):
    """永豐 Shioaji 實盤 Adapter"""

    def __init__(self, simulation: bool = True):
        self._api = shioaji.Shioaji(simulation=simulation)
        self._trades: dict[str, sj.Trade] = {}

    def connect(self, person_id: str, password: str, ca_path: str):
        self._api.login(person_id, password)
        self._api.activate_ca(ca_path=ca_path, ca_passwd="password")
        # 註冊成交回報 callback
        self._api.set_order_callback(self._on_order_update)

    def submit_order(self, order: Order) -> str:
        contract = self._api.Contracts.Stocks[order.instrument.symbol]
        sj_order = self._api.Order(
            price=float(order.price) if order.price else 0,
            quantity=int(order.quantity) // 1000,  # 張數
            action=sj.constant.Action.Buy if order.side == Side.BUY else sj.constant.Action.Sell,
            price_type=self._map_price_type(order),
            order_type=sj.constant.OrderType.ROD,
        )
        trade = self._api.place_order(contract, sj_order)
        self._trades[trade.order.id] = trade
        return trade.order.id

    def cancel_order(self, order_id: str) -> bool:
        trade = self._trades.get(order_id)
        if trade:
            self._api.cancel_order(trade)
            return True
        return False

    def query_positions(self) -> dict[str, dict[str, Any]]:
        positions = self._api.list_positions(self._api.stock_account)
        return {
            p.code: {"qty": p.quantity, "avg_cost": p.price}
            for p in positions
        }

    def query_account(self) -> dict[str, Any]:
        margin = self._api.account_balance()
        return {"balance": margin.acc_balance}

    def is_connected(self) -> bool:
        return self._api is not None
```

### Fubon Neo Adapter 對接草案

```python
class FubonBroker(BrokerAdapter):
    """富邦 Neo API 實盤 Adapter"""

    def __init__(self):
        from fubon_neo.sdk import FubonSDK
        self._sdk = FubonSDK()
        self._account = None

    def connect(self, id: str, pwd: str, cert_path: str, cert_pwd: str):
        accounts = self._sdk.login(id, pwd, cert_path, cert_pwd)
        self._account = accounts.data[0]

    def submit_order(self, order: Order) -> str:
        result = self._sdk.stock.place_order(
            account=self._account,
            buy_sell=BSAction.Buy if order.side == Side.BUY else BSAction.Sell,
            symbol=order.instrument.symbol,
            price=str(order.price),
            quantity=int(order.quantity) // 1000,
            market_type=MarketType.Common,
            price_type=PriceType.Limit,
            time_in_force=TimeInForce.ROD,
        )
        return result.data.order_no
```

---

## 六、推薦方案與實施路線

### 🏆 推薦：永豐金 Shioaji（第一階段）+ 富邦 Neo（第二階段）

**理由：**

1. **Shioaji 最適合起步**
   - Python 原生 SDK，與本專案技術棧完全契合
   - 唯一支援 `simulation=True` 一鍵切換模擬交易的券商 API
   - 跨平台支援（未來可部署至 Linux 伺服器）
   - 14 天更新週期，社群最活躍
   - BrokerAdapter 對接最直觀

2. **富邦 Neo 作為備援/擴充**
   - 多語言 SDK 為未來擴展保留彈性
   - 條件單、觸價單等進階委託類型
   - 英文文件降低協作門檻

3. **Fugle 作為行情數據補充**
   - REST/WebSocket 行情 API 品質最佳
   - 可與 FinMind（本專案現有數據源）互補

### 實施路線圖

```
Phase 1 — Paper Trading（模擬交易）
├── 實作 ShioajiBroker(BrokerAdapter)
├── 新增 ExecutionService：mode-aware 路由（backtest → SimBroker, paper → ShioajiBroker(sim=True)）
├── 實作非同步成交回報 callback → Order 狀態更新
├── 整合至 AppState + API routes
└── 驗證：模擬帳戶跑 1 個月 daily rebalance

Phase 2 — Live Trading（實盤交易，小額）
├── CA 憑證管理流程
├── EOD 持倉對帳（query_positions vs Portfolio）
├── 交易時段驗證（09:00–13:30 台股）
├── 限價單 / IOC / FOK 支援
├── 告警通知整合（src/notifications/）
└── 驗證：10 萬元實盤運行 2 週

Phase 3 — 多券商支援
├── 實作 FubonBroker(BrokerAdapter)
├── 券商選擇邏輯（config 層）
├── 跨券商持倉匯總
└── 效能比較（延遲、成交品質）
```

---

## 七、法規與開戶須知

| 項目 | 說明 |
|------|------|
| 個人 API 交易 | 無需特殊執照，標準證券帳戶即可 |
| 申請流程 | 簽署「應用程式介面服務申請暨委託交易風險預告書」（多數券商可線上完成） |
| 最低開戶金額 | 大部分券商無最低限額 |
| 手續費 | 標準費率：買賣各 0.1425%（可談折扣），證交稅 0.3%（賣方） |
| 券商技術支援 | 各券商明確不提供程式偵錯服務 |
| API 帳戶數限制 | 通常每位用戶限一組 API 帳戶 |

---

## 八、風險與注意事項

1. **閉源風險**：所有台灣券商 API 核心皆為閉源，版本升級可能造成 breaking changes
2. **憑證管理**：CA 憑證有效期通常 1 年，需定期更新；自動化部署需妥善管理憑證檔案
3. **API 穩定性**：台灣券商 API 非 SLA 等級的服務，偶有斷線或延遲，需實作重連機制
4. **成交回報延遲**：實際成交回報可能有數秒延遲，策略需容忍不確定狀態
5. **漲跌停限制**：台股 ±10% 漲跌停，市價單可能以漲/跌停價成交
6. **零股交易**：盤中零股（09:10–13:30 每 3 分鐘撮合一次）與整股市場撮合頻率不同
