import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { config } from '../config';
import ALL_QUESTIONS from '../data/questions.json';

function normalizeText(value = '') {
    return value
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function PopularPage() {
    const navigate = useNavigate();
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedCategory, setSelectedCategory] = useState('All');
    const [history, setHistory] = useState([]);

    // Fetch history
    React.useEffect(() => {
        const fetchHistory = async () => {
            try {
                const res = await fetch(config.API.HISTORY_ENDPOINT);
                if (res.ok) {
                    const data = await res.json();
                    if (data.success) {
                        setHistory(data.history);
                    }
                }
            } catch (e) {
                console.error("Failed to load history", e);
            }
        };
        fetchHistory();
    }, []);

    // Split into popular (pinned) and all questions from JSON
    const popularQuestions = ALL_QUESTIONS.filter(q => q.popular);
    const allQuestions = ALL_QUESTIONS;

    // Build category list dynamically from JSON
    const categories = ['All', 'History', ...new Set(allQuestions.map(q => q.category))];

    // Filter all questions by category + search
    const query = normalizeText(searchTerm);
    const queryTokens = query ? query.split(' ') : [];

    const filteredQuestions = allQuestions.filter(q => {
        const matchesCategory = selectedCategory === 'All' || q.category === selectedCategory;
        if (!matchesCategory) return false;

        if (!queryTokens.length) return true;

        const searchable = normalizeText(
            `${q.question} ${q.category} ${(q.tags || []).join(' ')}`
        );
        const matchesSearch = queryTokens.every(token => searchable.includes(token));

        return matchesCategory && matchesSearch;
    });

    const handleQuestionClick = (question) => {
        navigate('/chat', { state: { initialMessage: question } });
    };

    return (
        <div className="h-full bg-white flex flex-col">
            {/* Search Bar */}
            <div className="p-3 sm:p-4 border-b border-slate-200">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                    <input
                        type="text"
                        placeholder="Search queries..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-navy/20 focus:border-brand-navy transition"
                    />
                </div>
            </div>

            {/* Category Filter Buttons */}
            <div className="px-3 sm:px-4 py-3 border-b border-slate-200 overflow-x-auto scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                <div className="flex gap-2 min-w-max snap-x snap-mandatory">
                    {categories.map((category) => (
                        <button
                            key={category}
                            onClick={() => setSelectedCategory(category)}
                            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors whitespace-nowrap snap-start ${selectedCategory === category
                                ? 'bg-brand-navy text-white'
                                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                                }`}
                        >
                            {category}
                        </button>
                    ))}
                </div>
            </div>

            {/* Questions List */}
            <div className="flex-1 overflow-y-auto p-3 sm:p-4 pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">

                {/* History Section */}
                {selectedCategory === 'History' && history.length > 0 && (
                    <div className="space-y-6">
                        <div className="mb-6">
                            <h2 className="text-xs font-medium text-slate-500 mb-3 uppercase tracking-wide flex items-center gap-2">
                                <span>Query History</span>
                            </h2>
                            <div className="space-y-3">
                                {history.map((item, idx) => (
                                    <div
                                        key={`hist-${idx}`}
                                        onClick={() => handleQuestionClick(item.query)}
                                        className="bg-white border border-slate-200 rounded-lg p-3 sm:p-4 hover:border-brand-navy/30 hover:shadow-sm transition-all cursor-pointer group relative"
                                    >
                                        <div className="flex justify-between items-start">
                                            <p className="text-[13px] text-slate-700 mb-2.5 group-hover:text-brand-navy transition-colors leading-relaxed font-semibold pr-12">
                                                {item.query}
                                            </p>
                                            <span className="absolute top-3 right-3 px-2 py-0.5 bg-slate-100 text-slate-500 text-[10px] rounded-full font-medium">
                                                {item.count} runs
                                            </span>
                                        </div>
                                        <div className="flex flex-wrap gap-1.5">
                                            <span className="px-2.5 py-1 bg-slate-50 text-slate-500 text-[11px] rounded-md">
                                                Last: {new Date(item.last_run).toLocaleDateString()}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {selectedCategory === 'History' && history.length === 0 && (
                    <div className="text-center py-12">
                        <p className="text-slate-400 text-sm">No history found yet. Ask a question to get started!</p>
                    </div>
                )}

                {/* Popular Questions — only on All tab with no search */}
                {selectedCategory === 'All' && searchTerm === '' && (
                    <div className="mb-6">
                        <h2 className="text-xs font-medium text-slate-500 mb-3 uppercase tracking-wide">POPULAR QUESTIONS</h2>
                        <div className="space-y-2">
                            {popularQuestions.map((item) => (
                                <div
                                    key={`pop-${item.id}`}
                                    onClick={() => handleQuestionClick(item.question)}
                                    className="bg-white border border-slate-200 rounded-lg p-2.5 sm:p-3 hover:border-brand-navy/30 hover:shadow-sm transition-all cursor-pointer group"
                                >
                                    <p className="text-[13px] text-slate-700 mb-2 group-hover:text-brand-navy transition-colors leading-relaxed font-semibold">
                                        {item.question}
                                    </p>
                                    <div className="flex flex-wrap gap-1.5">
                                        {item.tags.map((tag, idx) => (
                                            <span key={idx} className="px-2.5 py-1 bg-blue-50 text-brand-navy text-[11px] rounded-md">
                                                {tag}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* All Questions */}
                {selectedCategory !== 'History' && (
                    <div>
                        {selectedCategory === 'All' && searchTerm === '' && (
                            <h2 className="text-xs font-medium text-slate-500 mb-3 uppercase tracking-wide">ALL QUESTIONS</h2>
                        )}
                        <div className="space-y-2">
                            {filteredQuestions.map((item) => (
                                <div
                                    key={`all-${item.id}`}
                                    onClick={() => handleQuestionClick(item.question)}
                                    className="bg-white border border-slate-200 rounded-lg p-2.5 sm:p-3 hover:border-brand-navy/30 hover:shadow-sm transition-all cursor-pointer group"
                                >
                                    <p className="text-[13px] text-slate-700 mb-2 group-hover:text-brand-navy transition-colors leading-relaxed font-semibold">
                                        {item.question}
                                    </p>
                                    <div className="flex flex-wrap gap-1.5">
                                        {item.tags.map((tag, idx) => (
                                            <span key={idx} className="px-2.5 py-1 bg-blue-50 text-brand-navy text-[11px] rounded-md">
                                                {tag}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {selectedCategory !== 'History' && filteredQuestions.length === 0 && (
                    <div className="text-center py-12">
                        <p className="text-slate-400 text-sm">No questions found matching your search.</p>
                    </div>
                )}
            </div>
        </div>
    );
}

export default PopularPage;
