# Credit Union Analytics MCP Server

This project wraps the public NCUA credit union database in an easy-to-use **Model Context Protocol (MCP)** server. Once the server is running, modern AI assistants (Claude Desktop, Codex CLI/IDE, Gemini apps, etc.) can ask natural-language questions and automatically run safe SQL queries behind the scenes. The goal is to let anyone explore credit union trends without wrestling with spreadsheets or learning every database detail.

---

## What you get
- **Ready-to-run MCP server** (`src/cu_mcp/server.py`) exposing three tools:
  1. `execute_sql` – run vetted SELECT queries (read-only, 10 s timeout, 1,000 row cap)
  2. `get_schema` – inspect available tables/views, columns, counts, and sample rows
  3. `get_example_queries` – grab curated SQL patterns for searches, comparisons, rankings, trends, and deeper analysis
- **DuckDB dataset** (`data/cu_data.duckdb`): 11 quarters of call report data with 15+ pre-calculated financial ratios in the `cu_with_ratios` view
- **Docs & references**: ratio formulas, account code cheatsheet, and example SQL playbook
- **MCP client instructions** for Claude Desktop, Codex CLI/IDE, or any MCP-compatible assistant

---

## Prerequisites

Before you begin, make sure you have:

### Required:
- ✅ **Python 3.12 or higher**
  - Check your version: `python3 --version`
  - Download from: https://www.python.org/downloads/
  - macOS with Homebrew: `brew install python@3.12`
- ✅ **pip** (comes with Python)

### Optional (choose one):
- **Claude Code CLI** - For command-line usage (recommended for easiest setup)
- **Claude Desktop** - For GUI usage
- **Other MCP-compatible assistant** - Codex, Gemini, etc.

> 💡 **Note:** The database file (`data/cu_data.duckdb`) is included and is 124MB. No separate download needed!

---

## Deployment Options

You have two ways to use this MCP server:

### Option 1: Local Installation (Run on Your Computer)
Follow the "Quick start" instructions below.
**Best for:** Personal use, testing, or when you want full control.

### Option 2: Remote Deployment (Host on Render)
Deploy to Render and share a URL with your team - no installation needed for users!
**Best for:** Team use, sharing with colleagues, always-on access.

📖 **See `RENDER_DEPLOYMENT.md` for full deployment instructions.**

Quick Render deploy:
1. Push code to GitHub
2. Connect GitHub to Render
3. Deploy (takes 5 minutes)
4. Share the URL with anyone!

---

## Quick start (15 minutes)
1. **Navigate to the project folder & create a virtual environment**
   ```bash
   cd cu_MCP  # or wherever you saved the folder
   /opt/homebrew/bin/python3.12 -m venv .venv   # adjust path for your OS
   source .venv/bin/activate                     # Windows: .venv\Scripts\activate
   ```

2. **Install dependencies** (brings in MCP SDK, DuckDB, pandas):
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

3. **Verify the database exists**
   - The database file is already included at `data/cu_data.duckdb`
   - The server opens it in read-only mode, so you can't accidentally change the data

4. **Run the MCP server**
   ```bash
   python -m cu_mcp.server
   ```
   Leave this terminal open; an MCP client will connect to it.

---

## Connecting your assistant
Every MCP client needs to know how to start the server. Here are common setups:

### Claude Code CLI (Recommended - Easiest Setup)
If you're using Claude Code CLI, simply run this command from your project directory:

**⚠️ Important:** Replace `/absolute/path/to/cu_MCP` with the actual full path where you saved this folder!

```bash
# Example: if your folder is at /Users/john/Documents/cu_MCP, use:
claude mcp add --transport stdio credit-union-analytics -- \
  /Users/john/Documents/cu_MCP/.venv/bin/python -m cu_mcp.server

# Windows example: if your folder is at C:\Users\john\cu_MCP, use:
claude mcp add --transport stdio credit-union-analytics -- \
  C:\Users\john\cu_MCP\.venv\Scripts\python.exe -m cu_mcp.server
```

Verify it's connected:
```bash
claude mcp list
```

You should see: `credit-union-analytics: ... - ✓ Connected`

**That's it!** Now just ask Claude Code natural language questions:
- "Show me the top 10 largest credit unions"
- "Compare efficiency ratios for Washington credit unions"
- "What's Navy Federal's ROA in the latest quarter?"

Claude Code will automatically use the MCP server to query the database.

### Claude Desktop
Edit `claude_desktop_config.json`:
- **macOS/Linux:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add this configuration (replace `/absolute/path/to/cu_MCP` with your actual path):
```json
{
  "mcpServers": {
    "credit-union-analytics": {
      "command": "/absolute/path/to/cu_MCP/.venv/bin/python",
      "args": ["-m", "cu_mcp.server"],
      "cwd": "/absolute/path/to/cu_MCP"
    }
  }
}
```
Restart Claude Desktop and you'll see the tools listed under "Servers".

### Codex CLI / IDE
Use the CLI helper (replace path with your actual path):
```bash
codex mcp add credit-union -- \
  /absolute/path/to/cu_MCP/.venv/bin/python -m cu_mcp.server
```
This updates `~/.codex/config.toml`, so the CLI and IDE extension both recognize the server.

