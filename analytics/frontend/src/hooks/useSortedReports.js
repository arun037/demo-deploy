import { useMemo } from 'react';

/**
 * Custom hook for sorting reports
 * @param {Array} reports - Array of report objects
 * @param {string} sortBy - Sort option: 'newest', 'oldest', 'alpha'
 * @returns {Array} Sorted reports
 */
export const useSortedReports = (reports, sortBy) => {
    return useMemo(() => {
        const sorted = [...reports];

        switch (sortBy) {
            case 'newest':
                return sorted.sort((a, b) =>
                    new Date(b.createdAt || b.date) - new Date(a.createdAt || a.date)
                );

            case 'oldest':
                return sorted.sort((a, b) =>
                    new Date(a.createdAt || a.date) - new Date(b.createdAt || b.date)
                );

            case 'alpha':
                return sorted.sort((a, b) => a.title.localeCompare(b.title));

            default:
                return sorted;
        }
    }, [reports, sortBy]);
};
