import React, { useState } from 'react';
import { Download } from 'lucide-react';

const measured = (value, unit) => Number.isFinite(value) ? `${value} ${unit}` : 'Unavailable';
const capacity = (vus) => vus > 0 ? measured(vus, 'VUs') : 'Capacity unavailable';
const timelinePageSize = 50;

function RunTimeline({ timeseries }) {
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
              {samples.slice(offset, offset + timelinePageSize).map((sample, index) => (
                <tr key={offset + index} className="border-b border-black/20">
                  <td className="py-1">{measured(sample.elapsed_sec, 's')}</td>
                  <td>{measured(sample.vus, 'VUs')}</td>
                  <td>{measured(sample.rps, 'RPS')}</td>
                  <td>{measured(sample.p95_ms, 'ms')}</td>
                  <td>{Number.isFinite(sample.error_pct) ? `${sample.error_pct}%` : 'Unavailable'}</td>
                </tr>
              ))}
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
  ['Recommended Load', 'knee_vus', 'knee_vus_delta', 'VUs'],
  ['Peak Throughput', 'peak_rps', 'peak_rps_delta', 'RPS'],
  ['P95 Latency', 'p95_ms', 'p95_ms_delta', 'ms'],
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
    selectedReportId ? runHistory.find((run) => run.run_id === selectedReportId) : runHistory[0]
  ) || {};

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
            if (!compareData) {
              handleCompareRuns(compareBaseId, compareCandidateId);
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
                value={selectedReportId}
                onChange={(e) => handleViewSingleReport(e.target.value)}
                className="border-2 border-black px-2 py-1 text-xs font-mono bg-white focus:outline-none w-full sm:w-64 cursor-pointer"
              >
                {runHistory.map((r) => (
                  <option key={r.id || r.run_id} value={r.id || r.run_id}>
                    {r.id || r.run_id} — {r.mode || 'Load Test'} ({r.timestamp})
                  </option>
                ))}
              </select>
            </div>

            <button
              type="button"
              onClick={() => handleExportReport(selectedReportId)}
              className="border-2 border-black px-3 py-1.5 text-xs font-bold uppercase hover:bg-black hover:text-white transition-colors cursor-pointer flex items-center gap-1.5"
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
              <div className="text-[10px] opacity-75">Total: {Number(report.total_requests ?? 0).toLocaleString()} Reqs</div>
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
              isProd ? 'border-t-4 border-t-teal-700 shadow-sm' : ''
            }`}>
              <div className="text-[10px] font-bold uppercase">VERDICT STATUS</div>
              <div className="text-sm font-black mt-2 uppercase border border-black px-1 py-0.5 inline-block">
                {report.status ?? report.verdict ?? '—'}
              </div>
              <div className="text-[10px] opacity-75 mt-1">
                Error rate: {report.error_pct == null ? 'Unavailable' : `${report.error_pct}%`}
              </div>
            </div>
          </div>

          {report.metrics_scope === 'legacy_window' && (
            <p className="text-xs">This older report measured latency and errors in its final telemetry window.</p>
          )}

          {singleRunReport && (
            <RunTimeline key={report.run_id ?? selectedReportId} timeseries={report.timeseries} />
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
                    <td className="py-1 font-bold text-right">{measured(report.latency_breakdown?.p50, 'ms')}</td>
                  </tr>
                  <tr className="border-b border-black/20">
                    <td className="py-1">P90:</td>
                    <td className="py-1 font-bold text-right">{measured(report.latency_breakdown?.p90, 'ms')}</td>
                  </tr>
                  <tr className="border-b border-black/20">
                    <td className="py-1">P95:</td>
                    <td className="py-1 font-bold text-right">{measured(report.p95_ms, 'ms')}</td>
                  </tr>
                  <tr className="border-b border-black/20">
                    <td className="py-1">P99:</td>
                    <td className="py-1 font-bold text-right">{measured(report.latency_breakdown?.p99, 'ms')}</td>
                  </tr>
                  <tr>
                    <td className="py-1">Max Recorded:</td>
                    <td className="py-1 font-bold text-right">{measured(report.latency_breakdown?.max, 'ms')}</td>
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
                  {!report.steps?.length && (
                    <tr><td colSpan={5} className="py-2">No step summaries available.</td></tr>
                  )}
                  {(report.steps || []).map((s, idx) => (
                    <tr key={s.step || idx} className="border-b border-black/20">
                      <td className="py-1">Step {s.step || idx + 1}</td>
                      <td className="py-1 text-right font-bold">{s.vus}</td>
                      <td className="py-1 text-right">{s.rps}</td>
                      <td className="py-1 text-right">{measured(s.p95_ms, 'ms')}</td>
                      <td className="py-1 text-right">{measured(s.error_pct, '%')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
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
                  value={compareBaseId}
                  onChange={(e) => setCompareBaseId(e.target.value)}
                  className="w-full border-2 border-black p-1 text-xs font-mono bg-white focus:outline-none cursor-pointer"
                >
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
                  value={compareCandidateId}
                  onChange={(e) => setCompareCandidateId(e.target.value)}
                  className="w-full border-2 border-black p-1 text-xs font-mono bg-white focus:outline-none cursor-pointer"
                >
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
                  onClick={() => handleCompareRuns(compareBaseId, compareCandidateId)}
                  className={`w-full border-2 border-black py-1.5 px-2 text-xs font-black uppercase transition-colors cursor-pointer text-center ${
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
              <h2 className="text-xs font-black uppercase">{compareData.overall_verdict}</h2>
              <p className="text-xs">{compareData.summary}</p>
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
                    {comparisonMetrics.map(([label, field, deltaField, unit]) => (
                      <tr key={field} className="border-b border-black/20">
                        <th scope="row" className="py-2 px-3">{label}</th>
                        <td className="py-2 px-3">{field === 'knee_vus' ? capacity(compareData.base_run[field]) : measured(compareData.base_run[field], unit)}</td>
                        <td className="py-2 px-3">{field === 'knee_vus' ? capacity(compareData.candidate_run[field]) : measured(compareData.candidate_run[field], unit)}</td>
                        <td className="py-2 px-3 text-right">{measured(compareData.deltas[deltaField], unit)}</td>
                      </tr>
                    ))}
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
