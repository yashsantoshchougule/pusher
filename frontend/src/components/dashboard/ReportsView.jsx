import React, { useState } from 'react';
import { Download, AlertTriangle } from 'lucide-react';

const measured = (value, unit) => Number.isFinite(value) ? `${value} ${unit}` : 'Unavailable';
const capacity = (vus) => vus > 0 ? measured(vus, 'VUs') : 'Capacity unavailable';
const timelinePageSize = 50;

function aggregateStepsFromTimeseries(timeseries) {
  if (!Array.isArray(timeseries) || timeseries.length === 0) return [];
  const tiers = new Map();
  for (const sample of timeseries) {
    if (!sample || !Number.isFinite(sample.vus) || sample.vus <= 0) continue;
    if (!tiers.has(sample.vus)) tiers.set(sample.vus, []);
    tiers.get(sample.vus).push(sample);
  }
  const median = (arr) => {
    if (!arr.length) return null;
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[mid] : Math.round(((sorted[mid - 1] + sorted[mid]) / 2) * 10) / 10;
  };
  let stepIndex = 0;
  return Array.from(tiers.entries()).map(([vus, samples]) => {
    stepIndex += 1;
    const rpsList = samples.map((s) => s.rps).filter(Number.isFinite);
    const p95List = samples.map((s) => s.p95_ms).filter(Number.isFinite);
    const errList = samples.map((s) => s.error_pct).filter(Number.isFinite);
    return {
      step: stepIndex,
      vus,
      rps: rpsList.length ? Math.round(rpsList.reduce((a, b) => a + b, 0) / rpsList.length) : 0,
      p95_ms: median(p95List),
      error_pct: errList.length ? Math.max(...errList) : null,
      samples: samples.length,
    };
  });
}

