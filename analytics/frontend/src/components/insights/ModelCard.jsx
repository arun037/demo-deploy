import React, { useState } from 'react';
import { Play, CheckCircle, Award, FileText, ChevronDown, ChevronUp } from 'lucide-react';
import { config } from '../../config';
import InsightReportModal from './InsightReportModal';

const ModelCard = ({ job }) => {
    const [inputs, setInputs] = useState({});
    const [prediction, setPrediction] = useState(null);
    const [loading, setLoading] = useState(false);
    const [isReportOpen, setIsReportOpen] = useState(false);
    const [showAllFeatures, setShowAllFeatures] = useState(false);

    if (!job || job.status !== 'completed' || !job.result) return null;

    const { target, recommended_features, metrics, input_features } = job.result;
    const plan = job.artifacts?.plan;
    const testMetrics = metrics?.test_metrics || {};
    const bestModel = metrics?.best_model_name || 'Unknown';
    const algorithmsTried = metrics?.algorithms_tried || 0;
    const isClassification = plan?.task_type === 'classification';

    // Clean feature names for display
    const cleanFeatureName = (name) => {
        let clean = name;
        for (const prefix of ['num__', 'cat__', 'remainder__']) {
            clean = clean.replace(prefix, '');
        }
        return clean.replace(/_/g, ' ');
    };

    // Use input_features (pre-engineering names) for prediction form
    const displayFeatures = input_features || recommended_features || [];
    const visibleFeatures = showAllFeatures ? displayFeatures : displayFeatures.slice(0, 6);

    const handlePredict = async () => {
        setLoading(true);
        try {
            const response = await fetch(`${config.API.BASE_URL}/api/insights/predict/${job.id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ input_data: inputs })
            });
            const data = await response.json();
            setPrediction(data.prediction);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleInputChange = (feature, value) => {
        setInputs(prev => ({ ...prev, [feature]: value }));
    };

    // Primary metric display
    const primaryMetric = isClassification
        ? { label: 'Accuracy', value: testMetrics.accuracy }
        : { label: 'R', value: testMetrics.r2 };

    return (
        <>
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col transition hover:shadow-md">
                {/* Header */}
                <div className="bg-gradient-to-r from-brand-navy to-blue-700 p-4 text-white flex items-start justify-between">
                    <div>
                        <h3 className="font-bold text-lg flex items-center gap-2">
                            <CheckCircle size={20} />
                            {plan?.task_name || "Predictive Model"}
                        </h3>
                        <div className="text-blue-100 text-sm mt-1 flex items-center gap-2 flex-wrap">
                            <span>Target: {target}</span>
                            <span className="bg-white/20 px-2 py-0.5 rounded-full text-xs font-bold flex items-center gap-1">
                                <Award size={12} /> {bestModel}
                            </span>
                        </div>
                    </div>
                    <button
                        onClick={() => setIsReportOpen(true)}
                        className="bg-white/10 hover:bg-white/20 p-2 rounded-lg transition-colors flex items-center gap-2 text-xs font-semibold backdrop-blur-sm"
                    >
                        <FileText size={16} />
                        Full Report
                    </button>
                </div>

                {/* Metrics Row */}
                <div className="p-4 grid grid-cols-3 gap-3 bg-slate-50 border-b border-slate-100">
                    <div className="text-center">
                        <div className="text-xs text-slate-500 uppercase">{primaryMetric.label}</div>
                        <div className="font-bold text-slate-800 text-lg">
                            {primaryMetric.value ? (primaryMetric.value * 100).toFixed(1) + '%' : 'N/A'}
                        </div>
                    </div>
                    {isClassification && testMetrics.f1 !== undefined && (
                        <div className="text-center">
                            <div className="text-xs text-slate-500 uppercase">F1</div>
                            <div className="font-bold text-slate-800 text-lg">
                                {(testMetrics.f1 * 100).toFixed(1)}%
                            </div>
                        </div>
                    )}
                    {!isClassification && testMetrics.rmse !== undefined && (
                        <div className="text-center">
                            <div className="text-xs text-slate-500 uppercase">RMSE</div>
                            <div className="font-bold text-slate-800 text-lg">
                                {testMetrics.rmse.toFixed(2)}
                            </div>
                        </div>
                    )}
                    <div className="text-center">
                        <div className="text-xs text-slate-500 uppercase">Models</div>
                        <div className="font-bold text-slate-800 text-lg">{algorithmsTried}</div>
                    </div>
                </div>

                {/* Input Form */}
                <div className="p-4 flex-1 space-y-3">
                    <h4 className="font-semibold text-slate-700 text-sm">Test Prediction</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {visibleFeatures.map(feat => (
                            <div key={feat}>
                                <label className="text-xs text-slate-500 block mb-1 truncate" title={feat}>
                                    {cleanFeatureName(feat)}
                                </label>
                                <input
                                    type="text"
                                    className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none transition"
                                    placeholder="Value..."
                                    onChange={(e) => handleInputChange(feat, e.target.value)}
                                />
                            </div>
                        ))}
                    </div>
                    {displayFeatures.length > 6 && (
                        <button
                            onClick={() => setShowAllFeatures(!showAllFeatures)}
                            className="text-xs text-indigo-600 hover:text-indigo-800 font-medium flex items-center gap-1 mx-auto"
                        >
                            {showAllFeatures ? (
                                <><ChevronUp size={14} /> Show fewer</>
                            ) : (
                                <><ChevronDown size={14} /> Show all {displayFeatures.length} features</>
                            )}
                        </button>
                    )}
                </div>

                {/* Footer / Action */}
                <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
                    {prediction !== null && (
                        <div className={`text-lg font-bold px-3 py-1 rounded-lg ${typeof prediction === 'number'
                                ? 'bg-blue-100 text-blue-800'
                                : prediction === 1 || prediction === '1' || prediction === true
                                    ? 'bg-green-100 text-green-800'
                                    : 'bg-amber-100 text-amber-800'
                            }`}>
                            Result: {typeof prediction === 'number' ? prediction.toFixed(2) : String(prediction)}
                        </div>
                    )}

                    <button
                        onClick={handlePredict}
                        disabled={loading}
                        className="bg-brand-navy text-white px-4 py-2 rounded-lg hover:bg-blue-800 transition flex items-center gap-2 text-sm ml-auto disabled:opacity-50"
                    >
                        {loading ? 'Thinking...' : 'Run Prediction'}
                        {!loading && <Play size={16} />}
                    </button>
                </div>
            </div>

            <InsightReportModal
                isOpen={isReportOpen}
                onClose={() => setIsReportOpen(false)}
                job={job}
            />
        </>
    );
};

export default ModelCard;
