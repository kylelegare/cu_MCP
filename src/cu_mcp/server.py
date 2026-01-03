"""FastMCP server exposing read-only access to the credit union DuckDB dataset."""
from __future__ import annotations

import concurrent.futures
import datetime as _dt
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import duckdb
import pandas as pd

try:  # FastMCP ships inside the official `mcp` package
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - helpful shim so module can be imported without FastMCP
    FastMCP = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants & metadata
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "cu_data.duckdb"
MAX_ROWS = 1000
QUERY_TIMEOUT_SECONDS = 10
SAMPLE_ROW_LIMIT = 5
FORBIDDEN_KEYWORDS = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE"]
RECOMMENDATION = "Use the cu_with_ratios view for most analytical queries"

TABLE_DESCRIPTIONS = {
    "cu_with_ratios": "⭐ Consolidated view that joins identifying info with pre-calculated ratios",
    "foicu": "Credit union identity (charter, branchings, geography)",
    "fs220": "Primary financial schedule with core account balances",
    "fs220a": "Supplemental schedule (non-interest income, employee stats)",
    "fs220b": "Breakouts for investment balances",
    "fs220c": "Allowance and delinquency metrics",
    "fs220g": "Member business loan detail",
    "fs220h": "Mortgage and real estate balances",
    "fs220i": "Indirect lending detail",
    "fs220j": "Deposit and share account detail",
    "fs220k": "Capital and net worth detail",
    "fs220l": "Income statement breakouts",
    "fs220m": "Expense detail",
    "fs220n": "Other operating income detail",
    "fs220p": "Product penetration data",
    "fs220q": "Member service measurements",
    "fs220r": "Technology and channel usage",
    "acctdesc": "Account code dictionary mapping acct_XXX columns to names",
}

COLUMN_DESCRIPTIONS = {
    "cu_number": "Unique credit union identifier assigned by the NCUA",
    "cycle_date": "Quarter end date for the reported metrics",
    "cu_name": "Credit union legal name",
    "city": "Headquarters city",
    "state": "Two-letter state or territory code",
    "assets": "Total assets reported for the quarter",
    "member_count": "Number of members",
    "member_growth_yoy": "Year-over-year member growth percentage",
    "loan_growth_yoy": "Year-over-year loan balance growth percentage",
    "share_growth_yoy": "Year-over-year share/deposit growth percentage",
    "asset_growth_yoy": "Year-over-year asset growth percentage",
    "roa": "Return on Assets (annualized percentage)",
    "efficiency_ratio": "Operating expenses as % of revenue (lower is better, typical range 50-90%)",
    "operating_expense_ratio": "Operating expenses as % of assets (annualized, different from efficiency ratio)",
    "loan_to_share_ratio": "Loan to share (deposit) ratio",
    "net_worth_ratio": "Net worth ratio (capital / assets)",
    "net_interest_margin": "Net interest income as % of assets (typical range 2-4%)",
    "non_interest_income_ratio": "Non-interest income as % of assets (annualized)",
    "members_per_employee": "Average members per full-time employee",
    "indirect_lending_ratio": "Indirect lending share of total loans",
    "avg_member_relationship": "Average relationship per member in dollars",
}

ALLOWED_CATEGORIES = {"search", "comparison", "ranking", "trends", "financial_analysis"}

