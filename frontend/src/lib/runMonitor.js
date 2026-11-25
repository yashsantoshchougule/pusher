const terminalEvents = new Set([
  'COMPLETE',
  'STOP',
  'STOPPED',
  'CIRCUIT_TRIPPED',
  'EMERGENCY_STOP',
  'FAILED',
  'MANUAL_ABORT',
]);

function isSnapshot(data) {
  return Number.isSafeInteger(data?.status_revision) && typeof data.is_running === 'boolean' &&
    (!data.is_running || (typeof data.run_id === 'string' && data.run_id.length > 0));
}

export function watchRun({ fetch, getToken, openSocket, onStatus, onStatusError, onStopping, onStopError }) {
  let latest = null;
  let lastTerminalRunId = null;
  let closed = false;
  let lastFrameAt = null;
  let statusRequest;
  let stopRequest;
  let pollTimer;
  let reconnectTimer;
  let socket;
  const hasLiveSocket = () => lastFrameAt !== null && Date.now() - lastFrameAt < 3000;

  function accept(data) {
    if (closed || !isSnapshot(data) || (latest && data.status_revision <= latest.status_revision)) return;
    const changed = latest?.run_id !== data.run_id || latest?.is_running !== data.is_running;
    const isTerminalEvent = terminalEvents.has(data.event) && !data.is_running && (
      data.run_id ? lastTerminalRunId !== data.run_id : latest?.run_id !== data.run_id
    );
    const ended = Boolean((latest?.is_running && changed) || isTerminalEvent);
    if (data.is_running && data.run_id && lastTerminalRunId === data.run_id) {
      lastTerminalRunId = null;
    }
    if (isTerminalEvent && data.run_id) {
      lastTerminalRunId = data.run_id;
    }
    latest = data;
    if (changed) onStopError('');
    onStatus(data, ended);
  }

  async function refresh() {
    if (closed || statusRequest) return;
    const previous = latest;
    statusRequest = new AbortController();
    const timeout = setTimeout(() => statusRequest.abort(), 5000);
    statusRequest.signal.addEventListener('abort', () => clearTimeout(timeout), { once: true });
    try {
      const response = await fetch('/api/load/status', { signal: statusRequest.signal, cache: 'no-store' });
      if (!response.ok) throw new Error('Status request failed');
      const data = await response.json();
      if (!isSnapshot(data)) throw new Error('Invalid run status');
      accept(data);
    } catch {
      if (!closed && !hasLiveSocket() && latest === previous) onStatusError();
    } finally {
      clearTimeout(timeout);
      statusRequest = null;
    }
  }

  async function poll() {
    if (!hasLiveSocket()) await refresh();
    if (!closed) pollTimer = setTimeout(poll, 1000);
  }

  function connect() {
    if (closed) return;
    try {
      const current = socket = openSocket();
      current.onopen = async () => {
        try {
          const token = await getToken();
          if (!closed && socket === current && current.readyState === 1) current.send(token);
        } catch {
          current.close();
        }
      };
      current.onmessage = (event) => {
        if (closed || socket !== current) return;
        try {
          const data = JSON.parse(event.data);
          if (!isSnapshot(data)) return;
          lastFrameAt = Date.now();
          accept(data);
        } catch {
          // Ignore malformed telemetry frames.
        }
      };
      current.onclose = () => {
        if (closed || socket !== current) return;
        lastFrameAt = null;
        socket = null;
        reconnectTimer = setTimeout(connect, 2000);
      };
      current.onerror = () => current.close();
    } catch {
      reconnectTimer = setTimeout(connect, 2000);
    }
  }

  async function stop(runId) {
    if (closed || stopRequest || !latest?.is_running || latest.run_id !== runId) return;
    stopRequest = new AbortController();
    const timeout = setTimeout(() => stopRequest.abort(), 15000);
    stopRequest.signal.addEventListener('abort', () => clearTimeout(timeout), { once: true });
    onStopError('');
    onStopping(true);
    try {
      const response = await fetch('/api/load/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_id: runId }),
        signal: stopRequest.signal,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok || !isSnapshot(data?.snapshot) ||
          (data.snapshot.is_running && data.snapshot.run_id === runId)) {
        throw new Error(typeof data?.detail === 'string' ? data.detail : 'Pusher could not confirm the run stopped.');
      }
      accept(data.snapshot);
    } catch (error) {
      if (!closed && latest?.is_running && latest.run_id === runId) {
        onStopError(error.name === 'AbortError' ? 'Pusher could not confirm the run stopped.' : error.message);
        void refresh();
      }
    } finally {
      clearTimeout(timeout);
      stopRequest = null;
      if (!closed) onStopping(false);
    }
  }

  void poll();
  connect();
  return {
    accept,
    refresh,
    stop,
    close() {
      closed = true;
      clearTimeout(pollTimer);
      clearTimeout(reconnectTimer);
      statusRequest?.abort();
      stopRequest?.abort();
      socket?.close();
    },
  };
}
