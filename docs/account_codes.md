# Account code reference

Raw call report schedules (fs220*, foicu) expose hundreds of `acct_XXX` columns. Use the `acctdesc` table to translate each code into a human-readable description when building ad-hoc SQL.

## Common account codes
| Account | Description | Notes |
| --- | --- | --- |
| `acct_010` | Total assets | Matches `assets` in the ratio view |
| `acct_018` | Net worth | Use for custom capital ratios |
| `acct_025` | Net income (YTD) | Annualized when computing ROA |
| `acct_030` | Total loans & leases | Equivalent to `loan_amount` |
| `acct_060` | Total shares/deposits | Equivalent to `total_shares` |
| `acct_142` | Total members | Equivalent to `member_count` |
| `acct_197` | Delinquent loans | Use with `acct_030` for delinquency ratio |
| `acct_440` | Allowance for loan losses | Use with `acct_197` for coverage ratio |
| `acct_570` | Operating expenses | Base for efficiency ratio |

## Helpful SQL snippets
```sql
-- Look up the friendly name for an account column
SELECT account, description
FROM acctdesc
WHERE account IN ('acct_010', 'acct_570');

-- Join descriptions onto an fs220 query
SELECT f.cu_number,
       f.cycle_date,
       a.description,
       f.acct_570 AS amount
FROM fs220 AS f
JOIN acctdesc AS a
  ON a.account = 'acct_570'
WHERE f.cycle_date = (SELECT MAX(cycle_date) FROM fs220);
```

Use `get_schema('acctdesc')` for the definitive list of account codes and their meanings.
