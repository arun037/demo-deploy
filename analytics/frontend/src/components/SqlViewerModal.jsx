import React, { useState } from 'react';
import { X, Copy, Check, Terminal } from 'lucide-react';

import { format } from 'sql-formatter';

const SqlViewerModal = ({ isOpen, onClose, sql, title }) => {
    const [copied, setCopied] = useState(false);

    const formattedSql = React.useMemo(() => {
        if (!sql) return '';
        try {
            return format(sql, { language: 'mysql' });
        } catch (error) {
            console.warn('SQL formatting failed:', error);
            return sql;
        }
    }, [sql]);

    if (!isOpen) return null;

    const handleCopy = () => {
        navigator.clipboard.writeText(formattedSql);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col animate-in zoom-in-95 duration-200 m-4">
                {/* Header */}
                <div className="bg-slate-900 px-6 py-4 flex items-center justify-between border-b border-slate-700">
                    <div className="flex items-center gap-3">
                        <div className="bg-slate-800 p-2 rounded-lg">
                            <Terminal className="text-blue-400" size={20} />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-white">SQL Query</h2>
                            <p className="text-slate-400 text-xs truncate max-w-md">{title}</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-slate-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-white/10"
                    >
                        <X size={24} />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-auto bg-slate-950 p-0 relative group scrollbar-thin scrollbar-thumb-slate-600 scrollbar-track-slate-800">
                    <div className="absolute top-4 right-4 z-10">
                        <button
                            onClick={handleCopy}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${copied
                                ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                                : 'bg-white/10 text-slate-300 hover:bg-white/20 border border-white/10'
                                }`}
                        >
                            {copied ? <Check size={14} /> : <Copy size={14} />}
                            {copied ? 'Copied!' : 'Copy SQL'}
                        </button>
                    </div>

                    <pre className="p-6 text-sm font-mono leading-relaxed text-blue-100 overflow-x-auto scrollbar-thin scrollbar-thumb-slate-600 scrollbar-track-slate-800">
                        <code className="language-sql">{formattedSql || '-- No SQL available'}</code>
                    </pre>
                </div>

                {/* Footer */}
                <div className="bg-slate-900 px-6 py-4 border-t border-slate-800 flex justify-end">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg font-medium transition-colors text-sm"
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
};

export default SqlViewerModal;
