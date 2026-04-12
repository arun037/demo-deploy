// Content script to inject sidebar into web pages
let sidebarContainer = null;
let isVisible = false;
let sidebarIframe = null;
let currentSidebarWidth = 450; // Store current width
let pageAdjustmentStyle = null; // Style element for page adjustment

// Adjust webpage to make room for sidebar
// Prevents horizontal scroll without creating white space
function adjustPageForSidebar(width) {
  if (!pageAdjustmentStyle) {
    pageAdjustmentStyle = document.createElement('style');
    pageAdjustmentStyle.id = 'analytics-sidebar-page-adjustment';
    document.head.appendChild(pageAdjustmentStyle);
  }
  
  if (isVisible && width > 0) {
    // Simply prevent horizontal scroll - sidebar overlays content
    // This prevents white space while still allowing sidebar to work
    pageAdjustmentStyle.textContent = `
      html {
        overflow-x: hidden !important;
      }
      body {
        overflow-x: hidden !important;
      }
    `;
  } else {
    // Restore normal scroll when sidebar is hidden
    pageAdjustmentStyle.textContent = `
      html {
        overflow-x: auto !important;
      }
      body {
        overflow-x: auto !important;
      }
    `;
  }
}

// Create the sidebar container
function createSidebar() {
  if (sidebarContainer) return;
  
  // Create fixed position container
  sidebarContainer = document.createElement('div');
  sidebarContainer.id = 'analytics-sidebar-root';
  sidebarContainer.style.cssText = `
    position: fixed !important;
    top: 0 !important;
    right: 0 !important;
    width: ${currentSidebarWidth}px !important;
    height: 100vh !important;
    z-index: 2147483647 !important;
    background: white !important;
    box-shadow: -2px 0 10px rgba(0,0,0,0.1) !important;
    display: none !important;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    transition: width 0.2s ease !important;
  `;
  
  // Create iframe for React app (better isolation from page styles)
  sidebarIframe = document.createElement('iframe');
  sidebarIframe.src = chrome.runtime.getURL('sidebar.html');
  sidebarIframe.style.cssText = `
    width: 100% !important;
    height: 100% !important;
    border: none !important;
    display: block !important;
  `;
  sidebarIframe.setAttribute('allow', 'microphone');
  
  sidebarContainer.appendChild(sidebarIframe);
  document.body.appendChild(sidebarContainer);
  
  // Add resize handle
  addResizeHandle();
}

// Add resize handle to allow users to resize sidebar
function addResizeHandle() {
  const handle = document.createElement('div');
  handle.id = 'analytics-sidebar-resize-handle';
  handle.style.cssText = `
    position: absolute !important;
    left: 0 !important;
    top: 0 !important;
    width: 4px !important;
    height: 100% !important;
    cursor: ew-resize !important;
    background: transparent !important;
    z-index: 2147483648 !important;
  `;
  
  // Add hover effect
  handle.addEventListener('mouseenter', () => {
    handle.style.background = 'rgba(59, 130, 246, 0.3)';
  });
  handle.addEventListener('mouseleave', () => {
    if (!handle.dataset.resizing) {
      handle.style.background = 'transparent';
    }
  });
  
  let isResizing = false;
  let startX = 0;
  let startWidth = currentSidebarWidth;
  
  handle.addEventListener('mousedown', (e) => {
    isResizing = true;
    handle.dataset.resizing = 'true';
    startX = e.clientX;
    startWidth = currentSidebarWidth;
    document.body.style.cursor = 'ew-resize';
    document.body.style.userSelect = 'none';
    handle.style.background = 'rgba(59, 130, 246, 0.5)';
    e.preventDefault();
    e.stopPropagation();
  });
  
  const handleMouseMove = (e) => {
    if (!isResizing) return;
    
    // Calculate new width: dragging left (negative diff) = smaller, dragging right (positive diff) = larger
    const diff = startX - e.clientX; // When dragging left, e.clientX decreases, diff is positive = smaller width
    const newWidth = Math.max(300, Math.min(800, startWidth + diff));
    
    currentSidebarWidth = newWidth;
    sidebarContainer.style.width = newWidth + 'px';
    
    // Update page adjustment
    if (isVisible) {
      adjustPageForSidebar(newWidth);
    }
  };
  
  const handleMouseUp = () => {
    if (isResizing) {
      isResizing = false;
      delete handle.dataset.resizing;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      handle.style.background = 'transparent';
      
      // Save width to storage
      chrome.storage.local.set({ sidebarWidth: currentSidebarWidth });
    }
  };
  
  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
  
  // Also handle mouse leave to stop resizing if mouse leaves window
  document.addEventListener('mouseleave', handleMouseUp);
  
  sidebarContainer.appendChild(handle);
}

