import React, { Suspense, lazy } from 'react';
import {
    BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
    AreaChart, Area, ScatterChart, Scatter,
    XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import { Lightbulb, TrendingUp } from 'lucide-react';
import { useContainerWidth } from '../hooks/useContainerWidth.js';

// Lazy-load Plotly to avoid bundle bloat for users who never see advanced charts
const Plot = lazy(() => import('react-plotly.js'));

// Advanced chart types rendered by Plotly (everything else uses Recharts)
const ADVANCED_CHART_TYPES = new Set([
    'bubble_chart', 'histogram', 'heatmap', 'funnel_chart',
    'waterfall_chart', 'treemap', 'gauge', 'candlestick'
]);

// Enhanced color scheme with vibrant, varied colors
const COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4', '#f97316'];

// Gradient color pairs for modern look
const GRADIENT_COLORS = [
    { start: '#3b82f6', end: '#60a5fa', name: 'blue' },      // Blue gradient
    { start: '#8b5cf6', end: '#a78bfa', name: 'purple' },    // Purple gradient
    { start: '#10b981', end: '#34d399', name: 'green' },     // Green gradient
    { start: '#f59e0b', end: '#fbbf24', name: 'amber' },     // Amber gradient
    { start: '#ef4444', end: '#f87171', name: 'red' },       // Red gradient
    { start: '#ec4899', end: '#f472b6', name: 'pink' },      // Pink gradient
    { start: '#06b6d4', end: '#22d3ee', name: 'cyan' },      // Cyan gradient
    { start: '#f97316', end: '#fb923c', name: 'orange' }     // Orange gradient
];



// Fallback colors for unknown categories
const DEFAULT_COLORS = COLORS;

const InsightPanel = React.memo(({ config, data }) => {
    const { isNarrow, width } = useContainerWidth();

    // Calculate responsive chart height based on container width
    // Narrow (< 500px): 200px, Mobile (500-640px): 240px, Tablet (640-1024px): 300px, Desktop: 360px
    const getChartHeight = (baseHeight = 360) => {
        if (isNarrow) return 200;
        if (width < 640) return 240;
        if (width < 1024) return 300;
        return baseHeight;
    };

    // Enhanced validation with better error handling
    if (!config) {
        console.warn('InsightPanel: No config provided');
        return null;
    }

    if (!data || !Array.isArray(data) || data.length === 0) {
        console.warn('InsightPanel: No valid data provided', { data });
        return (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm mt-4 p-6 text-center">
                <div className="text-slate-400 text-sm">No data available for visualization</div>
            </div>
        );
    }

    // Support both old format (single chart) and new format (list of charts)
    const charts = config.charts || [config];
    const summary = config.summary;

    // Helper function to get category-aware colors
    const getCategoryColors = (chartConfig, index) => {
        return DEFAULT_COLORS;
    };

    // Helper function to safely get chart data with validation
    const getChartData = (chartConfig) => {
        const chartData = chartConfig.data_override || data;

        if (!Array.isArray(chartData) || chartData.length === 0) {
            console.warn('InsightPanel: Invalid chart data', { chartConfig: chartConfig.title, data: chartData });
            return [];
        }

        return chartData;
    };

    // Helper function to detect chart type mapping
    // Backend sends: 'bar_chart', 'pie_chart', 'line_chart', 'area_chart', 'multi_line',
    //                'multi_bar', 'scatter_chart', 'kpi_card' etc.
    // Also handles legacy short names: 'bar', 'pie', 'line', 'area', 'scatter', 'kpi'
    const getRechartsType = (chartType) => {
        const typeMapping = {
            // New _chart / _card names (from new backend)
            'bar_chart': 'bar',
            'line_chart': 'line',
            'area_chart': 'area',
            'pie_chart': 'pie',
            'multi_line': 'line',   // handled inside case 'line' via chart_type check
            'multi_bar': 'bar',    // handled inside case 'bar' via chart_type check
            'scatter_chart': 'scatter',
            // Legacy short names (backward compat)
            'bar': 'bar',
            'grouped_bar': 'bar',
            'horizontal_bar': 'bar',
            'line': 'line',
            'area': 'area',
            'pie': 'pie',
            'scatter': 'scatter',
        };
        return typeMapping[chartType] || 'bar';
    };

    // Key Normalization Helper
    const findMatchingKey = (requestedKey, dataRow) => {
        if (!requestedKey || !dataRow) return requestedKey;
        const keys = Object.keys(dataRow);
        const exact = keys.find(k => k === requestedKey);
        if (exact) return exact;
        const normalized = requestedKey.toLowerCase().replace(/_/g, '').replace(/ /g, '');
        return keys.find(k => k.toLowerCase().replace(/_/g, '').replace(/ /g, '') === normalized) || requestedKey;
    };

    // ──────────────────────────────────────────────────────────────────────────
    // Advanced Charts via Plotly.js
    // ──────────────────────────────────────────────────────────────────────────
    const PLOTLY_BASE_LAYOUT = {
        margin: { t: 20, r: 10, b: 50, l: 50 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { family: 'Inter, system-ui, sans-serif', size: 11, color: '#475569' },
        showlegend: false,
    };

    const renderAdvancedChart = (chartConfig, index, chartData) => {
        const { chart_type, title, description, x_key, y_key, size_key } = chartConfig;
        // DataContractor sends pre-shaped data in data_override for advanced types
        const d = chartConfig.data_override || chartData;

        let traces = [];
        let extraLayout = {};

        try {
            switch (chart_type) {
                case 'bubble_chart': {
                    // Expects [{x, y, z}] from DataContractor
                    const xs = Array.isArray(d) ? d.map(r => r.x ?? r[x_key] ?? 0) : [];
                    const ys = Array.isArray(d) ? d.map(r => r.y ?? r[y_key] ?? 0) : [];
                    const zs = Array.isArray(d) ? d.map(r => r.z ?? r[size_key] ?? 1) : [];
                    const maxZ = Math.max(...zs, 1);
                    traces = [{
                        type: 'scatter', mode: 'markers',
                        x: xs, y: ys,
                        marker: {
                            size: zs.map(z => Math.max(8, Math.sqrt(z / maxZ) * 60)),
                            color: zs, colorscale: 'Blues', showscale: true,
                            opacity: 0.75, line: { color: '#fff', width: 1 }
                        },
                        text: Array.isArray(d) ? d.map((_, i) => `(${xs[i]}, ${ys[i]}) size: ${zs[i]}`) : [],
                        hovertemplate: '%{text}<extra></extra>'
                    }];
                    extraLayout = { xaxis: { title: x_key }, yaxis: { title: y_key } };
                    break;
                }
                case 'histogram': {
                    const vals = Array.isArray(d) ? d.map(r => r[x_key] ?? Object.values(r)[0]) : [];
                    traces = [{
                        type: 'histogram', x: vals,
                        marker: { color: '#3b82f6', opacity: 0.8 },
                        nbinsx: Math.min(30, Math.ceil(Math.sqrt(vals.length)))
                    }];
                    extraLayout = { bargap: 0.05, xaxis: { title: x_key } };
                    break;
                }
                case 'heatmap': {
                    // Expects {type:'pivot', z, x_labels, y_labels} or list of records
                    if (d && d.type === 'pivot') {
                        traces = [{ type: 'heatmap', z: d.z, x: d.x_labels, y: d.y_labels, colorscale: 'Blues' }];
                    } else if (Array.isArray(d)) {
                        const xs = [...new Set(d.map(r => r[x_key]))];
                        const ys = [...new Set(d.map(r => r[y_key || size_key]))];
                        const zMatrix = ys.map(yv => xs.map(xv => {
                            const found = d.find(r => r[x_key] === xv && r[y_key] === yv);
                            return found ? (found[size_key] ?? 0) : 0;
                        }));
                        traces = [{ type: 'heatmap', z: zMatrix, x: xs, y: ys, colorscale: 'Blues' }];
                    }
                    break;
                }
                case 'funnel_chart': {
                    const labels = Array.isArray(d) ? d.map(r => r[x_key] ?? Object.keys(r)[0]) : [];
                    const values = Array.isArray(d) ? d.map(r => r[y_key] ?? Object.values(r)[1]) : [];
                    traces = [{ type: 'funnel', y: labels, x: values, textinfo: 'value+percent initial', marker: { color: COLORS } }];
                    extraLayout = { funnelmode: 'stack' };
                    break;
                }
                case 'waterfall_chart': {
                    const labels = Array.isArray(d) ? d.map(r => r[x_key]) : [];
                    const values = Array.isArray(d) ? d.map(r => r[y_key]) : [];
                    traces = [{
                        type: 'waterfall', x: labels, y: values,
                        connector: { line: { color: '#94a3b8' } },
                        increasing: { marker: { color: '#10b981' } },
                        decreasing: { marker: { color: '#ef4444' } },
                        totals: { marker: { color: '#3b82f6' } }
                    }];
                    break;
                }
                case 'treemap': {
                    const labels = Array.isArray(d) ? d.map(r => r[x_key]) : [];
                    const values = Array.isArray(d) ? d.map(r => r[y_key]) : [];
                    traces = [{
                        type: 'treemap',
                        labels: labels, parents: labels.map(() => ''), values: values,
                        textinfo: 'label+value+percent root',
                        marker: { colorscale: 'Blues' }
                    }];
                    break;
                }
                case 'gauge': {
                    const val = Array.isArray(d) && d.length > 0 ? (d[0][y_key] ?? Object.values(d[0])[0]) : 0;
                    const maxVal = val * 1.5;
                    traces = [{
                        type: 'indicator', mode: 'gauge+number', value: val,
                        gauge: {
                            axis: { range: [0, maxVal] },
                            bar: { color: '#3b82f6' },
                            steps: [
                                { range: [0, maxVal * 0.4], color: '#dbeafe' },
                                { range: [maxVal * 0.4, maxVal * 0.7], color: '#93c5fd' },
                                { range: [maxVal * 0.7, maxVal], color: '#3b82f6' }
                            ]
                        }
                    }];
                    extraLayout = { margin: { t: 30, r: 20, b: 20, l: 20 } };
                    break;
                }
                default: {
                    // Unknown advanced type: fallback to simple bar
                    const xVals = Array.isArray(d) ? d.map(r => r[x_key] ?? Object.keys(r)[0]) : [];
                    const yVals = Array.isArray(d) ? d.map(r => r[y_key] ?? Object.values(r)[1]) : [];
                    traces = [{ type: 'bar', x: xVals, y: yVals, marker: { color: '#3b82f6' } }];
                }
            }
        } catch (err) {
            console.error('InsightPanel: Advanced chart render failed', err);
            return (
                <div key={index} className="bg-white rounded-lg p-3 border border-slate-200 shadow-sm">
                    <h4 className="text-xs font-semibold text-slate-700">{title}</h4>
                    <div className="text-center py-6 text-slate-400 text-xs">Advanced chart could not be rendered</div>
                </div>
            );
        }

        return (
            <div key={index} className="bg-white rounded-lg p-3 border border-blue-100 shadow-sm">
                <div className="mb-2 flex items-center justify-between">
                    <h4 className="text-xs font-semibold text-slate-700 pl-1 border-l-2 border-blue-500">{title}</h4>
                    <span className="text-[9px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full font-medium uppercase tracking-wide">
                        {chart_type.replace(/_/g, ' ')}
                    </span>
                </div>
                <Suspense fallback={<div className="h-64 flex items-center justify-center text-slate-400 text-xs">Loading chart…</div>}>
                    <Plot
                        data={traces}
                        layout={{ ...PLOTLY_BASE_LAYOUT, ...extraLayout, height: 280 }}
                        config={{ displayModeBar: false, responsive: true }}
                        style={{ width: '100%' }}
                    />
                </Suspense>
                {description && <p className="text-[10px] text-slate-500 mt-2 italic">{description}</p>}
            </div>
        );
    };

    const renderSingleChart = (chartConfig, index) => {

        const {
            chart_type, title, subtitle, x_key, y_key, description,
            x_axis_title, y_axis_title, // NEW: Axis labels from backend
            data_override, category_insights, enhanced, series_by, group_by
        } = chartConfig;

        // ── KPI Card: handle FIRST, before getChartData (data_override is a dict, not an array) ──
        if (chart_type === 'kpi' || chart_type === 'kpi_card') {
            let displayValue = chartConfig.value;
            // data_override from DataContractor is {value: "$1.2M"} — a dict
            if (!displayValue && data_override && typeof data_override === 'object' && !Array.isArray(data_override)) {
                displayValue = data_override.value;
            }
            // Fallback: first value from the raw data array
            if (!displayValue) {
                const rawData = Array.isArray(data_override) ? data_override : (Array.isArray(chartConfig.data) ? chartConfig.data : null);
                if (rawData && rawData.length > 0) {
                    displayValue = Object.values(rawData[0])[0];
                }
            }
            return (
                <div key={index} className="bg-gradient-to-br from-blue-50 to-slate-50 rounded-lg p-4 border border-blue-200 shadow-sm">
                    <div className="flex items-center gap-1 mb-2">
                        <TrendingUp size={14} className="text-blue-500" />
                        <h4 className="text-xs font-semibold text-slate-600">{title}</h4>
                    </div>
                    <div className="text-3xl font-bold text-brand-navy">{String(displayValue ?? 'N/A')}</div>
                    {description && <p className="text-[10px] text-slate-500 mt-2 italic">{description}</p>}
                </div>
            );
        }

        // ── Advanced charts: route to Plotly BEFORE array check ──
        if (ADVANCED_CHART_TYPES.has(chart_type) || chartConfig.is_advanced) {
            const rawData = Array.isArray(data_override) ? data_override : [];
            return renderAdvancedChart(chartConfig, index, rawData);
        }

        // Get validated chart data for standard charts (must be array)
        const chartData = getChartData(chartConfig);
        if (chartData.length === 0) {
            return (
                <div key={index} className="bg-white rounded-lg p-3 border border-slate-200 shadow-sm">
                    <h4 className="text-xs font-semibold text-slate-700">{title || 'Chart'}</h4>
                    <div className="text-center py-8 text-slate-400 text-sm">No data available</div>
                </div>
            );
        }

        // Safe key resolution with fallbacks
        const actualXKey = findMatchingKey(x_key, chartData[0]) || Object.keys(chartData[0] || {})[0];
        const actualYKey = findMatchingKey(y_key, chartData[0]) || Object.keys(chartData[0] || {})[1];

        if (!actualXKey || !actualYKey) {
            console.warn('InsightPanel: Missing required keys', {
                chart: title,
                x_key,
                y_key,
                actualXKey,
                actualYKey,
                availableKeys: Object.keys(chartData[0] || {})
            });
            return (
                <div key={index} className="bg-white rounded-lg p-3 border border-slate-200 shadow-sm">
                    <h4 className="text-xs font-semibold text-slate-700">{title || 'Chart'}</h4>
                    <div className="text-center py-8 text-slate-400 text-sm">Invalid data structure</div>
                </div>
            );
        }

        // Get category-aware colors
        const colors = getCategoryColors(chartConfig, index);
        const rechartsType = getRechartsType(chart_type);

        const ChartComponent = () => {
            // Enhanced error boundary
            try {
                switch (rechartsType) {
                    case 'bar':
                        // Handle grouped bars and multi-series with gradients
                        if ((chart_type === 'grouped_bar' || chart_type === 'multi_bar') && (group_by || series_by)) {
                            // For grouped bars, we expect data to have multiple numeric columns
                            const numericColumns = Object.keys(chartData[0] || {}).filter(key =>
                                key !== actualXKey && typeof chartData[0][key] === 'number'
                            );

                            return (
                                <ResponsiveContainer width="100%" height={getChartHeight(360)}>
                                    <BarChart data={chartData} margin={{ top: 20, bottom: 70 }}>
                                        <defs>
                                            {numericColumns.slice(0, 4).map((col, i) => {
                                                const gradient = GRADIENT_COLORS[i % GRADIENT_COLORS.length];
                                                return (
                                                    <linearGradient key={`gradient-${col}`} id={`groupedGradient-${index}-${i}`} x1="0" y1="0" x2="0" y2="1">
                                                        <stop offset="0%" stopColor={gradient.start} stopOpacity={1} />
                                                        <stop offset="100%" stopColor={gradient.end} stopOpacity={0.8} />
                                                    </linearGradient>
                                                );
                                            })}
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                        <XAxis
                                            dataKey={actualXKey}
                                            tick={{ fontSize: 11, fill: '#64748b', angle: -45, textAnchor: 'end' }}
                                            axisLine={{ stroke: '#cbd5e1' }}
                                            tickLine={false}
                                            height={80}
                                            interval={0}
                                        />
                                        <YAxis
                                            tick={{ fontSize: 11, fill: '#64748b' }}
                                            axisLine={false}
                                            tickLine={false}
                                        />
                                        <Tooltip
                                            contentStyle={{
                                                borderRadius: '12px',
                                                border: 'none',
                                                boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
                                                padding: '12px'
                                            }}
                                            formatter={(value) => typeof value === 'number' ? value.toLocaleString() : value}
                                        />
                                        <Legend iconType="circle" wrapperStyle={{ fontSize: '11px' }} />
                                        {numericColumns.slice(0, 4).map((col, i) => (
                                            <Bar
                                                key={col}
                                                dataKey={col}
                                                fill={`url(#groupedGradient-${index}-${i})`}
                                                radius={[6, 6, 0, 0]}
                                                name={col.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                            />
                                        ))}
                                    </BarChart>
                                </ResponsiveContainer>
                            );
                        }

                        // Standard bar chart with enhanced styling
                        const gradientId = `barGradient-${index}`;
                        const gradient = GRADIENT_COLORS[index % GRADIENT_COLORS.length];

                        // Calculate summary stats
                        const total = chartData.reduce((sum, item) => sum + (Number(item[actualYKey]) || 0), 0);
                        const average = total / chartData.length;
                        const max = Math.max(...chartData.map(item => Number(item[actualYKey]) || 0));

                        // Custom label component for bars
                        const CustomLabel = (props) => {
                            const { x, y, width, height, value } = props;
                            if (height < 20) return null; // Don't show label if bar is too small

                            return (
                                <text
                                    x={x + width / 2}
                                    y={y - 6}
                                    fill="#475569"
                                    textAnchor="middle"
                                    transform={`rotate(-25, ${x + width / 2}, ${y - 6})`}
                                    fontSize="10px"
                                    fontWeight="600"
                                >
                                    {typeof value === 'number' ? value.toLocaleString() : value}
                                </text>
                            );
                        };

                        const barMargin = {
                            top: 20,
                            right: 20,
                            bottom: x_axis_title ? 75 : 60,
                            left: y_axis_title ? 20 : 0
                        };

                        return (
                            <>
                                {/* Summary Statistics */}
                                <div className="grid grid-cols-3 gap-2 mb-3">
                                    <div className="bg-gradient-to-br from-blue-50 to-blue-100/50 rounded-lg p-2 border border-blue-200">
                                        <div className="text-[9px] text-blue-600 font-medium uppercase tracking-wide">Total</div>
                                        <div className="text-sm font-bold text-blue-900">{total.toLocaleString()}</div>
                                    </div>
                                    <div className="bg-gradient-to-br from-purple-50 to-purple-100/50 rounded-lg p-2 border border-purple-200">
                                        <div className="text-[9px] text-purple-600 font-medium uppercase tracking-wide">Average</div>
                                        <div className="text-sm font-bold text-purple-900">{Math.round(average).toLocaleString()}</div>
                                    </div>
                                    <div className="bg-gradient-to-br from-amber-50 to-amber-100/50 rounded-lg p-2 border border-amber-200">
                                        <div className="text-[9px] text-amber-600 font-medium uppercase tracking-wide">Peak</div>
                                        <div className="text-sm font-bold text-amber-900">{max.toLocaleString()}</div>
                                    </div>
                                </div>

                                <ResponsiveContainer width="100%" height={360}>
                                    <BarChart data={chartData} margin={barMargin}>
                                        <defs>
                                            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="0%" stopColor={gradient.start} stopOpacity={1} />
                                                <stop offset="100%" stopColor={gradient.end} stopOpacity={0.8} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                        <XAxis
                                            dataKey={actualXKey}
                                            tick={{ fontSize: 11, fill: '#64748b', angle: -45, textAnchor: 'end' }}
                                            axisLine={{ stroke: '#cbd5e1' }}
                                            tickLine={false}
                                            height={80}
                                            interval={0}
                                            label={x_axis_title ? { value: x_axis_title, position: 'insideBottom', offset: -5, fontSize: 12, fill: '#475569', fontWeight: 500 } : undefined}
                                        />
                                        <YAxis
                                            tick={{ fontSize: 11, fill: '#64748b' }}
                                            axisLine={false}
                                            tickLine={false}
                                            label={y_axis_title ? { value: y_axis_title, angle: -90, position: 'insideLeft', offset: 10, fontSize: 12, fill: '#475569', fontWeight: 500 } : undefined}
                                        />
                                        <Tooltip
                                            contentStyle={{
                                                borderRadius: '12px',
                                                border: 'none',
                                                boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
                                                padding: '12px',
                                                backgroundColor: 'white'
                                            }}
                                            formatter={(value) => [typeof value === 'number' ? value.toLocaleString() : value, title]}
                                            labelStyle={{ fontWeight: 600, color: '#1e293b', marginBottom: '4px' }}
                                        />
                                        <Bar
                                            dataKey={actualYKey}
                                            fill={`url(#${gradientId})`}
                                            radius={[8, 8, 0, 0]}
                                            name={title}
                                            label={<CustomLabel />}
                                        />
                                    </BarChart>
                                </ResponsiveContainer>
                            </>
                        );
                    case 'line':
                        // Handle multi-line charts with enhanced styling
                        if (chart_type === 'multi_line' && series_by) {
                            // For multi-line, we expect data to have multiple numeric columns or series
                            const numericColumns = Object.keys(chartData[0] || {}).filter(key =>
                                key !== actualXKey && typeof chartData[0][key] === 'number'
                            );

                            const multiLineMargin = {
                                top: 20,
                                right: 20,
                                bottom: x_axis_title ? 50 : 20,
                                left: y_axis_title ? 20 : 0
                            };

                            return (
                                <ResponsiveContainer width="100%" height={getChartHeight(260)}>
                                    <LineChart data={chartData} margin={multiLineMargin}>
                                        <defs>
                                            {numericColumns.slice(0, 4).map((col, i) => {
                                                const gradient = GRADIENT_COLORS[i % GRADIENT_COLORS.length];
                                                return (
                                                    <linearGradient key={`line-gradient-${col}`} id={`lineGradient-${index}-${i}`} x1="0" y1="0" x2="0" y2="1">
                                                        <stop offset="0%" stopColor={gradient.start} stopOpacity={0.3} />
                                                        <stop offset="100%" stopColor={gradient.end} stopOpacity={0.05} />
                                                    </linearGradient>
                                                );
                                            })}
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                        <XAxis
                                            dataKey={actualXKey}
                                            hide={chartData.length > 20}
                                            tick={{ fontSize: 11, fill: '#64748b' }}
                                            axisLine={{ stroke: '#cbd5e1' }}
                                            tickLine={false}
                                        />
                                        <YAxis
                                            tick={{ fontSize: 11, fill: '#64748b' }}
                                            axisLine={false}
                                            tickLine={false}
                                        />
                                        <Tooltip
                                            contentStyle={{
                                                borderRadius: '12px',
                                                border: 'none',
                                                boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
                                                padding: '12px'
                                            }}
                                            formatter={(value) => typeof value === 'number' ? value.toLocaleString() : value}
                                        />
                                        <Legend iconType="circle" wrapperStyle={{ fontSize: '11px' }} />
                                        {numericColumns.slice(0, 4).map((col, i) => (
                                            <Line
                                                key={col}
                                                type="monotone"
                                                dataKey={col}
                                                stroke={GRADIENT_COLORS[i % GRADIENT_COLORS.length].start}
                                                strokeWidth={3}
                                                dot={{ fill: GRADIENT_COLORS[i % GRADIENT_COLORS.length].start, r: 4 }}
                                                activeDot={{ r: 6, strokeWidth: 2 }}
                                                name={col.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                            />
                                        ))}
                                    </LineChart>
                                </ResponsiveContainer>
                            );
                        }

                        // Standard line chart with gradient area fill
                        const lineGradientId = `lineAreaGradient-${index}`;
                        const lineGradient = GRADIENT_COLORS[index % GRADIENT_COLORS.length];

                        const lineMargin = {
                            top: 20,
                            right: 20,
                            bottom: x_axis_title ? 50 : 20,
                            left: y_axis_title ? 20 : 0
                        };

                        return (
                            <ResponsiveContainer width="100%" height={getChartHeight(260)}>
                                <LineChart data={chartData} margin={lineMargin}>
                                    <defs>
                                        <linearGradient id={lineGradientId} x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="0%" stopColor={lineGradient.start} stopOpacity={0.3} />
                                            <stop offset="100%" stopColor={lineGradient.end} stopOpacity={0.05} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                    <XAxis
                                        dataKey={actualXKey}
                                        hide={chartData.length > 20}
                                        tick={{ fontSize: 11, fill: '#64748b' }}
                                        axisLine={{ stroke: '#cbd5e1' }}
                                        tickLine={false}
                                        height={x_axis_title ? 50 : 30}
                                        label={x_axis_title ? { value: x_axis_title, position: 'insideBottom', offset: -5, fontSize: 12, fill: '#475569', fontWeight: 500 } : undefined}
                                    />
                                    <YAxis
                                        tick={{ fontSize: 11, fill: '#64748b' }}
                                        axisLine={false}
                                        tickLine={false}
                                        label={y_axis_title ? { value: y_axis_title, angle: -90, position: 'insideLeft', offset: 10, fontSize: 12, fill: '#475569', fontWeight: 500 } : undefined}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            borderRadius: '12px',
                                            border: 'none',
                                            boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
                                            padding: '12px'
                                        }}
                                        formatter={(value) => typeof value === 'number' ? value.toLocaleString() : value}
                                        labelStyle={{ fontWeight: 600, color: '#1e293b', marginBottom: '4px' }}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey={actualYKey}
                                        stroke={lineGradient.start}
                                        strokeWidth={3}
                                        dot={{ fill: lineGradient.start, r: 4, strokeWidth: 2, stroke: '#fff' }}
                                        activeDot={{ r: 6, strokeWidth: 2, stroke: '#fff' }}
                                        name={title}
                                        fill={`url(#${lineGradientId})`}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        );
                    case 'area':
                        const areaGradientId = `areaGradient-${index}`;
                        const areaGradient = GRADIENT_COLORS[index % GRADIENT_COLORS.length];

                        const areaMargin = {
                            top: 20,
                            right: 20,
                            bottom: x_axis_title ? 50 : 20,
                            left: y_axis_title ? 20 : 0
                        };

                        return (
                            <ResponsiveContainer width="100%" height={getChartHeight(260)}>
                                <AreaChart data={chartData} margin={areaMargin}>
                                    <defs>
                                        <linearGradient id={areaGradientId} x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="0%" stopColor={areaGradient.start} stopOpacity={0.4} />
                                            <stop offset="100%" stopColor={areaGradient.end} stopOpacity={0.1} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                    <XAxis
                                        dataKey={actualXKey}
                                        hide={chartData.length > 20}
                                        tick={{ fontSize: 11, fill: '#64748b' }}
                                        axisLine={{ stroke: '#cbd5e1' }}
                                        tickLine={false}
                                        height={x_axis_title ? 50 : 30}
                                        label={x_axis_title ? { value: x_axis_title, position: 'insideBottom', offset: -5, fontSize: 12, fill: '#475569', fontWeight: 500 } : undefined}
                                    />
                                    <YAxis
                                        tick={{ fontSize: 11, fill: '#64748b' }}
                                        axisLine={false}
                                        tickLine={false}
                                        label={y_axis_title ? { value: y_axis_title, angle: -90, position: 'insideLeft', offset: 10, fontSize: 12, fill: '#475569', fontWeight: 500 } : undefined}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            borderRadius: '12px',
                                            border: 'none',
                                            boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
                                            padding: '12px'
                                        }}
                                        formatter={(value) => typeof value === 'number' ? value.toLocaleString() : value}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey={actualYKey}
                                        stroke={areaGradient.start}
                                        fill={`url(#${areaGradientId})`}
                                        strokeWidth={2}
                                        name={title}
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        );
                    case 'scatter':
                        const scatterMargin = {
                            top: 20,
                            right: 20,
                            bottom: x_axis_title ? 50 : 20,
                            left: y_axis_title ? 20 : 0
                        };
                        return (
                            <ResponsiveContainer width="100%" height={getChartHeight(260)}>
                                <ScatterChart data={chartData} margin={scatterMargin}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis
                                        dataKey={actualXKey}
                                        name={actualXKey}
                                        tick={{ fontSize: 11 }}
                                        height={x_axis_title ? 50 : 30}
                                        label={x_axis_title ? { value: x_axis_title, position: 'insideBottom', offset: -5, fontSize: 12, fill: '#475569', fontWeight: 500 } : undefined}
                                    />
                                    <YAxis
                                        dataKey={actualYKey}
                                        name={actualYKey}
                                        tick={{ fontSize: 11 }}
                                        label={y_axis_title ? { value: y_axis_title, angle: -90, position: 'insideLeft', offset: 10, fontSize: 12, fill: '#475569', fontWeight: 500 } : undefined}
                                    />
                                    <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                                    <Legend iconType="circle" />
                                    <Scatter name={title} data={chartData} fill={colors[0]} />
                                </ScatterChart>
                            </ResponsiveContainer>
                        );
                    case 'pie':
                        // Limit pie chart data to prevent overcrowding
                        const pieData = chartData.slice(0, 8);

                        // Responsive sizing for pie/donut chart
                        const getPieRadius = () => {
                            if (isNarrow) {
                                return { innerRadius: 30, outerRadius: 50 };
                            }
                            if (width < 640) {
                                return { innerRadius: 40, outerRadius: 60 };
                            }
                            return { innerRadius: 50, outerRadius: 75 };
                        };

                        const { innerRadius, outerRadius } = getPieRadius();

                        // Adjust vertical position for narrow containers
                        const cyPosition = isNarrow ? '50%' : '45%';

                        // Responsive font sizes
                        const labelFontSize = isNarrow ? '9px' : width < 640 ? '10px' : '11px';
                        const legendFontSize = isNarrow ? '9px' : width < 640 ? '10px' : '11px';

                        return (
                            <ResponsiveContainer width="100%" height={getChartHeight(300)}>
                                <PieChart>
                                    <Pie
                                        data={pieData}
                                        cx="50%"
                                        cy={cyPosition}
                                        innerRadius={innerRadius}
                                        outerRadius={outerRadius}
                                        paddingAngle={3}
                                        dataKey={actualYKey}
                                        nameKey={actualXKey}
                                        label={({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
                                            const RADIAN = Math.PI / 180;
                                            const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
                                            const x = cx + radius * Math.cos(-midAngle * RADIAN);
                                            const y = cy + radius * Math.sin(-midAngle * RADIAN);

                                            // Only show label if slice is > 5% to avoid clutter
                                            if (percent < 0.05) return null;

                                            return (
                                                <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={labelFontSize} fontWeight="700">
                                                    {`${(percent * 100).toFixed(0)}%`}
                                                </text>
                                            );
                                        }}
                                        labelLine={false}
                                    >
                                        {pieData.map((entry, idx) => (
                                            <Cell key={`cell-${idx}`} fill={COLORS[idx % COLORS.length]} />
                                        ))}
                                    </Pie>
                                    <Tooltip
                                        contentStyle={{
                                            borderRadius: '12px',
                                            border: 'none',
                                            boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
                                            padding: isNarrow ? '8px' : '12px',
                                            fontSize: isNarrow ? '10px' : '12px'
                                        }}
                                        formatter={(value) => typeof value === 'number' ? value.toLocaleString() : value}
                                    />
                                    <Legend
                                        layout="horizontal"
                                        verticalAlign="bottom"
                                        align="center"
                                        iconType="circle"
                                        iconSize={isNarrow ? 8 : 10}
                                        wrapperStyle={{
                                            fontSize: legendFontSize,
                                            paddingTop: isNarrow ? "5px" : "10px",
                                            lineHeight: isNarrow ? "14px" : "16px",
                                            width: "100%",
                                            display: "flex",
                                            flexWrap: "wrap",
                                            justifyContent: "center",
                                            gap: isNarrow ? "8px" : "12px"
                                        }}
                                    />
                                </PieChart>
                            </ResponsiveContainer>
                        );
                    default:
                        console.warn('InsightPanel: Unknown chart type', { chart_type, rechartsType });
                        // Fallback to bar chart for unknown types
                        return (
                            <ResponsiveContainer width="100%" height={getChartHeight(320)}>
                                <BarChart data={chartData} margin={{ bottom: 60 }}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <XAxis dataKey={actualXKey} hide={chartData.length > 20} tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                                    <YAxis tick={{ fontSize: 11 }} />
                                    <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                                    <Legend iconType="circle" />
                                    <Bar dataKey={actualYKey} fill={colors[0]} radius={[4, 4, 0, 0]} name={title} />
                                </BarChart>
                            </ResponsiveContainer>
                        );
                }
            } catch (error) {
                console.error('InsightPanel: Chart rendering error', { error, chartConfig, chartData });
                return (
                    <div className="text-center py-8 text-red-400 text-sm">
                        <div>Chart rendering failed</div>
                        <div className="text-xs text-slate-400 mt-1">{error.message}</div>
                    </div>
                );
            }
        };

        // Debug logging for development
        if (process.env.NODE_ENV === 'development') {
            console.log('InsightPanel: Rendering chart', {
                title,
                chart_type,
                rechartsType,
                enhanced,
                dataPoints: chartData.length,
                keys: { actualXKey, actualYKey },
                colors: colors.slice(0, 3),
                hasMultiSeries: !!(series_by || group_by)
            });
        }

        return (
            <div key={index} className={`bg-white rounded-lg ${isNarrow ? 'p-2' : 'p-3'} border shadow-sm ${enhanced ? 'border-brand-navy/30 bg-gradient-to-br from-white to-blue-50/30' : 'border-slate-100'}`}>
                <div className={`${isNarrow ? 'mb-1' : 'mb-2'}`}>
                    <div className={`flex items-start justify-between ${isNarrow ? 'mb-0.5' : 'mb-1'}`}>
                        <h4 className={`${isNarrow ? 'text-[10px]' : 'text-xs'} font-semibold text-slate-700 pl-1 border-l-2 border-brand-navy`}>{title}</h4>
                        <div className="flex items-center gap-1">
                            {enhanced && <span className={`${isNarrow ? 'text-[9px] px-1.5 py-0.5' : 'text-xs px-2 py-0.5'} bg-blue-100 text-brand-navy rounded-full font-medium`}>Enhanced</span>}
                            {(series_by || group_by) && <span className={`${isNarrow ? 'text-[9px] px-1.5 py-0.5' : 'text-xs px-2 py-0.5'} bg-blue-100 text-blue-700 rounded-full font-medium`}>Multi-Series</span>}
                        </div>
                    </div>
                    {subtitle && <p className={`${isNarrow ? 'text-[10px]' : 'text-xs'} text-brand-navy font-medium ${isNarrow ? 'mb-0.5' : 'mb-1'} pl-1`}>{subtitle}</p>}
                </div>
                <ChartComponent />
                {description && <p className={`${isNarrow ? 'text-[9px] mt-2' : 'text-[10px] mt-4'} text-slate-500 italic`}>{description}</p>}
                {category_insights && category_insights.length > 0 && (
                    <div className="mt-3 pt-2 border-t border-slate-100">
                        <h5 className="text-xs font-semibold text-slate-600 mb-1">Key Insights</h5>
                        <ul className="space-y-1">
                            {category_insights.slice(0, 3).map((insight, i) => (
                                <li key={i} className="text-xs text-slate-600 flex items-start gap-1">
                                    <span className="text-brand-navy mt-0.5">-</span>
                                    <span>{insight}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className="bg-white rounded-xl border border-blue-100 shadow-sm mt-4 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="bg-gradient-to-r from-slate-50 to-white px-4 py-3 border-b border-slate-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Lightbulb className="text-amber-500" size={18} />
                    <h3 className="font-semibold text-slate-800 text-sm">AI Insights</h3>
                </div>
                <span className="text-[10px] bg-blue-100 text-brand-navy px-2 py-0.5 rounded-full font-medium">{charts.length} visualizations</span>
            </div>

            <div className="p-4 bg-slate-50/50">
                <div className="max-h-[600px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {charts.map((chart, idx) => renderSingleChart(chart, idx))}
                    </div>
                </div>

                {/* Analysis summary card hidden per user request */}
            </div>
        </div>
    );
});

export default InsightPanel;
