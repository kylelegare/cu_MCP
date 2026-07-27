CREATE OR REPLACE VIEW cu_with_ratios AS
WITH joined AS (
    SELECT
        f.cu_number,
        f.cycle_date,
        f.cu_name,
        f.city,
        f.state,
        f.county_code AS county,
        f.cu_type AS charter_type,
        s.acct_010 AS assets,
        s.acct_018 AS total_shares,
        s.acct_025a AS loan_count,
        s.acct_025b AS loan_amount,
        s.acct_083 AS member_count,
        s.acct_602 AS net_income_quarterly,
        s.acct_671 AS operating_expenses_quarterly,
        COALESCE(a.acct_564a, 0) + COALESCE(a.acct_564b, 0) AS total_employees,
        COALESCE(NULLIF(s.acct_602, 0), a.acct_661a) AS reported_net_income_ytd,
        COALESCE(a.acct_115, 0) AS interest_income_ytd,
        COALESCE(a.acct_350, 0) AS interest_expense_ytd,
        COALESCE(a.acct_117, 0) AS non_interest_income_ytd,
        COALESCE(a.acct_618a, 0) AS indirect_loans,
        COALESCE(s.acct_931, 0) AS regular_reserves,
        COALESCE(s.acct_940, 0) AS undivided_earnings,
        COALESCE(s.acct_658, 0) AS other_reserves,
        COALESCE(s.acct_041b, 0) AS delinquent_loans,
        s.acct_719 AS allowance_for_loan_losses,
        CASE EXTRACT(QUARTER FROM f.cycle_date)
            WHEN 1 THEN 4.0
            WHEN 2 THEN 2.0
            WHEN 3 THEN 4.0 / 3.0
            ELSE 1.0
        END AS annualization_factor
    FROM foicu AS f
    INNER JOIN fs220 AS s
        ON f.cu_number = s.cu_number
       AND f.cycle_date = s.cycle_date
    LEFT JOIN fs220a AS a
        ON f.cu_number = a.cu_number
       AND f.cycle_date = a.cycle_date
    WHERE s.acct_010 > 0
)
SELECT
    cu_number,
    cycle_date,
    cu_name,
    city,
    state,
    county,
    charter_type,
    assets,
    total_shares,
    loan_count,
    loan_amount,
    member_count,
    net_income_quarterly,
    operating_expenses_quarterly,
    total_employees,
    ((total_shares - LAG(total_shares, 4) OVER w) * 100.0) / NULLIF(LAG(total_shares, 4) OVER w, 0) AS share_growth_yoy,
    ((loan_amount - LAG(loan_amount, 4) OVER w) * 100.0) / NULLIF(LAG(loan_amount, 4) OVER w, 0) AS loan_growth_yoy,
    ((member_count - LAG(member_count, 4) OVER w) * 100.0) / NULLIF(LAG(member_count, 4) OVER w, 0) AS member_growth_yoy,
    ((assets - LAG(assets, 4) OVER w) * 100.0) / NULLIF(LAG(assets, 4) OVER w, 0) AS asset_growth_yoy,
    assets / NULLIF(member_count, 0) AS avg_member_relationship,
    loan_count / NULLIF(member_count, 0) AS loans_per_member,
    (loan_amount * 100.0) / NULLIF(total_shares, 0) AS loan_to_share_ratio,
    (operating_expenses_quarterly * annualization_factor * 100.0) / NULLIF(assets, 0) AS operating_expense_ratio,
    (non_interest_income_ytd * annualization_factor * 100.0) / NULLIF(assets, 0) AS non_interest_income_ratio,
    (reported_net_income_ytd * annualization_factor * 100.0) / NULLIF(assets, 0) AS roa,
    ((interest_income_ytd - interest_expense_ytd) * annualization_factor * 100.0) / NULLIF(assets, 0) AS net_interest_margin,
    ((regular_reserves + undivided_earnings + other_reserves) * 100.0) / NULLIF(assets, 0) AS net_worth_ratio,
    (delinquent_loans * 100.0) / NULLIF(loan_amount, 0) AS delinquency_ratio,
    (allowance_for_loan_losses * 100.0) / NULLIF(delinquent_loans, 0) AS coverage_ratio,
    member_count / NULLIF(total_employees, 0) AS members_per_employee,
    (operating_expenses_quarterly * 100.0) / NULLIF((interest_income_ytd - interest_expense_ytd) + non_interest_income_ytd, 0) AS efficiency_ratio,
    (indirect_loans * 100.0) / NULLIF(loan_amount, 0) AS indirect_lending_ratio
FROM joined
WINDOW w AS (PARTITION BY cu_number ORDER BY cycle_date);
