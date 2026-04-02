"""Market channel bootstrap — quote manager, realtime risk, price polling."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.config import Config
    from src.api.websocket import WebSocketManager

logger = logging.getLogger(__name__)


def setup_market_feed(state: Any, config: Config, ws_manager: WebSocketManager) -> None:
    """Set up quote manager, realtime risk monitor, and price polling fallback.

    Only runs in paper/live mode. Called from lifespan after execution service init.
    Modifies state in place: sets state.realtime_risk_monitor, state.quote_manager.
    """
    from src.execution.broker.sinopac import SinopacBroker
    from src.execution.quote.sinopac import SinopacQuoteManager, TickData
    from src.risk.realtime import RealtimeRiskMonitor

    loop = asyncio.get_running_loop()

    # LT-7: set_portfolio BEFORE initialize (connect may trigger fill callbacks)
    # Pass mutation_lock so async fills don't race with API rebalance
    state.execution_service.set_portfolio(state.portfolio, loop, state.mutation_lock)

    state.execution_service.initialize()
    logger.info("ExecutionService initialized: mode=%s", config.mode)

    broker = state.execution_service.broker
    quote_manager: SinopacQuoteManager | None = None

    if isinstance(broker, SinopacBroker) and broker.api is not None:
        quote_manager = SinopacQuoteManager(broker.api)
        quote_manager.set_event_loop(loop)

        # Broadcast ticks to WebSocket market channel
        _qm = quote_manager  # bind for closure (always non-None here)

        async def _ws_broadcast_tick(tick_data: TickData) -> None:
            payload = _qm.to_ws_payload(tick_data)
            await ws_manager.broadcast("market", payload)

        quote_manager.set_broadcast_callback(_ws_broadcast_tick, loop)

        # Subscribe to current portfolio positions
        for symbol in list(state.portfolio.positions.keys()):
            quote_manager.subscribe(symbol)

        logger.info(
            "Market channel: SinopacQuoteManager connected, %d symbols subscribed",
            len(state.portfolio.positions),
        )

    # Realtime risk monitor
    realtime_risk = RealtimeRiskMonitor(
        portfolio=state.portfolio,
        risk_engine=state.risk_engine,
        ws_manager=ws_manager,
        loop=loop,
        execution_service=state.execution_service,
        app_state=state,
        mode=config.mode,
    )
    state.realtime_risk_monitor = realtime_risk

    if quote_manager is not None:
        # Register price update callback for risk monitoring
        def _risk_on_tick(tick_data: TickData) -> None:
            realtime_risk.on_price_update(tick_data.symbol, tick_data.price)

        quote_manager.on_tick(_risk_on_tick)

    state.quote_manager = quote_manager

    # Fallback: poll prices when ticks are unavailable.
    # Shioaji simulation mode has quote_manager but doesn't push ticks,
    # so we also enable polling in simulation mode.
    is_simulation = False
    if isinstance(broker, SinopacBroker):
        is_simulation = getattr(broker, "simulation", False)
    elif getattr(state.execution_service, '_fallback_mode', False):
        is_simulation = True

    if quote_manager is None or is_simulation:
        # P4: Simulation mode uses ShioajiFeed.snapshot for realtime prices (not Yahoo close)
        _poll_feed_source: Any = None
        if is_simulation and isinstance(broker, SinopacBroker) and broker.api is not None:
            try:
                from src.data.sources.shioaji_feed import ShioajiFeed
                _poll_feed_source = ShioajiFeed(broker.api)
                logger.info("Price polling: using ShioajiFeed (snapshot API)")
            except Exception:
                # expected: ShioajiFeed init failure (simulation mode, no live API)
                logger.debug("ShioajiFeed init failed, falling back to config feed", exc_info=True)

        from src.data.data_catalog import get_catalog
        from src.data.feed import HistoricalFeed
        import pandas as pd

        def _build_catalog_feed(symbols: list[str]) -> HistoricalFeed:
            catalog = get_catalog()
            feed = HistoricalFeed()
            for sym in symbols:
                df = catalog.get("price", sym)
                if not df.empty:
                    if not isinstance(df.index, pd.DatetimeIndex):
                        df.index = pd.to_datetime(df.index)
                    feed.load(sym, df)
            return feed

        async def _price_poll_loop() -> None:
            """Poll latest prices every 60s when ticks unavailable."""
            _cached_feed = _poll_feed_source
            _cached_syms: list[str] = []
            while True:
                await asyncio.sleep(60)
                try:
                    syms = sorted(state.portfolio.positions.keys())
                    if not syms:
                        continue
                    # If no ShioajiFeed, fallback to catalog feed
                    if _cached_feed is None or syms != _cached_syms:
                        if _poll_feed_source is not None:
                            _cached_feed = _poll_feed_source
                        else:
                            _cached_feed = _build_catalog_feed(syms)
                        _cached_syms = syms
                    if _cached_feed is not None:
                        n_updated = realtime_risk.poll_prices_from_feed(_cached_feed)
                        # ShioajiFeed failure -> fallback to catalog feed
                        if n_updated == 0 and _poll_feed_source is not None and _cached_feed is _poll_feed_source:
                            logger.warning("ShioajiFeed returned 0 prices — falling back to catalog")
                            _cached_feed = _build_catalog_feed(syms)
                            _cached_syms = syms
                            if _cached_feed is not None:
                                realtime_risk.poll_prices_from_feed(_cached_feed, realtime=False)
                except Exception:
                    # expected: external API failure (price feed)
                    logger.warning("Price poll failed", exc_info=True)

        asyncio.create_task(_price_poll_loop())
        logger.info("Price polling fallback started (60s interval)")
