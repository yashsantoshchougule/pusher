import React from 'react';
import { AlertTriangle, CheckCircle2, Flame, ShieldAlert } from 'lucide-react';

function healthPillClass(status, isProd) {
  const s = String(status || '').toUpperCase();
  if (s === 'CRASHING' || s === 'CRASHED / FAILING') {
    return isProd
      ? 'bg-rose-100 text-rose-900 border-rose-500'
      : 'bg-primary text-white border-line';
  }
  if (s === 'SLOWING' || s === 'SLOWED DOWN') {
    return isProd
      ? 'bg-amber-100 text-amber-900 border-amber-500'
      : 'bg-surface text-ink border-line';
  }
  return isProd
    ? 'bg-emerald-100 text-emerald-900 border-emerald-500'
    : 'bg-surface text-ink border-line';
}

export default function FailureDiagnosisCard({
  failureBreakdown = [],
  crashSummary = null,
  themeMode = 'production',
  compact = false,
}) {
  const isProd = themeMode === 'production';
  const rows = Array.isArray(failureBreakdown) ? failureBreakdown : [];
  const summary = crashSummary && typeof crashSummary === 'object' ? crashSummary : null;

  if (!summary && rows.length === 0) {
    return null;
  }

  const topLabel = String(summary?.status_label || 'SMOOTH').toUpperCase();
  const isCrashed = topLabel.includes('CRASH') || topLabel.includes('FAIL');
  const isSlowing = topLabel.includes('SLOW');

  const bannerClass = isProd
    ? (isCrashed
      ? 'bg-rose-50 border-rose-500 text-rose-950'
      : isSlowing
      ? 'bg-amber-50 border-amber-500 text-amber-950'
      : 'bg-emerald-50 border-emerald-500 text-emerald-950')
    : 'bg-surface border-line text-ink';

  return (
    <section className={`ui-outline border border-line bg-surface ${compact ? 'p-3' : 'p-4'} space-y-3 ${isProd ? 'shadow-sm' : ''}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
        <div className="flex items-center gap-2">
          {isCrashed ? (
            <Flame className={`w-4 h-4 shrink-0 ${isProd ? 'text-rose-700' : ''}`} />
          ) : isSlowing ? (
            <AlertTriangle className={`w-4 h-4 shrink-0 ${isProd ? 'text-amber-700' : ''}`} />
          ) : (
            <CheckCircle2 className={`w-4 h-4 shrink-0 ${isProd ? 'text-emerald-700' : ''}`} />
          )}
          <h3 className="text-xs sm:text-sm font-black uppercase tracking-wider">
            WHERE DID IT START CRASHING / FAILING?
          </h3>
        </div>
        <span className={`border px-2 py-0.5 text-[10px] font-black uppercase ${healthPillClass(topLabel, isProd)}`}>
          {topLabel}
        </span>
      </div>

      {summary && (
        <div className={`border-2 p-2.5 text-xs space-y-1.5 ${bannerClass}`}>
          <div className="font-bold leading-snug">
            {summary.plain_english_verdict || 'No failures detected during this run.'}
          </div>
          <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono">
            <span>
              Safe Capacity: <strong>{Number(summary.safe_max_vus ?? 0).toLocaleString()} VUs</strong>
            </span>
            {summary.first_error_vus != null && (
              <span>
                First Error: <strong>{summary.first_error_vus} VUs</strong> at <strong>{summary.first_error_sec ?? 0}s</strong>
                {summary.first_error_part ? ` (${summary.first_error_part})` : ''}
              </span>
            )}
            {summary.primary_error_code && (
              <span className="border border-current px-1.5 py-0.2 text-[10px] font-bold uppercase">
                Primary Error: {summary.primary_error_code}
              </span>
            )}
          </div>
        </div>
      )}

      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-[11px] font-mono">
            <thead>
              <tr className="border-b border-line">
                <th className="py-1.5 px-2">PROJECT PART / STEP</th>
                <th className="py-1.5 px-2 text-right">REQS</th>
                <th className="py-1.5 px-2 text-right">FAILED</th>
                <th className="py-1.5 px-2 text-right">ERR %</th>
                <th className="py-1.5 px-2 text-right">AVG / P95</th>
                <th className="py-1.5 px-2">FIRST BROKE</th>
                <th className="py-1.5 px-2">ERROR CODES</th>
                <th className="py-1.5 px-2 text-center">HEALTH</th>
                <th className="py-1.5 px-2">WHAT HAPPENED</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((part, idx) => {
                const codeEntries = Object.entries(part.status_codes || {});
                return (
                  <tr key={`${part.part_name}-${idx}`} className="border-b border-line/25 hover:bg-soft">
                    <td className="py-1.5 px-2 font-bold">
                      <div className="truncate max-w-[200px]" title={part.part_name}>
                        {part.part_name}
                      </div>
                      <div className="text-[9px] opacity-70 truncate max-w-[200px]">
                        {part.method} {part.path}
                      </div>
                    </td>
                    <td className="py-1.5 px-2 text-right">{Number(part.total_requests ?? 0).toLocaleString()}</td>
                    <td className={`py-1.5 px-2 text-right font-bold ${isProd && part.failed_requests > 0 ? 'text-rose-700' : ''}`}>
                      {Number(part.failed_requests ?? 0).toLocaleString()}
                    </td>
                    <td className={`py-1.5 px-2 text-right font-bold ${isProd && part.error_rate_pct > 0 ? 'text-rose-700' : ''}`}>
                      {Number(part.error_rate_pct ?? 0).toFixed(1)}%
                    </td>
                    <td className="py-1.5 px-2 text-right whitespace-nowrap">
                      {part.avg_latency_ms ?? 0} / {part.p95_latency_ms ?? 0} ms
                    </td>
                    <td className="py-1.5 px-2 whitespace-nowrap">
                      {part.first_error_at_vus != null
                        ? `${part.first_error_at_vus} VUs @ ${part.first_error_at_sec ?? 0}s`
                        : '—'}
                    </td>
                    <td className="py-1.5 px-2">
                      {codeEntries.length === 0 ? (
                        <span className="opacity-60">None</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {codeEntries.map(([code, cnt]) => (
                            <span key={code} className="border border-line px-1 py-0.2 text-[9px] font-bold bg-soft">
                              {code}: {cnt}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="py-1.5 px-2 text-center">
                      <span className={`border px-1.5 py-0.5 text-[9px] font-black uppercase ${healthPillClass(part.health_status, isProd)}`}>
                        {part.health_status || 'HEALTHY'}
                      </span>
                    </td>
                    <td className="py-1.5 px-2 text-[10px] font-sans leading-snug max-w-[220px]">
                      {part.plain_reason || '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
