
import React from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    AreaChart, Area, Cell
} from 'recharts';
import { Lightbulb, TrendingUp, BarChart2, Shield, Zap, Award, Activity, Target } from 'lucide-react';

/* =============================================
   PREMIUM INSIGHT REPORT
   - Dynamic NxN Confusion Matrix
   - Model Comparison Chart
   - Gradient Feature Importance
   - Data Quality Badge
   - 4+ Metric Cards
   ============================================= */

const InsightReport = ({ job }) => {
    if (!job || !job.result) return null;

    const { narrative, charts, target, data_quality } = job.result;
    const plan = job.artifacts?.plan || {};
    const metrics = job.result.metrics?.test_metrics || {};
    const validationScores = job.result.metrics?.validation_scores || {};
    const bestModelName = job.result.metrics?.best_model_name || 'Unknown';
    const dataAnalysis = job.result.metrics?.data_analysis || {};

    // Chart data
    const featureImpData = (charts?.feature_importance || []).slice(0, 10);
    const distributionData = charts?.distribution || null;
    const confusionData = charts?.confusion_matrix || {};

    // Distribution chart data
    const distChartData = distributionData ? distributionData.bins.map((bin, i) => ({
        bin,
        count: distributionData.counts[i]
    })) : [];

    // Model comparison data (from validation_scores)
    const modelComparisonData = Object.entries(validationScores)
        .filter(([_, v]) => !v.error)
        .map(([name, scores]) => ({
            name: name,
            score: Math.round((scores.mean || 0) * 1000) / 10,
            isBest: name === bestModelName
        }))
        .sort((a, b) => b.score - a.score);

    // Task type detection
    const isClassification = plan.task_type === 'classification';

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            {/* Executive Summary */}
            <div className="bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 p-6 rounded-xl border border-indigo-100 shadow-sm">
                <h3 className="text-xl font-bold text-indigo-900 flex items-center gap-2 mb-4">
                    <Lightbulb className="text-amber-500" />
                    Executive Summary
                </h3>

                {plan.hypothesis && (
                    <div className="mb-4 text-sm text-indigo-600 bg-white/60 p-3 rounded-lg border border-indigo-100">
                        <span className="font-bold uppercase text-xs tracking-wider opacity-70 block mb-1">Initial Hypothesis</span>
                        "{plan.hypothesis}"
                    </div>
                )}

                <div className="prose prose-indigo max-w-none text-slate-700 leading-relaxed font-medium">
                    {narrative || "Analysis complete. Review the metrics below."}
                </div>
            </div>

            {/* Metrics Overview */}
            <div className={`grid gap-4 ${isClassification ? 'grid-cols-2 md:grid-cols-5' : 'grid-cols-2 md:grid-cols-4'}`}>
                {isClassification ? (
                    <>
                        <MetricCard label="Accuracy" value={fmt(metrics.accuracy)} sublabel="Overall Correct"
                            icon={<Target size={16} className="text-green-600" />} color="green" />
                        <MetricCard label="F1 Score" value={fmt(metrics.f1)} sublabel="Balanced Measure"
                            icon={<Shield size={16} className="text-blue-600" />} color="blue" />
                        <MetricCard label="Precision" value={fmt(metrics.precision)} sublabel="Positive Accuracy"
                            icon={<Zap size={16} className="text-purple-600" />} color="purple" />
                        <MetricCard label="Recall" value={fmt(metrics.recall)} sublabel="Detection Rate"
                            icon={<Activity size={16} className="text-orange-600" />} color="orange" />
                        <MetricCard label="Algorithm" value={bestModelName} sublabel={`${dataAnalysis.algorithms_tried || '?'} tried`}
                            icon={<Award size={16} className="text-amber-600" />} color="amber" isText />
                    </>
                ) : (
                    <>
                        <MetricCard label="R Score" value={fmt(metrics.r2)} sublabel="Variance Explained"
                            icon={<TrendingUp size={16} className="text-green-600" />} color="green" />
                        <MetricCard label="MAE" value={metrics.mae?.toFixed(2) || 'N/A'} sublabel="Mean Abs Error"
                            icon={<BarChart2 size={16} className="text-blue-600" />} color="blue" />
                        <MetricCard label="RMSE" value={metrics.rmse?.toFixed(2) || 'N/A'} sublabel="Root Mean Sq Error"
                            icon={<Activity size={16} className="text-orange-600" />} color="orange" />
                        <MetricCard label="Algorithm" value={bestModelName} sublabel={`${dataAnalysis.algorithms_tried || '?'} tried`}
                            icon={<Award size={16} className="text-amber-600" />} color="amber" isText />
                    </>
                )}
            </div>

            {/* Data Quality Badge */}
            {data_quality && data_quality.score !== undefined && (
                <div className="flex items-center gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-sm
                        ${data_quality.score >= 80 ? 'bg-green-500' : data_quality.score >= 50 ? 'bg-amber-500' : 'bg-red-500'}`}>
                        {data_quality.score}
                    </div>
                    <div>
                        <div className="font-semibold text-slate-800">Data Quality Score</div>
                        <div className="text-xs text-slate-500">
                            {data_quality.score >= 80 ? 'Excellent data quality' :
                                data_quality.score >= 50 ? 'Moderate  some data issues detected' :
                                    'Poor  significant data quality issues'}
                            {data_quality.total_missing_pct > 0 && ` - ${data_quality.total_missing_pct}% avg missing`}
                        </div>
                    </div>
                </div>
            )}

            {/* Model Comparison Chart */}
            {modelComparisonData.length > 1 && (
                <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                    <h4 className="font-bold text-slate-800 mb-1 flex items-center gap-2">
                        <Award size={18} className="text-amber-500" />
                        Algorithm Competition
                    </h4>
                    <p className="text-xs text-slate-500 mb-4">
                        Cross-validated performance of all candidate models (higher is better)
                    </p>
                    <div style={{ height: Math.max(200, modelComparisonData.length * 40) }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={modelComparisonData} layout="vertical" margin={{ left: 20, right: 40 }}>
                                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                                <YAxis
                                    dataKey="name" type="category" width={140}
                                    tick={{ fontSize: 11, fill: '#64748b' }}
                                />
                                <Tooltip
                                    cursor={{ fill: '#f1f5f9' }}
                                    formatter={(val) => [`${val}%`, 'CV Score']}
                                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                />
                                <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={24}>
                                    {modelComparisonData.map((entry, idx) => (
                                        <Cell key={idx} fill={entry.isBest ? '#6366f1' : '#cbd5e1'} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}

            {/* Charts Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                {/* Feature Importance with Gradient */}
                <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                    <h4 className="font-bold text-slate-800 mb-1">Key Drivers</h4>
                    <p className="text-xs text-slate-500 mb-4">What impacts {target} the most?</p>
                    <div className="h-72">
                        {featureImpData.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={featureImpData} layout="vertical" margin={{ left: 20 }}>
                                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                    <XAxis type="number" hide />
                                    <YAxis
                                        dataKey="feature" type="category" width={130}
                                        tick={{ fontSize: 10, fill: '#64748b' }}
                                    />
                                    <Tooltip
                                        cursor={{ fill: '#f1f5f9' }}
                                        formatter={(val) => [val.toFixed(4), 'Importance']}
                                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                    />
                                    <Bar dataKey="importance" radius={[0, 4, 4, 0]} barSize={18}>
                                        {featureImpData.map((entry, idx) => (
                                            <Cell key={idx} fill={getGradientColor(idx, featureImpData.length)} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="h-full flex items-center justify-center text-slate-400 text-sm">No importance data</div>
                        )}
                    </div>
                </div>

                {/* Distribution */}
                <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                    <h4 className="font-bold text-slate-800 mb-1">Data Distribution</h4>
                    <p className="text-xs text-slate-500 mb-4">How is {target} distributed?</p>
                    <div className="h-72">
                        {distChartData.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={distChartData}>
                                    <defs>
                                        <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <XAxis
                                        dataKey="bin"
                                        tick={{ fontSize: 9, fill: '#64748b' }}
                                        interval={0} angle={-45} textAnchor="end" height={70}
                                    />
                                    <YAxis hide />
                                    <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                                    <Area type="monotone" dataKey="count" stroke="#8b5cf6" fillOpacity={1} fill="url(#colorCount)" />
                                </AreaChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="h-full flex items-center justify-center text-slate-400 text-sm">No distribution data</div>
                        )}
                    </div>
                </div>
            </div>

            {/* Dynamic NxN Confusion Matrix */}
            {confusionData.matrix && confusionData.matrix.length > 0 && (
                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                    <h4 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
                        <TrendingUp size={18} className="text-indigo-600" />
                        Prediction Matrix ({confusionData.labels.length}-Class)
                    </h4>
                    <div className="flex flex-col md:flex-row items-start gap-8">
                        <div className="overflow-x-auto scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                            <table className="border-collapse">
                                <thead>
                                    <tr>
                                        <th className="p-2 text-xs text-slate-500">Actual  / Predicted </th>
                                        {confusionData.labels.map(l => (
                                            <th key={l} className="p-2 text-xs font-bold text-indigo-700 text-center min-w-[60px]">{l}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {confusionData.matrix.map((row, ri) => (
                                        <tr key={ri}>
                                            <td className="p-2 text-xs font-bold text-indigo-700">{confusionData.labels[ri]}</td>
                                            {row.map((val, ci) => {
                                                const maxVal = Math.max(...confusionData.matrix.flat());
                                                const intensity = maxVal > 0 ? val / maxVal : 0;
                                                const isDiagonal = ri === ci;
                                                return (
                                                    <td key={ci} className="p-1">
                                                        <div
                                                            className="w-16 h-16 flex items-center justify-center rounded-lg text-sm font-bold transition-all"
                                                            style={{
                                                                backgroundColor: isDiagonal
                                                                    ? `rgba(99, 102, 241, ${0.15 + intensity * 0.85})`
                                                                    : `rgba(239, 68, 68, ${intensity * 0.4})`,
                                                                color: (isDiagonal && intensity > 0.4) || (!isDiagonal && intensity > 0.6) ? 'white' : '#475569'
                                                            }}
                                                        >
                                                            {val}
                                                        </div>
                                                    </td>
                                                );
                                            })}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        <div className="flex-1 space-y-3">
                            <div className="bg-indigo-50 p-4 rounded-lg border border-indigo-100">
                                <p className="text-sm text-indigo-900 font-medium">
                                    Diagonal cells (blue) show correct predictions. Off-diagonal cells (red) show errors.
                                    Higher diagonal values indicate better model performance for each class.
                                </p>
                            </div>
                            <div className="flex items-center gap-4 text-xs text-slate-500">
                                <div className="flex items-center gap-1">
                                    <div className="w-4 h-4 rounded bg-indigo-500"></div> Correct
                                </div>
                                <div className="flex items-center gap-1">
                                    <div className="w-4 h-4 rounded bg-red-300"></div> Misclassified
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

/* ---------- HELPERS ---------- */

const fmt = (val) => {
    if (val === undefined || val === null) return 'N/A';
    return (val * 100).toFixed(1) + '%';
};

const getGradientColor = (index, total) => {
    // Green  Yellow  Orange  Red gradient
    const colors = ['#10b981', '#22c55e', '#84cc16', '#eab308', '#f97316', '#ef4444', '#dc2626', '#b91c1c', '#991b1b', '#7f1d1d'];
    return colors[Math.min(index, colors.length - 1)];
};

const MetricCard = ({ label, value, sublabel, icon, color = 'slate', isText = false }) => (
    <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-center hover:shadow-md transition-shadow">
        <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-500 uppercase">{label}</span>
            {icon}
        </div>
        <div className={`${isText ? 'text-sm' : 'text-xl'} font-bold text-slate-800 truncate`} title={value}>{value}</div>
        <div className="text-xs text-slate-400 mt-1 truncate">{sublabel}</div>
    </div>
);

export default InsightReport;
