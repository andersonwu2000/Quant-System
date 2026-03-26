"""Tests for multi-currency Portfolio extensions。"""

from decimal import Decimal

from src.core.models import AssetClass, Instrument, Portfolio, Position


def _make_instrument(symbol: str, currency: str = "TWD", ac: AssetClass = AssetClass.EQUITY) -> Instrument:
    return Instrument(symbol=symbol, currency=currency, asset_class=ac)


class TestPortfolioMultiCurrency:
    def test_backward_compat_nav(self):
        """既有單幣別行為不變。"""
        p = Portfolio(cash=Decimal("1000000"))
        assert p.nav == Decimal("1000000")

    def test_total_cash_single_currency(self):
        """無 cash_by_currency 時回傳 self.cash。"""
        p = Portfolio(cash=Decimal("500000"))
        assert p.total_cash() == Decimal("500000")

    def test_total_cash_multi_currency(self):
        p = Portfolio(cash=Decimal("0"), base_currency="TWD")
        p.cash_by_currency = {"TWD": Decimal("3000000"), "USD": Decimal("10000")}
        fx = {("USD", "TWD"): Decimal("31")}
        total = p.total_cash(fx)
        assert total == Decimal("3000000") + Decimal("10000") * Decimal("31")

    def test_total_cash_no_fx_fallback(self):
        """無匯率時假設 1:1。"""
        p = Portfolio(cash=Decimal("0"))
        p.cash_by_currency = {"TWD": Decimal("100"), "USD": Decimal("50")}
        total = p.total_cash()  # no fx_rates
        assert total == Decimal("150")

    def test_currency_exposure_single(self):
        p = Portfolio(cash=Decimal("1000000"), base_currency="TWD")
        exposure = p.currency_exposure()
        assert exposure["TWD"] == Decimal("1000000")

    def test_currency_exposure_with_positions(self):
        inst_tw = _make_instrument("2330.TW", "TWD")
        inst_us = _make_instrument("AAPL", "USD")
        p = Portfolio(
            cash=Decimal("500000"),
            base_currency="TWD",
            positions={
                "2330.TW": Position(instrument=inst_tw, quantity=Decimal("1000"), avg_cost=Decimal("600"), market_price=Decimal("650")),
                "AAPL": Position(instrument=inst_us, quantity=Decimal("10"), avg_cost=Decimal("170"), market_price=Decimal("180")),
            },
        )
        exp = p.currency_exposure()
        assert exp["TWD"] == Decimal("500000") + Decimal("1000") * Decimal("650")
        assert exp["USD"] == Decimal("10") * Decimal("180")

    def test_asset_class_weights(self):
        inst_eq = _make_instrument("AAPL", "USD", AssetClass.EQUITY)
        inst_etf = _make_instrument("TLT", "USD", AssetClass.ETF)
        p = Portfolio(
            cash=Decimal("0"),
            positions={
                "AAPL": Position(instrument=inst_eq, quantity=Decimal("100"), avg_cost=Decimal("100"), market_price=Decimal("100")),
                "TLT": Position(instrument=inst_etf, quantity=Decimal("100"), avg_cost=Decimal("100"), market_price=Decimal("100")),
            },
        )
        weights = p.asset_class_weights()
        assert "EQUITY" in weights
        assert "ETF" in weights
        assert weights["EQUITY"] == Decimal("0.5")

    def test_asset_class_weights_empty(self):
        p = Portfolio(cash=Decimal("100"))
        assert p.asset_class_weights() == {}