# Example query catalog. Each entry contains SQL that can be run as-is.
EXAMPLE_QUERIES: List[Dict[str, str]] = [
    {
        "category": "search",
        "title": "Find credit unions by name pattern",
        "description": "Locate credit unions that partially match a provided name substring",
        "sql": """-- Use LOWER() with wildcards so name matching is flexible
SELECT cu_name, state, city, assets, member_count
FROM cu_with_ratios
WHERE LOWER(cu_name) LIKE '%navy%'
  AND cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
ORDER BY assets DESC;""",
        "use_case": "When users only know part of the credit union's name",
    },
    {
        "category": "search",
        "title": "Filter by state and asset threshold",
        "description": "State-level screening with asset floors for size comparisons",
        "sql": """-- Latest quarter filter keeps the result list current
SELECT cu_name, city, assets, member_count, roa
FROM cu_with_ratios
WHERE state = 'WA'
  AND assets > 500000000
  AND cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
ORDER BY assets DESC;""",
        "use_case": "Great starting point for \"show me CUs in <state> above $X\" questions",
    },
    {
        "category": "search",
        "title": "Multi-criteria performance search",
        "description": "Combine efficiency, ROA, and size filters to find standout performers",
        "sql": """-- Keep criteria explicit so LLMs can easily tweak thresholds
SELECT cu_name, state, assets, roa, efficiency_ratio
FROM cu_with_ratios
WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
  AND roa > 1.0
  AND efficiency_ratio < 70
  AND assets > 100000000
ORDER BY roa DESC;""",
        "use_case": "Use when the user lists multiple numeric constraints",
    },
    {
        "category": "search",
        "title": "Find CUs by metric range",
        "description": "Filter on ROA within a desired band to control volatility",
        "sql": """-- BETWEEN keeps ROA within a manageable band
SELECT cu_name, state, assets, roa, efficiency_ratio
FROM cu_with_ratios
WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
  AND roa BETWEEN 1.0 AND 2.0
ORDER BY roa DESC;""",
        "use_case": "Answer \"find CUs with ROA between 1% and 2%\" style prompts",
    },
    {
        "category": "comparison",
        "title": "Compare two specific credit unions",
        "description": "Side-by-side snapshot for two named institutions",
        "sql": """-- Provide consistent list of key operating metrics
SELECT cu_name, assets, roa, efficiency_ratio, net_worth_ratio, loan_to_share_ratio
FROM cu_with_ratios
WHERE cu_name IN ('NAVY FEDERAL CREDIT UNION', 'PENTAGON FEDERAL CREDIT UNION')
  AND cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios);""",
        "use_case": "Use when the user mentions two institutions explicitly",
    },
    {
        "category": "comparison",
        "title": "Compare a CU to its state peers",
        "description": "Rank a target CU in the context of other CUs in the same state",
        "sql": """-- Use window functions for percentile style context
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
LIMIT 20;""",
        "use_case": "Good follow-up when users ask how a CU compares to others nearby",
    },
    {
        "category": "comparison",
        "title": "Compare CU metrics to national averages",
        "description": "Show how a selected CU stacks up against US-wide averages",
        "sql": """-- Compute national averages then join back for context
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
WHERE l.cu_name = 'NAVY FEDERAL CREDIT UNION';""",
        "use_case": "When the prompt mentions \"national average\" or \"typical CU\"",
    },
    {
        "category": "ranking",
        "title": "Top 10 by assets",
        "description": "Basic league-table ranked by total assets",
        "sql": """-- Keep ORDER BY aligned with ranking metric
SELECT cu_name, state, assets, roa
FROM cu_with_ratios
WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
ORDER BY assets DESC
LIMIT 10;""",
        "use_case": "Answer \"largest credit unions\" questions",
    },
    {
        "category": "ranking",
        "title": "Bottom 10 by efficiency ratio",
        "description": "Identify most efficient operators using ASC ordering",
        "sql": """-- Lower efficiency ratio is better
SELECT cu_name, state, assets, efficiency_ratio
FROM cu_with_ratios
WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
  AND efficiency_ratio IS NOT NULL
ORDER BY efficiency_ratio ASC
LIMIT 10;""",
        "use_case": "Useful when looking for \"most efficient\" institutions",
    },
    {
        "category": "ranking",
        "title": "Top ROA performers with size filter",
        "description": "Rank ROA but exclude very small CUs for stability",
        "sql": """-- Add an assets filter to focus on meaningful peers
SELECT cu_name, state, assets, roa, efficiency_ratio
FROM cu_with_ratios
WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
  AND roa IS NOT NULL
  AND assets > 100000000
ORDER BY roa DESC
LIMIT 15;""",
        "use_case": "Use when asked for \"top performers\"",
    },
    {
        "category": "ranking",
        "title": "Ranking within a state",
        "description": "Dense_rank within a single state to show position",
        "sql": """-- Window functions keep ordinal ranking with ties
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
ORDER BY roa_rank;""",
        "use_case": "When the request narrows to a particular geography",
    },
    {
        "category": "trends",
        "title": "Show metrics over time for one CU",
        "description": "List every quarter for a CU to analyze trajectory",
        "sql": """-- No date filter so all quarters are returned
SELECT cycle_date, cu_name, assets, roa, efficiency_ratio, member_count
FROM cu_with_ratios
WHERE cu_name = 'NAVY FEDERAL CREDIT UNION'
ORDER BY cycle_date;""",
        "use_case": "Use when the prompt says \"over time\" or \"trend\"",
    },
    {
        "category": "trends",
        "title": "Quarter-over-quarter growth",
        "description": "Use window functions to calculate QoQ deltas",
        "sql": """-- LAG() compares the current quarter to the previous
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
ORDER BY cycle_date;""",
        "use_case": "When asked about sequential quarter changes",
    },
    {
        "category": "trends",
        "title": "Year-over-year comparison",
        "description": "Show YOY metrics already calculated in the dataset",
        "sql": """-- Uses the *_growth_yoy columns baked into cu_with_ratios
SELECT cu_name,
       cycle_date,
       member_growth_yoy,
       loan_growth_yoy,
       share_growth_yoy
FROM cu_with_ratios
WHERE cu_name LIKE '%NAVY FEDERAL%'
  AND member_growth_yoy IS NOT NULL
ORDER BY cycle_date;""",
        "use_case": "Quickly answer YOY questions without extra math",
    },
    {
        "category": "trends",
        "title": "Identify improving efficiency",
        "description": "Aggregate min/max efficiency to gauge improvement",
        "sql": """-- Improvement = worst minus best (positive means trending better)
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
LIMIT 20;""",
        "use_case": "Surface CUs that improved cost structure materially",
    },
    {
        "category": "financial_analysis",
        "title": "High performers across multiple metrics",
        "description": "Filter on ROA, efficiency, net worth, and size simultaneously",
        "sql": """-- Combine thresholds to satisfy complex multi-metric prompts
SELECT cu_name, state, assets, roa, efficiency_ratio, net_worth_ratio
FROM cu_with_ratios
WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
  AND roa > 1.0
  AND efficiency_ratio < 70
  AND net_worth_ratio > 10
  AND assets > 100000000
ORDER BY roa DESC;""",
        "use_case": "Answer \"find top performers by multiple metrics\" questions",
    },
    {
        "category": "financial_analysis",
        "title": "Percentile analysis",
        "description": "Use percent_rank to compute ROA percentile",
        "sql": """-- Multiply PERCENT_RANK by 100 to express as percentile
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
LIMIT 50;""",
        "use_case": "Useful for \"top quartile\" or \"top 25%\" prompts",
    },
    {
        "category": "financial_analysis",
        "title": "Correlation between ROA and loan-to-share ratio",
        "description": "Quantify how two metrics move together",
        "sql": """-- DuckDB corr() function quickly summarizes the relationship
WITH latest AS (
    SELECT roa, loan_to_share_ratio
    FROM cu_with_ratios
    WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
      AND roa IS NOT NULL
      AND loan_to_share_ratio IS NOT NULL
)
SELECT corr(roa, loan_to_share_ratio) AS roa_vs_loan_to_share_corr
FROM latest;""",
        "use_case": "When users ask \"do CUs with X tend to have Y\"",
    },
    {
        "category": "financial_analysis",
        "title": "Geographic averages",
        "description": "Aggregate by state to summarize efficiency and ROA",
        "sql": """-- Aggregate metrics to build quick state scorecards
SELECT state,
       COUNT(*) AS cu_count,
       AVG(assets) AS avg_assets,
       AVG(roa) AS avg_roa,
       AVG(efficiency_ratio) AS avg_efficiency
FROM cu_with_ratios
WHERE cycle_date = (SELECT MAX(cycle_date) FROM cu_with_ratios)
GROUP BY state
ORDER BY avg_assets DESC;""",
        "use_case": "Use for \"state level averages\" prompts",
    },
]


