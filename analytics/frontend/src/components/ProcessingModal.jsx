import React, { useRef, useEffect, useState } from 'react';
import { X, CheckCircle2, Loader2, AlertCircle, Sparkles, Search, Brain, Code2, ShieldCheck, Wrench, PlayCircle, MessageSquare, BarChart3, GitBranch, Clock } from 'lucide-react';
import { useContainerWidth } from '../hooks/useContainerWidth.js';
import { config } from '../config.js';

// ─── Phase Config (clean demo labels) ────────────────────────────────────────
const PHASE_CONFIG = {
    ROUTER: {
        label: 'Understanding Request',
        sublabel: 'Classifying intent & query type',
        icon: Brain,
        color: 'text-violet-500',
        bg: 'bg-violet-50',
        border: 'border-violet-200',
        ring: 'ring-violet-400',
    },
    RETRIEVER: {
        label: 'Finding Relevant Data',
        sublabel: 'Scanning data sources',
        icon: Search,
        color: 'text-blue-500',
        bg: 'bg-blue-50',
        border: 'border-blue-200',
        ring: 'ring-blue-400',
    },
    CLARIFICATION: {
        label: 'Refining Understanding',
        sublabel: 'Resolving ambiguities',
        icon: GitBranch,
        color: 'text-amber-500',
        bg: 'bg-amber-50',
        border: 'border-amber-200',
        ring: 'ring-amber-400',
    },
    CLARIFIED: {
        label: 'Query Refined',
        sublabel: 'Incorporating your answers',
        icon: GitBranch,
        color: 'text-amber-500',
        bg: 'bg-amber-50',
        border: 'border-amber-200',
        ring: 'ring-amber-400',
    },
    CONTEXT: {
        label: 'Loading Context',
        sublabel: 'Preparing data context',
        icon: Search,
        color: 'text-sky-500',
        bg: 'bg-sky-50',
        border: 'border-sky-200',
        ring: 'ring-sky-400',
    },
    FOLLOWUP: {
        label: 'Refining Previous Query',
        sublabel: 'Applying your refinements',
        icon: GitBranch,
        color: 'text-indigo-500',
        bg: 'bg-indigo-50',
        border: 'border-indigo-200',
        ring: 'ring-indigo-400',
    },
    PLANNER: {
        label: 'Building Query Logic',
        sublabel: 'Structuring the analytical approach',
        icon: Brain,
        color: 'text-indigo-500',
        bg: 'bg-indigo-50',
        border: 'border-indigo-200',
        ring: 'ring-indigo-400',
    },
    SYNTHESIZER: {
        label: 'Generating Answer',
        sublabel: 'Constructing the analysis',
        icon: Code2,
        color: 'text-brand-navy',
        bg: 'bg-blue-50',
        border: 'border-blue-200',
        ring: 'ring-brand-navy',
    },
    SQL_GENERATION: {
        label: 'Generating Answer',
        sublabel: 'Constructing the analysis',
        icon: Code2,
        color: 'text-brand-navy',
        bg: 'bg-blue-50',
        border: 'border-blue-200',
        ring: 'ring-brand-navy',
    },
    VALIDATOR: {
        label: 'Verifying Accuracy',
        sublabel: 'Checking results for quality',
        icon: ShieldCheck,
        color: 'text-emerald-500',
        bg: 'bg-emerald-50',
        border: 'border-emerald-200',
        ring: 'ring-emerald-400',
    },
    FIXER: {
        label: 'Optimising',
        sublabel: 'Improving result quality',
        icon: Wrench,
        color: 'text-orange-500',
        bg: 'bg-orange-50',
        border: 'border-orange-200',
        ring: 'ring-orange-400',
    },
    EXECUTOR: {
        label: 'Fetching Results',
        sublabel: 'Running analysis on your data',
        icon: PlayCircle,
        color: 'text-[#2D7A8E]',
        bg: 'bg-teal-50',
        border: 'border-teal-200',
        ring: 'ring-[#2D7A8E]',
    },
    RESPONSE: {
        label: 'Preparing Response',
        sublabel: 'Composing your summary',
        icon: MessageSquare,
        color: 'text-[#4CAF50]',
        bg: 'bg-green-50',
        border: 'border-green-200',
        ring: 'ring-[#4CAF50]',
    },
    INSIGHTS: {
        label: 'Generating Insights',
        sublabel: 'Building charts & visualisations',
        icon: BarChart3,
        color: 'text-pink-500',
        bg: 'bg-pink-50',
        border: 'border-pink-200',
        ring: 'ring-pink-400',
    },
};

