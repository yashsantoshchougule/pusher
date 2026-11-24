# F04 Reports overstate peak concurrency

Measure the highest number of VUs with overlapping outbound requests in the shared request path. Count a VU from opening its request through response drain or cancellation. Reset the counters between runs, and limit started workers to the existing connection cap. Preserve the configured target separately and clamp scheduled telemetry to the worker cap.

Display the measured peak in reports and history, including a real zero. Use the report's knee analysis summary in place of the sample concurrency graph. Preserve older stored report values because their measured peak cannot be recovered.

Use an overlapping fake transport to assert a 10-VU ramp that ends during the first stage reports a peak of 2. Also verify a capped steady workload, both worker modes, and an immediate stop with zero requests. Run report, Guard, cancellation, and frontend checks.
