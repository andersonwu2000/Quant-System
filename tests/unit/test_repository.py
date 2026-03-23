"""Tests for PortfolioRepository — uses SQLite in-memory."""

from datetime import datetime, timezone
from decimal import Decimal

import sqlalchemy as sa

from src.data.store import metadata
from src.domain.models import Instrument, Portfolio, Position, Side, Trade
from src.domain.repository import PortfolioRepository


def _make_engine() -> sa.Engine:
    """Create an in-memory SQLite engine with all tables."""
    engine = sa.create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    return engine


class TestCreateAndGetPortfolio:
    def test_create_and_get_portfolio(self):
        engine = _make_engine()
        repo = PortfolioRepository(engine)

        pid = repo.create("Test Portfolio", Decimal("5000000"), strategy_name="momentum")
        assert isinstance(pid, str)
        assert len(pid) > 0

        portfolio = repo.get(pid)
        assert portfolio is not None
        assert portfolio.cash == Decimal("5000000")
        assert portfolio.initial_cash == Decimal("5000000")
        assert len(portfolio.positions) == 0

    def test_get_nonexistent_returns_none(self):
        engine = _make_engine()
        repo = PortfolioRepository(engine)
        assert repo.get("nonexistent") is None

    def test_get_meta(self):
        engine = _make_engine()
        repo = PortfolioRepository(engine)

        pid = repo.create("My Portfolio", Decimal("1000000"), strategy_name="mean_reversion")
        meta = repo.get_meta(pid)
        assert meta is not None
        assert meta["name"] == "My Portfolio"
        assert meta["strategy_name"] == "mean_reversion"
        assert meta["created_at"] is not None


class TestSaveAndLoadSnapshot:
    def test_save_and_load_snapshot(self):
        engine = _make_engine()
        repo = PortfolioRepository(engine)

        pid = repo.create("Snapshot Test", Decimal("10000000"))

        # Build a portfolio with positions
        portfolio = Portfolio(
            positions={
                "AAPL": Position(
                    instrument=Instrument(symbol="AAPL"),
                    quantity=Decimal("100"),
                    avg_cost=Decimal("150"),
                    market_price=Decimal("170"),
                ),
                "MSFT": Position(
                    instrument=Instrument(symbol="MSFT"),
                    quantity=Decimal("50"),
                    avg_cost=Decimal("300"),
                    market_price=Decimal("320"),
                ),
            },
            cash=Decimal("8000000"),
            initial_cash=Decimal("10000000"),
        )

        repo.save_snapshot(pid, portfolio)

        # Load it back
        loaded = repo.get(pid)
        assert loaded is not None
        assert loaded.cash == Decimal("8000000")
        assert "AAPL" in loaded.positions
        assert "MSFT" in loaded.positions
        assert loaded.positions["AAPL"].quantity == Decimal("100")
        assert loaded.positions["AAPL"].avg_cost == Decimal("150")
        assert loaded.positions["AAPL"].market_price == Decimal("170")
        assert loaded.positions["MSFT"].quantity == Decimal("50")

    def test_snapshot_upsert_same_date(self):
        engine = _make_engine()
        repo = PortfolioRepository(engine)

        pid = repo.create("Upsert Test", Decimal("5000000"))

        portfolio1 = Portfolio(
            positions={
                "AAPL": Position(
                    instrument=Instrument(symbol="AAPL"),
                    quantity=Decimal("100"),
                    avg_cost=Decimal("150"),
                    market_price=Decimal("160"),
                ),
            },
            cash=Decimal("4000000"),
        )
        repo.save_snapshot(pid, portfolio1)

        # Save again with updated data — same day should upsert
        portfolio2 = Portfolio(
            positions={
                "AAPL": Position(
                    instrument=Instrument(symbol="AAPL"),
                    quantity=Decimal("200"),
                    avg_cost=Decimal("155"),
                    market_price=Decimal("165"),
                ),
            },
            cash=Decimal("3500000"),
        )
        repo.save_snapshot(pid, portfolio2)

        loaded = repo.get(pid)
        assert loaded is not None
        assert loaded.positions["AAPL"].quantity == Decimal("200")
        assert loaded.cash == Decimal("3500000")


