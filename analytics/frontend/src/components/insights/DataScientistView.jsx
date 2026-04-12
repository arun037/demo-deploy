import React, { useEffect, useRef } from 'react';
import { Terminal, Cpu, Database, Activity, CheckCircle, XCircle } from 'lucide-react';

const PIPELINE_STEPS = [
    { key: 'loading_data', label: 'Connecting to database & loading data...', icon: Database },
    { key: 'profiling', label: 'Profiling data quality & statistics...', icon: Activity },
    { key: 'planning', label: 'AI reasoning about prediction targets...', icon: Cpu },
    { key: 'engineering', label: 'Engineering features adaptively...', icon: Activity },
    { key: 'training', label: 'Training & evaluating model candidates...', icon: Cpu },
    { key: 'explaining', label: 'Generating business insights & charts...', icon: Activity },
    { key: 'completed', label: 'Analysis complete  model optimized.', icon: CheckCircle },
];

const DataScientistView = ({ job }) => {
    const scrollRef = useRef(null);

    useEffect(() => {
        if (scrollRef.current) {
            const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
            const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
            if (isNearBottom || job.status === 'queued') {
                scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
            }
        }
    }, [job]);

    if (!job) return null;

    const stepKeys = PIPELINE_STEPS.map(s => s.key);
    const currentIdx = stepKeys.indexOf(job.status);

    const getStepColor = (stepKey) => {
        const stepIdx = stepKeys.indexOf(stepKey);
        if (currentIdx > stepIdx) return 'text-green-400';
        if (currentIdx === stepIdx) return 'text-blue-400 animate-pulse';
        return 'text-slate-600';
    };

    // Progress percentage
    const progress = job.progress || (currentIdx >= 0 ? Math.round((currentIdx / (stepKeys.length - 1)) * 100) : 0);

    return (
        <div className="bg-slate-900 rounded-lg p-4 font-mono text-sm shadow-xl border border-slate-700 h-96 flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-700 pb-2 mb-2">
                <div className="flex items-center gap-2 text-green-400">
                    <Terminal size={16} />
                    <span className="font-bold">AI_ARCHITECT_v3.0</span>
                </div>
                <div className="text-xs text-slate-500">{job.id?.slice(0, 12)}...</div>
            </div>

            {/* Progress Bar */}
            <div className="mb-3">
                <div className="flex justify-between text-xs text-slate-500 mb-1">
                    <span>{job.message || job.status}</span>
                    <span>{progress}%</span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-1.5">
                    <div
                        className="h-1.5 rounded-full transition-all duration-500 ease-out"
                        style={{
                            width: `${progress}%`,
                            background: job.status === 'failed'
                                ? '#ef4444'
                                : job.status === 'completed'
                                    ? '#22c55e'
                                    : 'linear-gradient(90deg, #6366f1, #a855f7)'
                        }}
                    />
                </div>
            </div>

            {/* Pipeline Steps */}
            <div className="flex-1 overflow-y-auto space-y-1.5 p-1 pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100" ref={scrollRef}>
                <div className="text-slate-500 text-xs">Initializing intelligent pipeline...</div>

                {PIPELINE_STEPS.map(step => {
                    if (currentIdx < stepKeys.indexOf(step.key) && job.status !== 'failed') return null;
                    const Icon = step.icon;
                    return (
                        <div key={step.key} className="flex items-center gap-2">
                            <Icon size={14} className={getStepColor(step.key)} />
                            <span className="text-slate-300 text-xs">{step.label}</span>
                        </div>
                    );
                })}

                {/* Plan artifact */}
                {job.artifacts?.plan && (
                    <div className="bg-slate-800 p-2 rounded border-l-2 border-purple-500 my-2">
                        <div className="text-purple-400 font-bold mb-1 text-xs">BRAIN: Analysis Plan</div>
                        <div className="text-xs text-slate-300 space-y-0.5">
                            <div>Type: <span className="text-white">{job.artifacts.plan.task_type}</span></div>
                            <div>Target: <span className="text-green-300">{job.artifacts.plan.target_column}</span></div>
                            <div className="text-slate-400 truncate">{job.artifacts.plan.reasoning}</div>
                        </div>
                    </div>
                )}

                {/* Feature metadata */}
                {job.artifacts?.feature_metadata && (
                    <div className="text-slate-500 text-xs flex items-center gap-2">
                        <Cpu size={12} className="text-cyan-400" />
                        Generated {job.artifacts.feature_metadata.final_feature_count} features
                        {job.artifacts.feature_metadata.encoding_strategy && (
                            <span className="text-slate-600">
                                ({job.artifacts.feature_metadata.high_cardinality_categoricals?.length > 0
                                    ? 'freq+onehot encoding'
                                    : 'onehot encoding'})
                            </span>
                        )}
                    </div>
                )}

                {/* Success result */}
                {job.result && (
                    <div className="mt-3 text-green-400 border border-green-800 bg-green-900/20 p-2 rounded text-xs">
                        <div className="font-bold mb-1">S Model trained successfully</div>
                        <div className="text-green-300">
                            Best: {job.result.metrics?.best_model_name || 'Unknown'}
                            {' - '}
                            {job.result.metrics?.test_metrics?.accuracy !== undefined
                                ? `Accuracy: ${(job.result.metrics.test_metrics.accuracy * 100).toFixed(1)}%`
                                : job.result.metrics?.test_metrics?.r2 !== undefined
                                    ? `R: ${(job.result.metrics.test_metrics.r2 * 100).toFixed(1)}%`
                                    : ''}
                            {' - '}
                            {job.result.metrics?.algorithms_tried || '?'} algorithms evaluated
                        </div>
                    </div>
                )}

                {/* Error */}
                {job.error && (
                    <div className="mt-3 text-red-400 border border-red-800 bg-red-900/20 p-2 rounded text-xs flex items-start gap-2">
                        <XCircle size={16} className="shrink-0 mt-0.5" />
                        <span>{job.error}</span>
                    </div>
                )}

                {/* Blinking cursor */}
                {!['completed', 'failed'].includes(job.status) && (
                    <div className="animate-pulse text-blue-400"></div>
                )}
            </div>
        </div>
    );
};

export default DataScientistView;
