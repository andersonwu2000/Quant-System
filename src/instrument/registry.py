"""
InstrumentRegistry — 集中管理所有可交易標的的 metadata。

支援從 YAML 配置檔載入、按市場/資產類別查詢。
提供預建的常用標的（台股藍籌、美股大盤、主要 ETF、期貨）。
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.instrument.model import (
    AssetClass,
    Instrument,
    Market,
    SubClass,
    TW_FUTURES_DEFAULTS,
    TW_STOCK_DEFAULTS,
    US_FUTURES_DEFAULTS,
    US_STOCK_DEFAULTS,
)

logger = logging.getLogger(__name__)


class InstrumentRegistry:
    """金融工具註冊表。"""

    def __init__(self) -> None:
        self._instruments: dict[str, Instrument] = {}

    def register(self, instrument: Instrument) -> None:
        """註冊一個金融工具。"""
        self._instruments[instrument.symbol] = instrument

    def get(self, symbol: str) -> Instrument | None:
        """查詢單一標的，不存在時回傳 None。"""
        return self._instruments.get(symbol)

    def get_or_create(self, symbol: str) -> Instrument:
        """查詢標的，不存在時自動推斷並建立。"""
        existing = self._instruments.get(symbol)
        if existing:
            return existing
        inst = _infer_instrument(symbol)
        self._instruments[symbol] = inst
        return inst

    def search(self, query: str, asset_class: AssetClass | None = None) -> list[Instrument]:
        """模糊搜尋標的。"""
        q = query.lower()
        results = []
        for inst in self._instruments.values():
            if asset_class and inst.asset_class != asset_class:
                continue
            if q in inst.symbol.lower() or q in inst.name.lower() or q in inst.sector.lower():
                results.append(inst)
        return results

    def by_market(self, market: Market) -> list[Instrument]:
        """按市場查詢。"""
        return [i for i in self._instruments.values() if i.market == market]

    def by_asset_class(self, cls: AssetClass) -> list[Instrument]:
        """按資產類別查詢。"""
        return [i for i in self._instruments.values() if i.asset_class == cls]

    def all(self) -> list[Instrument]:
        """回傳所有已註冊的標的。"""
        return list(self._instruments.values())

    def symbols(self) -> list[str]:
        """回傳所有 symbol。"""
        return list(self._instruments.keys())

    def __len__(self) -> int:
        return len(self._instruments)

    def __contains__(self, symbol: str) -> bool:
        return symbol in self._instruments

    def load_from_yaml(self, path: str | Path) -> int:
        """
        從 YAML 檔載入標的定義。

        YAML 格式：
        ```yaml
        instruments:
          - symbol: "2330.TW"
            name: "台積電"
            asset_class: equity
            market: tw
            currency: TWD
            lot_size: 1000
        ```

        Returns:
            載入的標的數量
        """
        import yaml  # type: ignore[import-untyped]

        p = Path(path)
        if not p.exists():
            logger.warning("Instrument config not found: %s", p)
            return 0

        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        count = 0
        for item in data.get("instruments", []):
            try:
                inst = _dict_to_instrument(item)
                self.register(inst)
                count += 1
            except Exception:
                logger.warning("Failed to load instrument: %s", item, exc_info=True)

        logger.info("Loaded %d instruments from %s", count, p)
        return count

    def load_defaults(self) -> int:
        """載入預建的常用標的。"""
        count = 0
        for inst in _default_instruments():
            self.register(inst)
            count += 1
        return count


# ── 內部工具 ─────────────────────────────────────────────


def _infer_instrument(symbol: str) -> Instrument:
    """根據 symbol 格式推斷標的屬性。"""
    s = symbol.upper()

    # 台股: 數字.TW
    if s.endswith(".TW"):
        code = s.replace(".TW", "")
        # 台股 ETF: 0050, 0056, 00878 等
        if code.startswith("0") or code.startswith("00"):
            return Instrument(
                symbol=symbol, asset_class=AssetClass.ETF,
                sub_class=SubClass.ETF_EQUITY, **TW_STOCK_DEFAULTS,  # type: ignore[arg-type]
            )
        return Instrument(symbol=symbol, asset_class=AssetClass.EQUITY, sub_class=SubClass.STOCK, **TW_STOCK_DEFAULTS)  # type: ignore[arg-type]

    # 期貨: =F 結尾
    if s.endswith("=F"):
        return Instrument(symbol=symbol, name=symbol, **US_FUTURES_DEFAULTS)  # type: ignore[arg-type]

    # 外匯: =X 結尾 — 不納入交易，但可用於匯率查詢
    if s.endswith("=X"):
        return Instrument(symbol=symbol, name=symbol, market=Market.US, currency="USD")

    # 已知美股 ETF
    _KNOWN_BOND_ETFS = {"TLT", "IEF", "SHY", "LQD", "HYG", "AGG", "BND", "VCIT", "VCSH"}
    _KNOWN_COMMODITY_ETFS = {"GLD", "SLV", "USO", "DBA", "IAU", "PDBC"}
    _KNOWN_EQUITY_ETFS = {
        "SPY", "QQQ", "IWM", "DIA", "VOO", "VTI", "EFA", "EEM", "VWO", "FXI", "EWJ", "EWT",
        "XLK", "XLF", "XLV", "XLE", "XLY", "XLP", "XLI", "XLU", "XLB", "XLRE", "SMH",
    }

    if s in _KNOWN_BOND_ETFS:
        return Instrument(
            symbol=symbol, asset_class=AssetClass.ETF,
            sub_class=SubClass.ETF_BOND, **US_STOCK_DEFAULTS,  # type: ignore[arg-type]
        )
    if s in _KNOWN_COMMODITY_ETFS:
        return Instrument(
            symbol=symbol, asset_class=AssetClass.ETF,
            sub_class=SubClass.ETF_COMMODITY, **US_STOCK_DEFAULTS,  # type: ignore[arg-type]
        )
    if s in _KNOWN_EQUITY_ETFS:
        return Instrument(
            symbol=symbol, asset_class=AssetClass.ETF,
            sub_class=SubClass.ETF_EQUITY, **US_STOCK_DEFAULTS,  # type: ignore[arg-type]
        )

    # 預設：美股個股
    return Instrument(symbol=symbol, asset_class=AssetClass.EQUITY, sub_class=SubClass.STOCK, **US_STOCK_DEFAULTS)  # type: ignore[arg-type]


def _dict_to_instrument(d: dict[str, Any]) -> Instrument:
    """從 dict 建構 Instrument。"""
    ac_map = {"equity": AssetClass.EQUITY, "etf": AssetClass.ETF, "futures": AssetClass.FUTURE, "future": AssetClass.FUTURE}
    mkt_map = {"tw": Market.TW, "us": Market.US}
    cur_map = {"TWD": "TWD", "USD": "USD"}
    sc_map = {
        "stock": SubClass.STOCK, "etf_equity": SubClass.ETF_EQUITY,
        "etf_bond": SubClass.ETF_BOND, "etf_commodity": SubClass.ETF_COMMODITY,
        "etf_mixed": SubClass.ETF_MIXED, "future": SubClass.FUTURE,
    }

    return Instrument(
        symbol=d["symbol"],
        name=d.get("name", ""),
        asset_class=ac_map.get(d.get("asset_class", "equity"), AssetClass.EQUITY),
        sub_class=sc_map.get(d.get("sub_class", "stock"), SubClass.STOCK),
        market=mkt_map.get(d.get("market", "us"), Market.US),
        currency=cur_map.get(d.get("currency", "USD"), "USD"),
        multiplier=Decimal(str(d.get("multiplier", 1))),
        tick_size=Decimal(str(d.get("tick_size", "0.01"))),
        lot_size=int(d.get("lot_size", 1)),
        margin_rate=Decimal(str(d["margin_rate"])) if d.get("margin_rate") else None,
        commission_rate=Decimal(str(d.get("commission_rate", "0.001425"))),
        tax_rate=Decimal(str(d.get("tax_rate", "0"))),
        sector=d.get("sector", ""),
    )


def _default_instruments() -> list[Instrument]:
    """預建常用標的。"""
    instruments: list[Instrument] = []

    # 主要台灣期貨
    tw_futures = [
        ("TX=F", "台指期", Decimal("200")),
        ("TE=F", "電子期", Decimal("4000")),
        ("TF=F", "金融期", Decimal("1000")),
    ]
    for sym, name, size in tw_futures:
        instruments.append(Instrument(
            symbol=sym, name=name, multiplier=size,
            margin_rate=Decimal("0.10"), **{k: v for k, v in TW_FUTURES_DEFAULTS.items() if k not in ("margin_rate",)},  # type: ignore[arg-type]
        ))

    # 主要美國期貨
    us_futures = [
        ("ES=F", "S&P 500 E-mini", Decimal("50"), Decimal("0.25")),
        ("NQ=F", "Nasdaq 100 E-mini", Decimal("20"), Decimal("0.25")),
        ("YM=F", "Dow E-mini", Decimal("5"), Decimal("1")),
        ("GC=F", "黃金期貨", Decimal("100"), Decimal("0.10")),
        ("SI=F", "白銀期貨", Decimal("5000"), Decimal("0.005")),
        ("CL=F", "原油期貨", Decimal("1000"), Decimal("0.01")),
    ]
    for sym, name, size, tick in us_futures:
        instruments.append(Instrument(
            symbol=sym, name=name, multiplier=size, tick_size=tick,
            margin_rate=Decimal("0.05"),
            **{k: v for k, v in US_FUTURES_DEFAULTS.items() if k not in ("margin_rate",)},  # type: ignore[arg-type]
        ))

    return instruments
