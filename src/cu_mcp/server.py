"""FastMCP server exposing read-only access to the credit union DuckDB dataset."""
from __future__ import annotations

import concurrent.futures
import datetime as _dt
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Tuple

import duckdb
import pandas as pd

try:  # FastMCP 2.x is a standalone package
    from fastmcp import FastMCP
except ImportError:  # pragma: no cover - helpful shim so module can be imported without FastMCP
    FastMCP = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "cu_data.duckdb"
MAX_ROWS = 1000
QUERY_TIMEOUT_SECONDS = 10
DEFAULT_MIN_ASSETS = 25_000_000
FORBIDDEN_KEYWORDS = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE", "ATTACH", "DETACH"]

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


# Note: Icons require FastMCP 2.13.0+. Once FastMCP Cloud updates, uncomment:
# icons=[Icon(src="https://raw.githubusercontent.com/kylelegare/cu_MCP/main/icon.png",
#             mimeType="image/png", sizes=["128x128"])]
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


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
@mcp.tool()
def search_credit_unions(query: str, min_assets: int = DEFAULT_MIN_ASSETS) -> Dict[str, Any]:
    """Query NCUA credit union call report data using SQL.

    Data: ~3,000 US credit unions (filtered to assets >= $25M by default), 11 quarters (Q1 2023 - Q3 2025).

    Main view: cu_with_ratios
    Key columns: cu_number, cu_name, city, state, assets, member_count, cycle_date

    Pre-calculated ratios (no math needed):
    - roa, efficiency_ratio, operating_expense_ratio, net_worth_ratio
    - loan_to_share_ratio, net_interest_margin, delinquency_ratio, coverage_ratio
    - member_growth_yoy, loan_growth_yoy, share_growth_yoy, asset_growth_yoy
    - members_per_employee, avg_member_relationship, indirect_lending_ratio

    Note: efficiency_ratio = operating expenses / revenue (lower is better, typical 50-90%).

    Args:
        query: SQL SELECT query against cu_with_ratios or other tables.
        min_assets: Minimum asset threshold in dollars. Default $25M filters out small CUs.
                    Set to 0 to include all credit unions.

    Returns: JSON with 'data' array, 'row_count', 'min_assets_applied', and optional 'warning'.
    Safety: SELECT only, 10-second timeout, 1000-row limit.
    """

    if query is None or not str(query).strip():
        return {"error": "Query cannot be empty", "query": query}

    is_valid, error_message = is_safe_query(query)
    if not is_valid:
        return {"error": error_message, "query": query}

    # Apply min_assets filter if specified and query uses cu_with_ratios
    effective_query = query
    if min_assets > 0 and "cu_with_ratios" in query.lower():
        # Wrap query to apply asset filter
        effective_query = f"""
        WITH filtered_data AS (
            SELECT * FROM cu_with_ratios WHERE assets >= {min_assets}
        )
        {query.replace('cu_with_ratios', 'filtered_data')}
        """

    def _run_query() -> pd.DataFrame:
        with _get_connection() as conn:
            return conn.execute(effective_query).fetchdf()

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
            "hint": "Verify column names. Available: cu_name, state, assets, roa, efficiency_ratio, etc.",
        }

    warning = None
    if len(result_df) > MAX_ROWS:
        result_df = result_df.head(MAX_ROWS)
        warning = f"Results limited to {MAX_ROWS} rows"

    return {
        "data": _serialize_dataframe(result_df),
        "row_count": len(result_df),
        "query": query,
        "min_assets_applied": min_assets if min_assets > 0 and "cu_with_ratios" in query.lower() else None,
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

    if transport == "http":
        # Run as HTTP server for remote access (FastMCP Cloud)
        import os
        port = int(os.getenv("PORT", "8000"))

        # HTTP transport (uses Streamable HTTP protocol internally)
        mcp.run(
            transport="http",
            host="0.0.0.0",
            port=port
        )
    else:
        # Run as stdio server for local use (Claude Desktop, Claude Code CLI)
        mcp.run()


if __name__ == "__main__":  # pragma: no cover - manual execution only
    main()
