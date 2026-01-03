# Credit Union Analytics MCP Server

Query NCUA credit union data using natural language through Claude! This **Model Context Protocol (MCP)** server is **live and ready to use** - just add the URL to your Claude client and start asking questions. No installation required.

🚀 **Live Server:** https://callreportmcp.fastmcp.app/mcp

---

## How to Connect

### Claude Code CLI:
```bash
claude mcp add --transport http credit-union-analytics https://callreportmcp.fastmcp.app/mcp
```

### Claude Desktop:
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "credit-union-analytics": {
      "url": "https://callreportmcp.fastmcp.app/mcp"
    }
  }
}
```

**That's it!** Once connected, Claude can answer questions about credit unions by querying the database automatically.

---

## Example Questions

**Search & Filter:**
- "Show me the top 10 largest credit unions"
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

---

## What's in the Data?

- **11 quarters** of NCUA call report data (Q1 2023 through Q3 2025)
- **~4,600 credit unions** per quarter (~50k rows total)
- **15+ pre-calculated financial ratios:**
  - ROA, efficiency ratio, loan-to-share ratio, net worth ratio
  - YOY growth for assets/loans/shares/members
  - Members per employee, indirect lending ratio, average member relationship
  - And more!

The server exposes three MCP tools:
1. **`execute_sql`** - Run read-only SELECT queries (10s timeout, 1,000 row limit)
2. **`get_schema`** - Inspect available tables, columns, and sample data
3. **`get_example_queries`** - Get curated SQL templates for common analyses

---

## Deploy Your Own

Want your own instance? Visit **[fastmcp.cloud](https://fastmcp.cloud)** (free during beta):

1. Fork this repo
2. Sign up and connect your GitHub account
3. Set entrypoint to: `src/cu_mcp/server.py:mcp`
4. Deploy - your server will be live at `https://your-project.fastmcp.app/mcp`

---

## License & Data Use

All credit union data originates from publicly available NCUA call reports. Please cite NCUA when publishing insights.

**Happy analyzing!** 📊
