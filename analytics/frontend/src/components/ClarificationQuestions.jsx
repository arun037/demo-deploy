import React from 'react';
import { CheckCircle2, HelpCircle, AlertCircle } from 'lucide-react';

function ClarificationQuestions({ questions, responses, onAnswer }) {
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
        <div className="space-y-4 mt-3">
            {questions.map((q, index) => {
                const isAnswered = responses && responses[q.category] !== undefined;
                const userAnswer = responses ? responses[q.category] : null;

                return (
                    <div
                        key={q.id || index}
                        className={`bg-gradient-to-r ${isAnswered ? 'from-green-50 to-blue-50' : 'from-slate-50 to-blue-50'} rounded-xl p-4 border ${isAnswered ? 'border-green-200' : 'border-slate-200'} transition-all`}
                    >
                        {/* Question Header */}
                        <div className="flex items-start gap-2 mb-3">
                            <span className="bg-brand-navy text-white text-xs font-bold px-2 py-1 rounded-full shrink-0">
                                Q{index + 1}
                            </span>
                            <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1 flex-wrap">
                                    {getImportanceBadge(q.importance)}
                                    {q.category && (
                                        <span className="text-xs text-slate-500 bg-white px-2 py-0.5 rounded-full border border-slate-200">
                                            {q.category.replace('_', ' ')}
                                        </span>
                                    )}
                                    {isAnswered && (
                                        <span className="text-xs text-green-700 bg-green-100 px-2 py-0.5 rounded-full border border-green-300 flex items-center gap-1">
                                            <CheckCircle2 size={12} />
                                            Answered
                                        </span>
                                    )}
                                </div>
                                <p className="text-slate-800 font-medium text-sm leading-relaxed">{q.question}</p>
                                {q.reasoning && !isAnswered && (
                                    <p className="text-xs text-slate-500 mt-1 italic">{q.reasoning}</p>
                                )}
                            </div>
                        </div>

                        {/* Answer Display or Options */}
                        {isAnswered ? (
                            <div className="ml-8 bg-white rounded-lg px-3 py-2 border border-green-200">
                                <p className="text-sm text-green-800 font-medium">
                                    S {typeof userAnswer === 'boolean' ? (userAnswer ? 'Yes' : 'No') : userAnswer}
                                </p>
                            </div>
                        ) : (
                            <div className="ml-8 space-y-2">
                                {/* Multiple Choice */}
                                {q.question_type === 'multiple_choice' && q.options && q.options.length > 0 && (
                                    <div className="space-y-2">
                                        {q.options.map((option, optIndex) => (
                                            <button
                                                key={optIndex}
                                                onClick={() => onAnswer(q.id, q.category, option)}
                                                className="w-full text-left px-3 py-2 rounded-lg border-2 border-slate-200 bg-white hover:border-blue-400 hover:bg-blue-50 text-slate-700 text-sm transition-all hover:shadow-sm"
                                            >
                                                {option}
                                            </button>
                                        ))}
                                    </div>
                                )}

                                {/* Yes/No */}
                                {q.question_type === 'yes_no' && (
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => onAnswer(q.id, q.category, true)}
                                            className="flex-1 px-3 py-2 rounded-lg border-2 border-slate-200 bg-white hover:border-green-400 hover:bg-green-50 text-slate-700 text-sm font-medium transition-all"
                                        >
                                            Yes
                                        </button>
                                        <button
                                            onClick={() => onAnswer(q.id, q.category, false)}
                                            className="flex-1 px-3 py-2 rounded-lg border-2 border-slate-200 bg-white hover:border-red-400 hover:bg-red-50 text-slate-700 text-sm font-medium transition-all"
                                        >
                                            No
                                        </button>
                                    </div>
                                )}

                                {/* Text Input */}
                                {q.question_type === 'text_input' && (
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            placeholder={q.default || 'Type your answer...'}
                                            onKeyPress={(e) => {
                                                if (e.key === 'Enter' && e.target.value.trim()) {
                                                    onAnswer(q.id, q.category, e.target.value.trim());
                                                    e.target.value = '';
                                                }
                                            }}
                                            className="flex-1 px-3 py-2 rounded-lg border-2 border-slate-200 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 outline-none text-sm"
                                        />
                                    </div>
                                )}

                                {q.default && (
                                    <p className="text-xs text-slate-500 mt-1">
                                        Default: <span className="font-medium">{q.default}</span>
                                    </p>
                                )}
                            </div>
                        )}
                    </div>
                );
            })}

            {/* Progress Indicator */}
            <div className="bg-blue-50 rounded-lg px-4 py-2 border border-blue-200">
                <p className="text-sm text-blue-800">
                    <span className="font-bold">{Object.keys(responses || {}).length}</span> of <span className="font-bold">{questions.length}</span> questions answered
                    {Object.keys(responses || {}).length === questions.length && (
                        <span className="ml-2 text-green-700">S Submitting...</span>
                    )}
                </p>
            </div>
        </div>
    );
}

export default ClarificationQuestions;
