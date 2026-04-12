# Chrome Extension Setup Guide

This guide explains how to build and load the Analytics Platform as a Chrome/Edge browser extension with a fixed right-side sidebar.

## Quick Start

### Prerequisites

- Node.js and npm installed
- Dependencies installed: `npm install` (in the `frontend/` directory)

### 1. Build the Extension

**Note:** The `dist/` folder is gitignored (as it should be). You need to build it locally.

```bash
cd frontend
npm run build:extension
```

Or use the shell script:
```bash
cd frontend
./build-extension.sh
```

This will:
- Build your React app with Vite
- Copy extension files (manifest.json, background.js, etc.) to `dist/`
- Copy public assets (logo, etc.) to `dist/`

### 2. Load in Chrome/Edge

1. Open Chrome/Edge and navigate to:
   - Chrome: `chrome://extensions/`
   - Edge: `edge://extensions/`

2. Enable **Developer mode** (toggle in top-right corner)

3. Click **"Load unpacked"**

4. Select the `frontend/dist/` folder

5. The extension icon should appear in your browser toolbar

### 3. Use the Extension

1. Visit any website
2. Click the extension icon in the toolbar
3. The Analytics sidebar will appear on the right side of the page
4. Click the icon again to hide/show the sidebar

## Features

- **Fixed Right Sidebar**: Appears as a 450px wide sidebar on the right side of any webpage
- **Resizable**: Drag the left edge of the sidebar to resize (300px - 800px)
- **Persistent State**: Remembers if sidebar was open/closed
- **Isolated**: Uses iframe to prevent conflicts with webpage styles
- **Full App**: All your React app features work normally in the sidebar

## Important Notes

- **`dist/` is gitignored** - This is correct! Build artifacts shouldn't be committed
- **Source files are in the repo** - All extension source files (manifest.json, background.js, content.js, etc.) are committed
- **Build locally** - Run `npm run build:extension` after cloning to create the `dist/` folder
- **One-time setup** - After building, you can load the extension. Rebuild only when you make changes

## File Structure

After building, your `frontend/dist/` folder contains:

```
dist/
├── manifest.json          # Extension manifest
├── background.js          # Service worker
├── content.js            # Content script (injects sidebar)
├── content.css           # Content script styles
├── sidebar.html          # React app entry point (for iframe)
├── index.html            # Regular web app entry (not used in extension)
├── assets/               # Built JavaScript and CSS
└── logo/                 # Extension icons
```

## Development

### Regular Web App (unchanged)
```bash
npm run dev
```
Your app works normally at `http://localhost:5173`

### Extension Build
```bash
npm run build:extension
```
Builds for extension with relative paths and copies all necessary files.

## Configuration

### Backend API URL

The extension uses the same `VITE_API_BASE_URL` environment variable. Make sure it's set in your `.env` file or the extension will use the default.

### Sidebar Width

Default width is 450px. To change it, edit `frontend/content.js`:
```javascript
width: 450px !important;  // Change this value
```

### Permissions

The extension requests:
- `storage` - For saving sidebar state
- `activeTab` - To inject sidebar into current tab
- `host_permissions` - To make API calls to your backend

## Troubleshooting

### Sidebar doesn't appear
- Check browser console for errors
- Verify extension is loaded (check `chrome://extensions/`)
- Make sure you clicked the extension icon

### Assets not loading
- Check that `logo/logo.png` exists in `dist/`
- Verify `web_accessible_resources` in `manifest.json` includes needed files

### API calls failing
- Check `host_permissions` in `manifest.json` includes your backend URL
- Verify `VITE_API_BASE_URL` is set correctly
- Check browser console for CORS errors (shouldn't happen with host_permissions)

### Build issues
- Make sure all dependencies are installed: `npm install`
- Check that `sidebar.html` is in the root of `frontend/`
- Verify Vite config has both `index.html` and `sidebar.html` as entry points

## Notes

- The app behaves **exactly the same** whether running as a web app or extension
- Extension context is automatically detected via `extensionContext.js` utility
- Asset paths are automatically adjusted for extension vs web context
- The sidebar uses an iframe for complete style isolation from web pages
