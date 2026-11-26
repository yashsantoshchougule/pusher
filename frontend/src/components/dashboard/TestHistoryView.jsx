import React from 'react';
import {
  CheckSquare,
  Square,
  Trash2,
} from 'lucide-react';
import FailureDiagnosisCard from './FailureDiagnosisCard';
import ProjectHealthChart from './ProjectHealthChart';

export default function TestHistoryView({
  runHistory,
  filteredRuns,
  hasActiveFilter = false,
  historyLoading,
  historyError,
  hasMoreHistory,
  onLoadMore,
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
  expandedRunId = null,
  expandedRunDetail = null,
  onToggleExpandRun,
  handleDownloadPdf,
  setActiveNav,
  themeMode = 'production',
}) {
  const isProd = themeMode === 'production';

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="border-b border-line pb-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="ui-page-title">
            Test history
          </h1>
          <p className="text-xs opacity-75">
            Historical record of completed, aborted, and circuit-broken load test executions.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setActiveNav('dashboard')}
          className="border border-line px-3 py-1 text-xs font-bold uppercase hover:bg-primary hover:text-white transition-colors cursor-pointer"
        >
          ← Back to Dashboard
        </button>
      </div>

      {/* 1. Top Summary & Filter Bar */}
      <div className={`ui-outline border border-line p-4 bg-surface space-y-3 ${isProd ? 'shadow-sm' : ''}`}>
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
          {/* Search Input */}
          <div className="md:col-span-4 relative">
            <input
              type="text"
              value={historySearch}
              onChange={(e) => setHistorySearch(e.target.value)}
              placeholder="Search Run ID or Target..."
              className="w-full ui-outline border border-line px-3 py-1.5 text-xs font-mono bg-surface focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          {/* Mode Filter Buttons */}
          <div className="md:col-span-5 flex flex-wrap gap-1">
            {['ALL', 'STEP-RAMP', 'SUDDEN RUSH', 'STEADY CROWD'].map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setHistoryModeFilter(m)}
                className={`border border-line px-2 py-1 text-[11px] font-bold uppercase cursor-pointer ${historyModeFilter === m
                  ? (isProd ? 'bg-primary text-white' : 'bg-primary text-white')
                  : 'bg-surface text-ink hover:bg-soft'
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
              className="w-full ui-outline border border-line px-2.5 py-1.5 text-xs font-mono bg-surface focus:outline-none cursor-pointer"
            >
              <option value="ALL">ALL VERDICTS</option>
              <option value="PASSED">PASSED</option>
              <option value="FAILED">FAILED</option>
              <option value="CIRCUIT_BREAKER">CIRCUIT BREAKER (TRIPPED)</option>
              <option value="MANUAL_ABORT">MANUAL ABORT</option>
            </select>
          </div>
        </div>

        {/* Compare Bar & Clear History Action */}
        <div className="flex flex-col sm:flex-row items-center justify-between border-t border-line pt-3 gap-2">
          <div className="flex items-center gap-2 text-xs">
            <span className="font-bold uppercase">Compare Staged:</span>
            <span className={`border border-line px-2 py-0.5 font-bold ${selectedForCompare.length === 2 && isProd ? 'bg-teal-50 border-teal-600 text-teal-900' : ''
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
              onClick={() => handleCompareRuns(selectedForCompare[0], selectedForCompare[1])}
              className={`border border-line px-3 py-1.5 text-xs font-bold uppercase transition-colors ${selectedForCompare.length === 2
                ? (isProd ? 'bg-primary text-white hover:bg-primary-hover cursor-pointer' : 'bg-primary text-white hover:bg-surface hover:text-ink cursor-pointer')
                : 'bg-surface text-ink opacity-40 cursor-not-allowed'
                }`}
            >
              COMPARE SELECTED (2/2) IN REPORTS →
            </button>
            <button
              type="button"
              onClick={handleClearArchive}
              className={`border border-line px-2.5 py-1.5 text-xs font-bold uppercase transition-colors cursor-pointer flex items-center gap-1 ${isProd ? 'bg-rose-50 text-rose-800 border-rose-400 hover:bg-rose-100' : 'bg-surface text-ink hover:bg-primary hover:text-white'
                }`}
              title="Confirm and clear all saved test runs from database"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>CLEAR</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. Interactive Runs Table */}
      <div className={`ui-outline border border-line bg-surface overflow-x-auto ${isProd ? 'shadow-sm' : ''}`}>
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-line bg-surface">
              <th className="py-2.5 px-3 w-10 text-center">COMPARE</th>
              <th className="py-2.5 px-3">RUN ID</th>
              <th className="py-2.5 px-3">TIMESTAMP</th>
              <th className="py-2.5 px-3">TARGET</th>
              <th className="py-2.5 px-3">MODE</th>
              <th className="py-2.5 px-3 text-right">VUs (PEAK / TARGET)</th>
              <th className="py-2.5 px-3 text-right">DUR</th>
              <th className="py-2.5 px-3 text-right">REQS</th>
              <th className="py-2.5 px-3 text-right">PEAK RPS</th>
              <th className="py-2.5 px-3 text-right">P95</th>
              <th className="py-2.5 px-3 text-right">ERR %</th>
              <th className="py-2.5 px-3 text-right">KNEE</th>
              <th className="py-2.5 px-3">VERDICT</th>
              <th className="py-2.5 px-3 text-center">ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {filteredRuns.length === 0 ? (
              <tr>
                <td colSpan="14" className="text-center py-10 opacity-70 font-bold uppercase tracking-wider text-xs">
                  {!hasActiveFilter && runHistory.length === 0 ? '0 RECORDED RUNS IN DATABASE' : 'No matching load test runs found in archive.'}
                </td>
              </tr>
            ) : (
              filteredRuns.map((run) => {
                const runId = run.id || run.run_id;
                const isSelected = selectedForCompare.includes(runId);
                const category = (run.verdictCategory || run.verdict || '').toUpperCase();
                const fullVerdict = run.status || run.status_label || category || 'UNKNOWN';
                const lowerVerdict = fullVerdict.toLowerCase();
                const isPassed = category === 'PASSED' || (!category && lowerVerdict.includes('passed'));
                const isTripped = category === 'CIRCUIT_BREAKER' || lowerVerdict.includes('circuit') || lowerVerdict.includes('tripped');
                const isFailed = category === 'FAILED' || lowerVerdict.startsWith('failed');
                const pillLabel = isPassed
                  ? 'PASSED'
                  : isTripped
                    ? 'CIRCUIT BREAKER'
                    : isFailed
                      ? 'FAILED'
                      : (category === 'MANUAL_ABORT' || lowerVerdict.includes('abort'))
                        ? 'MANUAL ABORT'
                        : fullVerdict;

                const peakVus = run.peakVus ?? run.peak_vus;
                const targetVus = run.target_vus;
                const elapsedSec = run.elapsed_sec;
                const plannedDur = run.duration_sec ?? run.duration;

                return (
                  <tr key={runId} className="border-b border-line/30 hover:bg-soft">
                    <td className="py-2 px-3 text-center">
                      <button
                        type="button"
                        onClick={() => toggleCompareRun(runId)}
                        className="cursor-pointer"
                      >
                        {isSelected ? (
                          <CheckSquare className={`w-4 h-4 ${isProd ? 'text-teal-700' : 'text-ink'}`} />
                        ) : (
                          <Square className="w-4 h-4 text-muted hover:text-ink" />
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
                    <td className="py-2 px-3 font-mono text-[11px] truncate max-w-[160px]" title={run.target_url || run.target}>
                      {run.project_name && (
                        <div className="font-sans font-bold text-ink truncate">{run.project_name}</div>
                      )}
                      <div className="truncate opacity-80">{run.target || run.target_url}</div>
                    </td>
                    <td className="py-2 px-3 font-bold uppercase text-[11px]">{run.mode}</td>
                    <td className="py-2 px-3 text-right font-bold">
                      {peakVus ?? '—'}{targetVus != null ? ` / ${targetVus}` : ''}
                    </td>
                    <td className="py-2 px-3 text-right">
                      {elapsedSec != null && plannedDur != null ? `${elapsedSec}s / ${plannedDur}s` : `${plannedDur ?? '—'}s`}
                    </td>
                    <td className="py-2 px-3 text-right">
                      {run.total_requests != null ? Number(run.total_requests).toLocaleString() : '—'}
                    </td>
                    <td className="py-2 px-3 text-right font-bold">{run.peakRps ?? run.peak_rps ?? run.rps ?? 0}</td>
                    <td className="py-2 px-3 text-right">{run.p95 ?? (run.p95_ms != null ? `${run.p95_ms} ms` : 'Unavailable')}</td>
                    <td className={`py-2 px-3 text-right font-bold ${isProd && (run.error_pct ?? 0) > 0 ? 'text-rose-700' : ''}`}>
                      {run.error_pct != null ? `${run.error_pct}%` : '—'}
                    </td>
                    <td className="py-2 px-3 text-right">
                      {run.knee_vus > 0 ? `${run.knee_vus} VUs` : 'Unavailable'}
                    </td>
                    <td className="py-2 px-3">
                      <span
                        title={fullVerdict}
                        className={`border px-1.5 py-0.5 text-[10px] font-bold uppercase whitespace-nowrap ${isPassed
                          ? (isProd ? 'bg-emerald-50 text-emerald-800 border-emerald-400' : 'bg-primary text-white border-line')
                          : (isTripped || isFailed)
                            ? (isProd ? 'bg-rose-50 text-rose-800 border-rose-400' : 'bg-primary text-white border-line')
                            : (isProd ? 'bg-amber-50 text-amber-800 border-amber-400' : 'bg-surface text-ink border-line')
                          }`}
                      >
                        {pillLabel}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        {onToggleExpandRun && (
                          <button
                            type="button"
                            onClick={() => onToggleExpandRun(runId)}
                            className={`border border-line px-1.5 py-0.5 text-[10px] font-bold uppercase transition-colors cursor-pointer ${expandedRunId === runId ? 'bg-primary text-white' : 'hover:bg-primary hover:text-white'
                              }`}
                            title="Show Health Graph & Failure Diagnosis Inline"
                          >
                            {expandedRunId === runId ? 'Hide' : 'Graph'}
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleViewSingleReport(runId)}
                          className="border border-line px-1.5 py-0.5 text-[10px] font-bold uppercase hover:bg-primary hover:text-white transition-colors cursor-pointer"
                          title="Inspect Report & Knee Breakdown"
                        >
                          Report
                        </button>
                        {handleDownloadPdf && (
                          <button
                            type="button"
                            onClick={() => handleDownloadPdf(runId, run.project_name)}
                            className={`border border-line px-1.5 py-0.5 text-[10px] font-bold uppercase transition-colors cursor-pointer ${isProd ? 'bg-emerald-700 text-white hover:bg-emerald-800' : 'hover:bg-primary hover:text-white'
                              }`}
                            title="Download Vector PDF Report"
                          >
                            PDF
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleCloneRun(run)}
                          className="border border-line px-1.5 py-0.5 text-[10px] font-bold uppercase hover:bg-primary hover:text-white transition-colors cursor-pointer"
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
      {expandedRunId && (
        <div className="border border-line bg-field p-4 space-y-3">
          {expandedRunDetail && (expandedRunDetail.run_id === expandedRunId || expandedRunDetail.id === expandedRunId) ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
                <div className="text-xs font-black uppercase">
                  {expandedRunDetail.project_name || expandedRunDetail.target_url} — Run {expandedRunId}
                </div>
                {handleDownloadPdf && (
                  <button
                    type="button"
                    onClick={() => handleDownloadPdf(expandedRunId, expandedRunDetail.project_name)}
                    className={`border border-line px-3 py-1 text-xs font-black uppercase transition-colors cursor-pointer ${isProd ? 'bg-emerald-700 text-white hover:bg-emerald-800' : 'bg-primary text-white hover:bg-surface hover:text-ink'
                      }`}
                  >
                    [ DOWNLOAD PDF REPORT ]
                  </button>
                )}
              </div>
              <ProjectHealthChart
                timelinePoints={expandedRunDetail.timeline_points || expandedRunDetail.timeseries || []}
                crashSummary={expandedRunDetail.crash_summary || null}
                projectName={expandedRunDetail.project_name || ''}
                themeMode={themeMode}
              />
              <FailureDiagnosisCard
                failureBreakdown={expandedRunDetail.failure_breakdown || []}
                crashSummary={expandedRunDetail.crash_summary || null}
                themeMode={themeMode}
                compact
              />
            </div>
          ) : (
            <div className="text-xs font-mono opacity-75">Loading run health graph &amp; crash diagnosis…</div>
          )}
        </div>
      )}
      {historyError && <p role="alert" className="text-sm text-red-700">{historyError}</p>}
      {hasMoreHistory && (
        <button type="button" disabled={historyLoading} onClick={onLoadMore}
          className="border border-line px-3 py-2 text-sm font-bold disabled:opacity-50">
          {historyLoading ? 'Loading…' : 'Load more runs'}
        </button>
      )}
    </div>
  );
}