class TestRecordAndGetTrades:
    def test_record_and_get_trades(self):
        engine = _make_engine()
        repo = PortfolioRepository(engine)

        pid = repo.create("Trade Test", Decimal("10000000"))

        trade1 = Trade(
            timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            symbol="AAPL",
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("150"),
            commission=Decimal("21.375"),
            slippage_bps=Decimal("5"),
        )
        trade2 = Trade(
            timestamp=datetime(2024, 2, 1, 10, 0, 0, tzinfo=timezone.utc),
            symbol="MSFT",
            side=Side.BUY,
            quantity=Decimal("50"),
            price=Decimal("300"),
            commission=Decimal("21.375"),
            slippage_bps=Decimal("5"),
        )
        trade3 = Trade(
            timestamp=datetime(2024, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
            symbol="AAPL",
            side=Side.SELL,
            quantity=Decimal("50"),
            price=Decimal("170"),
            commission=Decimal("12.1125"),
            slippage_bps=Decimal("5"),
        )

        repo.record_trade(pid, trade1, source="manual")
        repo.record_trade(pid, trade2, source="system")
        repo.record_trade(pid, trade3, source="manual", notes="Partial exit")

        trades = repo.get_trades(pid)
        assert len(trades) == 3
        # Most recent first
        assert trades[0]["symbol"] == "AAPL"
        assert trades[0]["side"] == "SELL"
        assert trades[0]["notes"] == "Partial exit"

    def test_get_trades_with_date_filter(self):
        engine = _make_engine()
        repo = PortfolioRepository(engine)

        pid = repo.create("Filter Test", Decimal("10000000"))

        for month in [1, 2, 3]:
            trade = Trade(
                timestamp=datetime(2024, month, 15, 10, 0, 0, tzinfo=timezone.utc),
                symbol="AAPL",
                side=Side.BUY,
                quantity=Decimal("10"),
                price=Decimal("150"),
                commission=Decimal("2.1375"),
                slippage_bps=Decimal("5"),
            )
            repo.record_trade(pid, trade)

        filtered = repo.get_trades(pid, start="2024-02-01", end="2024-02-28")
        assert len(filtered) == 1

    def test_get_trades_empty(self):
        engine = _make_engine()
        repo = PortfolioRepository(engine)

        pid = repo.create("Empty Trades", Decimal("10000000"))
        trades = repo.get_trades(pid)
        assert trades == []


class TestListPortfolios:
    def test_list_portfolios(self):
        engine = _make_engine()
        repo = PortfolioRepository(engine)

        repo.create("Portfolio A", Decimal("5000000"), strategy_name="momentum")
        repo.create("Portfolio B", Decimal("10000000"), strategy_name="mean_reversion")

        items = repo.list_all()
        assert len(items) == 2
        names = {item["name"] for item in items}
        assert names == {"Portfolio A", "Portfolio B"}

        # Check fields
        for item in items:
            assert "id" in item
            assert "cash" in item
            assert "position_count" in item

    def test_list_empty(self):
        engine = _make_engine()
        repo = PortfolioRepository(engine)
        assert repo.list_all() == []


class TestDeletePortfolioCascades:
    def test_delete_portfolio_cascades(self):
        engine = _make_engine()
        repo = PortfolioRepository(engine)

        pid = repo.create("To Delete", Decimal("10000000"))

        # Add positions
        portfolio = Portfolio(
            positions={
                "AAPL": Position(
                    instrument=Instrument(symbol="AAPL"),
                    quantity=Decimal("100"),
                    avg_cost=Decimal("150"),
                    market_price=Decimal("160"),
                ),
            },
            cash=Decimal("8000000"),
        )
        repo.save_snapshot(pid, portfolio)

        # Add trade
        trade = Trade(
            timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            symbol="AAPL",
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("150"),
            commission=Decimal("21.375"),
            slippage_bps=Decimal("5"),
        )
        repo.record_trade(pid, trade)

        # Delete
        deleted = repo.delete(pid)
        assert deleted is True

        # Verify everything is gone
        assert repo.get(pid) is None
        assert repo.get_trades(pid) == []

        # Verify DB tables are clean
        with engine.connect() as conn:
            snap_count = conn.execute(
                sa.text("SELECT COUNT(*) FROM position_snapshots WHERE portfolio_id = :pid"),
                {"pid": pid},
            ).scalar()
            trade_count = conn.execute(
                sa.text("SELECT COUNT(*) FROM trade_records WHERE portfolio_id = :pid"),
                {"pid": pid},
            ).scalar()
            assert snap_count == 0
            assert trade_count == 0

    def test_delete_nonexistent_returns_false(self):
        engine = _make_engine()
        repo = PortfolioRepository(engine)
        assert repo.delete("nonexistent") is False


class TestUpdateCash:
    def test_update_cash(self):
        engine = _make_engine()
        repo = PortfolioRepository(engine)

        pid = repo.create("Cash Test", Decimal("10000000"))
        repo.update_cash(pid, Decimal("8500000"))

        portfolio = repo.get(pid)
        assert portfolio is not None
        assert portfolio.cash == Decimal("8500000")
