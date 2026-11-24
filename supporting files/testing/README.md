# Testing Directory Guidelines & Local Mock Testing Manual

## 1. Purpose of This Directory
This directory is the **exclusive, mandatory location** for all testing artifacts:
* Test scripts (unit, integration, and security tests)
* Mock target server endpoints
* Load engine prototypes and architectural spikes
* Memory and performance benchmark experiments 

> **STRICT RULE**: No test scripts, mock servers, or prototype engines may reside in the project root or source directories. They must be saved exclusively within `supporting files/testing/`.

---

## 2. Directory Layout

```
supporting files/testing/
├── mocks/          # Mock HTTP target server:
│   └── mock_target_server.py  # Fast 200, 5xx cascades, 429 WAF simulation
│
├── unit/           # Automated logic & boundary tests:
│   ├── test_time_mapping.cjs  # Node.js automated runner for 100-frame clock mapping
│   └── test_time_mapping.py   # Python automated runner for 100-frame clock mapping
│
├── verification/   # Diagnostic, image processing & UI sampling scripts:
│   ├── check_all_frames.ps1   # Validates all 100 timelapse frames exist & are readable
│   ├── detect_crop.ps1        # Detects pillarbox border dimensions on frames
│   ├── crop_all_frames.ps1    # Automated lossless cropping tool for timelapse frames
│   ├── check_colors.ps1       # Hex color sampler for UI elements & surfaces
│   ├── sample_colors.ps1      # Multi-point screen sampling diagnostic
│   ├── compare_exact.ps1      # Exact color consistency validator
│   └── analyze_images.py      # Pixel luminance & RGB analyzer
│
└── conftest.py      # Isolated SQLite and provider fixtures
```

---

## 3. How to Run Tests Locally (`PUSHER_MODE=local_dev`)

Developers can use the built-in sandbox without a public domain or provider account. For the normal startup commands and the built-in target URL, see the [project README](../../README.md). The standalone mock server is an optional second target.

### Optional standalone mock target
Start Pusher as shown in the project README. To use the standalone mock with its normal sandbox origin, bind it to loopback:

```powershell
uv run --locked python -c 'import runpy; from http.server import HTTPServer; m = runpy.run_path("supporting files/testing/mocks/mock_target_server.py"); HTTPServer(("127.0.0.1", 8080), m["MockTargetHandler"]).serve_forever()'
```

Choose `http://127.0.0.1:8080` with Sandbox Simulation enabled.

---

## 4. Testing Protocols & Verification Standards
1. **Safety circuit breakers**: Run `test_automatic_brakes.py` for threshold boundaries and `test_emergency_stop.py` for cancellation, resource cleanup, and restart. Five consecutive 5xx responses or three 429 responses within three seconds trigger their respective brakes. Benchmark stop latency separately.
2. **RAM profiling**: Record actual peak process memory, concurrency, throughput, and stop times on a representative host. The default 500 MB budget uses the model $\text{RAM} = 50 + \text{VUs} \times 0.20$ MB. This model is an admission limit. Use measured results for host claims.
3. **Target Policy Tests** run with `uv run --locked python -m pytest`. The suite selects a temporary SQLite path before loading the backend. Use the loopback smoke check in the project README for an end-to-end verification.
