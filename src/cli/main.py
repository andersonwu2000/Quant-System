"""
CLI 工具 — 量化交易系統的命令列介面。

用法：
    python -m src.cli.main backtest --strategy momentum --universe 2330.TW 2317.TW
    python -m src.cli.main status
    python -m src.cli.main server
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="quant",
    help="量化交易系統 CLI",
    no_args_is_help=True,
)
console = Console()


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.command()
def backtest(
    strategy: str = typer.Option("momentum", "--strategy", "-s", help="策略名稱"),
    universe: list[str] = typer.Option(
        ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
        "--universe", "-u",
        help="股票池",
    ),
    start: str = typer.Option("2020-01-01", "--start", help="開始日期"),
    end: str = typer.Option("2024-12-31", "--end", help="結束日期"),
    cash: float = typer.Option(10_000_000, "--cash", "-c", help="初始資金"),
    rebalance: str = typer.Option("weekly", "--rebalance", "-r", help="再平衡頻率"),
    slippage: float = typer.Option(5.0, "--slippage", help="滑價 (bps)"),
    validate: bool = typer.Option(False, "--validate", "-v", help="是否執行回測驗證"),
    log_level: str = typer.Option("INFO", "--log-level", "-l"),
):
    """執行回測。"""
    _setup_logging(log_level)

    from src.backtest.engine import BacktestConfig, BacktestEngine

    # 解析策略
    strat = _resolve_strategy(strategy)

    config = BacktestConfig(
        universe=universe,
        start=start,
        end=end,
        initial_cash=cash,
        rebalance_freq=rebalance,
        slippage_bps=slippage,
    )

    console.print(f"\n[bold]Running backtest: {strategy}[/bold]")
    console.print(f"Universe: {', '.join(universe)}")
    console.print(f"Period: {start} ~ {end}")
    console.print(f"Initial cash: ${cash:,.0f}\n")

    engine = BacktestEngine()
    result = engine.run(strat, config)

    # 顯示結果
    console.print(f"\n[bold green]{result.summary()}[/bold green]\n")

    # 可選驗證
    if validate:
        from src.backtest.validation import validate_backtest
        validation = validate_backtest(result)
        console.print(validation.summary())

    return result


@app.command()
def server(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(False, "--reload"),
    log_level: str = typer.Option("INFO", "--log-level", "-l"),
):
    """啟動 API 伺服器。"""
    _setup_logging(log_level)
    import uvicorn
    console.print(f"[bold]Starting API server at http://{host}:{port}[/bold]")
    console.print("Docs: http://localhost:{port}/docs")
    uvicorn.run(
        "src.api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level.lower(),
    )


@app.command()
def status():
    """顯示系統狀態。"""
    _setup_logging("WARNING")

    table = Table(title="Quant Trading System Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Detail")

    from src.config import get_config
    config = get_config()

    table.add_row("Mode", config.mode, "")
    table.add_row("Data Source", config.data_source, "")
    table.add_row("API", f"{config.api_host}:{config.api_port}", "")
    table.add_row("Log Level", config.log_level, "")
    table.add_row("Commission", f"{config.commission_rate:.4%}", "")
    table.add_row("Max Position", f"{config.max_position_pct:.0%}", "")
    table.add_row("Max Daily DD", f"{config.max_daily_drawdown_pct:.0%}", "")

    console.print(table)


@app.command()
def factors(
    symbol: str = typer.Argument(help="股票代號"),
    lookback: int = typer.Option(252, "--lookback", "-l"),
):
    """計算並顯示因子值。"""
    _setup_logging("WARNING")

    from src.data.sources.yahoo import YahooFeed
    from src.strategy import factors as f

    console.print(f"[bold]Fetching data for {symbol}...[/bold]")
    feed = YahooFeed()
    bars = feed.get_bars(symbol)

    if bars.empty:
        console.print("[red]No data available[/red]")
        return

    table = Table(title=f"Factors for {symbol}")
    table.add_column("Factor", style="cyan")
    table.add_column("Value", style="yellow")

    mom = f.momentum(bars, lookback=lookback)
    if not mom.empty:
        table.add_row("Momentum (12-1)", f"{mom['momentum']:.4f}")

    mr = f.mean_reversion(bars, lookback=20)
    if not mr.empty:
        table.add_row("Mean Reversion (Z)", f"{mr['z_score']:.4f}")

    vol = f.volatility(bars, lookback=20)
    if not vol.empty:
        table.add_row("Volatility (20d ann.)", f"{vol['volatility']:.4f}")

    _rsi = f.rsi(bars, period=14)
    if not _rsi.empty:
        table.add_row("RSI (14)", f"{_rsi['rsi']:.2f}")

    mac = f.moving_average_crossover(bars, fast=10, slow=50)
    if not mac.empty:
        table.add_row("MA Cross (10/50)", f"{mac['ma_cross']:.4f}")

    console.print(table)
    console.print(f"\nData: {len(bars)} bars, last: {bars.index[-1]}")


def _resolve_strategy(name: str):
    """根據名稱解析策略。"""
    from strategies.momentum import MomentumStrategy
    from strategies.mean_reversion import MeanReversionStrategy

    mapping = {
        "momentum": MomentumStrategy,
        "momentum_12_1": MomentumStrategy,
        "mean_reversion": MeanReversionStrategy,
    }

    cls = mapping.get(name)
    if cls is None:
        console.print(f"[red]Unknown strategy: {name}[/red]")
        console.print(f"Available: {', '.join(mapping.keys())}")
        raise typer.Exit(1)

    return cls()


if __name__ == "__main__":
    app()
