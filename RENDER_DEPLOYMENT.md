# Deploying Credit Union MCP Server to Render

This guide walks you through deploying the Credit Union MCP Server as a remote service on Render, making it accessible to anyone with the URL.

---

## Prerequisites

1. **GitHub Account** (to host the code)
2. **Render Account** (free tier works fine)
   - Sign up at: https://render.com

---

## Step 1: Push Code to GitHub

Since Render deploys from Git repositories, you need to push your code to GitHub first.

### Create a new GitHub repository:

1. Go to https://github.com/new
2. Name it: `credit-union-mcp` (or whatever you prefer)
3. Make it **Public** or **Private** (your choice)
4. **Don't** initialize with README (we already have one)
5. Click "Create repository"

### Push your code:

```bash
cd /Users/legare/Documents/coding/cu_MCP

# Initialize git (if not already)
git init

# Add all files (excluding .venv, etc. per .gitignore)
git add .

# Commit
git commit -m "Initial commit - Credit Union MCP Server"

# Add your GitHub repo as remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/credit-union-mcp.git

# Push to GitHub
git branch -M main
git push -u origin main
```

---

## Step 2: Deploy to Render

### Option A: One-Click Deploy (Easiest)

1. **Go to Render Dashboard**: https://dashboard.render.com
2. Click **"New +" → "Web Service"**
3. **Connect your GitHub repository**:
   - Click "Connect account" if first time
   - Select your `credit-union-mcp` repository
4. **Configure the service**:
   - **Name**: `credit-union-mcp` (or your choice)
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt && pip install -e .`
   - **Start Command**: `python -m cu_mcp.server --transport sse --port $PORT`
   - **Plan**: Free (or paid if you need more resources)
5. **Environment Variables**:
   - Click "Advanced"
   - Add: `PYTHON_VERSION` = `3.12.0`
6. Click **"Create Web Service"**

### Option B: Use render.yaml (Blueprint)

If you have `render.yaml` in your repo (already included), Render will auto-detect it:

1. Go to: https://dashboard.render.com/select-repo
2. Select your repository
3. Render will detect `render.yaml` and use those settings
4. Click "Apply"

---

## Step 3: Wait for Deployment

Render will:
1. Clone your repository
2. Install Python 3.12
3. Install dependencies (`pip install -r requirements.txt`)
4. Start the MCP server on SSE transport
5. Assign you a URL like: `https://credit-union-mcp.onrender.com`

This takes **3-5 minutes** for the first deployment.

---

## Step 4: Get Your Server URL

Once deployed, Render gives you a URL like:
```
https://credit-union-mcp-xyz123.onrender.com
```

**This is your remote MCP server URL!**

---

## Step 5: Connect to Your Remote MCP Server

### From Claude Code CLI:

```bash
claude mcp add --transport sse credit-union-analytics \
  https://credit-union-mcp-xyz123.onrender.com/sse
```

### From Claude Desktop:

Edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "credit-union-analytics": {
      "transport": "sse",
      "url": "https://credit-union-mcp-xyz123.onrender.com/sse"
    }
  }
}
```

---

## Testing Your Deployment

Once connected, test with:
- "Show me the top 10 largest credit unions"
- "What's Navy Federal's efficiency ratio?"

If it works, you're done! 🎉

---

## Important Notes

### Free Tier Limitations:
- Render's free tier **spins down after 15 minutes of inactivity**
- First request after spin-down takes 30-60 seconds to wake up
- 750 hours/month of runtime (enough for light usage)

### Database:
- The 124MB database is included in your deployment
- Render's free tier has 512MB disk space (plenty of room)
- Database is read-only so no data persistence issues

### Upgrading:
If you need always-on service:
- Upgrade to Render's **$7/month** plan
- Server stays awake 24/7
- Faster response times

---

## Troubleshooting

### "Build failed"
- Check Render logs for the error
- Usually means: missing dependency or Python version issue
- Make sure `runtime.txt` has `python-3.12.0`

### "Service unavailable"
- Free tier might be spinning down
- Wait 60 seconds and try again

### "MCP connection failed"
- Check your URL ends with `/sse`
- Verify the service is running in Render dashboard

### Need to update the code:
```bash
git add .
git commit -m "Update message"
git push
```
Render auto-deploys on push!

---

## Security Considerations

### Current Setup (Read-Only):
- ✅ Database is read-only
- ✅ Only SELECT queries allowed
- ✅ 10-second query timeout
- ✅ 1,000 row result limit
- ✅ No write operations possible

### Optional: Add Authentication

To restrict access, you can add API key authentication:
1. Add environment variable in Render: `MCP_API_KEY=your-secret-key`
2. Modify server.py to check the API key
3. Share the API key only with authorized users

(Let me know if you want help implementing this!)

---

## Costs

- **Free Tier**: $0/month
  - 750 hours runtime
  - 512MB storage
  - Spins down after 15 min inactivity

- **Starter Plan**: $7/month
  - Always-on (no spin down)
  - 25GB storage
  - Better for production use

---

## Next Steps

1. Deploy to Render following steps above
2. Share the URL with colleagues
3. They add it to their Claude Code or Claude Desktop
4. Everyone can query credit union data remotely!

**No installation required for users - just the URL!** 🚀
