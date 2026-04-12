/**
 * Utility functions to detect and handle extension context
 */

/**
 * Check if the app is running inside a Chrome extension
 */
export const isExtension = () => {
  return typeof chrome !== 'undefined' && 
         chrome.runtime && 
         chrome.runtime.id &&
         window.location.protocol === 'chrome-extension:';
};

/**
 * Get the base URL for assets when running in extension
 */
export const getAssetBaseUrl = () => {
  if (isExtension()) {
    return chrome.runtime.getURL('');
  }
  return '/';
};

/**
 * Get the full path to an asset
 */
export const getAssetPath = (path) => {
  // Remove leading slash if present
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  
  if (isExtension()) {
    return chrome.runtime.getURL(cleanPath);
  }
  return `/${cleanPath}`;
};

/**
 * Check if running in sidebar iframe
 */
export const isSidebarContext = () => {
  return isExtension() && window.self !== window.top;
};
