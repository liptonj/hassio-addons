# Quick Start Guide

Get up and running with ThousandEyes Enterprise Agent in 5 minutes!

## Prerequisites

✅ Home Assistant with Supervisor installed  
✅ ThousandEyes account with active subscription  
✅ Minimum 2GB RAM available  

## Step 1: Get Your Token (2 minutes)

1. Visit [ThousandEyes Portal](https://app.thousandeyes.com)
2. Navigate to: **Cloud & Enterprise Agents** → **Agent Settings**
3. Click **Add New Enterprise Agent**
4. Copy the **Account Group Token** (starts with a long string of characters)

Keep this token handy - you'll need it in Step 3!

## Step 2: Install Add-on (1 minute)

### For Local Testing

1. Copy all files to `/addons/thousandeyes-agent/` on your Home Assistant
2. In Home Assistant UI: **Settings** → **Add-ons** → **Add-on Store**
3. Click ⋮ menu → **Check for updates**
4. Refresh browser (Ctrl+F5)
5. Find add-on in **Local add-ons** section
6. Click **Install**

### For Production

1. Add repository URL in Add-on Store
2. Find "ThousandEyes Enterprise Agent"
3. Click **Install**

## Step 3: Configure (1 minute)

1. Click on the add-on
2. Go to **Configuration** tab
3. Add your token:

```yaml
account_token: "your-token-from-step-1"
```

4. Click **Save**

That's it! Just the token is required for basic setup.

### Optional: Give it a name

```yaml
account_token: "your-token-here"
agent_hostname: "home-network"
```

## Step 4: Start (30 seconds)

1. Go to **Info** tab
2. Click **Start**
3. Click **Log** tab
4. Wait for: `Starting ThousandEyes Enterprise Agent with configured settings`

✅ Green checkmark means success!

## Step 5: Verify (1 minute)

1. Go back to [ThousandEyes Portal](https://app.thousandeyes.com)
2. Navigate to: **Cloud & Enterprise Agents** → **Agent Settings**
3. Wait 2-5 minutes for agent to appear
4. Look for your agent (with hostname if you set one)
5. Status should show **Online** (green dot)

🎉 **Congratulations!** Your agent is now running!

## Next Steps

### Assign Your First Test

1. In ThousandEyes portal: **Cloud & Enterprise Agents** → **Test Settings**
2. Create new test or edit existing one
3. In **Agents** section, select your new agent
4. Save test
5. Results will appear within 1-2 minutes

### Common Test Types

- **HTTP Server**: Monitor website availability
- **Page Load**: Test web page performance
- **Network**: Measure latency and packet loss
- **DNS Server**: Monitor DNS resolution

## Troubleshooting

### Agent won't start
- **Check**: Did you enter the account token?
- **Fix**: Add token in Configuration tab

### Agent not in portal
- **Wait**: Can take up to 5 minutes
- **Check**: Review logs for errors
- **Fix**: Verify token is correct

### Behind a proxy?
Add to configuration:
```yaml
account_token: "your-token"
proxy_enabled: true
proxy_host: "proxy.example.com"
proxy_port: 8080
```

## Need More Help?

- 📖 Full documentation: [README.md](README.md)
- 🔧 Detailed setup: [INSTALL.md](INSTALL.md)
- 📚 All options: [DOCS.md](DOCS.md)
- 🐛 Issues: Check GitHub Issues
- 💬 Questions: Home Assistant Community Forum

## Configuration Examples

### Minimal (Just Works)
```yaml
account_token: "abc123..."
```

### Recommended
```yaml
account_token: "abc123..."
agent_hostname: "home-lab"
memory_limit: "2048"
log_level: "INFO"
```

### With Proxy
```yaml
account_token: "abc123..."
proxy_enabled: true
proxy_host: "proxy.corp.com"
proxy_port: 8080
proxy_user: "username"
proxy_pass: "password"
```

### With Custom DNS
```yaml
account_token: "abc123..."
custom_dns_enabled: true
custom_dns_servers:
  - "8.8.8.8"
  - "8.8.4.4"
```

## Pro Tips

💡 **Tip 1**: Give your agent a meaningful hostname like "home-office" or "garage-pi"

💡 **Tip 2**: Start with INFO log level, change to DEBUG only when troubleshooting

💡 **Tip 3**: Keep auto_update enabled to get latest agent features automatically

💡 **Tip 4**: Monitor Home Assistant system resources - agent uses ~1-2GB RAM

💡 **Tip 5**: Assign tests gradually - don't overload your agent initially

## Success Checklist

- [x] ThousandEyes account created
- [x] Account token obtained
- [x] Add-on installed
- [x] Token configured
- [x] Add-on started
- [x] Agent appears in portal
- [x] Agent shows "Online" status
- [ ] First test assigned
- [ ] Test results visible
- [ ] Monitoring network like a pro! 🚀

---

**Time to complete**: ~5 minutes  
**Difficulty**: Easy  
**Prerequisites**: ThousandEyes account, Home Assistant with Supervisor

Enjoy monitoring your network! 📊

