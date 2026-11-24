from collections import deque


WAF_HEADERS = {"cf-ray", "cf-chl-bypass", "x-amzn-errortype", "x-akamai-transformed", "x-datadome"}
WAF_MARKERS = (b"cloudflare ray id", b"attention required!", b"aws waf", b"access denied")
MAX_P95_CEILING_MS = 8000


class CircuitBreakers:
    def __init__(self, error_limit: float, latency_limit: float):
        self.error_limit = min(error_limit, 25)
        self.latency_limit = min(latency_limit, MAX_P95_CEILING_MS)
        self.consecutive_5xx = 0
        self.responses = deque()
        self.window_5xx = 0
        self.rate_limits = deque()
        self.timings = deque()

    def observe_status(self, now, status, headers):
        is_5xx = 500 <= status < 600
        self.consecutive_5xx = self.consecutive_5xx + 1 if is_5xx else 0
        if self.consecutive_5xx >= 5:
            return "5 consecutive server failures"
        self.responses.append((now, is_5xx))
        self.window_5xx += is_5xx
        while self.responses and now - self.responses[0][0] > 5:
            _, expired = self.responses.popleft()
            self.window_5xx -= expired
        if len(self.responses) >= 20 and 100 * self.window_5xx / len(self.responses) > self.error_limit:
            return "rolling server error threshold"
        if status == 403 and WAF_HEADERS.intersection(headers):
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
        if latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] > self.latency_limit:
            return "rolling p95 latency threshold"
        return None
