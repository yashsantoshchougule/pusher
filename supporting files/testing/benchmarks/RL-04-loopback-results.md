# RL-04 loopback measurements

Windows host, 12 logical CPUs, 16,013 MiB installed RAM, CPython 3.12.13, 500 MB runner budget, 2,867 configured workers. Separate runner and target processes shared the host. The target was Pusher's built-in loopback sandbox. Each trial used a 15-second observation window and a 20-second engine deadline. Stop drained every run and produced a matching report with `MANUAL_ABORT`. Every requested level was observed in all three trials. No early stops occurred.

Reproduce with `uv run --locked python -B "supporting files/testing/verification/check_local_sandbox.py" --benchmark`. On this Windows host the permitted base interpreter and existing locked virtual environment packages were used.

| VUs | Trial | Observed s | Requests | Average RPS | Peak RPS | p95 ms | Errors % | Stop ms | Peak target TCP | Peak RSS MiB runner / target | Peak CPU % of one core runner / target |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 1 | 15.02 | 2587 | 172 | 202 | 135 | 0 | 31 | 10 | 68.6 / 63.2 | 103 / 33.3 |
| 10 | 2 | 15.02 | 2695 | 179 | 197 | 127 | 0 | 47 | 10 | 69.4 / 63.7 | 103.2 / 29.4 |
| 10 | 3 | 15.01 | 2675 | 178 | 195 | 133 | 0 | 32 | 10 | 70.8 / 64 | 103 / 35.3 |
| 25 | 1 | 15.05 | 2266 | 151 | 173 | 407 | 0 | 63 | 25 | 71.5 / 65.5 | 103 / 29.4 |
| 25 | 2 | 15.05 | 2121 | 141 | 161 | 414 | 0 | 63 | 25 | 72.4 / 65.7 | 103 / 29.4 |
| 25 | 3 | 15.03 | 2344 | 156 | 166 | 373 | 0 | 62 | 25 | 72.3 / 66.1 | 103.7 / 31.4 |
| 50 | 1 | 15.06 | 2019 | 134 | 156 | 947 | 0 | 94 | 50 | 74.3 / 68.5 | 102.9 / 20 |
| 50 | 2 | 15.06 | 2007 | 133 | 150 | 969 | 0 | 94 | 50 | 74.6 / 68.7 | 103 / 27.8 |
| 50 | 3 | 15.05 | 2022 | 134 | 157 | 915 | 0 | 94 | 50 | 74.7 / 69.3 | 102.8 / 27.8 |

In this fixture, average throughput fell and p95 latency rose at higher concurrency. The runner reached roughly one core during the sampled periods. These nine loopback observations characterize this host, workload, and observation window. Staging capacity requires a representative workload and hardware, agreed thresholds and traffic limits, and separate verification.
