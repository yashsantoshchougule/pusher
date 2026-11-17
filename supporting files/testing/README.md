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
├── prototypes/     # Experimental load engine prototypes (async IO benchmarks)
└── benchmarks/     # Memory usage profiling scripts (verifying <250MB for 1,000 VUs)
```

---

## 3. How to Run Tests Locally (`PUSHER_MODE=local_dev`)

Developers can test Pusher locally without a live public domain or cloud hosting by using the standalone mock target server:

### Step A: Start the Mock Target Server
Run the standalone mock target server:

```bash
python "supporting files/testing/mocks/mock_target_server.py"
# Binds to 0.0.0.0:8080 (Accessible via localhost:8080 or LAN IP, e.g., http://192.168.1.50:8080)
```

### Step B: Run Pusher in Local Dev Mode
Configure and start the Pusher application:

```bash
# 1. Ensure PUSHER_MODE=local_dev in your .env file
# 2. Start Pusher backend & frontend
# 3. Enter target URL: http://localhost:8080 (or http://<LAN-IP>:8080)
# 4. Click "Start Test"
```

---

## 4. Testing Protocols & Verification Standards
1. **Safety Circuit Breaker Validation**: Confirm that when the mock server simulates 5 consecutive 5xx errors or HTTP 429 responses, Pusher's engine halts within < 200ms.
2. **RAM Profiling Protocol**: Run memory benchmarks to confirm that memory usage stays strictly within the `100MB–250MB` budget for 1,000 virtual users.
3. **SSRF Unit Tests**: Run unit tests (`pytest "supporting files/testing/unit/"`) to verify that all private IP ranges and cloud metadata endpoints are blocked in production mode.
