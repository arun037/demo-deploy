import React, { useState, useEffect, useRef, useMemo, Suspense, lazy } from 'react';
import {
    BarChart3, TrendingUp, Users, DollarSign, Package, AlertCircle,
    RefreshCw, ArrowUpRight, ArrowDownRight, Loader2, PieChart as PieChartIcon,
    Pencil, Check, X, Activity, Layers, Info, FileCode, Target, Globe,
    Clock, Copy, Map, Filter, AlertTriangle, PauseCircle, ChevronDown,
    RotateCcw
} from 'lucide-react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer, BarChart, Bar, PieChart as RechartsPieChart,
    Pie, Cell, Legend, AreaChart, Area
} from 'recharts';
import SqlViewerModal from '../components/SqlViewerModal';
import { config } from '../config.js';

// ─── Lazy-load Plotly ─────────────────────────────────────────────────────────
const Plot = lazy(() => import('react-plotly.js'));

// ─── Period options ───────────────────────────────────────────────────────────
const PERIOD_OPTIONS = [
    { value: '7d',  label: 'Last 7 Days',    short: '7D'  },
    { value: '30d', label: 'Last 30 Days',   short: '30D' },
    { value: '3m',  label: 'Last 3 Months',  short: '3M'  },
    { value: '6m',  label: 'Last 6 Months',  short: '6M'  },
    { value: '12m', label: 'Last 12 Months', short: '12M' },
    { value: 'all', label: 'All Time',       short: 'All' },
];

// ─── Brand colors ─────────────────────────────────────────────────────────────
const BRAND_COLORS = [
    '#3b82f6', '#8b5cf6', '#10b981', '#f59e0b',
    '#ef4444', '#ec4899', '#06b6d4', '#f97316',
];

