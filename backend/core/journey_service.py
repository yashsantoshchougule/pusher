"""
Journey Service for Multi-Step Sequential API Testing:
- In-memory Journey Store with pre-configured 3-step Sandbox Flow
- Same-Origin SSRF Step Validator
- 1-VU Dry-Run Validator with First-4KB Token Extraction and Interpolation
"""

import json
import time
import urllib.parse
import httpx
from pydantic import BaseModel, Field

from backend.core.target_service import validate_target_url, target_store


class JourneyStepModel(BaseModel):
    step_id: int | str
    name: str = Field(..., min_length=1, max_length=100)
    method: str = Field("GET", pattern="^(GET|POST|PUT|DELETE|PATCH)$")
    path: str = Field(..., min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    body: str | None = None
    expected_status: int = 200
    extract_json_key: str | None = None


DEFAULT_SANDBOX_STEPS = [
    {
        "step_id": 1,
        "name": "Step 1: Authenticate & Issue Token",
        "method": "POST",
        "path": "/api/sandbox/login",
        "headers": {"Content-Type": "application/json"},
        "body": '{"email": "loadtest@pusher.internal", "password": "secure_sandbox_key"}',
        "expected_status": 200,
        "extract_json_key": "token",
    },
    {
        "step_id": 2,
        "name": "Step 2: Fetch Catalog",
        "method": "GET",
        "path": "/api/sandbox/items",
        "headers": {"Authorization": "Bearer {{token}}"},
        "body": "",
        "expected_status": 200,
        "extract_json_key": None,
    },
    {
        "step_id": 3,
        "name": "Step 3: Submit High-Concurrency Checkout",
        "method": "POST",
        "path": "/api/sandbox/checkout",
        "headers": {"Authorization": "Bearer {{token}}", "Content-Type": "application/json"},
        "body": '{"item_id": "ITEM-9065", "quantity": 1}',
        "expected_status": 200,
        "extract_json_key": None,
    },
]


class JourneyStore:
    def __init__(self):
        self.steps: list[dict] = [dict(s) for s in DEFAULT_SANDBOX_STEPS]
        self.use_journey: bool = False
        self.last_dry_run_results: list[dict] = []
        self.last_dry_run_timestamp: str | None = None

    def get_journey(self) -> dict:
        return {
            "steps": self.steps,
            "use_journey": self.use_journey,
            "dry_run_results": self.last_dry_run_results,
            "dry_run_timestamp": self.last_dry_run_timestamp,
        }

    def save_journey(self, steps: list[dict], use_journey: bool = False) -> None:
        self.steps = steps[:10]  # Cap at 10 steps
        self.use_journey = use_journey


journey_store = JourneyStore()


def validate_journey_steps(
    steps: list[dict],
    active_target_url: str | None = None,
    is_sandbox: bool = False,
) -> tuple[bool, str | None]:
    """
    Enforces Same-Origin SSRF protection for each step in the chain.
    - Relative paths (starting with '/') are safe and inherit the verified target's origin.
    - Full URLs must match the verified target's origin exactly.
    - External cross-origin or private network URLs are strictly rejected.
    """
    if not steps:
        return False, "Journey must contain at least 1 step."

    if len(steps) > 10:
        return False, "Journey exceeds maximum limit of 10 steps."

    target = active_target_url or target_store.target_url or "http://127.0.0.1:8000"
    target_parsed = urllib.parse.urlparse(target)
    target_origin = f"{target_parsed.scheme}://{target_parsed.netloc}".lower()

    for idx, s in enumerate(steps, 1):
        path = s.get("path", "").strip()
        if not path:
            return False, f"Step {idx} has an empty endpoint path."

        # If full URL is provided, verify origin matches
        if path.startswith("http://") or path.startswith("https://"):
            step_parsed = urllib.parse.urlparse(path)
            step_origin = f"{step_parsed.scheme}://{step_parsed.netloc}".lower()

            if is_sandbox and ("/api/sandbox/" in path or "sandbox.pusher.local" in step_origin):
                continue

            if step_origin != target_origin:
                return False, f"SSRF Blocked: Step {idx} points to '{step_origin}', which does not match verified target origin '{target_origin}'."

            # Run SSRF IP validation on host
            valid, msg, _ = validate_target_url(path, is_sandbox=is_sandbox)
            if not valid:
                return False, f"Step {idx} SSRF violation: {msg}"
        elif not path.startswith("/"):
            return False, f"Step {idx} path must begin with '/' or be a valid full URL."

    return True, None


async def execute_dry_run(
    steps: list[dict],
    base_url: str = "http://127.0.0.1:8000",
    guard_id: str = "PG-ACTIVE",
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """
    1-VU Dry-Run Validator:
    Executes each step in sequence, extracting variables (like {{token}}) from the first
    4 KB chunk into a local context, asserting expected status codes, and measuring latency.
    """
    results = []
    context: dict[str, str] = {}

    own_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)
        own_client = True

    try:
        for s in steps:
            step_id = s.get("step_id", len(results) + 1)
            name = s.get("name", f"Step {step_id}")
            method = s.get("method", "GET").upper()
            raw_path = s.get("path", "")
            expected_status = s.get("expected_status", 200)
            extract_key = s.get("extract_json_key")

            # Interpolate path
            resolved_path = raw_path
            for k, v in context.items():
                resolved_path = resolved_path.replace(f"{{{{{k}}}}}", str(v))

            if resolved_path.startswith("http://") or resolved_path.startswith("https://"):
                url = resolved_path
            else:
                clean_base = base_url.rstrip("/")
                clean_path = resolved_path.lstrip("/")
                url = f"{clean_base}/{clean_path}"

            # Interpolate headers
            headers = {"X-Pusher-Guard-ID": guard_id, "User-Agent": "Pusher-DryRun/1.0"}
            raw_headers = s.get("headers") or {}
            for hk, hv in raw_headers.items():
                val = str(hv)
                for ck, cv in context.items():
                    val = val.replace(f"{{{{{ck}}}}}", str(cv))
                headers[hk] = val

            # Interpolate body
            body_content = s.get("body")
            if body_content:
                for ck, cv in context.items():
                    body_content = body_content.replace(f"{{{{{ck}}}}}", str(cv))

            t0 = time.perf_counter()
            passed = False
            status_code = 0
            error_msg = None
            extracted_val = None

            try:
                # 4 KB chunk discard streaming execution
                async with client.stream(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body_content.encode("utf-8") if body_content else None,
                ) as resp:
                    status_code = resp.status_code
                    first_chunk = b""
                    async for chunk in resp.aiter_bytes(chunk_size=4096):
                        if not first_chunk:
                            first_chunk = chunk
                        # Discard subsequent chunks immediately

                latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)

                if status_code == expected_status or (expected_status == 200 and status_code in (200, 201)):
                    passed = True
                else:
                    error_msg = f"Expected status {expected_status}, received {status_code}"

                # Extract JSON token from first 4 KB chunk if requested
                if passed and extract_key and first_chunk:
                    try:
                        parsed_json = json.loads(first_chunk.decode("utf-8", errors="ignore"))
                        if isinstance(parsed_json, dict) and extract_key in parsed_json:
                            extracted_val = str(parsed_json[extract_key])
                            context[extract_key] = extracted_val
                    except Exception as e:
                        error_msg = f"Failed to extract '{extract_key}' from response: {str(e)}"
                        passed = False

            except Exception as e:
                latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
                passed = False
                error_msg = str(e)

            results.append({
                "step_id": step_id,
                "name": name,
                "method": method,
                "path": raw_path,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "passed": passed,
                "extracted_var": extract_key if extracted_val else None,
                "error": error_msg,
            })

            # If a step fails in dry run, stop subsequent steps
            if not passed:
                break

    finally:
        if own_client:
            await client.aclose()

    journey_store.last_dry_run_results = results
    journey_store.last_dry_run_context = context
    journey_store.last_dry_run_timestamp = time.strftime("%H:%M:%S")
    return results
