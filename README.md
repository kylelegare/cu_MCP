# Credit Union Analytics MCP Server

Query NCUA credit union data using natural language through Claude! This **Model Context Protocol (MCP)** server is **deployed on Render** - just add the URL to your Claude client and start asking questions. No installation required.

🚀 **Live Server:** https://cu-mcp.onrender.com

Ask questions like:
- "Show me the top 10 largest credit unions"
- "Compare efficiency ratios for Washington credit unions"
- "What's Navy Federal's ROA in the latest quarter?"

The AI automatically queries 11 quarters of NCUA call report data with pre-calculated financial ratios.

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

## What You Need

To use this server, you just need **one of these**:
- ✅ **Claude Code CLI** - Command-line interface
- ✅ **Claude Desktop** - Desktop application
- ✅ **Any MCP-compatible client**

**No Python installation required** - the server is already hosted on Render!

---

## 🚀 Using the Server (No Installation!)

This server is deployed on Render. Just add the URL to your Claude client:

### For Claude Code CLI:
```bash
claude mcp add --transport sse credit-union-analytics \
  https://cu-mcp.onrender.com/sse
```

### For Claude Desktop:
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "credit-union-analytics": {
      "transport": "sse",
      "url": "https://cu-mcp.onrender.com/sse"
    }
  }
}
```

**That's it!** Now ask Claude questions about credit unions.

---

## 🛠️ Deploying Your Own Instance

Want to deploy your own version? See **`RENDER_DEPLOYMENT.md`** for step-by-step instructions.

**Quick version:**
1. Fork this repo
2. Sign up at Render.com (free)
3. Connect your GitHub repo
4. Deploy (takes 5 minutes)
5. Get your URL and share it!

---

## 💻 Local Development (Optional)

If you want to run the server locally for development:

<details>
<summary>Click to expand local setup instructions</summary>

### Prerequisites:
- Python 3.12+
- pip

### Setup:
```bash
# Clone the repo
git clone https://github.com/kylelegare/cu_MCP.git
cd cu_MCP

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Run the server
python -m cu_mcp.server
```

### Connect locally:

**Claude Code CLI:**
```bash
claude mcp add --transport stdio credit-union-analytics -- \
  /absolute/path/to/cu_MCP/.venv/bin/python -m cu_mcp.server
```

**Claude Desktop** (`claude_desktop_config.json`):
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

</details>

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
