
import React from 'react';
import { X, FileText } from 'lucide-react';
import InsightReport from './InsightReport';

const InsightReportModal = ({ isOpen, onClose, job }) => {
    if (!isOpen || !job) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200 p-4">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-5xl h-[90vh] flex flex-col animate-in zoom-in-95 duration-200">
                {/* Header */}
                <div className="bg-slate-900 px-6 py-4 flex items-center justify-between border-b border-slate-700 shrink-0">
                    <div className="flex items-center gap-3">
                        <div className="bg-indigo-600 p-2 rounded-lg">
                            <FileText className="text-white" size={20} />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-white">
                                {job.artifacts?.plan?.task_name || "Insight Report"}
                            </h2>
                            <p className="text-slate-400 text-xs">
                                Analysis Job ID: {job.id}
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-slate-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-white/10"
                    >
                        <X size={24} />
                    </button>
                </div>

                {/* Content - Scrollable */}
                <div className="flex-1 overflow-y-auto bg-slate-50 p-6 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                    <InsightReport job={job} />
                </div>

                {/* Footer */}
                <div className="bg-white px-6 py-4 border-t border-slate-200 flex justify-end shrink-0">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-medium transition-colors text-sm"
                    >
                        Close Report
                    </button>
                </div>
            </div>
        </div>
    );
};

export default InsightReportModal;