### MCP Inspector (handy during development)
The MCP SDK ships with a GUI inspector:
```bash
source .venv/bin/activate
mcp dev src/cu_mcp/server.py
```
Use the Inspector UI to call each tool, inspect responses, and debug queries before involving an AI assistant.

> 📝 **Environment variables?** Not required for this server. If you want to add custom config later (e.g., alternate database paths), you can extend `cu_mcp.server` and pass env vars via the MCP client config.

---

## Using the server in practice
Once an assistant is connected, you can ask natural language questions about credit unions. The AI will automatically use the MCP server to query the database.

### Example Questions You Can Ask:

**Search & Filter:**
- "Show me the largest credit unions in California"
- "Find credit unions in Washington with assets over $500M"
- "Which credit unions have 'Federal' in their name?"

**Performance Analysis:**
- "Compare Navy Federal and State Employees' FCU on efficiency and ROA"
- "Show me the most efficient credit unions in Texas"
- "Which credit unions have ROA above 1.5%?"

**Trends Over Time:**
- "How has SchoolsFirst's efficiency ratio changed over the last 3 quarters?"
- "Show Navy Federal's metrics over time"
- "Which credit unions improved their efficiency the most?"

**Comparisons & Rankings:**
- "What is the average efficiency ratio by state?"
- "Rank the top 10 credit unions by ROA"
- "Compare BECU to the Washington state average"

**Behind the Scenes:** The assistant may call `get_schema()` to understand the database structure or `get_example_queries()` to find proven SQL templates, then adapt them to answer your specific question.

---

## Tool reference
| Tool | When the assistant should use it | Key safeguards |
| --- | --- | --- |
| `execute_sql(query: str)` | Answer analytical questions, comparisons, rankings, KPI lookups | Read-only DuckDB connection, validates query starts with `SELECT`, blocks `DROP/DELETE/ALTER/...`, 10 s timeout, 1,000-row limit with warning |
| `get_schema(table_name: Optional[str])` | Understand available tables or inspect a single table/view | Adds friendly descriptions, column info, row counts, 3–5 sample rows (latest quarter when available) |
| `get_example_queries(category: Optional[str])` | Need inspiration for SQL patterns (“search”, “comparison”, “ranking”, “trends”, “financial_analysis”) | Returns curated, runnable SQL plus descriptions and use cases |

---

## What’s in the data?
- 11 quarters of call report data (Q1 2023 through Q3 2025)
- ~4,600 credit unions per quarter (~50k rows overall)
- `cu_with_ratios` view merges identity info with 15+ derived metrics:
  - ROA, efficiency ratio, loan-to-share ratio, net worth ratio
  - YOY growth for assets/loans/shares/members
  - Members per employee, indirect lending ratio, average member relationship
- Additional raw schedules (`foicu`, `fs220`, `acctdesc`, etc.) for deep dives. See `docs/ratio_formulas.md` and `docs/account_codes.md` for definitions.

---

## Example SQL library
A complete copy of the sample queries returned by `get_example_queries` lives in `examples/example_queries.md`. Categories include:
- **Search:** name lookups, multi-criteria filters, metric ranges
- **Comparison:** side-by-side CU comparisons, state peer context, national averages
- **Ranking:** top/bottom lists, percentile views, state-specific ranks
- **Trends:** quarter-over-quarter growth, YOY metrics, improving efficiency filters
- **Financial analysis:** multi-metric screens, correlation checks, geographic aggregates

All templates use the latest quarter via `(SELECT MAX(cycle_date) FROM cu_with_ratios)` unless the query explicitly looks across time.

---

## Testing checklist
- `python -m cu_mcp.server` starts without errors (FastMCP from `mcp[cli]` installed)
- `get_schema()` lists every table with helpful descriptions
- `get_schema('cu_with_ratios')` returns column metadata + sample rows
- `get_example_queries()` returns all categories; filtering works
- `execute_sql()` runs SELECT queries and rejects anything unsafe
- Results cap at 1,000 rows with a warning message
- Invalid SQL returns a user-friendly error plus a hint to call `get_schema`
- DuckDB is truly read-only (try a DELETE and watch it fail before hitting the database)
- Real prompts succeed via your MCP client of choice

---

## Troubleshooting
| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError: mcp.server.fastmcp` | MCP SDK not installed | Activate venv, run `pip install -r requirements.txt`, `pip install -e .` |
| `Database not found` error | Missing `data/cu_data.duckdb` | Copy/download file into `data/` (read-only) |
| MCP client never shows tools | Wrong command/args/cwd in config | Double-check absolute paths and that the venv is active |
| Timeout error from `execute_sql` | Query scanning too much data | Add filters or aggregate more aggressively |
| Results truncated at 1,000 rows | Query returns a huge set | Apply `LIMIT`, narrow the WHERE clause |

---

## Ideas for future versions (not yet implemented)
- Export-to-CSV tool (with row streaming)
- Chart-generation helper (ROA trends, state heatmaps)
- Automatic “favorite queries” library
- Additional datasets (FRED interest rates, BLS employment) for macro comparisons

---

## License & data use
All credit union data originates from the NCUA call reports (publicly available). Please cite NCUA when publishing insights.

Happy analyzing!
