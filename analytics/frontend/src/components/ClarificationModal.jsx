import React, { useState } from 'react';
import { X, HelpCircle, CheckCircle2, AlertCircle } from 'lucide-react';

function ClarificationModal({ isOpen, questions, onSubmit, onSkip }) {
    const [responses, setResponses] = useState({});

    if (!isOpen || !questions || questions.length === 0) return null;

    const handleOptionSelect = (questionId, category, value) => {
        setResponses(prev => ({
            ...prev,
            [category]: value
        }));
    };

    const handleTextInput = (questionId, category, value) => {
        setResponses(prev => ({
            ...prev,
            [category]: value
        }));
    };

    const handleSubmit = () => {
        onSubmit(responses);
        setResponses({});
    };

    const handleSkipClick = () => {
        setResponses({});
        onSkip();
    };

    const getImportanceBadge = (importance) => {
        const badges = {
            critical: { color: 'bg-red-100 text-red-700 border-red-300', icon: AlertCircle, label: 'Critical' },
            high: { color: 'bg-orange-100 text-orange-700 border-orange-300', icon: HelpCircle, label: 'High' },
            medium: { color: 'bg-blue-100 text-blue-700 border-blue-300', icon: HelpCircle, label: 'Medium' },
            low: { color: 'bg-gray-100 text-gray-600 border-gray-300', icon: HelpCircle, label: 'Low' }
        };
        const badge = badges[importance] || badges.medium;
        const Icon = badge.icon;

        return (
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${badge.color}`}>
                <Icon size={12} />
                {badge.label}
            </span>
        );
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col animate-in zoom-in-95 duration-200">
                {/* Header */}
                <div className="bg-gradient-to-r from-brand-navy to-[#2E5A8F] px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="bg-white/20 p-2 rounded-lg">
                            <HelpCircle className="text-white" size={24} />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-white">Quick Clarification</h2>
                            <p className="text-blue-100 text-sm">Help me understand your request better</p>
                        </div>
                    </div>
                    <button
                        onClick={handleSkipClick}
                        className="text-white/80 hover:text-white transition-colors p-1 rounded-lg hover:bg-white/10"
                    >
                        <X size={24} />
                    </button>
                </div>

                {/* Questions */}
                <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6 pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                    {questions.map((q, index) => (
                        <div key={q.id || index} className="bg-slate-50 rounded-xl p-5 border border-slate-200 hover:border-blue-300 transition-all">
                            {/* Question Header */}
                            <div className="flex items-start justify-between gap-3 mb-3">
                                <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-2">
                                        <span className="bg-brand-navy text-white text-sm font-bold px-2.5 py-0.5 rounded-full">
                                            Q{index + 1}
                                        </span>
                                        {getImportanceBadge(q.importance)}
                                        {q.category && (
                                            <span className="text-xs text-slate-500 bg-slate-200 px-2 py-0.5 rounded-full">
                                                {q.category.replace('_', ' ')}
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-slate-800 font-medium leading-relaxed">{q.question}</p>
                                    {q.reasoning && (
                                        <p className="text-xs text-slate-500 mt-2 italic"> {q.reasoning}</p>
                                    )}
                                </div>
                            </div>

                            {/* Answer Options */}
                            {q.question_type === 'multiple_choice' && q.options && q.options.length > 0 && (
                                <div className="space-y-2 mt-4">
                                    {q.options.map((option, optIndex) => (
                                        <button
                                            key={optIndex}
                                            onClick={() => handleOptionSelect(q.id, q.category, option)}
                                            className={`w-full text-left px-4 py-3 rounded-lg border-2 transition-all ${responses[q.category] === option
                                                ? 'border-brand-navy bg-blue-50 text-brand-navy font-medium'
                                                : 'border-slate-200 bg-white hover:border-blue-300 hover:bg-blue-50/50 text-slate-700'
                                                }`}
                                        >
                                            <div className="flex items-center gap-2">
                                                <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${responses[q.category] === option
                                                    ? 'border-brand-navy bg-brand-navy'
                                                    : 'border-slate-300'
                                                    }`}>
                                                    {responses[q.category] === option && (
                                                        <CheckCircle2 size={12} className="text-white" />
                                                    )}
                                                </div>
                                                <span className="flex-1">{option}</span>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            )}

                            {q.question_type === 'yes_no' && (
                                <div className="flex gap-3 mt-4">
                                    <button
                                        onClick={() => handleOptionSelect(q.id, q.category, true)}
                                        className={`flex-1 px-4 py-3 rounded-lg border-2 transition-all font-medium ${responses[q.category] === true
                                            ? 'border-green-500 bg-green-50 text-green-900'
                                            : 'border-slate-200 bg-white hover:border-green-300 text-slate-700'
                                            }`}
                                    >
                                        Yes
                                    </button>
                                    <button
                                        onClick={() => handleOptionSelect(q.id, q.category, false)}
                                        className={`flex-1 px-4 py-3 rounded-lg border-2 transition-all font-medium ${responses[q.category] === false
                                            ? 'border-red-500 bg-red-50 text-red-900'
                                            : 'border-slate-200 bg-white hover:border-red-300 text-slate-700'
                                            }`}
                                    >
                                        No
                                    </button>
                                </div>
                            )}

                            {q.question_type === 'text_input' && (
                                <div className="mt-4">
                                    <input
                                        type="text"
                                        value={responses[q.category] || ''}
                                        onChange={(e) => handleTextInput(q.id, q.category, e.target.value)}
                                        placeholder={q.default || 'Type your answer...'}
                                        className="w-full px-4 py-3 rounded-lg border-2 border-slate-200 focus:border-brand-navy focus:ring-2 focus:ring-brand-navy/20 outline-none transition-all"
                                    />
                                </div>
                            )}
                        </div>
                    ))}
                </div>

                {/* Footer */}
                <div className="bg-slate-50 px-6 py-4 border-t border-slate-200 flex items-center justify-between">
                    <button
                        onClick={handleSkipClick}
                        className="px-4 py-2 text-slate-600 hover:text-slate-800 font-medium transition-colors"
                    >
                        Skip & Use Original Query
                    </button>
                    <button
                        onClick={handleSubmit}
                        disabled={Object.keys(responses).length === 0}
                        className="px-6 py-2.5 bg-brand-navy text-white rounded-lg font-medium hover:bg-opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg flex items-center gap-2"
                    >
                        <CheckCircle2 size={18} />
                        Submit Answers ({Object.keys(responses).length})
                    </button>
                </div>
            </div>
        </div>
    );
}

export default ClarificationModal;
