# 🔄 Browser Cache Issue - How to See Your Changes

## The Problem
Your browser has cached the old JavaScript/CSS files. The new container is running with updated code, but your browser is showing the old version.

## Solution: Hard Refresh / Clear Cache

### Option 1: Hard Refresh (Fastest)

**Chrome / Edge (Windows/Linux):**
```
Ctrl + Shift + R
```
or
```
Ctrl + F5
```

**Chrome / Edge (Mac):**
```
Cmd + Shift + R
```

**Firefox (Windows/Linux):**
```
Ctrl + Shift + R
```
or
```
Ctrl + F5
```

**Firefox (Mac):**
```
Cmd + Shift + R
```

**Safari (Mac):**
```
Cmd + Option + R
```

### Option 2: Clear Browser Cache

**Chrome/Edge:**
1. Press `F12` to open DevTools
2. Right-click the refresh button
3. Select "Empty Cache and Hard Reload"

**Firefox:**
1. Press `F12` to open DevTools
2. Right-click refresh button
3. Select "Empty Cache and Hard Reload"

**Safari:**
1. Safari menu → Clear History
2. Select "all history"
3. Click "Clear History"

### Option 3: Incognito/Private Window

**Chrome/Edge:**
```
Ctrl + Shift + N  (Windows/Linux)
Cmd + Shift + N   (Mac)
```

**Firefox:**
```
Ctrl + Shift + P  (Windows/Linux)
Cmd + Shift + P   (Mac)
```

**Safari:**
```
Cmd + Shift + N   (Mac)
```

Then visit: http://localhost:8090/admin/login

---

## Verify New Version is Loading

### Check the Console
1. Open DevTools (`F12`)
2. Go to "Network" tab
3. Refresh the page
4. Look for `index-Cp02-Faf.js` (new file)
   - If you see `index-C0UWSq6-.js` (old file), cache not cleared

### Check Application Tab
1. Open DevTools (`F12`)
2. Go to "Application" tab
3. Click "Clear site data"
4. Refresh

---

## Quick Test

After clearing cache, you should see:

1. **Login Page** at http://localhost:8090/admin/login
   - Username/password form
   - "Admin Login" heading
   - Meraki blue gradient background

2. **Redirects** when accessing admin routes directly:
   - http://localhost:8090/admin → redirects to login
   - http://localhost:8090/admin/settings → redirects to login

3. **After Login**:
   - Dashboard with stats
   - Settings with EDITABLE form (not "Home Assistant" message)

---

## Still Not Working?

Try this terminal command to verify the backend is serving the new build:

```bash
# Check the JS file hash
curl -s http://localhost:8090/ | grep -o 'index-[^.]*\.js'

# Should output: index-Cp02-Faf.js (new version)
# If it shows: index-C0UWSq6-.js (old version, restart container)
```

If the hash is correct (`index-Cp02-Faf.js`), it's 100% a browser cache issue.

---

## Development Tip

To avoid cache issues in the future:

1. Keep DevTools open (`F12`)
2. Go to Network tab
3. Check "Disable cache" checkbox
4. Refresh will always get latest files

---

## Current Container Info

```
Container: meraki-portal-test
Port: 8090
Status: Running ✅
Frontend: index-Cp02-Faf.js (NEW BUILD)
```

The new code IS running in the container. Your browser just needs to download it!
