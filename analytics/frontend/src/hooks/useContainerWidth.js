import { useState, useEffect } from 'react';

/**
 * Hook to detect container width and provide responsive breakpoints
 * Useful for adapting UI when embedded in sidepanels or narrow containers
 */
export const useContainerWidth = () => {
  const [width, setWidth] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth;
    }
    return 1920; // Default to desktop
  });

  useEffect(() => {
    const handleResize = () => {
      setWidth(window.innerWidth);
    };

    window.addEventListener('resize', handleResize);
    handleResize(); // Initial call

    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return {
    width,
    isNarrow: width < 500,      // Sidepanel/narrow mode (< 500px)
    isMobile: width < 640,       // Mobile (< 640px)
    isTablet: width >= 640 && width < 1024,  // Tablet
    isDesktop: width >= 1024,    // Desktop
  };
};
