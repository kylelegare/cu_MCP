# Ratio formulas (cu_with_ratios view)

All ratios are pre-computed in the `cu_with_ratios` view so downstream tools do not need to repeat math. The table below documents the business meaning and construction of each metric.

| Column | Definition | Formula Notes |
| --- | --- | --- |
| `roa` | Return on Assets (%) | `(reported_net_income_ytd * annualization_factor) / assets * 100`; `annualization_factor = 4 / quarter_number`, using `acct_602` or falling back to `acct_661a` |
| `efficiency_ratio` | Operating expenses as % of revenue | `acct_671 / (net_interest_income_ytd + non_interest_income_ytd) * 100`; lower is better |
| `operating_expense_ratio` | Operating expenses as % of assets | `(acct_671 * annualization_factor) / assets * 100`; annualized from YTD values |
| `loan_to_share_ratio` | Lending aggressiveness | `acct_025b / acct_018 * 100` |
| `net_interest_margin` | Net interest spread | `((acct_115 - acct_350) * annualization_factor) / assets * 100` |
| `net_worth_ratio` | Capital adequacy | `(acct_931 + acct_940 + acct_658) / assets * 100` |
| `delinquency_ratio` | Delinquent loans as % of total | `acct_041b / acct_025b * 100` |
| `coverage_ratio` | Allowance coverage of delinquencies | `acct_719 / acct_041b * 100` |
| `non_interest_income_ratio` | Non-interest income as % of assets | `(acct_117 * annualization_factor) / assets * 100` |
| `member_growth_yoy` | Trailing 4-quarter member growth | `(member_count - LAG(member_count, 4)) / LAG(member_count, 4) * 100` |
| `loan_growth_yoy` | Trailing 4-quarter loan growth | `(loan_amount - LAG(loan_amount, 4)) / LAG(loan_amount, 4) * 100` |
| `share_growth_yoy` | Trailing 4-quarter share growth | `(total_shares - LAG(total_shares, 4)) / LAG(total_shares, 4) * 100` |
| `asset_growth_yoy` | Trailing 4-quarter asset growth | `(assets - LAG(assets, 4)) / LAG(assets, 4) * 100` |
| `avg_member_relationship` | Avg. assets per member | `assets / NULLIF(member_count, 0)` |
| `loans_per_member` | Loan count per member | `acct_025a / NULLIF(member_count, 0)` |
| `members_per_employee` | Productivity proxy | `member_count / NULLIF(full_time + part_time, 0)` |
| `indirect_lending_ratio` | Share of loans sourced indirectly | `acct_618a / acct_025b * 100` |

## Important Notes

**Efficiency Ratio vs. Operating Expense Ratio:**
- **Efficiency Ratio** measures operating expenses relative to revenue (net interest income + non-interest income). Lower is better. Typical range: 50-90%.
- **Operating Expense Ratio** measures operating expenses relative to total assets. This is a different metric that shows expense burden on the balance sheet.

**Annualization of Income-Statement Ratios:**
- NCUA call report income-statement fields are reported year-to-date for Q2-Q4.
- The view normalizes them with `annualization_factor = 4 / quarter_number`.
- That means Q1 uses `4.0`, Q2 uses `2.0`, Q3 uses `1.333...`, and Q4 uses `1.0`.

**YoY Growth Ratios:**
- Require at least 4 prior quarters of data for a given credit union
- Will be NULL for the first year of data or for newly chartered CUs

**Data Quality Note:**
- Some institutions report `acct_602 = 0` while `acct_661a` contains the income value used for ROA. The view falls back to `acct_661a` in those cases.
