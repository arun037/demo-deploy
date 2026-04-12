import React, { useState, useEffect } from 'react';
import { X, Loader2 } from 'lucide-react';

function ReportNameModal({ isOpen, onClose, onSave, suggestedName, isLoading = false }) {
  const [reportName, setReportName] = useState('');

  useEffect(() => {
    if (isOpen) {
      setReportName(suggestedName || '');
    }
  }, [isOpen, suggestedName]);

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (reportName.trim()) {
      onSave(reportName.trim());
    }
  };

  const handleClose = () => {
    if (!isLoading) {
      setReportName('');
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-md w-full border border-slate-200">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-800">Save Report</h2>
          <button
            onClick={handleClose}
            disabled={isLoading}
            className="p-1 hover:bg-slate-100 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <X size={20} className="text-slate-500" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-4">
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Report Name
            </label>
            <input
              type="text"
              value={reportName}
              onChange={(e) => setReportName(e.target.value)}
              placeholder="Enter report name..."
              disabled={isLoading}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-navy/20 focus:border-brand-navy transition disabled:opacity-50 disabled:cursor-not-allowed"
              autoFocus
              maxLength={60}
            />
            <p className="mt-1 text-xs text-slate-500">
              {reportName.length}/60 characters
            </p>
          </div>

          {/* Suggested name hint */}
          {suggestedName && suggestedName !== reportName && (
            <div className="mb-4 p-2 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-xs text-slate-600 mb-1">
                <span className="font-medium">Suggested:</span> {suggestedName}
              </p>
              <button
                type="button"
                onClick={() => setReportName(suggestedName)}
                disabled={isLoading}
                className="text-xs text-brand-navy hover:text-blue-900 font-medium"
              >
                Use suggested name
              </button>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={handleClose}
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!reportName.trim() || isLoading}
              className="px-4 py-2 text-sm font-medium text-white bg-brand-navy hover:bg-opacity-90 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isLoading ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Report'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default ReportNameModal;
