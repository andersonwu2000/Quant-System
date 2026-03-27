"""FinMind 數據批量下載腳本 — 下載基本面 + 籌碼面數據到本地 Parquet。

用法:
    python -m scripts.download_finmind_data --dataset all --start 2019-01-01
    python -m scripts.download_finmind_data --dataset balance_sheet --symbols 2330 2317
    python -m scripts.download_finmind_data --dataset institutional --symbols-file data/tw50_symbols.txt
    python -m scripts.download_finmind_data --symbols-from-market --force
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import get_config
from src.data.sources.finmind_common import get_dataloader, strip_tw_suffix, ensure_tw_suffix

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# 預設 universe: TW50 成分股（排除 ETF）
TW50_SYMBOLS = [
    "1101", "1216", "1301", "1303", "1326", "1402",
    "2002", "2207", "2301", "2303", "2308", "2317",
    "2327", "2330", "2345", "2357", "2379", "2382",
    "2395", "2408", "2412", "2454", "2474", "2603",
    "2609", "2615", "2801", "2880", "2881", "2882",
    "2883", "2884", "2885", "2886", "2887", "2890",
    "2891", "2892", "2912", "3008", "3034", "3037",
    "3045", "3231", "3443", "3711", "4904", "5871",
    "5876", "5880", "6505",
]

FUND_DIR = Path("data/fundamental")
MARKET_DIR = Path("data/market")

# FinMind 免費 600 req/hr → ~0.6s/req 安全間隔
REQUEST_DELAY = 0.7

# 支援的數據集
DATASETS = {
    "balance_sheet": {
        "method": "taiwan_stock_financial_statement",
        "desc": "資產負債表 / 財務報表（EPS, ROE, 營收, 資產等）",
        "suffix": "financial_statement",
    },
    "per": {
        "method": "taiwan_stock_per_pbr",
        "desc": "本益比 / 淨值比（每日）",
        "suffix": "per",
    },
    "revenue": {
        "method": "taiwan_stock_month_revenue",
        "desc": "月營收",
        "suffix": "revenue",
    },
    "institutional": {
        "method": "taiwan_stock_institutional_investors",
        "desc": "三大法人買賣超（外資/投信/自營商）",
        "suffix": "institutional",
    },
    "margin": {
        "method": "taiwan_stock_margin_purchase_short_sale",
        "desc": "融資融券餘額",
        "suffix": "margin",
    },
    "shareholding": {
        "method": "taiwan_stock_shareholding",
        "desc": "董監持股",
        "suffix": "shareholding",
    },
    "day_trading": {
        "method": "taiwan_stock_day_trading",
        "desc": "當沖資訊",
        "suffix": "daytrading",
    },
    "dividend": {
        "method": "taiwan_stock_dividend",
        "desc": "股利發放",
        "suffix": "dividend",
    },
    "price": {
        "method": "taiwan_stock_daily",
        "desc": "日線 OHLCV（含已下市股票，修復倖存者偏差）",
        "suffix": "1d",
        "output_dir": "data/market",  # 存到 market/ 而非 fundamental/
    },
}


def download_dataset(
    dl: object,
    dataset_key: str,
    symbols: list[str],
    start: str,
    end: str,
    *,
    force: bool = False,
) -> int:
    """下載單一數據集的所有股票。

    Returns:
        成功下載的股票數。
    """
    ds = DATASETS[dataset_key]
    method_name = ds["method"]
    suffix = ds["suffix"]
    method = getattr(dl, method_name, None)
    if method is None:
        logger.error("FinMind DataLoader 沒有方法: %s", method_name)
        return 0

    # price dataset 存到 data/market/，其他存到 data/fundamental/
    out_dir = Path(ds.get("output_dir", str(FUND_DIR)))
    out_dir.mkdir(parents=True, exist_ok=True)
    success = 0
    skipped = 0

    for i, sym in enumerate(symbols):
        bare = strip_tw_suffix(sym)
        tw_sym = ensure_tw_suffix(sym)
        out_path = out_dir / f"{tw_sym}_{suffix}.parquet"

        # 本地已有就跳過（除非 --force）
        if out_path.exists() and not force:
            try:
                existing = pd.read_parquet(out_path)
                if not existing.empty and len(existing) > 10:
                    skipped += 1
                    continue
            except Exception:
                pass  # 損壞的檔案，重新下載

        logger.info(
            "[%d/%d] 下載 %s %s ...",
            i + 1, len(symbols), bare, ds["desc"],
        )

        try:
            time.sleep(REQUEST_DELAY)
            df = method(stock_id=bare, start_date=start, end_date=end)

            if df is None or df.empty:
                logger.warning("  %s: 無數據", bare)
                continue

            # Price dataset: normalize columns to match Yahoo format
            if dataset_key == "price":
                col_map = {"max": "high", "min": "low", "Trading_Volume": "volume"}
                df = df.rename(columns=col_map)
                keep_cols = [c for c in ["date", "open", "high", "low", "close", "volume"] if c in df.columns]
                df = df[keep_cols]
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date").sort_index()
                # 去 timezone
                if hasattr(df.index, "tz") and df.index.tz is not None:
                    df.index = df.index.tz_localize(None)

            # Price dataset: merge with existing data (don't lose history)
            if dataset_key == "price" and out_path.exists():
                try:
                    existing = pd.read_parquet(out_path)
                    if not existing.empty:
                        merged = pd.concat([existing, df])
                        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
                        df = merged
                except Exception:
                    pass  # 合併失敗就用新數據覆蓋

            df.to_parquet(out_path)
            logger.info("  %s: %d 列 → %s", bare, len(df), out_path)
            success += 1

        except Exception as e:
            logger.error("  %s: 失敗 %s", bare, e)
            # Rate limit handling
            if "429" in str(e) or "Too Many" in str(e):
                logger.warning("Rate limited, waiting 60s...")
                time.sleep(60)

    logger.info(
        "%s 完成: %d 成功, %d 跳過 (已有), %d 失敗",
        dataset_key, success, skipped,
        len(symbols) - success - skipped,
    )
    return success


def main() -> None:
    parser = argparse.ArgumentParser(description="FinMind 數據批量下載")
    parser.add_argument(
        "--dataset",
        choices=list(DATASETS.keys()) + ["all"],
        default="all",
        help="要下載的數據集 (default: all)",
    )
    parser.add_argument(
        "--symbols",
        nargs="*",
        help="股票代碼列表 (e.g. 2330 2317)，預設 TW50",
    )
    parser.add_argument("--start", default="2019-01-01", help="起始日期")
    parser.add_argument("--end", default="2025-12-31", help="結束日期")
    parser.add_argument("--dry-run", action="store_true", help="只顯示計畫不下載")
    parser.add_argument(
        "--symbols-from-market",
        action="store_true",
        help="從 data/market/*.parquet 自動發現台股代碼",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="強制重新下載，即使本地已有檔案",
    )
    args = parser.parse_args()

    # Resolve symbols: explicit --symbols > --symbols-from-market > TW50 default
    if args.symbols:
        symbols = args.symbols
    elif args.symbols_from_market:
        discovered = sorted({
            p.stem.split(".TW")[0]
            for p in MARKET_DIR.glob("*.parquet")
            if ".TW" in p.stem
        })
        if not discovered:
            logger.error("data/market/ 中找不到 *.TW.parquet 檔案")
            sys.exit(1)
        symbols = discovered
        logger.info("從 data/market/ 發現 %d 支台股: %s ...", len(symbols), symbols[:5])
    else:
        symbols = TW50_SYMBOLS
    symbols = [strip_tw_suffix(s) for s in symbols]

    # Resolve datasets
    if args.dataset == "all":
        datasets = list(DATASETS.keys())
    else:
        datasets = [args.dataset]

    # Summary
    total_requests = len(symbols) * len(datasets)
    est_time = total_requests * REQUEST_DELAY / 60
    print(f"計畫: {len(symbols)} 支股票 × {len(datasets)} 數據集 = {total_requests} 請求")
    print(f"預估時間: {est_time:.0f} 分鐘")
    print(f"數據集: {datasets}")
    print(f"期間: {args.start} ~ {args.end}")
    print(f"存儲: {FUND_DIR}/")
    print()

    if args.dry_run:
        for ds in datasets:
            print(f"  {ds}: {DATASETS[ds]['desc']}")
        return

    # Get FinMind token
    config = get_config()
    token = config.finmind_token
    if not token:
        logger.warning("未設定 QUANT_FINMIND_TOKEN，使用免費額度 (600 req/hr)")

    dl = get_dataloader(token)
    print(f"FinMind DataLoader 已初始化 (token: {'有' if token else '無'})")
    print()

    total_success = 0
    for ds_key in datasets:
        print(f"=== {ds_key}: {DATASETS[ds_key]['desc']} ===")
        n = download_dataset(dl, ds_key, symbols, args.start, args.end, force=args.force)
        total_success += n
        print()

    print(f"全部完成: {total_success} 個檔案已下載到 {FUND_DIR}/")


if __name__ == "__main__":
    main()
