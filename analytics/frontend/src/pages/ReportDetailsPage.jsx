import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Calendar, FileText, BarChart3, Table as TableIcon, Download, Share2, Trash2, RefreshCw, Filter, ChevronDown, ChevronUp, ArrowDownAZ, ArrowUpAZ, ArrowDown01, ArrowUp10, ArrowUpDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import InsightPanel from '../components/InsightPanel.jsx';
import { config } from '../config.js';
import { exportReportToPdf } from '../utils/exportPdf.js';

// Date formatting helpers
const parseDate = (dateStr, format) => {
    if (!dateStr) return null;
    try {
        // Handle common formats
        const parts = dateStr.split(/[\/\-\.]/);
        if (format.includes('dd/MM/yy') || format.includes('dd/MM/yyyy')) {
            // DD/MM/YY or DD/MM/YYYY
            const day = parseInt(parts[0], 10);
            const month = parseInt(parts[1], 10) - 1;
            const year = parts[2].length === 2 ? 2000 + parseInt(parts[2], 10) : parseInt(parts[2], 10);
            return new Date(year, month, day);
        } else if (format.includes('MM/dd/yy') || format.includes('MM/dd/yyyy')) {
            // MM/DD/YY or MM/DD/YYYY
            const month = parseInt(parts[0], 10) - 1;
            const day = parseInt(parts[1], 10);
            const year = parts[2].length === 2 ? 2000 + parseInt(parts[2], 10) : parseInt(parts[2], 10);
            return new Date(year, month, day);
        } else if (format.includes('yyyy-MM-dd')) {
            // ISO format
            return new Date(dateStr);
        }
        return new Date(dateStr);
    } catch (e) {
        return null;
    }
};

const formatDate = (date, format) => {
    if (!date) return '';
    try {
        const d = new Date(date);
        const day = String(d.getDate()).padStart(2, '0');
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const year = d.getFullYear();
        const shortYear = String(year).slice(-2);

        if (format.includes('dd/MM/yy')) {
            return `${day}/${month}/${shortYear}`;
        } else if (format.includes('dd/MM/yyyy')) {
            return `${day}/${month}/${year}`;
        } else if (format.includes('MM/dd/yy')) {
            return `${month}/${day}/${shortYear}`;
        } else if (format.includes('MM/dd/yyyy')) {
            return `${month}/${day}/${year}`;
        } else if (format.includes('yyyy-MM-dd')) {
            return `${year}-${month}-${day}`;
        }
        return `${day}/${month}/${shortYear}`; // Default
    } catch (e) {
        return '';
    }
};

