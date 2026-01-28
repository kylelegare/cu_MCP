#!/usr/bin/env python3
"""Apply the fix to cu_with_ratios view in the DuckDB database.

This script fixes the following ratio calculation issues:
1. Delinquency ratio: Now uses 60+ days (acct_021b + acct_022b + acct_023b)
   instead of 6+ months (acct_022b + acct_023b)
2. Coverage ratio: Now uses acct_719 (Allowance for Loan Losses)
   instead of acct_300 (Provision for Loan Losses)
3. Coverage ratio denominator: Now uses 60+ days delinquent loans

Run this script to update the view in your local database:
    python scripts/apply_fix.py
"""

import duckdb
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "cu_data.duckdb"
SQL_PATH = BASE_DIR / "scripts" / "fix_ratios_view.sql"


def main():
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return 1

    if not SQL_PATH.exists():
        print(f"Error: SQL file not found at {SQL_PATH}")
        return 1

    print(f"Connecting to database: {DB_PATH}")

    with duckdb.connect(str(DB_PATH), read_only=False) as conn:
        # Read the SQL file
        sql = SQL_PATH.read_text()

        print("Applying fix to cu_with_ratios view...")

        # Execute the SQL (DROP and CREATE)
        conn.execute(sql)

        print("View updated successfully!")

        # Verify the fix by checking TDECU (cu_number = 60705)
        print("\nVerifying fix with TDECU (cu_number = 60705)...")
        result = conn.execute("""
            SELECT
                cu_name,
                cycle_date,
                assets,
                roa,
                delinquency_ratio,
                coverage_ratio,
                net_worth_ratio
            FROM cu_with_ratios
            WHERE cu_number = 60705
            ORDER BY cycle_date DESC
            LIMIT 1
        """).fetchone()

        if result:
            print(f"\n  Credit Union: {result[0]}")
            print(f"  Period: {result[1]}")
            print(f"  Assets: ${result[2]:,.0f}")
            print(f"  ROA: {result[3]:.2f}%")
            print(f"  Delinquency Ratio: {result[4]:.2f}%")
            print(f"  Coverage Ratio: {result[5]:.2f}%")
            print(f"  Net Worth Ratio: {result[6]:.2f}%")
        else:
            print("  Warning: TDECU not found in data")

        # Also show raw values for verification
        print("\n  Raw account values for verification:")
        raw = conn.execute("""
            SELECT
                s.acct_021b as delinq_60_180d,
                s.acct_022b as delinq_180_360d,
                s.acct_023b as delinq_360plus,
                s.acct_025b as total_loans,
                s.acct_719 as allowance,
                s.acct_602 as net_income
            FROM fs220 s
            WHERE s.cu_number = 60705
            ORDER BY s.cycle_date DESC
            LIMIT 1
        """).fetchone()

        if raw:
            total_delinq = (raw[0] or 0) + (raw[1] or 0) + (raw[2] or 0)
            print(f"    Delinquent 60-180 days: ${raw[0]:,.0f}")
            print(f"    Delinquent 180-360 days: ${raw[1]:,.0f}")
            print(f"    Delinquent 360+ days: ${raw[2]:,.0f}")
            print(f"    Total Delinquent (60+ days): ${total_delinq:,.0f}")
            print(f"    Total Loans: ${raw[3]:,.0f}")
            print(f"    Allowance (acct_719): ${raw[4]:,.0f}")
            print(f"    Net Income (acct_602): ${raw[5]:,.0f}")
            print(f"\n    Calculated delinquency ratio: {total_delinq * 100.0 / raw[3]:.2f}%")

    return 0


if __name__ == "__main__":
    exit(main())
