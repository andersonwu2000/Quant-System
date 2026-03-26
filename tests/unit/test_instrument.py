"""Tests for src/instrument/ — Instrument Registry。"""

from decimal import Decimal

import pytest

from src.core.models import AssetClass, Instrument, Market, SubClass

from src.instrument.registry import InstrumentRegistry, _infer_instrument


class TestInstrumentModel:
    def test_defaults(self):
        inst = Instrument(symbol="AAPL")
        assert inst.asset_class == AssetClass.EQUITY
        assert inst.currency == "TWD"
        assert inst.multiplier == Decimal("1")

    def test_frozen(self):
        inst = Instrument(symbol="AAPL")
        with pytest.raises(AttributeError):
            inst.symbol = "MSFT"  # type: ignore[misc]

    def test_unified_model(self):
        """統一模型：domain/models.py 的 Instrument 就是唯一定義。"""
        inst = Instrument(symbol="2330.TW", name="台積電", market=Market.TW, currency="TWD")
        assert inst.symbol == "2330.TW"
        assert inst.currency == "TWD"
        assert inst.sub_class == SubClass.STOCK

    def test_futures_instrument(self):
        inst = Instrument(
            symbol="ES=F", name="S&P E-mini",
            asset_class=AssetClass.FUTURE, sub_class=SubClass.FUTURE,
            multiplier=Decimal("50"), margin_rate=Decimal("0.05"),
        )
        assert inst.asset_class == AssetClass.FUTURE
        assert inst.multiplier == Decimal("50")
        assert inst.margin_rate == Decimal("0.05")


class TestInferInstrument:
    def test_tw_stock(self):
        inst = _infer_instrument("2330.TW")
        assert inst.market == Market.TW
        assert inst.asset_class == AssetClass.EQUITY
        assert inst.currency == "TWD"

    def test_tw_etf(self):
        inst = _infer_instrument("0050.TW")
        assert inst.asset_class == AssetClass.ETF
        assert inst.sub_class == SubClass.ETF_EQUITY

    def test_tw_etf_long_code(self):
        inst = _infer_instrument("00878.TW")
        assert inst.asset_class == AssetClass.ETF

    def test_us_futures(self):
        inst = _infer_instrument("ES=F")
        assert inst.asset_class == AssetClass.FUTURE
        assert inst.currency == "USD"

    def test_bond_etf(self):
        inst = _infer_instrument("TLT")
        assert inst.asset_class == AssetClass.ETF
        assert inst.sub_class == SubClass.ETF_BOND

    def test_commodity_etf(self):
        inst = _infer_instrument("GLD")
        assert inst.sub_class == SubClass.ETF_COMMODITY

    def test_equity_etf(self):
        inst = _infer_instrument("SPY")
        assert inst.sub_class == SubClass.ETF_EQUITY

    def test_us_stock_default(self):
        inst = _infer_instrument("AAPL")
        assert inst.asset_class == AssetClass.EQUITY
        assert inst.market == Market.US


class TestInstrumentRegistry:
    def test_register_and_get(self):
        reg = InstrumentRegistry()
        inst = Instrument(symbol="AAPL", name="Apple")
        reg.register(inst)
        assert reg.get("AAPL") == inst
        assert reg.get("MSFT") is None

    def test_get_or_create(self):
        reg = InstrumentRegistry()
        inst = reg.get_or_create("2330.TW")
        assert inst.market == Market.TW
        assert "2330.TW" in reg

    def test_search(self):
        reg = InstrumentRegistry()
        reg.register(Instrument(symbol="AAPL", name="Apple", sector="tech"))
        reg.register(Instrument(symbol="MSFT", name="Microsoft", sector="tech"))
        reg.register(Instrument(symbol="JPM", name="JPMorgan", sector="finance"))
        results = reg.search("tech")
        assert len(results) == 2

    def test_by_market(self):
        reg = InstrumentRegistry()
        reg.register(Instrument(symbol="AAPL", market=Market.US))
        reg.register(Instrument(symbol="2330.TW", market=Market.TW))
        assert len(reg.by_market(Market.US)) == 1
        assert len(reg.by_market(Market.TW)) == 1

    def test_by_asset_class(self):
        reg = InstrumentRegistry()
        reg.register(Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY))
        reg.register(Instrument(symbol="SPY", asset_class=AssetClass.ETF))
        reg.register(Instrument(symbol="ES=F", asset_class=AssetClass.FUTURE))
        assert len(reg.by_asset_class(AssetClass.EQUITY)) == 1
        assert len(reg.by_asset_class(AssetClass.ETF)) == 1
        assert len(reg.by_asset_class(AssetClass.FUTURE)) == 1

    def test_load_defaults(self):
        reg = InstrumentRegistry()
        count = reg.load_defaults()
        assert count > 0
        assert reg.get("ES=F") is not None

    def test_len_and_contains(self):
        reg = InstrumentRegistry()
        reg.register(Instrument(symbol="AAPL"))
        assert len(reg) == 1
        assert "AAPL" in reg
        assert "MSFT" not in reg