const FALLBACK_CONFIG = {
    label: 'Processing',
    sublabel: 'Working on your request',
    icon: Sparkles,
    color: 'text-slate-500',
    bg: 'bg-slate-50',
    border: 'border-slate-200',
    ring: 'ring-slate-400',
};

// ─── Admin phase labels (raw) ─────────────────────────────────────────────────
const ADMIN_PHASE_NAMES = {
    ROUTER: 'Intent Classification',
    RETRIEVER: 'Schema Retrieval',
    PLANNER: 'Query Planning',
    SYNTHESIZER: 'SQL Generation',
    SQL_GENERATION: 'SQL Generation',
    VALIDATOR: 'SQL Validation',
    FIXER: 'Error Correction',
    EXECUTOR: 'Query Execution',
    RESPONSE: 'Response Generation',
    INSIGHTS: 'Insight Analysis',
    CLARIFICATION: 'Clarification',
    CLARIFIED: 'Query Refined',
    CONTEXT: 'Context Loading',
    FOLLOWUP: 'Follow-up Rewrite',
};

// ─── Elapsed time hook ────────────────────────────────────────────────────────
function useElapsedTime(isRunning) {
    const [elapsed, setElapsed] = useState(0);
    const startRef = useRef(null);
    const finalRef = useRef(0);
    useEffect(() => {
        if (isRunning) {
            startRef.current = Date.now();
            const id = setInterval(() => {
                const val = ((Date.now() - startRef.current) / 1000).toFixed(1);
                finalRef.current = val;
                setElapsed(val);
            }, 100);
            return () => clearInterval(id);
        }
        // Don't reset — keep last value visible after completion
    }, [isRunning]);
    return elapsed;
}

// ═══════════════════════════════════════════════════════════════════════════════
// CLEAN DEMO VIEW (regular users)
// ═══════════════════════════════════════════════════════════════════════════════
const StepRow = ({ log, isActive, isDone, index }) => {
    const cfg = PHASE_CONFIG[log.phase] || FALLBACK_CONFIG;
    const Icon = cfg.icon;
    // Use frontend wall-clock duration (accurate); fall back to backend time_ms if not yet computed
    const timeS = log.durationS ?? (log.data?.time_ms > 0 ? (log.data.time_ms / 1000).toFixed(2) : null);

    return (
        <div className={`
            flex items-center gap-3 px-4 py-3 rounded-xl border transition-all duration-500
            ${isDone
                ? `${cfg.bg} ${cfg.border}`
                : isActive
                    ? `${cfg.bg} ${cfg.border} ring-1 ${cfg.ring} shadow-sm`
                    : 'bg-slate-50 border-slate-100 opacity-40'
            }
        `}>
            <div className={`
                flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center
                ${isDone ? cfg.bg : isActive ? 'bg-white' : 'bg-slate-100'}
                ${isActive ? `ring-1 ${cfg.ring}` : ''}
            `}>
                {isDone
                    ? <CheckCircle2 size={16} className={cfg.color} />
                    : isActive
                        ? <Loader2 size={16} className={`${cfg.color} animate-spin`} />
                        : <Icon size={16} className="text-slate-400" />
                }
            </div>
            <div className="flex-1 min-w-0">
                <p className={`text-sm font-semibold leading-tight ${isDone || isActive ? 'text-slate-800' : 'text-slate-400'}`}>
                    {cfg.label}
                </p>
                <p className={`text-xs leading-tight mt-0.5 ${isDone || isActive ? 'text-slate-500' : 'text-slate-300'}`}>
                    {cfg.sublabel}
                </p>
            </div>
            <div className="flex-shrink-0 flex items-center gap-2">
                {isDone && timeS && (
                    <span className="text-[10px] font-medium text-slate-400 tabular-nums">{timeS}s</span>
                )}
                {isDone && (
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${cfg.bg} ${cfg.color} border ${cfg.border}`}>
                        Done
                    </span>
                )}
                {isActive && (
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-white ${cfg.color} border ${cfg.border} animate-pulse`}>
                        Active
                    </span>
                )}
            </div>
        </div>
    );
};

