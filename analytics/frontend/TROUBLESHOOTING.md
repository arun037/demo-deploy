# Extension Troubleshooting Guide

## Sidebar Not Opening When Clicking Extension Icon

### Step 1: Check Browser Console

1. Open the webpage where you're testing
2. Press `F12` to open DevTools
3. Go to **Console** tab
4. Look for any errors (red text)

### Step 2: Check Extension Console

1. Go to `chrome://extensions/` or `edge://extensions/`
2. Find your extension
3. Click **"service worker"** link (for background.js)
4. Check for errors in the console

### Step 3: Check Content Script is Loading

1. Open DevTools on any webpage
2. Go to **Console** tab
3. Type: `document.getElementById('analytics-sidebar-root')`
4. If it returns `null`, the content script hasn't loaded yet
5. Try clicking the extension icon again

### Step 4: Verify Files Are Built

Make sure you ran:
```bash
cd frontend
npm run build:extension
```

Check that these files exist in `dist/`:
- ✅ manifest.json
- ✅ background.js
- ✅ content.js
- ✅ content.css
- ✅ sidebar.html
- ✅ assets/ folder with .js files
- ✅ logo/logo.png

### Step 5: Reload Extension

1. Go to `chrome://extensions/`
2. Find your extension
3. Click the **reload** icon (circular arrow)
4. Try clicking the extension icon again

### Step 6: Check Permissions

Make sure the extension has these permissions:
- ✅ storage
- ✅ activeTab
- ✅ scripting

### Step 7: Test on Different Pages

Some pages (like `chrome://` pages) cannot have content scripts injected. Try:
- Regular websites (http:// or https://)
- Not chrome://, edge://, or about: pages

### Step 8: Manual Test

Open browser console and run:
```javascript
// Check if content script loaded
console.log('Sidebar container:', document.getElementById('analytics-sidebar-root'));

// Manually trigger toggle
chrome.runtime.sendMessage({action: 'toggleSidebar'});
```

## Common Issues

### Issue: "Failed to load extension"
- **Solution**: Make sure `manifest.json` is in `dist/` folder

### Issue: Sidebar appears but is blank
- **Solution**: Check browser console for 404 errors on assets
- **Solution**: Verify `web_accessible_resources` in manifest includes `assets/*`

### Issue: Extension icon doesn't respond
- **Solution**: Check background.js console for errors
- **Solution**: Make sure `scripting` permission is in manifest

### Issue: Content script not running
- **Solution**: Check if page URL matches content script `matches` pattern
- **Solution**: Some pages (chrome://) cannot run content scripts

## Debug Mode

To enable more logging, the content.js and background.js files already have `console.log` statements. Check:
1. Background script console (click "service worker" in extensions page)
2. Content script console (regular page DevTools)
