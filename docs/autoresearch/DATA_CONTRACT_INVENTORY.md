# Data Contract Inventory — AutoResearch / AutoAlpha Pipeline

All data assembly points in the pipeline, documenting call chains, datasets, PIT masking, key naming, and caching.

## 1. evaluate.py (Factor Evaluation Harness)

| Aspect | Detail |
|--------|--------|
| **Call chain** | `main()` -> `_load_all_data(universe)` -> `DataCatalog(PROJECT_ROOT/"data").get(ds_name, sym)` for each dataset in `REGISTRY` |
| **Datasets** | All datasets from `src/data/registry.REGISTRY`: price (-> `bars`), revenue, per (-> `per_history`), institutional, margin, shareholding, securities_lending, day_trading, dividend, income_statement, cash_flow, balance_sheet. Disabled: pe, pb, roe, market_cap (empty dicts, look-ahead bias). |
| **PIT masking** | `_mask_data(data, as_of)` reads `pit_delay_days` from REGISTRY per dataset. Price: `.loc[:as_of]` (0-day delay). Revenue: 40-day delay. Income/balance/cash_flow: 45-90 days. Others: 0 days. Applied at every IC sampling date. |
| **Key naming** | Bare symbols from `data/research/universe.txt` (e.g. `2330.TW`). Universe file determines format. |
| **Cache** | Module-level `_data_cache` (dict). Built once on first call, reused for all IC dates. Stage 2 large-scale incrementally appends new symbols to same cache. `_close_matrix` (DataFrame) also module-level for vectorized forward returns. |

**Stage 2 (large-scale)**: Extends `_data_cache["bars"]` with additional symbols from `large_universe.txt` (865+). Only loads price bars for new symbols; reuses other datasets from Stage 1 cache.

## 2. strategy_builder.py (Auto Strategy Builder)

| Aspect | Detail |
|--------|--------|
| **Call chain** | `build_from_research_factor()` -> creates `ResearchFactorStrategy.on_bar()` -> calls `ctx.bars()`, `ctx.get_revenue()`, `ctx.get_institutional()`, `ctx.get_per_history()`, `ctx.get_margin()` per symbol -> each method calls `DataCatalog.get()` |
| **Datasets** | bars, revenue, institutional, per_history, margin. Also stubs pe, pb, roe as empty dicts in `_data` bundle. |
| **PIT masking** | Delegated to `Context` methods. `ctx.bars()` truncates to `ctx.now()`. `ctx.get_revenue()` applies 40-day delay via `_as_of_naive() - DateOffset(days=40)`. `get_per_history/institutional/margin` truncate to `_as_of_naive()` (0-day delay). |
| **Key naming** | Uses whatever symbols `ctx.universe()` returns (from `DataFeed`). In backtest, these are suffixed (e.g. `2330.TW`). |
| **Cache** | Per-strategy month-level cache (`_last_month` / `_cached` on strategy instance). No cross-call data cache; each `on_bar` re-reads from Context. |

## 3. deployed_executor.py (Paper Trading Executor)

| Aspect | Detail |
|--------|--------|
| **Call chain** | `_execute_single()` -> `_load_data_for_universe(universe)` -> `get_catalog().get(ds_name, sym)` per dataset per symbol |
| **Datasets** | bars (price), revenue, institutional, per_history (via `catalog.get("per")`), margin. Stubs pe, pb, roe as empty dicts. |
| **PIT masking** | Explicit in `_execute_single()`: bars `.loc[:as_of]`, revenue `date <= as_of - 40 days`, institutional/per_history/margin `date <= as_of`. Hardcoded 40-day delay (does NOT read REGISTRY). |
| **Key naming** | Suffixed `.TW` symbols. Universe built from `catalog.available_symbols("price")`, filtered to `.TW` only, excludes ETFs (`00xx`), capped at 200. |
| **Cache** | No persistent cache. `_load_data_for_universe()` is called fresh each execution. |

## 4. base.py — Context (Strategy Data Interface)

