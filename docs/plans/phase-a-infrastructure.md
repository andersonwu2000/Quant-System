# Phase A：多資產基礎設施

> 完成日期：2026-03-24
> 狀態：✅ 完成

## 目標
將單一股票系統升級為多資產架構，支援台股/美股/ETF/期貨的統一處理。

## 產出
- **InstrumentRegistry** (`src/instrument/`): 自動從 symbol 推斷 asset_class/market/currency。`_infer_instrument()` 辨識 `.TW`→台股、`=F`→期貨、已知 ETF 列表。
- **多幣別 Portfolio**: `nav_in_base(fx_rates)`、`currency_exposure()`、`cash_by_currency`
- **DataFeed 擴展**: FX 時間序列（`get_fx_rate`）、`get_futures_chain`
- **FRED 數據源** (`src/data/sources/fred.py`): 宏觀經濟數據（成長/通膨/利率/信用）
- **管線整合**: `weights_to_orders()` 支援乘數、lot_size；SimBroker per-instrument 費率
- **模型統一**: Instrument frozen dataclass 含 multiplier/margin_rate/commission_rate/tax_rate
