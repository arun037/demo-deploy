import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ChevronDown } from 'lucide-react';
import { config } from '../config.js';
import { useSortedReports } from '../hooks/useSortedReports.js';
import ReportCard from '../components/ReportCard.jsx';

function ReportsPage() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('newest'); // 'newest', 'oldest', 'alpha'
  const [isSortOpen, setIsSortOpen] = useState(false);
  const sortRef = React.useRef(null);
  const [editingReportId, setEditingReportId] = useState(null);
  const [editReportName, setEditReportName] = useState('');

  // Close sort menu on outside click
  React.useEffect(() => {
    function handleClickOutside(event) {
      if (sortRef.current && !sortRef.current.contains(event.target)) {
        setIsSortOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const [reports, setReports] = useState([]);
  const [reportToDelete, setReportToDelete] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [notification, setNotification] = useState(null);

  useEffect(() => {
    const fetchReports = async () => {
      try {
        console.log('Fetching from:', config.API.REPORTS_ENDPOINT);
        const res = await fetch(`${config.API.REPORTS_ENDPOINT}`);
        console.log('Response status:', res.status);

        if (!res.ok) {
          console.error('API error:', res.statusText);
          return;
        }

        const data = await res.json();
        console.log('API response:', data);

        if (data.success && Array.isArray(data.reports)) {
          const saved = data.reports;

          // Adapt saved reports to UI structure
          const adaptedReports = saved.map(r => {
            // Get first 3 keys for headers if not explicit
            const keys = r.columns || (r.data && r.data.length > 0 ? Object.keys(r.data[0]) : []);
            const displayHeaders = keys.slice(0, 3).map(k => k.replace(/_/g, ' '));

            // Adapt rows for preview (limit to 3 rows, 3 cols)
            const previewData = (r.data || []).slice(0, 3).map(row => {
              const adaptedRow = {};
              keys.slice(0, 3).forEach((k, idx) => {
                adaptedRow[`col${idx + 1}`] = row[k];
              });
              return adaptedRow;
            });

            return {
              ...r, // Spread all original fields first (includes base_sql, detailed_summary, default_params, etc.)
              id: r.id,
              title: r.title || 'Untitled Report',
              type: r.type || 'table',
              entity: r.entity || 'report',
              rowCount: r.rowCount || (r.data ? r.data.length : 0),
              date: new Date(r.createdAt || r.created_at).toLocaleDateString(),
              summary: r.detailed_summary || r.summary || 'No summary available', // Prioritize detailed_summary
              analysis: r.detailed_summary || r.summary, // Use summary as analysis text
              preview: previewData,
              headers: displayHeaders,
              // Preserve full data for Details Page
              data: r.data || [],
              fullHeaders: keys.map(k => k.replace(/_/g, ' ')),
              classification: r.classification,
              // Preserve filter schema and params
              filterSchema: r.filterSchema || {},
              base_params: r.base_params || {},
              charts: r.charts || [],
              createdAt: r.createdAt,
              columns: r.columns
            };
          });

          setReports(adaptedReports);
        } else {
          console.warn('Unexpected response format:', data);
        }
      } catch (e) {
        console.error("Failed to load reports:", e);
      }
    };

    fetchReports();
  }, []);

  const getTypeColor = (type) => {
    switch (type) {
      case 'table': return 'bg-blue-100 text-blue-700';
      case 'chart': return 'bg-green-100 text-green-700';
      case 'summary': return 'bg-orange-100 text-orange-700';
      default: return 'bg-slate-100 text-slate-700';
    }
  };

  const getEntityColor = (entity) => {
    switch (entity) {
      case 'vendor': return 'bg-purple-100 text-purple-700';
      case 'department': return 'bg-pink-100 text-pink-700';
      case 'po': return 'bg-indigo-100 text-indigo-700';
      default: return 'bg-slate-100 text-slate-700';
    }
  };

  // Use custom hook for sorting
  const sortedReports = useSortedReports(reports, sortBy);

  // Filter after sorting
  const filteredReports = sortedReports.filter(r =>
    r.title.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleSortSelect = (option) => {
    setSortBy(option);
    setIsSortOpen(false);
  };

  const getSortLabel = () => {
    switch (sortBy) {
      case 'newest': return 'Newest First';
      case 'oldest': return 'Oldest First';
      case 'alpha': return 'Alphabetical';
      default: return 'Newest First';
    }
  };

  const handleStartRename = (report, e) => {
    e.stopPropagation(); // Prevent navigation
    setEditingReportId(report.id);
    setEditReportName(report.title);
  };

  const handleCancelRename = (e) => {
    e.stopPropagation();
    setEditingReportId(null);
    setEditReportName('');
  };

  const handleSaveRename = async (reportId, e) => {
    e.stopPropagation();
    if (!editReportName.trim()) {
      return;
    }

    try {
      const res = await fetch(`${config.API.REPORTS_ENDPOINT}/${reportId}/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_title: editReportName.trim() })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to rename report');
      }

      // Update local state
      setReports(prev => prev.map(r =>
        r.id === reportId ? { ...r, title: editReportName.trim() } : r
      ));
      setEditingReportId(null);
      setEditReportName('');
    } catch (error) {
      console.error('Rename failed', error);
      alert(`Failed to rename: ${error.message}`);
    }
  };

  const handleDeleteClick = (report, e) => {
    e.stopPropagation();
    setReportToDelete(report);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (!reportToDelete) return;

    setDeleting(true);
    try {
      const res = await fetch(`${config.API.REPORTS_ENDPOINT}/${reportToDelete.id}`, {
        method: 'DELETE'
      });

      if (res.ok) {
        setReports(reports.filter(r => r.id !== reportToDelete.id));
        setNotification({ type: 'success', message: 'Report deleted successfully' });
        setTimeout(() => setNotification(null), 3000);
      } else {
        throw new Error('Failed to delete report');
      }
    } catch (error) {
      console.error('Failed to delete report:', error);
      setNotification({ type: 'error', message: 'Failed to delete report' });
      setTimeout(() => setNotification(null), 3000);
    } finally {
      setDeleting(false);
      setShowDeleteConfirm(false);
      setReportToDelete(null);
    }
  };

  const cancelDelete = () => {
    setShowDeleteConfirm(false);
    setReportToDelete(null);
  };


  return (
    <div className="h-full bg-slate-50/50 p-2 sm:p-3 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
      {/* Notification Toast */}
      {notification && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg ${notification.type === 'success' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
          }`}>
          {notification.message}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md mx-4">
            <h3 className="text-lg font-semibold text-slate-800 mb-2">Delete Report?</h3>
            <p className="text-sm text-slate-600 mb-4">
              Are you sure you want to delete "{reportToDelete?.title}"? This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={cancelDelete}
                disabled={deleting}
                className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="px-4 py-2 text-sm font-medium text-white bg-red-500 rounded-lg hover:bg-red-600 transition-colors disabled:opacity-50"
              >
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="w-full">

        {/* Header */}
        <div className="mb-3 sm:mb-4">
          <h3 className="text-base sm:text-lg font-semibold text-slate-800">Saved Reports</h3>
          <p className="text-[11px] sm:text-xs text-slate-500">{reports.length} reports</p>
        </div>

        {/* Filters */}
        <div className="flex gap-3 mb-4 sm:mb-5">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              type="text"
              placeholder="Search reports..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-navy/20 focus:border-brand-navy transition"
            />
          </div>
          <div className="relative" ref={sortRef}>
            <button
              onClick={() => setIsSortOpen(!isSortOpen)}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition whitespace-nowrap"
            >
              {getSortLabel()}
              <ChevronDown size={14} className={`text-slate-400 transition-transform ${isSortOpen ? 'rotate-180' : ''}`} />
            </button>

            {isSortOpen && (
              <div className="absolute right-0 top-full mt-1 w-40 bg-white border border-slate-200 rounded-lg shadow-lg z-20 py-1">
                <button
                  onClick={() => handleSortSelect('newest')}
                  className={`w-full text-left px-4 py-2 text-xs sm:text-sm hover:bg-slate-50 ${sortBy === 'newest' ? 'text-brand-navy font-medium' : 'text-slate-700'}`}
                >
                  Newest First
                </button>
                <button
                  onClick={() => handleSortSelect('oldest')}
                  className={`w-full text-left px-4 py-2 text-xs sm:text-sm hover:bg-slate-50 ${sortBy === 'oldest' ? 'text-brand-navy font-medium' : 'text-slate-700'}`}
                >
                  Oldest First
                </button>
                <button
                  onClick={() => handleSortSelect('alpha')}
                  className={`w-full text-left px-4 py-2 text-xs sm:text-sm hover:bg-slate-50 ${sortBy === 'alpha' ? 'text-brand-navy font-medium' : 'text-slate-700'}`}
                >
                  Alphabetical
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          {filteredReports.map((report) => (
            <ReportCard
              key={report.id}
              report={report}
              editingReportId={editingReportId}
              editReportName={editReportName}
              onStartRename={handleStartRename}
              onSaveRename={handleSaveRename}
              onCancelRename={handleCancelRename}
              onDeleteClick={handleDeleteClick}
              onEditReportNameChange={setEditReportName}
            />
          ))}
        </div>

      </div>
    </div>
  );
}

export default ReportsPage;
