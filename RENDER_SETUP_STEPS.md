# Render Deployment Steps - Your Code is Ready!

✅ Your code is on GitHub: https://github.com/kylelegare/cu_MCP

Now follow these steps to deploy to Render:

---

## Step 1: Go to Render

Open this link: **https://dashboard.render.com/register**

- Sign up with GitHub (easiest)
- Or create account with email

---

## Step 2: Create New Web Service

Once logged in:

1. Click the big blue **"New +"** button (top right)
2. Select **"Web Service"**

---

## Step 3: Connect GitHub Repository

1. Click **"Connect account"** next to GitHub
2. Authorize Render to access your GitHub
3. You'll see a list of your repositories
4. Find and click **"Connect"** next to `kylelegare/cu_MCP`

---

## Step 4: Configure the Service

Render auto-detects most settings from your `render.yaml` file, but verify:

**Basic Settings:**
- **Name**: `credit-union-mcp` (or whatever you want)
- **Region**: Choose closest to you
- **Branch**: `main`
- **Runtime**: `Python 3`

**Build & Deploy:**
- **Build Command**: `pip install -r requirements.txt && pip install -e .`
- **Start Command**: `python -m cu_mcp.server --transport sse --port $PORT`

**Plan:**
- Select **"Free"** (or paid if you want always-on)

---

## Step 5: Advanced Settings (Optional)

Click **"Advanced"** and add environment variable:
- Key: `PYTHON_VERSION`
- Value: `3.12.0`

(This ensures Python 3.12 is used)

---

## Step 6: Deploy!

1. Click the big **"Create Web Service"** button at the bottom
2. Render will start building your service
3. Watch the logs - it takes **3-5 minutes**

You'll see:
```
==> Installing dependencies
==> Starting server
==> Deploy successful!
```

---

## Step 7: Get Your URL

Once deployed, Render shows your service URL at the top:

**Something like:**
```
https://credit-union-mcp-abc123.onrender.com
```

**Copy this URL!**

---

## Step 8: Test It

Your MCP server is now live!

To connect from Claude Code:
```bash
claude mcp add --transport sse credit-union-analytics \
  https://YOUR-RENDER-URL.onrender.com/sse
```

Then ask Claude Code:
- "Show me the top 10 largest credit unions"

---

## 🎉 You're Done!

Your MCP server is:
- ✅ Running on Render
- ✅ Accessible via URL
- ✅ Ready to share with anyone

**Share the URL with your team** - they just add it to their Claude client and can start querying!

---

## Important Notes

### Free Tier Behavior:
- Server sleeps after 15 minutes of no activity
- First request after sleep takes ~60 seconds to wake up
- 750 hours/month of runtime (plenty for team use)

### Upgrading:
- $7/month for always-on service
- No sleep, instant responses

### Updating Your Server:
When you make changes:
```bash
git add .
git commit -m "Update description"
git push
```
Render auto-deploys in 2-3 minutes!

---

## Need Help?

If deployment fails, check Render logs for errors. Common issues:
- Python version (make sure 3.12 is specified)
- Missing dependencies (check requirements.txt)
- Port configuration (should use $PORT variable)

All of these are already configured correctly in your code!

---

**Ready? Go to Step 1!**

https://dashboard.render.com/register
