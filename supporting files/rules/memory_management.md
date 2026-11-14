# Memory Management & Resource Efficiency Rules

## 1. Why Memory Management Matters
When running a load test, the tool itself can accidentally eat up all the memory (RAM) on your laptop or server. If the load testing tool runs out of memory, it will crash your computer or cloud server before the target website even feels the load.

**Pusher's Golden Rule**: Keep memory usage ultra-low so Pusher can run comfortably on standard laptops (16GB RAM) and free cloud servers (like Render or Railway with only 512MB RAM) without crashing.

---

## 2. Strict RAM & Disk Budget

The load engine must stay within these strict memory limits:

| Test State | Target RAM Usage | Hard Maximum Allowed |
| :--- | :--- | :--- |
| **Idle Engine (Waiting for test)** | `< 30 MB RAM` | `50 MB RAM` |
| **100 Concurrent Users** | `40 MB – 80 MB RAM` | `100 MB RAM` |
| **1,000 Concurrent Users** | **`100 MB – 250 MB RAM`** | **`300 MB RAM`** |
| **Per-Connection Memory Overhead** | `< 120 KB per user` | `200 KB per user` |
| **Total Disk Usage on Laptop/Server**| **`< 1 GB Disk`** | Zero request body logging to disk |
| **Live Speed Dashboard Memory** | `< 5 MB RAM` | Bounded memory buckets |

---

## 3. Strict Rules for Low Memory

### Rule 3.1: Headless Browsers Are Strictly Banned
> **NEVER USE**: Puppeteer, Playwright, Selenium, or headless Chrome/Firefox in the load engine.

* **Why?** A single headless Chrome tab uses between 50MB and 150MB of RAM. If you simulate 1,000 users using Chrome, you would need **50,000 MB to 150,000 MB (50GB to 150GB) of RAM**, which will immediately freeze and crash your laptop.
* **The Pusher Way**: Use lightweight asynchronous HTTP requests. In Python, an async connection uses only about **120 KB of RAM**. 1,000 async connections take only ~120 MB total, which fits easily inside 512MB of RAM.

```
       ❌ FORBIDDEN: Headless Browser Approach
       [ Load Engine ] ──> [ Browser Process 1 (100MB) ] ──> Target Website
                       ──> [ Browser Process 2 (100MB) ] ──> Target Website
                       ──> [ Browser Process N (100MB) ] ──> Target Website (Laptop Freezes & Crashes!)

       ✅ ENFORCED: Asynchronous Non-blocking HTTP Engine
       [ Pusher Load Engine (Python asyncio + aiohttp) ]
             │
             ├── Async Virtual User #1 ──┐
             ├── Async Virtual User #2 ──┼──> [ Shared Connection Pool ] ──> Target Website
             └── Async Virtual User #N ──┘    (Total RAM: 100MB–250MB for 1,000 Users)
```

---

### Rule 3.2: Reusable Socket Connection Pool
* When a virtual user makes multiple requests, do not open a new network connection every single time.
* Use HTTP `Keep-Alive` to reuse existing TCP and SSL/TLS connections.
* Cache DNS lookups in memory for 60 seconds so the laptop does not waste time and resources asking DNS servers for the same IP address repeatedly.
* This avoids "socket exhaustion" (where Windows or Linux runs out of temporary network ports).

---

### Rule 3.3: Chunked Streaming & Immediate Discard (Zero-Buffering)
When testing a website, downloading a 2MB page 1,000 times would fill RAM with 2,000MB (2GB) of data in seconds.

1. **Never Save Full Pages in RAM**: The load engine must never load the entire response body into memory strings or byte arrays.
2. **Read Small Chunks and Throw Away**:
   * Read response headers (status code, content type, latency).
   * Read the incoming body in tiny 4KB to 8KB chunks.
   * Add the size of the chunk to a total byte counter.
   * Immediately discard the chunk so Python can free the memory instantly.
3. **Infinite Stream Guard (10MB Hard Cap)**:
   * A broken server or slowloris stream could send endless data. If any single response body exceeds **10 MB**, the worker immediately terminates the stream, logs it as `OVERSIZED_RESPONSE`, and frees the socket.

