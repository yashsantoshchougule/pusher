import React from 'react';
import {
  Search,
  CheckSquare,
  Square,
  Trash2,
  ArrowRight,
  Copy,
  ExternalLink,
  Activity
} from 'lucide-react';

export default function TestHistoryView({
  runHistory,
  filteredRuns,
  historySearch,
  setHistorySearch,
  historyModeFilter,
  setHistoryModeFilter,
  historyStatusFilter,
  setHistoryStatusFilter,
  selectedForCompare,
  toggleCompareRun,
  handleCompareRuns,
  handleClearArchive,
  handleViewSingleReport,
  handleCloneRun,
  setActiveNav,
  themeMode = 'production',
}) {
  const isProd = themeMode === 'production';

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="border-b-2 border-black pb-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black uppercase tracking-wider">
            TEST RUN ARCHIVE &amp; COMPARISON STAGING
          </h1>
          <p className="text-xs opacity-75">
            Historical record of completed, aborted, and circuit-broken load test executions.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setActiveNav('dashboard')}
          className="border-2 border-black px-3 py-1 text-xs font-bold uppercase hover:bg-black hover:text-white transition-colors cursor-pointer"
        >
          ← Back to Dashboard
        </button>
      </div>

      {/* 1. Top Summary & Filter Bar */}
      <div className={`border-2 border-black p-4 bg-white space-y-3 ${isProd ? 'shadow-sm' : ''}`}>
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
          {/* Search Input */}
          <div className="md:col-span-4 relative">
            <input
              type="text"
              value={historySearch}
              onChange={(e) => setHistorySearch(e.target.value)}
              placeholder="Search Run ID or Target..."
              className="w-full border-2 border-black px-3 py-1.5 text-xs font-mono bg-white focus:outline-none focus:ring-1 focus:ring-black"
            />
          </div>

          {/* Mode Filter Buttons */}
          <div className="md:col-span-5 flex flex-wrap gap-1">
            {['ALL', 'STEP-RAMP', 'SUDDEN RUSH', 'STEADY CROWD'].map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setHistoryModeFilter(m)}
                className={`border border-black px-2 py-1 text-[11px] font-bold uppercase cursor-pointer ${
                  historyModeFilter === m
                    ? (isProd ? 'bg-slate-900 text-white' : 'bg-black text-white')
                    : 'bg-white text-black hover:bg-black/5'
                }`}
              >
                {m}
              </button>
            ))}
          </div>

          {/* Status Dropdown */}
          <div className="md:col-span-3">
            <select
              value={historyStatusFilter}
              onChange={(e) => setHistoryStatusFilter(e.target.value)}
              className="w-full border-2 border-black px-2.5 py-1.5 text-xs font-mono bg-white focus:outline-none cursor-pointer"
            >
              <option value="ALL">ALL VERDICTS</option>
              <option value="PASSED">PASSED</option>
              <option value="CIRCUIT_TRIPPED">CIRCUIT TRIPPED (429/5XX)</option>
              <option value="MANUAL_ABORT">MANUAL ABORT</option>
            </select>
          </div>
        </div>

        {/* Compare Bar & Clear History Action */}
        <div className="flex flex-col sm:flex-row items-center justify-between border-t border-black pt-3 gap-2">
          <div className="flex items-center gap-2 text-xs">
            <span className="font-bold uppercase">Compare Staged:</span>
            <span className={`border border-black px-2 py-0.5 font-bold ${
              selectedForCompare.length === 2 && isProd ? 'bg-teal-50 border-teal-600 text-teal-900' : ''
            }`}>
              {selectedForCompare.length} / 2 Selected
            </span>
            <span className="text-[11px] opacity-75">
              ({selectedForCompare.join(', ') || 'Select up to 2 runs to benchmark'})
            </span>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              disabled={selectedForCompare.length < 2}
              onClick={() => handleCompareRuns(selectedForCompare[1] || 'RUN-102', selectedForCompare[0] || 'RUN-103')}
              className={`border-2 border-black px-3 py-1.5 text-xs font-bold uppercase transition-colors ${
                selectedForCompare.length === 2
                  ? (isProd ? 'bg-teal-700 text-white hover:bg-teal-800 cursor-pointer' : 'bg-black text-white hover:bg-white hover:text-black cursor-pointer')
                  : 'bg-white text-black opacity-40 cursor-not-allowed'
              }`}
            >
              COMPARE SELECTED (2/2) IN REPORTS →
            </button>
            <button
              type="button"
              onClick={handleClearArchive}
              className={`border-2 border-black px-2.5 py-1.5 text-xs font-bold uppercase transition-colors cursor-pointer flex items-center gap-1 ${
                isProd ? 'bg-rose-50 text-rose-800 border-rose-400 hover:bg-rose-100' : 'bg-white text-black hover:bg-black hover:text-white'
              }`}
              title="Clear all saved test runs from database"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>CLEAR</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. Interactive Runs Table */}
      <div className={`border-2 border-black bg-white overflow-x-auto ${isProd ? 'shadow-sm' : ''}`}>
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b-2 border-black bg-white">
              <th className="py-2.5 px-3 w-10 text-center">COMPARE</th>
              <th className="py-2.5 px-3">RUN ID</th>
              <th className="py-2.5 px-3">TIMESTAMP</th>
              <th className="py-2.5 px-3">TARGET</th>
              <th className="py-2.5 px-3">MODE</th>
              <th className="py-2.5 px-3 text-right">VUs</th>
              <th className="py-2.5 px-3 text-right">DUR</th>
              <th className="py-2.5 px-3 text-right">PEAK RPS</th>
              <th className="py-2.5 px-3 text-right">P95</th>
              <th className="py-2.5 px-3">VERDICT</th>
              <th className="py-2.5 px-3 text-center">ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {filteredRuns.length === 0 ? (
              <tr>
                <td colSpan="11" className="text-center py-8 opacity-60 font-bold uppercase">
                  No matching load test runs found in archive.
                </td>
              </tr>
            ) : (
              filteredRuns.map((run) => {
                const runId = run.id || run.run_id;
                const isSelected = selectedForCompare.includes(runId);
                const verdict = run.status || (run.verdictCategory === 'PASSED' ? 'PASSED' : 'AUTO-ABORT');
                const isPassed = run.verdictCategory === 'PASSED' || verdict.includes('PASSED');
                const isTripped = run.verdictCategory === 'CIRCUIT_BREAKER' || verdict.includes('Circuit') || verdict.includes('429');

                return (
                  <tr key={runId} className="border-b border-black/30 hover:bg-black/5">
                    <td className="py-2 px-3 text-center">
                      <button
                        type="button"
                        onClick={() => toggleCompareRun(runId)}
                        className="cursor-pointer"
                      >
                        {isSelected ? (
                          <CheckSquare className={`w-4 h-4 ${isProd ? 'text-teal-700' : 'text-black'}`} />
                        ) : (
                          <Square className="w-4 h-4 text-black/40 hover:text-black" />
                        )}
                      </button>
                    </td>
                    <td className="py-2 px-3 font-bold">
                      <button
                        type="button"
                        onClick={() => handleViewSingleReport(runId)}
                        className="underline hover:opacity-75 cursor-pointer"
                      >
                        {runId}
                      </button>
                    </td>
                    <td className="py-2 px-3 text-[11px] opacity-80">{run.timestamp}</td>
                    <td className="py-2 px-3 font-mono text-[11px] truncate max-w-[160px]">{run.target}</td>
                    <td className="py-2 px-3 font-bold uppercase text-[11px]">{run.mode}</td>
                    <td className="py-2 px-3 text-right font-bold">{run.peakVus || run.vus}</td>
                    <td className="py-2 px-3 text-right">{run.duration}s</td>
                    <td className="py-2 px-3 text-right font-bold">{run.peakRps || run.rps}</td>
                    <td className="py-2 px-3 text-right">{run.p95}</td>
                    <td className="py-2 px-3">
                      <span className={`border border-current px-1.5 py-0.5 text-[10px] font-bold ${
                        isPassed
                          ? (isProd ? 'bg-emerald-50 text-emerald-800 border-emerald-400' : 'bg-black text-white border-black')
                          : isTripped
                          ? (isProd ? 'bg-rose-50 text-rose-800 border-rose-400' : 'bg-black text-white border-black')
                          : (isProd ? 'bg-amber-50 text-amber-800 border-amber-400' : 'bg-white text-black border-black')
                      }`}>
                        {verdict}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => handleViewSingleReport(runId)}
                          className="border border-black px-1.5 py-0.5 text-[10px] font-bold uppercase hover:bg-black hover:text-white transition-colors cursor-pointer"
                          title="Inspect Report & Knee Breakdown"
                        >
                          Report
                        </button>
                        <button
                          type="button"
                          onClick={() => handleCloneRun(run)}
                          className="border border-black px-1.5 py-0.5 text-[10px] font-bold uppercase hover:bg-black hover:text-white transition-colors cursor-pointer"
                          title="Clone Run Settings to Traffic Setup"
                        >
                          Clone
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
