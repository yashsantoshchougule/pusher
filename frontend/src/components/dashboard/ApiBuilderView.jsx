import React from 'react';
import {
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  Play,
  CheckSquare,
  Square,
  RefreshCw,
  FileText,
  CheckCircle2,
  XCircle,
  Code
} from 'lucide-react';

export default function ApiBuilderView({
  journeySteps,
  maxJourneySteps,
  setJourneySteps,
  useJourney,
  setUseJourney,
  journeyMessage,
  setJourneyMessage,
  isDryRunning,
  dryRunResults,
  handleUpdateStep,
  handleAddStep,
  handleDeleteStep,
  handleMoveStep,
  handleResetJourneyDefaults,
  sandboxPresetAvailable,
  resettingJourney,
  handleExecuteDryRun,
  dryRunTarget,
  handleStopDryRun,
  dryRunStopping,
  handleSaveJourney,
  journeySaving,
  handleSaveAndLaunchJourney,
  journeyLaunchBlocker,
  setActiveNav,
  themeMode = 'production',
}) {
  const isProd = themeMode === 'production';
  const savedDryRun = Array.isArray(dryRunResults);
  const dryRunSteps = savedDryRun ? dryRunResults : (dryRunResults?.results ?? dryRunResults?.steps ?? []);
  const extractedNames = Object.keys(dryRunResults?.extracted_context ?? {});
  const showDryRun = savedDryRun ? dryRunSteps.length > 0 : Boolean(dryRunResults);
  const cancelledDryRun = dryRunResults?.status === 'cancelled';

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="border-b-2 border-black pb-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black uppercase tracking-wider">
            API LOAD TEST BUILDER (MULTI-STEP CHAIN)
          </h1>
          <p className="text-xs opacity-75">
            Build sequential synthetic user journeys with token chaining, first-chunk variable extraction, and response status assertions.
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

      {/* Status & Notification Banner */}
      {journeyMessage && (
        <div className={`border-2 border-black p-3 text-xs font-bold flex items-center justify-between ${
          isProd ? 'bg-slate-900 text-white' : 'bg-black text-white'
        }`}>
          <span>{journeyMessage}</span>
          <button
            type="button"
            onClick={() => setJourneyMessage(null)}
            className="border border-white px-2 py-0.5 text-[10px] uppercase hover:bg-white hover:text-black transition-colors cursor-pointer"
          >
            DISMISS
          </button>
        </div>
      )}

      {/* Multi-Step Mode Toolbar */}
      <div className={`border-2 border-black p-4 bg-white space-y-3 ${isProd ? 'shadow-sm' : ''}`}>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-black pb-3">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setUseJourney(!useJourney)}
              className="flex items-center gap-2 text-xs font-bold uppercase select-none cursor-pointer"
            >
              {useJourney ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
              <span>Enable Multi-Step Journey in Load Engine</span>
            </button>
            <span className={`border border-black px-2 py-0.5 text-[10px] font-bold uppercase ${
              useJourney
                ? (isProd ? 'bg-emerald-600 text-white border-emerald-700' : 'bg-black text-white')
                : 'bg-white text-black'
            }`}>
              {useJourney ? 'ACTIVE IN LOAD RUNS' : 'INACTIVE (SINGLE URL MODE)'}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {sandboxPresetAvailable && (
              <button
                type="button"
                onClick={handleResetJourneyDefaults}
                disabled={resettingJourney}
                className="border border-black px-2.5 py-1 text-xs font-bold uppercase hover:bg-black hover:text-white transition-colors cursor-pointer flex items-center gap-1 disabled:opacity-50"
              >
                <RefreshCw className="w-3 h-3" />
                <span>{resettingJourney ? 'Loading sandbox preset…' : 'Reset Sandbox Defaults'}</span>
              </button>
            )}
            <button
              type="button"
              onClick={handleExecuteDryRun}
              disabled={isDryRunning || !dryRunTarget || !journeySteps.length}
              className={`border-2 border-black px-3 py-1 text-xs font-black uppercase transition-colors flex items-center gap-1.5 cursor-pointer ${
                isDryRunning
                  ? 'bg-white text-black opacity-50'
                  : (isProd ? 'bg-teal-700 text-white hover:bg-teal-800' : 'bg-black text-white hover:bg-white hover:text-black')
              }`}
            >
              <Play className="w-3 h-3" />
              <span>{isDryRunning ? 'Running steps…' : 'Dry run steps once'}</span>
            </button>
            {isDryRunning && (
              <button
                type="button"
                onClick={handleStopDryRun}
                disabled={dryRunStopping}
                className="border border-black px-3 py-1 text-xs font-bold disabled:opacity-50"
              >
                {dryRunStopping ? 'Stopping…' : 'Stop dry run'}
              </button>
            )}
          </div>
        </div>
        <p className="text-xs">
          {dryRunTarget
            ? <>Dry runs send real requests to <code>{dryRunTarget}</code>. Write steps can change data.</>
            : 'Verify the target to run these steps.'}
        </p>

        {/* 1-VU Dry-Run Diagnostic Results Card */}
        {showDryRun && (
          <div className={`border-2 border-black p-3 bg-white space-y-2 ${
            isProd && !savedDryRun ? (dryRunResults.all_passed ? 'border-l-4 border-l-emerald-600' : 'border-l-4 border-l-rose-600') : ''
          }`}>
            <div className="flex items-center justify-between border-b border-black pb-1">
              <span className="font-bold text-xs uppercase flex items-center gap-1.5">
                {savedDryRun ? null : dryRunResults.all_passed ? (
                  <CheckCircle2 className={`w-4 h-4 ${isProd ? 'text-emerald-600' : ''}`} />
                ) : (
                  <XCircle className={`w-4 h-4 ${isProd ? 'text-rose-600' : ''}`} />
                )}
                <span>{savedDryRun ? 'Last Saved Dry-Run Steps' : '1-VU Dry-Run Execution Log'}</span>
              </span>
              {!savedDryRun && (
                <span className={`text-[10px] font-bold border border-black px-2 py-0.5 ${
                  dryRunResults.all_passed
                    ? (isProd ? 'bg-emerald-600 text-white border-emerald-700' : 'bg-black text-white')
                    : (isProd ? 'bg-rose-600 text-white border-rose-700' : 'bg-black text-white')
                }`}>
                  {cancelledDryRun ? 'DRY RUN CANCELLED' : dryRunResults.all_passed ? 'CHAIN VERIFIED' : 'CHAIN FAILED'}
                </span>
              )}
            </div>

            {!savedDryRun && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                <div><span className="font-bold">Total Duration:</span> {dryRunResults.total_duration_ms == null ? 'Unavailable' : `${dryRunResults.total_duration_ms} ms`}</div>
                <div><span className="font-bold">Steps Passed:</span> {dryRunSteps.filter((step) => step.passed).length} / {dryRunResults.total_steps}</div>
                <div>
                  <span className="font-bold">Extracted Variables:</span>{' '}
                  {extractedNames.map((name) => `{{${name}}}`).join(', ') || 'None'}
                </div>
              </div>
            )}

            {/* Individual step log */}
            <div className="space-y-1 pt-1 font-mono text-[11px]">
              {dryRunSteps.map((st, i) => (
                <div key={st.step_id || i} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-1 border border-black p-1.5 bg-white">
                  <div className="flex items-center gap-2 truncate">
                    <span className={`w-2 h-2 ${st.passed ? (isProd ? 'bg-emerald-600' : 'bg-black') : (isProd ? 'bg-rose-600' : 'bg-black')}`} />
                    <span className="font-bold">{st.name}</span>
                    <span className="opacity-70 truncate max-w-[200px]">({st.method} {st.path})</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[10px]">{st.status_code ? `HTTP ${st.status_code}` : 'No response'}</span>
                    <span className="text-[10px]">{st.latency_ms}ms</span>
                    <span className={`text-[9px] font-bold border border-black px-1 ${
                      st.passed
                        ? (isProd ? 'bg-emerald-50 text-emerald-800' : 'bg-black text-white')
                        : (isProd ? 'bg-rose-50 text-rose-800' : 'bg-black text-white')
                    }`}>
                      {st.passed ? 'PASS' : 'FAIL'}
                    </span>
                  </div>
                  {st.error && <p className="col-span-2 text-xs text-rose-800">{st.error}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Steps List */}
        <div className="space-y-4 pt-2">
          {journeySteps.map((step, index) => (
            <div key={step.step_id || index} className="border-2 border-black p-4 bg-white space-y-3">
              <div className="flex items-center justify-between border-b border-black pb-2">
                <div className="flex items-center gap-2">
                  <span className={`border-2 border-black w-6 h-6 flex items-center justify-center text-xs font-black ${
                    isProd ? 'bg-slate-900 text-white' : 'bg-black text-white'
                  }`}>
                    {index + 1}
                  </span>
                  <input
                    type="text"
                    value={step.name}
                    onChange={(e) => handleUpdateStep(index, 'name', e.target.value)}
                    className="font-bold text-xs uppercase bg-white border-b border-dashed border-black focus:outline-none"
                    placeholder="Step Name..."
                  />
                </div>

                <div className="flex items-center gap-1.5">
                  <select
                    value={step.method}
                    onChange={(e) => handleUpdateStep(index, 'method', e.target.value)}
                    className="border-2 border-black px-2 py-0.5 text-xs font-bold uppercase bg-white cursor-pointer"
                  >
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="DELETE">DELETE</option>
                    <option value="PATCH">PATCH</option>
                  </select>

                  <button
                    type="button"
                    onClick={() => handleMoveStep(index, -1)}
                    disabled={index === 0}
                    className="border border-black p-1 hover:bg-black hover:text-white disabled:opacity-30 disabled:hover:bg-white disabled:hover:text-black cursor-pointer"
                    title="Move Up"
                  >
                    <ArrowUp className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleMoveStep(index, 1)}
                    disabled={index === journeySteps.length - 1}
                    className="border border-black p-1 hover:bg-black hover:text-white disabled:opacity-30 disabled:hover:bg-white disabled:hover:text-black cursor-pointer"
                    title="Move Down"
                  >
                    <ArrowDown className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteStep(index)}
                    disabled={journeySteps.length <= 1}
                    className="border border-black p-1 hover:bg-black hover:text-white disabled:opacity-30 disabled:hover:bg-white disabled:hover:text-black cursor-pointer ml-1"
                    title="Delete Step"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Step Fields Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="font-bold uppercase text-[10px] block mb-1">
                    Path (Relative / Same-Origin / Sandbox):
                  </label>
                  <input
                    type="text"
                    value={step.path}
                    onChange={(e) => handleUpdateStep(index, 'path', e.target.value)}
                    placeholder="/api/sandbox/..."
                    className="w-full border-2 border-black p-1.5 text-xs bg-white focus:outline-none"
                  />
                  <span className="text-[10px] opacity-70 block mt-0.5">
                    E.g. /api/sandbox/items or https://api.myproject.dev/items
                  </span>
                  {step.requires_query && (
                    <p className="mt-1 text-xs">
                      Re-enter the query string after reopening this journey.
                      {' '}<button type="button" className="underline" onClick={() => handleUpdateStep(index, 'requires_query', false)}>Remove requirement</button>
                    </p>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="font-bold uppercase text-[10px] block mb-1">
                      Expected Status:
                    </label>
                    <input
                      type="number"
                      value={step.expected_status || 200}
                      onChange={(e) => handleUpdateStep(index, 'expected_status', parseInt(e.target.value) || 200)}
                      className="w-full border-2 border-black p-1.5 text-xs bg-white focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="font-bold uppercase text-[10px] block mb-1">
                      Extract JSON Key:
                    </label>
                    <input
                      type="text"
                      value={step.extract_json_key || ''}
                      onChange={(e) => handleUpdateStep(index, 'extract_json_key', e.target.value || null)}
                      placeholder="token"
                      className="w-full border-2 border-black p-1.5 text-xs bg-white focus:outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="font-bold uppercase text-[10px] block mb-1">
                    Headers (JSON object)
                  </label>
                  <input
                    type="text"
                    value={typeof step.headers === 'object' ? JSON.stringify(step.headers) : (step.headers || '')}
                    onChange={(e) => {
                      try {
                        handleUpdateStep(index, 'headers', JSON.parse(e.target.value || '{}'));
                      } catch {
                        handleUpdateStep(index, 'headers', e.target.value);
                      }
                    }}
                    placeholder='{"Authorization": "Bearer {{token}}"}'
                    className="w-full border-2 border-black p-1.5 text-xs bg-white focus:outline-none font-mono"
                  />
                  {step.required_headers?.length > 0 && (
                    <p className="mt-1 text-xs">
                      Runtime headers needed after reopening this journey: {step.required_headers.join(', ')}.
                      {' '}<button type="button" className="underline" onClick={() => handleUpdateStep(index, 'required_headers', [])}>Remove requirement</button>
                    </p>
                  )}
                </div>

                <div>
                  <label className="font-bold uppercase text-[10px] block mb-1">
                    Body Payload (JSON for POST/PUT):
                  </label>
                  <input
                    type="text"
                    value={step.body == null ? '' : (typeof step.body === 'string' ? step.body : JSON.stringify(step.body))}
                    onChange={(e) => handleUpdateStep(index, 'body', e.target.value || null)}
                    placeholder='{"quantity": 1}'
                    className="w-full border-2 border-black p-1.5 text-xs bg-white focus:outline-none font-mono"
                  />
                  {step.requires_body && (
                    <p className="mt-1 text-xs">
                      Re-enter the body after reopening this journey.
                      {' '}<button type="button" className="underline" onClick={() => handleUpdateStep(index, 'requires_body', false)}>Remove requirement</button>
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Add Step Button */}
        <button
          type="button"
          onClick={handleAddStep}
          disabled={journeySteps.length >= maxJourneySteps}
          className="w-full border-2 border-dashed border-black py-2.5 text-xs font-bold uppercase hover:bg-black hover:text-white transition-colors flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Plus className="w-4 h-4" />
          <span>Add Step ({journeySteps.length}/{maxJourneySteps})</span>
        </button>
      </div>

      {/* Save & Return Buttons */}
      {(!journeySteps.length || journeyLaunchBlocker) && (
        <p role="status" className="text-xs font-bold">
          {journeySteps.length ? journeyLaunchBlocker : 'Add at least one step before saving.'}
        </p>
      )}
      <div className="border-t-2 border-black pt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <button
          type="button"
          onClick={() => handleSaveJourney(null)}
          disabled={journeySaving || !journeySteps.length}
          className="border-2 border-black py-3 px-4 text-xs font-bold uppercase hover:bg-black hover:text-white transition-colors cursor-pointer text-center disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {journeySaving ? 'Saving journey…' : 'Save Journey Configuration'}
        </button>
        <button
          type="button"
          onClick={handleSaveAndLaunchJourney}
          disabled={Boolean(journeyLaunchBlocker) || journeySaving}
          className={`border-2 border-black py-3 px-4 text-xs font-black uppercase transition-colors text-center tracking-wider cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
            isProd ? 'bg-emerald-600 text-white hover:bg-emerald-700' : 'bg-black text-white hover:bg-white hover:text-black'
          }`}
        >
          Save &amp; Launch Journey Run Now →
        </button>
      </div>
    </div>
  );
}