```python
# APPROVED ZERO-BUFFERING PATTERN (Python aiohttp)
MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB hard cap

async with session.get(target_url) as response:
    status = response.status
    total_bytes = 0
    # Stream small chunks and throw them away immediately
    async for chunk in response.content.iter_chunked(4096):
        total_bytes += len(chunk)
        if total_bytes > MAX_RESPONSE_BYTES:
            record_metric(status, latency_ms, total_bytes, warning="OVERSIZED_RESPONSE")
            break
    # Record metrics in memory (latency, status, bytes)
    record_metric(status, latency_ms, total_bytes)
```

---

### Rule 3.4: Mini Error Snapshot (First 512 Bytes Only)
When the target website returns an error (`404`, `500`, `502`, etc.), developers want to know what went wrong.
* To save memory, save **only the first 512 bytes** of the error message to show in the UI.
* Discard everything past the first 512 bytes.
* Never save response bodies for successful `200 OK` requests.

---

### Rule 3.5: One-Test-at-a-Time Queue Lock (With Abandoned Test Eviction)
To protect the laptop or 512MB cloud server from being overwhelmed by multiple users clicking "Start Test" at the same time:
* The backend enforces an `asyncio.Lock()` execution queue.
* **Only 1 active load test runs at any given time**.
* If a second test is requested, it is placed in a `QUEUED` waiting state and displays an estimated wait time based on how many seconds are left on the running test.
* **Abandoned Queue Eviction**: Queued jobs must maintain an active client ping (via WebSocket/SSE). If a user closes their tab and sends no ping for **30 seconds**, their queued test is automatically cancelled to prevent phantom runs.

```python
# ENFORCED QUEUE LOCK WITH HEARTBEAT CHECK
active_test_lock = asyncio.Lock()

async def start_load_test(test_request):
    if active_test_lock.locked():
        return {"status": "QUEUED", "message": "Another test is currently running. You are in queue."}
    
    async with active_test_lock:
        return await execute_engine(test_request)
```

---

### Rule 3.6: Live Speed Dashboard Memory Cap (`< 5 MB`)
* Never store millions of individual request objects in memory.
* Instead, summarize the data live using fixed-size memory buckets (`HdrHistogram` or reservoir sampling) to calculate:
  * Current Requests Per Second (RPS)
  * Status code counts (`200`, `404`, `500`, etc.)
  * Live response speeds: `p50` (median), `p90`, `p95`, and `p99` (tail speed)
* The telemetry buffer uses circular ring buffers that hold only the latest 1-second interval frames, consuming less than 5 MB of RAM total.

---

### Rule 3.7: Operating System File Descriptor Check (Windows & Linux Safe)
Every network socket opened on your computer uses an Operating System "File Descriptor".
* At startup, Pusher checks the computer's open file limit using platform-safe code:

```python
import sys

def get_safe_concurrency_ceiling(requested_vus: int) -> int:
    if sys.platform == "win32":
        # Windows handles socket pools safely via winloop/asyncio up to 2048 sockets
        max_sockets = 2048
    else:
        # Linux / macOS POSIX file descriptor check
        import resource
        soft_limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        max_sockets = soft_limit

    # Reserve 30% safety buffer for OS, browser, and database pipes
    safe_max_vus = int(max_sockets * 0.70)
    return min(requested_vus, safe_max_vus)
```

* If a beginner asks for 1,000 users but the laptop allows only 512 open files, Pusher automatically caps concurrency to a safe number (e.g., 350 users) and explains why in simple English, preventing a sudden `Too many open files` crash.

---

## 4. Memory Verification Checklist
Before approving any load engine code, confirm:
- [ ] RAM usage stays under 250MB when running 1,000 concurrent requests.
- [ ] No browser packages (Playwright, Puppeteer, Selenium) are installed or imported.
- [ ] Only 1 load test runs at a time using the single-test queue lock.
- [ ] Response bodies are read in small chunks and discarded immediately (10MB stream ceiling enforced).
- [ ] Error messages are trimmed to the first 512 bytes.
- [ ] Cross-platform file descriptor check works on Windows without raising `AttributeError`.
- [ ] Total disk space used by the project stays well under 1GB with zero request logging to disk.
