import React from 'react';
import { Bot, User, BarChart3, Download, Eye, Copy, Trash, Bookmark, Calendar, ArrowDownAZ, ArrowUpAZ, ArrowDown01, ArrowUp10, ArrowUpDown, ChevronDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import InsightPanel from './InsightPanel.jsx';
import { useContainerWidth } from '../hooks/useContainerWidth.js';

function DataTable({ sqlData }) {
  if (!sqlData || !Array.isArray(sqlData.data) || sqlData.data.length === 0) {
    return null;
  }

  const data = sqlData.data;
  const columns = sqlData.columns || Object.keys(data[0] || {});
  const totalRows = data.length;

  // Sorting state - null key means no client-side sort applied (preserves SQL ORDER BY)
  const [sortConfig, setSortConfig] = React.useState(() => ({
    key: null,
    direction: 'desc'
  }));

  // Sort handler
  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  // Apply sorting
  const sortedData = React.useMemo(() => {
    if (!sortConfig.key) return data;

    return [...data].sort((a, b) => {
      const aVal = a[sortConfig.key];
      const bVal = b[sortConfig.key];

      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;

      // Numeric sort
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal;
      }

      // String sort (case insensitive)
      const aStr = String(aVal).toLowerCase();
      const bStr = String(bVal).toLowerCase();

      if (aStr < bStr) {
        return sortConfig.direction === 'asc' ? -1 : 1;
      }
      if (aStr > bStr) {
        return sortConfig.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });
  }, [data, sortConfig]);

  // Pagination: 10 rows per page
  const ROWS_PER_PAGE = 10;
  const [currentPage, setCurrentPage] = React.useState(1);
  const totalPages = Math.ceil(sortedData.length / ROWS_PER_PAGE);
  const startIndex = (currentPage - 1) * ROWS_PER_PAGE;
  const pageData = sortedData.slice(startIndex, startIndex + ROWS_PER_PAGE);

  // Reset to page 1 when sort changes
  React.useEffect(() => { setCurrentPage(1); }, [sortConfig]);

  // Page number list with ellipsis (mirrors Reports page)
  const getPageNumbers = () => {
    const pages = [];
    const maxVisible = 5;
    if (totalPages <= maxVisible + 2) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      if (currentPage > 3) pages.push('...');
      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);
      for (let i = start; i <= end; i++) pages.push(i);
      if (currentPage < totalPages - 2) pages.push('...');
      pages.push(totalPages);
    }
    return pages;
  };

  // Always use Table layout with horizontal scroll
  return (
    <div className="mt-3 sm:mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="bg-slate-50 px-3 py-2 border-b border-slate-200 flex justify-between items-center">
        <span className="text-xs font-semibold text-slate-600">Data Preview ({totalRows} rows)</span>
        <span className="text-[10px] text-slate-400">
          Showing {startIndex + 1}–{Math.min(startIndex + ROWS_PER_PAGE, totalRows)} of {totalRows}
        </span>
      </div>

      <div className="grid w-full min-w-0">
        <div className="overflow-x-auto scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
          <table className="min-w-full text-xs text-left whitespace-nowrap">
            <thead className="bg-slate-50 font-semibold text-slate-600">
              <tr>
                {columns.map((col) => {
                  // Check if column is numeric by examining first non-null value
                  const isNumeric = data.some(row => {
                    const val = row[col];
                    return val !== null && val !== undefined && typeof val === 'number';
                  });

                  return (
                    <th
                      key={col}
                      className="px-3 py-2 border-b border-slate-200 cursor-pointer hover:bg-slate-100 transition-colors select-none group"
                      onClick={() => handleSort(col)}
                    >
                      <div className="flex items-center gap-1.5">
                        {col.replace(/_/g, ' ')}
                        {sortConfig.key === col ? (
                          isNumeric ? (
                            sortConfig.direction === 'asc' ?
                              <ArrowDown01 size={14} className="text-brand-navy" /> :
                              <ArrowUp10 size={14} className="text-brand-navy" />
                          ) : (
                            sortConfig.direction === 'asc' ?
                              <ArrowDownAZ size={14} className="text-brand-navy" /> :
                              <ArrowUpAZ size={14} className="text-brand-navy" />
                          )
                        ) : (
                          <ArrowUpDown size={12} className="text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                        )}
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {pageData.map((row, idx) => (
                <tr key={idx} className="hover:bg-slate-50/50 transition-colors">
                  {columns.map((col) => {
                    let val = row[col];
                    // Don't format IDs with commas
                    const isIdColumn = col.toLowerCase().includes('id') || col.toLowerCase().endsWith('_id');

                    // Render safegaurd: if val is an object (like those returned from complex SQL grouping/JSON), stringify it
                    let displayVal = val;
                    if (val !== null && val !== undefined) {
                      if (typeof val === 'object') {
                        try {
                          displayVal = JSON.stringify(val);
                        } catch (e) {
                          displayVal = String(val);
                        }
                      } else if (typeof val === 'number' && !isIdColumn) {
                        displayVal = val.toLocaleString();
                      }
                    }

                    return (
                      <td key={col} className="px-3 py-2 text-slate-700">
                        {displayVal}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination footer */}
      <div className="border-t border-slate-200 px-3 py-2 flex items-center justify-between bg-slate-50">
        <span className="text-[10px] text-slate-500">
          {sqlData.count > totalRows
            ? `Showing first ${totalRows} of ${sqlData.count.toLocaleString()} — Save as Report for full data`
            : `Showing ${startIndex + 1} to ${Math.min(startIndex + ROWS_PER_PAGE, totalRows)} of ${totalRows} rows`}
        </span>
        {totalPages > 1 && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="p-1 rounded hover:bg-slate-200 disabled:opacity-50 disabled:hover:bg-transparent"
            >
              <ChevronDown className="rotate-90" size={12} />
            </button>
            <div className="flex items-center gap-0.5">
              {getPageNumbers().map((page, idx) => (
                <button
                  key={idx}
                  onClick={() => typeof page === 'number' && setCurrentPage(page)}
                  disabled={page === '...'}
                  className={`min-w-[20px] h-5 px-1 rounded text-[10px] font-medium transition-colors flex items-center justify-center ${page === currentPage
                    ? 'bg-brand-navy text-white'
                    : page === '...'
                      ? 'text-slate-400 cursor-default'
                      : 'text-slate-600 hover:bg-slate-100'
                    }`}
                >
                  {page}
                </button>
              ))}
            </div>
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="p-1 rounded hover:bg-slate-200 disabled:opacity-50 disabled:hover:bg-transparent"
            >
              <ChevronDown className="-rotate-90" size={12} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

const MessageBubble = React.memo(({ role, content, sqlData, responseMeta, timestamp, onGenerateReport, insight, clarificationOptions, onOptionSelect, isLatest, isAdmin = false }) => {
  const isUser = role === 'user';
  const [showSqlModal, setShowSqlModal] = React.useState(false);
  const [copySuccess, setCopySuccess] = React.useState(false);
  const { isNarrow, width } = useContainerWidth();
  const hasSqlRows = !!(sqlData && Array.isArray(sqlData.data) && sqlData.data.length > 0);
  const hasSqlQuery = !!(responseMeta?.generatedSql);
  // Show action bar if there are SQL rows OR if admin has SQL query (even with no data)
  const shouldShowActionBar = !isUser && (hasSqlRows || (isAdmin && hasSqlQuery));

  // Format timestamp or use a default
  const timeString = timestamp
    ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  // Handle SQL copy
  const handleCopySql = async () => {
    const sql = responseMeta?.generatedSql;
    if (!sql) return;

    try {
      await navigator.clipboard.writeText(sql);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch (err) {
      console.error('Failed to copy SQL:', err);
    }
  };

  return (
    <div className={`flex w-full mb-4 sm:mb-6 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`flex flex-col w-full min-w-0 sm:max-w-[90%] md:max-w-[85%] lg:max-w-[75%] ${isUser ? 'items-end' : 'items-start'}`}>

        {/* Header (Name & Time) */}
        <div className={`flex items-center gap-1.5 sm:gap-2 mb-1 sm:mb-1.5 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
          <div className={`flex items-center justify-center p-0.5 sm:p-1 rounded-full ${isUser ? 'bg-blue-100 text-brand-navy' : 'bg-slate-200 text-slate-600'}`}>
            {isUser ? <User size={12} className="sm:w-[14px] sm:h-[14px]" /> : <Bot size={12} className="sm:w-[14px] sm:h-[14px]" />}
          </div>
          <span className="text-[10px] sm:text-xs font-bold text-slate-400 uppercase tracking-wide">
            {isUser ? 'You' : 'AI Assistant'}
          </span>
          <span className="text-[9px] sm:text-[10px] text-slate-300">{timeString}</span>
        </div>

        {/* Bubble */}
        <div
          className={`relative px-3 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm leading-relaxed shadow-sm ${isUser
            ? 'bg-blue-100/50 text-slate-800 rounded-2xl rounded-tr-sm border border-blue-200'
            : 'bg-white text-slate-800 rounded-2xl rounded-tl-sm border border-slate-200'
            }`}
        >
          {/* Main Text Content */}
          <div className="prose prose-sm max-w-none prose-slate prose-p:leading-relaxed prose-pre:bg-slate-100 prose-pre:text-slate-700">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
          </div>

          {/* Clarification Options Buttons */}
          {!isUser && isLatest && clarificationOptions && clarificationOptions.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2 animate-in slide-in-from-left-2 duration-300">
              {clarificationOptions.map((opt, idx) => (
                <button
                  key={idx}
                  onClick={() => onOptionSelect && onOptionSelect(opt)}
                  className="px-3 py-2 text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 hover:text-brand-navy border border-blue-200 rounded-lg transition-all shadow-sm active:scale-95 text-left"
                >
                  {opt}
                </button>
              ))}
            </div>
          )}

          {/* Inline Data Table */}
          {!isUser && sqlData && <DataTable sqlData={sqlData} />}

          {/* No Data Message for Admin */}
          {!isUser && !hasSqlRows && hasSqlQuery && (
            <div className="mt-3 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg">
              <p className="text-xs text-slate-500 italic">No data found for this query.</p>
            </div>
          )}

          {/* Action Bar (Date & Save Actions) - Between Table and Insights */}
          {shouldShowActionBar && (
            <div className="mt-0 pt-2 pb-1 flex items-center justify-between border-t border-slate-100/80">
              {/* Date Display */}
              <div className="flex items-center gap-1.5 text-slate-400">
                {/* <Calendar size={12} strokeWidth={2} /> */}
                <span className="text-[10px] font-medium tracking-wide opacity-80">
                  {new Date().toLocaleDateString('en-US', { month: 'numeric', day: 'numeric', year: 'numeric' })}
                </span>
              </div>

              {/* Action Icons */}
              <div className="flex items-center gap-1">
                {/* Eye + Copy — admin only */}
                {isAdmin && (
                  <>
                    <button
                      onClick={() => setShowSqlModal(true)}
                      className="p-1.5 text-slate-400 hover:text-brand-navy hover:bg-slate-50 rounded-lg transition-all"
                      title="View SQL Query"
                    >
                      <Eye size={14} strokeWidth={1.8} />
                    </button>
                    <button
                      onClick={handleCopySql}
                      className={`p-1.5 ${copySuccess ? 'text-green-600' : 'text-slate-400'} hover:text-brand-navy hover:bg-slate-50 rounded-lg transition-all relative`}
                      title="Copy SQL Query"
                    >
                      <Copy size={13} strokeWidth={1.8} />
                      {copySuccess && (
                        <span className="absolute -top-6 left-1/2 -translate-x-1/2 text-[9px] bg-green-600 text-white px-2 py-0.5 rounded whitespace-nowrap">
                          Copied!
                        </span>
                      )}
                    </button>
                  </>
                )}

                {/* Save as Report — always visible */}
                {(responseMeta?.classification !== 'NON_REPORT') && (
                  <button
                    onClick={() => onGenerateReport && onGenerateReport(
                      responseMeta.query_id,
                      responseMeta.suggested_title,
                      responseMeta.generatedSql,
                      responseMeta.userQuery,
                      sqlData?.columns,
                      insight?.charts || []
                    )}
                    className="p-1.5 text-slate-400 hover:text-brand-navy hover:bg-slate-50 rounded-lg transition-all group relative"
                    title="Save as Report"
                  >
                    <Bookmark size={14} strokeWidth={1.8} />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* AI Insights Panel */}
          {!isUser && insight && hasSqlRows && (
            <InsightPanel config={insight} data={sqlData.data} />
          )}

          {!isUser && !insight && hasSqlRows && (
            <div className="mt-2 text-[10px] text-slate-400 flex items-center gap-1.5 opacity-70 animate-pulse">
              <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce"></div>
              <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0.2s]"></div>
              <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0.4s]"></div>
              <span>Analyzing data for insights...</span>
            </div>
          )}
        </div>

        {/* SQL Query Modal */}
        {showSqlModal && responseMeta?.generatedSql && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-2 sm:p-4" onClick={() => setShowSqlModal(false)}>
            <div className={`bg-white rounded-xl shadow-2xl w-full max-h-[80vh] overflow-hidden ${isNarrow || width < 500 ? 'max-w-[calc(100%-1rem)]' : width < 1024 ? 'max-w-2xl' : 'max-w-3xl'}`} onClick={(e) => e.stopPropagation()}>
              <div className="bg-slate-50 px-4 py-3 border-b border-slate-200 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-slate-800">SQL Query</h3>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleCopySql}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    <Copy size={12} />
                    {copySuccess ? 'Copied!' : 'Copy'}
                  </button>
                  <button
                    onClick={() => setShowSqlModal(false)}
                    className="text-slate-400 hover:text-slate-600 transition-colors"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>
              <div className="p-4 overflow-y-auto max-h-[calc(80vh-60px)] pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                <pre className="text-xs bg-slate-900 text-green-400 p-4 rounded-lg overflow-x-auto font-mono scrollbar-thin scrollbar-thumb-green-500/30 scrollbar-track-slate-800">
                  {responseMeta.generatedSql}
                </pre>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

const MessageList = React.memo(({ messages, onGenerateReport, onSaveReport, onOptionSelect, isAdmin = false }) => {
  return (
    <div className="w-full px-2 sm:px-4 py-3 sm:py-6">
      {messages.length === 0 && (
        <div className="h-full flex flex-col items-center justify-center text-slate-400 gap-3 sm:gap-4 opacity-60">
          <div className="bg-slate-100 p-3 sm:p-4 rounded-full">
            <Bot size={36} strokeWidth={1.5} className="sm:w-[48px] sm:h-[48px]" />
          </div>
          <p className="text-xs sm:text-sm text-center px-4">Ask about requisitions, PO spend, vendors, or inventory...</p>
        </div>
      )}

      {messages.map((m, idx) => (
        <MessageBubble
          key={idx}
          role={m.role}
          content={m.content}
          sqlData={m.sqlData}
          responseMeta={m.responseMeta}
          timestamp={m.timestamp}
          insight={m.insight}
          onGenerateReport={onGenerateReport}
          clarificationOptions={m.clarificationOptions}
          onOptionSelect={onOptionSelect}
          isLatest={idx === messages.length - 1}
          isAdmin={isAdmin}
        />
      ))}
      {/* Invisible element to auto-scroll to bottom could go here */}
    </div>
  );
});

export default MessageList;