// Toggle sidebar visibility
function toggleSidebar() {
  console.log('Toggle sidebar called, current state:', isVisible);
  
  if (!sidebarContainer) {
    console.log('Creating sidebar container...');
    createSidebar();
  }
  
  isVisible = !isVisible;
  console.log('Setting sidebar visibility to:', isVisible);
  
  if (sidebarContainer) {
    sidebarContainer.style.display = isVisible ? 'block' : 'none';
    console.log('Sidebar display set to:', sidebarContainer.style.display);
    
    // Adjust webpage when sidebar opens/closes
    adjustPageForSidebar(isVisible ? currentSidebarWidth : 0);
  } else {
    console.error('Sidebar container is null!');
  }
  
  // Save state to storage
  chrome.storage.local.set({ 
    sidebarVisible: isVisible,
    sidebarWidth: currentSidebarWidth 
  }).catch(err => {
    console.error('Failed to save sidebar state:', err);
  });
}

// Initialize sidebar on page load
function initSidebar() {
  if (document.body) {
    createSidebar();
    // Restore previous state (visibility and width)
    chrome.storage.local.get(['sidebarVisible', 'sidebarWidth'], (result) => {
      if (result.sidebarWidth && result.sidebarWidth >= 300 && result.sidebarWidth <= 800) {
        currentSidebarWidth = result.sidebarWidth;
        if (sidebarContainer) {
          sidebarContainer.style.width = currentSidebarWidth + 'px';
        }
      }
      
      if (result.sidebarVisible) {
        isVisible = true;
        if (sidebarContainer) {
          sidebarContainer.style.display = 'block';
          adjustPageForSidebar(currentSidebarWidth);
        }
      }
    });
  } else {
    // Wait for body to be available
    const observer = new MutationObserver(() => {
      if (document.body) {
        observer.disconnect();
        createSidebar();
        chrome.storage.local.get(['sidebarVisible', 'sidebarWidth'], (result) => {
          if (result.sidebarWidth && result.sidebarWidth >= 300 && result.sidebarWidth <= 800) {
            currentSidebarWidth = result.sidebarWidth;
            if (sidebarContainer) {
              sidebarContainer.style.width = currentSidebarWidth + 'px';
            }
          }
          
          if (result.sidebarVisible) {
            isVisible = true;
            if (sidebarContainer) {
              sidebarContainer.style.display = 'block';
              adjustPageForSidebar(currentSidebarWidth);
            }
          }
        });
      }
    });
    observer.observe(document.documentElement, { childList: true });
  }
}

// Listen for messages from background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'toggleSidebar') {
    try {
      toggleSidebar();
      sendResponse({ success: true, visible: isVisible });
    } catch (error) {
      console.error('Error toggling sidebar:', error);
      sendResponse({ success: false, error: error.message });
    }
  }
  return true; // Keep channel open for async response
});

// Initialize when script loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initSidebar);
} else {
  initSidebar();
}

// Handle page navigation (SPA)
let lastUrl = location.href;
new MutationObserver(() => {
  const url = location.href;
  if (url !== lastUrl) {
    lastUrl = url;
    // Re-initialize if needed
    if (!sidebarContainer) {
      initSidebar();
    }
  }
}).observe(document, { subtree: true, childList: true });
