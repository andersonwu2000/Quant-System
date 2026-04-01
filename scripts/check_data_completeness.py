
import sqlite3
from datetime import date
from src.data.master import SecuritiesMaster
from src.data.quality_gate import pre_trade_quality_gate
import pandas as pd

def check_data_completeness():
    # 1. Connect to DB and get active symbols
    from sqlalchemy import create_engine
    engine = create_engine('sqlite:///data/quant.db')
    master = SecuritiesMaster(engine)
    active_symbols = master.active_symbols()
    all_symbols = [s.symbol for s in master.list_all()]
    print(f"Total symbols in DB: {len(all_symbols)}")
    print(f"Active symbols in DB: {len(active_symbols)}")
    
    # 2. Run quality gate on active symbols
    # Use a recent date as reference (2026-03-31)
    ref_date = date(2026, 3, 31)
    print(f"Running quality gate with reference date: {ref_date}")
    
    result = pre_trade_quality_gate(active_symbols, reference_date=ref_date)
    
    print("\n--- Quality Gate Results ---")
    print(f"Passed: {result.passed}")
    print(f"Universe Size: {result.universe_size}")
    print(f"Freshest Date: {result.freshest_date}")
    
    for check in result.checks:
        print(f"Check {check.name}: {'PASS' if check.passed else 'FAIL'} - {check.detail}")
    
    if result.blocking:
        print(f"Blocking Issues: {result.blocking}")
    
    if result.warnings:
        print(f"Warnings (first 5): {result.warnings[:5]}")
        
    # 3. Check specific datasets coverage
    from src.data.registry import REGISTRY, parquet_path
    
    datasets = ["revenue", "financial_statement", "institutional"]
    print("\n--- Dataset Coverage (Active Symbols) ---")
    for ds_name in datasets:
        found = 0
        for sym in active_symbols:
            p = parquet_path(sym, ds_name)
            if p.exists() and p.stat().st_size > 100:
                found += 1
        print(f"{ds_name:20}: {found}/{len(active_symbols)} ({found/len(active_symbols):.1%})")

    conn.close()

if __name__ == "__main__":
    check_data_completeness()