function ReportDetailsPage() {
    const { state } = useLocation();
    const navigate = useNavigate();
    const { id } = useParams();
    const [reportData, setReportData] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [viewMode, setViewMode] = useState('table');
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [report, setReport] = useState(null);
    const [filters, setFilters] = useState({});
    const [isRegenerating, setIsRegenerating] = useState(false);
    const [filtersChanged, setFiltersChanged] = useState(false);
    const [hasRegeneratedWithFilters, setHasRegeneratedWithFilters] = useState(false);
    const [showSaveVersionModal, setShowSaveVersionModal] = useState(false);
    const [saveVersionTitle, setSaveVersionTitle] = useState('');
    const [isSavingVersion, setIsSavingVersion] = useState(false);
    const [currentPage, setCurrentPage] = useState(1);
    const [isFilterExpanded, setIsFilterExpanded] = useState(true);
    const [isSummaryExpanded, setIsSummaryExpanded] = useState(false);
    const [showNoDataMessage, setShowNoDataMessage] = useState(false);
    const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
    const [toast, setToast] = useState(null);
    const rowsPerPage = 12;

    useEffect(() => {
        if (toast) {
            const timer = setTimeout(() => setToast(null), 3000);
            return () => clearTimeout(timer);
        }
    }, [toast]);

    const showToast = (message, type = 'success') => {
        setToast({ message, type });
    };

    // Load report (from state or fetch from API)
    useEffect(() => {
        if (state?.report) {
            handleReportLoad(state.report);
        } else {
            // Fetch from API
            fetchReport();
        }
    }, [id]);

    // Set default sort when data loads
    useEffect(() => {
        const columns = reportData?.columns || report?.columns;
        if (!sortConfig.key && columns && columns.length > 0) {
            // Default to 'id' if present, otherwise first column
            const defaultKey = columns.find(c => c.toLowerCase() === 'id') || columns[0];
            setSortConfig({ key: defaultKey, direction: 'asc' });
        }
    }, [reportData, report, sortConfig.key]);

    const handleReportLoad = (loadedReport) => {
        setReport(loadedReport);

        // Initialize filters
        if (loadedReport.filterSchema) {
            const initialFilters = {};
            Object.entries(loadedReport.filterSchema).forEach(([key, schema]) => {
                if (schema.default) {
                    initialFilters[key] = schema.default;
                }
            });
            setFilters(initialFilters);
        }

        // Logic to determine if we need to execute the report
        // If it's a legacy report with data, use it.
        // If it's a new report (no data, has base_sql), execute it.
        // If it has chart_config, always execute to regenerate charts with fresh data
        if (loadedReport.base_sql) {
            console.log("SQL report detected, triggering executeReport to get fresh data and regenerate charts");
            executeReport(loadedReport.id, loadedReport.default_params || {});
        } else if (loadedReport.data && loadedReport.data.length > 0) {
            console.log("Legacy report detected, using stored data");
            setReportData({
                data: loadedReport.data,
                columns: loadedReport.columns,
                charts: loadedReport.charts || [], // Legacy charts
                cached: false
            });
        } else {
            console.warn("Report has no data and no base_sql - cannot execute", loadedReport);
        }
    };

    const fetchReport = async () => {
        try {
            const res = await fetch(`${config.API.REPORTS_ENDPOINT}`);
            const data = await res.json();
            if (data.success) {
                const foundReport = data.reports.find(r => r.id === id);
                if (foundReport) {
                    handleReportLoad(foundReport);
                }
            }
        } catch (e) {
            console.error("Failed to fetch report", e);
        }
    };

    const executeReport = async (reportId, params, showToastOnSuccess = false) => {
        setIsLoading(true);
        try {
            const res = await fetch(`${config.API.REPORTS_ENDPOINT}/${reportId}/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ params: params || {} })
            });

            const data = await res.json();
            if (data.status === 'success') {
                setReportData({
                    data: data.data,
                    columns: data.columns,
                    charts: data.charts || [],
                    cachedAt: data.executed_at,
                    cached: data.cached || false
                });
                if (showToastOnSuccess) {
                    showToast('Report refreshed successfully!');
                }
            } else {
                showToast(`Failed to execute report: ${data.message}`, 'error');
            }
        } catch (e) {
            console.error("Failed to execute report", e);
            showToast("Failed to execute report", 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const handleFilterChange = (filterKey, value) => {
        setFilters(prev => ({ ...prev, [filterKey]: value }));
        setFiltersChanged(true);
    };

    const handleClearFilters = () => {
        if (report?.default_params) {
            setFilters(report.default_params);
            setFiltersChanged(true); // Allow regenerate to reset to defaults
        } else {
            setFilters({});
            setFiltersChanged(true);
        }
    };


    const handleRegenerate = async () => {
        setIsRegenerating(true);
        setShowNoDataMessage(false); // Clear any previous no-data message
        try {
            // For new reports, we might just want to re-execute with new params
            // But the current backend /regenerate endpoint does a full update of the definition too.
            // Let's stick to the current flow for now.
            const res = await fetch(`${config.API.REPORTS_ENDPOINT}/${id}/regenerate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filters, temporary: true })
            });

            const data = await res.json();
            if (data.status === 'success') {
                // Check if the result has no data
                if (!data.data || data.data.length === 0) {
                    // Show "No data found" message but keep old data
                    setShowNoDataMessage(true);
                    // Update summary to show the no-data message
                    setReport(prev => ({
                        ...prev,
                        detailed_summary: data.summary || 'No records matched the requested criteria. This may indicate no activity for the selected period or filters.',
                        lastRegeneratedAt: new Date().toISOString()
                    }));
                } else {
                    // Update report with new data
                    setReportData({
                        data: data.data,
                        columns: data.columns || report.columns,
                        charts: data.charts,
                        cachedAt: new Date().toISOString(),
                        cached: false
                    });

                    setReport(prev => ({
                        ...prev,
                        detailed_summary: data.summary,
                        lastRegeneratedAt: new Date().toISOString()
                    }));
                    setShowNoDataMessage(false);
                    setHasRegeneratedWithFilters(true);
                }
                setFiltersChanged(false);
            } else {
                alert(`Failed to regenerate: ${data.message}`);
            }
        } catch (e) {
            console.error("Regeneration failed", e);
            alert("Failed to regenerate report");
        } finally {
            setIsRegenerating(false);
        }
    };

    const handleSaveVersion = async () => {
        if (!saveVersionTitle.trim()) return;
        setIsSavingVersion(true);
        try {
            const res = await fetch(`${config.API.REPORTS_ENDPOINT}/${id}/save-version`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filters, title: saveVersionTitle.trim() })
            });
            const data = await res.json();
            if (data.status === 'success') {
                setShowSaveVersionModal(false);
                setSaveVersionTitle('');
                setHasRegeneratedWithFilters(false);
                showToast(`Saved as "${data.title}"`);
            } else {
                showToast(data.message || 'Failed to save', 'error');
            }
        } catch (e) {
            console.error('Save version failed', e);
            showToast('Failed to save filtered report', 'error');
        } finally {
            setIsSavingVersion(false);
        }
    };

    const handleDeleteClick = () => {
        setShowDeleteModal(true);
    };

    const handleDeleteConfirm = () => {
        navigate('/reports');
    };

    const handleDeleteCancel = () => {
        setShowDeleteModal(false);
    };

    // Sorting Logic
    const handleSort = (key) => {
        let direction = 'asc';
        if (sortConfig.key === key && sortConfig.direction === 'asc') {
            direction = 'desc';
        }
        setSortConfig({ key, direction });
    };

    // Pagination logic
    const tableData = reportData?.data || report?.data || report?.preview || [];

    // Apply sorting before pagination
    const sortedData = React.useMemo(() => {
        if (!sortConfig.key) return tableData;

        return [...tableData].sort((a, b) => {
            const aVal = a[sortConfig.key];
            const bVal = b[sortConfig.key];

            if (aVal === null || aVal === undefined) return 1;
            if (bVal === null || bVal === undefined) return -1;

            // Numeric sort
            if (typeof aVal === 'number' && typeof bVal === 'number') {
                return sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal;
            }

            // String sort (case insensitive)
            const aStr = String(aVal).toLowerCase();
            const bStr = String(bVal).toLowerCase();

            if (aStr < bStr) {
                return sortConfig.direction === 'asc' ? -1 : 1;
            }
            if (aStr > bStr) {
                return sortConfig.direction === 'asc' ? 1 : -1;
            }
            return 0;
        });
    }, [tableData, sortConfig]);

    if (!report) {
        return <div className="h-full flex items-center justify-center">Loading...</div>;
    }

    const filterSchema = report.filterSchema || {};

    const charts = reportData?.charts || report.charts || [];
    const totalPages = Math.ceil(sortedData.length / rowsPerPage);
    const startIndex = (currentPage - 1) * rowsPerPage;
    const endIndex = startIndex + rowsPerPage;
    const currentPageData = sortedData.slice(startIndex, endIndex);

    // Generate page numbers for pagination
    const getPageNumbers = () => {
        const pages = [];
        const maxVisible = 5;

        if (totalPages <= maxVisible + 2) {
            // Show all pages if total is small
            for (let i = 1; i <= totalPages; i++) {
                pages.push(i);
            }
        } else {
            // Always show first page
            pages.push(1);

            if (currentPage > 3) {
                pages.push('...');
            }

            // Show pages around current
            const start = Math.max(2, currentPage - 1);
            const end = Math.min(totalPages - 1, currentPage + 1);

            for (let i = start; i <= end; i++) {
                pages.push(i);
            }

            if (currentPage < totalPages - 2) {
                pages.push('...');
            }

            // Always show last page
            pages.push(totalPages);
        }

        return pages;
    };

    // Helper function to get date range display
    const getDateRangeDisplay = () => {
        // Priority 1: Check if there's a date filter in filterSchema
        const dateFilter = Object.entries(filterSchema).find(([key, schema]) => schema.type === 'date');

        if (dateFilter) {
            const [filterKey, filterDef] = dateFilter;

            // Check if we have base_params with date values
            if (report.base_params) {
                const startDate = report.base_params.start_date || report.base_params[`${filterKey}_start`];
                const endDate = report.base_params.end_date || report.base_params[`${filterKey}_end`];

                if (startDate && endDate) {
                    const start = new Date(startDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                    const end = new Date(endDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                    return `${start} - ${end}`;
                }
            }
        }

        // Priority 2: Check data for date columns
        if (tableData && tableData.length > 0) {
            const firstRow = tableData[0];
            const lastRow = tableData[tableData.length - 1];

            // Look for common date column names
            const dateColumns = report.columns?.filter(col =>
                col.toLowerCase().includes('date') ||
                col.toLowerCase().includes('_dt') ||
                col === 'first_usage_date' ||
                col === 'last_usage_date'
            ) || [];

            if (dateColumns.length >= 2) {
                // If we have first_usage_date and last_usage_date
                const firstDateCol = dateColumns.find(col => col.includes('first') || col.includes('min'));
                const lastDateCol = dateColumns.find(col => col.includes('last') || col.includes('max'));

                if (firstDateCol && lastDateCol) {
                    const minDate = tableData.reduce((min, row) => {
                        const date = new Date(row[firstDateCol]);
                        return date < min ? date : min;
                    }, new Date(firstRow[firstDateCol]));

                    const maxDate = tableData.reduce((max, row) => {
                        const date = new Date(row[lastDateCol]);
                        return date > max ? date : max;
                    }, new Date(lastRow[lastDateCol]));

                    const start = minDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                    const end = maxDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                    return `${start} - ${end}`;
                }
            }
        }

        // Fallback: Show "All Time" or creation date
        return 'All Time';
    };

    const summaryContent = report ? (report.detailed_summary || report.analysis || report.summary) : '';
    const shouldShowReadMore = summaryContent && (summaryContent.length > 300 || summaryContent.split('\n').length > 6);

    return (
        <div className="h-full bg-slate-50/50 flex flex-col relative overflow-hidden">
            {/* Toast Notification */}
            {toast && (
                <div className={`fixed top-4 left-1/2 transform -translate-x-1/2 z-50 px-4 py-2 rounded-lg shadow-lg text-sm font-medium transition-all duration-300 ${toast.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'
                    }`}>
                    {toast.message}
                </div>
            )}
            {/* Delete Confirmation Modal */}
            {showDeleteModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
                        <div className="flex items-start gap-4 mb-4">
                            <div className="flex-shrink-0 w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                                <Trash2 size={24} className="text-red-600" />
                            </div>
                            <div className="flex-1">
                                <h3 className="text-lg font-semibold text-slate-900 mb-1">Delete Report</h3>
                                <p className="text-sm text-slate-600">
                                    Are you sure you want to delete this report? This action cannot be undone.
                                </p>
                            </div>
                        </div>
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={handleDeleteCancel}
                                className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleDeleteConfirm}
                                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition"
                            >
                                Delete Report
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Save Filtered Version Modal */}
            {showSaveVersionModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
                        <h3 className="text-lg font-semibold text-slate-900 mb-1">Save as New Report</h3>
                        <p className="text-sm text-slate-500 mb-4">
                            The current filters will be baked into a new standalone report.
                        </p>
                        <input
                            type="text"
                            value={saveVersionTitle}
                            onChange={e => setSaveVersionTitle(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleSaveVersion()}
                            placeholder="Report name"
                            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-navy/30 mb-4"
                            autoFocus
                        />
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={() => { setShowSaveVersionModal(false); setSaveVersionTitle(''); }}
                                className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSaveVersion}
                                disabled={!saveVersionTitle.trim() || isSavingVersion}
                                className="px-4 py-2 text-sm font-medium text-white bg-brand-navy rounded-lg hover:bg-opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {isSavingVersion ? 'Saving...' : 'Save Report'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Header */}
            <div className="bg-white border-b border-slate-200 px-6 py-2 flex items-center justify-between shadow-sm">
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => navigate('/reports')}
                        className="flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-800 transition px-3 py-1.5 rounded-lg hover:bg-slate-100 border border-transparent hover:border-slate-200"
                    >
                        <ArrowLeft size={16} />
                        Back to Reports
                    </button>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => exportReportToPdf({ report, reportData, viewMode, setViewMode })}
                        className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition border border-slate-200"
                        title="Download PDF"
                    >
                        <Download size={18} />
                    </button>
                    <button className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition border border-slate-200">
                        <Share2 size={18} />
                    </button>
                    <button
                        onClick={handleDeleteClick}
                        className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition border border-slate-200"
                        title="Delete report"
                    >
                        <Trash2 size={18} />
                    </button>
                </div>
            </div>

            {/* Filter Panel (Top Bar) - Moved inside title section */}
            {/* Main Content */}
            <div className="flex-1 overflow-y-auto p-4 pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                <div className="max-w-6xl mx-auto">

                    {/* Title Section with Filters */}
                    <div className="mb-4 bg-white rounded-xl border border-slate-200 p-5">
                        <h1 className="text-xl font-bold text-slate-800 mb-2">{report.title}</h1>
                        <div className="flex items-center gap-4 text-xs text-slate-500 mb-4">
                            <span className="flex items-center gap-1.5">
                                <Calendar size={12} />
                                {getDateRangeDisplay()}
                            </span>
                            <span className="flex items-center gap-1.5">
                                <FileText size={12} />
                                Table
                            </span>
                            <span className="flex items-center gap-1.5">
                                <BarChart3 size={12} />
                                {report.rowCount} rows
                            </span>
                            {/* Refresh Button */}
                            <button
                                onClick={() => executeReport(id, filters, true)}
                                className="flex items-center gap-1.5 ml-2 text-brand-navy hover:text-brand-navy/80 font-medium transition-colors hover:bg-blue-50 px-2 py-0.5 rounded"
                                title="Refresh Data"
                            >
                                <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} />
                                Refresh
                            </button>
                        </div>

                        {/* Filter Controls - Collapsible */}
                        <div className="border-t border-slate-200 pt-4">
                            {Object.keys(filterSchema).length > 0 ? (
                                <div className="mb-6 bg-indigo-50/50 rounded-xl border border-indigo-100 overflow-hidden">
                                    {/* Filter Header - Always Visible */}
                                    <button
                                        onClick={() => setIsFilterExpanded(!isFilterExpanded)}
                                        className="w-full flex items-center justify-between p-4 bg-indigo-50/80 hover:bg-indigo-100/50 transition-colors"
                                    >
                                        <div className="flex items-center gap-2">
                                            <h3 className="text-xs font-bold text-indigo-900 uppercase tracking-wide flex items-center gap-2">
                                                <Filter size={14} />
                                                Filters
                                            </h3>
                                            {Object.keys(filters).length > 0 && (
                                                <span className="ml-2 px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-[10px] normal-case">
                                                    {Object.keys(filters).length} active
                                                </span>
                                            )}
                                        </div>
                                        {isFilterExpanded ? (
                                            <ChevronUp size={16} className="text-indigo-400" />
                                        ) : (
                                            <ChevronDown size={16} className="text-indigo-400" />
                                        )}
                                    </button>

                                    {/* Filter Controls - Expandable */}
                                    {isFilterExpanded && (
                                        <div className="p-5 pt-0 border-t border-indigo-100/50">
                                            <div className="mt-4 space-y-3">
                                                {/* Group filters by type */}
                                                {(() => {
                                                    const dateFilters = Object.entries(filterSchema).filter(([_, schema]) => schema.type === 'date');
                                                    const textFilters = Object.entries(filterSchema).filter(([_, schema]) => schema.type === 'text' || schema.type === 'enum');
                                                    const numericFilters = Object.entries(filterSchema).filter(([_, schema]) => schema.type === 'numeric');

                                                    return (
                                                        <>
                                                            {/* Date Range Section */}
                                                            {dateFilters.length > 0 && (
                                                                <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                                                                    <h4 className="text-xs font-semibold text-slate-700 mb-2">Date Range</h4>
                                                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                                                        {dateFilters.map(([key, schema]) => (
                                                                            <div key={key} className="space-y-1">
                                                                                <label className="block text-xs text-slate-600 font-medium">
                                                                                    {schema.column.replace(/_/g, ' ')}
                                                                                    {schema.mandatory && <span className="text-red-500 ml-1">*</span>}
                                                                                </label>
                                                                                <div className="flex items-center gap-1.5">
                                                                                    <DatePicker
                                                                                        selected={parseDate(filters[key]?.start, schema.display_format || 'dd/MM/yy')}
                                                                                        onChange={(date) => {
                                                                                            const formatted = formatDate(date, schema.display_format || 'dd/MM/yy');
                                                                                            handleFilterChange(key, { ...filters[key], start: formatted });
                                                                                        }}
                                                                                        dateFormat={schema.display_format || 'dd/MM/yy'}
                                                                                        placeholderText="Start Date"
                                                                                        className="text-xs border border-slate-300 rounded-md px-2 py-1.5 w-full focus:outline-none focus:ring-1 focus:ring-brand-navy/20 focus:border-brand-navy"
                                                                                        wrapperClassName="flex-1"
                                                                                    />
                                                                                    <span className="text-xs text-slate-400">to</span>
                                                                                    <DatePicker
                                                                                        selected={parseDate(filters[key]?.end, schema.display_format || 'dd/MM/yy')}
                                                                                        onChange={(date) => {
                                                                                            const formatted = formatDate(date, schema.display_format || 'dd/MM/yy');
                                                                                            handleFilterChange(key, { ...filters[key], end: formatted });
                                                                                        }}
                                                                                        dateFormat={schema.display_format || 'dd/MM/yy'}
                                                                                        placeholderText="End Date"
                                                                                        className="text-xs border border-slate-300 rounded-md px-2 py-1.5 w-full focus:outline-none focus:ring-1 focus:ring-brand-navy/20 focus:border-brand-navy"
                                                                                        wrapperClassName="flex-1"
                                                                                    />
                                                                                </div>
                                                                            </div>
                                                                        ))}
                                                                    </div>
                                                                </div>
                                                            )}

                                                            {/* Text/Enum Filters Section */}
                                                            {textFilters.length > 0 && (
                                                                <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                                                                    <h4 className="text-xs font-semibold text-slate-700 mb-2">Product Filters</h4>
                                                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                                                        {textFilters.map(([key, schema]) => (
                                                                            <div key={key} className="space-y-1">
                                                                                <label className="block text-xs text-slate-600 font-medium">
                                                                                    {schema.column.replace(/_/g, ' ')}
                                                                                    {schema.mandatory && <span className="text-red-500 ml-1">*</span>}
                                                                                </label>
                                                                                <input
                                                                                    type="text"
                                                                                    placeholder={`Enter ${schema.column.replace(/_/g, ' ').toLowerCase()}...`}
                                                                                    className="w-full text-xs border border-slate-300 rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-navy/20 focus:border-brand-navy"
                                                                                    value={filters[key] || ''}
                                                                                    onChange={(e) => handleFilterChange(key, e.target.value)}
                                                                                />
                                                                            </div>
                                                                        ))}
                                                                    </div>
                                                                </div>
                                                            )}

                                                            {/* Numeric Filters Section */}
                                                            {numericFilters.length > 0 && (
                                                                <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                                                                    <h4 className="text-xs font-semibold text-slate-700 mb-2">Quantity</h4>
                                                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                                                        {numericFilters.map(([key, schema]) => (
                                                                            <div key={key} className="space-y-1">
                                                                                <label className="block text-xs text-slate-600 font-medium">
                                                                                    {schema.column.replace(/_/g, ' ')}
                                                                                    {schema.mandatory && <span className="text-red-500 ml-1">*</span>}
                                                                                </label>
                                                                                <div className="grid grid-cols-2 gap-1.5">
                                                                                    <input
                                                                                        type="number"
                                                                                        placeholder="Min"
                                                                                        className="text-xs border border-slate-300 rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-navy/20 focus:border-brand-navy"
                                                                                        value={filters[key]?.min || ''}
                                                                                        onChange={(e) => handleFilterChange(key, { ...filters[key], min: e.target.value })}
                                                                                    />
                                                                                    <input
                                                                                        type="number"
                                                                                        placeholder="Max"
                                                                                        className="text-xs border border-slate-300 rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-navy/20 focus:border-brand-navy"
                                                                                        value={filters[key]?.max || ''}
                                                                                        onChange={(e) => handleFilterChange(key, { ...filters[key], max: e.target.value })}
                                                                                    />
                                                                                </div>
                                                                            </div>
                                                                        ))}
                                                                    </div>
                                                                </div>
                                                            )}

                                                            {/* Action Buttons */}
                                                            <div className="flex items-center justify-end gap-2 pt-1">
                                                                <button
                                                                    onClick={handleClearFilters}
                                                                    disabled={!filtersChanged}
                                                                    className={`px-3 py-1.5 text-xs font-medium rounded-md transition ${filtersChanged
                                                                        ? 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50'
                                                                        : 'bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200'
                                                                        }`}
                                                                >
                                                                    Clear Filters
                                                                </button>
                                                                <button
                                                                    onClick={handleRegenerate}
                                                                    disabled={!filtersChanged || isRegenerating}
                                                                    className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold rounded-md transition ${filtersChanged && !isRegenerating
                                                                        ? 'bg-brand-navy text-white hover:bg-opacity-90 shadow-sm'
                                                                        : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                                                                        }`}
                                                                >
                                                                    <RefreshCw size={12} className={isRegenerating ? 'animate-spin' : ''} />
                                                                    {isRegenerating ? 'Applying...' : 'Apply Filters'}
                                                                </button>
                                                                {hasRegeneratedWithFilters && (
                                                                    <button
                                                                        onClick={() => {
                                                                            setSaveVersionTitle(`${report.title}  Filtered`);
                                                                            setShowSaveVersionModal(true);
                                                                        }}
                                                                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md border border-brand-navy text-brand-navy hover:bg-brand-navy hover:text-white transition"
                                                                        title="Save this filtered view as a new report"
                                                                    >
                                                                        Save as New Report
                                                                    </button>
                                                                )}
                                                            </div>
                                                        </>
                                                    );
                                                })()}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="text-xs text-slate-400 italic">
                                    No filters available for this report
                                </div>
                            )}
                        </div>
                    </div>



                    {/* Analysis/Summary Section */}
                    {(report.detailed_summary || report.analysis || report.summary) && (
                        <div className="mb-6 bg-indigo-50/50 rounded-xl border border-indigo-100 overflow-hidden">
                            <button
                                onClick={() => setIsSummaryExpanded(!isSummaryExpanded)}
                                className="w-full flex items-center justify-between p-4 bg-indigo-50/80 hover:bg-indigo-100/50 transition-colors"
                            >
                                <h3 className="text-xs font-bold text-indigo-900 uppercase tracking-wide flex items-center gap-2">
                                    <FileText size={14} />
                                    Summary
                                </h3>
                                {isSummaryExpanded ? (
                                    <ChevronUp size={16} className="text-indigo-400" />
                                ) : (
                                    <ChevronDown size={16} className="text-indigo-400" />
                                )}
                            </button>

                            {isSummaryExpanded && (
                                <div className="p-5 pt-0 border-t border-indigo-100/50">
                                    <div className="prose prose-sm max-w-none text-slate-700 leading-relaxed text-xs mt-4">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                            {summaryContent}
                                        </ReactMarkdown>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Toggle Switch */}
                    <div className="mb-6 flex gap-2">
                        <button
                            onClick={() => setViewMode('table')}
                            className={`inline-flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-md transition ${viewMode === 'table'
                                ? 'bg-brand-navy text-white shadow-sm'
                                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                                }`}
                        >
                            <TableIcon size={14} />
                            Table
                        </button>
                        <button
                            onClick={() => setViewMode('chart')}
                            className={`inline-flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-md transition ${viewMode === 'chart'
                                ? 'bg-brand-navy text-white shadow-sm'
                                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                                }`}
                        >
                            <BarChart3 size={14} />
                            Chart
                        </button>
                    </div>

                    {/* Viewport */}
                    {!isLoading && charts && charts.length > 0 && (
                        <div id="pdf-chart-container" style={viewMode !== 'chart' ? { position: 'absolute', left: '-9999px', opacity: 0, pointerEvents: 'none' } : {}}>
                            <InsightPanel
                                config={{ charts: charts }}
                                data={tableData}
                            />
                        </div>
                    )}
                    {/* Chart view: no charts placeholder */}
                    {viewMode === 'chart' && !isLoading && !(charts && charts.length > 0) && (
                        <div className="bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col">
                            <div className="flex-1 flex flex-col items-center justify-center p-6">
                                <div className="w-full h-64 bg-slate-50 rounded-lg border border-dashed border-slate-200 flex flex-col items-center justify-center text-slate-400 gap-3">
                                    <BarChart3 size={48} strokeWidth={1} />
                                    <span className="text-sm">No charts available for this report</span>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Loading state */}
                    {isLoading && (
                        <div className="bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col">
                            <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
                                <RefreshCw size={32} className="animate-spin mb-3 text-brand-navy" />
                                <span className="font-medium">Executing report...</span>
                                <span className="text-xs mt-1">Fetching fresh data and generating charts</span>
                            </div>
                        </div>
                    )}

                    {/* Table view */}
                    {viewMode === 'table' && !isLoading && (
                        <div className="bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col">
                            <div className="flex-1 flex flex-col relative">
                                {/* No Data Overlay Message */}
                                {showNoDataMessage && (
                                    <div className="absolute inset-0 bg-white/95 backdrop-blur-sm z-10 flex items-center justify-center">
                                        <div className="text-center p-8">
                                            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-slate-100 flex items-center justify-center">
                                                <FileText size={32} className="text-slate-400" />
                                            </div>
                                            <h3 className="text-lg font-semibold text-slate-800 mb-2">No Data Found</h3>
                                            <p className="text-sm text-slate-600 max-w-md">
                                                No records matched the selected filters. Try adjusting your filter criteria or clearing filters to see all data.
                                            </p>
                                            <button
                                                onClick={() => setShowNoDataMessage(false)}
                                                className="mt-4 px-4 py-2 text-xs font-medium text-brand-navy hover:text-brand-navy/80 hover:bg-blue-50 rounded-lg transition"
                                            >
                                                Dismiss
                                            </button>
                                        </div>
                                    </div>
                                )}

                                <div className="overflow-x-auto scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                                    <table className="min-w-full text-xs text-left">
                                        <thead className="bg-slate-50 text-slate-600 font-medium border-b border-slate-200">
                                            <tr>
                                                {(report.columns || report.fullHeaders || report.headers || []).map((h, i) => {
                                                    const isNumeric = (() => {
                                                        try {
                                                            if (report.filterSchema && report.filterSchema[h]) {
                                                                return report.filterSchema[h].type === 'numeric';
                                                            }
                                                            if (tableData.length > 0) {
                                                                const val = tableData[0][h];
                                                                return typeof val === 'number' || (!isNaN(parseFloat(val)) && isFinite(val));
                                                            }
                                                        } catch (e) {
                                                            return false;
                                                        }
                                                        return false;
                                                    })();

                                                    return (
                                                        <th
                                                            key={i}
                                                            className="px-4 py-2 whitespace-nowrap cursor-pointer hover:bg-slate-100 transition-colors select-none group"
                                                            onClick={() => handleSort(h)}
                                                        >
                                                            <div className="flex items-center gap-1.5">
                                                                {h}
                                                                {sortConfig.key === h ? (
                                                                    isNumeric ? (
                                                                        sortConfig.direction === 'asc' ?
                                                                            <ArrowDown01 size={14} className="text-brand-navy" /> :
                                                                            <ArrowUp10 size={14} className="text-brand-navy" />
                                                                    ) : (
                                                                        sortConfig.direction === 'asc' ?
                                                                            <ArrowDownAZ size={14} className="text-brand-navy" /> :
                                                                            <ArrowUpAZ size={14} className="text-brand-navy" />
                                                                    )
                                                                ) : (
                                                                    <ArrowUpDown size={12} className="text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                                                                )}
                                                            </div>
                                                        </th>
                                                    );
                                                })}
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-100">
                                            {currentPageData.map((row, idx) => (
                                                <tr key={idx} className="hover:bg-slate-50/50">
                                                    {(report.columns || report.fullHeaders || report.headers || []).map((col, cIdx) => {
                                                        const val = row[col];
                                                        // Don't format IDs with commas
                                                        const isIdColumn = col.toLowerCase().includes('id') || col.toLowerCase().endsWith('_id');
                                                        return (
                                                            <td key={cIdx} className="px-4 py-2 text-slate-700 whitespace-nowrap">
                                                                {typeof val === 'number' && !isIdColumn ? val.toLocaleString() : (val ?? '')}
                                                            </td>
                                                        );
                                                    })}
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>

                                {/* Pagination Controls */}
                                {totalPages > 1 && (
                                    <div className="border-t border-slate-200 px-4 py-3 flex items-center justify-between bg-slate-50">
                                        <div className="text-xs text-slate-600">
                                            Showing {startIndex + 1} to {Math.min(endIndex, tableData.length)} of {tableData.length} rows
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <button
                                                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                                disabled={currentPage === 1}
                                                className="p-1 rounded hover:bg-slate-200 disabled:opacity-50 disabled:hover:bg-transparent"
                                            >
                                                <ChevronDown className="rotate-90" size={14} />
                                            </button>
                                            <div className="flex items-center gap-1">
                                                {getPageNumbers().map((page, idx) => (
                                                    <button
                                                        key={idx}
                                                        onClick={() => typeof page === 'number' && setCurrentPage(page)}
                                                        disabled={page === '...'}
                                                        className={`min-w-[24px] h-6 px-1 rounded text-xs font-medium transition-colors flex items-center justify-center ${page === currentPage
                                                            ? 'bg-brand-navy text-white'
                                                            : page === '...'
                                                                ? 'text-slate-400 cursor-default'
                                                                : 'text-slate-600 hover:bg-slate-100'
                                                            }`}
                                                    >
                                                        {page}
                                                    </button>
                                                ))}
                                            </div>
                                            <button
                                                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                                disabled={currentPage === totalPages}
                                                className="p-1 rounded hover:bg-slate-200 disabled:opacity-50 disabled:hover:bg-transparent"
                                            >
                                                <ChevronDown className="-rotate-90" size={14} />
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default ReportDetailsPage;