| Aspect | Detail |
|--------|--------|
| **Call chain** | `Context.__init__(feed, portfolio, current_time, fundamentals_provider)`. Each getter calls `DataCatalog.get()` internally. |
| **Datasets** | `bars()` -> `feed.get_bars()`. `get_revenue()` -> `catalog.get("revenue")`. `get_per_history()` -> `catalog.get("per")`. `get_institutional()` -> `catalog.get("institutional")`. `get_margin()` -> `catalog.get("margin")`. `fundamentals()` -> `FundamentalsProvider.get_financials()`. |
| **PIT masking** | `bars()`: truncates index to `<= current_time`. `get_revenue()`: 40-day delay hardcoded (`_as_of_naive() - DateOffset(days=40)`). `get_per_history/institutional/margin`: truncates to `_as_of_naive()` (0-day delay). Does NOT read REGISTRY pit_delay_days. |
| **Key naming** | Accepts whatever symbol string is passed. No normalization. |
| **Cache** | None at Context level. Each call hits DataCatalog (which has its own caching). |

## 5. validator.py (StrategyValidator)

| Aspect | Detail |
|--------|--------|
| **Call chain** | `validate()` -> `_build_catalog_feed(universe)` -> `get_catalog().get("price", sym)` -> feeds into `HistoricalFeed` -> passed to `BacktestEngine.run(feed_override=...)`. Strategy's `on_bar(ctx)` then reads via Context. |
| **Datasets** | Only price bars loaded directly by Validator (into `HistoricalFeed`). Revenue/per/institutional/margin loaded lazily by the Strategy via Context during backtest. Benchmark: `_load_0050()` loads `0050.TW` price from catalog. |
| **PIT masking** | Price: BacktestEngine's SimContext sets `current_time`, Context.bars() truncates. Revenue/fundamentals: delegated to Context methods (40-day delay for revenue, 0 for others). Validator itself does not apply PIT masking. |
| **Key naming** | Suffixed `.TW` symbols. Universe passed in by caller (evaluate.py or API). |
| **Cache** | `_shared_feed` stored on Validator instance, reused across full backtest + walk-forward + OOS runs within one `validate()` call. Rebuilt per `validate()` call. |

## 6. auto_alpha.py — POST /submit-factor (API Submission)

| Aspect | Detail |
|--------|--------|
| **Call chain** | `submit_factor()` -> saves code to `src/strategy/factors/research/{name}.py` -> `build_from_research_factor()` -> `StrategyValidator.validate()` -> if passed, `PaperDeployer.deploy()` |
| **Datasets** | Universe scanned via `get_catalog().available_symbols("price")`. Filters to `.TW`, excludes ETFs, caps at 200, requires >= 500 bars. Actual data loading delegated to Validator (price) and Strategy/Context (revenue, per, etc.). |
| **PIT masking** | No direct masking. Entirely delegated to Validator -> BacktestEngine -> Context chain. |
| **Key naming** | Suffixed `.TW`. Factor name sanitized to valid Python identifier. |
| **Cache** | None. Each submission runs fresh. |

## PIT Delay Summary

| Dataset | REGISTRY pit_delay_days | evaluate.py _mask_data | Context methods | deployed_executor.py |
|---------|------------------------|------------------------|-----------------|---------------------|
| price | 0 | 0 (via REGISTRY) | 0 (truncate to now) | 0 (.loc[:as_of]) |
| revenue | 40 | 40 (via REGISTRY) | 40 (hardcoded) | 40 (hardcoded) |
| per | 0 | 0 (via REGISTRY) | 0 | 0 |
| institutional | 0 | 0 (via REGISTRY) | 0 | 0 |
| margin | 0 | 0 (via REGISTRY) | 0 | 0 |
| income_statement | 45 | 45 (via REGISTRY) | N/A | N/A |
| balance_sheet | 90 | 90 (via REGISTRY) | N/A | N/A |
| cash_flow | 90 | 90 (via REGISTRY) | N/A | N/A |

**Key inconsistency**: evaluate.py reads `pit_delay_days` from REGISTRY (single source of truth). Context and deployed_executor hardcode the 40-day revenue delay instead of reading REGISTRY. If REGISTRY changes, those two paths will diverge.

## Cache Topology

```
evaluate.py          strategy_builder.py     deployed_executor.py
    |                       |                        |
_data_cache (module)   per-month (instance)     none (fresh each run)
    |                       |                        |
    +--- _close_matrix      +--- Context             +--- DataCatalog
         (module)                |                        |
                                DataCatalog              DataCatalog
```

All paths ultimately read from `DataCatalog`, which resolves to local parquet files under `data/market/`.