// ─── API ──────────────────────────────────────────────────────────────────────
const fetchConfig       = async () => (await fetch(`${config.API.DASHBOARD_ENDPOINT}/config`)).json();
const regenerateDashboard = async () => (await fetch(`${config.API.DASHBOARD_ENDPOINT}/regenerate`, { method: 'POST' })).json();
const fetchInsightData  = async (id, period, extraFilters = {}) => {
    const params = new URLSearchParams({ period, refresh: 'false' });
    // extraFilters is {param: value} — only send non-"all" values
    Object.entries(extraFilters).forEach(([k, v]) => { if (v && v !== 'all') params.set(k, v); });
    const res = await fetch(`${config.API.DASHBOARD_ENDPOINT}/data/${id}?${params}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
};
const patchInsightTitle = async (id, title) => (await fetch(`${config.API.DASHBOARD_ENDPOINT}/insight/${id}/title`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title })
})).json();

// ─── Formatters ───────────────────────────────────────────────────────────────
const fmtValue = (v, fmt) => {
    if (v === null || v === undefined) return '—';
    const n = Number(v);
    if (isNaN(n)) return String(v);
    if (fmt === 'currency') {
        if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
        if (n >= 1_000)     return `$${(n / 1_000).toFixed(1)}K`;
        return `$${n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
    }
    if (fmt === 'percentage') return `${n.toFixed(1)}%`;
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`;
    return n.toLocaleString();
};

// ─── Icon map ─────────────────────────────────────────────────────────────────
const ICONS = {
    'dollar-sign': DollarSign, 'users': Users, 'package': Package,
    'trending-up': TrendingUp, 'alert-circle': AlertCircle,
    'bar-chart': BarChart3, 'bar-chart-3': BarChart3, 'pie-chart': PieChartIcon,
    'activity': Activity, 'layers': Layers, 'target': Target, 'globe': Globe,
    'clock': Clock, 'copy': Copy, 'map': Map, 'filter': Filter,
    'alert-triangle': AlertTriangle, 'pause-circle': PauseCircle, 'file-text': FileCode,
};
const getIcon = (name) => ICONS[name] || BarChart3;

// ─── Accent colors from hex ───────────────────────────────────────────────────
const ACCENT = {
    '#10b981': { bg: 'bg-emerald-50', ring: 'bg-emerald-500', text: 'text-emerald-600' },
    '#3b82f6': { bg: 'bg-blue-50',    ring: 'bg-blue-500',    text: 'text-blue-600'    },
    '#8b5cf6': { bg: 'bg-violet-50',  ring: 'bg-violet-500',  text: 'text-violet-600'  },
    '#f59e0b': { bg: 'bg-amber-50',   ring: 'bg-amber-500',   text: 'text-amber-600'   },
    '#ef4444': { bg: 'bg-red-50',     ring: 'bg-red-500',     text: 'text-red-600'     },
    '#ec4899': { bg: 'bg-pink-50',    ring: 'bg-pink-500',    text: 'text-pink-600'    },
    '#06b6d4': { bg: 'bg-cyan-50',    ring: 'bg-cyan-500',    text: 'text-cyan-600'    },
    '#f97316': { bg: 'bg-orange-50',  ring: 'bg-orange-500',  text: 'text-orange-600'  },
    '#94a3b8': { bg: 'bg-slate-50',   ring: 'bg-slate-400',   text: 'text-slate-600'   },
};
const accent = (hex) => ACCENT[hex] || { bg: 'bg-indigo-50', ring: 'bg-indigo-500', text: 'text-indigo-600' };

const TOOLTIP_STYLE = {
    contentStyle: {
        borderRadius: '10px', border: '1px solid #e2e8f0',
        boxShadow: '0 10px 25px -5px rgba(0,0,0,.1)',
        fontSize: '12px', padding: '8px 12px',
    },
};

const PLOTLY_LAYOUT = {
    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    font: { family: 'Inter,system-ui,sans-serif', size: 11, color: '#64748b' },
    margin: { t: 16, r: 16, b: 52, l: 64 },
    showlegend: false,
    autosize: true,
    xaxis: { automargin: true },
    yaxis: { automargin: true },
};
const PLOTLY_CFG = { displayModeBar: false, responsive: true };

// ─── Pivot [{period, series, value}] → [{period, A:n, B:n}] ─────────────────
const pivotRows = (rows, pk, sk, vk) => {
    if (!rows?.length || !sk || !pk || !vk) return { pivoted: [], series: [] };
    
    // Get unique series values, filter out empty/null
    const series = [...new Set(rows.map(r => String(r[sk] ?? '').trim()).filter(s => s))];
    if (!series.length) return { pivoted: [], series: [] };
    
    // Group by period
    const byPeriod = {};
    rows.forEach(r => {
        const p = String(r[pk] ?? '').trim();
        const s = String(r[sk] ?? '').trim();
        const v = Number(r[vk]) || 0;
        
        if (!p || !s) return; // Skip invalid rows
        
        if (!byPeriod[p]) {
            byPeriod[p] = { _p: p };
            // Initialize all series to 0 for this period
            series.forEach(ser => { byPeriod[p][ser] = 0; });
        }
        byPeriod[p][s] = v;
    });
    
    // Convert to array and sort by period
    const pivoted = Object.values(byPeriod)
        .filter(p => p._p) // Remove empty periods
        .sort((a, b) => {
            // Try numeric sort first, then string
            const aNum = Number(a._p);
            const bNum = Number(b._p);
            if (!isNaN(aNum) && !isNaN(bNum)) return aNum - bNum;
            return String(a._p).localeCompare(String(b._p));
        });
    
    return { pivoted, series: series.filter(s => s) };
};

// ─── Normalize to [{label, value}] ───────────────────────────────────────────
const normalize = (rows) => {
    if (!rows?.length) return [];
    const r0 = rows[0];
    const keys = Object.keys(r0);
    const SKIP = new Set(['period', 'category', 'label', 'name', 'site', 'lead_status']);
    const axisKey = ['period', 'category', 'label', 'name', 'site', 'lead_status'].find(k => k in r0) || keys[0];
    const valKey  = keys.find(k => !SKIP.has(k)) || keys[keys.length - 1] || 'total';
    return rows.map(r => ({ label: r[axisKey] ?? '', value: Number(r[valKey]) || 0 }));
};

// ─── EditableTitle ────────────────────────────────────────────────────────────
const EditableTitle = ({ insightId, title: initTitle, className, onSave }) => {
    const [editing, setEditing] = useState(false);
    const [val, setVal]         = useState(initTitle);
    const [saving, setSaving]   = useState(false);
    const ref = useRef(null);
    useEffect(() => { if (editing) ref.current?.focus(); }, [editing]);

    const save = async () => {
        if (!val.trim() || val === initTitle) { setVal(initTitle); setEditing(false); return; }
        setSaving(true);
        try { const r = await patchInsightTitle(insightId, val.trim()); if (r.success) { setEditing(false); onSave?.(val.trim()); } }
        catch { setVal(initTitle); }
        finally { setSaving(false); }
    };

    if (editing) return (
        <div className="flex items-center gap-1">
            <input ref={ref} value={val} onChange={e => setVal(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') { setVal(initTitle); setEditing(false); } }}
                className={`${className} border border-blue-300 rounded px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-blue-400`}
                disabled={saving} />
            <button onClick={save} disabled={saving} className="p-1 rounded text-emerald-600 hover:bg-emerald-50"><Check size={13} /></button>
            <button onClick={() => { setVal(initTitle); setEditing(false); }} className="p-1 rounded text-red-500 hover:bg-red-50"><X size={13} /></button>
        </div>
    );
    return (
        <div className="flex items-center gap-1 group/title">
            <span className={className}>{val}</span>
            <button onClick={() => setEditing(true)} className="opacity-0 group-hover/title:opacity-100 p-0.5 rounded text-slate-300 hover:text-slate-500 transition-opacity"><Pencil size={11} /></button>
        </div>
    );
};

// ─── Tooltip icon ─────────────────────────────────────────────────────────────
const Tip = ({ text }) => {
    if (!text) return null;
    return (
        <div className="relative group/tip inline-flex">
            <Info size={13} className="text-slate-300 hover:text-slate-400 cursor-help" />
            <div className="pointer-events-none absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-52 px-3 py-2 bg-slate-800 text-white text-xs rounded-lg shadow-xl opacity-0 invisible group-hover/tip:opacity-100 group-hover/tip:visible transition-all z-50 text-center">
                {text}
                <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800" />
            </div>
        </div>
    );
};

// ─── Per-card period selector ─────────────────────────────────────────────────
const PeriodPill = ({ value, defaultValue = 'all', onChange, supportsFilter }) => {
    const isChanged = value !== defaultValue;
    if (!supportsFilter) return (
        <span className="inline-flex items-center text-[10px] text-slate-400 bg-slate-100 px-2 py-1 rounded-lg gap-1">
            <Clock size={9} />All time
        </span>
    );
    return (
        <label className={`relative inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium border cursor-pointer transition-all select-none overflow-hidden
            ${isChanged ? 'border-blue-300 bg-blue-50 text-blue-700' : 'border-slate-200 bg-slate-50 text-slate-500 hover:bg-white hover:border-slate-300'}`}
            title="Change time period for this card">
            <Clock size={9} className="shrink-0 pointer-events-none" />
            <span className="pointer-events-none">{PERIOD_OPTIONS.find(o => o.value === value)?.short ?? value}</span>
            <ChevronDown size={9} className="shrink-0 pointer-events-none" />
            {isChanged && (
                <button onClick={e => { e.preventDefault(); e.stopPropagation(); onChange(defaultValue); }}
                    className="ml-0.5 text-blue-400 hover:text-blue-600 pointer-events-auto z-10" title="Reset to default">
                    <RotateCcw size={9} />
                </button>
            )}
            <select value={value} onChange={e => onChange(e.target.value)}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer">
                {PERIOD_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
        </label>
    );
};

// ─── Card shell ───────────────────────────────────────────────────────────────
const Card = ({ children, className = '' }) => (
    <div className={`bg-white rounded-2xl border border-slate-100 shadow-sm hover:shadow-md transition-shadow flex flex-col ${className}`}>
        {children}
    </div>
);

// ─── Card header bar ──────────────────────────────────────────────────────────
const CardHead = ({ insight, currentTitle, onSave, onViewSql, period, onPeriodChange,
                    resolvedFilters, dimFilters, onDimChange }) => {
    const supportsFilter = insight.filter_metadata?.supports_time_filter !== false;
    const defaultPeriod  = 'all';
    const activeFilterCount = (resolvedFilters || []).filter(rf => dimFilters?.[rf.param] && dimFilters[rf.param] !== 'all').length
        + (period !== defaultPeriod ? 1 : 0);

    return (
        <div className="px-4 pt-4 pb-2">
            {/* Row 1: title + actions */}
            <div className="flex items-start gap-2 mb-2">
                <div className="flex items-start gap-1.5 flex-1 min-w-0">
                    <EditableTitle insightId={insight.id} title={currentTitle}
                        className="text-[12px] sm:text-[13px] font-semibold text-slate-700 leading-tight break-words line-clamp-2"
                        onSave={onSave} />
                    <Tip text={insight.description} />
                </div>
                <div className="flex items-center gap-0.5 shrink-0">
                    {activeFilterCount > 0 && (
                        <span className="text-[9px] font-bold bg-indigo-500 text-white rounded-full w-4 h-4 flex items-center justify-center" title={`${activeFilterCount} active filter${activeFilterCount>1?'s':''}`}>
                            {activeFilterCount}
                        </span>
                    )}
                    <button onClick={() => onViewSql(insight)} title="View SQL"
                        className="p-1 text-slate-300 hover:text-blue-400 transition-colors rounded">
                        <FileCode size={12} />
                    </button>
                </div>
            </div>
            {/* Row 2: filter pills */}
            <div className="flex items-center gap-1.5 flex-wrap">
                <PeriodPill value={period} defaultValue={defaultPeriod}
                    onChange={onPeriodChange} supportsFilter={supportsFilter} />
                {resolvedFilters && resolvedFilters.map(rf => (
                    <DimFilterPill key={rf.param} filterRef={rf.filterRef} filterDef={rf}
                        value={dimFilters?.[rf.param] || 'all'}
                        onChange={(v) => onDimChange(rf.param, v)} />
                ))}
            </div>
        </div>
    );
};

// ─── Skeleton loader ──────────────────────────────────────────────────────────
const Skeleton = ({ h = 'h-40' }) => (
    <div className={`${h} w-full rounded-xl bg-slate-100 animate-pulse`} />
);

// ─── Dimensional filter pill (site, category, status …) ──────────────────────
const DIM_ICONS = {
    site:          Globe,
    lead_status:   Activity,
    lead_category: Layers,
    lead_source:   TrendingUp,
};
const DimFilterPill = ({ filterRef, filterDef, value, onChange }) => {
    if (!filterDef) return null;
    const isActive = value && value !== 'all';
    const Icon = DIM_ICONS[filterRef] || Filter;
    const selectedLabel = filterDef.options.find(o => o.value === value)?.label || filterDef.label;
    return (
        <label className={`relative inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium border cursor-pointer transition-all select-none overflow-hidden
            ${isActive
                ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
                : 'border-slate-200 bg-slate-50 text-slate-500 hover:bg-white hover:border-slate-300'}`}
            title={`Filter by ${filterDef.label}`}>
            <Icon size={9} className="shrink-0 pointer-events-none" />
            <span className="pointer-events-none max-w-[68px] truncate">{isActive ? selectedLabel : filterDef.label}</span>
            <ChevronDown size={9} className="shrink-0 pointer-events-none" />
            <select value={value} onChange={e => onChange(e.target.value)}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer">
                {filterDef.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
        </label>
    );
};

// ─── Main DashboardCard ───────────────────────────────────────────────────────
const DashboardCard = ({ insight, onViewSql, filterDefs = {} }) => {
    // Default period per card — cards that don't support time filter use 'all'
    const supportsTime = insight.filter_metadata?.supports_time_filter !== false;
    const [period,     setPeriod]     = useState('all');
    const [dimFilters, setDimFilters] = useState({});
    const [data,    setData]    = useState(null);
    const [loading, setLoading] = useState(true);
    const [error,   setError]   = useState(null);
    const [title,   setTitle]   = useState(insight.title);

    // Resolve which card_filters this insight has, with their full definitions + filterRef key
    const resolvedFilters = useMemo(() => {
        return (insight.card_filters || []).map(cf => {
            const def = cf.filter_ref ? filterDefs[cf.filter_ref] : null;
            return def ? { ...def, filterRef: cf.filter_ref, sql_fragment: cf.sql_fragment } : null;
        }).filter(Boolean);
    }, [insight.card_filters, filterDefs]);

    const load = async (p, df) => {
        try {
            setLoading(true); setError(null);
            const extras = {};
            resolvedFilters.forEach(rf => {
                const v = df[rf.param] || 'all';
                if (v !== 'all') extras[rf.param] = v;
            });
            const res = await fetchInsightData(insight.id, p, extras);
            if (res.success) setData(res.data);
            else setError('No data');
        } catch (e) { setError(e.message); }
        finally { setLoading(false); }
    };

    // Reload whenever this card's own period or dim filters change
    useEffect(() => { load(period, dimFilters); }, [period, dimFilters]);

    const handlePeriodChange = (p) => { setPeriod(p); };

    const handleDimChange = (param, value) => {
        setDimFilters(prev => ({ ...prev, [param]: value }));
    };

    const rows = data?.rows || [];
    const chartType = insight.chart_type || insight.viz_type || 'bar';
    const color     = insight.color || '#3b82f6';
    const ac        = accent(color);

    // ── Mobile detection for responsive charts ──────────────────────────────────
    const [isMobile, setIsMobile] = useState(window.innerWidth < 640);
    useEffect(() => {
        const handleResize = () => setIsMobile(window.innerWidth < 640);
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    const headProps = {
        insight, currentTitle: title, onSave: setTitle, onViewSql,
        period, onPeriodChange: handlePeriodChange,
        resolvedFilters, dimFilters, onDimChange: handleDimChange,
    };

    // ── Loading ───────────────────────────────────────────────────────────────
    if (loading) return (
        <Card className="p-5 min-h-[160px] justify-center items-center gap-2">
            <Loader2 size={22} className="animate-spin text-blue-400" />
            <span className="text-xs text-slate-400">Loading...</span>
        </Card>
    );

    // ── Error / empty ─────────────────────────────────────────────────────────
    if (error || !data) return (
        <Card className="flex flex-col min-h-[160px]">
            <CardHead {...headProps} />
            <div className="flex-1 flex flex-col items-center justify-center gap-2 pb-5">
                <AlertCircle size={20} className="text-slate-300" />
                <span className="text-xs text-slate-400">{error || 'No data available'}</span>
            </div>
        </Card>
    );

    // ── No rows (but request succeeded) ─────────────────────────────────────
    if (!rows.length && insight.category !== 'kpi') return (
        <Card className="flex flex-col min-h-[160px]">
            <CardHead {...headProps} />
            <div className="flex-1 flex flex-col items-center justify-center gap-2 pb-5">
                <AlertCircle size={18} className="text-slate-200" />
                <span className="text-xs text-slate-400">No data for this period — try a wider range</span>
            </div>
        </Card>
    );

    // ════════════════════════════════════════════════════════════════════════
    // 1 ─ KPI Card
    // ════════════════════════════════════════════════════════════════════════
    if (insight.category === 'kpi' || insight.viz_type === 'kpi_card') {
        const row0 = rows[0] || {};
        const SKIP = new Set(['period', 'category', 'label', 'name', 'site', 'lead_status']);
        const vk   = Object.keys(row0).find(k => !SKIP.has(k)) || Object.keys(row0)[0] || 'total';
        const raw  = row0[vk];
        const comp = data?.comparison;
        const Icon = getIcon(insight.icon);

        return (
            <Card>
                {/* color accent bar */}
                <div className="h-1 rounded-t-2xl" style={{ background: color }} />
                <CardHead {...headProps} />
                {/* Value + icon row */}
                <div className="flex items-end justify-between px-4 pt-2 pb-4 gap-3">
                    <div className="min-w-0 flex-1">
                        <div className="text-xl sm:text-2xl lg:text-3xl font-bold text-slate-800 tabular-nums leading-tight break-all">
                            {fmtValue(raw, insight.format)}
                        </div>
                        {comp && (
                            <div className="flex items-center gap-1 mt-1">
                                {comp.trend === 'up'
                                    ? <ArrowUpRight size={13} className="text-emerald-500" />
                                    : <ArrowDownRight size={13} className="text-red-500" />}
                                <span className={`text-xs font-medium ${comp.trend === 'up' ? 'text-emerald-600' : 'text-red-500'}`}>
                                    {Math.abs(comp.change_percent)}%
                                </span>
                                <span className="text-[11px] text-slate-400">vs prev</span>
                            </div>
                        )}
                    </div>
                    <div className={`shrink-0 p-2 sm:p-2.5 rounded-xl ${ac.bg} flex-shrink-0`}>
                        <Icon size={16} className={`${ac.text} sm:w-5 sm:h-5`} />
                    </div>
                </div>
            </Card>
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    // 2 ─ Gauge (Plotly)
    // ════════════════════════════════════════════════════════════════════════
    if (chartType === 'gauge') {
        const r0  = rows[0] || {};
        const val = Number(Object.values(r0)[0]) || 0;
        const max = insight.visual_config?.max_value || 100;
        const traces = [{
            type: 'indicator', mode: 'gauge+number',
            value: Math.min(val, max * 1.5), // cap display
            gauge: {
                axis: { range: [0, max], tickcolor: '#94a3b8', tickwidth: 1 },
                bar:  { color, thickness: 0.25 },
                bgcolor: 'white', borderwidth: 0,
                steps: [
                    { range: [0, max * 0.4],  color: '#dcfce7' },
                    { range: [max * 0.4, max * 0.7], color: '#fef9c3' },
                    { range: [max * 0.7, max],        color: '#fee2e2' },
                ],
                threshold: { line: { color: '#ef4444', width: 3 }, thickness: 0.75, value: max * 0.8 }
            },
            number: { suffix: insight.format === 'percentage' ? '%' : '', font: { size: 32, color: '#1e293b' } }
        }];
        return (
            <Card>
                <CardHead {...headProps} />
                <div className="px-2 pb-3">
                    <Suspense fallback={<Skeleton />}>
                        <Plot data={traces}
                            layout={{ ...PLOTLY_LAYOUT, height: 200, margin: { t: 20, r: 16, b: 10, l: 16 } }}
                            config={PLOTLY_CFG} style={{ width: '100%' }} />
                    </Suspense>
                </div>
            </Card>
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    // 3 ─ Treemap (Plotly)
    // ════════════════════════════════════════════════════════════════════════
    if (chartType === 'treemap') {
        const labels = rows.map(r => r.category ?? r.label ?? r.name ?? '');
        const values = rows.map(r => Number(r.total ?? r.value ?? r.revenue ?? 0));
        const traces = [{
            type: 'treemap',
            labels, parents: labels.map(() => ''), values,
            textinfo: 'label+value+percent root',
            textfont: { size: isMobile ? 9 : 11 },
            marker: { colorscale: 'Blues', showscale: false },
        }];
        return (
            <Card>
                <CardHead {...headProps} />
                <div className="px-2 pb-3">
                    <Suspense fallback={<Skeleton h="h-64" />}>
                        <Plot data={traces}
                            layout={{ ...PLOTLY_LAYOUT, height: isMobile ? 250 : 300, margin: { t: 10, r: 4, b: 4, l: 4 } }}
                            config={PLOTLY_CFG} style={{ width: '100%' }} />
                    </Suspense>
                </div>
            </Card>
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    // 4 ─ Heatmap (Plotly)
    // ════════════════════════════════════════════════════════════════════════
    if (chartType === 'heatmap') {
        const xk = insight.visual_config?.x_key || 'period';
        const yk = insight.visual_config?.y_key || 'site';
        const zk = insight.visual_config?.z_key || 'total';
        const xs = [...new Set(rows.map(r => r[xk] ?? ''))];
        const ys = [...new Set(rows.map(r => r[yk] ?? ''))];
        const zMatrix = ys.map(yv => xs.map(xv => {
            const f = rows.find(r => r[xk] === xv && r[yk] === yv);
            return f ? (Number(f[zk]) || 0) : 0;
        }));
        // Responsive margins and sizing for mobile
        const heatmapHeight = isMobile ? 280 : 320;
        const heatmapMargins = isMobile 
            ? { t: 15, r: 50, b: 80, l: 90 }  // Reduced margins for mobile
            : { t: 20, r: 100, b: 70, l: 180 };
        const textSize = isMobile ? 8 : 10;
        const tickSize = isMobile ? 9 : 11;
        return (
            <Card>
                <CardHead {...headProps} />
                <div className="px-2 pb-3">
                    <div className="max-h-[500px] max-w-full overflow-y-auto overflow-x-auto pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                        <div className="min-w-max">
                            <Suspense fallback={<Skeleton h="h-64" />}>
                                <Plot data={[{ type: 'heatmap', z: zMatrix, x: xs, y: ys, colorscale: 'Blues', showscale: true, 
                                    text: zMatrix.map((row, i) => row.map(v => v > 0 ? v.toLocaleString() : '')),
                                    texttemplate: '%{text}', textfont: { size: textSize }, hovertext: zMatrix }]}
                                    layout={{
                                        ...PLOTLY_LAYOUT, height: heatmapHeight,
                                        margin: heatmapMargins,
                                        yaxis: { 
                                            automargin: true, 
                                            tickfont: { size: tickSize },
                                            tickmode: 'linear',
                                            tickangle: 0,
                                            side: 'left',
                                        },
                                        xaxis: { 
                                            automargin: true, 
                                            tickangle: isMobile ? -45 : -35, 
                                            tickfont: { size: textSize },
                                            side: 'bottom',
                                        },
                                    }}
                                    config={PLOTLY_CFG} style={{ width: '100%', minWidth: '600px' }} />
                            </Suspense>
                        </div>
                    </div>
                </div>
            </Card>
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    // 5 ─ Funnel (Plotly)
    // ════════════════════════════════════════════════════════════════════════
    if (chartType === 'funnel_chart') {
        const lbls = rows.map(r => r.category ?? r.label ?? r.name ?? '');
        const vals = rows.map(r => Number(r.total ?? r.value ?? 0));
        return (
            <Card>
                <CardHead {...headProps} />
                <div className="px-2 pb-3">
                    <Suspense fallback={<Skeleton h="h-64" />}>
                        <Plot
                            data={[{ type: 'funnel', y: lbls, x: vals, textinfo: 'value+percent initial', textposition: 'inside', marker: { color: BRAND_COLORS.slice(0, lbls.length) }, connector: { line: { color: '#e2e8f0', width: 2 } } }]}
                            layout={{ ...PLOTLY_LAYOUT, height: 340, margin: { t: 10, r: 90, b: 10, l: 140 } }}
                            config={PLOTLY_CFG} style={{ width: '100%' }} />
                    </Suspense>
                </div>
            </Card>
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    // 6 ─ Waterfall (Plotly)
    // ════════════════════════════════════════════════════════════════════════
    if (chartType === 'waterfall_chart') {
        if (!rows.length) {
            return (
                <Card className="flex flex-col min-h-[160px]">
                    <CardHead {...headProps} />
                    <div className="flex-1 flex flex-col items-center justify-center gap-2 pb-5">
                        <AlertCircle size={18} className="text-slate-200" />
                        <span className="text-xs text-slate-400">No data for this period — try a wider range</span>
                    </div>
                </Card>
            );
        }

        const xk = insight.visual_config?.x_key || 'period';
        const yk = insight.visual_config?.y_key || 'total';
        const lbls = rows.map(r => String(r[xk] ?? '').slice(0, 15));
        const vals = rows.map(r => Number(r[yk]) || 0);

        // Plotly waterfall needs 'measure' array: 'relative' for changes, 'total' for cumulative
        // For revenue waterfall, all values are 'relative' (monthly changes)
        const measures = new Array(vals.length).fill('relative');

        return (
            <Card>
                <CardHead {...headProps} />
                <div className="px-2 pb-3">
                    <Suspense fallback={<Skeleton h="h-64" />}>
                        <Plot
                            data={[{
                                type: 'waterfall',
                                orientation: 'v',
                                x: lbls,
                                y: vals,
                                measure: measures,
                                connector: { line: { color: '#cbd5e1', width: 1.5 } },
                                increasing: { marker: { color: '#10b981', line: { color: '#059669', width: 1 } } },
                                decreasing: { marker: { color: '#ef4444', line: { color: '#dc2626', width: 1 } } },
                                totals: { marker: { color: '#3b82f6', line: { color: '#2563eb', width: 1 } } },
                                textposition: 'outside',
                                textfont: { size: 10 },
                                texttemplate: '%{y:$,.0f}',
                                hovertemplate: '<b>%{x}</b><br>%{y:$,.2f}<extra></extra>',
                            }]}
                            layout={{
                                ...PLOTLY_LAYOUT, height: 340,
                                margin: { t: 20, r: 20, b: 70, l: 70 },
                                xaxis: { 
                                    automargin: true, 
                                    tickangle: -30, 
                                    tickfont: { size: 10 },
                                    title: { text: xk, font: { size: 11 } }
                                },
                                yaxis: { 
                                    automargin: true,
                                    tickfont: { size: 10 },
                                    title: { text: yk === 'total' ? 'Revenue' : yk, font: { size: 11 } },
                                    tickformat: '$,.0f'
                                },
                            }}
                            config={PLOTLY_CFG} style={{ width: '100%' }} />
                    </Suspense>
                </div>
            </Card>
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    // 7 ─ Bubble (Plotly)
    // ════════════════════════════════════════════════════════════════════════
    if (chartType === 'bubble_chart') {
        const xk   = insight.visual_config?.x_key   || 'leads';
        const yk   = insight.visual_config?.y_key   || 'revenue';
        const sk   = insight.visual_config?.size_key || 'revenue';
        const xs   = rows.map(r => Number(r[xk]) || 0);
        const ys   = rows.map(r => Number(r[yk]) || 0);
        const szs  = rows.map(r => Number(r[sk]) || 1);
        const mxS  = Math.max(...szs, 1);
        const text = rows.map(r => r.category ?? r.label ?? r.name ?? '');
        return (
            <Card>
                <CardHead {...headProps} />
                <div className="px-2 pb-3">
                    <Suspense fallback={<Skeleton h="h-64" />}>
                        <Plot
                            data={[{
                                type: 'scatter', mode: 'markers+text',
                                x: xs, y: ys, text,
                                textposition: 'top center', textfont: { size: 10, color: '#475569' },
                                marker: {
                                    size: szs.map(s => Math.max(10, Math.sqrt(s / mxS) * 60)),
                                    color: BRAND_COLORS.slice(0, rows.length).concat(BRAND_COLORS).slice(0, rows.length),
                                    opacity: 0.78, line: { color: '#fff', width: 1.5 }
                                },
                                hovertemplate: text.map((t, i) => `<b>${t}</b><br>${xk}: ${xs[i]}<br>${yk}: ${ys[i]}<extra></extra>`)
                            }]}
                            layout={{
                                ...PLOTLY_LAYOUT, height: 340,
                                margin: { t: 20, r: 20, b: 60, l: 70 },
                                xaxis: { title: { text: xk, font: { size: 11 } }, automargin: true },
                                yaxis: { title: { text: yk, font: { size: 11 } }, automargin: true },
                            }}
                            config={PLOTLY_CFG} style={{ width: '100%' }} />
                    </Suspense>
                </div>
            </Card>
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    // 8 ─ Area / Line (Recharts)
    // ════════════════════════════════════════════════════════════════════════
    if (['area', 'area_chart', 'line', 'line_chart'].includes(chartType)) {
        const isArea  = chartType === 'area' || chartType === 'area_chart';
        const nd      = normalize(rows);
        const gradId  = `ag-${insight.id}`;
        const fmt     = (v) => fmtValue(v, insight.format);
        const tickFmt = (v) => String(v).length > 9 ? String(v).slice(0, 8) + '…' : v;

        return (
            <Card>
                <CardHead {...headProps} />
                <div className="px-3 pt-3 pb-4">
                    <div className="max-h-[400px] max-w-full overflow-y-auto overflow-x-auto pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                        <div className="min-w-max">
                            <ResponsiveContainer width="100%" height={260} minWidth={600}>
                        {isArea ? (
                            <AreaChart data={nd} margin={{ top: 4, right: 6, bottom: 20, left: 4 }}>
                                <defs>
                                    <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%"  stopColor={color} stopOpacity={0.22} />
                                        <stop offset="95%" stopColor={color} stopOpacity={0.02} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                <XAxis dataKey="label" tickFormatter={tickFmt} axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 10 }} dy={6} interval="preserveStartEnd" />
                                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 10 }} tickFormatter={fmt} />
                                <Tooltip {...TOOLTIP_STYLE} formatter={(v) => [fmtValue(v, insight.format), 'Value']} />
                                <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2.5} fill={`url(#${gradId})`} dot={false} activeDot={{ r: 5, fill: color }} />
                            </AreaChart>
                        ) : (
                            <LineChart data={nd} margin={{ top: 4, right: 6, bottom: 20, left: 4 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                <XAxis dataKey="label" tickFormatter={tickFmt} axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 10 }} dy={6} interval="preserveStartEnd" />
                                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 10 }} tickFormatter={fmt} />
                                <Tooltip {...TOOLTIP_STYLE} formatter={(v) => [fmtValue(v, insight.format), 'Value']} />
                                <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2.5} dot={{ fill: color, r: 3, stroke: '#fff', strokeWidth: 2 }} activeDot={{ r: 6 }} />
                            </LineChart>
                        )}
                    </ResponsiveContainer>
                        </div>
                    </div>
                </div>
            </Card>
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    // 9 ─ Multi-Line (Recharts) — detects series column automatically
    // ════════════════════════════════════════════════════════════════════════
    if (chartType === 'multi_line') {
        if (!rows.length) {
            return (
                <Card className="flex flex-col min-h-[160px]">
                    <CardHead {...headProps} />
                    <div className="flex-1 flex flex-col items-center justify-center gap-2 pb-5">
                        <AlertCircle size={18} className="text-slate-200" />
                        <span className="text-xs text-slate-400">No data for this period — try a wider range</span>
                    </div>
                </Card>
            );
        }

        const r0  = rows[0] || {};
        const ks  = Object.keys(r0);
        // Find period key - prioritize 'period', then 'label', then first column
        const pk  = ks.find(k => k.toLowerCase() === 'period' || k.toLowerCase() === 'label' || k.toLowerCase() === 'date') || ks[0];
        // Find series key - look for common series column names
        const sk  = ks.find(k => {
            if (k === pk) return false;
            const kLower = k.toLowerCase();
            return kLower === 'site' || kLower === 'category' || kLower === 'status' || kLower === 'lead_status' || 
                   kLower === 'series' || kLower === 'name' || (typeof r0[k] === 'string' && r0[k] && isNaN(Number(r0[k])));
        }) || null;
        // Find value key - first numeric column that's not period or series
        const vk  = ks.find(k => k !== pk && k !== sk && !isNaN(Number(r0[k])) && r0[k] !== null) || 
                   ks.find(k => k !== pk && k !== sk) || ks[ks.length - 1];
        const fmt = (v) => fmtValue(v, insight.format);

        let chartData, seriesNames;
        if (sk && rows.length > 0) {
            // Pivot: group by period, create columns for each series value
            const p = pivotRows(rows, pk, sk, vk);
            chartData   = p.pivoted || [];
            seriesNames = p.series || [];
            
            // Debug: log if transformation failed
            if (!chartData.length || !seriesNames.length) {
                console.warn(`[Multi-Line] Pivot failed for ${insight.id}:`, {
                    rows: rows.slice(0, 3),
                    pk, sk, vk,
                    pivoted: chartData.length,
                    series: seriesNames.length
                });
            }
        } else {
            // Fallback: use all numeric columns as series
            chartData   = rows.map(r => {
                const obj = { _p: r[pk] || '' };
                ks.forEach(k => {
                    if (k !== pk && !isNaN(Number(r[k]))) {
                        obj[k] = Number(r[k]) || 0;
                    }
                });
                return obj;
            });
            seriesNames = ks.filter(k => k !== pk && !isNaN(Number(r0[k])));
        }

        if (!chartData.length || !seriesNames.length) {
            console.error(`[Multi-Line] No chart data for ${insight.id}:`, {
                rows: rows.length,
                keys: ks,
                pk, sk, vk,
                chartData: chartData.length,
                seriesNames: seriesNames.length
            });
            return (
                <Card className="flex flex-col min-h-[160px]">
                    <CardHead {...headProps} />
                    <div className="flex-1 flex flex-col items-center justify-center gap-2 pb-5">
                        <AlertCircle size={18} className="text-slate-200" />
                        <span className="text-xs text-slate-400">Could not parse chart data — check SQL query</span>
                        <span className="text-[10px] text-slate-300 mt-1">Keys: {ks.join(', ')}</span>
                    </div>
                </Card>
            );
        }

        // Ensure we have valid data
        const xAxisKey = sk ? (chartData[0]?._p !== undefined ? '_p' : pk) : '_p';
        
        return (
            <Card>
                <CardHead {...headProps} />
                <div className="px-3 pt-3 pb-4">
                    <div className="max-h-[400px] max-w-full overflow-y-auto overflow-x-auto pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                        <div className="min-w-max">
                            <ResponsiveContainer width="100%" height={300} minWidth={800}>
                                <LineChart data={chartData} margin={{ top: 10, right: 30, bottom: 50, left: 10 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis 
                                dataKey={xAxisKey} 
                                tickFormatter={v => {
                                    const s = String(v || '');
                                    return s.length > 12 ? s.slice(0, 11) + '…' : s;
                                }} 
                                axisLine={false} 
                                tickLine={false} 
                                tick={{ fill: '#94a3b8', fontSize: 10 }} 
                                dy={6} 
                                angle={-35} 
                                textAnchor="end" 
                                height={70}
                                interval="preserveStartEnd"
                            />
                            <YAxis 
                                axisLine={false} 
                                tickLine={false} 
                                tick={{ fill: '#94a3b8', fontSize: 10 }} 
                                tickFormatter={fmt} 
                                width={65}
                            />
                            <Tooltip 
                                {...TOOLTIP_STYLE} 
                                formatter={(v, n) => {
                                    const val = Number(v) || 0;
                                    const name = String(n || '').replace(/_/g, ' ');
                                    return [fmtValue(val, insight.format), name];
                                }}
                                labelFormatter={v => `Period: ${v}`}
                            />
                            <Legend 
                                iconSize={10} 
                                wrapperStyle={{ fontSize: '11px', paddingTop: '10px', lineHeight: '1.4' }} 
                                formatter={v => {
                                    const s = String(v).replace(/_/g, ' ');
                                    return s.length > 22 ? s.slice(0, 21) + '…' : s;
                                }}
                                verticalAlign="bottom"
                                height={36}
                            />
                            {seriesNames.filter(s => s).map((s, i) => {
                                // Ensure the series key exists in the data
                                const hasData = chartData.some(d => d[s] !== undefined && d[s] !== null);
                                if (!hasData) {
                                    console.warn(`[Multi-Line] Series '${s}' has no data in chartData`, chartData[0]);
                                }
                                return (
                                    <Line 
                                        key={`${s}-${i}`} 
                                        type="monotone" 
                                        dataKey={s} 
                                        stroke={BRAND_COLORS[i % BRAND_COLORS.length]}
                                        strokeWidth={2.5} 
                                        dot={{ r: 3, fill: BRAND_COLORS[i % BRAND_COLORS.length] }} 
                                        activeDot={{ r: 6, strokeWidth: 2 }}
                                        name={String(s).replace(/_/g, ' ')}
                                        connectNulls={false}
                                    />
                                );
                            })}
                        </LineChart>
                    </ResponsiveContainer>
                        </div>
                    </div>
                </div>
            </Card>
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    // 10 ─ Pie / Donut (Recharts)
    // ════════════════════════════════════════════════════════════════════════
    if (['pie', 'pie_chart'].includes(chartType)) {
        if (!rows.length) {
            return (
                <Card className="flex flex-col min-h-[160px]">
                    <CardHead {...headProps} />
                    <div className="flex-1 flex flex-col items-center justify-center gap-2 pb-5">
                        <AlertCircle size={18} className="text-slate-200" />
                        <span className="text-xs text-slate-400">No data available — check filters</span>
                    </div>
                </Card>
            );
        }

        const r0      = rows[0] || {};
        const catK    = ['category', 'label', 'name', 'lead_status', 'site'].find(k => k in r0) || Object.keys(r0)[0];
        const valK    = Object.keys(r0).find(k => k !== catK) || 'total';
        const clrs    = insight.visual_config?.colors || BRAND_COLORS;
        const isDonut = insight.visual_config?.donut === true;
        const total   = rows.reduce((s, r) => s + (Number(r[valK]) || 0), 0);

        if (total === 0) {
            return (
                <Card className="flex flex-col min-h-[160px]">
                    <CardHead {...headProps} />
                    <div className="flex-1 flex flex-col items-center justify-center gap-2 pb-5">
                        <AlertCircle size={18} className="text-slate-200" />
                        <span className="text-xs text-slate-400">All values are zero — no data to display</span>
                    </div>
                </Card>
            );
        }

        const renderLabel = ({ cx, cy, midAngle, outerRadius, value }) => {
            if (value / total < 0.04) return null;
            const RAD = Math.PI / 180;
            const r   = outerRadius + 18;
            const x   = cx + r * Math.cos(-midAngle * RAD);
            const y   = cy + r * Math.sin(-midAngle * RAD);
            return (
                <text x={x} y={y} fill="#64748b" fontSize={10} textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central">
                    {((value / total) * 100).toFixed(1)}%
                </text>
            );
        };

        return (
            <Card>
                <CardHead {...headProps} />
                <div className="px-3 pt-2 pb-4">
                    <div className="max-h-[400px] max-w-full overflow-y-auto overflow-x-auto pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                        <div className="min-w-max">
                            <ResponsiveContainer width="100%" height={260} minWidth={400}>
                                <RechartsPieChart>
                            <Pie data={rows} dataKey={valK} nameKey={catK} cx="50%" cy="48%"
                                outerRadius={isDonut ? 88 : 100} innerRadius={isDonut ? 50 : 0}
                                labelLine={false} label={renderLabel}>
                                {rows.map((_, i) => <Cell key={i} fill={clrs[i % clrs.length]} />)}
                            </Pie>
                            <Tooltip {...TOOLTIP_STYLE} formatter={(v) => [fmtValue(v, insight.format)]} />
                            <Legend 
                                layout="horizontal"
                                verticalAlign="bottom"
                                align="center"
                                iconSize={8} 
                                iconType="circle" 
                                wrapperStyle={{ 
                                    fontSize: '11px', 
                                    width: '100%',
                                    display: 'flex',
                                    flexWrap: 'wrap',
                                    justifyContent: 'center',
                                    gap: '12px',
                                    paddingTop: '8px'
                                }}
                                formatter={v => String(v).length > 22 ? String(v).slice(0, 20) + '…' : v} 
                            />
                        </RechartsPieChart>
                    </ResponsiveContainer>
                        </div>
                    </div>
                </div>
            </Card>
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    // 11 ─ Horizontal Bar (custom ranked list)
    // ════════════════════════════════════════════════════════════════════════
    if (chartType === 'horizontal_bar') {
        const r0   = rows[0] || {};
        const catK = ['category', 'label', 'name', 'lead_status', 'site'].find(k => k in r0) || Object.keys(r0)[0];
        const valK = Object.keys(r0).find(k => k !== catK) || 'total';
        const sorted  = [...rows].sort((a, b) => (Number(b[valK]) || 0) - (Number(a[valK]) || 0));
        const maxVal  = Math.max(...sorted.map(r => Number(r[valK]) || 0), 1);
        const trunc   = (s, n = 20) => String(s ?? '').length > n ? String(s).slice(0, n) + '…' : String(s ?? '');

        return (
            <Card>
                <CardHead {...headProps} />
                <div className="px-5 pt-3 pb-5 space-y-2" style={{ maxHeight: 320, overflowY: 'auto' }}>
                    {sorted.slice(0, 15).map((r, i) => {
                        const val = Number(r[valK]) || 0;
                        const pct = (val / maxVal) * 100;
                        const c   = BRAND_COLORS[i % BRAND_COLORS.length];
                        return (
                            <div key={i} className="grid grid-cols-[auto_1fr_auto] items-center gap-3">
                                <span className="text-xs text-slate-400 w-5 text-right font-mono">{i + 1}</span>
                                <div className="flex flex-col gap-0.5">
                                    <span className="text-xs text-slate-600 font-medium leading-tight truncate" title={String(r[catK])}>{trunc(r[catK])}</span>
                                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: c }} />
                                    </div>
                                </div>
                                <span className="text-xs font-semibold text-slate-700 tabular-nums whitespace-nowrap">
                                    {fmtValue(val, insight.format)}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </Card>
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    // 12 ─ Grouped Bar (Recharts)
    // ════════════════════════════════════════════════════════════════════════
    if (chartType === 'grouped_bar') {
        const r0   = rows[0] || {};
        const ks   = Object.keys(r0);
        const catK = ['category', 'label', 'name'].find(k => k in r0) || ks[0];
        const sk   = ks.find(k => k !== catK && (typeof r0[k] === 'string' || isNaN(Number(r0[k])))) || null;
        const vk   = ks.find(k => k !== catK && k !== sk && !isNaN(Number(r0[k]))) || ks[ks.length - 1];
        const clrs = insight.visual_config?.colors || BRAND_COLORS;

        let chartData = rows;
        let barKeys   = [vk];
        if (sk) {
            const cats   = [...new Set(rows.map(r => r[catK] ?? ''))].slice(0, 10);
            const series = [...new Set(rows.map(r => r[sk]   ?? ''))].slice(0, 5);
            chartData = cats.map(cat => {
                const obj = { _cat: cat };
                series.forEach(s => {
                    const m = rows.find(r => r[catK] === cat && r[sk] === s);
                    obj[s]  = m ? Number(m[vk]) || 0 : 0;
                });
                return obj;
            });
            barKeys = series;
        }

        return (
            <Card>
                <CardHead {...headProps} />
                <div className="px-3 pt-2 pb-4">
                    <div className="max-h-[400px] max-w-full overflow-y-auto overflow-x-auto pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                        <div className="min-w-max">
                            <ResponsiveContainer width="100%" height={280} minWidth={700}>
                                <BarChart data={chartData} margin={{ top: 4, right: 6, bottom: 50, left: 4 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis dataKey={sk ? '_cat' : catK} tickFormatter={v => String(v).length > 10 ? String(v).slice(0, 9) + '…' : v}
                                axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 10 }} angle={-30} textAnchor="end" height={55} />
                            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 10 }} tickFormatter={v => fmtValue(v, insight.format)} />
                            <Tooltip {...TOOLTIP_STYLE} formatter={(v, n) => [fmtValue(v, insight.format), n]} />
                            <Legend iconSize={8} wrapperStyle={{ fontSize: '11px' }} />
                            {barKeys.map((k, i) => <Bar key={k} dataKey={k} fill={clrs[i % clrs.length]} radius={[3, 3, 0, 0]} maxBarSize={28} name={String(k).replace(/_/g, ' ')} />)}
                        </BarChart>
                    </ResponsiveContainer>
                        </div>
                    </div>
                </div>
            </Card>
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    // 13 ─ Standard Bar (Recharts)
    // ════════════════════════════════════════════════════════════════════════
    if (['bar', 'bar_chart'].includes(chartType) || insight.viz_type === 'bar_chart') {
        const r0   = rows[0] || {};
        const catK = ['category', 'label', 'name', 'lead_status', 'site', 'period'].find(k => k in r0) || Object.keys(r0)[0];
        const valK = Object.keys(r0).find(k => k !== catK) || 'total';
        const barC = insight.visual_config?.color || color;
        const gid  = `bg-${insight.id}`;

        return (
            <Card>
                <CardHead {...headProps} />
                <div className="px-3 pt-2 pb-4">
                    <div className="max-h-[400px] max-w-full overflow-y-auto overflow-x-auto pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                        <div className="min-w-max">
                            <ResponsiveContainer width="100%" height={260} minWidth={600}>
                                <BarChart data={rows} margin={{ top: 4, right: 6, bottom: 50, left: 4 }}>
                            <defs>
                                <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%"   stopColor={barC} stopOpacity={0.9} />
                                    <stop offset="100%" stopColor={barC} stopOpacity={0.45} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis dataKey={catK} tickFormatter={v => String(v).length > 10 ? String(v).slice(0, 9) + '…' : v}
                                axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 10 }} angle={-30} textAnchor="end" height={55} />
                            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 10 }} tickFormatter={v => fmtValue(v, insight.format)} />
                            <Tooltip {...TOOLTIP_STYLE} formatter={(v) => [fmtValue(v, insight.format), 'Value']} />
                            <Bar dataKey={valK} fill={`url(#${gid})`} radius={[4, 4, 0, 0]} maxBarSize={36} />
                        </BarChart>
                    </ResponsiveContainer>
                        </div>
                    </div>
                </div>
            </Card>
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    // 14 ─ Fallback table
    // ════════════════════════════════════════════════════════════════════════
    const cols = rows.length ? Object.keys(rows[0]) : [];
    return (
        <Card>
            <CardHead {...headProps} />
            <div className="flex-1 overflow-auto px-5 pb-5 pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                {rows.length > 0 ? (
                    <table className="w-full text-xs">
                        <thead className="bg-slate-50 sticky top-0">
                            <tr>{cols.map(c => <th key={c} className="px-3 py-2 text-left text-slate-500 font-medium uppercase tracking-wide whitespace-nowrap">{c}</th>)}</tr>
                        </thead>
                        <tbody>
                            {rows.slice(0, 20).map((r, i) => (
                                <tr key={i} className="border-t border-slate-50 hover:bg-slate-50/60">
                                    {cols.map(c => <td key={c} className="px-3 py-2 text-slate-700 whitespace-nowrap">{String(r[c] ?? '—')}</td>)}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : (
                    <div className="h-24 flex items-center justify-center text-slate-400 text-sm">No data</div>
                )}
            </div>
        </Card>
    );
};

// ─── Section heading ──────────────────────────────────────────────────────────
const SectionHead = ({ icon: Icon, label, ringColor, count }) => (
    <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
            <div className={`w-8 h-8 rounded-xl ${ringColor} flex items-center justify-center`}>
                <Icon size={16} className="text-white" />
            </div>
            <h2 className="text-base font-semibold text-slate-700">{label}</h2>
        </div>
        <span className="text-xs text-slate-400 tabular-nums">{count} card{count !== 1 ? 's' : ''}</span>
    </div>
);

// ─── DashboardPage ────────────────────────────────────────────────────────────
export default function DashboardPage() {
    const [loading,    setLoading]    = useState(true);
    const [dashConfig, setDashConfig] = useState(null);
    const [regen,      setRegen]      = useState(false);
    const [progress,   setProgress]   = useState('');
    const [toast,      setToast]      = useState(null);
    const [sqlInsight, setSqlInsight] = useState(null);

    const notify = (type, msg) => { setToast({ type, msg }); setTimeout(() => setToast(null), 5000); };

    useEffect(() => {
        (async () => {
            try {
                const res = await fetchConfig();
                setDashConfig(res.exists ? res.config : null);
            } catch { notify('error', 'Failed to load dashboard'); }
            finally { setLoading(false); }
        })();
    }, []);

    const handleRegen = async () => {
        if (dashConfig && !confirm('Regenerate dashboard? Current layout will be replaced.')) return;
        setRegen(true); setProgress('Initializing...');
        notify('info', 'Starting generation...');
        try {
            const res = await regenerateDashboard();
            if (!res.success) { notify('error', 'Failed to start generation'); setRegen(false); return; }
            const steps = ['Analyzing schema…', 'Planning insights…', 'Generating SQL…', 'Validating queries…'];
            let n = 0;
            const poll = setInterval(async () => {
                setProgress(steps[Math.min(Math.floor(n / 5), steps.length - 1)] + (n > 15 ? ` (${n * 3}s)` : ''));
                n++;
                try {
                    const c = await fetchConfig();
                    if (c.exists) { clearInterval(poll); setDashConfig(c.config); setRegen(false); setProgress(''); notify('success', '✓ Dashboard generated!'); }
                    else if (n >= 40) { clearInterval(poll); setRegen(false); setProgress(''); notify('warning', 'Taking long — refresh in a minute.'); }
                } catch {}
            }, 3000);
        } catch { setRegen(false); setProgress(''); notify('error', 'Generation failed.'); }
    };

    if (loading) return (
        <div className="h-full flex flex-col items-center justify-center gap-3 bg-slate-50">
            <Loader2 size={32} className="animate-spin text-blue-500" />
            <p className="text-sm text-slate-400">Loading dashboard…</p>
        </div>
    );

    if (!dashConfig) return (
        <div className="h-full flex flex-col items-center justify-center bg-slate-50 p-8">
            <div className="max-w-xs text-center space-y-5">
                <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto">
                    <BarChart3 size={28} className="text-blue-600" />
                </div>
                <div>
                    <h2 className="text-xl font-bold text-slate-800">No Dashboard Yet</h2>
                    <p className="text-sm text-slate-500 mt-1">Generate a custom AI-powered dashboard from your data.</p>
                </div>
                <button onClick={handleRegen} disabled={regen}
                    className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition font-medium shadow-lg shadow-blue-200 disabled:opacity-50">
                    {regen ? <Loader2 size={18} className="animate-spin" /> : <RefreshCw size={18} />}
                    {regen ? (progress || 'Generating…') : 'Generate Dashboard'}
                </button>
            </div>
        </div>
    );

    const kpis       = dashConfig?.insights?.filter(i => i.category === 'kpi')          || [];
    const trends     = dashConfig?.insights?.filter(i => i.category === 'trend')        || [];
    const dists      = dashConfig?.insights?.filter(i => i.category === 'distribution') || [];
    const alerts     = dashConfig?.insights?.filter(i => i.category === 'alert')        || [];
    const total      = kpis.length + trends.length + dists.length + alerts.length;
    const filterDefs = dashConfig?.filter_definitions || {};

    return (
        <div className="h-full overflow-y-auto bg-slate-50/80 pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100" style={{ WebkitOverflowScrolling: 'touch' }}>
            {/* hide scrollbar for horizontal overflow in filter strip */}
            <style>{`.no-scrollbar::-webkit-scrollbar{display:none}`}</style>

            {/* ── Toast ──────────────────────────────────────────────────────── */}
            {toast && (
                <div className={`fixed top-4 right-4 z-50 max-w-sm px-4 py-3 rounded-xl shadow-xl text-sm font-medium flex items-center gap-2
                    ${toast.type === 'success' ? 'bg-emerald-500 text-white' :
                      toast.type === 'error'   ? 'bg-red-500 text-white' :
                      toast.type === 'warning' ? 'bg-amber-500 text-white' : 'bg-blue-600 text-white'}`}>
                    {toast.msg}
                </div>
            )}

            <div className="max-w-screen-xl mx-auto px-3 sm:px-5 lg:px-8 py-4 sm:py-6 space-y-8 sm:space-y-10">

                {/* ── Header ─────────────────────────────────────────────────── */}
                <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                            <h1 className="text-lg sm:text-xl font-bold text-slate-800">
                                {dashConfig?.dashboard_metadata?.title || 'Franchise Analytics'}
                            </h1>
                            <span className="shrink-0 text-[11px] px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full font-medium">AI</span>
                        </div>
                        <p className="text-slate-400 text-xs sm:text-sm mt-0.5 line-clamp-1">
                            {dashConfig?.dashboard_metadata?.description || 'Real-time franchise performance intelligence'}
                            <span className="mx-1.5 text-slate-300">·</span>
                            <span className="text-slate-500 font-medium">{total}</span> cards · each card has its own filters
                        </p>
                    </div>
                    <button onClick={handleRegen} disabled={regen}
                        className="shrink-0 flex items-center gap-1.5 px-3 py-2 bg-white border border-slate-200 text-slate-600 rounded-xl hover:bg-slate-50 active:scale-95 transition-all shadow-sm text-sm font-medium disabled:opacity-50">
                        <RefreshCw size={14} className={regen ? 'animate-spin' : ''} />
                        <span className="hidden sm:inline">{regen ? (progress || 'Working…') : 'Regenerate'}</span>
                    </button>
                </div>

                {/* ── 1. KPIs ────────────────────────────────────────────────── */}
                {kpis.length > 0 && (
                    <section>
                        <SectionHead icon={DollarSign} label="Key Performance Indicators" ringColor="bg-emerald-500" count={kpis.length} />
                        {/* Responsive: 1 col on mobile, 3 on sm, 4 on lg — fills perfectly */}
                        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
                            {kpis.map(ins => <DashboardCard key={ins.id} insight={ins} onViewSql={setSqlInsight} filterDefs={filterDefs} />)}
                        </div>
                    </section>
                )}

                {/* ── 2. Trends ──────────────────────────────────────────────── */}
                {trends.length > 0 && (
                    <section>
                        <SectionHead icon={TrendingUp} label="Trend Analysis" ringColor="bg-blue-500" count={trends.length} />
                        {/* 1 col mobile, 2 col on lg+ */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
                            {trends.map(ins => <DashboardCard key={ins.id} insight={ins} onViewSql={setSqlInsight} filterDefs={filterDefs} />)}
                        </div>
                    </section>
                )}

                {/* ── 3. Distributions ───────────────────────────────────────── */}
                {dists.length > 0 && (
                    <section>
                        <SectionHead icon={BarChart3} label="Distribution Insights" ringColor="bg-violet-500" count={dists.length} />
                        {/* 1→2→3 cols depending on screen width */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-6">
                            {dists.map(ins => <DashboardCard key={ins.id} insight={ins} onViewSql={setSqlInsight} filterDefs={filterDefs} />)}
                        </div>
                    </section>
                )}

                {/* ── 4. Alerts ──────────────────────────────────────────────── */}
                {alerts.length > 0 && (
                    <section>
                        <SectionHead icon={AlertCircle} label="Alerts & Monitors" ringColor="bg-rose-500" count={alerts.length} />
                        {/* 1→2→3→4 cols */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-5">
                            {alerts.map(ins => <DashboardCard key={ins.id} insight={ins} onViewSql={setSqlInsight} filterDefs={filterDefs} />)}
                        </div>
                    </section>
                )}

                {/* ── Footer ─────────────────────────────────────────────────── */}
                <div className="flex items-center justify-between py-3 border-t border-slate-200 text-xs text-slate-400">
                    <span>Franchise Analytics · {total} visualizations</span>
                    {dashConfig?.generated_at && <span>Generated {new Date(dashConfig.generated_at).toLocaleDateString()}</span>}
                </div>
            </div>

            <SqlViewerModal isOpen={!!sqlInsight} onClose={() => setSqlInsight(null)}
                sql={sqlInsight?.sql} title={sqlInsight?.title} />
        </div>
    );
}
