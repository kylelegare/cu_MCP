# Account code reference

Raw call report schedules (fs220*, foicu) expose hundreds of `acct_XXX` columns. Use the `acctdesc` table to translate each code into a human-readable description when building ad-hoc SQL.

## Common account codes
| Account | Description | Notes |
| --- | --- | --- |
| `acct_010` | Total assets | Matches `assets` in the ratio view |
| `acct_018` | Total shares and deposits | Matches `total_shares` in the ratio view |
| `acct_025a` | Total number of loans and leases | Matches `loan_count` in the ratio view |
| `acct_025b` | Total amount of loans and leases | Matches `loan_amount` in the ratio view |
| `acct_041b` | Total delinquent loans (2+ months) | Used in `delinquency_ratio` |
| `acct_083` | Number of current members | Matches `member_count` in the ratio view |
| `acct_115` | Total interest income | Used in `net_interest_margin` and `efficiency_ratio` |
| `acct_117` | Total non-interest income | Used in `efficiency_ratio` |
| `acct_350` | Total interest expense | Used in `net_interest_margin` |
| `acct_550` | Total charge-offs YTD | Loan losses |
| `acct_564a` | Full-time employees | Combined with `acct_564b` for `members_per_employee` |
| `acct_564b` | Part-time employees | Combined with `acct_564a` for `members_per_employee` |
| `acct_602` | Net income | Used in `roa` (annualized) |
| `acct_618a` | Total indirect loans outstanding | Used in `indirect_lending_ratio` |
| `acct_671` | Total non-interest expense | Operating expenses; used in `efficiency_ratio` and `operating_expense_ratio` |
| `acct_719` | Allowance for loan & lease losses | Used in `coverage_ratio` |
| `acct_931` | Regular reserves | Part of net worth calculation |
| `acct_940` | Undivided earnings | Part of net worth calculation |
| `acct_658` | Other reserves | Part of net worth calculation |

## Helpful SQL snippets
```sql
-- Look up the friendly name for an account column
SELECT account, acctname FROM acctdesc WHERE LOWER(account) = 'acct_010';

-- Search for accounts by keyword
SELECT account, acctname, tablename FROM acctdesc WHERE acctname LIKE '%delinq%';

-- Join descriptions onto an fs220 query
SELECT f.cu_number,
       f.cycle_date,
       f.acct_671 AS operating_expenses
FROM fs220 AS f
WHERE f.cycle_date = (SELECT MAX(cycle_date) FROM fs220)
LIMIT 10;
```
