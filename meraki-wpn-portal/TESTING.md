# 🎉 Meraki WPN Portal - Running in Standalone Mode

## ✅ Container Status

The Docker container is **running successfully** with the new editable Settings UI!

```
Container Name: meraki-portal-test
Status: Running
Port: 8090 → 8080
```

## 🌐 Access Information

### Public Portal
- **URL**: http://localhost:8090
- **Features**: Self-registration, My Network lookup

### Admin Portal
- **URL**: http://localhost:8090/admin
- **Username**: `admin`
- **Password**: `admin123`

### Settings UI (NEW!)
- **URL**: http://localhost:8090/admin/settings
- **Full configuration management available**

## 🎨 What You Can Test

### 1. Admin Login
1. Go to http://localhost:8090/admin
2. Login with `admin` / `admin123`
3. You'll see the admin dashboard

### 2. Settings UI (Main Feature!)
1. Click "Settings" in the admin nav
2. You can now **edit all settings**:
   - ✅ Meraki API Key
   - ✅ Admin Password (change it!)
   - ✅ OAuth/SSO (Duo & Entra ID)
   - ✅ Portal Branding
   - ✅ Network Defaults
   - ✅ Registration Options

3. **Actions Available**:
   - **Save Changes** - Persist to file
   - **Test Connection** - Validate Meraki API
   - **Reset to Defaults** - Restore defaults
   - **Change Password** - Update admin password

### 3. Features to Test

#### Update Meraki API Key
1. Navigate to Settings
2. Enter your real Meraki API key
3. Click "Test Connection" to validate
4. Click "Save Changes"

#### Configure OAuth
1. Enable OAuth toggle
2. Select provider (Duo or Entra ID)
3. Enter credentials
4. Save changes

#### Change Branding
1. Update Property Name
2. Change primary color with color picker
3. Add logo URL
4. Save and see changes in public portal

#### Change Admin Password
1. Click "Change Admin Password"
2. Enter current password
3. Enter new password
4. Confirm new password
5. Save

## 📊 Logs

To view real-time logs:
```bash
docker logs -f meraki-portal-test
```

## 🛑 Stop Container

```bash
docker stop meraki-portal-test
docker rm meraki-portal-test
```

## 🔄 Restart Container

```bash
docker restart meraki-portal-test
```

## 📁 Data Persistence

All data is stored in:
```
./meraki-wpn-portal/data/
├── meraki_wpn_portal.db          # SQLite database
└── config/
    └── portal_settings.json       # Encrypted settings file
```

## 🔐 Security Notes

1. **Secrets are encrypted** - Settings file uses Fernet encryption
2. **Encryption key** - Generated automatically, check logs for `SETTINGS_ENCRYPTION_KEY`
3. **Production** - Set `SETTINGS_ENCRYPTION_KEY` env var to persist key across restarts
4. **Change default password** - Use the Settings UI to update admin password

## 🎯 Next Steps

1. **Test the Settings UI** - Navigate to http://localhost:8090/admin/settings
2. **Add real Meraki API key** - Replace `your-api-key-here`
3. **Configure OAuth** (optional) - Set up Duo or Entra ID
4. **Customize branding** - Update colors, logo, property name
5. **Test self-registration** - Go to http://localhost:8090 (public portal)

## 🐛 Troubleshooting

### Settings not saving?
- Check logs: `docker logs meraki-portal-test`
- Verify `EDITABLE_SETTINGS=true` is set
- Ensure running in standalone mode

### OAuth not working?
- Click "Test Connection" to validate credentials
- Check callback URL matches your OAuth app config
- View logs for detailed error messages

### Port conflict?
```bash
# Use a different port
docker stop meraki-portal-test && docker rm meraki-portal-test
docker run -d --name meraki-portal-test -p 8091:8080 \
  -e RUN_MODE=standalone \
  -e EDITABLE_SETTINGS=true \
  -e ADMIN_USERNAME=admin \
  -e ADMIN_PASSWORD=admin123 \
  --entrypoint /run-standalone.sh \
  meraki-wpn-portal:test
```

## ✨ Key Features Working

- ✅ FastAPI backend running
- ✅ React frontend built and served
- ✅ Admin authentication
- ✅ Editable Settings UI
- ✅ Encrypted settings storage
- ✅ OAuth configuration support
- ✅ Meraki API integration
- ✅ Database persistence

**Everything is ready to test!** 🚀
