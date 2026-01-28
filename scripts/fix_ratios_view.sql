-- Fix cu_with_ratios view to use correct NCUA standard calculations
--
-- Issues identified:
-- 1. Delinquency ratio: was using 6+ months, should be 60+ days (2+ months)
-- 2. Coverage ratio: was using acct_300 (Provision), should use acct_719 (Allowance)
-- 3. Coverage ratio denominator: was using 6+ months delinquent, should be 60+ days
--
-- NCUA Standard Formulas (from FPR Ratio and Formula Guide):
-- - Delinquency Ratio = Loans 60+ days delinquent / Total Loans
-- - Coverage Ratio = Allowance for Loan Losses / Delinquent Loans 60+ days
-- - ROA = Annualized Net Income / Average Assets (using quarterly annualization)

DROP VIEW IF EXISTS cu_with_ratios;

CREATE VIEW cu_with_ratios AS
SELECT
    f.cu_number,
    f.cycle_date,
    f.cu_name,
    f.city,
    f.state,
    f.county_code AS county,
    f.cu_type AS charter_type,

    -- Core metrics
    s.acct_010 AS assets,
    s.acct_018 AS total_shares,
    s.acct_025a AS loan_count,
    s.acct_025b AS loan_amount,
    s.acct_083 AS member_count,
    s.acct_602 AS net_income_quarterly,
    s.acct_671 AS operating_expenses_quarterly,
    (COALESCE(a.acct_564a, 0) + COALESCE(a.acct_564b, 0)) AS total_employees,

    -- YoY Growth metrics (unchanged - these are correct)
    ((s.acct_018 - LAG(s.acct_018, 4) OVER (PARTITION BY f.cu_number ORDER BY f.cycle_date)) * 100.0)
        / NULLIF(LAG(s.acct_018, 4) OVER (PARTITION BY f.cu_number ORDER BY f.cycle_date), 0) AS share_growth_yoy,

    ((s.acct_025b - LAG(s.acct_025b, 4) OVER (PARTITION BY f.cu_number ORDER BY f.cycle_date)) * 100.0)
        / NULLIF(LAG(s.acct_025b, 4) OVER (PARTITION BY f.cu_number ORDER BY f.cycle_date), 0) AS loan_growth_yoy,

    ((s.acct_083 - LAG(s.acct_083, 4) OVER (PARTITION BY f.cu_number ORDER BY f.cycle_date)) * 100.0)
        / NULLIF(LAG(s.acct_083, 4) OVER (PARTITION BY f.cu_number ORDER BY f.cycle_date), 0) AS member_growth_yoy,

    ((s.acct_010 - LAG(s.acct_010, 4) OVER (PARTITION BY f.cu_number ORDER BY f.cycle_date)) * 100.0)
        / NULLIF(LAG(s.acct_010, 4) OVER (PARTITION BY f.cu_number ORDER BY f.cycle_date), 0) AS asset_growth_yoy,

    -- Member relationship metrics (unchanged)
    (s.acct_010 / NULLIF(s.acct_083, 0)) AS avg_member_relationship,
    (s.acct_025a / NULLIF(s.acct_083, 0)) AS loans_per_member,

    -- Loan-to-Share Ratio (unchanged - correct)
    (s.acct_025b * 100.0) / NULLIF(s.acct_018, 0) AS loan_to_share_ratio,

    -- Operating Expense Ratio (unchanged - annualized)
    ((s.acct_671 * 4) * 100.0) / NULLIF(s.acct_010, 0) AS operating_expense_ratio,

    -- Non-Interest Income Ratio (unchanged)
    ((COALESCE(a.acct_117, 0) * 4) * 100.0) / NULLIF(s.acct_010, 0) AS non_interest_income_ratio,

    -- ROA - Return on Assets (annualized)
    -- Note: acct_602 may be 0 if CU reports net income directly to undivided earnings
    -- acct_661a (from fs220a income statement) is more consistently populated
    -- Uses COALESCE: if acct_602 is 0, use acct_661a instead
    -- Both are YTD values; we annualize by multiplying by 4 (rough quarterly assumption)
    ((COALESCE(NULLIF(s.acct_602, 0), a.acct_661a) * 4) * 100.0) / NULLIF(s.acct_010, 0) AS roa,

    -- Net Interest Margin (unchanged)
    ((COALESCE(a.acct_115, 0) - COALESCE(a.acct_350, 0)) * 100.0) / NULLIF(s.acct_010, 0) AS net_interest_margin,

    -- Net Worth Ratio (unchanged - uses balance sheet equity accounts)
    (((COALESCE(s.acct_931, 0) + COALESCE(s.acct_940, 0)) + COALESCE(s.acct_658, 0)) * 100.0)
        / NULLIF(s.acct_010, 0) AS net_worth_ratio,

    -- FIXED: Delinquency Ratio - NCUA uses 60+ days (2+ months)
    -- Old: (acct_022b + acct_023b) = only 6+ months
    -- New: (acct_021b + acct_022b + acct_023b) = 60+ days (2+ months)
    -- acct_021b = 2 to <6 months delinquent
    -- acct_022b = 6 to <12 months delinquent
    -- acct_023b = 12+ months delinquent
    ((COALESCE(s.acct_021b, 0) + COALESCE(s.acct_022b, 0) + COALESCE(s.acct_023b, 0)) * 100.0)
        / NULLIF(s.acct_025b, 0) AS delinquency_ratio,

    -- FIXED: Coverage Ratio - Uses Allowance for Loan Losses (acct_719) over 60+ day delinquent loans
    -- Old: acct_300 (Provision - income statement expense) / (6+ month delinquent)
    -- New: acct_719 (Allowance - balance sheet) / (60+ day delinquent loans)
    (s.acct_719 * 100.0)
        / NULLIF((COALESCE(s.acct_021b, 0) + COALESCE(s.acct_022b, 0) + COALESCE(s.acct_023b, 0)), 0) AS coverage_ratio,

    -- Members per Employee (unchanged)
    (s.acct_083 / NULLIF((COALESCE(a.acct_564a, 0) + COALESCE(a.acct_564b, 0)), 0)) AS members_per_employee,

    -- Efficiency Ratio (unchanged)
    -- Operating Expenses / (Net Interest Income + Non-Interest Income)
    (s.acct_671 * 100.0)
        / NULLIF(((COALESCE(a.acct_115, 0) - COALESCE(a.acct_350, 0)) + COALESCE(a.acct_117, 0)), 0) AS efficiency_ratio,

    -- Indirect Lending Ratio (unchanged)
    (COALESCE(a.acct_618a, 0) * 100.0) / NULLIF(s.acct_025b, 0) AS indirect_lending_ratio

FROM foicu AS f
INNER JOIN fs220 AS s
    ON f.cu_number = s.cu_number
    AND f.cycle_date = s.cycle_date
LEFT JOIN fs220a AS a
    ON f.cu_number = a.cu_number
    AND f.cycle_date = a.cycle_date
WHERE s.acct_010 > 0;
