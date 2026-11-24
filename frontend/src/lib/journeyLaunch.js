export async function saveAndLaunchJourney(save, launch) {
  const saved = await save(true);
  if (saved?.use_journey) await launch(saved);
}

export function journeyRequestError(detail, fallback) {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (!Array.isArray(detail)) return fallback;
  const error = detail[0];
  if (error?.loc?.[1] === 'steps') {
    if (error.type === 'too_long') return 'A journey can contain up to 10 steps.';
    if (error.type === 'too_short') return 'Add at least one step to the journey.';
  }
  return 'The server rejected the journey settings. Review the steps and try again.';
}
export function restoreJourneyInputs(savedSteps, submittedSteps) {
  return savedSteps.map((step, index) => {
    const submitted = submittedSteps[index];
    const queryStart = submitted?.path?.indexOf('?') ?? -1;
    return {
      ...step,
      path: queryStart >= 0 ? step.path + submitted.path.slice(queryStart) : step.path,
      headers: { ...step.headers, ...submitted?.headers },
      body: submitted?.body ?? null,
    };
  });
}

