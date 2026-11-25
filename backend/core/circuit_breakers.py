from collections import deque


WAF_HEADERS = {"cf-ray", "cf-chl-bypass", "x-amzn-errortype", "x-akamai-transformed", "x-datadome"}
WAF_MARKERS = (b"cloudflare ray id", b"attention required!", b"aws waf", b"access denied")
MAX_ERROR_PCT_CAP = 25
MAX_P95_CEILING_MS = 8000


class CircuitBreakers:
    def __init__(self, error_limit: float, latency_limit: float):
        self.error_limit = min(error_limit, MAX_ERROR_PCT_CAP)
        self.latency_limit = min(latency_limit, MAX_P95_CEILING_MS)
        self.consecutive_5xx = 0
        self.responses = deque()
        self.window_5xx = 0
        self.rate_limits = deque()
        self.timings = deque()

    def is_waf_headers(self, headers) -> bool:
        return bool(WAF_HEADERS.intersection(headers))

    def observe_status(self, now, status, headers):
        is_failure = (500 <= status < 600) or status == 0
        self.consecutive_5xx = self.consecutive_5xx + 1 if is_failure else 0
        if self.consecutive_5xx >= 5:
            return "5 consecutive connection failures" if status == 0 else "5 consecutive server failures"
        self.responses.append((now, is_failure))
        self.window_5xx += is_failure
        while self.responses and now - self.responses[0][0] > 5:
            _, expired = self.responses.popleft()
            self.window_5xx -= expired
        if len(self.responses) >= 20 and 100 * self.window_5xx / len(self.responses) > self.error_limit:
            return "rolling server error threshold"
        if status == 403 and self.is_waf_headers(headers):
            return "firewall blocked the request"
        if status == 429:
            self.rate_limits.append(now)
            while now - self.rate_limits[0] > 3:
                self.rate_limits.popleft()
            if len(self.rate_limits) >= 3:
                return "rate limit: 3 responses in 3 seconds"
        return None

    def observe_preview(self, status, body):
        if status == 403 and any(marker in body.lower() for marker in WAF_MARKERS):
            return "firewall blocked the request"
        return None

    def observe_timing(self, now, latency_ms, timed_out):
        self.timings.append((now, latency_ms, timed_out))

    def timing_reason(self, now):
        while self.timings and now - self.timings[0][0] > 10:
            self.timings.popleft()
        if len(self.timings) < 20:
            return None
        if sum(timed_out for _, _, timed_out in self.timings) / len(self.timings) > 0.30:
            return "more than 30% of requests timed out"
        latencies = sorted(latency for _, latency, _ in self.timings)
        p95_idx = max(0, (len(latencies) * 95 + 99) // 100 - 1)
        if latencies[p95_idx] > self.latency_limit:
            return "rolling p95 latency threshold"
        return None
