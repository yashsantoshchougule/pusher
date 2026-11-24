# Issue 09 — Save & Launch

- Return the saved journey from the save handler. Start only when that handler succeeds, passing the returned steps and enabled flag directly into the launch payload.
- Keep normal launch buttons using the current editor selection. Verify that failed saves launch nothing and successful saves launch the acknowledged steps even when journey mode was previously off.
