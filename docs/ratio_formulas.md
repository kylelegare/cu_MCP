# Ratio formulas (cu_with_ratios view)

All ratios are pre-computed in the `cu_with_ratios` view so downstream tools do not need to repeat math. The table below documents the business meaning and construction of each metric.

| Column | Definition | Formula Notes |
| --- | --- | --- |
| `roa` | Return on Assets (%) | `(net_income_quarterly * 4) / assets * 100` (annualized) |
| `efficiency_ratio` | Operating expenses as % of revenue | `operating_expenses_quarterly / (net_interest_income + non_interest_income) * 100`; lower is better; measures cost efficiency |
| `operating_expense_ratio` | Operating expenses as % of assets | `(operating_expenses_quarterly * 4) / assets * 100` (annualized); different from efficiency ratio |
| `loan_to_share_ratio` | Lending aggressiveness | `loan_amount / total_shares * 100` |
| `net_interest_margin` | Net interest spread | `((interest_income - interest_expense) / assets) * 100`; key profitability metric |
| `net_worth_ratio` | Capital adequacy | `(net_worth / assets) * 100` |
| `delinquency_ratio` | Delinquent loans as % of total | `delinquent_loans / loan_amount * 100` |
| `coverage_ratio` | Allowance coverage of delinquencies | `allowance_for_loan_losses / delinquent_loans * 100` |
| `member_growth_yoy` | Trailing 4-quarter member growth | `(member_count - LAG(member_count, 4)) / LAG(member_count, 4) * 100` |
| `loan_growth_yoy` | Trailing 4-quarter loan growth | `(loan_amount - LAG(loan_amount, 4)) / LAG(loan_amount, 4) * 100` |
| `share_growth_yoy` | Trailing 4-quarter share growth | `(total_shares - LAG(total_shares, 4)) / LAG(total_shares, 4) * 100` |
| `asset_growth_yoy` | Trailing 4-quarter asset growth | `(assets - LAG(assets, 4)) / LAG(assets, 4) * 100` |
| `avg_member_relationship` | Avg. assets per member | `assets / NULLIF(member_count, 0)` |
| `loans_per_member` | Loan balance per member | `loan_amount / NULLIF(member_count, 0)` |
| `members_per_employee` | Productivity proxy | `member_count / NULLIF(total_employees, 0)` |
| `indirect_lending_ratio` | Share of loans sourced indirectly | `indirect_loan_balance / loan_amount * 100` |

## Important Notes

**Efficiency Ratio vs. Operating Expense Ratio:**
- **Efficiency Ratio** measures operating expenses relative to revenue (net interest income + non-interest income). Lower is better. Typical range: 50-90%.
- **Operating Expense Ratio** measures operating expenses relative to total assets. This is a different metric that shows expense burden on the balance sheet.

**Net Interest Margin:**
- Calculated as (Interest Income - Interest Expense) / Assets
- Typical range for credit unions: 2-4%
- Key indicator of lending profitability

**Data Quality Note:**
- Some large credit unions show $0 net income (and therefore 0% ROA) in recent quarters due to data reporting variations. This is a source data limitation, not a calculation error.

Additional derived fields are documented inline in `src/cu_mcp/server.py` and surfaced through `get_schema()`.
