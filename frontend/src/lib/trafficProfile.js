export const DEFAULT_TRAFFIC_PROFILE = {
  mode: 'step_ramp',
  ram_limit_mb: 500,
  virtual_users: 100,
  duration_sec: 30,
  max_error_pct: 5,
  p95_ceiling_ms: 1500,
  cache_bust: true,
};

function roundEven(value) {
  const whole = Math.floor(value);
  return value - whole === 0.5 && whole % 2 === 0 ? whole : Math.round(value);
}

export function trafficPhases(mode, vus, duration, schedule) {
  if (mode === 'steady_crowd') return [{ start: 0, end: duration, vus }];
  if (!schedule) return [];
  if (mode === 'step_ramp') {
    const { step_ratios: ratios, step_min_seconds: minimum } = schedule;
    const step = Math.max(minimum, duration / ratios.length);
    return ratios.map((ratio, index) => ({
      start: index * step,
      end: index === ratios.length - 1 ? duration : Math.min(duration, (index + 1) * step),
      vus: Math.max(1, roundEven(vus * ratio)),
    })).filter(phase => phase.start < phase.end);
  }
  const warmup = Math.min(schedule.rush_warmup_seconds, duration);
  const warmupVus = Math.min(vus, Math.max(schedule.rush_warmup_min_vus, roundEven(vus * schedule.rush_warmup_ratio)));
  const phases = [{ start: 0, end: warmup, vus: warmupVus }];
  if (duration > warmup) phases.push({ start: warmup, end: duration, vus });
  return phases;
}

export function createTrafficProfile(fetch, onChange, onSaveError, onSaveSuccess) {
  let draft = DEFAULT_TRAFFIC_PROFILE;
  let edited = false;
  let dirty = false;
  let inFlight = null;
  let nextSave = null;
  let latestSave = 0;

  function replace(config) {
    draft = config;
    onChange(config);
  }

  async function writeNow(body, saveNumber) {
    try {
      const response = await fetch('/api/traffic/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
      });
      if (!response.ok) throw new Error('Save rejected');
      if (saveNumber === latestSave) {
        dirty = false;
        onSaveError('');
        onSaveSuccess?.();
      }
      return true;
    } catch {
      if (saveNumber === latestSave) onSaveError('Could not save Traffic Setup. Please try again.');
      return false;
    }
  }

  function save() {
    latestSave += 1;
    if (!inFlight) {
      const run = writeNow(JSON.stringify(draft), latestSave).finally(() => {
        if (inFlight === run) inFlight = null;
      });
      inFlight = run;
      return run;
    }
    if (!nextSave) {
      const queued = inFlight.then(() => {
        nextSave = null;
        const run = writeNow(JSON.stringify(draft), latestSave).finally(() => {
          if (inFlight === run) inFlight = null;
        });
        inFlight = run;
        return run;
      });
      nextSave = queued;
    }
    return nextSave;
  }

  return {
    hydrate(config) {
      if (!edited) {
        dirty = false;
        replace({ ...DEFAULT_TRAFFIC_PROFILE, ...config, cache_bust: Boolean(config.cache_bust ?? true) });
      }
    },
    edit(overrides) {
      edited = true;
      dirty = true;
      replace({ ...draft, ...overrides });
    },
    isDirty() {
      return dirty;
    },
    save,
  };
}
