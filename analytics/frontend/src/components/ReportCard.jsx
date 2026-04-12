import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Clock, Edit2, Trash2, FileText, XCircle } from 'lucide-react';

/**
 * ReportCard component - displays a single report in the reports grid
 */
function ReportCard({
    report,
    editingReportId,
    editReportName,
    onStartRename,
    onSaveRename,
    onCancelRename,
    onDeleteClick,
    onEditReportNameChange
}) {
    const navigate = useNavigate();

    const getTypeColor = (type) => {
        switch (type?.toLowerCase()) {
            case 'table': return 'bg-blue-100 text-brand-navy';
            case 'chart': return 'bg-purple-100 text-purple-700';
            case 'comprehensive': return 'bg-indigo-100 text-indigo-700';
            default: return 'bg-slate-100 text-slate-700';
        }
    };

    const getEntityColor = (entity) => {
        switch (entity?.toLowerCase()) {
            case 'vendor': return 'bg-orange-100 text-orange-700';
            case 'inventory': return 'bg-teal-100 text-teal-700';
            case 'purchase': return 'bg-cyan-100 text-cyan-700';
            case 'general': return 'bg-slate-100 text-slate-600';
            default: return 'bg-slate-100 text-slate-600';
        }
    };

    const isEditing = editingReportId === report.id;

    return (
        <div
            className="bg-slate-100 rounded-xl border-2 border-slate-300 shadow-md hover:shadow-lg hover:border-blue-300 transition-all cursor-pointer flex flex-col overflow-hidden group"
            onClick={() => navigate(`/reports/${report.id}`, { state: { report } })}
        >
            {/* Card Header */}
            <div className="p-2 sm:p-2.5 border-b-2 border-slate-200 bg-gradient-to-br from-slate-50 to-slate-100/50">
                <div className="flex justify-between items-start mb-1.5">
                    {isEditing ? (
                        <div className="flex-1 flex items-center gap-2">
                            <input
                                type="text"
                                value={editReportName}
                                onChange={(e) => onEditReportNameChange(e.target.value)}
                                onClick={(e) => e.stopPropagation()}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                        onSaveRename(report.id, e);
                                    } else if (e.key === 'Escape') {
                                        onCancelRename(e);
                                    }
                                }}
                                className="flex-1 px-2 py-1 text-sm font-semibold text-slate-800 border border-blue-300 rounded focus:outline-none focus:ring-2 focus:ring-brand-navy/20"
                                autoFocus
                                maxLength={60}
                            />
                            <button
                                onClick={(e) => onSaveRename(report.id, e)}
                                className="p-1 text-green-600 hover:bg-green-50 rounded transition"
                                title="Save"
                            >
                                <FileText size={14} />
                            </button>
                            <button
                                onClick={onCancelRename}
                                className="p-1 text-red-600 hover:bg-red-50 rounded transition"
                                title="Cancel"
                            >
                                <XCircle size={14} />
                            </button>
                        </div>
                    ) : (
                        <h3 className="font-semibold text-slate-800 text-sm sm:text-base line-clamp-1 flex-1" title={report.title}>
                            {report.title}
                        </h3>
                    )}
                </div>
                <div className="flex flex-wrap gap-1.5 sm:gap-2">
                    <span className={`px-1.5 sm:px-2 py-0.5 rounded-full text-[9px] sm:text-[10px] font-semibold uppercase tracking-wide ${getTypeColor(report.type)}`}>
                        {report.type}
                    </span>
                    <span className={`px-1.5 sm:px-2 py-0.5 rounded-full text-[9px] sm:text-[10px] font-semibold uppercase tracking-wide ${getEntityColor(report.entity)}`}>
                        {report.entity}
                    </span>
                    <span className="px-1.5 sm:px-2 py-0.5 rounded-full text-[9px] sm:text-[10px] font-semibold uppercase tracking-wide bg-slate-200 text-brand-navy">
                        {report.rowCount} rows
                    </span>
                </div>
            </div>

            {/* Preview Content */}
            <div className="p-2 sm:p-2.5 flex-1 bg-white">
                <div className="space-y-1.5">
                    <div className="flex items-start gap-2">
                        <div className="flex-1">
                            <p className="text-xs font-medium text-slate-600 mb-1">Summary:</p>
                            <p className="text-xs text-slate-500 line-clamp-3 leading-relaxed">
                                {report.summary ?
                                    report.summary.replace(/^#+\s*/gm, '').replace(/\*\*/g, '').replace(/__/, '')
                                    : 'No summary available'}
                            </p>
                        </div>
                    </div>

                    {/* Metadata */}
                    <div className="flex items-center justify-between text-[10px] text-slate-400 pt-2 border-t border-slate-100">
                        <div className="flex items-center gap-3">
                            <span className="flex items-center gap-1">
                                <span>{report.columns?.length || 0} columns</span>
                            </span>
                            <span className="flex items-center gap-1">
                                <span>{Object.keys(report.filterSchema || {}).length} filters</span>
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Footer */}
            <div className="px-2 sm:px-2.5 py-1.5 sm:py-2 border-t-2 border-slate-200 bg-slate-50/50 flex items-center justify-between text-[10px] sm:text-xs text-slate-400">
                <div className="flex items-center gap-1 sm:gap-1.5">
                    <Clock size={11} className="sm:w-[12px] sm:h-[12px]" />
                    <span>{report.date}</span>
                </div>
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                        onClick={(e) => onStartRename(report, e)}
                        className="p-1 sm:p-1.5 hover:bg-slate-100 rounded text-slate-500 hover:text-brand-navy transition"
                        title="Rename"
                    >
                        <Edit2 size={12} className="sm:w-[14px] sm:h-[14px]" />
                    </button>
                    <button
                        onClick={(e) => onDeleteClick(report, e)}
                        className="p-1 sm:p-1.5 hover:bg-slate-100 rounded text-slate-500 hover:text-red-600 transition"
                        title="Delete"
                    >
                        <Trash2 size={12} className="sm:w-[14px] sm:h-[14px]" />
                    </button>
                </div>
            </div>
        </div>
    );
}

export default ReportCard;
