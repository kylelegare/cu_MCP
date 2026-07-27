# Credit Union Analytics MCP Server

Query NCUA credit union data using natural language through Claude! This **Model Context Protocol (MCP)** server is **live and ready to use** - just add the URL to your AI assistant and start asking questions. No installation required.

Live Server: https://callreportmcp.fastmcp.app/mcp

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
2. Click the **connector icon** in the message input area
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

- **13 quarters** of NCUA call report data (Q1 2023 through Q1 2026)
- **~4,300 credit unions** per quarter (~60k rows total)
- **15+ pre-calculated financial ratios:**
  - ROA, efficiency ratio, loan-to-share ratio, net worth ratio
  - YOY growth for assets/loans/shares/members
  - Members per employee, indirect lending ratio, average member relationship
  - Net interest margin, delinquency ratio, coverage ratio
  - And more!

Income-statement-based ratios are annualized from the NCUA's year-to-date call report fields, so Q2/Q3/Q4 values stay comparable to Q1 and year-end figures.

The server exposes one tool:
- **`search_credit_unions`** - Query credit union data with SQL (10s timeout, 1,000 row limit, $25M asset floor by default)

For deeper exploration, the tool also supports querying raw NCUA tables (`foicu`, `fs220`, `fs220a`-`fs220r`) and an `acctdesc` reference table for account code lookups.

---

## License & Data Use

All credit union data originates from publicly available NCUA call reports. Please cite NCUA when publishing insights.

## Maintenance

NCUA publishes a new call report cycle roughly 10 weeks after each quarter end, at a
predictable URL: `https://www.ncua.gov/files/publications/analysis/call-report-data-YYYY-MM.zip`.
There is no notification feed, and revised cycles are re-published silently at the same
URL — so [`scripts/refresh_data.py`](scripts/refresh_data.py) polls instead, recording each
cycle's upstream `Last-Modified` in [`data/source_manifest.json`](data/source_manifest.json).

```bash
# Is anything new or revised upstream? (exit 1 when work is pending)
python scripts/refresh_data.py check

# Download and load whatever check found
python scripts/refresh_data.py sync

# Or load a zip you already downloaded
python scripts/refresh_data.py ingest --zip call-report-data-2026-03.zip
```

Ingest backs up the database first, loads every quarterly table in one transaction,
adds any account columns NCUA introduced that quarter, refuses to insert a cycle that
would silently drop values in a type conversion, replaces `acctdesc`, reapplies
[`scripts/rebuild_cu_with_ratios.sql`](scripts/rebuild_cu_with_ratios.sql), and prints
recent-quarter medians so an obviously bad load is visible before you commit.

After a successful run, commit `data/cu_data.duckdb` (Git LFS) and
`data/source_manifest.json` and redeploy.

### Automated refresh

[`.github/workflows/refresh-data.yml`](.github/workflows/refresh-data.yml) runs the
above every Monday and opens a pull request when NCUA publishes or revises a cycle —
so a refresh is a review-and-merge, not a chore you have to remember.

The check runs *without* Git LFS on purpose. It only needs `source_manifest.json`, and
materializing the 132MB database weekly would spend most of a free-tier LFS bandwidth
allowance to learn that nothing changed. The full download happens only in the refresh
job, roughly four times a year.

`check` exits `0` when current, `1` when cycles are pending, and `2` if the check itself
failed, so it drives a scheduler without log-scraping. `--json` emits a parseable summary
on stdout with diagnostics on stderr. The whole pipeline depends on `duckdb` plus the
standard library, so it also runs fine from plain cron:

```cron
# Mail you only when something is actually pending
0 9 * * 1 cd /path/to/cu_MCP && .venv/bin/python scripts/refresh_data.py check
```
