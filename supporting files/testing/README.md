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