const DemoModal = ({ logs, isComplete, error, onClose, elapsed }) => {
    const logsEndRef = useRef(null);
    const completionTimeRef = useRef(null);
    const { isNarrow } = useContainerWidth();
    
    useEffect(() => {
        if (logsEndRef.current) logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    // Capture wall-clock completion time once
    useEffect(() => {
        if ((isComplete || error) && !completionTimeRef.current) {
            completionTimeRef.current = Date.now();
        }
    }, [isComplete, error]);

    // Dedupe phases, keeping the FIRST receivedAt (when phase started)
    const deduped = logs.reduce((acc, log) => {
        const idx = acc.findIndex(l => l.phase === log.phase);
        if (idx >= 0) {
            acc[idx] = { ...log, firstSeenAt: acc[idx].firstSeenAt };
        } else {
            acc.push({ ...log, firstSeenAt: log.receivedAt || Date.now() });
        }
        return acc;
    }, []);

    // Compute wall-clock duration for each phase
    const dedupedWithDuration = deduped.map((log, i) => {
        const start = log.firstSeenAt;
        const end = i < deduped.length - 1
            ? deduped[i + 1].firstSeenAt
            : (completionTimeRef.current || (isComplete || error ? Date.now() : null));
        const durationS = start && end ? ((end - start) / 1000).toFixed(2) : null;
        return { ...log, durationS };
    });

    const activePhase = !isComplete && !error && logs.length > 0 ? logs[logs.length - 1].phase : null;
    // Total = elapsed prop (real wall clock, captured before it freezes)
    const totalS = elapsed;

    return (
        <div className="flex flex-col h-full">
            {/* Header - Fixed at top */}
            <div className="bg-[#182e58] px-4 sm:px-6 py-4 sm:py-5 flex-shrink-0">
                <div className="flex items-center justify-between w-full">
                    <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
                        <div className={`${isNarrow ? 'w-9 h-9' : 'w-11 h-11'} rounded-xl flex items-center justify-center flex-shrink-0 ${isComplete ? 'bg-[#4CAF50]/20' : error ? 'bg-red-400/20' : 'bg-white/15'}`}>
                            {isComplete ? <CheckCircle2 className="text-[#4CAF50]" size={isNarrow ? 20 : 24} />
                                : error ? <AlertCircle className="text-red-300" size={isNarrow ? 20 : 24} />
                                    : <Sparkles className="text-white animate-pulse" size={isNarrow ? 18 : 22} />}
                        </div>
                        <div className="min-w-0 flex-1">
                            <h2 className={`text-white font-bold ${isNarrow ? 'text-sm' : 'text-base'} tracking-tight leading-tight truncate`}>
                                {isComplete ? 'Analysis Complete' : error ? 'Analysis Failed' : 'Analysing Your Request'}
                            </h2>
                            <p className={`text-white/65 ${isNarrow ? 'text-[10px]' : 'text-xs'} mt-0.5 truncate`}>
                                {isComplete ? `Completed in ${elapsed}s`
                                    : error ? 'An error occurred during processing'
                                        : `AI agents working · ${elapsed}s elapsed`}
                            </p>
                        </div>
                    </div>
                    {(isComplete || error) && (
                        <button onClick={onClose} className="text-white/60 hover:text-white transition p-1.5 hover:bg-white/10 rounded-lg flex-shrink-0 ml-2">
                            <X size={isNarrow ? 16 : 18} />
                        </button>
                    )}
                </div>
                {/* Progress bar */}
                {!isComplete && !error && (
                    <div className="relative mt-4 h-1 bg-white/20 rounded-full overflow-hidden">
                        <div className="absolute left-0 top-0 h-full bg-white/70 rounded-full transition-all duration-700"
                            style={{ width: logs.length === 0 ? '5%' : `${Math.min(95, (deduped.length / 8) * 100)}%` }} />
                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-[shimmer_1.5s_infinite] -translate-x-full" />
                    </div>
                )}
                {isComplete && (
                    <div className="relative mt-4 h-1 bg-white/20 rounded-full overflow-hidden">
                        <div className="absolute left-0 top-0 h-full w-full bg-[#4CAF50]/80 rounded-full" />
                    </div>
                )}
            </div>

            {/* Body - Scrollable */}
            <div className={`${isNarrow ? 'px-3 py-3' : 'px-5 py-4'} overflow-y-auto flex-1 min-h-0 scrollbar-thin space-y-2`}>
                {error ? (
                    <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
                        <AlertCircle className="text-red-400 flex-shrink-0 mt-0.5" size={18} />
                        <div>
                            <p className="font-semibold text-red-800 text-sm mb-0.5">Something went wrong</p>
                            <p className="text-red-600 text-xs leading-relaxed">{error}</p>
                        </div>
                    </div>
                ) : logs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-10 gap-3">
                        <div className="relative">
                            <div className="w-12 h-12 rounded-full border-2 border-brand-navy/20 border-t-brand-navy animate-spin" />
                            <div className="absolute inset-0 flex items-center justify-center">
                                <Brain size={18} className="text-brand-navy" />
                            </div>
                        </div>
                        <p className="text-slate-500 text-sm font-medium">Initialising AI agents…</p>
                    </div>
                ) : (
                    <>
                        {dedupedWithDuration.map((log, i) => {
                            const isActive = log.phase === activePhase;
                            const isDone = isComplete || log.phase !== activePhase;
                            return <StepRow key={log.phase} log={log} index={i} isActive={isActive} isDone={isDone} />;
                        })}
                        {!isComplete && !error && (
                            <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-dashed border-slate-200 bg-slate-50/60">
                                <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center">
                                    <Loader2 size={15} className="text-brand-navy animate-spin" />
                                </div>
                                <p className="text-xs text-slate-400 font-medium">Next step incoming…</p>
                            </div>
                        )}
                        {isComplete && !error && (
                            <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-[#4CAF50]/30 bg-green-50 mt-1">
                                <div className="w-8 h-8 rounded-lg bg-[#4CAF50]/10 flex items-center justify-center">
                                    <CheckCircle2 size={16} className="text-[#4CAF50]" />
                                </div>
                                <div className="flex-1">
                                    <p className="text-sm font-semibold text-green-800">All steps completed</p>
                                    <p className="text-xs text-green-600">{dedupedWithDuration.length} agents ran successfully</p>
                                </div>
                                <span className="text-xs font-bold text-[#4CAF50] tabular-nums">{totalS}s</span>
                            </div>
                        )}
                    </>
                )}
                <div ref={logsEndRef} />
            </div>

            {/* Footer - Fixed at bottom */}
            {isComplete && !error && !config.APP.AUTO_CLOSE_PROCESSING_MODAL && (
                <div className={`${isNarrow ? 'px-3 py-3' : 'px-5 py-4'} border-t border-slate-100 bg-slate-50/70 flex-shrink-0`}>
                    <button onClick={onClose}
                        className={`w-full bg-gradient-to-r from-brand-navy to-brand-teal hover:opacity-90 text-white font-semibold ${isNarrow ? 'py-2 px-3 text-sm' : 'py-2.5 px-4'} rounded-xl transition-all shadow-md shadow-brand-navy/20 flex items-center justify-center gap-2`}>
                        <Sparkles size={isNarrow ? 14 : 15} /> View Results
                    </button>
                </div>
            )}
            {error && (
                <div className={`${isNarrow ? 'px-3 py-3' : 'px-5 py-4'} border-t border-slate-100 bg-slate-50/70 flex-shrink-0`}>
                    <button onClick={onClose}
                        className={`w-full bg-slate-800 hover:bg-slate-700 text-white font-semibold ${isNarrow ? 'py-2 px-3 text-sm' : 'py-2.5 px-4'} rounded-xl transition-all flex items-center justify-center gap-2`}>
                        <X size={isNarrow ? 14 : 15} /> Dismiss
                    </button>
                </div>
            )}
        </div>
    );
};

// ═══════════════════════════════════════════════════════════════════════════════
// ADMIN DEBUG VIEW (enhanced with visual states and better UI)
// ═══════════════════════════════════════════════════════════════════════════════
const AdminModal = ({ logs, isComplete, error, onClose }) => {
    const logsEndRef = useRef(null);
    const { isNarrow } = useContainerWidth();
    const elapsed = useElapsedTime(!isComplete && !error);
    
    useEffect(() => {
        if (logsEndRef.current) logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    // Determine active phase (last log if not complete)
    const activePhase = !isComplete && !error && logs.length > 0 ? logs[logs.length - 1].phase : null;
    
    // Dedupe phases to show unique steps
    const deduped = logs.reduce((acc, log) => {
        const idx = acc.findIndex(l => l.phase === log.phase);
        if (idx >= 0) {
            acc[idx] = { ...log, firstSeenAt: acc[idx].firstSeenAt };
        } else {
            acc.push({ ...log, firstSeenAt: log.receivedAt || Date.now() });
        }
        return acc;
    }, []);

    return (
        <div className="flex flex-col h-full min-h-0">
            {/* Header - Fixed at top */}
            <div className={`bg-[#182e58] ${isNarrow ? 'px-4 py-3' : 'px-6 py-4'} flex items-center justify-between flex-shrink-0 shadow-lg`}>
                <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
                    <div className={`bg-white/20 backdrop-blur-sm ${isNarrow ? 'p-1.5' : 'p-2'} rounded-lg flex-shrink-0 shadow-md`}>
                        {isComplete
                            ? <CheckCircle2 className="text-white" size={isNarrow ? 20 : 24} />
                            : error
                                ? <AlertCircle className="text-white" size={isNarrow ? 20 : 24} />
                                : <Loader2 className="text-white animate-spin" size={isNarrow ? 20 : 24} />}
                    </div>
                    <div className="min-w-0 flex-1">
                        <h2 className={`text-white font-semibold ${isNarrow ? 'text-sm' : 'text-lg'} truncate`}>
                            {isComplete ? 'Query Complete' : error ? 'Query Failed' : 'Processing Query'}
                        </h2>
                        <p className={`text-white/80 ${isNarrow ? 'text-[10px]' : 'text-sm'} truncate flex items-center gap-2`}>
                            {isComplete ? 'All agents completed successfully' : error ? 'An error occurred' : `SQL Swarm agents working · ${elapsed}s`}
                        </p>
                    </div>
                </div>
                {/* Admin badge */}
                <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                    <span className={`bg-amber-400/20 text-amber-200 ${isNarrow ? 'text-[9px] px-1.5 py-0.5' : 'text-[10px] px-2 py-0.5'} font-bold uppercase tracking-wider rounded-full border border-amber-400/30 shadow-sm`}>
                        Admin View
                    </span>
                    {(isComplete || error) && (
                        <button onClick={onClose} className="text-white/80 hover:text-white transition p-1.5 hover:bg-white/10 rounded-lg">
                            <X size={isNarrow ? 18 : 20} />
                        </button>
                    )}
                </div>
            </div>

            {/* Progress bar */}
            {!isComplete && !error && (
                <div className="relative h-1.5 bg-white/10 overflow-hidden flex-shrink-0">
                    <div className="absolute left-0 top-0 h-full bg-white/40 rounded-r-full transition-all duration-700"
                        style={{ width: logs.length === 0 ? '5%' : `${Math.min(95, (deduped.length / 10) * 100)}%` }} />
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-[shimmer_1.5s_infinite] -translate-x-full" />
                </div>
            )}
            {isComplete && (
                <div className="relative h-1.5 bg-white/10 overflow-hidden flex-shrink-0">
                    <div className="absolute left-0 top-0 h-full w-full bg-[#4CAF50]/80 rounded-r-full" />
                </div>
            )}

            {/* Logs - Scrollable */}
            <div className={`${isNarrow ? 'p-3' : 'p-5'} overflow-y-auto flex-1 min-h-0 bg-gradient-to-b from-slate-50 to-white pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100`}>
                {error ? (
                    <div className="bg-red-50 border-2 border-red-200 rounded-xl p-4 flex items-start gap-3 shadow-sm">
                        <AlertCircle className="text-red-500 flex-shrink-0 mt-0.5" size={20} />
                        <div>
                            <h3 className="font-semibold text-red-900 mb-1">Error</h3>
                            <p className="text-red-700 text-sm">{error}</p>
                        </div>
                    </div>
                ) : logs.length === 0 ? (
                    <div className="text-center py-12">
                        <div className="relative inline-block mb-4">
                            <div className="w-16 h-16 rounded-full border-4 border-brand-teal/20 border-t-brand-teal animate-spin" />
                            <div className="absolute inset-0 flex items-center justify-center">
                                <Brain size={20} className="text-brand-teal" />
                            </div>
                        </div>
                        <p className="text-brand-navy font-medium">Initializing agents...</p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {logs.map((log, index) => {
                            const cfg = PHASE_CONFIG[log.phase] || FALLBACK_CONFIG;
                            const Icon = cfg.icon;
                            const isActive = log.phase === activePhase;
                            const isDone = isComplete || (index < logs.length - 1);
                            const phaseName = ADMIN_PHASE_NAMES[log.phase] || log.phase;
                            
                            return (
                                <div key={index}
                                    className={`
                                        rounded-xl border-2 transition-all duration-500 shadow-sm
                                        ${isDone 
                                            ? `${cfg.bg} ${cfg.border} border-opacity-60` 
                                            : isActive
                                                ? `${cfg.bg} ${cfg.border} ring-2 ${cfg.ring} ring-opacity-50 shadow-md`
                                                : 'bg-slate-50 border-slate-200 opacity-60'
                                        }
                                        animate-in slide-in-from-left-2 fade-in
                                    `}
                                    style={{ animationDelay: `${index * 30}ms` }}>
                                    {/* Phase Header */}
                                    <div className={`${isNarrow ? 'p-3' : 'p-4'} border-b ${cfg.border} border-opacity-30`}>
                                        <div className="flex items-start gap-3">
                                            {/* Icon */}
                                            <div className={`
                                                flex-shrink-0 ${isNarrow ? 'w-10 h-10' : 'w-12 h-12'} rounded-xl flex items-center justify-center
                                                ${isDone ? cfg.bg : isActive ? 'bg-white shadow-md' : 'bg-slate-100'}
                                                ${isActive ? `ring-2 ${cfg.ring} ring-opacity-50` : ''}
                                                transition-all duration-300
                                            `}>
                                                {isDone
                                                    ? <CheckCircle2 size={isNarrow ? 18 : 20} className={cfg.color} />
                                                    : isActive
                                                        ? <Loader2 size={isNarrow ? 18 : 20} className={`${cfg.color} animate-spin`} />
                                                        : <Icon size={isNarrow ? 18 : 20} className="text-slate-400" />
                                                }
                                            </div>
                                            
                                            {/* Phase Info */}
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
                                                    <h3 className={`font-bold ${isNarrow ? 'text-sm' : 'text-base'} ${cfg.color}`}>
                                                        {phaseName}
                                                    </h3>
                                                    <div className="flex items-center gap-2">
                                                        {log.data?.time_ms && (
                                                            <span className={`text-xs ${cfg.color} flex items-center gap-1 font-medium bg-white/60 px-2 py-0.5 rounded-full`}>
                                                                <Clock size={11} />
                                                                {(log.data.time_ms / 1000).toFixed(2)}s
                                                            </span>
                                                        )}
                                                        {isDone && (
                                                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${cfg.bg} ${cfg.color} border ${cfg.border}`}>
                                                                ✓ Done
                                                            </span>
                                                        )}
                                                        {isActive && (
                                                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-white ${cfg.color} border ${cfg.border} animate-pulse`}>
                                                                ⟳ Active
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                                <p className={`text-sm ${isDone || isActive ? 'text-slate-700' : 'text-slate-500'} leading-relaxed`}>
                                                    {log.message}
                                                </p>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Phase Details */}
                                    {log.data && (
                                        <div className={`${isNarrow ? 'p-3' : 'p-4'} space-y-3 bg-white/50`}>
                                            {/* Schema/Data Info */}
                                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                                {log.data.request_type && (
                                                    <div className="bg-gradient-to-br from-blue-50 to-blue-100/50 rounded-lg p-2.5 border border-blue-200/50">
                                                        <span className="text-xs font-semibold text-blue-700 uppercase tracking-wide">Request Type</span>
                                                        <p className="text-sm text-blue-900 font-medium mt-1">{log.data.request_type}</p>
                                                    </div>
                                                )}
                                                {log.data.intent && (
                                                    <div className="bg-gradient-to-br from-purple-50 to-purple-100/50 rounded-lg p-2.5 border border-purple-200/50">
                                                        <span className="text-xs font-semibold text-purple-700 uppercase tracking-wide">Intent</span>
                                                        <p className="text-sm text-purple-900 font-medium mt-1">{log.data.intent}</p>
                                                    </div>
                                                )}
                                                {log.data.tables && (
                                                    <div className="bg-gradient-to-br from-emerald-50 to-emerald-100/50 rounded-lg p-2.5 border border-emerald-200/50">
                                                        <span className="text-xs font-semibold text-emerald-700 uppercase tracking-wide">Tables</span>
                                                        <p className="text-sm text-emerald-900 font-medium mt-1">{log.data.tables.join(', ')}</p>
                                                    </div>
                                                )}
                                                {log.data.columns && log.data.columns.length > 0 && (
                                                    <div className="bg-gradient-to-br from-cyan-50 to-cyan-100/50 rounded-lg p-2.5 border border-cyan-200/50">
                                                        <span className="text-xs font-semibold text-cyan-700 uppercase tracking-wide">Columns</span>
                                                        <p className="text-sm text-cyan-900 font-medium mt-1">{log.data.columns.join(', ')}</p>
                                                    </div>
                                                )}
                                                {log.data.row_count !== undefined && (
                                                    <div className="bg-gradient-to-br from-teal-50 to-teal-100/50 rounded-lg p-2.5 border border-teal-200/50">
                                                        <span className="text-xs font-semibold text-teal-700 uppercase tracking-wide">Rows</span>
                                                        <p className="text-sm text-teal-900 font-medium mt-1">{log.data.row_count.toLocaleString()}</p>
                                                    </div>
                                                )}
                                                {log.data.status && (
                                                    <div className="bg-gradient-to-br from-indigo-50 to-indigo-100/50 rounded-lg p-2.5 border border-indigo-200/50">
                                                        <span className="text-xs font-semibold text-indigo-700 uppercase tracking-wide">Status</span>
                                                        <p className="text-sm text-indigo-900 font-medium mt-1">{log.data.status}</p>
                                                    </div>
                                                )}
                                            </div>

                                            {/* Plan */}
                                            {log.data.plan && (
                                                <div className="bg-gradient-to-br from-slate-50 to-slate-100/50 rounded-lg p-3 border border-slate-200/50">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <Brain size={14} className="text-slate-600" />
                                                        <span className="text-xs font-semibold text-slate-700 uppercase tracking-wide">Query Plan</span>
                                                    </div>
                                                    <pre className="text-xs text-slate-800 whitespace-pre-wrap font-mono bg-white/60 p-2 rounded border border-slate-200/50 max-h-40 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                                                        {log.data.plan.substring(0, 300)}{log.data.plan.length > 300 ? '...' : ''}
                                                    </pre>
                                                </div>
                                            )}

                                            {/* SQL */}
                                            {log.data.sql && (
                                                <div className="bg-gradient-to-br from-brand-navy to-slate-900 rounded-lg p-3 border-2 border-brand-teal/30 shadow-lg">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <Code2 size={14} className="text-brand-teal-light" />
                                                        <span className="text-xs font-semibold text-brand-teal-light uppercase tracking-wide">Generated SQL</span>
                                                    </div>
                                                    <pre className="text-xs text-green-300 whitespace-pre-wrap font-mono bg-black/30 p-3 rounded border border-green-500/20 max-h-60 overflow-y-auto scrollbar-thin scrollbar-thumb-green-500/30">
                                                        {log.data.sql}
                                                    </pre>
                                                </div>
                                            )}

                                            {/* Error */}
                                            {log.data.error && (
                                                <div className="bg-gradient-to-br from-red-50 to-red-100/50 rounded-lg p-3 border-2 border-red-300">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <AlertCircle size={14} className="text-red-600" />
                                                        <span className="text-xs font-semibold text-red-700 uppercase tracking-wide">Error</span>
                                                    </div>
                                                    <pre className="text-xs text-red-800 whitespace-pre-wrap font-mono bg-white/60 p-2 rounded border border-red-200">
                                                        {log.data.error}
                                                    </pre>
                                                </div>
                                            )}

                                            {/* Thinking Process */}
                                            {log.data.thinking && (
                                                <details className="bg-gradient-to-br from-amber-50 to-amber-100/50 rounded-lg p-3 border border-amber-200/50 cursor-pointer hover:border-amber-300 transition-colors">
                                                    <summary className="text-xs font-semibold text-amber-700 uppercase tracking-wide cursor-pointer list-none flex items-center gap-2">
                                                        <Brain size={14} />
                                                        <span>Thinking Process</span>
                                                    </summary>
                                                    <pre className="text-xs text-amber-900 mt-3 whitespace-pre-wrap font-mono bg-white/60 p-2 rounded border border-amber-200/50">
                                                        {log.data.thinking}
                                                    </pre>
                                                </details>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}

                        {!isComplete && !error && (
                            <div className="flex items-center justify-center py-4 bg-gradient-to-r from-brand-teal/10 to-brand-navy/10 rounded-xl border-2 border-dashed border-brand-teal/30">
                                <Loader2 className="animate-spin text-brand-teal mr-2" size={18} />
                                <span className="text-sm text-brand-navy font-medium">Processing next step...</span>
                            </div>
                        )}
                        
                        {isComplete && !error && (
                            <div className="flex items-center gap-3 px-4 py-4 rounded-xl border-2 border-green-300 bg-gradient-to-r from-green-50 to-emerald-50 shadow-sm">
                                <div className="w-10 h-10 rounded-xl bg-green-100 flex items-center justify-center flex-shrink-0">
                                    <CheckCircle2 size={20} className="text-green-600" />
                                </div>
                                <div className="flex-1">
                                    <p className="text-sm font-bold text-green-800">All Steps Completed</p>
                                    <p className="text-xs text-green-600 mt-0.5">{deduped.length} agents executed successfully</p>
                                </div>
                                <span className="text-sm font-bold text-green-700 tabular-nums bg-white/60 px-3 py-1 rounded-full">
                                    {elapsed}s
                                </span>
                            </div>
                        )}
                        <div ref={logsEndRef} />
                    </div>
                )}
            </div>

            {/* Footer - Fixed at bottom */}
            {isComplete && !error && !config.APP.AUTO_CLOSE_PROCESSING_MODAL && (
                <div className={`bg-gradient-to-r from-slate-50 to-slate-100 ${isNarrow ? 'px-4 py-3' : 'px-6 py-4'} border-t-2 border-brand-teal/20 flex-shrink-0 shadow-lg`}>
                    <button onClick={onClose}
                        className={`w-full bg-gradient-to-r from-brand-teal to-brand-navy hover:from-brand-teal/90 hover:to-brand-navy/90 text-white font-semibold ${isNarrow ? 'py-2.5 px-3 text-sm' : 'py-3 px-4'} rounded-xl transition-all shadow-md shadow-brand-navy/20 flex items-center justify-center gap-2`}>
                        <CheckCircle2 size={isNarrow ? 14 : 16} /> View Results
                    </button>
                </div>
            )}
            {error && (
                <div className={`bg-gradient-to-r from-slate-50 to-slate-100 ${isNarrow ? 'px-4 py-3' : 'px-6 py-4'} border-t-2 border-red-200 flex-shrink-0`}>
                    <button onClick={onClose}
                        className={`w-full bg-slate-800 hover:bg-slate-700 text-white font-semibold ${isNarrow ? 'py-2.5 px-3 text-sm' : 'py-3 px-4'} rounded-xl transition-all flex items-center justify-center gap-2`}>
                        <X size={isNarrow ? 14 : 16} /> Dismiss
                    </button>
                </div>
            )}
        </div>
    );
};

// ═══════════════════════════════════════════════════════════════════════════════
// ROOT EXPORT — routes to admin or demo view based on isAdmin prop
// ═══════════════════════════════════════════════════════════════════════════════
const ProcessingModal = ({ isOpen, onClose, logs, isComplete, error, isAdmin = false }) => {
    if (!isOpen) return null;

    const elapsed = useElapsedTime(!isComplete && !error);
    const { isNarrow, width } = useContainerWidth();

    // Responsive modal width: narrow containers get full width with padding
    const getModalMaxWidth = () => {
        if (isNarrow || width < 500) return 'max-w-[calc(100%-2rem)]';
        if (width < 640) return 'max-w-lg';
        if (isAdmin) return 'max-w-2xl';
        return 'max-w-lg';
    };

    // Calculate height based on container width to ensure header is always visible
    const getModalHeight = () => {
        if (isNarrow || width < 500) return 'h-[90vh]';
        return 'h-[80vh]';
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-2 sm:p-4">
            <div className={`bg-white rounded-2xl shadow-2xl w-full overflow-hidden animate-in fade-in zoom-in-95 duration-300 ${getModalMaxWidth()} ${getModalHeight()} flex flex-col`}>
                {isAdmin
                    ? <AdminModal logs={logs} isComplete={isComplete} error={error} onClose={onClose} />
                    : <DemoModal  logs={logs} isComplete={isComplete} error={error} onClose={onClose} elapsed={elapsed} />
                }
            </div>
        </div>
    );
};

export default ProcessingModal;
