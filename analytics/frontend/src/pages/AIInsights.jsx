import React, { useState, useEffect } from 'react';
import { Brain, Sparkles, Play, RefreshCw } from 'lucide-react';
import DataScientistView from '../components/insights/DataScientistView';
import ModelCard from '../components/insights/ModelCard';
import { config } from '../config';

const AIInsights = () => {
    const [activeJob, setActiveJob] = useState(null);
    const [jobHistory, setJobHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [polling, setPolling] = useState(false);

    useEffect(() => {
        fetchJobs();
    }, []);

    // Poll active jobs
    useEffect(() => {
        let interval;
        if (polling) {
            interval = setInterval(async () => {
                try {
                    const res = await fetch(`${config.API.BASE_URL}/api/insights/jobs`);
                    if (res.ok) {
                        const data = await res.json();
                        setJobHistory(data);

                        // Find any still-running job
                        const running = data.find(j => !['completed', 'failed'].includes(j.status));
                        if (running) {
                            setActiveJob(running);
                        } else {
                            setPolling(false);
                            // Show latest completed
                            const latest = data.find(j => j.status === 'completed');
                            if (latest) setActiveJob(latest);
                        }
                    }
                } catch (e) {
                    console.error("Polling failed", e);
                }
            }, 2000);
        }
        return () => clearInterval(interval);
    }, [polling]);

    const fetchJobs = async () => {
        try {
            const res = await fetch(`${config.API.BASE_URL}/api/insights/jobs`);
            if (res.ok) {
                const data = await res.json();
                setJobHistory(data);
                const running = data.find(j => !['completed', 'failed'].includes(j.status));
                if (running) {
                    setActiveJob(running);
                    setPolling(true);
                }
            }
        } catch (e) {
            console.error("Failed to fetch jobs");
        }
    };

    const handleGenerate = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${config.API.BASE_URL}/api/insights/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            if (res.ok) {
                const data = await res.json();
                setPolling(true);
                if (data.job_ids && data.job_ids.length > 0) {
                    setTimeout(fetchJobs, 1000);
                }
            }
        } catch (e) {
            alert("Failed to start analysis");
        } finally {
            setLoading(false);
        }
    };

    const completedJobs = jobHistory.filter(j => j.status === 'completed');

    return (
        <div className="p-6 max-w-7xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                        <Brain className="text-purple-600" />
                        AI Insights Engine
                    </h1>
                    <p className="text-slate-500 text-sm mt-1">
                        Intelligent pipeline: Data Analysis  Algorithm Selection  Model Training  Business Insights
                    </p>
                </div>
                <button
                    onClick={fetchJobs}
                    className="p-2 text-slate-400 hover:text-brand-navy transition"
                    title="Refresh Jobs"
                >
                    <RefreshCw size={20} />
                </button>
            </div>

            {/* Controls */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                <div className="flex flex-col md:flex-row gap-6 items-center justify-between">
                    <div>
                        <h3 className="font-semibold text-slate-800">Project-Wide Intelligent Discovery</h3>
                        <p className="text-slate-500 text-sm">
                            The AI analyzes your data, selects the best algorithms, and trains optimized models  all automatically.
                        </p>
                    </div>
                    <div className="flex items-center gap-4">
                        {polling && (
                            <div className="text-sm text-purple-600 animate-pulse font-medium">
                                AI is analyzing...
                            </div>
                        )}
                        <button
                            onClick={handleGenerate}
                            disabled={loading || polling}
                            className={`
                                flex items-center gap-2 px-6 py-3 rounded-lg font-bold text-white transition shadow-lg transform hover:scale-105
                                ${loading || polling ? 'bg-slate-400 cursor-not-allowed' : 'bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700'}
                            `}
                        >
                            {polling ? (
                                <>
                                    <RefreshCw className="animate-spin" size={20} />
                                    Analyzing...
                                </>
                            ) : (
                                <>
                                    <Sparkles size={20} />
                                    Analyze Project
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Left: Live Analysis */}
                <div className="space-y-4">
                    <h2 className="font-semibold text-slate-700 flex items-center gap-2">
                        <ActivityIcon /> Live Analysis
                    </h2>
                    {activeJob ? (
                        <DataScientistView job={activeJob} />
                    ) : (
                        <div className="h-96 bg-slate-100 rounded-lg border border-slate-200 flex flex-col items-center justify-center text-slate-400 gap-4">
                            <Brain size={48} className="opacity-20" />
                            <span>Click "Analyze Project" to start the AI pipeline.</span>
                        </div>
                    )}
                </div>

                {/* Right: Models */}
                <div className="space-y-4">
                    <h2 className="font-semibold text-slate-700 flex items-center gap-2">
                        <Play size={18} className="text-green-600" /> Trained Models
                    </h2>
                    <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                        {completedJobs.length === 0 && (
                            <div className="h-96 w-full rounded-xl border-dashed border-2 border-slate-200 flex items-center justify-center text-slate-400">
                                No trained models yet
                            </div>
                        )}
                        {completedJobs.map(job => (
                            <ModelCard key={job.id} job={job} />
                        ))}
                    </div>
                </div>
            </div>

            {/* Job History */}
            {jobHistory.length > 0 && (
                <div className="mt-8">
                    <h3 className="font-semibold text-slate-700 mb-4">Recent Jobs</h3>
                    <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                        <table className="min-w-full text-sm text-left">
                            <thead className="bg-slate-50 text-slate-600">
                                <tr>
                                    <th className="px-4 py-3">ID</th>
                                    <th className="px-4 py-3">Dataset</th>
                                    <th className="px-4 py-3">Type</th>
                                    <th className="px-4 py-3">Algorithm</th>
                                    <th className="px-4 py-3">Status</th>
                                    <th className="px-4 py-3">Created</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {jobHistory.map(job => (
                                    <tr key={job.id} className="hover:bg-slate-50 transition">
                                        <td className="px-4 py-3 font-mono text-xs text-slate-500">{job.id?.slice(0, 8)}...</td>
                                        <td className="px-4 py-3 font-medium">{job.artifacts?.table || 'Unknown'}</td>
                                        <td className="px-4 py-3">{job.artifacts?.plan?.task_type || '-'}</td>
                                        <td className="px-4 py-3 text-xs">
                                            {job.result?.metrics?.best_model_name || '-'}
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium 
                                                ${job.status === 'completed' ? 'bg-green-100 text-green-700' :
                                                    job.status === 'failed' ? 'bg-red-100 text-red-700' :
                                                        'bg-blue-100 text-blue-700'}`}>
                                                {job.status}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-slate-400">{new Date(job.created_at).toLocaleString()}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
};

const ActivityIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-blue-500">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
    </svg>
);

export default AIInsights;
