# Example SQL patterns

Mirror of the query templates returned by the `get_example_queries` tool. All examples hit the `cu_with_ratios` view because it bundles identifiers with calculated ratios.

## Search
### Find credit unions by name
```sql
-- Use LOWER() with wildcards to keep matching flexible
SELECT cu_name, state, city, assets, member_count
FROM cu_with_ratios
WHERE LOWER(cu_name) LIKE '%navy%'
  AND cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
ORDER BY assets DESC;
```

### Filter by state and asset threshold
```sql
SELECT cu_name, city, assets, member_count, roa
FROM cu_with_ratios
WHERE state = 'WA'
  AND assets > 500000000
  AND cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
ORDER BY assets DESC;
```

### Multi-criteria search
```sql
SELECT cu_name, state, assets, roa, efficiency_ratio
FROM cu_with_ratios
WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
  AND roa > 1.0
  AND efficiency_ratio < 70
  AND assets > 100000000
ORDER BY roa DESC;
```

### Metric range search
```sql
SELECT cu_name, state, assets, roa, efficiency_ratio
FROM cu_with_ratios
WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
  AND roa BETWEEN 1.0 AND 2.0
ORDER BY roa DESC;
```

## Comparison
### Compare two named credit unions
```sql
SELECT cu_name, assets, roa, efficiency_ratio, net_worth_ratio, loan_to_share_ratio
FROM cu_with_ratios
WHERE cu_name IN ('NAVY FEDERAL CREDIT UNION', 'PENTAGON FEDERAL CREDIT UNION')
  AND cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios);
```

### Compare a CU to state peers
```sql
WITH state_peers AS (
    SELECT cu_name,
           state,
           assets,
           roa,
           efficiency_ratio,
           PERCENT_RANK() OVER (ORDER BY assets) AS asset_percentile
    FROM cu_with_ratios
    WHERE state = 'WA'
      AND cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
)
SELECT *
FROM state_peers
ORDER BY assets DESC
LIMIT 20;
```

### Compare against national averages
```sql
WITH latest AS (
    SELECT *
    FROM cu_with_ratios
    WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
),
national AS (
    SELECT AVG(roa) AS avg_roa,
           AVG(efficiency_ratio) AS avg_efficiency,
           AVG(net_worth_ratio) AS avg_net_worth
    FROM latest
)
SELECT l.cu_name,
       l.state,
       l.assets,
       l.roa,
       l.efficiency_ratio,
       l.net_worth_ratio,
       n.avg_roa,
       n.avg_efficiency,
       n.avg_net_worth
FROM latest AS l
CROSS JOIN national AS n
WHERE l.cu_name = 'NAVY FEDERAL CREDIT UNION';
```

## Ranking
### Top 10 by assets
```sql
SELECT cu_name, state, assets, roa
FROM cu_with_ratios
WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
ORDER BY assets DESC
LIMIT 10;
```

### Bottom 10 by efficiency ratio
```sql
SELECT cu_name, state, assets, efficiency_ratio
FROM cu_with_ratios
WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
  AND efficiency_ratio IS NOT NULL
ORDER BY efficiency_ratio ASC
LIMIT 10;
```

### Top ROA performers (asset filter)
```sql
SELECT cu_name, state, assets, roa, efficiency_ratio
FROM cu_with_ratios
WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
  AND roa IS NOT NULL
  AND assets > 100000000
ORDER BY roa DESC
LIMIT 15;
```

### Ranking within a state
```sql
WITH latest AS (
    SELECT *
    FROM cu_with_ratios
    WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
),
ranked AS (
    SELECT cu_name,
           state,
           assets,
           roa,
           DENSE_RANK() OVER (PARTITION BY state ORDER BY roa DESC) AS roa_rank
    FROM latest
    WHERE state = 'CA'
)
SELECT *
FROM ranked
WHERE roa_rank <= 10
ORDER BY roa_rank;
```

## Trends
### Show metrics over time
```sql
SELECT cycle_date, cu_name, assets, roa, efficiency_ratio, member_count
FROM cu_with_ratios
WHERE cu_name = 'NAVY FEDERAL CREDIT UNION'
ORDER BY cycle_date;
```

### Quarter-over-quarter growth
```sql
WITH ordered AS (
    SELECT cu_name,
           cycle_date,
           assets,
           LAG(assets) OVER (PARTITION BY cu_name ORDER BY cycle_date) AS prev_assets,
           member_count,
           LAG(member_count) OVER (PARTITION BY cu_name ORDER BY cycle_date) AS prev_members
    FROM cu_with_ratios
    WHERE cu_name = 'NAVY FEDERAL CREDIT UNION'
)
SELECT cu_name,
       cycle_date,
       assets,
       prev_assets,
       (assets - prev_assets) / NULLIF(prev_assets, 0) * 100 AS assets_qoq_growth,
       member_count,
       prev_members,
       (member_count - prev_members) / NULLIF(prev_members, 0) * 100 AS member_qoq_growth
FROM ordered
ORDER BY cycle_date;
```

### Year-over-year comparison
```sql
SELECT cu_name,
       cycle_date,
       member_growth_yoy,
       loan_growth_yoy,
       share_growth_yoy
FROM cu_with_ratios
WHERE cu_name LIKE '%NAVY FEDERAL%'
  AND member_growth_yoy IS NOT NULL
ORDER BY cycle_date;
```

### Improving efficiency
```sql
WITH stats AS (
    SELECT cu_name,
           state,
           MIN(efficiency_ratio) AS best_efficiency,
           MAX(efficiency_ratio) AS worst_efficiency
    FROM cu_with_ratios
    WHERE efficiency_ratio IS NOT NULL
    GROUP BY cu_name, state
)
SELECT cu_name,
       state,
       worst_efficiency - best_efficiency AS improvement
FROM stats
WHERE worst_efficiency - best_efficiency >= 5
ORDER BY improvement DESC
LIMIT 20;
```

## Financial analysis
### High performers across metrics
```sql
SELECT cu_name, state, assets, roa, efficiency_ratio, net_worth_ratio
FROM cu_with_ratios
WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
  AND roa > 1.0
  AND efficiency_ratio < 70
  AND net_worth_ratio > 10
  AND assets > 100000000
ORDER BY roa DESC;
```

### Percentile analysis
```sql
WITH latest AS (
    SELECT *
    FROM cu_with_ratios
    WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
      AND roa IS NOT NULL
)
SELECT cu_name,
       state,
       assets,
       roa,
       PERCENT_RANK() OVER (ORDER BY roa) * 100 AS roa_percentile
FROM latest
ORDER BY roa DESC
LIMIT 50;
```

### Correlation analysis
```sql
WITH latest AS (
    SELECT roa, loan_to_share_ratio
    FROM cu_with_ratios
    WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
      AND roa IS NOT NULL
      AND loan_to_share_ratio IS NOT NULL
)
SELECT corr(roa, loan_to_share_ratio) AS roa_vs_loan_to_share_corr
FROM latest;
```

### Geographic averages
```sql
SELECT state,
       COUNT(*) AS cu_count,
       AVG(assets) AS avg_assets,
       AVG(roa) AS avg_roa,
       AVG(efficiency_ratio) AS avg_efficiency
FROM cu_with_ratios
WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
GROUP BY state
ORDER BY avg_assets DESC;
```