class _MCPStub:
    """Fallback shim so the module can be imported without FastMCP installed."""

    def tool(self, *_, **__):  # noqa: D401 - trivial shim
        def decorator(func):
            return func

        return decorator

    def run(self) -> None:
        raise ImportError(
            "FastMCP lives in the `mcp` package. Install it with `pip install \"mcp[cli]\"`."
        )


mcp = FastMCP("Credit Union Analytics") if FastMCP else _MCPStub()


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def _ensure_database() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Ensure cu_data.duckdb is placed in the data/ directory."
        )


def _get_connection() -> duckdb.DuckDBPyConnection:
    _ensure_database()
    return duckdb.connect(str(DB_PATH), read_only=True)


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _serialize_value(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().isoformat()
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "item") and callable(value.item):  # numpy scalar
        try:
            return value.item()
        except Exception:  # pragma: no cover - fallback only
            return value
    return value


def _serialize_dataframe(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    if frame.empty:
        return []
    sanitized = frame.where(pd.notnull(frame), None)
    records: List[Dict[str, Any]] = sanitized.to_dict("records")
    for row in records:
        for key, value in list(row.items()):
            if value is None:
                continue
            row[key] = _serialize_value(value)
    return records


def _table_type_to_string(table_type: str) -> str:
    return "view" if table_type and table_type.upper() == "VIEW" else "table"


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
@mcp.tool()
def execute_sql(query: str) -> Dict[str, Any]:
    """Execute a validated SELECT query with strong safety guardrails."""

    if query is None or not str(query).strip():
        return {"error": "Query cannot be empty", "query": query}

    is_valid, error_message = is_safe_query(query)
    if not is_valid:
        return {"error": error_message, "query": query}

    def _run_query() -> pd.DataFrame:
        with _get_connection() as conn:
            return conn.execute(query).fetchdf()

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_query)
            result_df = future.result(timeout=QUERY_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError:
        return {
            "error": f"Query exceeded {QUERY_TIMEOUT_SECONDS} second timeout",
            "query": query,
            "hint": "Simplify filters or aggregate before returning large result sets",
        }
    except Exception as exc:  # pragma: no cover - DuckDB exceptions vary by query
        return {
            "error": f"Query execution failed: {exc}",
            "query": query,
            "hint": "Check table/column names using get_schema tool",
        }

    warning = None
    if len(result_df) > MAX_ROWS:
        result_df = result_df.head(MAX_ROWS)
        warning = f"Results limited to {MAX_ROWS} rows (too many to display)"

    return {
        "data": _serialize_dataframe(result_df),
        "row_count": len(result_df),
        "query": query,
        "warning": warning,
    }


def is_safe_query(query: str) -> Tuple[bool, str]:
    """Validate the query only contains safe SELECT statements."""

    query_upper = query.strip().upper()
    if not query_upper.startswith("SELECT"):
        return False, "Only SELECT queries are allowed"

    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in query_upper:
            return False, f"Query contains forbidden keyword: {keyword}"

    return True, ""


@mcp.tool()
def get_schema(table_name: Optional[str] = None) -> Dict[str, Any]:
    """Return database metadata and optional table detail."""

    with _get_connection() as conn:
        if not table_name:
            rows = conn.execute(
                """
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY table_name
                """
            ).fetchall()
            tables = []
            for name, table_type in rows:
                tables.append(
                    {
                        "name": name,
                        "type": _table_type_to_string(table_type),
                        "description": TABLE_DESCRIPTIONS.get(name, ""),
                    }
                )
            return {"tables": tables, "recommendation": RECOMMENDATION}

        normalized_name = table_name.strip()
        if not normalized_name:
            return {"error": "table_name cannot be empty"}

        metadata = conn.execute(
            """
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
              AND LOWER(table_name) = ?
            LIMIT 1
            """,
            [normalized_name.lower()],
        ).fetchone()

        if not metadata:
            return {"error": f"Table or view '{table_name}' not found"}

        resolved_name, table_type = metadata
        quoted_name = _quote_identifier(resolved_name)
        columns_df = conn.execute(f"PRAGMA table_info({quoted_name})").fetchdf()
        column_records = []
        for record in columns_df.to_dict("records"):
            column_records.append(
                {
                    "name": record["name"],
                    "type": record.get("type", "UNKNOWN"),
                    "description": COLUMN_DESCRIPTIONS.get(record["name"], ""),
                }
            )

        row_count = conn.execute(f"SELECT COUNT(*) FROM {quoted_name}").fetchone()[0]

        column_names = {col["name"].lower() for col in column_records}
        if "cycle_date" in column_names:
            sample_query = (
                f"""
                SELECT *
                FROM {quoted_name}
                WHERE cycle_date = (SELECT MAX(cycle_date) FROM {quoted_name})
                LIMIT {SAMPLE_ROW_LIMIT}
                """
            )
        else:
            sample_query = f"SELECT * FROM {quoted_name} LIMIT {SAMPLE_ROW_LIMIT}"

        sample_df = conn.execute(sample_query).fetchdf()

        return {
            "table_name": resolved_name,
            "type": _table_type_to_string(table_type),
            "description": TABLE_DESCRIPTIONS.get(resolved_name, ""),
            "columns": column_records,
            "row_count": row_count,
            "sample_data": _serialize_dataframe(sample_df),
        }


@mcp.tool()
def get_example_queries(category: Optional[str] = None) -> Dict[str, Any]:
    """Return SQL query templates organized by category."""

    if category:
        normalized = category.strip().lower()
        if normalized not in ALLOWED_CATEGORIES:
            return {
                "error": "Unknown category",
                "category": category,
                "allowed_categories": sorted(ALLOWED_CATEGORIES),
            }
        filtered = [ex for ex in EXAMPLE_QUERIES if ex["category"] == normalized]
    else:
        normalized = "all"
        filtered = EXAMPLE_QUERIES

    return {
        "category": normalized,
        "examples": filtered,
        "available_categories": sorted(ALLOWED_CATEGORIES),
        "note": "All queries reference the cu_with_ratios view and can be used as-is",
    }


# ---------------------------------------------------------------------------
# Server bootstrap
# ---------------------------------------------------------------------------
def main() -> None:
    """Entry point for running via `python -m cu_mcp.server`."""
    import sys
    import os

    _ensure_database()

    # Check for command-line arguments to determine transport mode
    transport = "stdio"  # default for local use

    for i, arg in enumerate(sys.argv):
        if arg == "--transport" and i + 1 < len(sys.argv):
            transport = sys.argv[i + 1]

    # Get port from environment variable (Render sets $PORT)
    port = int(os.getenv("PORT", "8000"))

    if transport == "sse":
        # Run as SSE server for remote access (Render, etc.)
        # FastMCP uses uvicorn which reads port from --port or environment
        mcp.run(transport="sse")
    else:
        # Run as stdio server for local use (Claude Desktop, Claude Code CLI)
        mcp.run()


if __name__ == "__main__":  # pragma: no cover - manual execution only
    main()
