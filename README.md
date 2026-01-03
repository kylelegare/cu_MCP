# Credit Union Analytics MCP Server

Query NCUA credit union data using natural language through Claude! This **Model Context Protocol (MCP)** server is **live and ready to use** - just add the URL to your AI assistant and start asking questions. No installation required.

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

### Claude.ai (Web):
1. Go to your conversation on [claude.ai](https://claude.ai)
2. Click the **connector icon** (🔌) in the message input area
3. Click **"Add connector"**
4. Enter the URL: `https://callreportmcp.fastmcp.app/mcp`
5. Name it: `Credit Union Analytics`

**Note:** On the web, you'll need to explicitly tell Claude to use the connector (e.g., "Use the Credit Union Analytics connector to find..."). Claude Desktop and CLI use it automatically.

### ChatGPT:
1. Go to ChatGPT and start a conversation
2. Click the **paperclip icon** to attach content
3. Select **"Connect to a data source"** or **"Custom connector"**
4. Enter the MCP server URL: `https://callreportmcp.fastmcp.app/mcp`

**Note:** ChatGPT's MCP support may vary. For best results, use Claude Desktop or Claude Code CLI.

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

## License & Data Use

All credit union data originates from publicly available NCUA call reports. Please cite NCUA when publishing insights.

**Happy analyzing!** 📊