function RunTimeline({ timeseries, p95Ceiling, isProd }) {
  const [page, setPage] = useState(0);
  const samples = Array.isArray(timeseries) ? timeseries
    .filter((sample) => Number.isFinite(sample?.elapsed_sec) && sample.elapsed_sec >= 0)
    .sort((a, b) => a.elapsed_sec - b.elapsed_sec) : [];
  const pageCount = Math.ceil(samples.length / timelinePageSize);
  const currentPage = Math.max(0, Math.min(page, pageCount - 1));
  const offset = currentPage * timelinePageSize;

  return (
    <section className="border-2 border-black p-4 bg-white space-y-2">
      <h2 className="text-xs font-bold uppercase border-b border-black pb-1">Run timeline</h2>
      {samples.length === 0 ? (
        <p className="text-xs">No timeline was recorded for this run.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-black">
                <th scope="col" className="py-1">Elapsed</th>
                <th scope="col">Virtual users</th>
                <th scope="col">Throughput</th>
                <th scope="col">P95 latency</th>
                <th scope="col">Error rate</th>
              </tr>
            </thead>
            <tbody>
              {samples.slice(offset, offset + timelinePageSize).map((sample, index) => {
                const isBreach = (Number.isFinite(sample.error_pct) && sample.error_pct > 0) ||
                  (Number.isFinite(p95Ceiling) && p95Ceiling > 0 && Number.isFinite(sample.p95_ms) && sample.p95_ms > p95Ceiling);
                return (
                  <tr
                    key={offset + index}
                    className={`border-b border-black/20 ${
                      isBreach ? (isProd ? 'bg-rose-50 text-rose-900 font-bold' : 'bg-black/10 font-bold') : ''
                    }`}
                  >
                    <td className="py-1">{measured(sample.elapsed_sec, 's')}</td>
                    <td>{measured(sample.vus, 'VUs')}</td>
                    <td>{measured(sample.rps, 'RPS')}</td>
                    <td>{measured(sample.p95_ms, 'ms')}</td>
                    <td>{Number.isFinite(sample.error_pct) ? `${sample.error_pct}%` : 'Unavailable'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {pageCount > 1 && (
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <button type="button" className="border px-2 py-1 disabled:opacity-50" disabled={currentPage === 0}
            onClick={() => setPage(currentPage - 1)}>Previous samples</button>
          <span role="status">{`Page ${currentPage + 1} of ${pageCount}`}</span>
          <button type="button" className="border px-2 py-1 disabled:opacity-50" disabled={currentPage === pageCount - 1}
            onClick={() => setPage(currentPage + 1)}>Next samples</button>
        </div>
      )}
    </section>
  );
}

const comparisonMetrics = [
  ['Recommended Load', 'knee_vus', 'knee_vus_delta', 'knee_vus_pct_change', 'VUs'],
  ['Peak Throughput', 'peak_rps', 'peak_rps_delta', 'peak_rps_pct_change', 'RPS'],
  ['P95 Latency', 'p95_ms', 'p95_ms_delta', 'p95_ms_pct_change', 'ms'],
  ['Error Rate', 'error_pct', 'error_pct_delta', null, '%'],
];

export default function ReportsView({
  reportMode,
  setReportMode,
  runHistory = [],
  selectedReportId,
  singleRunReport,
  compareBaseId,
  setCompareBaseId,
  compareCandidateId,
  setCompareCandidateId,
  compareData,
  reportError = '',
  handleViewSingleReport,
  handleCompareRuns,
  handleExportReport,
  setActiveNav,
  themeMode = 'production',
}) {
  const isProd = themeMode === 'production';

  if (!singleRunReport && (!runHistory || runHistory.length === 0)) {
    return (
      <div className="space-y-6">
        <div className="border-b-2 border-black pb-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-black uppercase tracking-wider">
              CAPACITY REPORTS &amp; BENCHMARK COMPARISON
            </h1>
            <p className="text-xs opacity-75">
              Mathematical Knee-of-the-Curve degradation detection and Before-vs-After regression comparison.
            </p>
          </div>
        </div>
        {reportError && <p role="alert" className="text-xs font-bold text-rose-700">{reportError}</p>}
        <div className="border-2 border-dashed border-black p-12 text-center bg-gray-50 flex flex-col items-center justify-center">
          <div className="text-sm font-black uppercase tracking-wider text-black">
            NO TEST RUNS AVAILABLE FOR ANALYSIS
          </div>
          <div className="text-xs opacity-75 mt-2 font-bold max-w-md">
            Execute a load test from 1. Dashboard or 3. Traffic Setup to generate automated capacity scorecards and knee-of-the-curve telemetry.
          </div>
          <button
            type="button"
            onClick={() => setActiveNav('dashboard')}
            className="mt-6 border-2 border-black px-4 py-2 text-xs font-bold uppercase bg-white hover:bg-black hover:text-white transition-colors cursor-pointer"
          >
            GO TO DASHBOARD →
          </button>
        </div>
      </div>
    );
  }

  const report = singleRunReport || (
    selectedReportId ? runHistory.find((run) => (run.run_id || run.id) === selectedReportId) : runHistory[0]
  ) || {};

  const activeReportId = selectedReportId || report.run_id || report.id || '';
  const verdictCat = (report.verdictCategory || report.verdict || '').toUpperCase();
  const isPassed = verdictCat === 'PASSED' || String(report.status || report.status_label || '').toUpperCase().includes('PASSED');
  const isFailed = verdictCat === 'CIRCUIT_BREAKER' || verdictCat === 'FAILED';
  const verdictTileBorder = isProd
    ? (isFailed ? 'border-t-rose-600' : isPassed ? 'border-t-emerald-600' : 'border-t-amber-500')
    : '';
  const verdictBadgeClass = isProd
    ? (isFailed
      ? 'bg-rose-50 text-rose-800 border-rose-400'
      : isPassed
      ? 'bg-emerald-50 text-emerald-800 border-emerald-400'
      : 'bg-amber-50 text-amber-900 border-amber-400')
    : 'bg-white text-black border-black';

  // Thresholds & failure counts
  const p95Ceiling = report.effective_p95_ceiling_ms ?? report.p95_ceiling_ms;
  const maxErrPct = report.effective_max_error_pct ?? report.max_error_pct;
  const totalReq = report.total_requests ?? 0;
  const s2xx = report.status_2xx ?? 0;
  const s429 = report.status_429 ?? 0;
  const s5xx = report.status_5xx ?? 0;
  const sTimeout = report.timeout_count ?? 0;
  const sNetErr = report.network_error_count ?? 0;
  const s3xx = report.status_3xx ?? 0;
  const s4xx = report.status_4xx ?? 0;
  const sOther = Number.isFinite(report.status_other)
    ? report.status_other
    : Math.max(0, totalReq - s2xx - s3xx - s4xx - s429 - s5xx - sTimeout - sNetErr);

  // Latency breakdown (support both p50 and p50_ms keys)
  const lb = report.latency_breakdown || {};
  const p50Val = lb.p50 ?? lb.p50_ms;
  const p90Val = lb.p90 ?? lb.p90_ms;
  const p99Val = lb.p99 ?? lb.p99_ms;
  const maxVal = lb.max ?? lb.max_ms;

  // Steps with timeseries VU-tier fallback
  const progressionSteps = (Array.isArray(report.steps) && report.steps.length > 0)
    ? report.steps
    : aggregateStepsFromTimeseries(report.timeseries);

  // Comparison comparability warnings
  const compareWarnings = [];
  if (compareData?.comparability_warnings?.length) {
    compareWarnings.push(...compareData.comparability_warnings);
  } else if (compareData?.base_run && compareData?.candidate_run) {
    const b = compareData.base_run;
    const c = compareData.candidate_run;
    if (b.target_url && c.target_url && b.target_url !== c.target_url) {
      compareWarnings.push('Runs targeted different URLs.');
    }
    if (b.mode && c.mode && b.mode !== c.mode) {
      compareWarnings.push(`Traffic modes differ (${b.mode} vs ${c.mode}).`);
    }
    if (b.target_vus && c.target_vus && b.target_vus !== c.target_vus) {
      compareWarnings.push(`Planned concurrency differs (${b.target_vus} vs ${c.target_vus} VUs).`);
    }
    if ((b.verdict && b.verdict !== 'PASSED') || (c.verdict && c.verdict !== 'PASSED')) {
      compareWarnings.push(`At least one run did not complete cleanly (${b.verdict || 'unknown'} vs ${c.verdict || 'unknown'}).`);
    }
  }
  const showCompareWarning = Boolean(compareData?.comparable === false || compareWarnings.length > 0);

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="border-b-2 border-black pb-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black uppercase tracking-wider">
            CAPACITY REPORTS &amp; BENCHMARK COMPARISON
          </h1>
          <p className="text-xs opacity-75">
            Mathematical Knee-of-the-Curve degradation detection and Before-vs-After regression comparison.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setActiveNav('history')}
            className="border-2 border-black px-3 py-1 text-xs font-bold uppercase hover:bg-black hover:text-white transition-colors cursor-pointer"
          >
            ← Test History
          </button>
          <button
            type="button"
            onClick={() => setActiveNav('dashboard')}
            className="border-2 border-black px-3 py-1 text-xs font-bold uppercase hover:bg-black hover:text-white transition-colors cursor-pointer"
          >
            ← Dashboard
          </button>
        </div>
      </div>

      {reportError && (
        <p role="alert" className="border-2 border-rose-500 bg-rose-50 text-rose-800 px-3 py-2 text-xs font-bold">
          {reportError}
        </p>
      )}

      {/* Sub-Navigation Tabs: Single-Run vs. Comparison */}
      <div className="flex border-b-2 border-black gap-2">
        <button
          type="button"
          onClick={() => setReportMode('single')}
          className={`px-4 py-2 text-xs font-black uppercase tracking-wider border-2 border-black border-b-0 cursor-pointer ${
            reportMode === 'single'
              ? (isProd ? 'bg-slate-900 text-white' : 'bg-black text-white')
              : 'bg-white text-black hover:bg-black/5'
          }`}
        >
          1. Single-Run Capacity Scorecard (Knee Analysis)
        </button>
        <button
          type="button"
          onClick={() => {
            setReportMode('compare');
            if (!compareData && compareBaseId && compareCandidateId) {
              handleCompareRuns(compareBaseId, compareCandidateId);
            } else if (!compareData && !compareBaseId && !compareCandidateId && runHistory.length >= 2) {
              const base = runHistory[1]?.run_id || runHistory[1]?.id;
              const cand = runHistory[0]?.run_id || runHistory[0]?.id;
              if (base && cand) handleCompareRuns(base, cand);
            }
          }}
          className={`px-4 py-2 text-xs font-black uppercase tracking-wider border-2 border-black border-b-0 cursor-pointer ${
            reportMode === 'compare'
              ? (isProd ? 'bg-slate-900 text-white' : 'bg-black text-white')
              : 'bg-white text-black hover:bg-black/5'
          }`}
        >
          2. Before-vs-After Baseline Comparison
        </button>
      </div>

      {/* TAB 1: SINGLE-RUN SCORECARD */}
      {reportMode === 'single' && (
        <div className="space-y-5">
          {/* Run Selector & Export Bar */}
          <div className={`border-2 border-black p-3 bg-white flex flex-col sm:flex-row items-center justify-between gap-3 ${
            isProd ? 'shadow-sm' : ''
          }`}>
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <span className="text-xs font-bold uppercase whitespace-nowrap">Select Run to Inspect:</span>
              <select
                value={activeReportId}
                onChange={(e) => handleViewSingleReport(e.target.value)}
                className="border-2 border-black px-2 py-1 text-xs font-mono bg-white focus:outline-none w-full sm:w-64 cursor-pointer"
              >
                {!activeReportId && <option value="">Select run…</option>}
                {runHistory.map((r) => (
                  <option key={r.id || r.run_id} value={r.id || r.run_id}>
                    {r.id || r.run_id} — {r.mode || 'Load Test'} ({r.timestamp})
                  </option>
                ))}
              </select>
            </div>

            <button
              type="button"
              disabled={!activeReportId}
              onClick={() => handleExportReport(activeReportId)}
              className="border-2 border-black px-3 py-1.5 text-xs font-bold uppercase hover:bg-black hover:text-white transition-colors cursor-pointer flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Download className="w-3.5 h-3.5" />
              <span>EXPORT JSON SCORECARD</span>
            </button>
          </div>

          {/* 4 Scorecard KPI Tiles */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className={`border-2 border-black p-3.5 bg-white text-center ${
              isProd ? 'border-t-4 border-t-teal-700 shadow-sm' : ''
            }`}>
              <div className="text-[10px] font-bold uppercase">RECOMMENDED LOAD</div>
              <div className="text-2xl font-black mt-1">
                {capacity(report.knee_vus)}
              </div>
            </div>
            <div className={`border-2 border-black p-3.5 bg-white text-center ${
              isProd ? 'border-t-4 border-t-teal-700 shadow-sm' : ''
            }`}>
              <div className="text-[10px] font-bold uppercase">PEAK THROUGHPUT</div>
              <div className="text-2xl font-black mt-1">
                {Number(report.peak_rps ?? 0).toLocaleString()} RPS
              </div>
              <div className="text-[10px] opacity-75">
                Total: {Number(totalReq).toLocaleString()} Reqs · Avg: {measured(report.avg_rps, 'RPS')}
              </div>
            </div>
            <div className={`border-2 border-black p-3.5 bg-white text-center ${
              isProd ? 'border-t-4 border-t-teal-700 shadow-sm' : ''
            }`}>
              <div className="text-[10px] font-bold uppercase">P95 LATENCY</div>
              <div className="text-2xl font-black mt-1">
                {measured(report.p95_ms, 'ms')}
              </div>
            </div>
            <div className={`border-2 border-black p-3.5 bg-white text-center ${
              isProd ? `border-t-4 ${verdictTileBorder} shadow-sm` : ''
            }`}>
              <div className="text-[10px] font-bold uppercase">VERDICT STATUS</div>
              <div className={`text-xs font-black mt-2 uppercase border px-1.5 py-0.5 inline-block ${verdictBadgeClass}`}>
                {report.status ?? report.status_label ?? report.verdict ?? '—'}
              </div>
              <div className="text-[10px] opacity-75 mt-1">
                Error rate: {report.error_pct == null ? 'Unavailable' : `${report.error_pct}%`}
              </div>
            </div>
          </div>

          {/* Execution Metadata, Configured Thresholds & Request Outcome Breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className={`border-2 border-black p-4 bg-white space-y-2 text-xs font-mono ${isProd ? 'shadow-sm' : ''}`}>
              <div className="text-xs font-bold uppercase border-b border-black pb-1">
                Execution Profile &amp; Configured Limits
              </div>
              <div className="grid grid-cols-2 gap-y-1 gap-x-2">
                <div><span className="font-bold">Target:</span> <span className="break-all">{report.target_url || report.target || 'Unavailable'}</span></div>
                <div><span className="font-bold">Mode:</span> {report.mode || 'Unavailable'}</div>
                <div><span className="font-bold">VUs (Peak/Target):</span> {report.peak_vus ?? report.peakVus ?? '—'} / {report.target_vus ?? '—'}</div>
                <div><span className="font-bold">Elapsed / Duration:</span> {report.elapsed_sec ?? '—'}s / {report.duration_sec ?? report.duration ?? '—'}s</div>
                <div><span className="font-bold">Avg Throughput:</span> {measured(report.avg_rps, 'RPS')}</div>
                <div><span className="font-bold">Engine RAM / Stream:</span> {measured(report.ram_mb, 'MB')} · {measured(report.bytes_discarded_mb, 'MB')}</div>
                <div>
                  <span className="font-bold">P95 Ceiling:</span>{' '}
                  {Number.isFinite(p95Ceiling) ? `${Number(p95Ceiling).toLocaleString()} ms` : 'Unavailable'}
                </div>
                <div>
                  <span className="font-bold">Max Error %:</span>{' '}
                  {Number.isFinite(maxErrPct) ? `${maxErrPct}%` : 'Unavailable'}
                </div>
                <div>
                  <span className="font-bold">RAM Limit:</span>{' '}
                  {Number.isFinite(report.ram_limit_mb) ? `${report.ram_limit_mb} MB` : 'Unavailable'}
                </div>
                <div>
                  <span className="font-bold">Req Timeout:</span>{' '}
                  {Number.isFinite(report.request_timeout_sec) ? `${report.request_timeout_sec}s` : 'Unavailable'}
                </div>
              </div>
            </div>

            <div className={`border-2 border-black p-4 bg-white space-y-2 text-xs font-mono ${isProd ? 'shadow-sm' : ''}`}>
              <div className="text-xs font-bold uppercase border-b border-black pb-1">
                Request &amp; Failure Breakdown
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="border border-black p-2">
                  <div className="text-[10px] opacity-75">2XX OK</div>
                  <div className={`text-sm font-black ${isProd ? 'text-emerald-700' : ''}`}>{s2xx.toLocaleString()}</div>
                </div>
                <div className="border border-black p-2">
                  <div className="text-[10px] opacity-75">429 LIMIT</div>
                  <div className={`text-sm font-black ${isProd && s429 > 0 ? 'text-amber-700' : ''}`}>{s429.toLocaleString()}</div>
                </div>
                <div className="border border-black p-2">
                  <div className="text-[10px] opacity-75">5XX ERROR</div>
                  <div className={`text-sm font-black ${isProd && s5xx > 0 ? 'text-rose-700' : ''}`}>{s5xx.toLocaleString()}</div>
                </div>
                <div className="border border-black p-2">
                  <div className="text-[10px] opacity-75">TIMEOUTS</div>
                  <div className={`text-sm font-black ${isProd && sTimeout > 0 ? 'text-rose-700' : ''}`}>{sTimeout.toLocaleString()}</div>
                </div>
                <div className="border border-black p-2">
                  <div className="text-[10px] opacity-75">NETWORK ERR</div>
                  <div className={`text-sm font-black ${isProd && sNetErr > 0 ? 'text-rose-700' : ''}`}>{sNetErr.toLocaleString()}</div>
                </div>
                <div className="border border-black p-2">
                  <div className="text-[10px] opacity-75">OTHER ({s3xx > 0 || s4xx > 0 ? '3XX/4XX/MISC' : 'NON-2XX'})</div>
                  <div className={`text-sm font-black ${isProd && (sOther + s3xx + s4xx) > 0 ? 'text-amber-800' : ''}`}>
                    {(sOther + s3xx + s4xx).toLocaleString()}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {report.metrics_scope === 'legacy_window' && (
            <p className="text-xs">This older report measured latency and errors in its final telemetry window.</p>
          )}

          {singleRunReport && (
            <RunTimeline
              key={report.run_id ?? selectedReportId}
              timeseries={report.timeseries}
              p95Ceiling={p95Ceiling}
              isProd={isProd}
            />
          )}

          {/* Mathematical Knee-of-the-Curve Analysis Card */}
          <div className={`border-2 border-black p-4 bg-white space-y-3 ${isProd ? 'shadow-sm' : ''}`}>
            <div className="flex items-center justify-between border-b-2 border-black pb-2">
              <h2 className="text-xs font-black uppercase tracking-wider">
                CAPACITY ANALYSIS
              </h2>
              <span className={`text-[10px] font-bold border border-black px-2 py-0.5 uppercase ${
                isProd ? 'bg-teal-50 border-teal-600 text-teal-900' : 'bg-white'
              }`}>
                PEAK CONCURRENT VUs · {report.peak_vus ?? report.peakVus ?? '—'}
              </span>
            </div>

            <p className="text-xs font-mono opacity-80 leading-relaxed">
              {report.bottleneck_summary ?? 'Open the full report to view the knee analysis.'}
            </p>
            {report.capacity_reason && (
              <p className="text-xs font-mono opacity-75">
                <strong>Reason:</strong> {report.capacity_reason}
              </p>
            )}
            {(report.linear_range || report.optimal_point || report.cliff_point) && (
              <div className="flex flex-wrap gap-4 text-[11px] font-mono pt-1 border-t border-black/20">
                {report.linear_range && <span>Linear Range: <strong>{report.linear_range}</strong></span>}
                {report.optimal_point && <span>Optimal Point: <strong>{report.optimal_point}</strong></span>}
                {report.cliff_point && <span>Cliff Point: <strong>{report.cliff_point}</strong></span>}
              </div>
            )}
          </div>

          {/* Latency Percentile Breakdown & VU Progression Table */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className={`border-2 border-black p-4 bg-white space-y-2 ${isProd ? 'shadow-sm' : ''}`}>
              <div className="text-xs font-bold uppercase border-b border-black pb-1">
                Latency Percentile Breakdown
              </div>
              <table className="w-full text-left text-xs font-mono">
                <tbody>
                  <tr className="border-b border-black/20">
                    <td className="py-1">P50 (Median):</td>
                    <td className="py-1 font-bold text-right">{measured(p50Val, 'ms')}</td>
                  </tr>
                  <tr className="border-b border-black/20">
                    <td className="py-1">P90:</td>
                    <td className="py-1 font-bold text-right">{measured(p90Val, 'ms')}</td>
                  </tr>
                  <tr className="border-b border-black/20">
                    <td className="py-1">P95:</td>
                    <td className="py-1 font-bold text-right">{measured(report.p95_ms ?? lb.p95 ?? lb.p95_ms, 'ms')}</td>
                  </tr>
                  <tr className="border-b border-black/20">
                    <td className="py-1">P99:</td>
                    <td className="py-1 font-bold text-right">{measured(p99Val, 'ms')}</td>
                  </tr>
                  <tr>
                    <td className="py-1">Max Recorded:</td>
                    <td className="py-1 font-bold text-right">{measured(maxVal, 'ms')}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className={`border-2 border-black p-4 bg-white space-y-2 ${isProd ? 'shadow-sm' : ''}`}>
              <div className="text-xs font-bold uppercase border-b border-black pb-1">
                VU Progression Step Summary
              </div>
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-black text-[10px]">
                    <th className="py-1">STEP</th>
                    <th className="py-1 text-right">VUs</th>
                    <th className="py-1 text-right">RPS</th>
                    <th className="py-1 text-right">P95</th>
                    <th className="py-1 text-right">ERR</th>
                  </tr>
                </thead>
                <tbody>
                  {!progressionSteps.length && (
                    <tr><td colSpan={5} className="py-2">No step summaries available.</td></tr>
                  )}
                  {progressionSteps.map((s, idx) => (
                    <tr key={s.step || idx} className="border-b border-black/20">
                      <td className="py-1">Step {s.step || idx + 1}</td>
                      <td className="py-1 text-right font-bold">{s.vus}</td>
                      <td className="py-1 text-right">{s.rps}</td>
                      <td className="py-1 text-right">{measured(s.p95_ms, 'ms')}</td>
                      <td className="py-1 text-right">{Number.isFinite(s.error_pct) ? `${s.error_pct}%` : 'Unavailable'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Journey Step Metrics Table (if journey steps exist) */}
          {Array.isArray(report.step_metrics) && report.step_metrics.length > 0 && (
            <div className={`border-2 border-black p-4 bg-white space-y-2 ${isProd ? 'shadow-sm' : ''}`}>
              <div className="text-xs font-bold uppercase border-b border-black pb-1">
                API Journey Step Performance
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="border-b border-black text-[10px]">
                      <th className="py-1">STEP</th>
                      <th className="py-1">METHOD</th>
                      <th className="py-1">PATH</th>
                      <th className="py-1 text-right">REQS</th>
                      <th className="py-1 text-right">PASS</th>
                      <th className="py-1 text-right">FAIL</th>
                      <th className="py-1 text-right">AVG (MS)</th>
                      <th className="py-1 text-center">LAST HTTP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.step_metrics.map((sm, idx) => (
                      <tr key={sm.step_id || idx} className="border-b border-black/20">
                        <td className="py-1 font-bold">{sm.name || `Step ${idx + 1}`}</td>
                        <td className="py-1">{sm.method}</td>
                        <td className="py-1 truncate max-w-[200px]">{sm.path}</td>
                        <td className="py-1 text-right">{sm.requests ?? 0}</td>
                        <td className="py-1 text-right">{sm.passed ?? 0}</td>
                        <td className="py-1 text-right">{sm.failed ?? 0}</td>
                        <td className="py-1 text-right">{measured(sm.avg_latency_ms, 'ms')}</td>
                        <td className="py-1 text-center">{sm.last_status || '---'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: BEFORE-VS-AFTER COMPARISON */}
      {reportMode === 'compare' && (
        <div className="space-y-5">
          {/* Comparison Pair Selector Bar */}
          <div className={`border-2 border-black p-4 bg-white space-y-3 ${isProd ? 'shadow-sm' : ''}`}>
            <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
              <div className="md:col-span-5 flex items-center gap-2">
                <span className="text-xs font-bold uppercase whitespace-nowrap">Baseline (Base):</span>
                <select
                  value={compareBaseId || ''}
                  onChange={(e) => setCompareBaseId(e.target.value)}
                  className="w-full border-2 border-black p-1 text-xs font-mono bg-white focus:outline-none cursor-pointer"
                >
                  <option value="">Select baseline run…</option>
                  {runHistory.map((r) => (
                    <option key={r.id || r.run_id} value={r.id || r.run_id}>
                      {r.id || r.run_id} — {r.mode} ({r.timestamp})
                    </option>
                  ))}
                </select>
              </div>

              <div className="md:col-span-5 flex items-center gap-2">
                <span className="text-xs font-bold uppercase whitespace-nowrap">Candidate:</span>
                <select
                  value={compareCandidateId || ''}
                  onChange={(e) => setCompareCandidateId(e.target.value)}
                  className="w-full border-2 border-black p-1 text-xs font-mono bg-white focus:outline-none cursor-pointer"
                >
                  <option value="">Select candidate run…</option>
                  {runHistory.map((r) => (
                    <option key={r.id || r.run_id} value={r.id || r.run_id}>
                      {r.id || r.run_id} — {r.mode} ({r.timestamp})
                    </option>
                  ))}
                </select>
              </div>

              <div className="md:col-span-2">
                <button
                  type="button"
                  disabled={!compareBaseId || !compareCandidateId}
                  onClick={() => handleCompareRuns(compareBaseId, compareCandidateId)}
                  className={`w-full border-2 border-black py-1.5 px-2 text-xs font-black uppercase transition-colors cursor-pointer text-center disabled:opacity-40 disabled:cursor-not-allowed ${
                    isProd ? 'bg-teal-700 text-white hover:bg-teal-800' : 'bg-black text-white hover:bg-white hover:text-black'
                  }`}
                >
                  RE-COMPARE
                </button>
              </div>
            </div>
          </div>

          {compareData ? (
            <div className="border-2 border-black p-4 bg-white space-y-3">
              <div className="flex items-center justify-between gap-2">
                <h2 className={`text-xs font-black uppercase px-2 py-0.5 border ${
                  isProd
                    ? (compareData.overall_verdict === 'IMPROVED'
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-400'
                      : compareData.overall_verdict === 'REGRESSED'
                      ? 'bg-rose-50 text-rose-800 border-rose-400'
                      : 'bg-amber-50 text-amber-900 border-amber-400')
                    : 'border-black'
                }`}>
                  {compareData.overall_verdict}
                </h2>
              </div>
              <p className="text-xs">{compareData.summary}</p>
              {showCompareWarning && (
                <div role="status" className={`border p-2.5 text-xs font-mono flex items-start gap-2 ${
                  isProd ? 'border-amber-400 bg-amber-50 text-amber-900' : 'border-black bg-white'
                }`}>
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  <div>
                    <strong>Comparability warning:</strong>{' '}
                    {compareWarnings.join(' ') || 'Baseline and candidate runs differ in configuration or outcome.'}
                  </div>
                </div>
              )}
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs font-mono">
                  <thead>
                    <tr className="border-b-2 border-black">
                      <th className="py-2 px-3">Metric</th>
                      <th className="py-2 px-3">Baseline ({compareData.base_run.run_id})</th>
                      <th className="py-2 px-3">Candidate ({compareData.candidate_run.run_id})</th>
                      <th className="py-2 px-3 text-right">Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonMetrics.map(([label, field, deltaField, pctField, unit]) => {
                      const deltaVal = compareData.deltas?.[deltaField];
                      const pctVal = pctField ? compareData.deltas?.[pctField] : null;
                      return (
                        <tr key={field} className="border-b border-black/20">
                          <th scope="row" className="py-2 px-3">{label}</th>
                          <td className="py-2 px-3">{field === 'knee_vus' ? capacity(compareData.base_run[field]) : measured(compareData.base_run[field], unit)}</td>
                          <td className="py-2 px-3">{field === 'knee_vus' ? capacity(compareData.candidate_run[field]) : measured(compareData.candidate_run[field], unit)}</td>
                          <td className="py-2 px-3 text-right">
                            {measured(deltaVal, unit)}
                            {Number.isFinite(pctVal) ? ` (${pctVal > 0 ? '+' : ''}${pctVal}%)` : ''}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <p className="text-xs" role="status">Select two reports and run a comparison to see measured values.</p>
          )}
        </div>
      )}
    </div>
  );
}
