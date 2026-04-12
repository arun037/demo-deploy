import React from 'react';

function SqlResultsPanel({ sqlData }) {
  if (!sqlData || !Array.isArray(sqlData.data) || sqlData.data.length === 0) {
    return null;
  }

  const data = sqlData.data;
  const columns = sqlData.columns || Object.keys(data[0] || {});
  const totalRows = data.length;
  const sampleSize = Math.min(15, totalRows);
  const sample = data.slice(0, sampleSize);

  return (
    <div className="border-t border-slate-200 mt-3 pt-3">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h3 className="text-xs font-semibold text-slate-700">Query Results</h3>
          <p className="text-[11px] text-slate-500">
            Showing {sampleSize.toLocaleString()} of {totalRows.toLocaleString()} records
          </p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
        <table className="min-w-full text-xs">
          <thead className="bg-slate-50">
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  className="px-2 py-1 text-left font-semibold text-slate-700 border-b border-slate-200"
                >
                  {col.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sample.map((row, idx) => (
              <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/60'}>
                {columns.map((col) => {
                  let value = row[col];
                  // Don't format IDs with commas
                  const isIdColumn = col.toLowerCase().includes('id') || col.toLowerCase().endsWith('_id');
                  if (typeof value === 'number' && !isIdColumn) {
                    value = value.toLocaleString();
                  }
                  return (
                    <td
                      key={col}
                      className="px-2 py-1 border-b border-slate-100 text-slate-800 align-top"
                    >
                      {value ?? ''}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default SqlResultsPanel;

