# Installation Guide

## Prerequisites

1. **Home Assistant Installation**
   - Running Home Assistant with Supervisor (required for add-ons)
   - Admin access to Home Assistant

2. **ThousandEyes Account**
   - Active ThousandEyes subscription
   - Account Group Token (from ThousandEyes portal)

3. **Network Requirements**
   - Internet connectivity (HTTPS port 443 outbound)
   - If behind proxy: proxy configuration details
   - Minimum 2GB RAM available for the agent

## Installation Methods

### Method 1: Local Add-on (Development/Testing)

#### Step 1: Access Add-ons Directory

**Using Samba (Recommended for macOS/Windows):**
1. Install and start the Samba add-on from Home Assistant
2. On macOS: Press `CMD+K` in Finder, enter `smb://homeassistant.local`
3. On Windows: Open File Explorer, enter `\\homeassistant.local\` in address bar
4. Navigate to the `addons` folder

**Using SSH:**
1. Install and configure the SSH add-on
2. SSH to your Home Assistant: `ssh root@homeassistant.local`
3. Navigate to: `cd /addons`

#### Step 2: Copy Add-on Files

1. Create directory: `mkdir -p /addons/thousandeyes-agent`
2. Copy all files from this repository to `/addons/thousandeyes-agent/`:
   - `config.yaml`
   - `Dockerfile`
   - `run.sh`
   - `README.md`
   - `CHANGELOG.md`
   - `build.yaml`
   - (optional) `icon.png`

#### Step 3: Install in Home Assistant

1. Open Home Assistant web interface
2. Navigate to **Settings** → **Add-ons**
3. Click **Add-on Store** (bottom right)
4. Click the three-dot menu (⋮) in top right
5. Click **Check for updates**
6. Refresh your browser (Ctrl+F5 or Cmd+Shift+R)
7. Look for **Local add-ons** section at the top
8. You should see "ThousandEyes Enterprise Agent"
9. Click on it and click **Install**

### Method 2: Custom Repository (Recommended for Production)

#### Step 1: Host Repository

1. Fork this repository on GitHub
2. Or create your own repository with these files

#### Step 2: Add Repository to Home Assistant

1. Open Home Assistant web interface
2. Navigate to **Settings** → **Add-ons**
3. Click **Add-on Store** (bottom right)
4. Click the three-dot menu (⋮) in top right
5. Click **Repositories**
6. Add your repository URL: `https://github.com/liptonj/thousandeyes-homeassistant-addon`
7. Click **Add**
8. Close the dialog

#### Step 3: Install Add-on

1. Refresh the Add-on Store
2. Find "ThousandEyes Enterprise Agent" in the list
3. Click on it and click **Install**
4. Wait for installation to complete

## Configuration

### Step 1: Get ThousandEyes Token

1. Log in to [ThousandEyes Portal](https://app.thousandeyes.com)
2. Go to **Cloud & Enterprise Agents** → **Agent Settings**
3. Click **Add New Enterprise Agent**
4. Copy the **Account Group Token**

### Step 2: Configure Add-on

1. In Home Assistant, go to the add-on page
2. Click on the **Configuration** tab
3. Add your configuration:

**Minimal (Required):**
```yaml
account_token: "paste-your-token-here"
```

**Recommended:**
```yaml
account_token: "paste-your-token-here"
agent_hostname: "homeassistant-main"
memory_limit: "2048"
log_level: "INFO"
```

4. Click **Save**

### Step 3: Start Add-on

1. Click on the **Info** tab
2. Click **Start**
3. Wait for the add-on to start (check logs)
4. Click on **Log** tab to view startup messages

## Verification

### Check Add-on Logs

1. In Home Assistant add-on page, click **Log** tab
2. Look for successful startup messages:
   ```
   [INFO] Starting ThousandEyes Enterprise Agent...
   [INFO] Account token configured
   [INFO] Starting ThousandEyes Enterprise Agent with configured settings
   ```

### Check ThousandEyes Portal

1. Log in to [ThousandEyes Portal](https://app.thousandeyes.com)
2. Go to **Cloud & Enterprise Agents** → **Agent Settings**
3. Wait 2-5 minutes for agent to register
4. Your agent should appear in the list
5. Verify it shows as **Online**

## Post-Installation

### Assign Tests

1. In ThousandEyes portal, create or edit a test
2. In the **Agents** section, select your new agent
3. Save the test
4. Wait for test results to appear

### Monitor Performance

1. Check Home Assistant system resources
2. Verify agent is using expected memory (~1-2 GB)
3. Review test results in ThousandEyes portal

## Troubleshooting Installation

### Add-on doesn't appear in store

1. Refresh browser cache (Ctrl+F5 or Cmd+Shift+R)
2. Check Supervisor logs:
   - **Settings** → **System** → **Logs**
   - Select **Supervisor** from dropdown
3. Look for YAML validation errors
4. Verify all required files are present
5. Click "Check for updates" again

### Installation fails

1. Check Home Assistant logs
2. Ensure adequate disk space (>1GB free)
3. Verify internet connectivity
4. Try restarting Home Assistant Supervisor

### Can't find addons directory

**For Samba:**
- Verify Samba add-on is running
- Check Samba add-on configuration
- Try IP address instead: `smb://192.168.1.x`

**For SSH:**
- Verify SSH add-on configuration
- Ensure SSH keys are configured
- Try absolute path: `/mnt/data/supervisor/addons/`

### Agent not starting

1. Check you've entered the account token
2. Review logs for specific error messages
3. Verify minimum resource requirements
4. Check network connectivity

## Updating

### Update Add-on

1. Home Assistant will notify you of updates
2. Go to the add-on page
3. Click **Update**
4. Wait for update to complete
5. Restart the add-on if needed

### Update Agent (ThousandEyes)

The agent auto-updates by default. To disable:
```yaml
auto_update: false
```

## Uninstallation

1. Stop the add-on
2. Click **Uninstall**
3. Confirm uninstallation
4. (Optional) Remove agent from ThousandEyes portal
5. (Optional) Remove repository from Home Assistant

## Getting Help

- **Add-on Issues**: Check GitHub issues
- **ThousandEyes Help**: [ThousandEyes Support](https://docs.thousandeyes.com/)
- **Home Assistant Help**: [Home Assistant Community](https://community.home-assistant.io/)

## Next Steps

After successful installation:
1. Read [README.md](README.md) for configuration options
2. Read [DOCS.md](DOCS.md) for detailed documentation
3. Configure additional options as needed
4. Set up tests in ThousandEyes portal
5. Monitor your network!

