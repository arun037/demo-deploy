/**
 * Shared date formatting utilities
 */

/**
 * Format a date as "time ago" for recent dates, or actual date for older ones
 * @param {string} isoString - ISO date string
 * @returns {string} Formatted date string
 * 
 * Examples:
 * - "Just now" (< 1 min)
 * - "5 mins ago" (< 1 hour)
 * - "3 hrs ago" (< 24 hours)
 * - "Yesterday" (24-48 hours)
 * - "3 days ago" (2-6 days)
 * - "28 Jan 2026" (> 7 days)
 */
export const formatTimeAgo = (isoString) => {
    if (!isoString) return 'Unknown';

    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    // Less than 1 minute
    if (diffMins < 1) return 'Just now';

    // Less than 1 hour
    if (diffHours < 1) {
        return `${diffMins} ${diffMins === 1 ? 'min' : 'mins'} ago`;
    }

    // Less than 24 hours
    if (diffHours < 24) {
        return `${diffHours} ${diffHours === 1 ? 'hr' : 'hrs'} ago`;
    }

    // Yesterday
    if (diffDays === 1) {
        return 'Yesterday';
    }

    // 2-6 days ago
    if (diffDays < 7) {
        return `${diffDays} days ago`;
    }

    // Older than a week - show actual date
    return date.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    }); // e.g., "28 Jan 2026"
};

/**
 * Format a date as a full readable string
 * @param {string} isoString - ISO date string
 * @returns {string} Formatted date string (e.g., "January 28, 2026")
 */
export const formatFullDate = (isoString) => {
    if (!isoString) return 'Unknown';

    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
};

/**
 * Format a date as short date
 * @param {string} isoString - ISO date string
 * @returns {string} Formatted date string (e.g., "28/01/2026")
 */
export const formatShortDate = (isoString) => {
    if (!isoString) return 'Unknown';

    const date = new Date(isoString);
    return date.toLocaleDateString('en-GB');
};
