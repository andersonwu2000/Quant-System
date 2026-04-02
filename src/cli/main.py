"""
CLI 工具 — 量化交易系統的命令列介面。

用法：
    python -m src.cli.main backtest --strategy momentum --universe 2330.TW 2317.TW
    python -m src.cli.main status
    python -m src.cli.main server
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional, cast

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
    report: Optional[str] = typer.Option(None, "--report", help="生成 HTML 報告（指定輸出路徑）"),
    export_trades: Optional[str] = typer.Option(None, "--export-trades", help="匯出交易明細 CSV"),
    benchmark: Optional[str] = typer.Option(None, "--benchmark", "-b", help="基準指數代碼（如 SPY, 0050.TW）"),
    log_level: str = typer.Option("INFO", "--log-level", "-l"),
) -> None:
    """執行回測。"""
    _setup_logging(log_level)

    from src.backtest.engine import BacktestConfig, BacktestEngine
    from src.strategy.registry import resolve_strategy

    # 解析策略
    try:
        strat = resolve_strategy(strategy)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    config = BacktestConfig(
        universe=universe,
        start=start,
        end=end,
        initial_cash=cash,
        rebalance_freq=cast(Literal["daily", "weekly", "monthly"], rebalance),
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

    # 匯出交易明細
    if export_trades:
        from src.backtest.report import export_trades_csv
        export_trades_csv(result, export_trades)
        console.print(f"[green]Trades exported to {export_trades}[/green]")

    # 基準比較
    bench_comparison = None
    if benchmark:
        from src.data.data_catalog import get_catalog
        from src.backtest.report import compare_with_benchmark
        import pandas as pd
        console.print(f"[bold]Loading benchmark: {benchmark}...[/bold]")
        _cat = get_catalog()
        bench_bars = _cat.get("price", benchmark)
        if not bench_bars.empty and not isinstance(bench_bars.index, pd.DatetimeIndex):
            bench_bars.index = pd.to_datetime(bench_bars.index)
        if not bench_bars.empty and start:
            bench_bars = bench_bars[bench_bars.index >= pd.Timestamp(start)]
        if not bench_bars.empty and end:
            bench_bars = bench_bars[bench_bars.index <= pd.Timestamp(end)]
        if not bench_bars.empty:
            bench_nav = bench_bars["close"]
            bench_comparison = compare_with_benchmark(result, bench_nav, benchmark)
            rel = bench_comparison.get("relative", {})
            console.print(f"  Excess Return: {rel.get('excess_return', 0):+.2%}")
            console.print(f"  Info Ratio:    {rel.get('information_ratio', 0):.2f}")
            console.print(f"  Alpha:         {rel.get('alpha', 0):+.2%}")
            console.print(f"  Beta:          {rel.get('beta', 0):.2f}\n")
        else:
            console.print(f"[yellow]No benchmark data for {benchmark}[/yellow]")

    # 生成 HTML 報告
    if report:
        from src.backtest.report import generate_html_report
        generate_html_report(result, benchmark_comparison=bench_comparison, output_path=report)
        console.print(f"[green]HTML report saved to {report}[/green]")



@app.command()
def server(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(False, "--reload"),
    log_level: str = typer.Option("INFO", "--log-level", "-l"),
) -> None:
    """啟動 API 伺服器。"""
    _setup_logging(log_level)
    import uvicorn
    console.print(f"[bold]Starting API server at http://{host}:{port}[/bold]")
    console.print(f"Docs: http://localhost:{port}/docs")
    uvicorn.run(
        "src.api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level.lower(),
    )


@app.command()
def status() -> None:
    """顯示系統狀態。"""
    _setup_logging("WARNING")

    table = Table(title="Quant Trading System Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Detail")

    from src.core.config import get_config
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
) -> None:
    """計算並顯示因子值。"""
    _setup_logging("WARNING")

    from src.data.data_catalog import get_catalog
    from src.strategy import factors as f
    import pandas as pd

    console.print(f"[bold]Loading data for {symbol}...[/bold]")
    _cat = get_catalog()
    bars = _cat.get("price", symbol)
    if not bars.empty and not isinstance(bars.index, pd.DatetimeIndex):
        bars.index = pd.to_datetime(bars.index)

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

    rev = f.short_term_reversal(bars, lookback=5)
    if not rev.empty:
        table.add_row("Reversal (5d)", f"{rev['reversal']:.4f}")

    illiq = f.amihud_illiquidity(bars, lookback=20)
    if not illiq.empty:
        table.add_row("Illiquidity (Amihud)", f"{illiq['illiquidity']:.6e}")

    skew = f.skewness(bars, lookback=60)
    if not skew.empty:
        table.add_row("Skewness (60d)", f"{skew['skew']:.4f}")

    maxr = f.max_return(bars, lookback=20)
    if not maxr.empty:
        table.add_row("Max Return (20d)", f"{maxr['max_ret']:.4f}")

    console.print(table)
    console.print(f"\nData: {len(bars)} bars, last: {bars.index[-1]}")


@app.command(name="factor-analysis")
def factor_analysis(
    factor: str = typer.Option("momentum", "--factor", "-f", help="因子名稱"),
    universe: list[str] = typer.Option(
        ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
        "--universe", "-u",
        help="股票池",
    ),
    start: str = typer.Option("2022-01-01", "--start", help="開始日期"),
    end: str = typer.Option("2024-12-31", "--end", help="結束日期"),
    horizon: int = typer.Option(5, "--horizon", "-h", help="報酬週期（交易日）"),
    decay: bool = typer.Option(False, "--decay", "-d", help="執行因子衰減分析"),
    log_level: str = typer.Option("WARNING", "--log-level", "-l"),
) -> None:
    """因子研究分析。"""
    _setup_logging(log_level)

    from src.data.data_catalog import get_catalog
    from src.strategy.research import (
        FACTOR_REGISTRY,
        analyze_factor,
        factor_decay as run_decay,
    )

    available = list(FACTOR_REGISTRY.keys())
    if factor not in FACTOR_REGISTRY:
        console.print(f"[red]Unknown factor: {factor}[/red]")
        console.print(f"Available: {', '.join(available)}")
        raise typer.Exit(1)

    console.print(f"\n[bold]Factor Analysis: {factor}[/bold]")
    console.print(f"Universe: {', '.join(universe)}")
    console.print(f"Period: {start} ~ {end}, Horizon: {horizon}d\n")

    # 載入數據
    import pandas as pd
    _cat = get_catalog()
    warmup_start = (pd.Timestamp(start) - pd.tseries.offsets.BDay(400)).strftime("%Y-%m-%d")
    data: dict[str, Any] = {}
    for sym in universe:
        bars = _cat.get("price", sym)
        if not bars.empty:
            if not isinstance(bars.index, pd.DatetimeIndex):
                bars.index = pd.to_datetime(bars.index)
            bars = bars[bars.index >= pd.Timestamp(warmup_start)]
            bars = bars[bars.index <= pd.Timestamp(end)]
            if not bars.empty:
                data[sym] = bars
                console.print(f"  Loaded {len(bars)} bars for {sym}")
        else:
            console.print(f"  [yellow]No data for {sym}[/yellow]")

    if len(data) < 3:
        console.print("[red]Need at least 3 symbols with data[/red]")
        raise typer.Exit(1)

    # IC 分析
    ic_result = analyze_factor(data, factor, horizon=horizon)
    console.print(f"\n{ic_result.summary()}")

    # 衰減分析
    if decay:
        console.print()
        decay_result = run_decay(data, factor)
        console.print(decay_result.summary())

    console.print()


@app.command()
def autostart(
    action: str = typer.Argument(..., help="install / uninstall / status"),
) -> None:
    """管理盤前自動啟動排程（Windows Task Scheduler）。"""
    import scripts.autostart as _auto
    if action == "install":
        _auto.install()
    elif action == "uninstall":
        _auto.uninstall()
    elif action == "status":
        _auto.status()
    else:
        console.print("[red]Unknown action. Use: install / uninstall / status[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
