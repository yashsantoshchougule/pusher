import React, { useMemo, useState } from 'react';
import { AlertTriangle, Activity } from 'lucide-react';

const W = 800;
const H = 250;
const PAD = { left: 48, right: 48, top: 20, bottom: 30 };
const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;

function normalizePoints(points) {
  if (!Array.isArray(points) || points.length === 0) return [];
  return points
    .filter((pt) => pt && typeof pt === 'object')
    .map((pt, idx) => ({
      t: Number(pt.t ?? pt.elapsed_sec ?? idx),
      vus: Math.max(0, Number(pt.vus ?? pt.active_vus ?? 0)),
      rps: Math.max(0, Number(pt.rps ?? pt.live_rps ?? 0)),
      p95_ms: Math.max(0, Number(pt.p95_ms ?? 0)),
      error_pct: Math.max(0, Math.min(100, Number(pt.error_pct ?? 0))),
    }))
    .sort((a, b) => a.t - b.t);
}

export default function ProjectHealthChart({
  timelinePoints = [],
  crashSummary = null,
  projectName = '',
  title = 'PROJECT PERFORMANCE HEALTH OVER TIME',
  live = false,
  themeMode = 'production',
}) {
  const isProd = themeMode === 'production';
  const [hoverIdx, setHoverIdx] = useState(null);

  const data = useMemo(() => normalizePoints(timelinePoints), [timelinePoints]);

  const maxT = useMemo(() => {
    if (data.length === 0) return 30;
    return Math.max(1, data[data.length - 1].t, data[0].t + 1);
  }, [data]);
  const minT = data.length > 0 ? data[0].t : 0;
  const spanT = Math.max(1, maxT - minT);

  const maxVus = useMemo(() => Math.max(10, ...data.map((d) => d.vus)), [data]);
  const maxP95 = useMemo(() => Math.max(200, ...data.map((d) => d.p95_ms)), [data]);
  const maxErr = useMemo(() => Math.max(10, ...data.map((d) => d.error_pct)), [data]);

  const xForT = (t) => PAD.left + ((t - minT) / spanT) * PLOT_W;
  const yForVus = (vus) => PAD.top + PLOT_H - (vus / maxVus) * PLOT_H * 0.85;
  const yForP95 = (ms) => PAD.top + PLOT_H - (ms / maxP95) * PLOT_H;
  const yForErr = (err) => PAD.top + PLOT_H - (err / maxErr) * PLOT_H;

  const p95Path = useMemo(() => {
    if (data.length === 0) return '';
    return data
      .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xForT(d.t).toFixed(1)} ${yForP95(d.p95_ms).toFixed(1)}`)
      .join(' ');
  }, [data, minT, spanT, maxP95]);

  const errPath = useMemo(() => {
    if (data.length === 0) return '';
    return data
      .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xForT(d.t).toFixed(1)} ${yForErr(d.error_pct).toFixed(1)}`)
      .join(' ');
  }, [data, minT, spanT, maxErr]);

  const vuAreaPath = useMemo(() => {
    if (data.length === 0) return '';
    const pts = data.map((d) => `${xForT(d.t).toFixed(1)} ${yForVus(d.vus).toFixed(1)}`);
    const baseRight = `${xForT(data[data.length - 1].t).toFixed(1)} ${(PAD.top + PLOT_H).toFixed(1)}`;
    const baseLeft = `${xForT(data[0].t).toFixed(1)} ${(PAD.top + PLOT_H).toFixed(1)}`;
    return `M ${baseLeft} L ${pts.join(' L ')} L ${baseRight} Z`;
  }, [data, minT, spanT, maxVus]);

  const vuStrokePath = useMemo(() => {
    if (data.length === 0) return '';
    return data
      .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xForT(d.t).toFixed(1)} ${yForVus(d.vus).toFixed(1)}`)
      .join(' ');
  }, [data, minT, spanT, maxVus]);

  const breakSec = crashSummary?.first_error_sec;
  const breakVus = crashSummary?.first_error_vus;
  const showBreakPin = breakSec != null && data.length > 0 && breakSec >= minT && breakSec <= maxT;
  const breakX = showBreakPin ? xForT(breakSec) : 0;

  const activePoint = hoverIdx != null && data[hoverIdx] ? data[hoverIdx] : null;

  const handleMouseMove = (evt) => {
    if (data.length === 0) return;
    const svg = evt.currentTarget;
    const rect = svg.getBoundingClientRect();
    if (!rect.width) return;
    const relX = ((evt.clientX - rect.left) / rect.width) * W;
    let nearest = 0;
    let bestDist = Infinity;
    for (let i = 0; i < data.length; i += 1) {
      const dist = Math.abs(xForT(data[i].t) - relX);
      if (dist < bestDist) {
        bestDist = dist;
        nearest = i;
      }
    }
    setHoverIdx(nearest);
  };

  const verdictLine = crashSummary?.plain_english_verdict
    || (data.length === 0
      ? 'Waiting for timeline samples — start a load test to inspect project health over time.'
      : `Peak ${maxVus} users • Max response ${Math.round(maxP95)} ms • Max error ${Math.max(...data.map((d) => d.error_pct)).toFixed(1)}%`);

  return (
    <section className={`ui-outline border border-line bg-surface p-3.5 space-y-2.5 ${isProd ? 'shadow-sm' : ''}`}>
      {/* Header & Plain-English Legend */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
        <div className="flex items-center gap-2">
          <Activity className={`w-4 h-4 shrink-0 ${isProd ? 'text-emerald-700' : ''}`} />
          <div>
            <div className="text-xs font-black uppercase tracking-wider">
              {projectName ? `${projectName} — ` : ''}{title}
            </div>
          </div>
          {live && (
            <span className="border border-line bg-emerald-600 text-white px-1.5 py-0.2 text-[9px] font-black uppercase">
              LIVE
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3 text-[10px] font-mono">
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-2.5 border border-emerald-600 bg-emerald-300/60" />
            <span>Active Users (VUs)</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3.5 h-0.5 bg-[var(--plot-latency)]" />
            <span>Response Time (Lower = Better)</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3.5 h-0.5 bg-[var(--plot-error)]" />
            <span>Errors / Failures (%)</span>
          </span>
        </div>
      </div>

      {/* Responsive SVG Plot */}
      <div className="relative w-full">
        {data.length === 0 ? (
          <div className="border border-dashed border-line/40 bg-field h-44 flex items-center justify-center text-xs font-mono text-muted">
            No timeline points recorded yet.
          </div>
        ) : (
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="w-full h-56 select-none overflow-visible"
            onMouseMove={handleMouseMove}
            onMouseLeave={() => setHoverIdx(null)}
            role="img"
            aria-label={title}
          >
            {/* 3 Soft Health Zones */}
            <rect
              x={PAD.left}
              y={PAD.top}
              width={PLOT_W}
              height={PLOT_H * 0.30}
              fill={'rgb(var(--ui-soft))'}
            />
            <rect
              x={PAD.left}
              y={PAD.top + PLOT_H * 0.30}
              width={PLOT_W}
              height={PLOT_H * 0.30}
              fill={'rgb(var(--ui-canvas))'}
            />
            <rect
              x={PAD.left}
              y={PAD.top + PLOT_H * 0.60}
              width={PLOT_W}
              height={PLOT_H * 0.40}
              fill={'rgb(var(--ui-field))'}
            />

            {/* Zone labels */}
            <text x={PAD.left + 6} y={PAD.top + 12} fontSize="9" fill="var(--plot-error)" fontWeight="bold" opacity="0.65">
              CRASHING / OVERLOADED
            </text>
            <text x={PAD.left + 6} y={PAD.top + PLOT_H * 0.30 + 12} fontSize="9" fill="rgb(var(--ui-muted))" fontWeight="bold" opacity="0.65">
              SLOWING
            </text>
            <text x={PAD.left + 6} y={PAD.top + PLOT_H * 0.60 + 12} fontSize="9" fill="var(--plot-latency)" fontWeight="bold" opacity="0.65">
              SMOOTH
            </text>

            {/* Frame & Axes */}
            <rect x={PAD.left} y={PAD.top} width={PLOT_W} height={PLOT_H} fill="none" stroke="rgb(var(--ui-control))" strokeWidth="1.2" />

            {/* Y-Axis Ticks (Left: Latency ms, Right: Error %) */}
            <text x={PAD.left - 6} y={PAD.top + 6} textAnchor="end" fontSize="9" fill="var(--plot-latency)" fontFamily="monospace">
              {Math.round(maxP95)}ms
            </text>
            <text x={PAD.left - 6} y={PAD.top + PLOT_H * 0.5 + 3} textAnchor="end" fontSize="9" fill="var(--plot-latency)" fontFamily="monospace">
              {Math.round(maxP95 / 2)}ms
            </text>
            <text x={PAD.left - 6} y={PAD.top + PLOT_H} textAnchor="end" fontSize="9" fill="var(--plot-latency)" fontFamily="monospace">
              0ms
            </text>

            <text x={W - PAD.right + 6} y={PAD.top + 6} textAnchor="start" fontSize="9" fill="var(--plot-error)" fontFamily="monospace">
              {Math.round(maxErr)}%
            </text>
            <text x={W - PAD.right + 6} y={PAD.top + PLOT_H * 0.5 + 3} textAnchor="start" fontSize="9" fill="var(--plot-error)" fontFamily="monospace">
              {Math.round(maxErr / 2)}%
            </text>
            <text x={W - PAD.right + 6} y={PAD.top + PLOT_H} textAnchor="start" fontSize="9" fill="var(--plot-error)" fontFamily="monospace">
              0% err
            </text>

            {/* X-Axis Time Ticks */}
            <text x={PAD.left} y={H - 8} textAnchor="start" fontSize="9" fill="rgb(var(--ui-muted))" fontFamily="monospace">
              {minT}s
            </text>
            <text x={PAD.left + PLOT_W * 0.5} y={H - 8} textAnchor="middle" fontSize="9" fill="rgb(var(--ui-muted))" fontFamily="monospace">
              {Math.round(minT + spanT * 0.5)}s
            </text>
            <text x={PAD.left + PLOT_W} y={H - 8} textAnchor="end" fontSize="9" fill="rgb(var(--ui-muted))" fontFamily="monospace">
              {maxT}s
            </text>

            {/* Shaded Sage Active Users Area */}
            {vuAreaPath && (
              <path d={vuAreaPath} fill="var(--plot-load)" fillOpacity="0.35" />
            )}
            {vuStrokePath && (
              <path d={vuStrokePath} fill="none" stroke="var(--plot-load)" strokeWidth="1.2" strokeDasharray="3 2" />
            )}

            {/* Forest Green Response Time Line */}
            {p95Path && (
              <path d={p95Path} fill="none" stroke="var(--plot-latency)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
            )}

            {/* Coral Red Error % Line */}
            {errPath && (
              <path d={errPath} fill="none" stroke="var(--plot-error)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            )}

            {/* Breaking Point Vertical Pin */}
            {showBreakPin && (
              <g>
                <line
                  x1={breakX}
                  y1={PAD.top}
                  x2={breakX}
                  y2={PAD.top + PLOT_H}
                  stroke="#b91c1c"
                  strokeWidth="1.6"
                  strokeDasharray="4 3"
                />
                <rect
                  x={Math.min(PAD.left + PLOT_W - 155, Math.max(PAD.left + 4, breakX - 75))}
                  y={PAD.top + 4}
                  width="150"
                  height="16"
                  rx="2"
                  fill="var(--plot-error)"
                />
                <text
                  x={Math.min(PAD.left + PLOT_W - 80, Math.max(PAD.left + 79, breakX))}
                  y={PAD.top + 15}
                  textAnchor="middle"
                  fontSize="9"
                  fill="#ffffff"
                  fontWeight="bold"
                  fontFamily="monospace"
                >
                  {`! Started failing: ${breakVus ?? '?'} VUs`}
                </text>
              </g>
            )}

            {/* Interactive Hover Crosshair & Highlight Dots */}
            {activePoint && (
              <g>
                <line
                  x1={xForT(activePoint.t)}
                  y1={PAD.top}
                  x2={xForT(activePoint.t)}
                  y2={PAD.top + PLOT_H}
                  stroke="rgb(var(--ui-control))"
                  strokeWidth="1"
                  strokeDasharray="2 2"
                />
                <circle cx={xForT(activePoint.t)} cy={yForP95(activePoint.p95_ms)} r="4" fill="var(--plot-latency)" stroke="rgb(var(--ui-surface))" strokeWidth="1.5" />
                <circle cx={xForT(activePoint.t)} cy={yForErr(activePoint.error_pct)} r="4" fill="var(--plot-error)" stroke="rgb(var(--ui-surface))" strokeWidth="1.5" />
                <circle cx={xForT(activePoint.t)} cy={yForVus(activePoint.vus)} r="3.5" fill="var(--plot-load)" stroke="rgb(var(--ui-surface))" strokeWidth="1.2" />
              </g>
            )}
          </svg>
        )}

        {/* Hover Telemetry Readout */}
        {activePoint && (
          <div className="mt-1 border border-line bg-primary text-white px-2.5 py-1 text-[10px] font-mono flex flex-wrap items-center justify-between gap-3">
            <span>Second: <strong>{activePoint.t}s</strong></span>
            <span>Active Users: <strong>{activePoint.vus} VUs</strong></span>
            <span>Throughput: <strong>{activePoint.rps} RPS</strong></span>
            <span>Response P95: <strong>{activePoint.p95_ms} ms</strong></span>
            <span className={activePoint.error_pct > 0 ? 'text-rose-300 font-bold' : 'text-emerald-300'}>
              Errors: <strong>{activePoint.error_pct}%</strong>
            </span>
          </div>
        )}
      </div>

      {/* 1-Line Plain-English Verdict Bar */}
      <div className="border-t border-line pt-2 flex items-center gap-2 text-xs font-medium text-ink">
        {crashSummary?.first_error_vus != null && (
          <AlertTriangle className="w-3.5 h-3.5 text-rose-700 shrink-0" />
        )}
        <span>{verdictLine}</span>
      </div>
    </section>
  );
}
