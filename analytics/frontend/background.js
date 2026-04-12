// Background service worker for extension
chrome.action.onClicked.addListener(async (tab) => {
  try {
    // Try to send message to content script
    const response = await chrome.tabs.sendMessage(tab.id, { action: 'toggleSidebar' });
    console.log('Sidebar toggled:', response);
  } catch (error) {
    // Content script might not be loaded yet, try to inject it
    console.log('Content script not loaded, injecting...', error);
    try {
      // Check if we can inject (some pages like chrome:// are restricted)
      if (tab.url && (tab.url.startsWith('http://') || tab.url.startsWith('https://'))) {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['content.js']
        });
        // Wait a bit for script to initialize
        await new Promise(resolve => setTimeout(resolve, 100));
        // Try sending message again
        await chrome.tabs.sendMessage(tab.id, { action: 'toggleSidebar' });
      } else {
        console.error('Cannot inject into this page:', tab.url);
      }
    } catch (injectError) {
      console.error('Failed to inject content script:', injectError);
    }
  }
});
