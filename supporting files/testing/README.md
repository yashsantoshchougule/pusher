+# Testing Directory Guidelines & 2-Laptop Test Manual

## 1. Purpose of This Directory
This directory is the **exclusive, mandatory location** for all testing artifacts:
* Test scripts (unit, integration, and security tests)
* Mock target server endpoints for Laptop 2
* Load engine prototypes and architectural spikes
* Memory and performance benchmark experiments

> **STRICT RULE**: No test scripts, mock servers, or prototype engines may reside in the project root or source directories. They must be saved exclusively within `supporting files/testing/`.

---

## 2. Directory Layout

```
supporting files/testing/
├── mocks/          # Mock HTTP servers running on Laptop 2:
│                   #   • Fast 200 OK responses
│                   #   • Cascading 5xx server crashes (for circuit breaker tests)
│                   #   • 429 / WAF challenges (for rate limit detection tests)
│                   #   • High-latency / timeout simulations
│
├── prototypes/     # Experimental load engine prototypes (async IO benchmarks)
│
├── benchmarks/     # Memory usage profiling scripts (verifying <250MB for 1,000 VUs)
│
└── unit/           # Unit tests for domain verification, SSRF blocking, and metrics
```

---

## 3. How to Run Tests on the 2-Laptop Setup

### Step A: Start Mock Target Server on Laptop 2
Laptop 2 runs the mock target server that simulates real application conditions without needing the public internet:

```bash
# On Laptop 2:
python supporting\ files/testing/mocks/mock_target_server.py
# Binds to 0.0.0.0:8080 (Accessible via Wi-Fi IP, e.g., http://192.168.1.50:8080)
```

### Step B: Run Pusher on Laptop 1
Laptop 1 connects over local Wi-Fi to Laptop 2 using `local_dev` mode:

```bash
# On Laptop 1:
# 1. Ensure PUSHER_MODE=local_dev in .env
# 2. Start Pusher backend & frontend
# 3. Enter target URL: http://192.168.1.50:8080
# 4. Click "Start Test"
```

---

## 4. Testing Protocols & Verification Standards
1. **Safety Circuit Breaker Validation**: Confirm that when Laptop 2 simulates 5 consecutive 5xx errors or HTTP 429 responses, Laptop 1's engine halts within < 200ms.
2. **RAM Profiling Protocol**: Run memory benchmarks to confirm that memory usage stays strictly within the `100MB–250MB` budget for 1,000 virtual users.
3. **SSRF Unit Tests**: Run unit tests (`pytest supporting files/testing/unit/`) to verify that all private IP ranges and cloud metadata endpoints are blocked in production mode.
